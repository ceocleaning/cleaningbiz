from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta
import uuid
import json
from square.client import Client
from django.db.models import Q
import logging
from django.db import transaction

from accounts.models import Business
from .models import BusinessSubscription, BillingHistory, SubscriptionPlan, UsageTracker, SubscriptionRenewalLog
from saas.models import PlatformSettings

logger = logging.getLogger(__name__)

def process_subscription_renewals():
    """
    Daily task to process subscription renewals.
    
    This function:
    1. Finds all active subscriptions that expire within the next day
    2. Attempts to charge the saved card for each business
    3. Creates a new subscription period on successful payment
    4. Sends email notifications for successful and failed payments
    5. Records all transactions in the BillingHistory
    """
    print("Starting subscription renewal process")

    
    
    # Get subscriptions expiring within the next day
    tomorrow = timezone.now() + timedelta(days=1)

    trial_plans = BusinessSubscription.objects.filter(
        plan__plan_type='trial',
        end_date__lte=timezone.now()
    )
    
    for plan in trial_plans:
        plan.is_active = False
        plan.status = 'ended'
        plan.save()
    
    # Find subscriptions that:
    # 1. Are marked as active in the database
    # 2. Have status 'active' or 'past_due'
    # 3. End date is within the next day (expiring soon)
    subscriptions_to_renew = BusinessSubscription.objects.filter(
        is_active=True,
        plan__plan_type='paid',
        end_date__lte=tomorrow
    ).filter(
        Q(status='past_due') | Q(status='active')
    ).exclude(
        plan__plan_tier='trial'
    )
    
    print(f"Found {subscriptions_to_renew.count()} subscriptions to renew")

    platform_settings = PlatformSettings.objects.first()
    
    # Initialize Square client
    square_client = Client(
        access_token=platform_settings.square_access_token,
        environment=platform_settings.square_environment
    )
    
    for subscription in subscriptions_to_renew:
        business = subscription.business
        current_plan = subscription.plan
        
        # Check if there's a plan change scheduled
        next_plan = None
        if subscription.next_plan_id:
            try:
                next_plan = SubscriptionPlan.objects.get(id=subscription.next_plan_id)
                print(f"Plan change detected for {business.businessName}: {current_plan.name} -> {next_plan.name}")
            except SubscriptionPlan.DoesNotExist:
                print(f"Next plan with ID {subscription.next_plan_id} not found for {business.businessName}")
                next_plan = None
        
        # Use the next plan if available, otherwise use the current plan
        plan_to_use = next_plan if next_plan else current_plan
        
        # Handle free plans (zero price) without payment processing
        if plan_to_use.price == 0:
            print(f"Free plan detected for {business.businessName} - Plan: {plan_to_use.name}. Skipping payment processing.")
            
            # Create a mock payment result for the free plan
            free_plan_result = {
                'success': True,
                'message': 'Free plan - no payment required',
                'payment_id': str(uuid.uuid4()),  # Generate a UUID as a placeholder
                'card_details': {'card': {'last_4': 'FREE'}}
            }
            
            # Handle the renewal directly
            _handle_successful_renewal(business, subscription, plan_to_use, free_plan_result, square_client)
            continue
            
        # Skip if business doesn't have a saved card (for paid plans)
        if not business.square_card_id or not business.square_customer_id:
            print(f"No saved card for {business.businessName}, sending notification")
            _send_no_card_notification(business, subscription, plan_to_use)
            continue
        
        # Process the renewal payment for paid plans
        renewal_result = _process_renewal_payment(business, subscription, plan_to_use, square_client)
        
        if renewal_result['success']:
            _handle_successful_renewal(business, subscription, plan_to_use, renewal_result, square_client)
        else:
            _handle_failed_renewal(business, subscription, plan_to_use, renewal_result)


def _process_renewal_payment(business, subscription, plan, square_client):
    """
    Process a renewal payment using Square.
    
    Args:
        business: The Business model instance
        subscription: The BusinessSubscription model instance
        plan: The SubscriptionPlan to renew with
        square_client: Initialized Square client
        
    Returns:
        dict: Result of the payment attempt with keys:
            - success: Boolean indicating if payment was successful
            - message: Description of the result
            - payment_id: Square payment ID (if successful)
            - error: Error details (if failed)
    """
    print(f"Processing renewal payment for {business.businessName} - Plan: {plan.name}")
    
    try:
        # Create a unique idempotency key for this payment
        idempotency_key = str(uuid.uuid4())

        # Apply yearly discount (20% off annual price)
        original_price = plan.price
        final_price = original_price
        if plan.billing_cycle == 'yearly':
            final_price = original_price * 0.8
        
        # Check for coupon - prioritize new_coupon over coupon_used
        coupon = None
        if subscription.new_coupon:
            # Use new_coupon if available (scheduled for this billing cycle)
            coupon = subscription.new_coupon
            print(f"Using new_coupon: {coupon.code} for {business.businessName}")
        elif subscription.coupon_used:
            # Fall back to coupon_used if no new_coupon is scheduled
            coupon = subscription.coupon_used
            print(f"Using coupon_used: {coupon.code} for {business.businessName}")
        
        discount_applied = False
        # original_price already set above (line 142), will be updated if coupon applies
        coupon_code = None
        discount_amount = 0
        
        # Apply coupon if it exists, is of type per_user, and is valid for the user
        if coupon and coupon.limit_type == 'per_user' and business.user:
            if coupon.is_valid_for_user(business.user):
                # Apply the coupon discount
                coupon_code = coupon.code
                original_price = final_price
                final_price = coupon.apply_discount(final_price)
                discount_amount = float(original_price) - float(final_price)
                discount_applied = True
                print(f"Applied coupon {coupon.code} for user {business.user.username}, discount amount: {discount_amount}")
                
                # If we used new_coupon, move it to coupon_used and clear new_coupon
                if subscription.new_coupon == coupon:
                    subscription.coupon_used = coupon
                    subscription.new_coupon = None
                    subscription.save()
                    print(f"Moved new_coupon to coupon_used for {business.businessName}")

        if final_price <= 0:
            print(f"Final price is zero for {business.businessName} after coupon {coupon.code}. Skipping payment.")
            return {
                'success': True,
                'message': 'Coupon applied - no payment required',
                'payment_id': str(uuid.uuid4()),  # mock id
                'card_details': {'card': {'last_4': 'FREE'}},
                'coupon_applied': True,
                'coupon_code': coupon.code,
                'original_price': original_price,
                'final_price': 0,
                'discount_amount': discount_amount
            }
        
        # Calculate amount in cents
        amount_money = {
            "amount": int(float(final_price) * 100),
            "currency": "USD"
        }
        
        # Create the payment request
        payment_body = {
            "idempotency_key": idempotency_key,
            "amount_money": amount_money,
            "autocomplete": True,
            "note": f"Automatic renewal: {plan.name} ({plan.billing_cycle}){' with coupon discount' if discount_applied else ''}",
            "payment_method_types": ["CARD"],
            "source_id": business.square_card_id,
            "customer_id": business.square_customer_id
        }
        
        # Process the payment
        payment_result = square_client.payments.create_payment(
            body=payment_body
        )
        
        if payment_result.is_success():
            payment = payment_result.body['payment']
            return {
                'success': True,
                'message': 'Payment processed successfully',
                'payment_id': payment['id'],
                'card_details': payment.get('card_details', {}),
                'coupon_applied': discount_applied,
                'coupon_code': coupon_code,
                'original_price': original_price,
                'final_price': final_price,
                'discount_amount': discount_amount
            }
        else:
            return {
                'success': False,
                'message': 'Payment processing failed',
                'error': payment_result.errors
            }
            
    except Exception as e:
        print(f"Error processing renewal payment: {str(e)}")
        return {
            'success': False,
            'message': 'Exception during payment processing',
            'error': str(e)
        }


def _handle_successful_renewal(business, old_subscription, plan, payment_result, square_client):
    """
    Handle a successful subscription renewal.
    
    Args:
        business: The Business model instance
        old_subscription: The previous BusinessSubscription model instance
        plan: The SubscriptionPlan that was renewed
        payment_result: The successful payment result
        square_client: Initialized Square client
    """
    print(f"Successful renewal for {business.businessName} - Plan: {plan.name}")
    
    billing_record = None
    new_subscription = None
    
    try:
        # Calculate new end date based on billing cycle
        if plan.billing_cycle == 'monthly':
            new_end_date = timezone.now() + timedelta(days=30)
        else:  # yearly
            new_end_date = timezone.now() + timedelta(days=365)
        
        # Determine renewal type
        renewal_type = 'automatic'
        if old_subscription.plan.id != plan.id:
            # Plan change detected
            if plan.price > old_subscription.plan.price:
                renewal_type = 'upgrade'
            elif plan.price < old_subscription.plan.price:
                renewal_type = 'downgrade'
            else:
                renewal_type = 'plan_change'
        
        # Mark the old subscription as inactive
        old_subscription.is_active = False
        old_subscription.status = 'ended'
        old_subscription.save()
        
        # Create a new subscription
        new_subscription = BusinessSubscription.objects.create(
            business=business,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=new_end_date,
            next_billing_date=new_end_date,
            square_subscription_id=payment_result['payment_id'],
            square_customer_id=business.square_customer_id,
            is_active=True
        )
        
        # Record the successful payment in billing history
        card_details = payment_result.get('card_details', {})
        card = card_details.get('card', {})
        last4 = card.get('last_4', '****')
        
        # Get coupon details from payment result if available
        coupon_applied = payment_result.get('coupon_applied', False)
        coupon_code = payment_result.get('coupon_code', None)
        discount_amount = payment_result.get('discount_amount', 0)
        final_price = payment_result.get('final_price', plan.price)
        
        # Determine status based on payment result
        is_free_plan = payment_result.get('message') == 'Free plan - no payment required'
        
        # Create billing history record with coupon details
        billing_record = BillingHistory.objects.create(
            business=business,
            subscription=new_subscription,
            amount=final_price,  # Use the final price after coupon discount
            status='paid',
            billing_date=timezone.now(),
            square_payment_id=payment_result['payment_id'],
            details={
                'renewal_type': renewal_type,
                'card_last4': last4,
                'plan_name': plan.name,
                'billing_cycle': plan.billing_cycle,
                'coupon_code': coupon_code if coupon_code else "No Coupon",
                'discount_amount': discount_amount,
                'coupon_applied': coupon_applied,
                'original_price': payment_result.get('original_price', plan.price)
            }
        )
        
        # Create comprehensive renewal log
        log_status = 'free_plan' if is_free_plan else 'success'
        
        SubscriptionRenewalLog.objects.create(
            business=business,
            subscription=new_subscription,
            status=log_status,
            renewal_type=renewal_type,
            old_plan=old_subscription.plan,
            new_plan=plan,
            amount_charged=final_price,
            square_payment_id=payment_result['payment_id'],
            card_last_4=last4,
            billing_record=billing_record,
            error_message=None,
            error_code=None,
            details={
                'payment_message': payment_result.get('message', 'Payment processed successfully'),
                'coupon_applied': coupon_applied,
                'coupon_code': coupon_code,
                'discount_amount': str(discount_amount),
                'original_price': str(payment_result.get('original_price', plan.price)),
                'final_price': str(final_price),
                'old_plan_name': old_subscription.plan.name,
                'new_plan_name': plan.name,
                'old_plan_price': str(old_subscription.plan.price),
                'new_plan_price': str(plan.price),
                'billing_cycle': plan.billing_cycle,
                'start_date': new_subscription.start_date.isoformat(),
                'end_date': new_subscription.end_date.isoformat(),
                'notification_sent': True,
            }
        )
        
        # Send success notification
        _send_successful_renewal_notification(business, new_subscription, plan, last4)
        
        print(f"Renewal completed successfully for {business.businessName}")
        logger.info(f"Successfully renewed subscription for {business.businessName} - {renewal_type} from {old_subscription.plan.name} to {plan.name}")
        
    except Exception as e:
        print(f"Error handling successful renewal: {str(e)}")
        logger.error(f"Error handling successful renewal for {business.businessName}: {str(e)}")
        
        # Create error log even in success handler if something goes wrong
        try:
            SubscriptionRenewalLog.objects.create(
                business=business,
                subscription=new_subscription if new_subscription else old_subscription,
                status='failed',
                renewal_type='automatic',
                old_plan=old_subscription.plan,
                new_plan=plan,
                amount_charged=None,
                square_payment_id=payment_result.get('payment_id'),
                card_last_4=None,
                billing_record=billing_record,
                error_message=f"Error in success handler: {str(e)}",
                error_code='HANDLER_ERROR',
                details={
                    'error_type': type(e).__name__,
                    'error_traceback': str(e),
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to create error log: {str(log_error)}")



def _handle_failed_renewal(business, subscription, plan, payment_result):
    """
    Handle a failed subscription renewal.
    
    Args:
        business: The Business model instance
        subscription: The BusinessSubscription model instance
        plan: The SubscriptionPlan that was attempted to renew
        payment_result: The failed payment result
    """
    print(f"Failed renewal for {business.businessName} - Plan: {plan.name}")
    
    billing_record = None
    
    try:
        # Record the failed payment in billing history
        error_details = payment_result.get('error', 'Unknown error')
        if isinstance(error_details, list):
            error_message = '; '.join([e.get('detail', str(e)) for e in error_details])
            error_code = error_details[0].get('code', 'UNKNOWN') if error_details else 'UNKNOWN'
        else:
            error_message = str(error_details)
            error_code = 'PAYMENT_FAILED'
        
        billing_record = BillingHistory.objects.create(
            business=business,
            subscription=subscription,
            amount=plan.price,
            status='failed',
            billing_date=timezone.now(),
            details={
                'renewal_type': 'automatic',
                'error': error_message,
                'plan_name': plan.name,
                'billing_cycle': plan.billing_cycle
            }
        )
        
        # Create comprehensive renewal failure log
        SubscriptionRenewalLog.objects.create(
            business=business,
            subscription=subscription,
            status='failed',
            renewal_type='automatic',
            old_plan=subscription.plan,
            new_plan=plan,
            amount_charged=None,
            square_payment_id=None,
            card_last_4=None,
            billing_record=billing_record,
            error_message=error_message,
            error_code=error_code,
            details={
                'payment_message': payment_result.get('message', 'Payment failed'),
                'error_details': str(error_details),
                'plan_name': plan.name,
                'plan_price': str(plan.price),
                'billing_cycle': plan.billing_cycle,
                'subscription_status': subscription.status,
                'subscription_end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                'notification_sent': True,
            }
        )
        
        # Update subscription status based on expiration
        today = timezone.now().date()
        grace_period_end = today - timedelta(days=2)  # 2 days after expiration
        
        if subscription.end_date.date() < grace_period_end:
            # Grace period has passed - mark as ended
            subscription.is_active = False
            subscription.status = 'ended'
            subscription.save()
        elif subscription.end_date.date() < today:
            # Just expired but within grace period - mark as past_due
            subscription.status = 'past_due'
            subscription.save()
        
        # Send failure notification
        try:
            _send_failed_renewal_notification(business, subscription, plan, error_message)
        except Exception as e:
            print(f"Error sending failed renewal notification: {str(e)}")
            logger.error(f"Error sending failed renewal notification: {str(e)}")
        
        print(f"Recorded failed renewal for {business.businessName}")
        logger.warning(f"Failed renewal for {business.businessName} - {error_message}")
        
    except Exception as e:
        print(f"Error handling failed renewal: {str(e)}")
        logger.error(f"Error handling failed renewal for {business.businessName}: {str(e)}")
        
        # Create error log even if the failure handler fails
        try:
            SubscriptionRenewalLog.objects.create(
                business=business,
                subscription=subscription,
                status='failed',
                renewal_type='automatic',
                old_plan=subscription.plan,
                new_plan=plan,
                amount_charged=None,
                square_payment_id=None,
                card_last_4=None,
                billing_record=billing_record,
                error_message=f"Error in failure handler: {str(e)}",
                error_code='HANDLER_ERROR',
                details={
                    'error_type': type(e).__name__,
                    'error_traceback': str(e),
                    'original_error': str(payment_result.get('error', 'Unknown')),
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to create error log: {str(log_error)}")



def _send_successful_renewal_notification(business, subscription, plan, card_last4, is_upgrade=False):
    """Send email notification for successful subscription renewal/upgrade"""
    try:
        subject = f"Subscription {'Upgraded' if is_upgrade else 'Renewed'}: {plan.name} Plan"
        
        message = f"""
Hello {business.businessName},

Your subscription has been {'upgraded' if is_upgrade else 'renewed'} to the {plan.name} plan.

Subscription Details:
- Plan: {plan.name} ({plan.get_billing_cycle_display()})
- Amount: ${plan.price}
- Payment Method: Card ending in {card_last4}
- Start Date: {subscription.start_date.strftime('%Y-%m-%d')}
- Next Billing Date: {subscription.end_date.strftime('%Y-%m-%d')}

{'This upgrade was processed because your current plan\'s usage reached 90% of its limits.' if is_upgrade else ''}

Thank you for your continued business!

Best regards,
The CleaningBizAI Team
        """
        
        # Send the email
        if business.user and business.user.email:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.user.email],
                fail_silently=False
            )
            logger.info(f"Sent {'upgrade' if is_upgrade else 'renewal'} notification to {business.user.email}")
        else:
            logger.warning(f"No email address found for {business.businessName}")
            
    except Exception as e:
        logger.error(f"Error sending {'upgrade' if is_upgrade else 'renewal'} notification: {str(e)}")


def _send_failed_renewal_notification(business, subscription, plan, error_message, is_upgrade=False):
    """Send email notification for failed subscription renewal/upgrade"""
    try:
        subject = f"ACTION REQUIRED: Subscription {'Upgrade' if is_upgrade else 'Renewal'} Failed"
        
        message = f"""
Hello {business.businessName},

We were unable to process the {'upgrade' if is_upgrade else 'renewal'} payment for your {plan.name} plan subscription.

Subscription Details:
- Plan: {plan.name} ({plan.get_billing_cycle_display()})
- Amount: ${plan.price}
- Error: {error_message}

{'Your usage has reached 90% of your current plan\'s limits. ' if is_upgrade else ''}To avoid any service interruptions, please:

1. Check that your payment method is valid and has sufficient funds
2. Update your payment information in your account settings
3. Contact our support team if you need assistance

Your subscription will remain on the current plan until the payment issue is resolved.

For immediate assistance, please contact our support team at support@cleaningbizai.com

Best regards,
The CleaningBizAI Team
        """
        
        # Send the email
        if business.user and business.user.email:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.user.email],
                fail_silently=False
            )
            logger.info(f"Sent failed {'upgrade' if is_upgrade else 'renewal'} notification to {business.user.email}")
        else:
            logger.warning(f"No email address found for {business.businessName}")
            
    except Exception as e:
        logger.error(f"Error sending failed {'upgrade' if is_upgrade else 'renewal'} notification: {str(e)}")


def _send_no_card_notification(business, subscription, plan):
    """Send email notification when no card is available for automatic renewal"""
    
    billing_record = None
    
    try:
        # Prepare email content
        subject = f"ACTION REQUIRED: Update Payment Method for Subscription Renewal"
        
        message = f"""
Hello {business.businessName},

Your subscription to the {plan.name} plan is about to expire, but we don't have a payment method on file to process the automatic renewal.

Subscription Details:
- Plan: {plan.name} ({plan.get_billing_cycle_display()})
- Amount: ${plan.price}
- Expiration Date: {subscription.end_date.strftime('%Y-%m-%d')}

To avoid service interruption, please log in to your account and add a payment method as soon as possible.

If you need assistance, please contact our support team.

Best regards,
The CleaningBizAI Team
        """
        
        # Send the email
        notification_sent = False
        if business.user and business.user.email:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.user.email],
                fail_silently=False
            )
            print(f"Sent no card notification to {business.user.email}")
            notification_sent = True
            
            # Create a record in billing history
            billing_record = BillingHistory.objects.create(
                business=business,
                subscription=subscription,
                amount=plan.price,
                status='failed',
                billing_date=timezone.now(),
                details={
                    'renewal_type': 'automatic',
                    'error': 'No payment method on file',
                    'plan_name': plan.name,
                    'billing_cycle': plan.billing_cycle
                }
            )
        else:
            print(f"No email address found for {business.businessName}")
            logger.warning(f"No email address found for {business.businessName}")
        
        # Create comprehensive renewal log for no card scenario
        SubscriptionRenewalLog.objects.create(
            business=business,
            subscription=subscription,
            status='no_card',
            renewal_type='automatic',
            old_plan=subscription.plan,
            new_plan=plan,
            amount_charged=None,
            square_payment_id=None,
            card_last_4=None,
            billing_record=billing_record,
            error_message='No payment method on file',
            error_code='NO_CARD',
            details={
                'plan_name': plan.name,
                'plan_price': str(plan.price),
                'billing_cycle': plan.billing_cycle,
                'subscription_end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                'notification_sent': notification_sent,
                'has_square_customer_id': bool(business.square_customer_id),
                'has_square_card_id': bool(business.square_card_id),
                'user_email': business.user.email if business.user else None,
            }
        )
        
        logger.info(f"No card notification logged for {business.businessName}")
            
    except Exception as e:
        print(f"Error sending no card notification: {str(e)}")
        logger.error(f"Error sending no card notification for {business.businessName}: {str(e)}")
        
        # Create error log
        try:
            SubscriptionRenewalLog.objects.create(
                business=business,
                subscription=subscription,
                status='no_card',
                renewal_type='automatic',
                old_plan=subscription.plan,
                new_plan=plan,
                amount_charged=None,
                square_payment_id=None,
                card_last_4=None,
                billing_record=billing_record,
                error_message=f"Error sending no card notification: {str(e)}",
                error_code='NOTIFICATION_ERROR',
                details={
                    'error_type': type(e).__name__,
                    'error_traceback': str(e),
                }
            )
        except Exception as log_error:
            logger.error(f"Failed to create no card log: {str(log_error)}")



def schedule_subscription_renewals():
    """
    Schedule the subscription renewal task to run every 5 minutes for testing.
    This function should be called when Django starts.
    """
    from django_q.tasks import schedule
    from django_q.models import Schedule
    
    # Check if the task is already scheduled
    task_name = 'Subscription Renewals (Test)'
    second_task_name = 'Auto Upgrade Subscription'

    
    if not Schedule.objects.filter(name=second_task_name).exists():
        schedule(
            'subscription.tasks.auto_upgrade_subscription',
            name=second_task_name,
            schedule_type='D',  # Daily
            next_run=timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        )

        logger.info(f"Scheduled {second_task_name} to run every day at Midnight")



@transaction.atomic
def auto_upgrade_subscription():
    """
    Automatically upgrade a subscription to the next available plan when the current plan is nearing its end date.
    
    This function checks all active subscriptions and attempts to upgrade them to the next available plan.
    """
    logger.info("Starting auto-upgrade subscription process")
    
    # Get all active subscriptions
    businesses = Business.objects.filter(isActive=True, isApproved=True, auto_upgrade=True)
    logger.info(f"Found {businesses.count()} businesses with auto-upgrade enabled")
    platform_settings = PlatformSettings.objects.first()
    # Initialize Square client
    square_client = Client(
        access_token=platform_settings.square_access_token,
        environment=platform_settings.square_environment
    )

    for business in businesses:
        try:
            logger.info(f"Processing auto-upgrade for {business.businessName}")
            
            # Validate payment method
            if not business.square_card_id or not business.square_customer_id:
                logger.warning(f"No payment method found for {business.businessName}")
                continue

            active_subscription = business.active_subscription()
            if not active_subscription:
                logger.warning(f"No active subscription found for {business.businessName}")
                continue

            if not active_subscription.is_subscription_active():
                logger.warning(f"Subscription is not active for {business.businessName}")
                continue

            current_plan = active_subscription.plan
            
            # Get current usage summary
            usage_summary = UsageTracker.get_usage_summary(business=business)
            logger.info(f"Current usage for {business.businessName}: {usage_summary.get('usage_percentage', {})}")
            
            # Check if any usage metric has reached 90% of the limit
            should_upgrade = False
            for metric, percentage in usage_summary.get('usage_percentage', {}).items():
                if percentage >= 90:
                    should_upgrade = True
                    logger.info(f"Usage threshold reached for {metric} ({percentage}%)")
                    break
            
            if should_upgrade:
                # Get the next available plan with proper ordering
                plans = SubscriptionPlan.objects.filter(
                    is_active=True, 
                    billing_cycle=current_plan.billing_cycle
                ).order_by('price')  # Order by price to ensure we get the next tier

                next_plan = None
                for plan in plans:
                    # Check if this plan has higher limits in any category
                    if (plan.leads > current_plan.leads or 
                        plan.voice_minutes > current_plan.voice_minutes or
                        plan.sms_messages > current_plan.sms_messages or
                        plan.agents > current_plan.agents):
                        next_plan = plan
                        logger.info(f"Found upgrade plan: {plan.name}")
                        break
                   
                if next_plan:
                    # Process the payment using the existing function
                    payment_result = _process_renewal_payment(business, active_subscription, next_plan, square_client)
                    
                    if payment_result['success']:
                        # Handle successful renewal using existing function
                        _handle_successful_renewal(business, active_subscription, next_plan, payment_result, square_client)
                        logger.info(f"Successfully upgraded {business.businessName} from {current_plan.name} to {next_plan.name}")
                    else:
                        # Handle failed renewal using existing function
                        _handle_failed_renewal(business, active_subscription, next_plan, payment_result)
                       
                   
                else:
                    logger.info(f"No higher plan available for {business.businessName} to upgrade from {current_plan.name}")
            else:
                logger.info(f"No upgrade needed for {business.businessName} - usage below threshold")

        except Exception as e:
            logger.error(f"Error processing auto-upgrade for {business.businessName}: {str(e)}")
            continue  # Continue with next business even if one fails



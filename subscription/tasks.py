from django.utils import timezone
from django.conf import settings
from django.core.mail import send_mail
from datetime import timedelta
import uuid
import json
from square.client import Client
from django.db.models import Q

from accounts.models import Business
from subscription.models import BusinessSubscription, BillingHistory, SubscriptionPlan

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
    
    # Get tomorrow's date and 5 days ago
    tomorrow = timezone.now() + timedelta(days=1)
    five_days_ago = timezone.now() - timedelta(days=5)
    
    # Find subscriptions that:
    # 1. Are marked as active in the database
    # 2. Have status 'active' or 'past_due'
    # 3. End date is between 5 days ago and tomorrow
    subscriptions_to_renew = BusinessSubscription.objects.filter(
        is_active=True,
        end_date__lte=tomorrow,
        end_date__gte=five_days_ago
    ).filter(
        Q(status='past_due') | Q(status='active')
    )
    
    print(f"Found {subscriptions_to_renew.count()} subscriptions to renew")
    
    # Initialize Square client
    square_client = Client(
        access_token=settings.SQUARE_ACCESS_TOKEN,
        environment=settings.SQUARE_ENVIRONMENT
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
        
        # Skip if business doesn't have a saved card
        if not business.square_card_id or not business.square_customer_id:
            print(f"No saved card for {business.businessName}, sending notification")
            _send_no_card_notification(business, subscription, plan_to_use)
            continue
        
        # Process the renewal payment
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
        
        # Calculate amount in cents
        amount_money = {
            "amount": int(float(plan.price) * 100),
            "currency": "USD"
        }
        
        # Create the payment request
        payment_body = {
            "idempotency_key": idempotency_key,
            "amount_money": amount_money,
            "autocomplete": True,
            "note": f"Automatic renewal: {plan.name} ({plan.billing_cycle})",
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
                'card_details': payment.get('card_details', {})
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
    
    try:
        # Calculate new end date based on billing cycle
        if plan.billing_cycle == 'monthly':
            new_end_date = timezone.now() + timedelta(days=30)
        else:  # yearly
            new_end_date = timezone.now() + timedelta(days=365)
        
        # Mark the old subscription as inactive
        old_subscription.is_active = False
        old_subscription.status = 'cancelled'
        old_subscription.save()
        
        # Create a new subscription
        new_subscription = BusinessSubscription.objects.create(
            business=business,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=new_end_date,
            square_subscription_id=payment_result['payment_id'],
            square_customer_id=business.square_customer_id,
            is_active=True
        )
        
        # Record the successful payment in billing history
        card_details = payment_result.get('card_details', {})
        card = card_details.get('card', {})
        last4 = card.get('last_4', '****')
        
        billing_record = BillingHistory.objects.create(
            business=business,
            subscription=new_subscription,
            amount=plan.price,
            status='paid',
            billing_date=timezone.now(),
            square_payment_id=payment_result['payment_id'],
            details={
                'renewal_type': 'automatic',
                'card_last4': last4,
                'plan_name': plan.name,
                'billing_cycle': plan.billing_cycle
            }
        )
        
        # Send success notification
        _send_successful_renewal_notification(business, new_subscription, plan, last4)
        
        print(f"Renewal completed successfully for {business.businessName}")
        
    except Exception as e:
        print(f"Error handling successful renewal: {str(e)}")


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
    
    try:
        # Record the failed payment in billing history
        error_details = payment_result.get('error', 'Unknown error')
        if isinstance(error_details, list):
            error_message = '; '.join([e.get('detail', str(e)) for e in error_details])
        else:
            error_message = str(error_details)
        
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
        
        # Mark subscription as past_due
        subscription.status = 'past_due'
        subscription.save()
        
        # Send failure notification
        _send_failed_renewal_notification(business, subscription, plan, error_message)
        
        print(f"Recorded failed renewal for {business.businessName}")
        
    except Exception as e:
        print(f"Error handling failed renewal: {str(e)}")


def _send_successful_renewal_notification(business, subscription, plan, card_last4):
    """Send email notification for successful subscription renewal"""
    try:
        # Prepare email content
        subject = f"Subscription Renewed: {plan.name} Plan"
        
        message = f"""
Hello {business.businessName},

Your subscription to the {plan.name} plan has been automatically renewed.

Subscription Details:
- Plan: {plan.name} ({plan.get_billing_cycle_display()})
- Amount: ${plan.price}
- Payment Method: Card ending in {card_last4}
- Start Date: {subscription.start_date.strftime('%Y-%m-%d')}
- Next Billing Date: {subscription.end_date.strftime('%Y-%m-%d')}

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
            print(f"Sent successful renewal notification to {business.user.email}")
        else:
            print(f"No email address found for {business.businessName}")
            
    except Exception as e:
        print(f"Error sending successful renewal notification: {str(e)}")


def _send_failed_renewal_notification(business, subscription, plan, error_message):
    """Send email notification for failed subscription renewal"""
    try:
        # Prepare email content
        subject = f"ACTION REQUIRED: Subscription Payment Failed"
        
        message = f"""
Hello {business.businessName},

We were unable to process the automatic renewal payment for your {plan.name} plan subscription.

Subscription Details:
- Plan: {plan.name} ({plan.get_billing_cycle_display()})
- Amount: ${plan.price}
- Error: {error_message}

Your subscription is now in a past-due state. To avoid service interruption, please log in to your account and update your payment method as soon as possible.

If you need assistance, please contact our support team.

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
            print(f"Sent failed renewal notification to {business.user.email}")
        else:
            print(f"No email address found for {business.businessName}")
            
    except Exception as e:
        print(f"Error sending failed renewal notification: {str(e)}")


def _send_no_card_notification(business, subscription, plan):
    """Send email notification when no card is available for automatic renewal"""
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
        if business.user and business.user.email:
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[business.user.email],
                fail_silently=False
            )
            print(f"Sent no card notification to {business.user.email}")
            
            # Create a record in billing history
            BillingHistory.objects.create(
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
            
    except Exception as e:
        print(f"Error sending no card notification: {str(e)}")


def schedule_subscription_renewals():
    """
    Schedule the subscription renewal task to run every 5 minutes for testing.
    This function should be called when Django starts.
    """
    from django_q.tasks import schedule
    from django_q.models import Schedule
    
    # Check if the task is already scheduled
    task_name = 'Subscription Renewals (Test)'
    
    # Delete any existing task with this name to avoid duplicates
    Schedule.objects.filter(name=task_name).delete()
    
    # Schedule the task to run every 5 minutes
    schedule(
        'subscription.tasks.process_subscription_renewals',
        name=task_name,
        schedule_type='I',  # Minutes
        minutes=5,  # Every 5 minutes
        repeats=-1,  # Repeat indefinitely
        next_run=timezone.now() + timedelta(seconds=30)  # Start in 30 seconds
    )
    print(f"Scheduled {task_name} to run every 5 minutes for testing")

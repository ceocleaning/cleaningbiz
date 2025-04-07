from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.utils import timezone
from django.db import transaction
from django.conf import settings
from django.urls import reverse
from django.views.decorators.http import require_POST
from datetime import datetime, timedelta
import json
import uuid
from square.client import Client

from .models import SubscriptionPlan, BusinessSubscription, BillingHistory, Feature, Coupon, CouponUsage, UsageTracker
from accounts.models import Business
from usage_analytics.services.usage_service import UsageService

@login_required
def subscription_management(request):
    """View for managing subscriptions."""
    business = request.user.business_set.first()
    
    # Get current subscription
    try:
        subscription = business.active_subscription()
        payment_method = subscription.square_customer_id is not None if subscription else False
        
        # Get next plan information if available
        next_plan = None
        if subscription and subscription.next_plan_id:
            try:
                next_plan = SubscriptionPlan.objects.get(id=subscription.next_plan_id)
            except SubscriptionPlan.DoesNotExist:
                pass
    except BusinessSubscription.DoesNotExist:
        subscription = None
        payment_method = False
        next_plan = None
    
    # Get all available plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price').exclude(name='Trial Plan')

    trial_plan = SubscriptionPlan.objects.filter(is_active=True, name='Trial Plan').first()
    is_eligible_for_trial = False if BusinessSubscription.objects.filter(business=business, plan=trial_plan).exists() else True
    
    # Get usage summary for current month
    if subscription:
        usage_summary = UsageTracker.get_usage_summary(
            business=business,
            start_date=subscription.start_date,
            end_date=subscription.end_date
        )
    else:
        usage_summary = None
 
    
    # Get recent billing history
    billing_history = BillingHistory.objects.filter(
        business=business
    ).order_by('-billing_date')[:5]
    
    # Get card details from Square if available
    card_details = None
    customer_details = None
    if business.square_card_id and business.square_customer_id:
        try:
            # Initialize Square client
            square_client = Client(
                access_token=settings.SQUARE_ACCESS_TOKEN,
                environment=settings.SQUARE_ENVIRONMENT
            )
            
            # Retrieve the card details
            card_result = square_client.cards.retrieve_card(
                card_id=business.square_card_id
            )
            
            if card_result.is_success():
                card = card_result.body.get('card', {})
                card_details = {
                    'last4': card.get('last_4'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year'),
                    'card_brand': card.get('card_brand')
                }
                
            # Retrieve the customer details
            customer_result = square_client.customers.retrieve_customer(
                customer_id=business.square_customer_id
            )
            
            if customer_result.is_success():
                customer = customer_result.body.get('customer', {})
                created_at = datetime.strptime(customer.get('created_at'), '%Y-%m-%dT%H:%M:%S.%f%z')

            
                customer_details = {
                    'given_name': customer.get('given_name', ''),
                    'family_name': customer.get('family_name', ''),
                    'email': customer.get('email_address', ''),
                    'phone': customer.get('phone_number', ''),
                    'created_at': created_at
                }
        except Exception as e:
            # Log the error but don't crash
            print(f"Error retrieving card or customer details: {e}")
    
    context = {
        'subscription': subscription,
        'plans': plans,
        'trial_plan': trial_plan,
        'is_eligible_for_trial': is_eligible_for_trial,
        'usage_summary': usage_summary,
        'billing_history': billing_history,
        'next_plan': next_plan,
        'payment_method': payment_method,
        'business': business,
        'card_details': card_details,
        'customer_details': customer_details,
        'active_page': 'subscription',
        'title': 'Subscription Management'
    }
    
    return render(request, 'usage_analytics/subscription.html', context)

@login_required
def billing_history(request):
    """View for billing history."""
    business = request.user.business_set.first()
    
    # Get all billing records
    billing_records = BillingHistory.objects.filter(
        business=business
    ).order_by('-billing_date')
    
    # Calculate total billed for the current year
    current_year = timezone.now().year
    start_of_year = datetime(current_year, 1, 1, tzinfo=timezone.get_current_timezone())
    total_billed = BillingHistory.objects.filter(
        business=business,
        billing_date__gte=start_of_year,
        status='paid'
    ).aggregate(total=models.Sum('amount'))['total'] or 0
    
    # Get last payment
    last_payment = BillingHistory.objects.filter(
        business=business,
        status='paid'
    ).order_by('-billing_date').first()
    
    # Get current subscription for next billing info
    try:
        subscription = BusinessSubscription.objects.get(
            business=business,
            is_active=True
        )
        
        # Check if there's a next plan scheduled
        next_plan_price = subscription.plan.price
        if subscription.next_plan_id:
            try:
                next_plan = SubscriptionPlan.objects.get(id=subscription.next_plan_id)
                next_plan_price = next_plan.price
            except SubscriptionPlan.DoesNotExist:
                pass
        
        # Set next billing info
        next_billing = {
            'date': subscription.next_billing_date or subscription.end_date,
            'amount': next_plan_price
        }
        
        # Set current balance if subscription is past_due
        current_balance = 0.00
        if subscription.status == 'past_due':
            current_balance = float(next_plan_price)
            
    except BusinessSubscription.DoesNotExist:
        next_billing = {
            'date': None,
            'amount': 0
        }
        current_balance = 0.00
    
    # Get payment method info from Square
    payment_method = {
        'last4': '4242',
        'exp_month': '12',
        'exp_year': '2025',
        'card_brand': 'visa'
    }
    
    # Fetch actual card details from Square if available
    if business.square_card_id and business.square_customer_id:
        try:
            # Initialize Square client
            from square.client import Client
            from django.conf import settings
            
            square_client = Client(
                access_token=settings.SQUARE_ACCESS_TOKEN,
                environment=settings.SQUARE_ENVIRONMENT
            )
            
            # Retrieve the card details
            card_result = square_client.cards.retrieve_card(
                card_id=business.square_card_id
            )
            
            if card_result.is_success():
                card = card_result.body.get('card', {})
                payment_method = {
                    'last4': card.get('last_4'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year'),
                    'card_brand': card.get('card_brand')
                }
        except Exception as e:
            # Log the error but don't crash
            print(f"Error retrieving card details: {e}")
    
    # Get plan information for invoices table
    invoices = []
    for record in billing_records:
        try:
            subscription = None
            plan_name = "Unknown"
            
            if record.subscription_id:
                try:
                    subscription = BusinessSubscription.objects.get(id=record.subscription_id)
                    plan_name = subscription.plan.name
                except BusinessSubscription.DoesNotExist:
                    pass
            
            # Extract period details from the JSON field
            details = record.details or {}
            
            # Properly serialize the details to JSON for the template
            # This ensures it will be valid JSON in the script tag
            details_json = json.dumps(details)
            
            invoices.append({
                'id': record.id,
                'date': record.billing_date,
                'amount': record.amount,
                'plan': plan_name,
                'status': record.status,
                'square_payment_id': record.square_payment_id,
                'square_invoice_id': record.square_invoice_id,
                'details': details,  # Original Python dict for template access
                'details_json': details_json  # JSON string for script tag
            })
        except Exception as e:
            print(f"Error processing billing record {record.id}: {e}")
            # Add a minimal record in case of error
            invoices.append({
                'id': record.id,
                'date': record.billing_date,
                'amount': record.amount,
                'plan': 'Unknown',
                'status': record.status,
                'square_payment_id': record.square_payment_id,
                'details': {}
            })
    
    context = {
        'billing_records': billing_records,  # Keep for backward compatibility
        'total_billed': total_billed,
        'current_balance': current_balance,  # Use the calculated current balance
        'last_payment': {
            'amount': last_payment.amount if last_payment else 0,
            'date': last_payment.billing_date if last_payment else None
        },
        'next_billing': next_billing,
        'payment_method': payment_method,
        'invoices': invoices,
        'active_page': 'billing_history',
        'title': 'Billing History'
    }
    
    return render(request, 'usage_analytics/billing_history.html', context)

@login_required
@require_POST
def change_plan(request):
    """Handle plan changes to take effect at the next billing date."""
    # Only accept POST requests
    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'Only POST requests are allowed'}, status=405)
    
    # Get plan IDs from JSON data
    try:
        # Parse JSON data from request body
        data = json.loads(request.body)
        new_plan_id = data.get('new_plan_id')
        current_plan_id = data.get('current_plan_id')

        print("new_plan_id:", new_plan_id)
        print("current_plan_id:", current_plan_id)
        
        if not new_plan_id or not current_plan_id:
            return JsonResponse({'status': 'error', 'message': 'Missing plan IDs'}, status=400)
        
        new_plan_id = int(new_plan_id)
        current_plan_id = int(current_plan_id)
    except json.JSONDecodeError:
        return JsonResponse({'status': 'error', 'message': 'Invalid JSON data'}, status=400)
    except (ValueError, TypeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid plan IDs'}, status=400)
    
    business = request.user.business_set.first()
    new_plan = get_object_or_404(SubscriptionPlan, pk=new_plan_id, is_active=True)
    
    # Check if business already has an active subscription
    try:
        current_subscription = BusinessSubscription.objects.get(
            business=business,
            is_active=True,
            plan_id=current_plan_id
        )
        
        # Don't change immediately, just mark for change at next billing date
        if current_subscription.plan.id == new_plan.id:
            return JsonResponse({
                'success': False, 
                'error': f"You are already subscribed to the {new_plan.name} plan."
            })
        else:
            # Store the new plan ID for changing at the next billing date
            current_subscription.next_plan_id = new_plan.id
            current_subscription.save()
            
            # Format the next billing date for display
            next_billing_date = current_subscription.next_billing_date.strftime('%B %d, %Y') if current_subscription.next_billing_date else "your next billing date"
            
            return JsonResponse({
                'success': True,
                'message': f"Your subscription will be changed from {current_subscription.plan.name} to {new_plan.name} on {next_billing_date}.",
                'plan_name': new_plan.name,
                'price': str(new_plan.price),
                'next_billing_date': next_billing_date
            })
        
    except BusinessSubscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': "No active subscription found.",
            'redirect_url': reverse('subscription:select_plan', args=[new_plan_id])
        })

@login_required
@require_POST
def cancel_subscription(request):
    """Cancel a subscription."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST requests are allowed'}, status=405)
    
    business = request.user.business_set.first()
    
    try:
        # Get plan ID from JSON data
        data = json.loads(request.body)
        plan_id = data.get('plan_id')
        
        if not plan_id:
            return JsonResponse({'success': False, 'error': 'Missing plan ID'}, status=400)
        
        try:
            plan_id = int(plan_id)
        except (ValueError, TypeError):
            return JsonResponse({'success': False, 'error': 'Invalid plan ID'}, status=400)
        
        # Find the subscription with the specified plan ID
        subscription = BusinessSubscription.objects.get(
            business=business,
            is_active=True,
            plan_id=plan_id
        )
        
        # Mark subscription as cancelled but keep it active until the next billing date
        subscription.status = 'cancelled'
        subscription.save()
        
        return JsonResponse({
            'success': True,
            'message': f"Your subscription to {subscription.plan.name} has been cancelled. You can continue using it until your next billing date on {subscription.next_billing_date.strftime('%B %d, %Y') if subscription.next_billing_date else 'the end of your current billing period'}."
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'}, status=400)
    except BusinessSubscription.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': "No active subscription found with the specified plan."
        })

@login_required
def get_subscription_data(request):
    """API endpoint to retrieve subscription data."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get current subscription
    try:
        subscription = BusinessSubscription.objects.filter(
            business=business,
            is_active=True
        ).latest('created_at')
        
        plan_data = {
            'id': subscription.plan.id,
            'name': subscription.plan.name,
            'price': float(subscription.plan.price),
            'billing_cycle': subscription.plan.billing_cycle,
            'voice_minutes': subscription.plan.voice_minutes,
            'voice_calls': subscription.plan.voice_calls,
            'sms_messages': subscription.plan.sms_messages,
            'features': subscription.plan.features,
            'status': subscription.status,
            'start_date': subscription.start_date.strftime('%Y-%m-%d'),
            'end_date': subscription.end_date.strftime('%Y-%m-%d') if subscription.end_date else None,
            'days_remaining': subscription.days_remaining()
        }
    except BusinessSubscription.DoesNotExist:
        plan_data = None
    
    # Get usage metrics
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get available plans
    available_plans = []
    for plan in SubscriptionPlan.objects.filter(is_active=True).order_by('price'):
        available_plans.append({
            'id': plan.id,
            'name': plan.name,
            'price': float(plan.price),
            'billing_cycle': plan.billing_cycle,
            'voice_minutes': plan.voice_minutes,
            'voice_calls': plan.voice_calls,
            'sms_messages': plan.sms_messages,
            'features': plan.features
        })
    
    response_data = {
        'current_plan': plan_data,
        'usage_metrics': usage_summary,
        'available_plans': available_plans
    }
    
    return JsonResponse(response_data)


@login_required
def select_plan(request, plan_id=None):
    """View for selecting a plan and proceeding to payment."""
    business = request.user.business_set.first()
    
    if plan_id:
        # Get the specific plan
        try:
            plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
            if "Trial" in plan.name:
                trial_already_availed = BusinessSubscription.objects.filter(business=business, plan__name__icontains="Trial").exists()
                if trial_already_availed:
                    messages.error(request, "You have already availed the trial plan.")
                    return redirect('subscription:subscription_management')

        except SubscriptionPlan.DoesNotExist:
            messages.error(request, "The selected plan is not available.")
            return redirect('subscription:subscription_management')
    else:
        # Redirect to subscription management if no plan_id
        return redirect('subscription:subscription_management')
    
    # Get current subscription
    try:
        subscription = BusinessSubscription.objects.filter(business=business, is_active=True).latest('created_at')
        
        # If user already has this plan, redirect to subscription management
        if subscription.plan.id == plan.id and not subscription.next_plan_id:
            messages.info(request, "You are already subscribed to this plan.")
            return redirect('subscription:subscription_management')
            
    except BusinessSubscription.DoesNotExist:
        subscription = None
    
    # Get card details from Square if available
    card_details = None
    if business.square_card_id and business.square_customer_id:
        try:
            # Initialize Square client
            square_client = Client(
                access_token=settings.SQUARE_ACCESS_TOKEN,
                environment=settings.SQUARE_ENVIRONMENT
            )
            
            # Retrieve the card details
            card_result = square_client.cards.retrieve_card(
                card_id=business.square_card_id
            )
            
            if card_result.is_success():
                card = card_result.body.get('card', {})
                card_details = {
                    'last4': card.get('last_4'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year'),
                    'card_brand': card.get('card_brand')
                }
        except Exception as e:
            # Log the error but don't crash
            print(f"Error retrieving card details: {e}")
    
    # Prepare context for the template
    context = {
        'plan': plan,
        'subscription': subscription,
        'business': business,
        'card_details': card_details,
        'square_app_id': settings.SQUARE_APP_ID,
        'environment': settings.SQUARE_ENVIRONMENT,
        'active_page': 'subscription',
        'title': 'Select Plan'
    }
    
    return render(request, 'subscription/payment.html', context)

@login_required
@require_POST
def process_payment(request, plan_id):
    """Process the payment for a subscription plan."""
    try:
        # Get the plan
        plan = get_object_or_404(SubscriptionPlan, id=plan_id, is_active=True)
        business = request.user.business_set.first()
        
        # Get payment details from form
        card_nonce = request.POST.get('card-nonce')
        use_existing_card = request.POST.get('use_existing_card') == 'true'
        
        # Get coupon code if applied
        coupon_code = request.POST.get('coupon_code')
        coupon = None
        
        # Calculate price (apply yearly discount if applicable)
        original_price = plan.price
        final_price = original_price
        
        # Apply yearly discount (20% off annual price)
        if plan.billing_cycle == 'yearly':
            # Calculate yearly price (12 months)
            yearly_price = original_price * 12
            # Apply 20% discount
            final_price = yearly_price * 0.8
        
        # Apply coupon if valid
        if coupon_code:
            try:
                coupon = Coupon.objects.get(code=coupon_code, is_active=True)
                
                # Validate coupon
                if coupon.is_valid() and coupon.is_valid_for_user(request.user):
                    # Check if coupon is applicable to this plan
                    if coupon.applicable_plans.filter(id=plan.id).exists() or not coupon.applicable_plans.exists():
                        final_price = coupon.apply_discount(final_price)
                    else:
                        coupon = None
                else:
                    coupon = None
            except Coupon.DoesNotExist:
                pass
        
        # Initialize Square client
        square_client = Client(
            access_token=settings.SQUARE_ACCESS_TOKEN,
            environment=settings.SQUARE_ENVIRONMENT
        )
        
        # Prepare payment amount
        amount_money = {
            "amount": int(final_price * 100),  # Convert to cents
            "currency": "USD"
        }
        
        # Generate a unique idempotency key for this payment
        idempotency_key = str(uuid.uuid4())
        
        # Create payment and customer if needed
        customer_id = None
        card_id = None
        
        # If using existing card, get the customer and card IDs
        if use_existing_card:
            customer_id = business.square_customer_id
            card_id = business.square_card_id
        
        # Create the payment
        payment_body = {
            "idempotency_key": idempotency_key,
            "amount_money": amount_money,
            "autocomplete": True,
            "note": f"Subscription to {plan.name} ({plan.billing_cycle})",
            "payment_method_types": ["CARD"]
        }
        
        # Add source ID (card nonce) or source (saved card)
        if use_existing_card and business.square_card_id:
            payment_body["source_id"] = business.square_card_id
            payment_body["customer_id"] = business.square_customer_id
        else:
            # If no card nonce and not using existing card, redirect back
            if not card_nonce and not use_existing_card:
                return redirect('subscription:select_plan', plan_id=plan_id)
            payment_body["source_id"] = card_nonce
        
        # Process the payment
        payment_result = square_client.payments.create_payment(
            body=payment_body
        )
        
        if not payment_result.is_success():
            messages.error(request, "Failed to process payment. Please try again")
            return redirect('subscription:select_plan', plan_id=plan_id)
            
        if payment_result.is_success():
            payment_id = payment_result.body['payment']['id']
        
        # Get payment details
        payment = payment_result.body['payment']
        transaction_id = payment['id']
        card_details = payment.get('card_details', {})
        card_last4 = card_details.get('card', {}).get('last_4', '****')
        
        # Check if the business already has an active subscription
        with transaction.atomic():
            try:
                current_subscription = business.active_subscription()
                if current_subscription:
                    # End the current subscription
                    current_subscription.is_active = False
                    current_subscription.end_date = timezone.now()
                    current_subscription.save()
                
            except BusinessSubscription.DoesNotExist:
                print("No active subscription found for this business.")
            
            # Create new subscription
            end_date = timezone.now() + timedelta(days=30 if plan.billing_cycle == 'monthly' else 365)
            
            new_subscription = BusinessSubscription.objects.create(
                business=business,
                plan=plan,
                status='active',
                start_date=timezone.now(),
                end_date=end_date,
                next_billing_date=end_date,
                square_subscription_id=transaction_id,  # Using Square payment ID
                square_customer_id=customer_id if customer_id else None,
                coupon_used=coupon  # Store the coupon used for this subscription
            )
            
            # Create a billing record for this transaction
            billing_record = BillingHistory.objects.create(
                business=business,
                subscription=new_subscription,
                amount=final_price,  # Use discounted price if coupon applied
                status='paid',
                billing_date=timezone.now(),
                square_payment_id=transaction_id,  # Store the Square payment ID
                square_invoice_id=transaction_id,  # For now, using the same ID for both
                details={
                    'payment_method': 'square',
                    'payment_date': timezone.now().isoformat(),
                    'customer_id': customer_id if customer_id else None,
                    'card_id': card_id if card_id else None,
                    'payment_status': 'COMPLETED',
                    'coupon_code': coupon_code if coupon_code else None,
                    'discount_amount': float(original_price - final_price) if coupon_code else 0.00
                }
            )
            
            # Record coupon usage if a coupon was applied
            if coupon:
                # Increment the coupon usage count
                coupon.use_coupon()
                
                # Record the specific usage for this user - use get_or_create to prevent duplicates
                CouponUsage.objects.get_or_create(
                    coupon=coupon,
                    user=request.user,
                    subscription=new_subscription
                )
            
            # Create usage tracker for the new subscription's business
            UsageTracker.objects.get_or_create(
                business=new_subscription.business,
                date=timezone.now().date(),
                defaults={'metrics': {}}  # Initialize with empty metrics
            )
        
        # Return success page
        return redirect('subscription:subscription_success', subscription_id=new_subscription.id, transaction_id=transaction_id)
    
    except Exception as e:
        print(f"Error processing payment: {str(e)}")
        return redirect('subscription:select_plan', plan_id=plan_id)

@login_required
def subscription_success(request, subscription_id, transaction_id):
    """Show subscription success page after successful payment."""
    business = request.user.business_set.first()
    subscription = get_object_or_404(BusinessSubscription, id=subscription_id, business=business)
    
    # Get billing history record for this transaction to show payment details
    billing_record = BillingHistory.objects.filter(
        subscription_id=subscription_id,
        square_payment_id=transaction_id
    ).first()
    
    # Initialize payment details
    payment_details = {
        'original_price': subscription.plan.price,
        'discount_amount': 0,
        'final_amount': subscription.plan.price,
        'coupon_code': None,
        'coupon_applied': False
    }
    
    # If we have billing record with details, use that information
    if billing_record:
        payment_details['final_amount'] = billing_record.amount
        
        # Check if coupon was applied
        if billing_record.details and 'coupon_code' in billing_record.details:
            payment_details['coupon_code'] = billing_record.details.get('coupon_code')
            payment_details['discount_amount'] = billing_record.details.get('discount_amount', 0)
            payment_details['original_price'] = billing_record.amount
            payment_details['coupon_applied'] = True
    
    context = {
        'subscription': subscription,
        'transaction_id': transaction_id,
        'payment_details': payment_details,
        'active_page': 'subscription',
        'title': 'Subscription Successful'
    }
    
    return render(request, 'subscription/success.html', context)

@login_required
def cancel_plan_change(request):
    """Cancel a scheduled plan change."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'error': 'Only POST requests are allowed'}, status=405)
    
    business = request.user.business_set.first()
    
    try:
        subscription = BusinessSubscription.objects.get(business=business, is_active=True)
        
        if not subscription.next_plan_id:
            return JsonResponse({'success': False, 'error': 'No plan change scheduled'})
        
        # Get the plan name before clearing it for the message
        try:
            next_plan = SubscriptionPlan.objects.get(id=subscription.next_plan_id)
            plan_name = next_plan.name
        except SubscriptionPlan.DoesNotExist:
            plan_name = "new plan"
        
        # Clear the next plan ID
        subscription.next_plan_id = None
        subscription.save()
        
        return JsonResponse({
            'success': True,
            'message': f"Your scheduled change to {plan_name} has been canceled."
        })
        
    except BusinessSubscription.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'No active subscription found'})

@login_required
def validate_coupon(request):
    """API endpoint to validate a coupon code."""
    if request.method != 'POST':
        return JsonResponse({'valid': False, 'message': 'Invalid request method'})
    
    code = request.POST.get('code')
    plan_id = request.POST.get('plan_id')
    
    if not code or not plan_id:
        return JsonResponse({'valid': False, 'message': 'Missing required parameters'})
    
    try:
        # Get the coupon and plan
        coupon = Coupon.objects.get(code=code, is_active=True)
        plan = SubscriptionPlan.objects.get(id=plan_id, is_active=True)
        
        # Check if the coupon is valid for this user and plan
        user = request.user
        
        # Check if the coupon is valid
        if not coupon.is_valid():
            return JsonResponse({'valid': False, 'message': 'This coupon is no longer valid'})
        
        # Check if the coupon is valid for this user
        if not coupon.is_valid_for_user(user):
            return JsonResponse({'valid': False, 'message': 'You have already used this coupon the maximum number of times'})
        
        # Check if the coupon is applicable to this plan
        if coupon.applicable_plans.exists() and not coupon.applicable_plans.filter(id=plan.id).exists():
            return JsonResponse({'valid': False, 'message': 'This coupon is not valid for the selected plan'})
        
        # Calculate the discount
        original_price = float(plan.price)
        discount_amount = float(coupon.calculate_discount(original_price))
        discounted_price = float(coupon.apply_discount(original_price))
        
        # Format the discount description
        if coupon.discount_type == 'percentage':
            discount_description = f"{coupon.discount_value}% off"
        else:
            discount_description = f"${coupon.discount_value} off"
        
        return JsonResponse({
            'valid': True,
            'message': 'Coupon applied successfully!',
            'discount_amount': round(discount_amount, 2),
            'discounted_price': round(discounted_price, 2),
            'discount_description': discount_description,
            'coupon_code': coupon.code
        })
    
    except Coupon.DoesNotExist:
        return JsonResponse({'valid': False, 'message': 'Invalid coupon code'})
    except SubscriptionPlan.DoesNotExist:
        return JsonResponse({'valid': False, 'message': 'Invalid subscription plan'})
    except Exception as e:
        return JsonResponse({'valid': False, 'message': f'An error occurred: {str(e)}'})

@login_required
def manage_card(request):
    """View for saving or updating card details."""
    business = request.user.business_set.first()
    
    # Get redirect URL if provided
    redirect_url = request.GET.get('redirect_url') or request.POST.get('redirect_url')
    
    # Get card details from Square if available
    card_details = None
    if business.square_card_id and business.square_customer_id:
        try:
            # Initialize Square client
            square_client = Client(
                access_token=settings.SQUARE_ACCESS_TOKEN,
                environment=settings.SQUARE_ENVIRONMENT
            )
            
            # Retrieve the card details
            card_result = square_client.cards.retrieve_card(
                card_id=business.square_card_id
            )
            
            if card_result.is_success():
                card = card_result.body.get('card', {})
                card_details = {
                    'last4': card.get('last_4'),
                    'exp_month': card.get('exp_month'),
                    'exp_year': card.get('exp_year'),
                    'card_brand': card.get('card_brand')
                }
        except Exception as e:
            # Log the error but don't crash
            print(f"Error retrieving card details: {e}")
    
    if request.method == 'POST':
        # Get the card nonce from the request
        card_nonce = request.POST.get('card-nonce')
        
        if not card_nonce:
            context = {
                'business': business,
                'card_details': card_details,
                'square_app_id': settings.SQUARE_APP_ID,
                'square_location_id': settings.SQUARE_LOCATION_ID,
                'redirect_url': redirect_url,
                'active_page': 'subscription',
                'title': 'Manage Payment Method'
            }
            return render(request, 'subscription/manage_card.html', context)
        
        # Initialize Square client
        square_client = Client(
            access_token=settings.SQUARE_ACCESS_TOKEN,
            environment=settings.SQUARE_ENVIRONMENT
        )
        
        # Check if business already has a Square customer ID
        if not business.square_customer_id:
            # Create a new customer
            customer_request = {
                'given_name': request.user.first_name or business.businessName,
                'family_name': request.user.last_name or "",
                'email_address': request.user.email,
                'reference_id': str(business.businessId),
                'phone_number': business.phone
            }
            
            customer_result = square_client.customers.create_customer(
                body=customer_request
            )
            
            if customer_result.is_success():
                customer_id = customer_result.body['customer']['id']
                business.square_customer_id = customer_id  # Store Square customer ID
                business.save()
            else:
                context = {
                    'business': business,
                    'card_details': card_details,
                    'square_app_id': settings.SQUARE_APP_ID,
                    'square_location_id': settings.SQUARE_LOCATION_ID,
                    'redirect_url': redirect_url,
                    'active_page': 'subscription',
                    'title': 'Manage Payment Method'
                }
                return render(request, 'subscription/manage_card.html', context)
        else:
            customer_id = business.square_customer_id
        
        # Create a card for the customer
        card_request = {
            'idempotency_key': str(uuid.uuid4()),
            'source_id': card_nonce,
            'card': {
                'customer_id': customer_id,
                'cardholder_name': f"{request.user.first_name} {request.user.last_name}".strip() or business.businessName,
                'billing_address': {
                    'postal_code': request.POST.get('postal-code', '12345')
                }
            }
        }
        
        try:
            card_result = square_client.cards.create_card(
                body=card_request
            )
            
            if card_result.is_success():
                card_id = card_result.body['card']['id']
                # Store the card ID in the business model
                business.square_card_id = card_id
                business.save()
                messages.success(request, "Card saved successfully.")
            
            if not card_result.is_success():
                messages.error(request, "Failed to save card.")
            else:
                context = {
                    'business': business,
                    'card_details': card_details,
                    'square_app_id': settings.SQUARE_APP_ID,
                    'square_location_id': settings.SQUARE_LOCATION_ID,
                    'redirect_url': redirect_url,
                    'active_page': 'subscription',
                    'title': 'Manage Payment Method'
                }
                return render(request, 'subscription/manage_card.html', context)
        except Exception as e:
            context = {
                'business': business,
                'card_details': card_details,
                'square_app_id': settings.SQUARE_APP_ID,
                'square_location_id': settings.SQUARE_LOCATION_ID,
                'redirect_url': redirect_url,
                'active_page': 'subscription',
                'title': 'Manage Payment Method'
            }
            return render(request, 'subscription/manage_card.html', context)
        
        # Redirect to the provided URL or default to subscription management
        if redirect_url:
            return redirect(redirect_url)
        return redirect('subscription:subscription_management')
    
    # For GET requests, render the card management page
    context = {
        'business': business,
        'card_details': card_details,
        'square_app_id': settings.SQUARE_APP_ID,
        'square_location_id': settings.SQUARE_LOCATION_ID,
        'redirect_url': redirect_url,
        'active_page': 'subscription',
        'title': 'Manage Payment Method'
    }
    return render(request, 'subscription/manage_card.html', context)





@login_required
@require_POST
def update_auto_upgrade(request):
    """Update the auto-upgrade setting for a business."""
    try:
        # Parse the request data
        data = json.loads(request.body)
        auto_upgrade = data.get('auto_upgrade', False)
        print(f"auto_upgrade: {auto_upgrade}")
        
        # Get the business
        business = request.user.business_set.first()
        if not business:
            return JsonResponse({
                'success': False,
                'message': 'No business found for this user.'
            })
        
        # Update the auto-upgrade setting
        business.auto_upgrade = auto_upgrade
        print(f"business.auto_upgrade: {business.auto_upgrade}")
        business.save()
        
        # Return success response
        return JsonResponse({
            'success': True,
            'message': 'Auto-upgrade setting updated successfully.'
        })
    
    except Exception as e:
        # Log the error
        print(f"Error updating auto-upgrade setting: {e}")
        
        # Return error response
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        })
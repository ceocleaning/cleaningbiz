from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.utils import timezone
from datetime import datetime, timedelta
import json
import uuid
from django.db import models, transaction
from django.contrib import messages

from accounts.models import Business
from .models import SubscriptionPlan, BusinessSubscription, UsageTracker, BillingHistory

@login_required
def subscription_management(request):
    """View for managing subscriptions."""
    business = request.user.business_set.first()
    
    # Get current subscription
    try:
        subscription = BusinessSubscription.objects.filter(
            business=business,
            is_active=True
        ).latest('created_at')
    except BusinessSubscription.DoesNotExist:
        subscription = None
    
    # Get all available plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    # Get usage summary for current month
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_of_month,
        end_date=today
    )
    
    # Get recent billing history
    billing_history = BillingHistory.objects.filter(
        business=business
    ).order_by('-billing_date')[:5]
    
    context = {
        'subscription': subscription,
        'plans': plans,
        'usage_summary': usage_summary,
        'billing_history': billing_history,
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
        next_billing = {
            'date': subscription.end_date,
            'amount': subscription.plan.price
        }
    except BusinessSubscription.DoesNotExist:
        next_billing = {
            'date': None,
            'amount': 0
        }
    
    # Get payment method info - dummy data for now
    payment_method = {
        'last4': '4242',
        'exp_month': '12',
        'exp_year': '2025',
        'brand': 'visa'
    }
    
    context = {
        'billing_records': billing_records,
        'total_billed': total_billed,
        'current_balance': 0.00,  # Assume no outstanding balance for now
        'last_payment': {
            'amount': last_payment.amount if last_payment else 0,
            'date': last_payment.billing_date if last_payment else None
        },
        'next_billing': next_billing,
        'payment_method': payment_method,
        'active_page': 'billing_history',
        'title': 'Billing History'
    }
    
    return render(request, 'usage_analytics/billing_history.html', context)

@login_required
@require_POST
def change_plan(request, plan_id):
    """Handle plan changes."""
    business = request.user.business_set.first()
    new_plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
    
    # Check if business already has an active subscription
    try:
        current_subscription = BusinessSubscription.objects.get(
            business=business,
            is_active=True
        )
        
        # Update the subscription
        current_subscription.is_active = False
        current_subscription.end_date = timezone.now()
        current_subscription.save()
        
    except BusinessSubscription.DoesNotExist:
        current_subscription = None
    
    # Create new subscription
    new_subscription = BusinessSubscription.objects.create(
        business=business,
        plan=new_plan,
        status='active',
        start_date=timezone.now(),
        # For monthly, end date is one month from now
        end_date=timezone.now() + timedelta(days=30) if new_plan.billing_cycle == 'monthly' else timezone.now() + timedelta(days=365)
    )
    
    # TODO: Integrate with actual payment gateway (Stripe)
    
    return redirect('subscription:subscription_management')

@login_required
@require_POST
def cancel_subscription(request):
    """Cancel a subscription."""
    business = request.user.business_set.first()
    
    try:
        subscription = BusinessSubscription.objects.get(
            business=business,
            is_active=True
        )
        
        subscription.status = 'cancelled'
        subscription.is_active = False
        subscription.end_date = timezone.now()
        subscription.save()
        
        # TODO: Handle actual cancellation with payment provider
        
        return JsonResponse({'status': 'success', 'message': 'Subscription cancelled successfully.'})
        
    except BusinessSubscription.DoesNotExist:
        return JsonResponse({'status': 'error', 'message': 'No active subscription found.'}, status=404)

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
def track_usage(request, metric_type):
    """Increment usage for a specific metric."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    business = request.user.business_set.first()
    increment_by = request.POST.get('increment_by', 1)
    
    try:
        increment_by = int(increment_by)
    except ValueError:
        return JsonResponse({'error': 'increment_by must be an integer'}, status=400)
    
    if metric_type not in ['voice_minutes', 'voice_calls', 'sms_messages']:
        return JsonResponse({'error': 'Invalid metric type'}, status=400)
    
    # Increment the specified metric
    usage = UsageTracker.increment_metric(
        business=business,
        metric_name=metric_type,
        increment_by=increment_by
    )
    
    return JsonResponse({
        'status': 'success',
        'metric': metric_type,
        'current_value': usage.metrics.get(metric_type, 0)
    })

@login_required
def select_plan(request, plan_id=None):
    """View for selecting a plan and proceeding to payment."""
    business = request.user.business_set.first()
    
    # Get all available plans
    plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    # If no plans exist yet, create dummy plans
    if plans.count() == 0:
        create_dummy_plans()
        plans = SubscriptionPlan.objects.filter(is_active=True).order_by('price')
    
    selected_plan = None
    if plan_id:
        selected_plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
    
    context = {
        'plans': plans,
        'selected_plan': selected_plan,
        'active_page': 'subscription',
        'title': 'Select Subscription Plan'
    }
    
    return render(request, 'subscription/payment.html', context)

@login_required
@require_POST
def process_payment(request, plan_id):
    """Process payment for a subscription plan."""
    business = request.user.business_set.first()
    plan = get_object_or_404(SubscriptionPlan, pk=plan_id, is_active=True)
    
    # Validate the payment form
    card_name = request.POST.get('card_name')
    card_number = request.POST.get('card_number', '').replace(' ', '')
    card_expiry = request.POST.get('card_expiry')
    card_cvc = request.POST.get('card_cvc')
    
    # Simple validation for demo purposes
    if not all([card_name, card_number, card_expiry, card_cvc]):
        messages.error(request, 'All payment fields are required.')
        return redirect('subscription:select_plan', plan_id=plan_id)
    
    if len(card_number) != 16 or not card_number.isdigit():
        messages.error(request, 'Please enter a valid 16-digit card number.')
        return redirect('subscription:select_plan', plan_id=plan_id)
    
    # Check if the business already has an active subscription
    with transaction.atomic():
        try:
            current_subscription = BusinessSubscription.objects.get(
                business=business,
                is_active=True
            )
            
            # End the current subscription
            current_subscription.is_active = False
            current_subscription.end_date = timezone.now()
            current_subscription.save()
            
        except BusinessSubscription.DoesNotExist:
            pass
        
        # Create new subscription
        end_date = timezone.now() + timedelta(days=30 if plan.billing_cycle == 'monthly' else 365)
        
        new_subscription = BusinessSubscription.objects.create(
            business=business,
            plan=plan,
            status='active',
            start_date=timezone.now(),
            end_date=end_date,
            stripe_subscription_id=f"sub_{uuid.uuid4().hex[:10]}",  # Dummy ID
            stripe_customer_id=f"cus_{uuid.uuid4().hex[:10]}"  # Dummy ID
        )
        
        # Create a billing record for this transaction
        transaction_id = f"txn_{uuid.uuid4().hex[:10]}"
        
        billing_record = BillingHistory.objects.create(
            business=business,
            subscription=new_subscription,
            amount=plan.price,
            status='paid',
            billing_date=timezone.now(),
            stripe_invoice_id=f"inv_{uuid.uuid4().hex[:10]}",  # Dummy ID
            details={
                'payment_method': 'card',
                'card_last4': card_number[-4:],
                'transaction_id': transaction_id
            }
        )
    
    # Return success page
    return redirect('subscription:subscription_success', subscription_id=new_subscription.id, transaction_id=transaction_id)

@login_required
def subscription_success(request, subscription_id, transaction_id):
    """Show subscription success page after successful payment."""
    business = request.user.business_set.first()
    subscription = get_object_or_404(BusinessSubscription, id=subscription_id, business=business)
    
    context = {
        'subscription': subscription,
        'transaction_id': transaction_id,
        'active_page': 'subscription',
        'title': 'Subscription Successful'
    }
    
    return render(request, 'subscription/success.html', context)

def create_dummy_plans():
    """Create dummy subscription plans for testing."""
    # Only create if no plans exist
    if SubscriptionPlan.objects.count() == 0:
        try:
            # Starter Plan
            SubscriptionPlan.objects.create(
                name="Starter Plan",
                price=49.99,
                billing_cycle="monthly",
                voice_minutes=300,
                voice_calls=100,
                sms_messages=500,
                features={
                    "basic_analytics": True,
                    "email_support": True,
                    "voice_templates": 5,
                    "sms_templates": 5,
                    "webhooks": False,
                    "custom_branding": False,
                    "priority_support": False
                }
            )
            
            # Professional Plan
            SubscriptionPlan.objects.create(
                name="Professional Plan",
                price=99.99,
                billing_cycle="monthly",
                voice_minutes=1000,
                voice_calls=500,
                sms_messages=2000,
                features={
                    "basic_analytics": True,
                    "advanced_analytics": True,
                    "email_support": True,
                    "voice_templates": 20,
                    "sms_templates": 20,
                    "webhooks": True,
                    "custom_branding": True,
                    "priority_support": False
                }
            )
            
            # Enterprise Plan
            SubscriptionPlan.objects.create(
                name="Enterprise Plan",
                price=199.99,
                billing_cycle="monthly",
                voice_minutes=5000,
                voice_calls=2000,
                sms_messages=10000,
                features={
                    "basic_analytics": True,
                    "advanced_analytics": True,
                    "email_support": True,
                    "voice_templates": 50,
                    "sms_templates": 50,
                    "webhooks": True,
                    "custom_branding": True,
                    "priority_support": True,
                    "dedicated_account_manager": True,
                    "custom_integrations": True
                }
            )
            
            # Create yearly versions with 20% discount
            for plan in SubscriptionPlan.objects.filter(billing_cycle="monthly"):
                yearly_price = float(plan.price) * 12 * 0.8  # 20% discount
                SubscriptionPlan.objects.create(
                    name=plan.name,
                    price=yearly_price,
                    billing_cycle="yearly",
                    voice_minutes=plan.voice_minutes,
                    voice_calls=plan.voice_calls,
                    sms_messages=plan.sms_messages,
                    features=plan.features
                )
        except Exception as e:
            print(f"Error creating plans: {str(e)}")
            pass



from django import template
from subscription.models import SubscriptionPlan
from subscription.views import create_dummy_plans

register = template.Library()

@register.simple_tag
def get_subscription_plans():
    """
    Returns all active subscription plans.
    If no plans exist, creates dummy plans first.
    """
    plans = SubscriptionPlan.objects.filter(is_active=True)
    
    # If no plans exist, create dummy ones
    if plans.count() == 0:
        create_dummy_plans()
        print("Dummy plans created")
        plans = SubscriptionPlan.objects.filter(is_active=True)
        print("Plans fetched:", plans)
        
    return plans 
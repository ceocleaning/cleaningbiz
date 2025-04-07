from django import template
from subscription.models import SubscriptionPlan

register = template.Library()

@register.simple_tag
def get_subscription_plans():
    pass
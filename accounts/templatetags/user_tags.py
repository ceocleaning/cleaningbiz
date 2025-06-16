from django import template
from django.contrib.auth.models import Group

register = template.Library()

@register.filter(name='is_cleaner')
def is_cleaner(user):
    """Check if user belongs to Cleaner group"""
    return user.groups.filter(name='Cleaner').exists()

@register.filter(name='is_business_owner')
def is_business_owner(user):
    """Check if user does not belong to Cleaner group (is a business owner)"""
    return not user.groups.filter(name='Cleaner').exists()

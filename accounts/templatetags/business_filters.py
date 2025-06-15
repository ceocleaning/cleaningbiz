from django import template
from django.utils import timezone
import pytz

register = template.Library()

@register.filter
def business_local_time(dt, business):
    """Convert a datetime to the business's local timezone"""
    if not dt:
        return ''
    try:
        if dt.tzinfo is None:
            dt = timezone.make_aware(dt)
        return dt.astimezone(business.get_timezone())
    except (ValueError, AttributeError):
        return dt

@register.filter
def format_business_datetime(dt, business):
    """Format a datetime in the business's timezone"""
    if not dt:
        return ''
    try:
        local_dt = business_local_time(dt, business)
        return local_dt.strftime("%B %d, %Y %I:%M %p")
    except (ValueError, AttributeError):
        return dt

@register.filter
def format_business_date(dt, business):
    """Format just the date part in the business's timezone"""
    if not dt:
        return ''
    try:
        local_dt = business_local_time(dt, business)
        return local_dt.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        return dt

@register.filter
def format_business_time(dt, business):
    """Format just the time part in the business's timezone"""
    if not dt:
        return ''
    try:
        local_dt = business_local_time(dt, business)
        return local_dt.strftime("%I:%M %p")
    except (ValueError, AttributeError):
        return dt 
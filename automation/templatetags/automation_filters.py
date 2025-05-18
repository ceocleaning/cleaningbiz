from django import template
from datetime import datetime, timezone
import pytz
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary using the key"""
    return dictionary.get(key, [])

@register.filter
def has_off_day_exception(exceptions):
    """Check if any exception in the list is an off day"""
    if not exceptions:
        return False
    
    for exception in exceptions:
        if exception.offDay:
            return True
    return False

@register.filter
def format_currency(value):
    """Format a number as currency"""
    try:
        return f"${value:,.2f}"
    except (ValueError, TypeError):
        return value

@register.filter
def format_timestamp(value):
    """Display timestamp exactly as stored in the database without timezone conversion"""
    if not value:
        return ''
    try:
        # Format the timestamp without any timezone conversion
        return value.strftime("%B %d, %Y %I:%M %p")
    except (ValueError, AttributeError):
        return value

@register.filter
def format_date(value):
    """Format date without timezone conversion"""
    if not value:
        return ''
    try:
        # Format just the date part
        return value.strftime("%B %d, %Y")
    except (ValueError, AttributeError):
        return value

@register.filter
def format_time(value):
    """Format time without timezone conversion"""
    if not value:
        return ''
    try:
        # Format just the time part
        return value.strftime("%I:%M %p")
    except (ValueError, AttributeError):
        return value

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        # Convert to Decimal for precise calculation
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        return value * arg
    except (ValueError, TypeError, decimal.InvalidOperation):
        return value

@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        # Convert to Decimal for precise calculation
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        if arg == 0:
            return 0
        return value / arg
    except (ValueError, TypeError, decimal.InvalidOperation):
        return value

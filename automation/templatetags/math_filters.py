from django import template
from decimal import Decimal, InvalidOperation

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        # Convert to Decimal for precise calculation
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        return value * arg
    except (ValueError, TypeError, InvalidOperation):
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
    except (ValueError, TypeError, InvalidOperation):
        return value

@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        # Convert to Decimal for precise calculation
        value = Decimal(str(value))
        arg = Decimal(str(arg))
        return value - arg
    except (ValueError, TypeError, InvalidOperation):
        return value

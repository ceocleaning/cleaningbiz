from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return (Decimal(str(value)) * Decimal(str(arg))).quantize(Decimal('0.01'))  #Return only 2 decimal places
    except (ValueError, TypeError):
        return value

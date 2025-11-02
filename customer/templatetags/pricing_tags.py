from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def calculate_savings(default_price, custom_price):
    """
    Calculate the savings between default and custom price.
    Returns the difference as a formatted string.
    """
    if not custom_price or not default_price:
        return "0.00"
    
    try:
        default = Decimal(str(default_price))
        custom = Decimal(str(custom_price))
        savings = default - custom
        return f"{savings:.2f}"
    except (ValueError, TypeError, InvalidOperation):
        return "0.00"


@register.filter
def has_savings(default_price, custom_price):
    """
    Check if there are actual savings (custom price is less than default).
    """
    if not custom_price or not default_price:
        return False
    
    try:
        default = Decimal(str(default_price))
        custom = Decimal(str(custom_price))
        return custom < default
    except (ValueError, TypeError):
        return False


@register.filter
def has_increase(default_price, custom_price):
    """
    Check if there's a price increase (custom price is more than default).
    """
    if not custom_price or not default_price:
        return False
    
    try:
        default = Decimal(str(default_price))
        custom = Decimal(str(custom_price))
        return custom > default
    except (ValueError, TypeError):
        return False

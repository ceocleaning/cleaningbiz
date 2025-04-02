from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value
        
@register.filter
@stringfilter
def replace(value, arg):
    """Replaces text in a string"""
    if len(arg.split(",")) != 2:
        return value
    
    what, to = arg.split(",")
    return value.replace(what, to) 
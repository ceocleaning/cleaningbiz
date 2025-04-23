from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def index(sequence, position):
    """
    Returns the item at the given position in the sequence.
    """
    try:
        return sequence[position]
    except (IndexError, TypeError, KeyError):
        return ''

@register.filter
def add(value, arg):
    """
    Adds the arg to the value.
    """
    try:
        return int(value) + int(arg)
    except (ValueError, TypeError):
        return value 

@register.filter
def get_day_name(day_names, day_index):
    """
    Returns the day name for a given day index (0-6, where 0 is Sunday).
    """
    try:
        # Ensure index is within 0-6 range (Sunday to Saturday)
        day_index = day_index % 7
        return day_names[day_index]
    except (IndexError, TypeError, KeyError):
        return '' 
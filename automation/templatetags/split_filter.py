from django import template

register = template.Library()

@register.filter
def split(value, delimiter=None):
    """
    Returns a list of strings, split at the specified delimiter.
    If a delimiter is not specified, splits at whitespace.
    """
    if delimiter is None:
        return value.split()
    return value.split(delimiter) 
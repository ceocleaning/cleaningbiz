from django import template

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

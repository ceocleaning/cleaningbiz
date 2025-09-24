from django import template
from django.utils.safestring import mark_safe
import json
import pprint

from notification.models import Notification
from notification.utils import get_unread_notification_count, get_user_type

register = template.Library()

@register.filter
def get_item(obj, key):
    """Get an item from a dictionary by key or attribute from an object"""
    if hasattr(obj, 'get') and callable(obj.get):
        # If it's a dictionary-like object with a get method
        return obj.get(key)
    elif hasattr(obj, key):
        # If it's an object with the attribute
        return getattr(obj, key)
    return None

@register.filter
def pprint(value):
    """Pretty print a value"""
    return pprint.pformat(value)

@register.filter
def jsonify(value):
    """Convert a value to JSON string"""
    return mark_safe(json.dumps(value))

@register.simple_tag
def unread_notification_count(user):
    """Get the count of unread notifications for a user"""
    return get_unread_notification_count(user)

@register.inclusion_tag('notification/tags/notification_badge.html')
def notification_badge(user):
    """Render a notification badge with unread count"""
    count = get_unread_notification_count(user)
    user_type = get_user_type(user)
    return {
        'count': count,
        'has_unread': count > 0,
        'user_type': user_type
    }

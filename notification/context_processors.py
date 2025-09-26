from .utils import get_unread_notification_count, get_user_type

def notification_context(request):
    """
    Context processor to add notification data to all templates
    """
    context = {
        'unread_notification_count': 0,
        'user_notification_type': None
    }
    
    if request.user.is_authenticated:
        context['unread_notification_count'] = get_unread_notification_count(request.user)
        context['user_notification_type'] = get_user_type(request.user)
    
    return context

from .models import ActivityLog
from django.contrib.contenttypes.models import ContentType

def log_activity(user, activity_type, description, request=None, obj=None, metadata=None):
    """
    Utility function to log user activities
    
    Parameters:
    - user: The user performing the action
    - activity_type: Type of activity (from ActivityLog.ACTIVITY_TYPES)
    - description: Description of the activity
    - request: The request object (optional, for IP address)
    - obj: The object being acted upon (optional)
    - metadata: Additional data to store (optional)
    """
    ip_address = None
    if request:
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip_address = x_forwarded_for.split(',')[0]
        else:
            ip_address = request.META.get('REMOTE_ADDR')
    
    activity_log = ActivityLog(
        user=user,
        activity_type=activity_type,
        description=description,
        ip_address=ip_address,
        metadata=metadata
    )
    
    # Add content object if provided
    if obj:
        content_type = ContentType.objects.get_for_model(obj)
        activity_log.content_type = content_type
        activity_log.object_id = obj.id
    
    activity_log.save()
    return activity_log

from django.utils import timezone
from django.contrib.contenttypes.models import ContentType
from .models import Notification
from .services import NotificationService

def get_user_type(user):
    """
    Determine the type of user: business_owner, cleaner, or customer
    
    Returns a string indicating the user type:
    - 'business_owner': User owns a business
    - 'cleaner': User is a cleaner
    - 'customer': User is a customer
    - None: User type cannot be determined
    """
    if not user or not user.is_authenticated:
        return None
        
    # Check if user is a business owner
    if hasattr(user, 'business_set') and user.business_set.exists():
        return 'business_owner'
        
    # Check if user is a cleaner
    if hasattr(user, 'cleaner_profile'):
        return 'cleaner'
        
    # Check if user is a customer
    if hasattr(user, 'customer'):
        return 'customer'
        
    return None


def get_unread_notification_count(user):
    """
    Get count of unread notifications for a user, filtered by user type
    """
    
    # Base query - filter by recipient and status
    query = Notification.objects.filter(
        recipient=user,
        notification_type='in_app',
        read_at__isnull=True
    )
    
    return query.count()

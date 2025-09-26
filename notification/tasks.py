from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Q

from .models import Notification
from .services import NotificationService


def clean_old_notifications(days=30):
    """
    Clean up old read notifications
    """
    cutoff_date = timezone.now() - timedelta(days=days)
    
    # Delete old read notifications
    old_notifications = Notification.objects.filter(
        Q(status='read', read_at__lt=cutoff_date) |
        Q(created_at__lt=cutoff_date, status='failed')
    )
    
    count = old_notifications.count()
    old_notifications.delete()
    
    return count

from django.db import models
from django.contrib.auth import get_user_model
import uuid


User = get_user_model()

class Notification(models.Model):
    """Base model for all types of notifications"""
    
    NOTIFICATION_TYPES = (
        ('email', 'Email'),
        ('sms', 'SMS'),
        ('in_app', 'In-App'),
    )
    

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='sent_notifications', null=True, blank=True)
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications', null=True, blank=True)

    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)

    subject = models.CharField(max_length=255)
    content = models.TextField(null=True, blank=True)
    template_name = models.CharField(max_length=100, null=True, blank=True)
    context_data = models.JSONField(default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)
    
    # Additional fields for specific notification types
    email_to = models.CharField(max_length=255, null=True, blank=True)
    sms_to = models.CharField(max_length=20, null=True, blank=True)
    
    
    # Reference to related object (polymorphic relationship)
    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=50, null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient']),
            models.Index(fields=['notification_type']),
        ]
    
    def __str__(self):
        return f"{self.id}"

# NotificationPreference model removed - preferences functionality no longer needed

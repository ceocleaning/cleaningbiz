from django.db import models
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey

# Create your models here.

class ActivityLog(models.Model):
    """
    Model to track user activities in the system
    """
    ACTIVITY_TYPES = (
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('payment', 'Payment'),
        ('subscription', 'Subscription'),
        ('business', 'Business'),
        ('feature', 'Feature'),
        ('coupon', 'Coupon'),
        ('user', 'User'),
        ('other', 'Other'),
    )
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activities')
    activity_type = models.CharField(max_length=20, choices=ACTIVITY_TYPES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    # For linking to specific objects (optional)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.CharField(max_length=255, null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Additional metadata stored as JSON
    metadata = models.JSONField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Activity Log'
        verbose_name_plural = 'Activity Logs'
    
    def __str__(self):
        return f"{self.user.username} - {self.get_activity_type_display()} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

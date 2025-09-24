from django.contrib import admin
from django.utils.html import format_html
from .models import Notification

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'recipient', 'notification_type', 'subject', 'created_at', 'sent_at')
    list_filter = ('notification_type', 'created_at', 'sent_at')
    search_fields = ('subject', 'content', 'recipient__email')
    readonly_fields = ('created_at', 'sent_at', 'read_at')
   
    
    def recipient_email(self, obj):
        return obj.recipient.email
    recipient_email.short_description = 'Recipient'
    




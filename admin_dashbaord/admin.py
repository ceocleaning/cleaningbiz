from django.contrib import admin

# Register your models here.
from .models import ActivityLog

@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'user', 'activity_type', 'description', 'ip_address', 'timestamp',
        'content_type', 'object_id', 'metadata'
    )
    list_filter = ('activity_type', 'timestamp', 'user')
    search_fields = ('description', 'user__username', 'ip_address', 'object_id')
    readonly_fields = ('timestamp',)

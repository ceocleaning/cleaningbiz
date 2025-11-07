from django.contrib import admin

from .models import Lead, Cleaners, CleanerAvailability, OpenJob, NotificationLog

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        'leadId', 'business', 'name', 'email', 'phone_number', 'notification_method',
        'sms_status', 'call_status', 'follow_up_call_status',
        'is_response_received', 'source', 'createdAt'
    )
    list_filter = (
        'notification_method', 'sms_status', 'call_status', 'follow_up_call_status',
        'is_response_received', 'type_of_cleaning', 'source', 'createdAt'
    )
    search_fields = ('leadId', 'name', 'email', 'phone_number', 'address1', 'city', 'state', 'zipCode', 'source')
    readonly_fields = (
        'createdAt', 'updatedAt', 'leadId', 'sms_sent_at', 'call_sent_at', 'follow_up_call_sent_at',
        'sms_message_sid', 'call_id', 'sms_error_message', 'call_error_message', 'follow_up_call_error_message'
    )
    fieldsets = (
        ('Basic Information', {
            'fields': ('leadId', 'business', 'name', 'email', 'phone_number', 'source')
        }),
        ('Service Details', {
            'fields': ('type_of_cleaning', 'bedrooms', 'bathrooms', 'squareFeet', 'estimatedPrice')
        }),
        ('Address', {
            'fields': ('address1', 'address2', 'city', 'state', 'zipCode')
        }),
        ('Schedule', {
            'fields': ('proposed_start_datetime', 'proposed_end_datetime')
        }),
        ('SMS Tracking', {
            'fields': ('sms_sent', 'sms_status', 'sms_sent_at', 'sms_message_sid', 'sms_error_message'),
            'classes': ('collapse',)
        }),
        ('Call Tracking', {
            'fields': ('is_call_sent', 'call_status', 'call_sent_at', 'call_id', 'call_error_message'),
            'classes': ('collapse',)
        }),
        ('Follow-up Call Tracking', {
            'fields': ('follow_up_call_sent', 'follow_up_call_status', 'follow_up_call_sent_at', 'follow_up_call_error_message'),
            'classes': ('collapse',)
        }),
        ('Notification Summary', {
            'fields': ('notification_method', 'is_response_received')
        }),
        ('Additional Info', {
            'fields': ('notes', 'content', 'details')
        }),
        ('Timestamps', {
            'fields': ('createdAt', 'updatedAt')
        }),
    )

@admin.register(Cleaners)
class CleanersAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'business', 'name', 'email', 'phoneNumber', 'rating', 'isAvailable', 'isActive', 'createdAt', 'updatedAt'
    )
    list_filter = ('isAvailable', 'isActive', 'rating', 'createdAt', 'updatedAt', 'business')
    search_fields = ('name', 'email', 'phoneNumber', 'business__businessName')
    readonly_fields = ('createdAt', 'updatedAt')

@admin.register(CleanerAvailability)
class CleanerAvailabilityAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'cleaner', 'availability_type', 'dayOfWeek', 'specific_date', 'startTime', 'endTime', 'offDay', 'createdAt', 'updatedAt'
    )
    list_filter = ('availability_type', 'dayOfWeek', 'specific_date', 'offDay', 'createdAt', 'updatedAt')
    search_fields = ('cleaner__name',)
    readonly_fields = ('createdAt', 'updatedAt')

@admin.register(OpenJob)
class OpenJobAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'booking', 'cleaner', 'status', 'assignment_type', 'createdAt', 'updatedAt'
    )
    list_filter = ('status', 'assignment_type', 'createdAt', 'updatedAt')
    search_fields = ('id', 'booking__id', 'cleaner__id')
    readonly_fields = ('createdAt', 'updatedAt', 'id')


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = (
        'id', 'lead', 'business', 'notification_type', 'status', 'success',
        'attempt_number', 'attempted_at'
    )
    list_filter = (
        'notification_type', 'status', 'success', 'attempted_at', 'business'
    )
    search_fields = (
        'lead__name', 'lead__phone_number', 'lead__leadId', 'message_sid', 'call_id', 'error_message'
    )
    readonly_fields = (
        'lead', 'business', 'notification_type', 'status', 'attempt_number',
        'attempted_at', 'success', 'error_message', 'error_code', 'message_sid',
        'call_id', 'message_content', 'metadata', 'created_at', 'updated_at'
    )
    date_hierarchy = 'attempted_at'
    
    fieldsets = (
        ('Lead Information', {
            'fields': ('lead', 'business')
        }),
        ('Notification Details', {
            'fields': ('notification_type', 'status', 'attempt_number', 'attempted_at', 'success')
        }),
        ('Message Content', {
            'fields': ('message_content', 'message_sid', 'call_id')
        }),
        ('Error Information', {
            'fields': ('error_message', 'error_code'),
            'classes': ('collapse',)
        }),
        ('Additional Data', {
            'fields': ('metadata',),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def has_add_permission(self, request):
        # Prevent manual creation of logs
        return False
    
    def has_delete_permission(self, request, obj=None):
        # Allow deletion for cleanup
        return True



admin.site.site_header = "CleaningBiz AI Dashboard"
admin.site.site_title = "CleaningBiz AI Dashboard"
admin.site.index_title = "Welcome to CleaningBiz AI Dashboard"
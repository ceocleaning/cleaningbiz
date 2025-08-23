from django.contrib import admin

from .models import Lead, Cleaners, CleanerAvailability, OpenJob

@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = (
        'leadId', 'business', 'name', 'email', 'phone_number', 'bedrooms', 'bathrooms', 'squareFeet',
        'type_of_cleaning', 'address1', 'address2', 'city', 'state', 'zipCode',
        'proposed_start_datetime', 'proposed_end_datetime', 'estimatedPrice', 'source',
        'is_response_received', 'is_call_sent', 'call_sent_at', 'follow_up_call_sent', 'follow_up_call_sent_at',
        'createdAt', 'updatedAt'
    )
    list_filter = (
        'type_of_cleaning', 'is_response_received', 'is_call_sent', 'follow_up_call_sent', 'createdAt', 'updatedAt', 'source'
    )
    search_fields = ('leadId', 'name', 'email', 'phone_number', 'address1', 'city', 'state', 'zipCode', 'source')
    readonly_fields = ('createdAt', 'updatedAt', 'leadId')

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




admin.site.site_header = "CleaningBiz AI Dashboard"
admin.site.site_title = "CleaningBiz AI Dashboard"
admin.site.index_title = "Welcome to CleaningBiz AI Dashboard"
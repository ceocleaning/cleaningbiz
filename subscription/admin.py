from django.contrib import admin
from .models import SubscriptionPlan, BusinessSubscription, UsageTracker, BillingHistory

@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ('name', 'price', 'billing_cycle', 'voice_minutes', 'voice_calls', 'sms_messages', 'is_active')
    list_filter = ('billing_cycle', 'is_active')
    search_fields = ('name',)

@admin.register(BusinessSubscription)
class BusinessSubscriptionAdmin(admin.ModelAdmin):
    list_display = ('business', 'plan', 'status', 'start_date', 'end_date', 'is_active')
    list_filter = ('status', 'is_active', 'plan')
    search_fields = ('business__name', 'stripe_subscription_id')
    date_hierarchy = 'start_date'

@admin.register(UsageTracker)
class UsageTrackerAdmin(admin.ModelAdmin):
    list_display = ('business', 'date', 'get_voice_minutes', 'get_voice_calls', 'get_sms_messages')
    list_filter = ('date',)
    search_fields = ('business__name',)
    date_hierarchy = 'date'
    
    def get_voice_minutes(self, obj):
        return obj.metrics.get('voice_minutes', 0)
    get_voice_minutes.short_description = 'Voice Minutes'
    
    def get_voice_calls(self, obj):
        return obj.metrics.get('voice_calls', 0)
    get_voice_calls.short_description = 'Voice Calls'
    
    def get_sms_messages(self, obj):
        return obj.metrics.get('sms_messages', 0)
    get_sms_messages.short_description = 'SMS Messages'

@admin.register(BillingHistory)
class BillingHistoryAdmin(admin.ModelAdmin):
    list_display = ('business', 'amount', 'status', 'billing_date')
    list_filter = ('status', 'billing_date')
    search_fields = ('business__name', 'stripe_invoice_id')
    date_hierarchy = 'billing_date'

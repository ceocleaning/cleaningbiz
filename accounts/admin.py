from django.contrib import admin
from django.contrib import messages
from .models import Business, BusinessSettings, ApiCredential, CustomAddons, PasswordResetOTP, SquareCredentials, StripeCredentials, PayPalCredentials, ThumbtackProfile


class BusinessAdmin(admin.ModelAdmin):
    list_display = ('businessName', 'user', 'phone', 'isActive', 'isApproved', 'createdAt')
    list_filter = ('isActive', 'isApproved', 'createdAt')
    search_fields = ('businessName', 'user__username', 'phone', 'address')
    readonly_fields = ('createdAt', 'updatedAt')
    actions = ['approve_businesses', 'reject_businesses']
    
    def approve_businesses(self, request, queryset):
        updated = queryset.update(isApproved=True, isActive=True)
        self.message_user(
            request,
            f'{updated} business(es) have been approved and activated.',
            messages.SUCCESS
        )
    approve_businesses.short_description = "Approve selected businesses"
    
    def reject_businesses(self, request, queryset):
        updated = queryset.update(isApproved=False, isActive=False)
        self.message_user(
            request,
            f'{updated} business(es) have been rejected and deactivated.',
            messages.WARNING
        )
    reject_businesses.short_description = "Reject selected businesses"

admin.site.register(Business, BusinessAdmin)


@admin.register(BusinessSettings)
class BusinessSettingsAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'bedroomPrice', 'bathroomPrice', 'depositFee', 'taxPercent', 'createdAt', 'updatedAt')
    search_fields = ('business__businessName',)
    readonly_fields = ('createdAt', 'updatedAt')

@admin.register(ApiCredential)
class ApiCredentialAdmin(admin.ModelAdmin):
    list_display = ('id', 'business')
    search_fields = ('business__businessName',)

@admin.register(CustomAddons)
class CustomAddonsAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'addonName', 'addonDataName', 'addonPrice')
    search_fields = ('business__businessName', 'addonName', 'addonDataName')



@admin.register(PasswordResetOTP)
class PasswordResetOTPAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'otp', 'is_used', 'failed_attempts', 'otp_sent_count', 'created_at', 'expires_at')
    search_fields = ('user__username', 'otp', 'token')
    readonly_fields = ('created_at', 'expires_at')

@admin.register(SquareCredentials)
class SquareCredentialsAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'access_token', 'app_id', 'location_id', 'created_at', 'updated_at')
    search_fields = ('business__businessName', 'access_token', 'app_id', 'location_id')
    readonly_fields = ('created_at', 'updated_at')

@admin.register(StripeCredentials)
class StripeCredentialsAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'stripe_secret_key', 'stripe_publishable_key')
    search_fields = ('business__businessName', 'stripe_secret_key', 'stripe_publishable_key')

@admin.register(PayPalCredentials)
class PayPalCredentialsAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'paypal_client_id', 'paypal_secret_key')
    search_fields = ('business__businessName', 'paypal_client_id', 'paypal_secret_key')

@admin.register(ThumbtackProfile)
class ThumbtackProfileAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'thumbtack_business_id', 'access_token', 'refresh_token', 'created_at', 'updated_at')
    search_fields = ('business__businessName', 'thumbtack_business_id', 'access_token', 'refresh_token')
    readonly_fields = ('created_at', 'updated_at')
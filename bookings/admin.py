from django.contrib import admin
from .models import Booking, BookingCustomAddons, Coupon, CouponUsage
from .payout_models import CleanerPayout
from django.utils.html import format_html

@admin.register(BookingCustomAddons)
class BookingCustomAddonsAdmin(admin.ModelAdmin):
    list_display = ('addon', 'qty', 'createdAt')
    list_filter = ('addon', 'createdAt')
    search_fields = ('addon__addonName',)
    readonly_fields = ('createdAt', 'updatedAt')

class BookingCustomAddonsInline(admin.TabularInline):
    model = Booking.customAddons.through  # Use the through model for ManyToMany
    extra = 1
    # No createdAt/updatedAt on the through model

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('bookingId', 'get_full_name', 'cleaningDate', 'serviceType', 'recurring', 'totalPrice', 'paymentMethod', 'isCompleted', 'createdAt', 'updatedAt')
    list_filter = ('serviceType', 'recurring', 'paymentMethod', 'isCompleted', 'createdAt', 'cleaningDate')
    search_fields = ('bookingId', 'customer__first_name', 'customer__last_name', 'customer__email', 'customer__phone_number', 'customer__address', 'customer__city', 'customer__state_or_province')
    readonly_fields = ('createdAt', 'updatedAt', 'bookingId')
    date_hierarchy = 'cleaningDate'
    list_per_page = 50
    inlines = [BookingCustomAddonsInline]
   

    def get_full_name(self, obj):
        return f"{obj.customer.first_name} {obj.customer.last_name}" if obj.customer else 'N/A'

    get_full_name.short_description = 'Customer Name'

@admin.register(CleanerPayout)
class CleanerPayoutAdmin(admin.ModelAdmin):
    list_display = ('payout_id', 'get_cleaner_name', 'amount', 'status', 'payment_method', 'payment_reference', 'created_at', 'updated_at', 'paid_at')
    list_filter = ('status', 'created_at', 'paid_at')
    search_fields = ('payout_id', 'cleaner_profile__cleaner__name', 'payment_reference')
    readonly_fields = ('created_at', 'updated_at', 'payout_id')
    date_hierarchy = 'created_at'

    def get_cleaner_name(self, obj):
        return obj.cleaner_profile.cleaner.name if obj.cleaner_profile and obj.cleaner_profile.cleaner else 'N/A'
    get_cleaner_name.short_description = 'Cleaner'


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = ['code', 'business', 'discount_type', 'discount_value', 'status', 'current_uses', 'max_uses', 'valid_from', 'valid_until', 'is_active']
    list_filter = ['status', 'discount_type', 'is_active', 'business']
    search_fields = ['code', 'description']
    readonly_fields = ['current_uses', 'created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('business', 'code', 'description', 'is_active')
        }),
        ('Discount Details', {
            'fields': ('discount_type', 'discount_value', 'min_booking_amount')
        }),
        ('Usage Limits', {
            'fields': ('max_uses', 'max_uses_per_customer', 'current_uses')
        }),
        ('Validity Period', {
            'fields': ('valid_from', 'valid_until', 'status')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj:  # Editing an existing object
            return self.readonly_fields + ['business', 'created_by']
        return self.readonly_fields


@admin.register(CouponUsage)
class CouponUsageAdmin(admin.ModelAdmin):
    list_display = ['coupon', 'booking', 'customer', 'discount_amount', 'applied_at']
    list_filter = ['applied_at', 'coupon']
    search_fields = ['coupon__code', 'customer__email', 'booking__bookingId']
    readonly_fields = ['coupon', 'booking', 'customer', 'discount_amount', 'applied_at']
    date_hierarchy = 'applied_at'
    
    def has_add_permission(self, request):
        return False  # Prevent manual creation
    
    def has_change_permission(self, request, obj=None):
        return False  # Prevent editing
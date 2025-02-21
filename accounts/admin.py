from django.contrib import admin

from .models import Business, BusinessSettings, BookingIntegration, ApiCredential, CustomAddons


admin.site.register(Business)
admin.site.register(BusinessSettings)
admin.site.register(BookingIntegration)
admin.site.register(ApiCredential)
admin.site.register(CustomAddons)
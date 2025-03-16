from django.contrib import admin

from .models import Business, BusinessSettings, ApiCredential, CustomAddons, PasswordResetOTP, SMTPConfig


admin.site.register(Business)
admin.site.register(BusinessSettings)
admin.site.register(ApiCredential)
admin.site.register(CustomAddons)
admin.site.register(SMTPConfig)
admin.site.register(PasswordResetOTP)
from django.contrib import admin

from .models import PlatformIntegration, DataMapping, IntegrationLog

admin.site.register(PlatformIntegration)
admin.site.register(DataMapping)
admin.site.register(IntegrationLog)

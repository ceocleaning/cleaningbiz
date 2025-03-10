from django.contrib import admin

# Register your models here.
from .models import Chat, Messages, AgentConfiguration


class AgentConfigurationAdmin(admin.ModelAdmin):
    fieldsets = (
        ('Basic Information', {
            'fields': ('business', 'agent_name', 'agent_role')
        }),
        ('Business Details', {
            'fields': ('business_description', 'business_mission'),
            'classes': ('collapse',),
        }),
        ('Services', {
            'fields': ('services',),
        }),
        ('Additional Settings', {
            'fields': ('custom_instructions',),
            'classes': ('collapse',),
        }),
    )
    list_display = ('business', 'agent_name')
    search_fields = ('business__businessName', 'agent_name')


admin.site.register(Chat)
admin.site.register(Messages)
admin.site.register(AgentConfiguration, AgentConfigurationAdmin)
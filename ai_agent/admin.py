from django.contrib import admin
from django.utils.html import format_html
import json

# Register your models here.
from .models import Chat, Messages, AgentConfiguration

class MessagesInline(admin.TabularInline):
    model = Messages
    extra = 0
    readonly_fields = ('role', 'message', 'createdAt')
    can_delete = False
    
    def has_add_permission(self, request, obj=None):
        return False

class ChatAdmin(admin.ModelAdmin):
    list_display = ('id', 'clientPhoneNumber', 'business', 'status', 'has_summary', 'createdAt')
    list_filter = ('status', 'business', 'createdAt')
    search_fields = ('clientPhoneNumber', 'sessionKey', 'business__businessName')
    readonly_fields = ('formatted_summary',)
    inlines = [MessagesInline]
    
    def has_summary(self, obj):
        if obj.summary and isinstance(obj.summary, dict) and len(obj.summary.keys()) > 0:
            return True
        return False
    has_summary.boolean = True
    has_summary.short_description = "Has Summary"
    
    def formatted_summary(self, obj):
        if not obj.summary:
            return "No summary available"
        
        try:
            # Format the JSON data nicely for display
            if isinstance(obj.summary, dict):
                html = "<div style='max-height: 400px; overflow: auto;'>"
                html += "<table style='width: 100%; border-collapse: collapse;'>"
                html += "<tr><th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;'>Field</th>"
                html += "<th style='border: 1px solid #ddd; padding: 8px; text-align: left; background-color: #f2f2f2;'>Value</th></tr>"
                
                for key, value in obj.summary.items():
                    html += f"<tr><td style='border: 1px solid #ddd; padding: 8px;'>{key}</td>"
                    html += f"<td style='border: 1px solid #ddd; padding: 8px;'>{value}</td></tr>"
                
                html += "</table></div>"
                return format_html(html)
            else:
                # If it's a JSON string, pretty-print it
                return format_html("<pre>{}</pre>", json.dumps(obj.summary, indent=2))
        except Exception as e:
            return f"Error formatting summary: {str(e)}"
    
    formatted_summary.short_description = "Summary Content"
    
    fieldsets = (
        (None, {
            'fields': ('clientPhoneNumber', 'sessionKey', 'business', 'status')
        }),
        ('Summary Information', {
            'fields': ('formatted_summary',),
            'classes': ('collapse',),
        }),
    )

class MessagesAdmin(admin.ModelAdmin):
    list_display = ('id', 'chat', 'role', 'short_message', 'createdAt')
    list_filter = ('role', 'createdAt')
    search_fields = ('message', 'chat__clientPhoneNumber')
    
    def short_message(self, obj):
        return obj.message[:50] + '...' if len(obj.message) > 50 else obj.message
    short_message.short_description = 'Message'

class AgentConfigurationAdmin(admin.ModelAdmin):
    list_display = ('id', 'business', 'agent_name')
    search_fields = ('business__businessName', 'agent_name')

admin.site.register(Chat, ChatAdmin)
admin.site.register(Messages, MessagesAdmin)
admin.site.register(AgentConfiguration, AgentConfigurationAdmin)
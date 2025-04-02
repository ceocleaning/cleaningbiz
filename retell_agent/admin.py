from django.contrib import admin
from .models import RetellAgent, RetellLLM

@admin.register(RetellAgent)
class RetellAgentAdmin(admin.ModelAdmin):
    list_display = ('agent_name', 'agent_id', 'business', 'llm', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('agent_name', 'agent_id', 'business__name')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['llm']

@admin.register(RetellLLM)
class RetellLLMAdmin(admin.ModelAdmin):
    list_display = ('model', 'llm_id', 'business', 'created_at')
    list_filter = ('created_at', 'model')
    search_fields = ('llm_id', 'business__name', 'model')
    readonly_fields = ('created_at', 'updated_at')

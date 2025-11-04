from django.contrib import admin
from .models import AgentConfig, Chat, Message

admin.site.register(AgentConfig)
admin.site.register(Chat)
admin.site.register(Message)

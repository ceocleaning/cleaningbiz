from django.contrib import admin

# Register your models here.
from .models import Chat, Messages, AgentConfiguration



   


admin.site.register(Chat)
admin.site.register(Messages)
admin.site.register(AgentConfiguration)
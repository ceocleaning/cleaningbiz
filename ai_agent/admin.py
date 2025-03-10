from django.contrib import admin

# Register your models here.
from .models import Chat, Messages

admin.site.register(Chat)
admin.site.register(Messages)
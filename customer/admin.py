from django.contrib import admin
from .models import Customer


class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_full_name', 'email', 'phone_number', 'created_at', 'updated_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')
    list_per_page = 50

admin.site.register(Customer, CustomerAdmin)


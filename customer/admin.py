from django.contrib import admin
from .models import Customer, Review


class CustomerAdmin(admin.ModelAdmin):
    list_display = ('id', 'get_full_name', 'email', 'phone_number', 'created_at', 'updated_at')
    search_fields = ('first_name', 'last_name', 'email', 'phone_number')
    list_per_page = 50


class ReviewAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'booking', 'rating', 'created_at', 'updated_at')
    search_fields = ('user__first_name', 'user__last_name', 'booking__id')
    list_per_page = 50

admin.site.register(Customer, CustomerAdmin)
admin.site.register(Review, ReviewAdmin)


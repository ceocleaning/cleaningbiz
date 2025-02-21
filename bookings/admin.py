from django.contrib import admin
from .models import Booking, Invoice, Payment, BookingCustomAddons

# Register your models here.

admin.site.register(Booking)
admin.site.register(Invoice)
admin.site.register(Payment)
admin.site.register(BookingCustomAddons)

from django.contrib import admin
from .models import Booking, BookingCustomAddons
from .payout_models import CleanerPayout

# Register your models here.

admin.site.register(Booking)
admin.site.register(CleanerPayout)
admin.site.register(BookingCustomAddons)

from django.contrib import admin
from .models import Lead, Cleaners, CleanerAvailability

admin.site.register(Lead)
admin.site.register(Cleaners)
admin.site.register(CleanerAvailability)

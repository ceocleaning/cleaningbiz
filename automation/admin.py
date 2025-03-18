from django.contrib import admin
from .models import Lead, Cleaners, CleanerAvailability

admin.site.register(Lead)
admin.site.register(Cleaners)
admin.site.register(CleanerAvailability)




admin.site.site_header = "CleaningBiz AI Dashboard"
admin.site.site_title = "CleaningBiz AI Dashboard"
admin.site.index_title = "Welcome to CleaningBiz AI Dashboard"
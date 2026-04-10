from django.contrib import admin
from .models import PlatformSettings, SupportTicket, TicketComment, DemoLeads

admin.site.register(PlatformSettings)
admin.site.register(SupportTicket)
admin.site.register(TicketComment)
admin.site.register(DemoLeads)


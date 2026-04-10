from django.urls import path
from . import views

app_name = 'saas'

urlpatterns = [
    # Support ticket URLs
    path('support/submit-ticket/', views.submit_ticket, name='submit_ticket'),
    path('support/my-tickets/', views.my_tickets, name='my_tickets'),
    path('support/tickets/<int:ticket_id>/', views.ticket_detail, name='ticket_detail'),
    
    # Maintenance mode URL
    path('maintenance/', views.maintenance_view, name='maintenance'),
    
    # Demo Leads and Video
    path('submit-demo-lead/', views.submit_demo_lead, name='submit_demo_lead'),
    path('demo-video/', views.demo_video, name='demo_video'),
]

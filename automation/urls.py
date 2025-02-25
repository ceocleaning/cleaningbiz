from django.urls import path
from . import views
from .webhooks import handle_retell_webhook, thumbtack_webhook



urlpatterns = [
    path('', views.home, name='home'),

    path('webhook/<str:secretKey>/', handle_retell_webhook, name='handle_retell_webhook_no_slash'),
    path('webhook/<str:secretKey>', handle_retell_webhook, name='handle_retell_webhook'),

    path('thumbtack-webhook/', thumbtack_webhook, name='thumbtack_webhook_no_slash'),
    path('thumbtack-webhook', thumbtack_webhook, name='thumbtack_webhook'),

    # Lead Management URLs
    path('leads/', views.all_leads, name='all_leads'),
    path('leads/create/', views.create_lead, name='create_lead'),
    path('leads/<str:leadId>/', views.lead_detail, name='lead_detail'),
    path('leads/<str:leadId>/update/', views.update_lead, name='update_lead'),
    path('leads/<str:leadId>/delete/', views.delete_lead, name='delete_lead'),

   
]
from django.urls import path
from . import chatbot, views

app_name = 'ai_agent'

urlpatterns = [
    path('chat/', chatbot.chat_view, name='chat_view'),
    path('api/chat/', chatbot.chat_api, name='chat_api'),
    path('api/chat/<str:client_phone_number>/delete/', chatbot.delete_chat, name='delete_chat'),
    
    # Twilio webhook URL
    path('api/twilio/webhook/', views.twilio_webhook, name='twilio_webhook'),

    path('agent-config/create/', views.agent_config_create, name='agent_config_create'),
    path('agent-config/', views.agent_config_detail, name='agent_config'),
    path('agent-config/<str:config_id>/edit/', views.agent_config_edit, name='agent_config_edit'),
    path('agent-config/delete/', views.agent_config_delete, name='agent_config_delete'),
    path('agent-config/preview/', views.agent_config_preview, name='agent_config_preview'),
]
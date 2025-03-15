from django.urls import path
from . import views, openai_agent

app_name = 'ai_agent'

urlpatterns = [
    # OpenAI-based chatbot endpoints (primary endpoints)
    path('chat/', openai_agent.chat_view, name='chat_view'),
    path('api/chat/', openai_agent.chat_api, name='chat_api'),
    path('api/chat/<str:client_phone_number>/delete/', openai_agent.delete_chat, name='delete_chat'),
    
    # Legacy OpenAI-based chatbot endpoints (keeping for backward compatibility)
    path('openai-chat/', openai_agent.chat_view, name='openai_chat_view'),
    path('api/openai-chat/', openai_agent.chat_api, name='openai_chat_api'),
    path('api/openai-chat/<str:client_phone_number>/delete/', openai_agent.delete_chat, name='openai_delete_chat'),
    
    # Twilio webhook URL
    path('api/twilio/webhook/<str:secretKey>/', views.twilio_webhook, name='twilio_webhook'),

    path('agent-config/create/', views.agent_config_create, name='agent_config_create'),
    path('agent-config/', views.agent_config_detail, name='agent_config'),
    path('agent-config/<str:config_id>/edit/', views.agent_config_edit, name='agent_config_edit'),
    path('agent-config/delete/', views.agent_config_delete, name='agent_config_delete'),
    path('agent-config/preview/', views.agent_config_preview, name='agent_config_preview'),
]
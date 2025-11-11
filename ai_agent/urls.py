from django.urls import path
from . import views, openai_agent

app_name = 'ai_agent'

urlpatterns = [
    # OpenAI-based chatbot endpoints (primary endpoints)
    path('api/chat/', views.chat_api, name='chat_api'),
    path('api/chat/<str:client_phone_number>/delete/', views.delete_chat, name='delete_chat'),
    
    
    # Twilio webhook URL
    path('api/twilio/webhook/<str:secretKey>/', views.twilio_webhook, name='twilio_webhook'),

    # New unified agent configuration pages
    path('agent-config/', views.agent_config_unified, name='agent_config'),
    path('agent-config/save/', views.agent_config_save, name='agent_config_save'),
    path('embed-agent/', views.embed_agent, name='embed_agent'),
    
    # Business credentials API
    path('api/business/credentials/', views.business_credentials_api, name='business_credentials_api'),
    
    # New SMS chat management views
    path('sms-chats/', views.all_chats, name='all_chats'),
    path('api/sms-chats/delete/', views.delete_chat, name='delete_sms_chat'),
    path('chat/<int:chat_id>/data', views.get_chat_data, name='get_chat_data'),
]
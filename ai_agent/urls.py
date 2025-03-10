from django.urls import path
from . import chatbot

app_name = 'ai_agent'

urlpatterns = [
    path('chat/', chatbot.chat_view, name='chat_view'),
    path('api/chat/', chatbot.chat_api, name='chat_api'),
    path('api/chat/<str:chat_id>/delete/', chatbot.delete_chat, name='delete_chat'),
]
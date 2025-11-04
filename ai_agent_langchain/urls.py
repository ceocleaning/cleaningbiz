from django.urls import path
from . import views, api_views

app_name = 'ai_agent'

urlpatterns = [
    # Unified agent dashboard
    path('', views.agent_dashboard, name='dashboard'),
    
    # Chat management
    path('chats/', views.chat_list, name='chat_list'),
    path('chats/<int:chat_id>/', views.chat_detail, name='chat_detail'),
    
    # API endpoints
    path('api/process-message/', views.process_message, name='process_message'),
    path('api/twilio-webhook/<str:business_id>/', views.twilio_webhook, name='twilio_webhook'),
    
    # Chat widget for embedding
    path('widget/<str:business_id>/', views.chat_widget, name='chat_widget'),
    
    # Retell API endpoints
    path('api/retell/check-availability/', api_views.check_availability, name='retell_check_availability'),
    path('api/retell/book-appointment/', api_views.book_appointment, name='retell_book_appointment'),
    path('api/retell/cancel-appointment/', api_views.cancel_appointment, name='retell_cancel_appointment'),
    path('api/retell/reschedule-appointment/', api_views.reschedule_appointment, name='retell_reschedule_appointment'),
    path('api/retell/get-appointment/<str:booking_id>/', api_views.get_appointment, name='retell_get_appointment'),
]

from django.urls import path
from . import views

app_name = 'notification'

urlpatterns = [
    # Web views
    path('', views.notification_list, name='notification_list'),
    path('<uuid:notification_id>/', views.notification_detail, name='notification_detail'),
    path('<uuid:notification_id>/mark-read/', views.mark_notification_read, name='mark_notification_read'),
    
    # API endpoints
    path('api/notifications/', views.api_notification_list, name='api_notification_list'),
    path('api/notifications/<uuid:notification_id>/mark-read/', views.api_mark_notification_read, name='api_mark_notification_read'),
]
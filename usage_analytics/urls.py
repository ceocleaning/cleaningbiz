from django.urls import path
from . import views

app_name = 'usage_analytics'

urlpatterns = [
    path('', views.usage_overview, name='usage_overview'),
    path('voice/', views.voice_analytics, name='voice_analytics'),
    path('sms/', views.sms_analytics, name='sms_analytics'),
    path('api/usage-data/', views.get_usage_data, name='get_usage_data'),
]

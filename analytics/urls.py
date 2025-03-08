from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    path('', views.analytics_dashboard, name='analytics_dashboard'),# Dont change this URL Path
    path('api/revenue-data/', views.revenue_data_api, name='revenue_data_api'),
    path('api/booking-data/', views.booking_data_api, name='booking_data_api'),
    path('api/cleaner-data/', views.cleaner_data_api, name='cleaner_data_api'),
    path('api/customer-data/', views.customer_data_api, name='customer_data_api'),
    path('api/addon-data/', views.addon_data_api, name='addon_data_api'),
]

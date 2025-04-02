from django.urls import path
from . import views

app_name = 'subscription'

urlpatterns = [
    path('', views.subscription_management, name='subscription_management'),
    path('billing-history/', views.billing_history, name='billing_history'),
    path('change-plan/<int:plan_id>/', views.change_plan, name='change_plan'),
    path('cancel/', views.cancel_subscription, name='cancel_subscription'),
    path('api/subscription-data/', views.get_subscription_data, name='get_subscription_data'),
    path('api/track/<str:metric_type>/', views.track_usage, name='track_usage'),
    
    # New payment URLs
    path('select-plan/', views.select_plan, name='select_plan'),
    path('select-plan/<int:plan_id>/', views.select_plan, name='select_plan'),
    path('process-payment/<int:plan_id>/', views.process_payment, name='process_payment'),
    path('success/<int:subscription_id>/<str:transaction_id>/', views.subscription_success, name='subscription_success'),
    

]


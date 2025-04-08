from django.urls import path
from . import views

app_name = 'admin_dashboard'

urlpatterns = [
    # Dashboard index
    path('', views.dashboard_index, name='index'),
    
    # Subscription Plans
    path('subscription-plans/', views.subscription_plans, name='subscription_plans'),
    path('subscription-plans/add/', views.add_plan, name='add_plan'),
    path('subscription-plans/edit/', views.edit_plan, name='edit_plan'),
    path('subscription-plans/delete/', views.delete_plan, name='delete_plan'),
    
    # Features
    path('features/', views.features, name='features'),
    path('features/add/', views.add_feature, name='add_feature'),
    path('features/edit/', views.edit_feature, name='edit_feature'),
    path('features/delete/', views.delete_feature, name='delete_feature'),
    
    # Coupons
    path('coupons/', views.coupons, name='coupons'),
    path('coupons/add/', views.add_coupon, name='add_coupon'),
    path('coupons/edit/', views.edit_coupon, name='edit_coupon'),
    path('coupons/delete/', views.delete_coupon, name='delete_coupon'),
    
    # Businesses
    path('businesses/', views.businesses, name='businesses'),
    path('businesses/add/', views.add_business, name='add_business'),
    path('businesses/edit/', views.edit_business, name='edit_business'),
    path('businesses/approve/', views.approve_business, name='approve_business'),
    path('businesses/reject/', views.reject_business, name='reject_business'),
    path('businesses/delete/', views.delete_business, name='delete_business'),
    path('businesses/export/', views.export_businesses, name='export_businesses'),
    path('businesses/<int:business_id>/', views.business_detail, name='business_detail'),
    
    # Subscription Management
    path('subscriptions/', views.subscriptions, name='subscriptions'),
    path('subscriptions/assign/', views.assign_subscription, name='assign_subscription'),
    path('subscriptions/admin-cancel-plan/', views.admin_cancel_plan, name='admin_cancel_plan'),
    path('subscriptions/admin-change-plan/', views.admin_change_plan, name='admin_change_plan'),
    
    # User Management
    path('users/', views.users, name='users'),
    path('users/add/', views.add_user, name='add_user'),
    path('users/edit/', views.edit_user, name='edit_user'),
    path('users/delete/', views.delete_user, name='delete_user'),
    
    # Activity Logs
    path('activity-logs/', views.activity_logs, name='activity_logs'),
    path('activity-logs/<int:log_id>/', views.activity_log_detail, name='activity_log_detail'),
]
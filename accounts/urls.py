from django.urls import path
from . import views

app_name = 'accounts'

urlpatterns = [
    path('login/', views.loginPage, name='login'),
    path('register/', views.SignupPage, name='signup'),
    path('logout/', views.logoutUser, name='logout'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/update/', views.update_profile, name='update_profile'),
    path('profile/change-password/', views.change_password, name='change_password'),
    path('profile/test-email/', views.test_email_settings, name='test_email_settings'),
    path('register-business/', views.register_business, name='register_business'),
    path('business/edit/', views.edit_business, name='edit_business'),
    path('business/settings/edit/', views.edit_business_settings, name='edit_business_settings'),
    path('custom-addon/add/', views.add_custom_addon, name='add_custom_addon'),
    path('custom-addon/<int:addon_id>/edit/', views.edit_custom_addon, name='edit_custom_addon'),
    path('custom-addon/<int:addon_id>/delete/', views.delete_custom_addon, name='delete_custom_addon'),
    path('business/credentials/edit/', views.edit_credentials, name='edit_credentials'),
    path('business/credentials/generate-secret/', views.generate_secret_key, name='generate_secret_key'),
    path('business/credentials/regenerate-secret/', views.regenerate_secret_key, name='regenerate_secret_key'),
   
    
    # Password Reset URLs
    path('forgot-password/', views.forgot_password, name='forgot_password'),
    path('verify-otp/<str:email>/', views.verify_otp, name='verify_otp'),
    path('resend-otp/<str:email>/', views.resend_otp, name='resend_otp'),
    path('reset-password/<str:email>/<str:token>/', views.reset_password, name='reset_password'),
    
    # SMTP Configuration URLs
    path('smtp-config/', views.smtp_config, name='smtp_config'),
    path('smtp-config/delete/', views.delete_smtp_config, name='delete_smtp_config'),
    
    # Approval Pending URL
    path('approval-pending/', views.approval_pending, name='approval_pending'),
    
    # Admin Business Approval URLs
    path('admin/business-approval/', views.admin_business_approval, name='admin_business_approval'),
    path('admin/business/<int:business_id>/approve/', views.approve_business, name='approve_business'),
    path('admin/business/<int:business_id>/reject/', views.reject_business, name='reject_business'),


    path('update-business-settings/', views.update_business_settings, name='update_business_settings'),
    
    # Square and Payment URLs
    path('payment-square/', views.payment_square_view, name='payment_square'),
    path('square-credentials/manage/', views.manage_square_credentials, name='manage_square_credentials'),
    
    # Cleaner Management URLs
    path('cleaners/', views.manage_cleaners, name='manage_cleaners'),
    path('cleaners/<int:cleaner_id>/register/', views.register_cleaner_user, name='register_cleaner_user'),
    path('cleaners/<int:cleaner_id>/', views.cleaner_detail, name='cleaner_detail'),
]
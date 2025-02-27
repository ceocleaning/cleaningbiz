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
    path('profile/update-credentials/', views.update_credentials, name='update_credentials'),
    path('profile/test-email/', views.test_email_settings, name='test_email_settings'),
    path('register-business/', views.register_business, name='register_business'),
    path('business/edit/', views.edit_business, name='edit_business'),
    path('business/settings/edit/', views.edit_business_settings, name='edit_business_settings'),
    path('custom-addon/add/', views.add_custom_addon, name='add_custom_addon'),
    path('custom-addon/<int:addon_id>/edit/', views.edit_custom_addon, name='edit_custom_addon'),
    path('custom-addon/<int:addon_id>/delete/', views.delete_custom_addon, name='delete_custom_addon'),
    path('business/credentials/edit/', views.edit_credentials, name='edit_credentials'),
    path('business/credentials/generate-secret/', views.generate_secret_key, name='generate_secret_key'),
    path('business/integrations/add/', views.add_integration, name='add_integration'),
    path('business/integrations/<int:pk>/edit/', views.edit_integration, name='edit_integration'),
    path('business/integrations/<int:pk>/delete/', views.delete_integration, name='delete_integration'),
]
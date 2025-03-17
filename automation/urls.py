from django.urls import path
from . import views
from .webhooks import handle_retell_webhook, thumbtack_webhook
from .api_views import check_availability_retell, test_check_availability, check_availability_for_booking, create_booking, sendCommercialFormLink



urlpatterns = [
    path('', views.LandingPage, name='LandingPage'),
    path('pricing/', views.PricingPage, name='PricingPage'),
    path('features/', views.FeaturesPage, name='FeaturesPage'),
    path('about-us/', views.AboutUsPage, name='AboutUsPage'),
    path('contact-us/', views.ContactUsPage, name='ContactUsPage'),
    path('docs/', views.DocsPage, name='DocsPage'),
    path('dashboard/', views.home, name='home'),
    path('webhook/<str:secretKey>/', handle_retell_webhook, name='retell_webhook'),
    path('webhook/thumbtack/<str:secretKey>/', thumbtack_webhook, name='thumbtack_webhook'),

    # Lead Management URLs
    path('leads/', views.all_leads, name='all_leads'),
    path('leads/create/', views.create_lead, name='create_lead'),
    path('leads/<str:leadId>/', views.lead_detail, name='lead_detail'),
    path('leads/<str:leadId>/update/', views.update_lead, name='update_lead'),
    path('leads/<str:leadId>/delete/', views.delete_lead, name='delete_lead'),

    # API endpoints
    path('api/availability/<str:secretKey>/', check_availability_retell, name='check_availability'),
    path('api/availability/<str:secretKey>/test/', test_check_availability, name='test_check_availability'),
    path('api/check-availability/', check_availability_for_booking, name='check_availability_for_booking'),
    path('api/create-booking/', create_booking, name='create_booking'),
    path('api/send-commercial-form-link/', sendCommercialFormLink, name='send_commercial_form_link'),
   
    
    # Test pages
    path('test/', views.test_features, name='test_features'),
    path('test/availability/', views.test_availability_api, name='test_availability_api'),

   
    # Cleaners URLs
    path('cleaners/', views.cleaners_list, name='cleaners_list'),
    path('cleaners/add/', views.add_cleaner, name='add_cleaner'),
    path('cleaners/<int:cleaner_id>/', views.cleaner_detail, name='cleaner_detail'),
    path('cleaners/<int:cleaner_id>/monthly-schedule/', views.cleaner_monthly_schedule, name='cleaner_monthly_schedule'),
    path('cleaners/<int:cleaner_id>/update-profile/', views.update_cleaner_profile, name='update_cleaner_profile'),
    path('cleaners/<int:cleaner_id>/update-schedule/', views.update_cleaner_schedule, name='update_cleaner_schedule'),
    path('cleaners/<int:cleaner_id>/add-specific-date/', views.add_specific_date, name='add_specific_date'),
    path('cleaners/<int:cleaner_id>/delete-specific-date/<int:exception_id>/', views.delete_specific_date, name='delete_specific_date'),
    path('cleaners/<int:cleaner_id>/toggle-availability/', views.toggle_cleaner_availability, name='toggle_cleaner_availability'),
    path('cleaners/<int:cleaner_id>/toggle-active/', views.toggle_cleaner_active, name='toggle_cleaner_active'),
    path('cleaners/<int:cleaner_id>/delete/', views.delete_cleaner, name='delete_cleaner'),

    # Business Schedule URLs
    path('business-schedule/', views.business_monthly_schedule, name='business_monthly_schedule'),
]
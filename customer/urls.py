from django.urls import path
from .views import dashboard, businesses_list, add_booking, customer_bookings, booking_detail, edit_booking, submit_review, edit_review, delete_review, customer_reviews
from .auth_views import customer_signup, customer_login, customer_logout, profile, change_password
from .api_views import booking_api
from .account_linking import link_customer_account, check_existing_customer, view_linked_businesses
from .pricing_views import (
    customer_pricing_list, customer_pricing_detail, customer_pricing_update,
    customer_pricing_toggle, customer_pricing_delete, customer_pricing_comparison
)
from .pricing_api import (
    get_customer_pricing, calculate_booking_total, get_all_pricing
)
from .check_customer_api import check_customer


app_name = 'customer'

urlpatterns = [
    path('dashboard/', dashboard, name='dashboard'),
    path('signup/', customer_signup, name='signup'),
    path('login/', customer_login, name='login'),
    path('logout/', customer_logout, name='logout'),
    path('profile/', profile, name='profile'),
    path('change-password/', change_password, name='change_password'),
    path('businesses/', businesses_list, name='businesses_list'),
    path('booking/add/<str:business_id>/', add_booking, name='add_booking'),
    path('bookings/', customer_bookings, name='bookings'),
    path('booking/<str:bookingId>/', booking_detail, name='booking_detail'),
    path('booking/edit/<str:bookingId>/', edit_booking, name='edit_booking'),
    path('booking/review/<str:bookingId>/', submit_review, name='submit_review'),
    path('review/edit/<int:review_id>/', edit_review, name='edit_review'),
    path('review/delete/<int:review_id>/', delete_review, name='delete_review'),
    path('reviews/', customer_reviews, name='reviews'),
    
    # API endpoints
    path('api/booking/<str:business_id>/', booking_api, name='booking_api'),
    
    # Account linking
    path('link-account/', link_customer_account, name='link_account'),
    path('check-existing-customer/', check_existing_customer, name='check_existing_customer'),
    path('linked-businesses/', view_linked_businesses, name='linked_businesses'),
    
    # Customer Pricing Management
    path('pricing/', customer_pricing_list, name='pricing_list'),
    path('pricing/<uuid:customer_id>/', customer_pricing_detail, name='pricing_detail'),
    path('pricing/<uuid:customer_id>/update/', customer_pricing_update, name='pricing_update'),
    path('pricing/<uuid:customer_id>/toggle/', customer_pricing_toggle, name='pricing_toggle'),
    path('pricing/<uuid:customer_id>/delete/', customer_pricing_delete, name='pricing_delete'),
    path('pricing/<uuid:customer_id>/comparison/', customer_pricing_comparison, name='pricing_comparison'),
    
    # Pricing API Endpoints
    path('api/pricing/<business_id>/customer/<uuid:customer_id>/', get_customer_pricing, name='api_customer_pricing'),
    path('api/pricing/calculate/', calculate_booking_total, name='api_calculate_total'),
    path('api/pricing/<business_id>/default/', get_all_pricing, name='api_default_pricing'),
    path('api/check-customer/', check_customer, name='api_check_customer'),
]

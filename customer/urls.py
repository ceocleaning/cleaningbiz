from django.urls import path
from .views import dashboard, businesses_list, add_booking, customer_bookings, booking_detail, edit_booking, submit_review, edit_review, delete_review, customer_reviews
from .auth_views import customer_signup, customer_login, customer_logout, profile, change_password
from .api_views import booking_api
from .account_linking import link_customer_account, check_existing_customer, view_linked_businesses


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
]

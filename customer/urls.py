from django.urls import path
from .views import dashboard, businesses_list, add_booking, customer_bookings, booking_detail, edit_booking
from .auth_views import customer_signup, customer_login, customer_logout, profile, change_password


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
]

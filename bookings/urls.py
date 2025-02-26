from django.urls import path
from . import views

app_name = 'bookings'

urlpatterns = [
    path('', views.all_bookings, name='all_bookings'),
    path('create/', views.create_booking, name='create_booking'),
    path('edit/<str:bookingId>/', views.edit_booking, name='edit_booking'),
    path('mark-completed/<str:bookingId>/', views.mark_completed, name='mark_completed'),
    path('delete/<str:bookingId>/', views.delete_booking, name='delete_booking'),
    path('detail/<str:bookingId>/', views.booking_detail, name='booking_detail'),
    
    # Invoice URLs
    
]
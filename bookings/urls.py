from django.urls import path, include
from . import views
from . import payout_urls
from . import coupon_views
from . import api_views

app_name = 'bookings'

urlpatterns = [
    path('', views.all_bookings, name='all_bookings'),
    path('create/', views.create_booking, name='create_booking'),
    path('edit/<str:bookingId>/', views.edit_booking, name='edit_booking'),
    path('mark-completed/<str:bookingId>/', views.mark_completed, name='mark_completed'),
    path('booking/<str:bookingId>/delete/', views.delete_booking, name='delete_booking'),
    path('detail/<str:bookingId>/', views.booking_detail, name='booking_detail'),
    path('customers/', views.customers, name='customers'),
    path('customers/detail/<uuid:id>/', views.customer_detail, name='customer_detail'),
    path('bulk-delete/', views.bulk_delete_bookings, name='bulk_delete_bookings'),
    path('calendar/', views.booking_calendar, name='booking_calendar'),
    path('embed-widget/', views.embed_booking_widget, name='embed_booking_widget'),
    path('api/booking-history-data/', views.booking_history_data, name='booking_history_data'),

    path('api/reschedule-booking/', views.reschedule_booking, name='reschedule_booking'),
    path('api/cancel-booking/', views.cancel_booking, name='cancel_booking'),
    
    # Job Management URLs
    path('reopen-job/<str:booking_id>/', views.reopen_job_for_cleaner, name='reopen_job_for_cleaner'),
    path('force-assign/<str:booking_id>/<str:cleaner_id>/', views.force_assign_booking, name='force_assign_booking'),
    path('reset-open-jobs/<str:booking_id>/', views.reset_open_jobs, name='reset_open_jobs'),
    
    # Coupon URLs
    path('coupons/', coupon_views.coupon_list, name='coupon_list'),
    path('coupons/create/', coupon_views.coupon_create, name='coupon_create'),
    path('coupons/<int:coupon_id>/', coupon_views.coupon_detail, name='coupon_detail'),
    path('coupons/<int:coupon_id>/edit/', coupon_views.coupon_edit, name='coupon_edit'),
    path('coupons/<int:coupon_id>/delete/', coupon_views.coupon_delete, name='coupon_delete'),
    path('coupons/<int:coupon_id>/toggle-status/', coupon_views.coupon_toggle_status, name='coupon_toggle_status'),
    
    # Coupon API
    path('api/validate-coupon/', api_views.validate_coupon, name='validate_coupon'),
    
    # Payout URLs
    path('', include(payout_urls)),
    
    # Invoice URLs
    
]
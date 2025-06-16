from django.urls import path
from . import payout_views

urlpatterns = [
    path('payouts/', payout_views.payouts_dashboard, name='payouts_dashboard'),
    path('payouts/detail/<str:payout_id>/', payout_views.payout_detail, name='payout_detail'),
    path('payouts/create/', payout_views.create_payout, name='create_payout'),
    path('payouts/mark-as-paid/<str:payout_id>/', payout_views.mark_payout_as_paid, name='mark_payout_as_paid'),
    path('payouts/cancel/<str:payout_id>/', payout_views.cancel_payout, name='cancel_payout'),
]

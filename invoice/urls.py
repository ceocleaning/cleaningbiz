from django.urls import path
from . import views, payment_views

app_name = 'invoice'

urlpatterns = [
    path('invoices/', views.all_invoices, name='all_invoices'),
    path('invoices/create/<str:bookingId>/', views.create_invoice, name='create_invoice'),
    path('invoices/edit/<str:invoiceId>/', views.edit_invoice, name='edit_invoice'),
    path('invoices/delete/<str:invoiceId>/', views.delete_invoice, name='delete_invoice'),
    path('invoices/detail/<str:invoiceId>/', views.invoice_detail, name='invoice_detail'),
    path('invoices/mark-paid/<str:invoiceId>/', views.mark_invoice_paid, name='mark_invoice_paid'),
    path('invoices/<str:invoiceId>/preview/', views.invoice_preview, name='invoice_preview'),
    path('invoices/<str:invoiceId>/generate-pdf/', views.generate_pdf, name='generate_pdf'),
    path('invoices/process-payment/', payment_views.process_payment, name='process_payment'),
    path('invoices/process-manual-payment/', payment_views.process_manual_payment, name='process_manual_payment'),
    path('invoices/process-stripe-payment/', payment_views.process_stripe_payment, name='process_stripe_payment'),
    path('invoices/capture-stripe-payment/', payment_views.capture_stripe_payment, name='capture_stripe_payment'),
    path('invoices/process-paypal-payment/', payment_views.process_paypal_payment, name='process_paypal_payment'),
    path('bulk-delete/', views.bulk_delete_invoices, name='bulk_delete_invoices'),
    path('bank-transfer/<str:invoice_id>/', views.manual_payment, name='manual_payment'),
    path('approve-payment/<str:invoice_id>/<str:payment_id>/', views.approve_payment, name='approve_payment'),
    path('reject-payment/<str:invoice_id>/<str:payment_id>/', views.reject_payment, name='reject_payment'),
]
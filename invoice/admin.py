from django.contrib import admin

from .models import Invoice, Payment, BankAccount

# Register your models here.

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoiceId", "booking", "amount", "isPaid", "createdAt", "updatedAt")
    search_fields = ("invoiceId", "booking__id", "amount", "isPaid")
    list_filter = ("isPaid", "createdAt", "updatedAt")


admin.site.register(Invoice, InvoiceAdmin)


class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paymentId", "invoice", "amount", "paymentMethod", "squarePaymentId", "transactionId", "status", "paidAt", "createdAt", "updatedAt")
    search_fields = ("paymentId", "invoice__invoiceId", "amount", "paymentMethod", "squarePaymentId", "transactionId", "status", "paidAt")
    list_filter = ("status", "paymentMethod", "createdAt", "updatedAt")

admin.site.register(Payment, PaymentAdmin)



class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("business", "account_name", "account_number", "bank_name", "ifsc_code", "branch", "created_at", "updated_at")
    search_fields = ("business__id", "account_name", "account_number", "bank_name", "ifsc_code", "branch")
    list_filter = ("bank_name", "ifsc_code", "created_at", "updated_at")

admin.site.register(BankAccount, BankAccountAdmin)
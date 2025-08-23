from django.contrib import admin

from .models import Invoice, Payment, BankAccount

# Register your models here.

class InvoiceAdmin(admin.ModelAdmin):
    list_display = ("invoiceId", "booking", "amount", "isPaid")
    search_fields = ("invoiceId", "booking", "amount", "isPaid")
    list_filter = (["isPaid"])


admin.site.register(Invoice, InvoiceAdmin)


class PaymentAdmin(admin.ModelAdmin):
    list_display = ("paymentId", "invoice", "amount", "status", "paidAt", "paymentMethod")
    search_fields = ("paymentId", "invoice", "amount", "status", "paidAt", "paymentMethod")
    list_filter = (["status", "paymentMethod"])
   
admin.site.register(Payment, PaymentAdmin)



class BankAccountAdmin(admin.ModelAdmin):
    list_display = ("business",'account_number', 'bank_name', 'account_name')
    search_fields = ("business",'account_number', 'bank_name', 'account_name')

admin.site.register(BankAccount, BankAccountAdmin)
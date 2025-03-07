from django.db import models
import random
import string
# Create your models here.


class Invoice(models.Model):
    invoiceId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    booking = models.OneToOneField('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.IntegerField(default=0)
    isPaid = models.BooleanField(default=False)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Invoice for {self.booking.firstName} {self.booking.lastName} - {self.booking.email}"

    def generateInvoiceId(self):
        prefix = "INV"
        id = random.choices(string.ascii_letters + string.digits, k=5)
        return prefix + ''.join(id)
    
    def save(self, *args, **kwargs):
        if not self.invoiceId:
            self.invoiceId = self.generateInvoiceId()
        super().save(*args, **kwargs)
    


class Payment(models.Model):
    paymentId = models.CharField(max_length=11, unique=True, null=True, blank=True)  # Our Own ID
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='payment_details')
    amount = models.IntegerField(default=0)
    paymentMethod = models.CharField(max_length=50, null=True, blank=True)
    squarePaymentId = models.CharField(max_length=100, null=True, blank=True)  # Square's payment ID
    
    paidAt = models.DateTimeField(null=True, blank=True)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Payment for {self.invoice.booking.firstName} {self.invoice.booking.lastName} - {self.invoice.booking.email}"
    
    def generatePaymentId(self):
        prefix = "PY"
        id = random.choices(string.ascii_letters + string.digits, k=5)
        return prefix + ''.join(id)
    
    def save(self, *args, **kwargs):
        if not self.paymentId:
            self.paymentId = self.generatePaymentId()
        super().save(*args, **kwargs)

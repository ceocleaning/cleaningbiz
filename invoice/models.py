from django.db import models
import random
import string
import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.utils import timezone
from decimal import Decimal
# Create your models here.


class Invoice(models.Model):
    invoiceId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    booking = models.OneToOneField('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total_paid_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    isPaid = models.BooleanField(default=False)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoiceId}"

    def generateInvoiceId(self):
        prefix = "inv"
        id = random.choices(string.digits, k=8)
        return prefix + ''.join(id)
    
    def get_remaining_amount(self):
        return max(0, self.amount - self.total_paid_amount)
    
    def is_partially_paid(self):
        return 0 < self.total_paid_amount < self.amount
    
    def update_payment_status(self):
        completed_payments = self.payments.filter(status__in=['COMPLETED', 'APPROVED'])
        total_paid = sum(payment.amount for payment in completed_payments)
        
        self.total_paid_amount = total_paid

        print("Condition: Total Paid >= Invoice Amount: ",total_paid >= self.amount)
        if total_paid >= self.amount:
            self.isPaid = True
        else:
            self.isPaid = False
        self.save()
    

    class Meta:
        ordering = ['-createdAt']  # newest first
    

    @property
    def payment_details(self):
        return self.payments.first()
    
    def save(self, *args, **kwargs):
        if not self.invoiceId:
            self.invoiceId = self.generateInvoiceId()
        
        self.amount = Decimal(self.amount)
        self.total_paid_amount = Decimal(self.total_paid_amount)
        

        super().save(*args, **kwargs)
    


class Payment(models.Model):
    PAYMENT_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('AUTHORIZED', 'Authorized'),
        ('COMPLETED', 'Completed'),
        ('FAILED', 'Failed'),
        ('CANCELLED', 'Cancelled'),

        ('SUBMITTED', 'Submitted'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    PAYMENT_METHOD_CHOICES = [
        ('card', 'Card'),
        ('bank_transfer', 'Bank Transfer'),
     
    ]

    PAYMENT_TYPE_CHOICES = [
        ('partial', 'Partial Payment'),
        ('full', 'Full Payment'),
        ('authorized', 'Authorized Payment')
    ]

    payment_type = models.CharField(max_length=20, choices=PAYMENT_TYPE_CHOICES, null=True, blank=True)
    paymentId = models.CharField(max_length=11, unique=True, null=True, blank=True)  # Our Own ID
    invoice = models.ForeignKey(Invoice, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    paymentMethod = models.CharField(max_length=50, null=True, blank=True, choices=PAYMENT_METHOD_CHOICES)
    squarePaymentId = models.CharField(max_length=100, null=True, blank=True)  # Square's payment ID
    transactionId = models.CharField(max_length=100, null=True, blank=True)  # For bank transfers
    fromAccountNumber = models.CharField(max_length=100, null=True, blank=True)
    fromBankName = models.CharField(max_length=100, null=True, blank=True)
    screenshot = models.ImageField(upload_to='screenshot/', null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS_CHOICES, default='PENDING')
    
    paidAt = models.DateTimeField(null=True, blank=True)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.paymentId}"
    
    class Meta:
        ordering = ['-createdAt']  # newest first
    
    def generatePaymentId(self):
        prefix = "pay"
        id = random.choices(string.digits, k=5)
        return prefix + ''.join(id)
    
    
    def compress_image(self, image_field):
        if image_field:
            img = Image.open(image_field)
            # Convert to RGB if the image has an alpha channel
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            
            # Create a BytesIO object to save the compressed image
            img_io = BytesIO()
            # Save with quality=60% and optimize for size
            img.save(img_io, format='JPEG', quality=60, optimize=True)
            
            # Create a new ContentFile with the compressed image
            compressed_image = ContentFile(img_io.getvalue(), name=image_field.name)
            return compressed_image
        return None

    def save(self, *args, **kwargs):
        # Compress the screenshot before saving if it exists
        if self.screenshot:
            # Check if the screenshot is being updated or is new
            if self.pk:
                old_instance = Payment.objects.get(pk=self.pk)
                if old_instance.screenshot and old_instance.screenshot != self.screenshot:
                    # Delete the old screenshot
                    old_instance.screenshot.delete(save=False)
            
            # Compress the new screenshot
            compressed_image = self.compress_image(self.screenshot)
            if compressed_image:
                self.screenshot = compressed_image
        
        if self.status in ['COMPLETED', 'APPROVED'] and not self.paidAt:
            if self.status == 'APPROVED':
                self.status = "COMPLETED"
            self.paidAt = timezone.now()
            
        if not self.paymentId:
            self.paymentId = self.generatePaymentId()
        
        self.amount = Decimal(self.amount)
            
        super().save(*args, **kwargs)
        
        # Update the invoice payment status after saving
        if self.status in ['COMPLETED', 'APPROVED']:
            self.invoice.update_payment_status()
        
        # Clean up the temporary file if it exists
        if hasattr(self, '_temp_screenshot'):
            del self._temp_screenshot


class BankAccount(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, related_name='bank_accounts')
    account_name = models.CharField(max_length=100)
    account_number = models.CharField(max_length=20)
    bank_name = models.CharField(max_length=100)
    ifsc_code = models.CharField(max_length=20)
    branch = models.CharField(max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.account_name} - {self.bank_name}"
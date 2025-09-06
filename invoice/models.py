from django.db import models
import random
import string
import os
from io import BytesIO
from PIL import Image
from django.core.files.base import ContentFile
from django.utils import timezone
# Create your models here.


class Invoice(models.Model):
    invoiceId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    booking = models.OneToOneField('bookings.Booking', on_delete=models.SET_NULL, null=True, blank=True)
    amount = models.IntegerField(default=0)
    isPaid = models.BooleanField(default=False)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.invoiceId}"

    def generateInvoiceId(self):
        prefix = "inv"
        id = random.choices(string.digits, k=5)
        return prefix + ''.join(id)
    
    def save(self, *args, **kwargs):
        if not self.invoiceId:
            self.invoiceId = self.generateInvoiceId()
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
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='payment_details')
    amount = models.IntegerField(default=0)
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
            self.paidAt = timezone.now()
            
        if not self.paymentId:
            self.paymentId = self.generatePaymentId()
            
        super().save(*args, **kwargs)
        
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
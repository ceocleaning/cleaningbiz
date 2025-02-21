from django.db import models
from django.contrib.auth import get_user_model
import random
import string

from httpx._transports import default
from accounts.models import Business


User = get_user_model()


serviceTypes = [
    ('standard', 'Standard Cleaning'),
    ('deep', 'Deep Cleaning'),
    ('moveinmoveout', 'Move In/Move Out'),
    ('airbnb', 'Airbnb Cleaning'),
]

paymentMethods = [
    ('creditcard', 'Credit Card'),
    ('paypal', 'PayPal'),
    ('stripe', 'Stripe'),
    ('other', 'Other'),
]

recurringOptions = [
    ('one-time', 'One Time'),
    ('weekly', 'Weekly'),
    ('biweekly', 'Bi-weekly'),
    ('monthly', 'Monthly'),
]


class BookingCustomAddons(models.Model):
    addon = models.ForeignKey('accounts.CustomAddons', on_delete=models.CASCADE)
    qty = models.IntegerField(default=0)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.addon.addonName} - {self.qty}"


class Booking(models.Model):
    # Basic Information
    bookingId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    business = models.ForeignKey(Business, on_delete=models.SET_NULL, null=True, blank=True)
    
    # Personal Information
    firstName = models.CharField(max_length=255, blank=True, null=True)
    lastName = models.CharField(max_length=255, blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    phoneNumber = models.CharField(max_length=20, blank=True, null=True)
    companyName = models.CharField(max_length=255, blank=True, null=True)
    
    # Address Information
    address1 = models.CharField(max_length=255, blank=True, null=True)
    address2 = models.CharField(max_length=255, blank=True, null=True)
    city = models.CharField(max_length=100, blank=True, null=True)
    stateOrProvince = models.CharField(max_length=100, blank=True, null=True)
    zipCode = models.CharField(max_length=10, blank=True, null=True)
    
    # Property Details
    bedrooms = models.IntegerField(default=0)
    bathrooms = models.IntegerField(default=0)
    squareFeet = models.IntegerField(default=0)
    
    # Service Information
    cleaningDateTime = models.DateTimeField(null=True, blank=True)
    serviceType = models.CharField(max_length=50, choices=serviceTypes, null=True, blank=True)
    recurring = models.CharField(max_length=20, choices=recurringOptions, default='one-time')
    
    # Add-ons (Optional Services)
    addonDishes = models.IntegerField(null=True, blank=True)
    addonLaundryLoads = models.IntegerField(null=True, blank=True)
    addonWindowCleaning = models.IntegerField(null=True, blank=True)
    addonPetsCleaning = models.IntegerField(null=True, blank=True)
    addonFridgeCleaning = models.IntegerField(null=True, blank=True)
    addonOvenCleaning = models.IntegerField(null=True, blank=True)
    addonBaseboard = models.IntegerField(null=True, blank=True)
    addonBlinds = models.IntegerField(null=True, blank=True)
    addonGreenCleaning = models.IntegerField(null=True, blank=True)
    addonCabinetsCleaning = models.IntegerField(null=True, blank=True)
    addonPatioSweeping = models.IntegerField(null=True, blank=True)
    addonGarageSweeping = models.IntegerField(null=True, blank=True)
    
    customAddons = models.ManyToManyField(BookingCustomAddons, blank=True, related_name='bookings')
    
    # Additional Information
    otherRequests = models.TextField(blank=True, null=True)
    paymentMethod = models.CharField(max_length=20, choices=paymentMethods, null=True, blank=True)
    totalPrice = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Status Fields
    isCompleted = models.BooleanField(default=False)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.firstName} {self.lastName} - {self.email}"
    
    def generateBookingId(self):
        prefix = "BK"
        id = random.choices(string.ascii_letters + string.digits, k=5)
        return prefix + ''.join(id)
    
    def save(self, *args, **kwargs):
        if not self.bookingId:
            self.bookingId = self.generateBookingId()
        super().save(*args, **kwargs)



class Invoice(models.Model):
    invoiceId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    booking = models.OneToOneField(Booking, on_delete=models.SET_NULL, null=True, blank=True)
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
    paymentId = models.CharField(max_length=11, unique=True, null=True, blank=True)
    invoice = models.OneToOneField(Invoice, on_delete=models.CASCADE, related_name='payment_details')
    amount = models.IntegerField(default=0)
    paymentMethod = models.CharField(max_length=50, null=True, blank=True)
    stripeChargeId = models.CharField(max_length=11, null=True, blank=True)
    
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



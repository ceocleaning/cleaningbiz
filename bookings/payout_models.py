from django.db import models
from django.utils import timezone
from accounts.models import Business, CleanerProfile

PAYOUT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('paid', 'Paid'),
    ('cancelled', 'Cancelled'),
]

class CleanerPayout(models.Model):
    """
    Model to track payouts to cleaners for completed bookings
    """
    payout_id = models.CharField(max_length=20, unique=True)
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='payouts')
    cleaner_profile = models.ForeignKey(CleanerProfile, on_delete=models.SET_NULL, null=True, blank=True, related_name='payouts')
    
    # Payout details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=PAYOUT_STATUS_CHOICES, default='pending')
    payment_method = models.CharField(max_length=50, null=True, blank=True)
    payment_reference = models.CharField(max_length=255, null=True, blank=True)
    
    # Dates
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paid_at = models.DateTimeField(null=True, blank=True)
    
    # Related bookings (a payout can include multiple bookings)
    bookings = models.ManyToManyField('bookings.Booking', related_name='payouts')
    
    # Notes
    notes = models.TextField(blank=True, null=True)
    
    def __str__(self):
        return f"Payout {self.payout_id} - {self.cleaner_profile.cleaner.name} - ${self.amount}"
    
    def mark_as_paid(self, payment_method=None, payment_reference=None):
        """Mark the payout as paid with the current timestamp"""
        self.status = 'paid'
        self.paid_at = timezone.now()
        if payment_method:
            self.payment_method = payment_method
        if payment_reference:
            self.payment_reference = payment_reference
        self.save()
    
    def calculate_total_amount(self):
        """Calculate the total payout amount from all associated bookings"""
        total = 0
        for booking in self.bookings.all():
            total += booking.get_cleaner_payout()
        return total
    
    def save(self, *args, **kwargs):
        # Generate a unique payout ID if not already set
        if not self.payout_id:
            import random
            import string
            prefix = "py-"
            random_digits = ''.join(random.choices(string.digits, k=8))
            self.payout_id = f"{prefix}{random_digits}"
        
        super().save(*args, **kwargs)

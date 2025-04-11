from django.db import models
from django.contrib.auth import get_user_model
import random
import string
from django.core.validators import MinValueValidator, MaxValueValidator

User = get_user_model()


WEEKDAY_CHOICES = (
    ('Monday', 'Monday'),
    ('Tuesday', 'Tuesday'),
    ('Wednesday', 'Wednesday'),
    ('Thursday', 'Thursday'),
    ('Friday', 'Friday'),
    ('Saturday', 'Saturday'),
    ('Sunday', 'Sunday'),
)


class Lead(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, null=True, blank=True)
    leadId = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=20)
    
    # Address fields
    address1 = models.CharField(max_length=255, null=True, blank=True)
    address2 = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state = models.CharField(max_length=50, null=True, blank=True)
    zipCode = models.CharField(max_length=20, null=True, blank=True)
    
    proposed_start_datetime = models.DateTimeField(null=True, blank=True)
    proposed_end_datetime = models.DateTimeField(null=True, blank=True)
    
    
    details = models.JSONField(null=True, blank=True, default=dict)
    

    
    # Pricing
    estimatedPrice = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    
    # Original fields
    notes = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)
    source = models.CharField(max_length=255)


    is_response_received = models.BooleanField(default=False)
    is_call_sent = models.BooleanField(default=False)
    call_sent_at = models.DateTimeField(null=True, blank=True)

    follow_up_call_sent = models.BooleanField(default=False)
    follow_up_call_sent_at = models.DateTimeField(null=True, blank=True)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.email if self.email else self.phone_number}"
    

    def save(self, *args, **kwargs):
        if not self.leadId:
            self.leadId = self.generateLeadId()
        if self.phone_number:
            self.phone_number = self.clean_phone_number(self.phone_number)
        super().save(*args, **kwargs)
    
    def generateLeadId(self):
        prefix = "ld-"
        id = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        return f"{prefix}{id}"
    
    def clean_phone_number(self, phone):
        """
        Clean and standardize phone number format by:
        1. Removing spaces, dashes, parentheses, and other non-numeric characters
        2. Ensuring proper country code format
        3. Handling various input formats
        
        Returns a standardized phone number string
        """
        if not phone:
            return phone
            
        # Remove all non-numeric characters
        cleaned = ''.join(char for char in phone if char.isdigit())
        
        # Handle US/Canada numbers
        if len(cleaned) == 10:
            # Add +1 country code if it's a 10-digit US/Canada number
            return f"+1{cleaned}"
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            # Format with + if it's an 11-digit number starting with 1
            return f"+{cleaned}"
        elif cleaned.startswith('00'):
            # Convert 00 international prefix to +
            return f"+{cleaned[2:]}"
        elif not cleaned.startswith('+'):
            # Add + if it doesn't have one and isn't handled by cases above
            return f"+{cleaned}"
        
        # Return the cleaned number
        return cleaned





class Cleaners(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phoneNumber = models.CharField(max_length=20)

    rating = models.IntegerField(default=1, validators=[MinValueValidator(1), MaxValueValidator(5)])

    bookings = models.ManyToManyField('bookings.Booking', blank=True, related_name='cleaners')

    isAvailable = models.BooleanField(default=True)

    isActive = models.BooleanField(default=True)
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)


    def __str__(self):
        return self.name

class CleanerAvailability(models.Model):
    AVAILABILITY_TYPE_CHOICES = (
        ('weekly', 'Weekly Recurring'),
        ('specific', 'Specific Date'),
    )
    
    cleaner = models.ForeignKey('automation.Cleaners', on_delete=models.CASCADE)
    
    # Type of availability entry
    availability_type = models.CharField(max_length=10, choices=AVAILABILITY_TYPE_CHOICES, default='weekly')
    
    # For weekly recurring schedule
    dayOfWeek = models.CharField(max_length=10, choices=WEEKDAY_CHOICES, null=True, blank=True)
    
    # For specific date exceptions
    specific_date = models.DateField(null=True, blank=True)
    
    # Common fields for both types
    startTime = models.TimeField(null=True, blank=True)
    endTime = models.TimeField(null=True, blank=True)
    offDay = models.BooleanField(default=False)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(availability_type='weekly', dayOfWeek__isnull=False, specific_date__isnull=True) |
                    models.Q(availability_type='specific', dayOfWeek__isnull=True, specific_date__isnull=False)
                ),
                name='valid_availability_type_fields'
            )
        ]

    def __str__(self):
        if self.availability_type == 'weekly':
            return f"{self.cleaner.name} - {self.dayOfWeek}"
        else:
            return f"{self.cleaner.name} - {self.specific_date.strftime('%Y-%m-%d')}"
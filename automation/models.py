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

serviceTypes = [
    ('standard', 'Standard Cleaning'),
    ('deep', 'Deep Cleaning'),
    ('moveinmoveout', 'Move In/Move Out'),
    ('airbnb', 'Airbnb Cleaning'),
    ('commercial', 'Commercial Cleaning'),
]


class Lead(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, null=True, blank=True)
    leadId = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=20, null=True, blank=True)

    bedrooms = models.IntegerField(null=True, blank=True)
    bathrooms = models.IntegerField(null=True, blank=True)
    squareFeet = models.IntegerField(null=True, blank=True)
    type_of_cleaning = models.CharField(max_length=255, null=True, blank=True, choices=serviceTypes)
    
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
    
    # SMS Tracking
    sms_sent = models.BooleanField(default=False)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    sms_status = models.CharField(max_length=50, null=True, blank=True, choices=[
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('failed', 'Failed'),
        ('not_attempted', 'Not Attempted')
    ])
    sms_error_message = models.TextField(null=True, blank=True)
    sms_message_sid = models.CharField(max_length=255, null=True, blank=True)  # Twilio Message SID
    
    # Call Tracking
    is_call_sent = models.BooleanField(default=False)
    call_sent_at = models.DateTimeField(null=True, blank=True)
    call_status = models.CharField(max_length=50, null=True, blank=True, choices=[
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('not_attempted', 'Not Attempted')
    ])
    call_error_message = models.TextField(null=True, blank=True)
    call_id = models.CharField(max_length=255, null=True, blank=True)  # Retell Call ID
    
    # Follow-up Call Tracking
    follow_up_call_sent = models.BooleanField(default=False)
    follow_up_call_sent_at = models.DateTimeField(null=True, blank=True)
    follow_up_call_status = models.CharField(max_length=50, null=True, blank=True, choices=[
        ('pending', 'Pending'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('not_attempted', 'Not Attempted')
    ])
    follow_up_call_error_message = models.TextField(null=True, blank=True)
    
    # Notification Method Used
    notification_method = models.CharField(max_length=20, null=True, blank=True, choices=[
        ('sms', 'SMS'),
        ('call', 'Call'),
        ('both', 'Both'),
        ('none', 'None')
    ])

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
        prefix = "ld"
        id = ''.join(random.choices(string.digits, k=5))
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
        

OPEN_JOB_CLEANER_STATUS = (
    ('pending', 'Pending'),
    ('accepted', 'Accepted'),
    ('rejected', 'Rejected'),
    ('closed', 'Closed'),
)

OPEN_JOB_ASSIGNMENT_TYPE = (
    ('top_rated', 'Top Rated'),
    ('all_available', 'All Available'),
)

class OpenJob(models.Model):
    id = models.CharField(max_length=255, primary_key=True)

    booking = models.ForeignKey('bookings.Booking', on_delete=models.CASCADE)
    cleaner = models.ForeignKey('accounts.CleanerProfile', on_delete=models.CASCADE)
    status = models.CharField(max_length=255, choices=OPEN_JOB_CLEANER_STATUS, default='pending')
    assignment_type = models.CharField(max_length=255, choices=OPEN_JOB_ASSIGNMENT_TYPE, default='all_available')

    
    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.booking.id} - {self.cleaner.cleaner.name}"
    
    def save(self, *args, **kwargs):
        if not self.id:
            self.id = self.generateOpenJobId()
        super().save(*args, **kwargs)
    
    def generateOpenJobId(self):
        prefix = "job_"
        id = ''.join(random.choices(string.digits, k=5))
        return f"{prefix}{id}"
    

class BookingNotificationTracker(models.Model):
    """Track which bookings have been processed for notifications"""
    booking = models.ForeignKey('bookings.Booking', on_delete=models.CASCADE)
    notification_type = models.CharField(max_length=50, default='cleaner_assignment_check')
    processed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('booking', 'notification_type')
        
    def __str__(self):
        return f"{self.booking.bookingId} - {self.notification_type} - {self.processed_at.strftime('%Y-%m-%d %H:%M')}"


class NotificationLog(models.Model):
    """Comprehensive log of all notification attempts (SMS and Calls) for leads"""
    
    NOTIFICATION_TYPE_CHOICES = [
        ('sms', 'SMS'),
        ('call', 'Call'),
        ('follow_up_call', 'Follow-up Call'),
    ]
    
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('sent', 'Sent'),
        ('initiated', 'Initiated'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('not_attempted', 'Not Attempted'),
    ]
    
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name='notification_logs')
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)
    
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    
    # Attempt tracking
    attempt_number = models.IntegerField(default=1)
    attempted_at = models.DateTimeField(auto_now_add=True)
    
    # Success/Failure details
    success = models.BooleanField(default=False)
    error_message = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=100, null=True, blank=True)
    
    # Provider-specific IDs
    message_sid = models.CharField(max_length=255, null=True, blank=True)  # Twilio SMS SID
    call_id = models.CharField(max_length=255, null=True, blank=True)  # Retell Call ID
    
    # Message content
    message_content = models.TextField(null=True, blank=True)
    
    # Additional metadata
    metadata = models.JSONField(null=True, blank=True, default=dict)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['lead', 'notification_type']),
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['status']),
        ]
    
    def __str__(self):
        return f"{self.lead.name} - {self.notification_type} - {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
    


LEADS_WEBHOOK_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('success', 'Success'),
    ('failed', 'Failed'),
]

LEADS_WEBHOOK_SOURCE_CHOICES = [
    ('thumbtack', 'Thumbtack'),
    ('manual_webhook', 'Manual Webhook'),
]

class LeadsWebhookLog(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)
    lead_source = models.CharField(max_length=20, choices=LEADS_WEBHOOK_SOURCE_CHOICES, default='manual_webhook')
    status = models.CharField(max_length=20, choices=LEADS_WEBHOOK_STATUS_CHOICES, default='pending')
    error_message = models.TextField(null=True, blank=True)
    error_code = models.CharField(max_length=100, null=True, blank=True)
    webhook_data = models.JSONField(null=True, blank=True, default=dict)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['business', 'created_at']),
            models.Index(fields=['status']),
        ]
    def __str__(self):
        return f"{self.business.name} - {self.status} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"
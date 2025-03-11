from django.db import models
from django.contrib.auth import get_user_model
import random
import string


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
    email = models.EmailField()
    phone_number = models.CharField(max_length=20)
    
    notes = models.TextField(blank=True, null=True)
    content = models.TextField(blank=True, null=True)

    source = models.CharField(max_length=255)

    is_response_received = models.BooleanField(default=False)
    is_call_sent = models.BooleanField(default=False)
    call_sent_at = models.DateTimeField(null=True, blank=True)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.email}"
    

    def save(self, *args, **kwargs):
        if not self.leadId:
            self.leadId = self.generateLeadId()
        super().save(*args, **kwargs)
    
    def generateLeadId(self):
        prefix = "ld-"
        id = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        return f"{prefix}{id}"





class Cleaners(models.Model):
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE, null=True, blank=True)
    name = models.CharField(max_length=255)
    email = models.EmailField(null=True, blank=True)
    phoneNumber = models.CharField(max_length=20)

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
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

    emailSentAt = models.DateTimeField(null=True, blank=True)
    isConverted = models.BooleanField(default=False)
    
    
    source = models.CharField(max_length=255)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} - {self.email}"
    

    def save(self, *args, **kwargs):
        if not self.leadId:
            self.leadId = self.generateLeadId()
        super().save(*args, **kwargs)
    
    def generateLeadId(self):
        return f"LD{random.choices(string.ascii_letters + string.digits, k=5)}"





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
    cleaner = models.ForeignKey('automation.Cleaners', on_delete=models.CASCADE)
    
    dayOfWeek = models.CharField(max_length=10, choices=WEEKDAY_CHOICES)
    startTime = models.TimeField(null=True, blank=True)
    endTime = models.TimeField(null=True, blank=True)

    offDay = models.BooleanField(default=False)

    createdAt = models.DateTimeField(auto_now_add=True)
    updatedAt = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.cleaner.name} - {self.dayOfWeek}"
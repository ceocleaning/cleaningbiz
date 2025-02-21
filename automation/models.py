from django.db import models
from django.contrib.auth import get_user_model
import random
import string


User = get_user_model()



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
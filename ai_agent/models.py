from django.db import models
from django.utils import timezone


CHAT_ROLE_CHOICES = (
    ('user', 'User'),
    ('assistant', 'Assistant')
)



class Messages(models.Model):
    chat = models.ForeignKey('Chat', on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    role = models.CharField(max_length=20, choices=CHAT_ROLE_CHOICES)
    message = models.TextField()
    is_first_message = models.BooleanField(default=False)
    createdAt = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return f"{self.role}: {self.message}"

class Chat(models.Model):
    chatId = models.CharField(max_length=20, unique=True)
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)

    summary = models.JSONField(null=True, blank=True, default=dict)

    createdAt = models.DateTimeField(default=timezone.now)
    updatedAt = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.chatId

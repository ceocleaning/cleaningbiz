from django.db import models
from django.contrib.auth.models import User
from business.models import Business
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
import json

class AgentConfig(models.Model):
    """
    Model for storing agent configuration including name and prompts.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='agent_configs')
    name = models.CharField(max_length=100, default="Business Assistant")
    
    prompt = models.TextField(blank=True, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.business.name} - {self.name}"

 

class Chat(models.Model):
    """
    Model for storing chat sessions between client and agent.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='chats')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    session_key = models.CharField(max_length=100, blank=True, null=True)
  
    summary = models.JSONField(default=dict, blank=True, null=True)

    response_received = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
   

    class Meta:
        unique_together = [['business', 'phone_number'], ['business', 'session_key']]
        indexes = [
            models.Index(fields=['phone_number']),
            models.Index(fields=['session_key']),
            models.Index(fields=['created_at']),
        ]

    def __str__(self):
        identifier = self.phone_number or self.session_key or self.id
        return f"{self.business.name} - {identifier}"

  
class Message(models.Model):
    """
    Model for storing individual messages in a chat.
    """
    ROLE_CHOICES = (
        ('user', 'User'),
        ('assistant', 'Assistant'),
        ('system', 'System'),
    )

    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='messages')
    role = models.CharField(max_length=10, choices=ROLE_CHOICES)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    tool_calls = models.JSONField(default=list, blank=True, null=True)
    tool_call_id = models.CharField(max_length=100, blank=True, null=True)
    parent_message_id = models.CharField(max_length=100, blank=True, null=True)

    class Meta:
        ordering = ['created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['role']),
        ]

    def __str__(self):
        return f"{self.chat.id} - {self.role} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


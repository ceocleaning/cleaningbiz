from django.db import models
from django.utils import timezone


CHAT_ROLE_CHOICES = (
    ('user', 'User'),
    ('assistant', 'Assistant'),
    ('tool', 'Tool')
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
    lead = models.ForeignKey('automation.Lead', on_delete=models.CASCADE, null=True, blank=True)
    clientPhoneNumber = models.CharField(max_length=15, null=True, blank=True, unique=True)
    business = models.ForeignKey('accounts.Business', on_delete=models.CASCADE)

    summary = models.JSONField(null=True, blank=True, default=dict)

    createdAt = models.DateTimeField(default=timezone.now)
    updatedAt = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.clientPhoneNumber} - {self.business.businessName}"


class AgentConfiguration(models.Model):
    """Store dynamic configuration for AI Voice Agent"""
    business = models.OneToOneField('accounts.Business', on_delete=models.CASCADE, related_name='agent_config')
    prompt = models.TextField(blank=True, null=True, help_text="Script for the AI agent")
   
    class Meta:
        verbose_name = "AI Agent Configuration"
        verbose_name_plural = "AI Agent Configurations"
    
    def __str__(self):
        return f"Agent Config for {self.business.businessName}"
    
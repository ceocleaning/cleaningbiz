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


class AgentConfiguration(models.Model):
    """Store dynamic configuration for AI Voice Agent"""
    business = models.OneToOneField('accounts.Business', on_delete=models.CASCADE, related_name='agent_config')
    
    # Agent identity
    agent_name = models.CharField(max_length=50, default="Sarah")
    agent_role = models.CharField(max_length=100, default="virtual customer support and sales representative")
    
    # Business description
    business_description = models.TextField(blank=True, null=True, 
        help_text="Description of the business that will be used in the AI prompt")
    business_mission = models.TextField(blank=True, null=True,
        help_text="Mission statement points, will be formatted as bullet points")
    
    # Services
    services = models.TextField(blank=True, null=True,
        help_text="Services provided by the business, will be formatted as bullet points")
    
    # Custom prompt additions
    custom_instructions = models.TextField(blank=True, null=True,
        help_text="Any additional custom instructions for the AI agent")

    script = models.TextField(blank=True, null=True,
        help_text="Script for the AI agent")
   
    class Meta:
        verbose_name = "AI Agent Configuration"
        verbose_name_plural = "AI Agent Configurations"
    
    def __str__(self):
        return f"Agent Config for {self.business.businessName}"
    
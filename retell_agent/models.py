from django.db import models
from django.conf import settings
from accounts.models import Business

class RetellAgent(models.Model):
    """
    Model to store Retell agent information.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='retell_agents')
    agent_id = models.CharField(max_length=255, unique=True)
    agent_name = models.CharField(max_length=255)
    llm = models.ForeignKey('RetellLLM', on_delete=models.SET_NULL, related_name='agents', null=True)
    voice_id = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.agent_name} ({self.agent_id})"
    
class RetellLLM(models.Model):
    """
    Model to store Retell LLM information.
    """
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='retell_llms')
    llm_id = models.CharField(max_length=255, unique=True)
    model = models.CharField(max_length=255)  # e.g., gpt-4o
    
    general_prompt = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.model} ({self.llm_id})"

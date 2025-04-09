from .models import ApiCredential
from django.db.models.signals import post_save
from django.dispatch import receiver
from retell_agent.api import RetellAgentAPI
from retell_agent.models import RetellAgent

@receiver(post_save, sender=ApiCredential)
def update_api_credential(sender, instance, **kwargs):
    if instance.id:
        payload = {
            'webhook_url' : instance.getRetellUrl()
        }

        retell_agent = RetellAgent.objects.filter(business=instance.business).first()
        if retell_agent:
            RetellAgentAPI.update_agent(retell_agent.agent_id, payload)
        

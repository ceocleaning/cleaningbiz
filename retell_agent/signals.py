from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import RetellAgent
from retell import Retell
from accounts.models import ApiCredential
from django.conf import settings



client = Retell(api_key=settings.RETELL_API_KEY)

@receiver(post_save, sender=RetellAgent)
def create_retell_agent(sender, instance, created, **kwargs):
    if created:
        # Create Phone Number
        try:
            api_credential = ApiCredential.objects.filter(business=instance.business).first()
            phone_number_response = client.phone_number.create(
                inbound_agent_id=instance.agent_id,
                outbound_agent_id=instance.agent_id,
                nickname=instance.agent_name
            )
            instance.agent_number = phone_number_response.phone_number
            instance.save()
            print(f"Phone number created for agent {instance.agent_name}: {phone_number_response.phone_number}")

        except Exception as e:
            print(f"Error creating phone number for agent {instance.agent_name}: {str(e)}")
            
            # raise 500 exception
            raise Exception(f"Error creating phone number for agent {instance.agent_name}: {str(e)}")
        

    
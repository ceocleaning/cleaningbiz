from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import EmailMessage
from .models import Lead
from django.conf import settings
from retell import Retell
import os
import requests
from django.core.mail import send_mail
from accounts.models import ApiCredential






@receiver(post_save, sender=Lead)
def set_status_and_send_email(sender, instance, created, **kwargs):
    apicreds = ApiCredential.objects.get(business=instance.business)
    client = Retell(api_key=apicreds.retellAPIKey)
    print("Signal received!")
    if created:
        try:
            apiCreds = ApiCredential.objects.get(business=instance.business)
            call_response = client.call.create_phone_call(
                from_number=apiCreds.voiceAgentNumber,
                to_number=instance.phone_number,
                retell_llm_dynamic_variables={
                    'name': instance.name,
                    'service': instance.content
                },
            )
            print(call_response)

        except Exception as e:
            print(f"Error making call: {e}")
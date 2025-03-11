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
from ai_agent.models import AgentConfiguration, Messages, Chat
from .tasks import send_call_to_lead
from django_q.tasks import schedule

import datetime
from twilio.rest import Client





@receiver(post_save, sender=Lead)
def set_status_and_send_email(sender, instance, created, **kwargs):
    if created:
        apiCred = ApiCredential.objects.get(business=instance.business)
        agentConfig = AgentConfiguration.objects.get(business=instance.business)
        client = Client(apiCred.twilioAccountSid, apiCred.twilioAuthToken)
        message_body = f"Hello {instance.name}, this is {agentConfig.agent_name} from {instance.business.businessName}. I was checking in to see if you'd like to schedule a cleaning service."
        message = client.messages.create(
            body=message_body,
            from_=apiCred.twilioSmsNumber,
            to=instance.phone_number
        )

        chat = Chat.objects.create(
            clientPhoneNumber=instance.phone_number,
            business=instance.business
        )

        Messages.objects.create(
            lead=instance,
            chat=chat,
            role='assistant',
            message=message_body
        )

        print(f"Message sent successfully! SID: {message.sid}")


        schedule(
            'automation.tasks.send_call_to_lead',  
            instance.id,  
            schedule_type='O',
            next_run=timezone.now() + datetime.timedelta(minutes=5),
            )
        print("Call scheduled for lead")


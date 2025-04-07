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
from subscription.models import BusinessSubscription, SubscriptionPlan, UsageTracker
from .tasks import send_call_to_lead
from django_q.tasks import schedule
from django_q.models import Schedule
import datetime
from twilio.rest import Client
from twilio.base.exceptions import TwilioRestException





@receiver(post_save, sender=Lead)
def set_status_and_send_email(sender, instance, created, **kwargs):
    from django_q.tasks import schedule
    from django_q.models import Schedule
    
    # Check if the schedule already exists
    if not Schedule.objects.filter(func="ai_agent.tasks.check_chat_status").exists():
        # Schedule the function to run every 2 minutes
        schedule(
            "ai_agent.tasks.check_chat_status",
            schedule_type=Schedule.MINUTES,
            minutes=30,
            repeats=-1,  # Run indefinitely
        )
        
    if created:
        try:
            # Check if both ApiCredential and AgentConfiguration exist for the business
            try:
                apiCred = ApiCredential.objects.get(business=instance.business)
                agentConfig = AgentConfiguration.objects.get(business=instance.business)
            except (ApiCredential.DoesNotExist, AgentConfiguration.DoesNotExist):
                # If either doesn't exist, just skip sending the SMS
                print(f"Skipping SMS for lead {instance.leadId}: Missing API credentials or agent configuration")
                return
                
            # Only proceed if we have both configurations
            print(f"Twilio Account SID: {apiCred.twilioAccountSid}")
            print(f"Twilio Auth Token: {apiCred.twilioAuthToken}")
            print(f"Twilio SMS Number: {apiCred.twilioSmsNumber}")

            # Check if Twilio credentials are properly set
            if not apiCred.twilioAccountSid or not apiCred.twilioAuthToken or not apiCred.twilioSmsNumber:
                print(f"Skipping SMS for lead {instance.leadId}: Incomplete Twilio credentials")
                return
                
            # Check if phone number is valid
            if not instance.phone_number or len(instance.phone_number) < 10:
                print(f"Skipping SMS for lead {instance.leadId}: Invalid phone number")
                return

            client = Client(apiCred.twilioAccountSid, apiCred.twilioAuthToken)

            message_body = f"Hello {instance.name}, this is {agentConfig.agent_name} from {instance.business.businessName}. I was checking in to see if you'd like to schedule a cleaning service."
            message = client.messages.create(
                body=message_body,
                from_=apiCred.twilioSmsNumber,
                to=instance.phone_number
            )

            chat = Chat.objects.filter(clientPhoneNumber=instance.phone_number).first()
            if chat:
                chat.delete()
                
            chat = Chat.objects.create(
                lead=instance,
                clientPhoneNumber=instance.phone_number,
                business=instance.business,
                status="pending"
            )
            Messages.objects.create(
                chat=chat,
                role='assistant',
                message=message_body,
                is_first_message=True
            )

            Messages.objects.create(
                chat=chat,
                role='assistant',
                message=f"Lead Name is {instance.name} and Lead Phone Number is {instance.phone_number} and Lead Email is {instance.email}",
                is_first_message=False
            )

            print(f"Message sent successfully! SID: {message.sid}")

            if instance.business.useCall and instance.business.timeToWait > 0:

                schedule(
                    'automation.tasks.send_call_to_lead',  
                    instance.id,  
                    schedule_type='O',
                    next_run=timezone.now() + datetime.timedelta(minutes=instance.business.timeToWait),
                )
                print(f"Call scheduled for lead {instance.id} in {instance.business.timeToWait} minutes")
                
        except TwilioRestException as e:
            print(f"Error sending message: {e}")

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
                return
            

            lead_details = f"Here are the details about the lead:\nName: {instance.name}\nPhone: {instance.phone_number}\nEmail: {instance.email if instance.email else 'Not provided'}\nAddress: {instance.address1 if instance.address1 else 'Not provided'}\nCity: {instance.city if instance.city else 'Not provided'}\nState: {instance.state if instance.state else 'Not provided'}\nZip Code: {instance.zipCode if instance.zipCode else 'Not provided'}\nProposed Start Time: {instance.proposed_start_datetime.strftime('%B %d, %Y at %I:%M %p') if instance.proposed_start_datetime else 'Not provided'}\nNotes: {instance.notes if instance.notes else 'No additional notes'}\nBedrooms: {instance.bedrooms if instance.bedrooms else 'Not provided'}\nBathrooms: {instance.bathrooms if instance.bathrooms else 'Not provided'}\nSquare Feet: {instance.squareFeet if instance.squareFeet else 'Not provided'}\nType of Cleaning: {instance.type_of_cleaning if instance.type_of_cleaning else 'Not provided'}"
                
   

            # Check if Twilio credentials are properly set
            if apiCred.twilioAccountSid and apiCred.twilioAuthToken and apiCred.twilioSmsNumber and instance.phone_number and len(instance.phone_number) == 10:
              
                client = Client(apiCred.twilioAccountSid, apiCred.twilioAuthToken)

                try:
                    message_body = f"Hello {instance.name}, this is {agentConfig.agent_name} from {instance.business.businessName}. I was checking in to see if you'd like to schedule a cleaning service with us?"
                    message = client.messages.create(
                        body=message_body,
                        from_=apiCred.twilioSmsNumber,
                        to=instance.phone_number
                    )

                except TwilioRestException as e:
                    print("Error sending SMS: ", e)
                    pass

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
                    message=lead_details,
                    is_first_message=False
                )

                if instance.business.useCall and instance.business.timeToWait > 0:

                    schedule(
                        'automation.tasks.send_call_to_lead',  
                        instance.id,  
                        schedule_type='O',
                        next_run=timezone.now() + datetime.timedelta(minutes=instance.business.timeToWait),
                    )
                    print(f"Call scheduled for lead {instance.id} in {instance.business.timeToWait} minutes")
            

            else:
                retellAgent = RetellAgent.objects.get(business=lead.business)
                if retellAgent.agent_number:
                    client = Retell(api_key=settings.RETELL_API_KEY)
                    call_response = client.call.create_phone_call(
                        from_number=retellAgent.agent_number,
                        to_number=instance.phone_number,
                        override_agent_id=retellAgent.agent_id,
                        retell_llm_dynamic_variables={
                            'name': instance.name,
                            'details': lead_details,
                            'service': 'cleaning'
                        }
                    )
                    instance.is_call_sent = True
                    insatnce.call_sent_at = timezone.now()
                    insatnce.save()


            
                
        except TwilioRestException as e:
            print(f"Error sending message: {e}")

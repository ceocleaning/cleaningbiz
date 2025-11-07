from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import EmailMessage
from .models import Lead, OpenJob, NotificationLog
from django.conf import settings
from retell import Retell
import os
import requests
import traceback
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

from retell_agent.models import RetellAgent

# Schedule the booking cleaner assignment check task to run hourly
def schedule_booking_cleaner_assignment_check():
    # Check if the schedule already exists
    if not Schedule.objects.filter(func="automation.tasks.check_booking_cleaner_assignment").exists():
        # Schedule the function to run every hour
        schedule(
            "automation.tasks.check_booking_cleaner_assignment",
            schedule_type=Schedule.HOURLY,
            repeats=-1,  # Run indefinitely
        )
        print("Scheduled check_booking_cleaner_assignment task to run hourly")

# Call the function to ensure the schedule is created




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
            if apiCred.twilioAccountSid and apiCred.twilioAuthToken and apiCred.twilioSmsNumber and instance.phone_number:
                # Attempt to send SMS
                sms_log = NotificationLog.objects.create(
                    lead=instance,
                    business=instance.business,
                    notification_type='sms',
                    status='pending',
                    attempt_number=1
                )
                
                try:
                    client = Client(apiCred.twilioAccountSid, apiCred.twilioAuthToken)
                    message_body = f"Hello {instance.name}, this is {agentConfig.agent_name} from {instance.business.businessName}. I was checking in to see if you'd like to schedule a cleaning service with us?"
                    
                    message = client.messages.create(
                        body=message_body,
                        from_=apiCred.twilioSmsNumber,
                        to=instance.phone_number
                    )
                    
                    # SMS sent successfully
                    instance.sms_sent = True
                    instance.sms_sent_at = timezone.now()
                    instance.sms_status = 'sent'
                    instance.sms_message_sid = message.sid
                    instance.notification_method = 'sms'
                    instance.save(update_fields=['sms_sent', 'sms_sent_at', 'sms_status', 'sms_message_sid', 'notification_method'])
                    
                    # Update log
                    sms_log.status = 'sent'
                    sms_log.success = True
                    sms_log.message_sid = message.sid
                    sms_log.message_content = message_body
                    sms_log.metadata = {
                        'to': instance.phone_number,
                        'from': apiCred.twilioSmsNumber,
                        'status': message.status
                    }
                    sms_log.save()
                    
                    print(f"✓ SMS sent successfully to {instance.name} ({instance.phone_number}). SID: {message.sid}")

                except TwilioRestException as e:
                    # SMS failed - log the error
                    error_message = f"Twilio Error: {str(e)}"
                    error_code = getattr(e, 'code', 'UNKNOWN')
                    
                    instance.sms_sent = False
                    instance.sms_status = 'failed'
                    instance.sms_error_message = error_message
                    instance.save(update_fields=['sms_sent', 'sms_status', 'sms_error_message'])
                    
                    # Update log
                    sms_log.status = 'failed'
                    sms_log.success = False
                    sms_log.error_message = error_message
                    sms_log.error_code = str(error_code)
                    sms_log.message_content = message_body
                    sms_log.metadata = {
                        'to': instance.phone_number,
                        'from': apiCred.twilioSmsNumber,
                        'error_details': str(e)
                    }
                    sms_log.save()
                    
                    print(f"✗ SMS failed for {instance.name} ({instance.phone_number}): {error_message}")
                    
                    # Don't return - continue to try call as fallback
                    
                except Exception as e:
                    # Unexpected error
                    error_message = f"Unexpected error: {str(e)}"
                    
                    instance.sms_sent = False
                    instance.sms_status = 'failed'
                    instance.sms_error_message = error_message
                    instance.save(update_fields=['sms_sent', 'sms_status', 'sms_error_message'])
                    
                    # Update log
                    sms_log.status = 'failed'
                    sms_log.success = False
                    sms_log.error_message = error_message
                    sms_log.message_content = message_body
                    sms_log.metadata = {'traceback': traceback.format_exc()}
                    sms_log.save()
                    
                    print(f"✗ Unexpected SMS error for {instance.name}: {error_message}")
                    # Don't return - continue to try call as fallback

                # Only create chat if SMS was sent successfully
                if instance.sms_sent and instance.sms_status == 'sent':
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

                    # Schedule follow-up call if configured
                    if instance.business.useCall and instance.business.timeToWait > 0:
                        schedule(
                            'automation.tasks.send_call_to_lead',  
                            instance.id,  
                            schedule_type='O',
                            next_run=timezone.now() + datetime.timedelta(minutes=instance.business.timeToWait),
                        )
                        print(f"✓ Follow-up call scheduled for lead {instance.id} in {instance.business.timeToWait} minutes")
                else:
                    # SMS failed, try making a call immediately as fallback
                    print(f"⚠ SMS failed, attempting call as fallback for lead {instance.name}")
                    try:
                        retellAgent = RetellAgent.objects.get(business=instance.business)
                        if retellAgent.agent_number:
                            call_log = NotificationLog.objects.create(
                                lead=instance,
                                business=instance.business,
                                notification_type='call',
                                status='pending',
                                attempt_number=1
                            )
                            
                            try:
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
                                
                                # Call initiated successfully
                                instance.is_call_sent = True
                                instance.call_sent_at = timezone.now()
                                instance.call_status = 'initiated'
                                instance.call_id = call_response.call_id if hasattr(call_response, 'call_id') else None
                                instance.notification_method = 'call'
                                instance.save(update_fields=['is_call_sent', 'call_sent_at', 'call_status', 'call_id', 'notification_method'])
                                
                                # Update log
                                call_log.status = 'initiated'
                                call_log.success = True
                                call_log.call_id = instance.call_id
                                call_log.metadata = {'call_response': str(call_response), 'reason': 'sms_fallback'}
                                call_log.save()
                                
                                print(f"✓ Fallback call initiated for {instance.name} ({instance.phone_number})")
                                
                            except Exception as call_error:
                                error_message = f"Call Error: {str(call_error)}"
                                instance.call_status = 'failed'
                                instance.call_error_message = error_message
                                instance.notification_method = 'none'
                                instance.save(update_fields=['call_status', 'call_error_message', 'notification_method'])
                                
                                call_log.status = 'failed'
                                call_log.success = False
                                call_log.error_message = error_message
                                call_log.metadata = {'traceback': traceback.format_exc(), 'reason': 'sms_fallback'}
                                call_log.save()
                                
                                print(f"✗ Fallback call failed for {instance.name}: {error_message}")
                    except RetellAgent.DoesNotExist:
                        instance.call_status = 'not_attempted'
                        instance.call_error_message = 'No Retell agent configured'
                        instance.notification_method = 'none'
                        instance.save(update_fields=['call_status', 'call_error_message', 'notification_method'])
                        print(f"✗ No Retell agent configured for fallback call to {instance.name}")
            

            else:
                # No Twilio credentials - try call directly
                instance.sms_status = 'not_attempted'
                instance.sms_error_message = 'Twilio credentials not configured'
                instance.save(update_fields=['sms_status', 'sms_error_message'])
                
                print(f"⚠ No Twilio credentials, attempting direct call for {instance.name}")
                
                try:
                    retellAgent = RetellAgent.objects.get(business=instance.business)
                    if retellAgent.agent_number:
                        call_log = NotificationLog.objects.create(
                            lead=instance,
                            business=instance.business,
                            notification_type='call',
                            status='pending',
                            attempt_number=1
                        )
                        
                        try:
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
                            
                            # Call initiated successfully
                            instance.is_call_sent = True
                            instance.call_sent_at = timezone.now()
                            instance.call_status = 'initiated'
                            instance.call_id = call_response.call_id if hasattr(call_response, 'call_id') else None
                            instance.notification_method = 'call'
                            instance.save(update_fields=['is_call_sent', 'call_sent_at', 'call_status', 'call_id', 'notification_method'])
                            
                            # Update log
                            call_log.status = 'initiated'
                            call_log.success = True
                            call_log.call_id = instance.call_id
                            call_log.metadata = {'call_response': str(call_response), 'reason': 'no_twilio'}
                            call_log.save()
                            
                            print(f"✓ Direct call initiated for {instance.name} ({instance.phone_number})")
                            
                        except Exception as call_error:
                            error_message = f"Call Error: {str(call_error)}"
                            instance.call_status = 'failed'
                            instance.call_error_message = error_message
                            instance.notification_method = 'none'
                            instance.save(update_fields=['call_status', 'call_error_message', 'notification_method'])
                            
                            call_log.status = 'failed'
                            call_log.success = False
                            call_log.error_message = error_message
                            call_log.metadata = {'traceback': traceback.format_exc(), 'reason': 'no_twilio'}
                            call_log.save()
                            
                            print(f"✗ Direct call failed for {instance.name}: {error_message}")
                    else:
                        instance.call_status = 'not_attempted'
                        instance.call_error_message = 'No agent phone number configured'
                        instance.notification_method = 'none'
                        instance.save(update_fields=['call_status', 'call_error_message', 'notification_method'])
                        print(f"✗ No agent phone number configured for {instance.name}")
                        
                except RetellAgent.DoesNotExist:
                    instance.call_status = 'not_attempted'
                    instance.call_error_message = 'No Retell agent configured'
                    instance.notification_method = 'none'
                    instance.save(update_fields=['call_status', 'call_error_message', 'notification_method'])
                    print(f"✗ No Retell agent configured for {instance.name}")


            
                
        except Exception as e:
            # Catch-all for any unexpected errors
            error_message = f"Unexpected error in lead notification: {str(e)}"
            print(f"✗ {error_message}")
            print(traceback.format_exc())
            
            # Try to update lead status
            try:
                instance.notification_method = 'none'
                instance.save(update_fields=['notification_method'])
            except:
                pass




@receiver(post_save, sender=OpenJob)
def schedule_open_job_task(sender, instance, created, **kwargs):
    schedule_booking_cleaner_assignment_check()
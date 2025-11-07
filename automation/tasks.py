from email import message
import traceback
from accounts.models import ApiCredential
from ai_agent.models import AgentConfiguration, Messages, Chat
from retell_agent.models import RetellAgent
from subscription.models import BusinessSubscription, SubscriptionPlan, UsageTracker
from retell import Retell
from .models import Lead, OpenJob, BookingNotificationTracker, NotificationLog
from bookings.models import Booking
from notification.services import NotificationService
from django.utils import timezone
from django.conf import settings
from datetime import timedelta
from bookings.utils import get_service_details


def send_call_to_lead(lead_id):
    """
    Send a follow-up call to a lead if they haven't responded to SMS.
    This is typically scheduled to run after a certain wait time.
    """
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        
        # Check if lead already responded
        if lead.is_response_received:
            print(f"⊘ Lead {lead.name} already responded, skipping follow-up call")
            lead.follow_up_call_status = 'not_attempted'
            lead.follow_up_call_error_message = 'Lead already responded'
            lead.save(update_fields=['follow_up_call_status', 'follow_up_call_error_message'])
            return 0
        
        # Get Retell agent
        try:
            retellAgent = RetellAgent.objects.get(business=lead.business)
        except RetellAgent.DoesNotExist:
            error_message = 'No Retell agent configured for this business'
            print(f"✗ {error_message} for lead {lead.name}")
            lead.follow_up_call_status = 'not_attempted'
            lead.follow_up_call_error_message = error_message
            lead.save(update_fields=['follow_up_call_status', 'follow_up_call_error_message'])
            return -1
        
        if not retellAgent.agent_number:
            error_message = 'No agent phone number configured'
            print(f"✗ {error_message} for lead {lead.name}")
            lead.follow_up_call_status = 'not_attempted'
            lead.follow_up_call_error_message = error_message
            lead.save(update_fields=['follow_up_call_status', 'follow_up_call_error_message'])
            return -1

        # Prepare lead details
        lead_details = f"Here are the details about the lead:\nName: {lead.name}\nPhone: {lead.phone_number}\nEmail: {lead.email if lead.email else 'Not provided'}\nAddress: {lead.address1 if lead.address1 else 'Not provided'}\nCity: {lead.city if lead.city else 'Not provided'}\nState: {lead.state if lead.state else 'Not provided'}\nZip Code: {lead.zipCode if lead.zipCode else 'Not provided'}\nProposed Start Time: {lead.proposed_start_datetime.strftime('%B %d, %Y at %I:%M %p') if lead.proposed_start_datetime else 'Not provided'}\nNotes: {lead.notes if lead.notes else 'No additional notes'}"

        # Create notification log
        call_log = NotificationLog.objects.create(
            lead=lead,
            business=lead.business,
            notification_type='follow_up_call',
            status='pending',
            attempt_number=1
        )
        
        try:
            # Initiate the call
            client = Retell(api_key=settings.RETELL_API_KEY)
            call_response = client.call.create_phone_call(
                from_number=retellAgent.agent_number,
                to_number=lead.phone_number,
                override_agent_id=retellAgent.agent_id,
                retell_llm_dynamic_variables={
                    'name': lead.name,
                    'details': lead_details,
                    'service': 'cleaning'
                }
            )
            
            # Extract call ID
            call_id = call_response.call_id if hasattr(call_response, 'call_id') else None
            
            # Update lead with success status
            lead.follow_up_call_sent = True
            lead.follow_up_call_sent_at = timezone.now()
            lead.follow_up_call_status = 'initiated'
            lead.save(update_fields=['follow_up_call_sent', 'follow_up_call_sent_at', 'follow_up_call_status'])
            
            # Update notification log
            call_log.status = 'initiated'
            call_log.success = True
            call_log.call_id = call_id
            call_log.metadata = {
                'call_response': str(call_response),
                'from_number': retellAgent.agent_number,
                'to_number': lead.phone_number,
                'agent_id': retellAgent.agent_id
            }
            call_log.save()
            
            print(f"✓ Follow-up call initiated successfully for {lead.name} ({lead.phone_number}). Call ID: {call_id}")
            return 0
            
        except Exception as call_error:
            # Call failed
            error_message = f"Call Error: {str(call_error)}"
            error_trace = traceback.format_exc()
            
            # Update lead with failure status
            lead.follow_up_call_status = 'failed'
            lead.follow_up_call_error_message = error_message
            lead.save(update_fields=['follow_up_call_status', 'follow_up_call_error_message'])
            
            # Update notification log
            call_log.status = 'failed'
            call_log.success = False
            call_log.error_message = error_message
            call_log.metadata = {
                'traceback': error_trace,
                'from_number': retellAgent.agent_number,
                'to_number': lead.phone_number,
                'agent_id': retellAgent.agent_id
            }
            call_log.save()
            
            print(f"✗ Follow-up call failed for {lead.name} ({lead.phone_number}): {error_message}")
            print(error_trace)
            return -1

    except Lead.DoesNotExist:
        print(f"✗ Lead with ID {lead_id} not found")
        return -1

    except Exception as e:
        error_message = f"Unexpected error in send_call_to_lead: {str(e)}"
        error_trace = traceback.format_exc()
        print(f"✗ {error_message}")
        print(error_trace)
        
        # Try to update lead if possible
        try:
            lead = Lead.objects.get(id=lead_id)
            lead.follow_up_call_status = 'failed'
            lead.follow_up_call_error_message = error_message
            lead.save(update_fields=['follow_up_call_status', 'follow_up_call_error_message'])
        except:
            pass
            
        return -1


def check_open_job(job_id):
    """
    Check the status of an open job and take appropriate actions if needed.
    This function is called by a scheduled task after a certain time period
    to follow up on open jobs that haven't been accepted or rejected.
    
    Args:
        job_id (str): The ID of the OpenJob to check
    """
    try:
        # Get the open job
        job = OpenJob.objects.get(id=job_id)
        
        # If the job is still pending after the wait time
        if job.status == 'pending':
            # You could implement additional logic here, such as:
            # 1. Send a reminder to the cleaner
            # 2. Automatically assign to another cleaner
            # 3. Notify the business owner
            print(f"Open job {job_id} is still pending after wait time")
            
        return 0
    except OpenJob.DoesNotExist:
        print(f"Open job {job_id} not found")
        return -1
    except Exception as e:
        print(f"Error checking open job {job_id}: {e}")
        return -1


def check_booking_cleaner_assignment():
    """
    Check bookings that are scheduled to start in 12 hours:
    1. If the booking has a cleaner assigned, do nothing
    2. If the booking is not paid, do nothing
    3. If the booking has open jobs with no cleaner accepting, send email to business owner
    
    This task is scheduled to run periodically (e.g., every hour)
    """
    try:
        # Calculate the time window (6 hours from now)
        target_time = timezone.now() + timedelta(hours=12)
        
        # Find bookings that start approximately 6 hours from now (within a 30-minute window)
        start_window = target_time - timedelta(minutes=15)
        end_window = target_time + timedelta(minutes=15)
        
        # Get bookings in the time window that haven't been cancelled
        upcoming_bookings = Booking.objects.filter(
            cleaningDate=target_time.date(),
            startTime__gte=start_window.time(),
            startTime__lte=end_window.time(),
            cleaner__isnull=True,
            cancelled_at__isnull=True
        )
        
        for booking in upcoming_bookings:
            if BookingNotificationTracker.objects.filter(
                booking=booking, 
                notification_type='cleaner_assignment_check'
            ).exists():
                continue
                
            if booking.cleaner is not None:
                continue
                
            if not booking.is_paid():
                continue
                
            open_jobs = OpenJob.objects.filter(booking=booking)
            
            if not open_jobs.exists():
                continue
                
            accepted_jobs = open_jobs.filter(status='accepted')
            if accepted_jobs.exists():
                continue

            business = booking.business
            
            subject = f"ACTION REQUIRED: No cleaner assigned for booking {booking.bookingId}"
            details = get_service_details(booking, 'owner')
            
            text_body = f"""Hello {business.businessName},
This is an important notification regarding booking {booking.bookingId}.

{details}

This booking has been paid or authorized, but no cleaner has accepted the job yet.
Please take immediate action to assign a cleaner or contact the customer.
You can view the full booking details in your dashboard.

Thank you,CleaningBiz AI
"""
            
            from_email = f"CleaningBiz AI <noreply@cleaningbizai.com>"
            
            NotificationService.send_notification(
                recipient=business.user,
                notification_type=['email', 'sms'],
                from_email=from_email,
                subject=subject,
                content=text_body,
                sender=business,
                email_to=business.user.email,
                sms_to=business.phone
            )
            
            BookingNotificationTracker.objects.create(
                booking=booking,
                notification_type='cleaner_assignment_check'
            )
            
            print(f"Sent cleaner assignment notification for booking {booking.bookingId} to {business.businessName}")
            
        return 0
    
    except Exception as e:
        print(f"Error checking booking cleaner assignments: {e}")
        return -1

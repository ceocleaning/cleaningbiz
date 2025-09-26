from email import message
from accounts.models import ApiCredential
from ai_agent.models import AgentConfiguration, Messages, Chat
from retell_agent.models import RetellAgent
from subscription.models import BusinessSubscription, SubscriptionPlan, UsageTracker
from retell import Retell
from .models import Lead, OpenJob, BookingNotificationTracker
from bookings.models import Booking
from notification.services import NotificationService
from django.utils import timezone
from django.conf import settings
from datetime import timedelta


def send_call_to_lead(lead_id):
    try:
        # Get the lead object from the database using the ID
        lead = Lead.objects.get(id=lead_id)
        retellAgent = RetellAgent.objects.get(business=lead.business)

        lead_details = f"Here are the details about the lead:\nName: {lead.name}\nPhone: {lead.phone_number}\nEmail: {lead.email if lead.email else 'Not provided'}\nAddress: {lead.address1 if lead.address1 else 'Not provided'}\nCity: {lead.city if lead.city else 'Not provided'}\nState: {lead.state if lead.state else 'Not provided'}\nZip Code: {lead.zipCode if lead.zipCode else 'Not provided'}\nProposed Start Time: {lead.proposed_start_datetime.strftime('%B %d, %Y at %I:%M %p') if lead.proposed_start_datetime else 'Not provided'}\nNotes: {lead.notes if lead.notes else 'No additional notes'}"

        if not lead.is_response_received and retellAgent.agent_number:
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
            lead.is_call_sent = True
            lead.call_sent_at = timezone.now()
            lead.save()
            
            print(call_response)
        
        return 0

    except Lead.DoesNotExist:
        return -1

    except Exception as e:
        print(f"Error making call: {e}")
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
            
            text_body = f"""Hello {business.businessName},
This is an important notification regarding booking {booking.bookingId}.
The booking is scheduled for today at {booking.startTime.strftime('%I:%M %p')} ({timezone.now().strft('%Y-%m-%d')}) - approximately 12 hours from now.
Customer: {booking.customer.first_name} {booking.customer.last_name}
Service: {booking.serviceType}
Address: {booking.customer.get_address() or 'N/A'}

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

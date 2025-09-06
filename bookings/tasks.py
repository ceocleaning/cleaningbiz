from .models import Booking
from accounts.models import ApiCredential
from django.db.models import Q
import datetime
from django.conf import settings
from django.utils import timezone
from twilio.rest import Client
from leadsAutomation.utils import send_email


from .email_template import get_email_template


def send_payment_reminder(booking_id):
    """
    Send a payment reminder email and SMS to clients when payment has not been made within 2 hours.
    Warns that the slot will be released if payment isn't made within 1 hour.
    
    """

    print(f"[INFO] Sending payment reminder for booking {booking_id}")
    try:
        booking = Booking.objects.get(bookingId=booking_id)
        # Check if booking is unpaid
        if not booking.is_paid():
            business = booking.business
            # Prepare message content
            email_subject = f"Urgent: Complete Your Payment for {business.businessName} Booking"
            # Create plain text email body
            text_body = f"""
PAYMENT REMINDER - {business.businessName}

Hello {booking.customer.get_full_name()},

We noticed that you haven't completed the payment for your cleaning service with {business.businessName}.

IMPORTANT: Your booking slot will be released if payment is not received within the next hour.

Booking Details:
- Service: {booking.get_serviceType_display()}
- Date: {booking.cleaningDate if isinstance(booking.cleaningDate, str) else booking.cleaningDate.strftime('%A, %B %d, %Y')}
- Time: {booking.startTime if isinstance(booking.startTime, str) else booking.startTime.strftime('%I:%M %p')} - {booking.endTime if isinstance(booking.endTime, str) else booking.endTime.strftime('%I:%M %p')}
- Amount Due: ${booking.totalPrice:.2f}

To secure your booking, please complete your payment here:
{settings.BASE_URL}/invoice/invoices/{booking.invoice.invoiceId}/preview/

If you have any questions, please contact us at {business.user.email or business.phone}.

This is an automated message from {business.businessName}.
            """
            # Send email
            try:
              
                # Set up email parameters
                from_email = f"{business.businessName} <{business.user.email}>"
                recipient_email = booking.customer.email
                
                # Send email based on available configuration
                send_email(
                    from_email=from_email,
                    to_email=recipient_email,
                    reply_to=business.user.email,
                    subject=email_subject,
                    text_content=text_body
                )
                    
                print(f"[INFO] Payment reminder email sent to {booking.customer.email} using default SMTP settings")
                
            except Exception as e:
                print(f"[ERROR] Failed to send payment reminder email: {str(e)}")
                
            # Send SMS reminder
            try:
                # Check if business has Twilio credentials
                if hasattr(business, 'apicredentials') and business.apicredentials:
                    api_cred = business.apicredentials
                    
                    if api_cred.twilioAccountSid and api_cred.twilioAuthToken and api_cred.twilioSmsNumber:
                        # Initialize Twilio client
                        client = Client(api_cred.twilioAccountSid, api_cred.twilioAuthToken)
                        
                        # SMS message content
                        sms_message = f"REMINDER from {business.businessName}: Your booking payment is pending. Your slot will be released in 1 hour if payment is not received. Complete payment here: {settings.BASE_URL}/invoice/invoices/{booking.invoice.invoiceId}/preview/"
                        
                        # Send SMS
                        message = client.messages.create(
                            body=sms_message,
                            from_=api_cred.twilioSmsNumber,
                            to=booking.customer.phone_number
                        )
                        
                        print(f"[INFO] Payment reminder SMS sent to {booking.customer.phone_number}, SID: {message.sid}")
                    else:
                        print("[INFO] No Twilio credentials found for business, skipping SMS reminder")
            except Exception as e:
                print(f"[ERROR] Failed to send payment reminder SMS: {str(e)}")
            
            # Update the booking to record when the payment reminder was sent
            booking.paymentReminderSentAt = timezone.now()
            booking.save() 
                
            return True
        else:
            print(f"[INFO] Booking {booking_id} is already paid, no reminder needed")
            return False
    except Booking.DoesNotExist:
        print(f"[ERROR] Booking with ID {booking_id} does not exist")
        return False
    except Exception as e:
        print(f"[ERROR] Error in send_payment_reminder: {str(e)}")
        return False


def delete_unpaid_bookings():
    """
    Find and delete unpaid bookings that are:
    1. Created more than 3 hours ago
    2. Have already received a payment reminder (paymentReminderSentAt is not null)
    3. Still unpaid
    
    This function should be scheduled to run periodically to clean up abandoned bookings
    after the 1-hour grace period following the payment reminder.
    """
    try:
        # Calculate the cutoff time (3 hours ago)
        three_hours_ago = timezone.now() - datetime.timedelta(hours=3)
        
        # Find bookings that match our criteria
        unpaid_bookings = Booking.objects.filter(
            createdAt__lte=three_hours_ago,  # Created more than 3 hours ago
        )
        
        deleted_count = 0
        for booking in unpaid_bookings:
            # Double-check if the booking is still unpaid
            if not booking.is_paid():
                # Log the booking details before deletion
                print(f"[INFO] Deleting unpaid booking: ID={booking.bookingId}, "
                      f"Name={booking.customer.get_full_name()}, "
                      f"Date={booking.cleaningDate}, "
                      f"Created={booking.createdAt}, "
                      f"Reminder Sent={booking.paymentReminderSentAt}")
                
                # Send cancellation notification if needed
                try:
                    business = booking.business
                    
                    # Email notification
                    subject = f"Booking Cancelled - {business.businessName}"
                    message = f"""
BOOKING CANCELLED

Hello {booking.customer.get_full_name()},

Your booking with {business.businessName} for {booking.cleaningDate.strftime('%A, %B %d, %Y')} at {booking.startTime.strftime('%I:%M %p')} has been cancelled due to non-payment.

Thank you,
{business.businessName}
                    """
                    
                    # Send email
                    from_email = f"{business.businessName} <{business.user.email}>" 

                    send_email(
                        from_email=from_email,
                        to_email=booking.customer.email,
                        reply_to=business.email,
                        subject=subject,
                        text_content=message
                    )
                except Exception as e:
                    print(f"[ERROR] Failed to send cancellation email: {str(e)}")
                
                # Delete the booking
                booking_id = booking.bookingId
                booking.delete()
                deleted_count += 1
                print(f"[INFO] Successfully deleted booking {booking_id}")
        
        print(f"[INFO] Deleted {deleted_count} unpaid bookings")
        return deleted_count
    except Exception as e:
        print(f"[ERROR] Error in delete_unpaid_bookings: {str(e)}")
        return 0
   

def send_day_before_reminder():
    """
    Send a reminder email and SMS to clients one day before their scheduled cleaning service.
    This helps reduce no-shows and allows clients to make any last-minute preparations.
    """
    try:
        # Calculate the date for bookings scheduled for tomorrow
        tomorrow = timezone.now().date() + datetime.timedelta(days=1)
        
        # Get all confirmed paid bookings scheduled for tomorrow
        bookings = Booking.objects.filter(
            Q(cleaningDate=tomorrow) | Q(cleaningDate=timezone.now().date()),
            cancelled_at__isnull=True,
            isCompleted=False
        )

       
        
        reminder_count = 0
        for booking in bookings:
            # Skip if a day-before reminder has already been sent
            if hasattr(booking, 'dayBeforeReminderSentAt') and booking.dayBeforeReminderSentAt:
                continue
                
            # Check if booking is paid
            if not booking.is_paid():
                continue
                
            business = booking.business
            to_whom = ['client', 'cleaner']
            # Prepare email content
            email_subject = f"Reminder: Your Cleaning Service with {business.businessName} Tomorrow"
            for to in to_whom:
                email_text = get_email_template(booking, to=to, when='tomorrow')
                recipient_email = booking.customer.email if to == 'client' else booking.cleaner.email

                from_email = f"{business.businessName} <{business.user.email}>"

                # Send email using the new utility
                send_email(
                    from_email=from_email,
                    to_email=recipient_email,
                    reply_to=business.user.email,
                    subject=email_subject,
                    text_content=email_text,
                )

            # Send SMS (unchanged)
            try:
                if hasattr(business, 'apicredentials') and business.apicredentials:
                    api_cred = business.apicredentials
                    if api_cred.twilioAccountSid and api_cred.twilioAuthToken and api_cred.twilioSmsNumber:
                        client = Client(api_cred.twilioAccountSid, api_cred.twilioAuthToken)
                        # Convert UTC date and time to business timezone for display
                        business_timezone = business.get_timezone()
                        
                        # Create datetime objects in UTC
                        utc_datetime = datetime.datetime.combine(booking.cleaningDate, booking.startTime)
                        utc_datetime = pytz.utc.localize(utc_datetime) if utc_datetime.tzinfo is None else utc_datetime
                        
                        # Convert to business timezone
                        local_datetime = utc_datetime.astimezone(business_timezone)
                        
                        # Format the local date and time for display
                        local_date = local_datetime.strftime('%A, %B %d')
                        local_time = local_datetime.strftime('%I:%M %p')
                        
                        sms_message = f"Reminder from {business.businessName}: Your cleaning service is scheduled for tomorrow, {local_date} at {local_time}. Please ensure access to your property. Questions? Call {business.phone}."
                        client.messages.create(
                            body=sms_message,
                            from_=api_cred.twilioSmsNumber,
                            to=booking.customer.phone_number
                        )
            except Exception as e:
                print(f"[ERROR] Failed to send day-before reminder SMS: {str(e)}")

            booking.dayBeforeReminderSentAt = timezone.now()
            booking.save()
            reminder_count += 1

        print(f"[INFO] Sent {reminder_count} day-before reminders (client & cleaner)")
        return reminder_count
    except Exception as e:
        print(f"[ERROR] Error in send_day_before_reminder: {str(e)}")
        return 0

def send_hour_before_reminder():
    """
    Send a reminder email and SMS to clients and cleaners one hour before their scheduled cleaning service.
    This final reminder helps ensure everyone is prepared for the service arrival.
    """
    try:
        now = timezone.now()
        one_hour_from_now = now + datetime.timedelta(hours=1)
        two_hours_from_now = now + datetime.timedelta(hours=2)
        
        # Get all confirmed paid bookings scheduled to start in the next hour
        current_date = now.date()
        
        # Find bookings for today where the start time is between 1-2 hours from now
        bookings = Booking.objects.filter(
            cleaningDate=current_date,
            startTime__gte=one_hour_from_now.time(),
            startTime__lt=two_hours_from_now.time(),
            cancelled_at__isnull=True,
            isCompleted=False,
            hourBeforeReminderSentAt__isnull=True
        )

        print(f"[INFO] Found {bookings.count()} bookings for hour-before reminder")
        
        reminder_count = 0
        for booking in bookings:
            # Skip if an hour-before reminder has already been sent
            if hasattr(booking, 'hourBeforeReminderSentAt') and booking.hourBeforeReminderSentAt:
                continue
                
            # Check if booking is paid
            if not booking.is_paid():
                continue
                
            business = booking.business
            
            # Prepare email content
            to_whom = ['client', 'cleaner'] 
            for to in to_whom:
                email_subject = f"Your {business.businessName} Cleaning Service Is Coming Soon"
                email_text = get_email_template(booking, to=to, when='in one hour')
                recipient_email = booking.customer.email if to == 'client' else booking.cleaner.email
             

                from_email = f"{business.businessName} <{business.user.email}>"

                # Send email using the new utility
                send_email(
                    from_email=from_email,
                    to_email=recipient_email,
                    reply_to=business.user.email,
                    subject=email_subject,
                    email_text=email_text
                )

            
            # Send SMS reminder
            try:
                # Check if business has Twilio credentials
                if hasattr(business, 'apicredentials') and business.apicredentials:
                    api_cred = business.apicredentials
                    
                    if api_cred.twilioAccountSid and api_cred.twilioAuthToken and api_cred.twilioSmsNumber:
                        # Initialize Twilio client
                        client = Client(api_cred.twilioAccountSid, api_cred.twilioAuthToken)
                        
                        # Convert UTC date and time to business timezone for display
                        business_timezone = business.get_timezone()
                        
                        # Create datetime objects in UTC
                        utc_datetime = datetime.datetime.combine(booking.cleaningDate, booking.startTime)
                        utc_datetime = pytz.utc.localize(utc_datetime) if utc_datetime.tzinfo is None else utc_datetime
                        
                        # Convert to business timezone
                        local_datetime = utc_datetime.astimezone(business_timezone)
                        
                        # Format the local time for display
                        local_time = local_datetime.strftime('%I:%M %p')
                        
                        # SMS message content
                        sms_message = f"REMINDER: Your {business.businessName} cleaning service begins in 1 hour at {local_time}. Please ensure property access. Questions? Call {business.phone}."
                        
                        # Send SMS
                        message = client.messages.create(
                            body=sms_message,
                            from_=api_cred.twilioSmsNumber,
                            to=booking.customer.phone_number
                        )
                        
                       
                        
            except Exception as e:
                print(f"[ERROR] Failed to send hour-before reminder SMS: {str(e)}")
            
            # Update the booking to record that the hour-before reminder was sent
            booking.hourBeforeReminderSentAt = timezone.now()
            booking.save()
            
            reminder_count += 1
            
      
        return reminder_count
        
    except Exception as e:
        print(f"[ERROR] Error in send_hour_before_reminder: {str(e)}")
        return 0


def send_post_service_followup():
    """
    Send a follow-up email and SMS to clients one day after their cleaning service was completed.
    This helps gather feedback, ensures satisfaction, and encourages repeat bookings.
    """
    try:
        # Calculate the date for bookings that were completed yesterday
        yesterday = timezone.now().date() - datetime.timedelta(days=1)
        
        # Get all completed bookings from yesterday
        bookings = Booking.objects.filter(
            cleaningDate=yesterday,
            isCompleted=True,
            cancelled_at__isnull=True
        )
        
        followup_count = 0
        for booking in bookings:
            # Skip if a post-service followup has already been sent
            if hasattr(booking, 'postServiceFollowupSent') and booking.postServiceFollowupSent:
                continue
                
            business = booking.business
            
            # Prepare email content
            email_subject = f"How was your experience with {business.businessName}?"
            
            # Create plain text email body
            text_body = f"""
THANK YOU FOR YOUR BUSINESS - {business.businessName}

Hello {booking.customer.get_full_name()},

Thank you for choosing {business.businessName} for your cleaning needs. We hope our service met your expectations.

YOUR RECENT SERVICE:
- Date: {booking.cleaningDate.strftime('%A, %B %d, %Y')}
- Service: {booking.get_serviceType_display()}

WE'D LOVE YOUR FEEDBACK
Your feedback is important to us and helps us improve our service. Could you take a moment to let us know how we did?
{settings.BASE_URL}/feedback/{booking.bookingId}/

SCHEDULE YOUR NEXT CLEANING
Would you like to schedule your next cleaning service? Visit the link below to book your preferred date and time.
{settings.BASE_URL}/book/{business.businessId}/

If you have any questions or special requests for future services, please don't hesitate to contact us at {business.phone or business.user.email}.

This is an automated message from {business.businessName}.
            """
            
            # Send email
            try:
                from_email = f"{business.businessName} <{business.user.email}>"
                recipient_email = booking.customer.email

                send_email(
                    from_email=from_email,
                    to_email=recipient_email,
                    reply_to=business.user.email,
                    subject=email_subject,
                    text_content=text_body
                )

            except Exception as e:
                print(f"[ERROR] Failed to send post-service followup email: {str(e)}")
            
            # Send SMS reminder
            try:
                # Check if business has Twilio credentials
                if hasattr(business, 'apicredentials') and business.apicredentials:
                    api_cred = business.apicredentials
                    
                    if api_cred.twilioAccountSid and api_cred.twilioAuthToken and api_cred.twilioSmsNumber:
                        # Initialize Twilio client
                        client = Client(api_cred.twilioAccountSid, api_cred.twilioAuthToken)
                        
                        # SMS message content
                        sms_message = f"Thank you for choosing {business.businessName}! How was your cleaning experience? Share feedback: {settings.BASE_URL}/feedback/{booking.bookingId}/ or book again: {settings.BASE_URL}/book/{business.businessId}/"
                        
                        # Send SMS
                        message = client.messages.create(
                            body=sms_message,
                            from_=api_cred.twilioSmsNumber,
                            to=booking.customer.phone_number
                        )
                        
                        print(f"[INFO] Post-service followup SMS sent to {booking.customer.phone_number}, SID: {message.sid}")
                    else:
                        print("[INFO] No Twilio credentials found for business, skipping SMS followup")
                        
            except Exception as e:
                print(f"[ERROR] Failed to send post-service followup SMS: {str(e)}")
            
            # Update the booking to record that the post-service followup was sent
            booking.postServiceFollowupSent = True
            booking.save()
            
            followup_count += 1
            
        print(f"[INFO] Sent {followup_count} post-service followups")
        return followup_count
        
    except Exception as e:
        print(f"[ERROR] Error in send_post_service_followup: {str(e)}")
        return 0
   
from accounts.models import CleanerProfile
from django.utils import timezone
import datetime
from leadsAutomation.utils import send_email
from notification.services import NotificationService
from accounts.timezone_utils import convert_from_utc, convert_to_utc
from datetime import datetime, timedelta
from bookings.utils import get_service_details



def send_arrival_confirmation_email(booking):
    """
    Send an email notification to the customer when the cleaner confirms arrival
    """
    business = booking.business
  
    
    # Get customer's full name
    customer_name = booking.customer.get_full_name()
    
    # Format date and time
    booking_date = booking.cleaningDate.strftime("%A, %B %d, %Y") if booking.cleaningDate else "N/A"
    booking_time = f"{booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}" if booking.startTime and booking.endTime else "N/A"
    
    
    full_address = booking.customer.get_address()
    
    # Get cleaner name
    cleaner_name = booking.cleaner.name if booking.cleaner else "Your cleaner"
    
    # Calculate estimated arrival time (current time + 15 minutes)
    now = timezone.now()
    local_now = convert_from_utc(now, booking.customer.timezone)
    arrival_time = local_now + timedelta(minutes=15)
    arrival_time_str = arrival_time.strftime("%I:%M %p")
    
    # Email subject
    subject = f"Cleaner is on the Way - {business.businessName}"
    

    
    # Create plain text version for email clients that don't support HTML
    text_body = f"""
    Hello {customer_name},
    
    Great news! {cleaner_name} is on the way to your location and should arrive around {arrival_time_str}.
    
    BOOKING DETAILS:
    Service: {booking.serviceType}
    Date: {booking_date}
    Time: {booking_time}
    Address: {full_address}
    Booking ID: {booking.bookingId}
    
    Please ensure your property is accessible for our cleaning team. If you have any special instructions or need to contact the cleaner, please call our customer service.
    
    Thank you for choosing {business.businessName}!
    
    {now.year} {business.businessName}. All rights reserved.
    This is an automated message, please do not reply directly to this email.
    """
    
    # Set the from email address using the SMTP config
    from_email = f"{business.businessName} <{business.user.email}>"

    # Send the email
    try:
        send_email(
            from_email=from_email,
            to_email=booking.customer.email,
            reply_to=business.user.email,
            subject=subject,
            text_content=text_body
        )
        return True
    except Exception as e:
        print(f"Error sending arrival confirmation email: {str(e)}")
        return False


def send_completion_notification_emails(booking):
    """
    Send email notifications to the customer, cleaner, and business owner when a booking is completed
    """
    business = booking.business
    customer_name = booking.customer.get_full_name()
    
    

    
    full_address = booking.customer.get_address()
    
    # Get cleaner name and email
    cleaner_name = booking.cleaner.name if booking.cleaner else "Your cleaner"
    cleaner_profile = CleanerProfile.objects.filter(cleaner=booking.cleaner).first()
    
    # Get business owner email
    business_owner_email = business.user.email if business.user else None
    
    # Set the from email address using the SMTP config
    from_email = f"{business.businessName} <{business.user.email}>"
    

    
    # 1. Send email to customer
    if booking.customer.email:
        customer_subject = f"Cleaning Service Completed - {business.businessName}"
        details = get_service_details(booking, 'customer')
        
        customer_text_body = f"""
Hello {customer_name},

Your Cleaning Service with {booking.business.businessName} has completed

Thank you for chosing {booking.business.businessName} for your cleaning service.

{details}



{timezone.now().year} {business.businessName}. All rights reserved.
This is an automated message, please do not reply directly to this email.
        """
        
        try:
            NotificationService.send_notification(
                recipient=booking.customer.user if booking.customer.user else None,
                from_email=from_email,
                notification_type=['sms', 'email'],
                subject=customer_subject,
                content=customer_text_body,
                to_email=booking.customer.email,
                to_sms=booking.customer.phone_number,
                sender=booking.business
            )

        except Exception as e:
            print(f"Error sending completion email and sms to customer: {str(e)}")
    
    # 3. Send email to business owner
    if business_owner_email:
        owner_subject = f"Booking Completed: {booking.bookingId}"
        details = get_service_details(booking, 'owner')

        
        owner_text_body = f"""
Hello,

A booking has been marked as completed by {cleaner_name}.

{details}

The booking has been successfully completed and marked as such in the system.

{timezone.now().year} {business.businessName}. All rights reserved.
This is an automated message, please do not reply directly to this email.
        """
        
        try:
            NotificationService.send_notification(
                recipient=booking.business.user,
                from_email=from_email,
                notification_type=['sms', 'email'],
                subject=owner_subject,
                content=owner_text_body,
                to_email=booking.business.user.email,
                to_sms=booking.business.phone,
                sender=booking.business
            )
        except Exception as e:
            print(f"Error sending completion email to business owner: {str(e)}")
    
    return True


def send_cleaner_arrived_notification(booking):
    """
    Send email and SMS notification to the customer when the cleaner has arrived at their location
    """
    business = booking.business
    customer_name = booking.customer.get_full_name()
     

    full_address = booking.customer.get_address()
    
    # Get cleaner name
    cleaner_name = booking.cleaner.name if booking.cleaner else "Your cleaner"
    
    # Get current time in customer's timezone
    now = timezone.now()
    current_time = convert_from_utc(now, booking.customer.timezone)
    arrival_time_str = current_time.strftime("%I:%M %p")
    
    # Email subject
    subject = f"Cleaner Has Arrived - {business.businessName}"

    details = get_service_details(booking, 'customer')
    
    # Create message content
    message_content = f"""
Hello {customer_name},

{cleaner_name} has arrived at your location at {arrival_time_str} and is ready to begin the cleaning service.

{details}

If you have any questions or need to provide additional instructions, please contact our customer service.

Thank you for choosing {business.businessName}!

{timezone.now().year} {business.businessName}. All rights reserved.
This is an automated message, please do not reply directly to this email.
    """
    
    # Set the from email address
    from_email = f"{business.businessName} <{business.user.email}>"
    
    # Send notification to customer
    try:
        NotificationService.send_notification(
            recipient=booking.customer.user if booking.customer.user else None,
            from_email=from_email,
            notification_type=['sms', 'email'],
            subject=subject,
            content=message_content,
            to_email=booking.customer.email,
            to_sms=booking.customer.phone_number,
            sender=booking.business
        )
        return True
    except Exception as e:
        print(f"Error sending cleaner arrived notification: {str(e)}")
        return False
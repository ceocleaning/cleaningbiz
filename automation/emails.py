from accounts.models import CleanerProfile
from django.utils import timezone
import datetime
from leadsAutomation.utils import send_email


def send_arrival_confirmation_email(booking):
    """
    Send an email notification to the customer when the cleaner confirms arrival
    """
    business = booking.business
  
    
    # Get customer's full name
    customer_name = f"{booking.customer.first_name} {booking.customer.last_name}" if booking.customer and booking.customer.last_name else (booking.customer.first_name if booking.customer else "Customer")
    
    # Format date and time
    booking_date = booking.cleaningDate.strftime("%A, %B %d, %Y") if booking.cleaningDate else "N/A"
    booking_time = f"{booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}" if booking.startTime and booking.endTime else "N/A"
    
    # Format address
    address_parts = []
    if booking.customer.address:
        address_parts.append(booking.customer.address)
   
    if booking.customer.city and booking.customer.state_or_province:
        address_parts.append(f"{booking.customer.city}, {booking.customer.state_or_province}")
    if booking.customer.zip_code:
        address_parts.append(booking.customer.zip_code)
    
    full_address = ", ".join(address_parts) if address_parts else "N/A"
    
    # Get cleaner name
    cleaner_name = booking.cleaner.name if booking.cleaner else "Your cleaner"
    
    # Calculate estimated arrival time (current time + 15 minutes)
    now = timezone.now()
    arrival_time = now + datetime.timedelta(minutes=15)
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
    
    {timezone.now().year} {business.businessName}. All rights reserved.
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
    
    # Format date and time
    booking_date = booking.cleaningDate.strftime("%A, %B %d, %Y") if booking.cleaningDate else "N/A"
    booking_time = f"{booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}" if booking.startTime and booking.endTime else "N/A"
    
    # Format address
    address_parts = []
    if booking.customer.address:
        address_parts.append(booking.customer.address)
    if booking.customer.city and booking.customer.state_or_province:
        address_parts.append(f"{booking.customer.city}, {booking.customer.state_or_province}")
    if booking.customer.zip_code:
        address_parts.append(booking.customer.zip_code)
    
    full_address = ", ".join(address_parts) if address_parts else "N/A"
    
    # Get cleaner name and email
    cleaner_name = booking.cleaner.name if booking.cleaner else "Your cleaner"
    cleaner_profile = CleanerProfile.objects.filter(cleaner=booking.cleaner).first()
    cleaner_email = cleaner_profile.user.email if cleaner_profile and cleaner_profile.user else None
    
    # Get business owner email
    business_owner_email = business.user.email if business.user else None
    
    # Set the from email address using the SMTP config
    from_email = f"{business.businessName} <{business.user.email}>"
    

    
    # 1. Send email to customer
    if booking.customer.email:
        customer_subject = f"Cleaning Service Completed - {business.businessName}"
        
        
        cleaner_text_body = f"""
        Hello {cleaner_name},
        
        Thank you for completing the cleaning service for booking {booking.bookingId}.
        
        JOB DETAILS:
        Client: {customer_name}
        Service: {booking.serviceType}
        Date: {booking_date}
        Time: {booking_time}
        Address: {full_address}
        Booking ID: {booking.bookingId}
        
        The job has been marked as completed in our system. Thank you for your hard work!
        
        {timezone.now().year} {business.businessName}. All rights reserved.
        This is an automated message, please do not reply directly to this email.
        """
        
        try:
            send_email(
                subject=cleaner_subject,
                to_email=cleaner_email,
                reply_to=business.user.email,
                text_content=cleaner_text_body,
                from_email=from_email
            )

        except Exception as e:
            print(f"Error sending completion email to cleaner: {str(e)}")
    
    # 3. Send email to business owner
    if business_owner_email:
        owner_subject = f"Booking Completed: {booking.bookingId}"

        
        owner_text_body = f"""
        Hello,
        
        A booking has been marked as completed by {cleaner_name}.
        
        BOOKING DETAILS:
        Client: {customer_name}
        Cleaner: {cleaner_name}
        Service: {booking.serviceType}
        Date: {booking_date}
        Time: {booking_time}
        Address: {full_address}
        Booking ID: {booking.bookingId}
        
        The booking has been successfully completed and marked as such in the system.
        
        {timezone.now().year} {business.businessName}. All rights reserved.
        This is an automated message, please do not reply directly to this email.
        """
        
        try:
            send_email(
                subject=owner_subject,
                to_email=business_owner_email,
                reply_to=business.user.email,
                text_content=owner_text_body,
                from_email=from_email
            )
        except Exception as e:
            print(f"Error sending completion email to business owner: {str(e)}")
    
    return True
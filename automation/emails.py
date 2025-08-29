from accounts.models import CleanerProfile
from django.utils import timezone
import datetime
from bookings.tasks import send_email_util
from django.contrib.auth.models import User
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
    
    # Create HTML email body
    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Cleaner Arrival Notification</title>
        <style>
            body {{
                font-family: Arial, sans-serif;
                line-height: 1.6;
                color: #333333;
                margin: 0;
                padding: 0;
            }}
            .container {{
                max-width: 600px;
                margin: 0 auto;
                padding: 20px;
            }}
            .header {{
                background-color: #4a90e2;
                color: white;
                padding: 20px;
                text-align: center;
            }}
            .content {{
                padding: 20px;
                background-color: #f9f9f9;
            }}
            .info-box {{
                background-color: white;
                border-radius: 5px;
                padding: 15px;
                margin-bottom: 20px;
                box-shadow: 0 2px 5px rgba(0,0,0,0.1);
            }}
            .info-label {{
                font-weight: bold;
                color: #4a90e2;
            }}
            .footer {{
                text-align: center;
                padding: 20px;
                font-size: 12px;
                color: #777777;
            }}
            .button {{
                display: inline-block;
                background-color: #4a90e2;
                color: white;
                padding: 10px 20px;
                text-decoration: none;
                border-radius: 5px;
                margin-top: 15px;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>Cleaner Arrival Notification</h1>
            </div>
            <div class="content">
                <p>Hello {customer_name},</p>
                
                <p>Great news! <strong>{cleaner_name}</strong> is on the way to your location and should arrive around <strong>{arrival_time_str}</strong>.</p>
                
                <div class="info-box">
                    <h3>Booking Details:</h3>
                    <p><span class="info-label">Service:</span> {booking.serviceType}</p>
                    <p><span class="info-label">Date:</span> {booking_date}</p>
                    <p><span class="info-label">Time:</span> {booking_time}</p>
                    <p><span class="info-label">Address:</span> {full_address}</p>
                    <p><span class="info-label">Booking ID:</span> {booking.bookingId}</p>
                </div>
                
                <p>Please ensure your property is accessible for our cleaning team. If you have any special instructions or need to contact the cleaner, please call our customer service.</p>
                
                <p>Thank you for choosing {business.businessName}!</p>
            </div>
            <div class="footer">
                <p>&copy; {timezone.now().year} {business.businessName}. All rights reserved.</p>
                <p>This is an automated message, please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """
    
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
            html_body=html_body,
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
    if booking.customer.address2:
        address_parts.append(booking.customer.address2)
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
    
    # Common email styles
    email_styles = """
        body {
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333333;
            margin: 0;
            padding: 0;
        }
        .container {
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
        }
        .header {
            background-color: #4a90e2;
            color: white;
            padding: 20px;
            text-align: center;
        }
        .content {
            padding: 20px;
            background-color: #f9f9f9;
        }
        .info-box {
            background-color: white;
            border-radius: 5px;
            padding: 15px;
            margin-bottom: 20px;
            box-shadow: 0 2px 5px rgba(0,0,0,0.1);
        }
        .info-label {
            font-weight: bold;
            color: #4a90e2;
        }
        .footer {
            text-align: center;
            padding: 20px;
            font-size: 12px;
            color: #777777;
        }
        .button {
            display: inline-block;
            background-color: #4a90e2;
            color: white;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 15px;
        }
    """
    
    # 1. Send email to customer
    if booking.customer.email:
        customer_subject = f"Cleaning Service Completed - {business.businessName}"
        
        customer_html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Cleaning Service Completed</title>
            <style>
                {email_styles}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Cleaning Service Completed</h1>
                </div>
                <div class="content">
                    <p>Hello {customer_name},</p>
                    
                    <p>We're pleased to inform you that your cleaning service has been successfully completed by <strong>{cleaner_name}</strong>.</p>
                    
                    <div class="info-box">
                        <h3>Booking Details:</h3>
                        <p><span class="info-label">Service:</span> {booking.serviceType}</p>
                        <p><span class="info-label">Date:</span> {booking_date}</p>
                        <p><span class="info-label">Time:</span> {booking_time}</p>
                        <p><span class="info-label">Address:</span> {full_address}</p>
                        <p><span class="info-label">Booking ID:</span> {booking.bookingId}</p>
                    </div>
                    
                    <p>We hope you're satisfied with our service. If you have any feedback or concerns, please don't hesitate to contact us.</p>
                    
                    <p>Thank you for choosing {business.businessName}!</p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} {business.businessName}. All rights reserved.</p>
                    <p>This is an automated message, please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        customer_text_body = f"""
        Hello {customer_name},
        
        We're pleased to inform you that your cleaning service has been successfully completed by {cleaner_name}.
        
        BOOKING DETAILS:
        Service: {booking.serviceType}
        Date: {booking_date}
        Time: {booking_time}
        Address: {full_address}
        Booking ID: {booking.bookingId}
        
        We hope you're satisfied with our service. If you have any feedback or concerns, please don't hesitate to contact us.
        
        Thank you for choosing {business.businessName}!
        
        {timezone.now().year} {business.businessName}. All rights reserved.
        This is an automated message, please do not reply directly to this email.
        """
        
        try:
            send_email(
                subject=customer_subject,
                to_email=booking.customer.email,
                from_email=from_email,
                reply_to=business.user.email,
                html_body=customer_html_body,
                text_content=customer_text_body
            )
            print("Completion email sent to customer.")
        except Exception as e:
            print(f"Error sending completion email to customer: {str(e)}")
    
    # 2. Send email to cleaner
    if cleaner_email:
        cleaner_subject = f"Job Completed: {booking.bookingId} - {business.businessName}"
        
        cleaner_html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Job Completed</title>
            <style>
                {email_styles}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Job Completed</h1>
                </div>
                <div class="content">
                    <p>Hello {cleaner_name},</p>
                    
                    <p>Thank you for completing the cleaning service for booking <strong>{booking.bookingId}</strong>.</p>
                    
                    <div class="info-box">
                        <h3>Job Details:</h3>
                        <p><span class="info-label">Client:</span> {customer_name}</p>
                        <p><span class="info-label">Service:</span> {booking.serviceType}</p>
                        <p><span class="info-label">Date:</span> {booking_date}</p>
                        <p><span class="info-label">Time:</span> {booking_time}</p>
                        <p><span class="info-label">Address:</span> {full_address}</p>
                        <p><span class="info-label">Booking ID:</span> {booking.bookingId}</p>
                    </div>
                    
                    <p>The job has been marked as completed in our system. Thank you for your hard work!</p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} {business.businessName}. All rights reserved.</p>
                    <p>This is an automated message, please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
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
                html_body=cleaner_html_body,
                text_content=cleaner_text_body,
                from_email=from_email
            )

        except Exception as e:
            print(f"Error sending completion email to cleaner: {str(e)}")
    
    # 3. Send email to business owner
    if business_owner_email:
        owner_subject = f"Booking Completed: {booking.bookingId}"
        
        owner_html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Booking Completed</title>
            <style>
                {email_styles}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Booking Completed</h1>
                </div>
                <div class="content">
                    <p>Hello,</p>
                    
                    <p>A booking has been marked as completed by <strong>{cleaner_name}</strong>.</p>
                    
                    <div class="info-box">
                        <h3>Booking Details:</h3>
                        <p><span class="info-label">Client:</span> {customer_name}</p>
                        <p><span class="info-label">Cleaner:</span> {cleaner_name}</p>
                        <p><span class="info-label">Service:</span> {booking.serviceType}</p>
                        <p><span class="info-label">Date:</span> {booking_date}</p>
                        <p><span class="info-label">Time:</span> {booking_time}</p>
                        <p><span class="info-label">Address:</span> {full_address}</p>
                        <p><span class="info-label">Booking ID:</span> {booking.bookingId}</p>
                    </div>
                    
                    <p>The booking has been successfully completed and marked as such in the system.</p>
                </div>
                <div class="footer">
                    <p>&copy; {timezone.now().year} {business.businessName}. All rights reserved.</p>
                    <p>This is an automated message, please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """
        
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
                html_body=owner_html_body,
                text_content=owner_text_body,
                from_email=from_email
            )
        except Exception as e:
            print(f"Error sending completion email to business owner: {str(e)}")
    
    return True
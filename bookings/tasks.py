from .models import Booking
from accounts.models import ApiCredential, SMTPConfig
from django.core.mail import send_mail, EmailMultiAlternatives
import datetime
from django.conf import settings
from django.utils import timezone
from twilio.rest import Client
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


def send_payment_reminder(booking_id):
    """
    Send a payment reminder email and SMS to clients when payment has not been made within 2 hours.
    Warns that the slot will be released if payment isn't made within 1 hour.
    """
    try:
        booking = Booking.objects.get(bookingId=booking_id)
        
        # Check if booking is unpaid
        if not booking.is_paid():
            business = booking.business
                
            # Prepare message content
            email_subject = f"URGENT: Complete Your Payment for {business.businessName} Booking"
                
            # Create HTML email body
            html_body = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Payment Reminder</title>
                <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background-color: #e74c3c; color: white; padding: 20px; text-align: center; }}
                        .content {{ padding: 20px; background-color: #f9f9f9; }}
                        .warning {{ color: #e74c3c; font-weight: bold; }}
                        .details {{ margin: 20px 0; }}
                        .details table {{ width: 100%; border-collapse: collapse; }}
                        .details table td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                        .details table td:first-child {{ font-weight: bold; width: 40%; }}
                        .button {{ display: inline-block; background-color: #e74c3c; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                        .footer {{ margin-top: 20px; text-align: center; font-size: 12px; color: #777; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Payment Reminder</h1>
                    </div>
                    <div class="content">
                        <p>Hello {booking.firstName} {booking.lastName},</p>
                        <p>We noticed that you haven't completed the payment for your cleaning service with {business.businessName}.</p>
                        
                        <p class="warning">⚠️ Important: Your booking slot will be released if payment is not received within the next hour.</p>
                        
                        <div class="details">
                            <h3>Booking Details:</h3>
                            <table>
                                <tr>
                                    <td>Service:</td>
                                    <td>{booking.get_serviceType_display()}</td>
                                </tr>
                                <tr>
                                    <td>Date:</td>
                                    <td>{booking.cleaningDate if isinstance(booking.cleaningDate, str) else booking.cleaningDate.strftime('%A, %B %d, %Y')}</td>
                                </tr>
                                <tr>
                                    <td>Time:</td>
                                    <td>{booking.startTime if isinstance(booking.startTime, str) else booking.startTime.strftime('%I:%M %p')} - {booking.endTime if isinstance(booking.endTime, str) else booking.endTime.strftime('%I:%M %p')}</td>
                                </tr>
                                <tr>
                                    <td>Amount Due:</td>
                                    <td>${booking.totalPrice:.2f}</td>
                                </tr>
                            </table>
                        </div>
                        
                        <p>To secure your booking, please complete your payment by clicking the button below:</p>
                        
                        <a href="{settings.BASE_URL}/invoice/invoices/{booking.invoice.invoiceId}/preview/" class="button">Complete Payment Now</a>
                        
                        <p>If you have any questions or need assistance, please contact us at {business.user.email or business.phone}.</p>
                    </div>
                    <div class="footer">
                        <p>This is an automated message from {business.businessName}.</p>
                    </div>
                </body>
                </html> 
                """                      
                 
            # Plain text version
            text_body = f"""
            PAYMENT REMINDER - {business.businessName}
            
            Hello {booking.firstName} {booking.lastName},
                
            We noticed that you haven't completed the payment for your cleaning service with {business.businessName}.
                
            IMPORTANT: Your booking slot will be released if payment is not received within the next hour.
                
            Booking Details:
            - Service: {booking.get_serviceType_display()}
            - Date: {booking.cleaningDate if isinstance(booking.cleaningDate, str) else booking.cleaningDate.strftime('%A, %B %d, %Y')}
            - Time: {booking.startTime if isinstance(booking.startTime, str) else booking.startTime.strftime('%I:%M %p')} - {booking.endTime if isinstance(booking.endTime, str) else booking.endTime.strftime('%I:%M %p')}
            - Amount Due: ${booking.totalPrice:.2f}
                
            To secure your booking, please complete your payment here:
            {settings.BASE_URL}/invoice/invoices/{booking.invoice.invoiceId}/preview/
                
            If you have any questions, please contact us at {business.email or business.phoneNumber}.
                
            This is an automated message from {business.businessName}.
            """
                
            # Send email
            try:
                # Get SMTP configuration for the business
                smtp_config = SMTPConfig.objects.filter(business=business).first()
                
                # Set up email parameters
                from_email = f"{business.businessName} <{business.email}>" if business.email else settings.DEFAULT_FROM_EMAIL
                recipient_email = booking.email
                
                # Send email based on available configuration
                if smtp_config and smtp_config.host and smtp_config.port and smtp_config.username and smtp_config.password:
                    # Create message container
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = email_subject
                    msg['From'] = from_email
                    msg['To'] = recipient_email
                    
                    # Attach parts
                    part1 = MIMEText(text_body, 'plain')
                    part2 = MIMEText(html_body, 'html')
                    msg.attach(part1)
                    msg.attach(part2)
                    
                    # Send using custom SMTP
                    server = smtplib.SMTP(host=smtp_config.host, port=smtp_config.port)
                    server.starttls()
                    server.login(smtp_config.username, smtp_config.password)
                    server.send_message(msg)
                    server.quit()
                    
                    print(f"[INFO] Payment reminder email sent to {booking.email} using business SMTP config")
                else:
                    # Use Django's email system
                    email_message = EmailMultiAlternatives(
                        subject=email_subject,
                        body=text_body,
                        from_email=from_email,
                        to=[recipient_email]
                    )
                    email_message.attach_alternative(html_body, "text/html")
                    email_message.send()
                    
                    print(f"[INFO] Payment reminder email sent to {booking.email} using default SMTP settings")
                
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
                            to=booking.phoneNumber
                        )
                        
                        print(f"[INFO] Payment reminder SMS sent to {booking.phoneNumber}, SID: {message.sid}")
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
            paymentReminderSentAt__isnull=False,  # Payment reminder was sent
        )
        
        deleted_count = 0
        for booking in unpaid_bookings:
            # Double-check if the booking is still unpaid
            if not booking.is_paid():
                # Log the booking details before deletion
                print(f"[INFO] Deleting unpaid booking: ID={booking.bookingId}, "
                      f"Name={booking.firstName} {booking.lastName}, "
                      f"Date={booking.cleaningDate}, "
                      f"Created={booking.createdAt}, "
                      f"Reminder Sent={booking.paymentReminderSentAt}")
                
                # Send cancellation notification if needed
                try:
                    business = booking.business
                    
                    # Email notification
                    subject = f"Booking Cancelled - {business.businessName}"
                    message = f"""
                    Hello {booking.firstName} {booking.lastName},
                    
                    Your booking with {business.businessName} for {booking.cleaningDate.strftime('%A, %B %d, %Y')} 
                    at {booking.startTime.strftime('%I:%M %p')} has been cancelled due to non-payment.
                    
                    Thank you,
                    {business.businessName}
                    """
                    
                    # Send email
                    from_email = f"{business.businessName} <{business.email}>" if business.email else settings.DEFAULT_FROM_EMAIL
                    send_mail(
                        subject,
                        message,
                        from_email,
                        [booking.email],
                        fail_silently=True,
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
   
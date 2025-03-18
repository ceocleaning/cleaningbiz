from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from bookings.models import Booking
from accounts.models import ApiCredential, SMTPConfig
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from twilio.rest import Client
from .models import Invoice, Payment
from automation.utils import sendEmailtoClientInvoice
from django.utils import timezone


def send_booking_confirmation_sms(sender, instance, created, **kwargs):
    """Send confirmation SMS when a new booking is created"""
    if created:  # Only send SMS for new bookings
        try:
            # Import needed modules
            from django.conf import settings
            from twilio.rest import Client
            
            # Get the business's API credentials
            apiCreds = ApiCredential.objects.get(business=instance.booking.business)
            
            # Check if Twilio credentials are configured
            if not apiCreds.twilioAccountSid or not apiCreds.twilioAuthToken or not apiCreds.twilioSmsNumber:
                print("Twilio credentials not configured for business")
                return False
            
            # Initialize Twilio client
            client = Client(apiCreds.twilioAccountSid, apiCreds.twilioAuthToken)
            
            # Get the invoice associated with this booking
            # We need to query for it directly since the signal might fire before the reverse relation is established
            try:
                
                
                # Generate invoice link
                invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
                
                # Create and send SMS
                message = client.messages.create(
                    to=instance.booking.phoneNumber,  # Use the booking's phone number
                    from_=apiCreds.twilioSmsNumber,
                    body=f"Hello {instance.booking.firstName}, your appointment with {instance.booking.business.businessName} is confirmed! Your total is ${instance.amount:.2f}. View and pay your invoice here: {invoice_link}"
                )
                
                print(f"SMS sent successfully to {instance.booking.phoneNumber}")
                return True
                
            except Exception as e:
                print(f"Error accessing invoice or sending SMS: {str(e)}")
                return False
                
        except Exception as e:
            print(f"Error in SMS notification: {str(e)}")
            return False



def send_booking_confirmation_email_with_invoice(sender, instance, created, **kwargs):
    """Send HTML email confirmation with invoice details when a new booking is created"""
    if created:  # Only send email for new bookings
        try:
            # Import needed modules
            from django.conf import settings

            
            # Get SMTP configuration
            smtpConfig = SMTPConfig.objects.filter(business=instance.booking.business)
            
            if not smtpConfig.exists() or not smtpConfig.first().username or not smtpConfig.first().password:
                print("Email credentials not configured for business")
                return False

            config = smtpConfig.first()
            
            # Generate invoice link
            invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
            
            # Create the email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Appointment Confirmation - {instance.booking.business.businessName}'
            msg['From'] = config.username
            msg['To'] = instance.booking.email

            # Create HTML email content with invoice details
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <meta charset="UTF-8">
                <meta name="viewport" content="width=device-width, initial-scale=1.0">
                <title>Appointment Confirmation</title>
                <style>
                    body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                    .header {{ background-color: #4a90e2; color: white; padding: 20px; text-align: center; }}
                    .content {{ padding: 20px; background-color: #f9f9f9; }}
                    .details {{ margin: 20px 0; }}
                    .details table {{ width: 100%; border-collapse: collapse; }}
                    .details table td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                    .details table td:first-child {{ font-weight: bold; width: 40%; }}
                    .button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                    .footer {{ margin-top: 20px; text-align: center; font-size: 12px; color: #777; }}
                </style>
            </head>
            <body>
                <div class="header">
                    <h1>Appointment Confirmed!</h1>
                </div>
                <div class="content">
                    <p>Hello {instance.booking.firstName} {instance.booking.lastName},</p>
                    <p>Your appointment with {instance.booking.business.businessName} has been confirmed. Thank you for choosing our services!</p>
                    
                    <div class="details">
                        <h3>Appointment Details:</h3>
                        <table>
                            <tr>
                                <td>Date:</td>
                                <td>{instance.booking.cleaningDate.strftime('%A, %B %d, %Y')}</td>
                            </tr>
                            <tr>
                                <td>Time:</td>
                                <td>{instance.booking.startTime.strftime('%I:%M %p')} - {instance.booking.endTime.strftime('%I:%M %p')}</td>
                            </tr>
                            <tr>
                                <td>Service Type:</td>
                                <td>{instance.booking.serviceType.title()} Cleaning</td>
                            </tr>
                            <tr>
                                <td>Address:</td>
                                <td>{instance.booking.address1}, {instance.booking.city}, {instance.booking.stateOrProvince} {instance.booking.zipCode}</td>
                            </tr>
                            <tr>
                                <td>Total Amount:</td>
                                <td>${instance.amount:.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p>To view your invoice and make a payment, please click the button below:</p>
                    <a href="{invoice_link}" class="button">View Invoice</a>
                    
                    <p>If you have any questions or need to make changes to your appointment, please contact us.</p>
                    <p>We look forward to serving you!</p>
                </div>
                <div class="footer">
                    <p>&copy; {instance.booking.business.businessName} | {instance.booking.business.user.email}</p>
                </div>
            </body>
            </html>
            """
            
            # Plain text alternative
            text_content = f"""Hello {instance.booking.firstName},

            Your appointment with {instance.booking.business.businessName} has been confirmed for {instance.booking.cleaningDate.strftime('%A, %B %d, %Y')} at {instance.booking.startTime.strftime('%I:%M %p')}.

            Service: {instance.booking.serviceType.title()} Cleaning
            Address: {instance.booking.address1}, {instance.booking.city}, {instance.booking.stateOrProvince} {instance.booking.zipCode}
            Total Amount: ${instance.amount:.2f}

            To view your invoice and make a payment, please visit: {invoice_link}

            Thank you for choosing {instance.booking.business.businessName}!
            """

            # Attach parts
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Set up SMTP connection
            smtp_server = smtplib.SMTP(config.host, config.port)
            if config.port == 587:
                smtp_server.starttls()
            smtp_server.login(config.username, config.password)
            
            # Send email
            smtp_server.send_message(msg)
            smtp_server.quit()
            
            print(f"Email confirmation with invoice sent successfully to {instance.booking.email}")
            return True
            
        except Exception as e:
            print(f"Error sending email with invoice: {str(e)}")
            return False


@receiver(post_save, sender=Payment)
def send_email_payment_completed(sender, instance, created, **kwargs):
    """Send email notification to client when payment is completed"""
    # Check if this is a Square payment with a payment ID and the invoice is marked as paid
    if instance.squarePaymentId and instance.invoice.isPaid:
        try:
            # Get the invoice and related booking
            invoice = instance.invoice
            booking = invoice.booking
            business = booking.business
            
            # Update payment status if not already completed
            if instance.status != 'COMPLETED':
                instance.status = 'COMPLETED'
                instance.paidAt = timezone.now()
                instance.save(update_fields=['status', 'paidAt'])
            
            # Send custom payment confirmation email
            try:
                # Get SMTP configuration for the business
                smtp_config = SMTPConfig.objects.filter(business=business).first()
                
                # Create email subject and content
                subject = f"Payment Confirmation - {business.businessName}"
                
                # Create HTML email body
                html_body = f"""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="UTF-8">
                    <meta name="viewport" content="width=device-width, initial-scale=1.0">
                    <title>Payment Confirmation</title>
                    <style>
                        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px; }}
                        .header {{ background-color: #4a90e2; color: white; padding: 20px; text-align: center; }}
                        .content {{ padding: 20px; background-color: #f9f9f9; }}
                        .details {{ margin: 20px 0; }}
                        .details table {{ width: 100%; border-collapse: collapse; }}
                        .details table td {{ padding: 8px; border-bottom: 1px solid #ddd; }}
                        .details table td:first-child {{ font-weight: bold; width: 40%; }}
                        .button {{ display: inline-block; background-color: #4CAF50; color: white; padding: 12px 24px; text-decoration: none; border-radius: 4px; margin-top: 20px; }}
                        .footer {{ margin-top: 20px; text-align: center; font-size: 12px; color: #777; }}
                    </style>
                </head>
                <body>
                    <div class="header">
                        <h1>Payment Confirmed!</h1>
                    </div>
                    <div class="content">
                        <p>Hello {booking.firstName} {booking.lastName},</p>
                        <p>We're pleased to confirm that your payment for the cleaning service with {business.businessName} has been successfully processed.</p>
                        
                        <div class="details">
                            <h3>Payment Details:</h3>
                            <table>
                                <tr>
                                    <td>Invoice ID:</td>
                                    <td>{invoice.invoiceId}</td>
                                </tr>
                                <tr>
                                    <td>Square Payment ID:</td>
                                    <td>{instance.squarePaymentId}</td>
                                </tr>
                                <tr>
                                    <td>Amount Paid:</td>
                                    <td>${invoice.amount:.2f}</td>
                                </tr>
                                <tr>
                                    <td>Payment Date:</td>
                                    <td>{instance.paidAt.strftime('%B %d, %Y at %I:%M %p')}</td>
                                </tr>
                                <tr>
                                    <td>Payment Method:</td>
                                    <td>Square</td>
                                </tr>
                            </table>
                        </div>
                        
                        <div class="details">
                            <h3>Appointment Details:</h3>
                            <table>
                                <tr>
                                    <td>Date:</td>
                                    <td>{booking.cleaningDate.strftime('%A, %B %d, %Y')}</td>
                                </tr>
                                <tr>
                                    <td>Time:</td>
                                    <td>{booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}</td>
                                </tr>
                                <tr>
                                    <td>Service:</td>
                                    <td>{booking.serviceType.title()} Cleaning</td>
                                </tr>
                            </table>
                        </div>
                        
                        <p>Thank you for choosing {business.businessName}. We look forward to providing you with excellent service!</p>
                        
                        <p>If you have any questions or need to make changes to your appointment, please contact us.</p>
                    </div>
                    <div class="footer">
                        <p>&copy; {timezone.now().year} {business.businessName}. All rights reserved.</p>
                        <p>{business.address}</p>
                        <p>Phone: {business.phone} | Email: {business.user.email}</p>
                    </div>
                </body>
                </html>
                """
                
                # Create plain text version
                text_body = f"""Payment Confirmation - {business.businessName}
                
                    Hello {booking.firstName} {booking.lastName},

                    We're pleased to confirm that your payment for the cleaning service with {business.businessName} has been successfully processed.

                    Payment Details:
                    - Invoice ID: {invoice.invoiceId}
                    - Square Payment ID: {instance.squarePaymentId}
                    - Amount Paid: ${invoice.amount:.2f}
                    - Payment Date: {instance.paidAt.strftime('%B %d, %Y at %I:%M %p')}
                    - Payment Method: Square

                    Appointment Details:
                    - Date: {booking.cleaningDate.strftime('%A, %B %d, %Y')}
                    - Time: {booking.startTime.strftime('%I:%M %p')} - {booking.endTime.strftime('%I:%M %p')}
                    - Service: {booking.serviceType.title()} Cleaning

                    Thank you for choosing {business.businessName}. We look forward to providing you with excellent service!

                    If you have any questions or need to make changes to your appointment, please contact us.

                    {business.businessName}
                    {business.address}
                    Phone: {business.phone} | Email: {business.user.email}
                """
                
                # Set up email parameters
                from_email = f"{business.businessName} <{business.email}>" if business.email else settings.DEFAULT_FROM_EMAIL
                recipient_email = booking.email
                
                # Send email based on available configuration
                if smtp_config:
                    # Create message container
                    msg = MIMEMultipart('alternative')
                    msg['Subject'] = subject
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
                else:
                    # Use Django's email system
                    from django.core.mail import EmailMultiAlternatives
                    email_message = EmailMultiAlternatives(
                        subject=subject,
                        body=text_body,
                        from_email=from_email,
                        to=[recipient_email]
                    )
                    email_message.attach_alternative(html_body, "text/html")
                    email_message.send()
                
                print(f"[DEBUG] Payment confirmation email sent successfully for invoice {invoice.invoiceId}")
                return True
                
            except Exception as e:
                print(f"[ERROR] Failed to send payment confirmation email: {str(e)}")
                return False
                
        except Exception as e:
            print(f"[ERROR] Error in send_email_payment_completed: {str(e)}")


# Connect the signals
post_save.connect(send_booking_confirmation_sms, sender=Invoice)
post_save.connect(send_booking_confirmation_email_with_invoice, sender=Invoice)

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Booking
from accounts.models import ApiCredential, SMTPConfig
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from twilio.rest import Client


def send_booking_confirmation_sms(sender, instance, created, **kwargs):
    """Send confirmation SMS when a new booking is created"""
    if created:  # Only send SMS for new bookings
        try:
            # Import needed modules
            from django.conf import settings
            from twilio.rest import Client
            from invoice.models import Invoice
            
            # Get the business's API credentials
            apiCreds = ApiCredential.objects.get(business=instance.business)
            
            # Check if Twilio credentials are configured
            if not apiCreds.twilioAccountSid or not apiCreds.twilioAuthToken or not apiCreds.twilioSmsNumber:
                print("Twilio credentials not configured for business")
                return False
            
            # Initialize Twilio client
            client = Client(apiCreds.twilioAccountSid, apiCreds.twilioAuthToken)
            
            # Get the invoice associated with this booking
            # We need to query for it directly since the signal might fire before the reverse relation is established
            try:
                # Try to find the invoice by booking
                invoice = Invoice.objects.filter(booking=instance).first()
                
                if not invoice:
                    print(f"No invoice found for booking {instance.bookingId}. SMS notification skipped.")
                    return False
                
                # Generate invoice link
                invoice_link = f"{settings.BASE_URL}/invoice/invoices/{invoice.invoiceId}/preview/"
                
                # Create and send SMS
                message = client.messages.create(
                    to=instance.phoneNumber,  # Use the booking's phone number
                    from_=apiCreds.twilioSmsNumber,
                    body=f"Hello {instance.firstName}, your appointment with {instance.business.businessName} is confirmed! Your total is ${invoice.amount:.2f}. View and pay your invoice here: {invoice_link}"
                )
                
                print(f"SMS sent successfully to {instance.phoneNumber}")
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
            from invoice.models import Invoice
            
            # Try to find the invoice by booking
            invoice = Invoice.objects.filter(booking=instance).first()
            
            if not invoice:
                print(f"No invoice found for booking {instance.bookingId}. Email notification skipped.")
                return False
                
            # Get SMTP configuration
            smtpConfig = SMTPConfig.objects.filter(business=instance.business)
            
            if not smtpConfig.exists() or not smtpConfig.first().username or not smtpConfig.first().password:
                print("Email credentials not configured for business")
                return False

            config = smtpConfig.first()
            
            # Generate invoice link
            invoice_link = f"{settings.BASE_URL}/invoice/invoices/{invoice.invoiceId}/preview/"
            
            # Create the email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Appointment Confirmation - {instance.business.businessName}'
            msg['From'] = config.username
            msg['To'] = instance.email

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
                    <p>Hello {instance.firstName} {instance.lastName},</p>
                    <p>Your appointment with {instance.business.businessName} has been confirmed. Thank you for choosing our services!</p>
                    
                    <div class="details">
                        <h3>Appointment Details:</h3>
                        <table>
                            <tr>
                                <td>Date:</td>
                                <td>{instance.cleaningDate.strftime('%A, %B %d, %Y')}</td>
                            </tr>
                            <tr>
                                <td>Time:</td>
                                <td>{instance.startTime.strftime('%I:%M %p')} - {instance.endTime.strftime('%I:%M %p')}</td>
                            </tr>
                            <tr>
                                <td>Service Type:</td>
                                <td>{instance.serviceType.title()} Cleaning</td>
                            </tr>
                            <tr>
                                <td>Address:</td>
                                <td>{instance.address1}, {instance.city}, {instance.stateOrProvince} {instance.zipCode}</td>
                            </tr>
                            <tr>
                                <td>Total Amount:</td>
                                <td>${invoice.amount:.2f}</td>
                            </tr>
                        </table>
                    </div>
                    
                    <p>To view your invoice and make a payment, please click the button below:</p>
                    <a href="{invoice_link}" class="button">View Invoice</a>
                    
                    <p>If you have any questions or need to make changes to your appointment, please contact us.</p>
                    <p>We look forward to serving you!</p>
                </div>
                <div class="footer">
                    <p>&copy; {instance.business.businessName} | {instance.business.user.email}</p>
                </div>
            </body>
            </html>
            """
            
            # Plain text alternative
            text_content = f"""Hello {instance.firstName},

            Your appointment with {instance.business.businessName} has been confirmed for {instance.cleaningDate.strftime('%A, %B %d, %Y')} at {instance.startTime.strftime('%I:%M %p')}.

            Service: {instance.serviceType.title()} Cleaning
            Address: {instance.address1}, {instance.city}, {instance.stateOrProvince} {instance.zipCode}
            Total Amount: ${invoice.amount:.2f}

            To view your invoice and make a payment, please visit: {invoice_link}

            Thank you for choosing {instance.business.businessName}!
            """

            # Attach parts
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Set up SMTP connection
            smtp_server = smtplib.SMTP(config.host, config.port)
            if config.useTLS:
                smtp_server.starttls()
            smtp_server.login(config.username, config.password)
            
            # Send email
            smtp_server.send_message(msg)
            smtp_server.quit()
            
            print(f"Email confirmation with invoice sent successfully to {instance.email}")
            return True
            
        except Exception as e:
            print(f"Error sending email with invoice: {str(e)}")
            return False

# Connect the signals
post_save.connect(send_booking_confirmation_sms, sender=Booking)
post_save.connect(send_booking_confirmation_email_with_invoice, sender=Booking)

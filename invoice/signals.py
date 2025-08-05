from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from bookings.models import Booking
from accounts.models import ApiCredential, SMTPConfig, Business
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from twilio.rest import Client
from .models import Invoice, Payment
from automation.utils import sendEmailtoClientInvoice
from django.utils import timezone
import json


@receiver(post_save, sender=Invoice)
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
                    body=f"Hello {instance.booking.firstName}, your appointment with {instance.booking.business.businessName} is pending!\n\nAppointment Details:\nDate: {instance.booking.cleaningDate}\nTime: {instance.booking.startTime}\nService: {instance.booking.serviceType}\nLocation: {instance.booking.address1}, {instance.booking.city}\n\nTotal Amount: ${instance.amount:.2f}\n\nPlease pay to confirm your appointment. View and pay your invoice here: {invoice_link}"
                )
                
                print(f"SMS sent successfully to {instance.booking.phoneNumber}")
                return True
                
            except Exception as e:
                print(f"Error accessing invoice or sending SMS: {str(e)}")
                return False
                
        except Exception as e:
            print(f"Error in SMS notification: {str(e)}")
            return False


@receiver(post_save, sender=Invoice)
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
                    <p>Your appointment with {instance.booking.business.businessName} is Pending. Please Pay to confirm your appointment. Thank you for choosing our services!</p>
                    
                    <div class="details">
                        <h3>Appointment Details:</h3>
                        <table>
                            <tr>
                                <td>Date:</td>
                                <td>{format_date(instance.booking.cleaningDate)}</td>
                            </tr>
                            <tr>
                                <td>Time:</td>
                                <td>{format_time(instance.booking.startTime)} - {format_time(instance.booking.endTime)}</td>
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
                                <td>Bedrooms:</td>
                                <td>{instance.booking.bedrooms}</td>
                            </tr>
                            <tr>
                                <td>Bedrooms:</td>
                                <td>{instance.booking.bathrooms}</td>
                            </tr>
                            <tr>
                                <td>Square Feet:</td>
                                <td>{instance.booking.squareFeet}</td>
                            </tr>
                            <tr>
                                <td>Addtional Requests:</td>
                                <td>{instance.booking.otherRequests}</td>
                            </tr>

                            <tr>
                                <td>Addons:</td>
                                <td>{instance.booking.get_all_addons()}</td>
                            </tr>


                            <tr>
                                <td>Subtotal:</td>
                                <td>${instance.booking.totalPrice - instance.booking.tax}</td>
                            </tr>
                            <tr>
                                <td>Tax:</td>
                                <td>${instance.booking.tax:.2f}</td>
                            </tr>
                            <tr>
                                <td>Total Amount:</td>
                                <td>${instance.amount:.2f}</td>
                            </tr>
                        </table>
                    </div>
                    <p>Please note that this is a pending payment. Once the payment is confirmed, your appointment will be confirmed.</p>
                    <p>To view your invoice and make a payment, please click the button below:</p>
                    <a href="{invoice_link}" class="button">View Invoice</a>

                    <a href="{invoice_link}">{invoice_link}</a>
                    
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

            Your appointment with {instance.booking.business.businessName} is pending for {format_date(instance.booking.cleaningDate)} at {format_time(instance.booking.startTime)}.

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







# Helper functions for date and time formatting
def format_date(date_value):
    """Format a date value safely, handling both date objects and strings"""
    if hasattr(date_value, 'strftime'):
        return date_value.strftime('%A, %B %d, %Y')
    return str(date_value)

def format_time(time_value):
    """Format a time value safely, handling both time objects and strings"""
    if hasattr(time_value, 'strftime'):
        return time_value.strftime('%I:%M %p')
    return str(time_value)


from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from bookings.models import Booking
from accounts.models import ApiCredential, Business
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
from twilio.rest import Client
from .models import Invoice, Payment
from automation.utils import sendEmailtoClientInvoice
from django.utils import timezone
import json
from leadsAutomation.utils import send_email


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

            
          
            
            # Generate invoice link
            invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
          

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

            send_email(
                from_email=f"{instance.booking.business.businessName} <{instance.booking.business.user.email}>",
                to_email=instance.booking.email,
                subject="Appointment Confirmation",
                html_content=html_content,
                text_content=text_content,
                reply_to=instance.booking.email
            )

       

            
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




@receiver(post_save, sender=Payment)
def send_payment_submitted_email(sender, instance, created, **kwargs):
    """Send HTML email confirmation with invoice details when a new payment of bank transfer is created"""
    # Only proceed for new bank transfer payments
    if created and instance.paymentMethod == 'bank_transfer' and instance.status == 'SUBMITTED':
        try:
            # Get the business and invoice details
            business = instance.invoice.booking.business
            customer = instance.invoice.booking
  
            # Email subject and content
            subject = f"New Bank Transfer Payment Received - {business.businessName}"
            recipient_email = business.user.email
          
            # HTML email content
            html_message = f"""
            <html>
                <body>
                    <h2>New Bank Transfer Payment Received</h2>
                    <p>Hello {business.user.first_name or business.businessName},</p>
                    <p>You have received a new bank transfer payment from {customer.firstName} {customer.lastName} for booking #{instance.invoice.booking.bookingId}.</p>
                    
                    <h3>Payment Details:</h3>
                    <ul>
                        <li><strong>Amount:</strong> ${instance.amount:.2f}</li>
                        <li><strong>Payment Method:</strong> Bank Transfer</li>
                        <li><strong>Transaction ID:</strong> {instance.transactionId or 'N/A'}</li>
                        <li><strong>Customer Name:</strong> {customer.firstName} {customer.lastName}</li>
                        <li><strong>Customer Email:</strong> {customer.email}</li>
                        <li><strong>Customer Phone:</strong> {customer.phoneNumber}</li>
                    </ul>
                    
                    <p>Please log in to your dashboard to review and approve this payment.</p>
               
                </body>
            </html>
            """
            
            # Plain text version for email clients that don't support HTML
            plain_message = f"""
            New Bank Transfer Payment Received
            
            Hello {business.user.first_name or business.businessName},
            
            You have received a new bank transfer payment from {customer.firstName} {customer.lastName} for booking #{instance.invoice.booking.bookingId}.
            
            Payment Details:
            - Amount: ${instance.amount:.2f}
            - Payment Method: Bank Transfer
            - Transaction ID: {instance.transactionId or 'N/A'}
            - Customer Name: {customer.firstName} {customer.lastName}
            - Customer Email: {customer.email}
            - Customer Phone: {customer.phoneNumber}
            
            Please log in to your dashboard to review and approve this payment.
      
            """
            
            send_email(
                from_email=f"{business.businessName} <{business.user.email}>",
                to_email=recipient_email,
                subject=subject,
                html_content=html_message,
                text_content=plain_message,
                reply_to=business.user.email
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending payment submitted email: {str(e)}")
            return False
    return True


@receiver(post_save, sender=Payment)
def send_payment_approved_email(sender, instance, created, **kwargs):
    """Send HTML email confirmation with invoice details when a new payment of bank transfer is created"""
    # Only proceed for new bank transfer payments
    if instance.paymentMethod == 'bank_transfer' and (instance.status == 'APPROVED' or instance.status == 'REJECTED'):
        try:
            # Get the business and invoice details
            business = instance.invoice.booking.business
            customer = instance.invoice.booking
            customer_name = f"{customer.firstName} {customer.lastName}"
            # Email subject and content
            subject = f"Payment {instance.status} - {customer_name if instance.status == 'APPROVED' else business.businessName}"
            recipient_email = customer.email if instance.status == 'APPROVED' else business.user.email
          
            # HTML email content
            html_message = f"""
            <html>
                <body>
                    <h2>Payment {instance.status}</h2>
                    <p>Hello {customer_name if instance.status == 'APPROVED' else business.businessName},</p>
                    <p>Payment has been {instance.status} for booking #{instance.invoice.booking.bookingId}.</p>
                    
                    <h3>Payment Details:</h3>
                    <ul>
                        <li><strong>Amount:</strong> ${instance.amount:.2f}</li>
                        <li><strong>Payment Method:</strong> Bank Transfer</li>
                        <li><strong>Transaction ID:</strong> {instance.transactionId or 'N/A'}</li>
                        <li><strong>Customer Name:</strong> {customer.firstName} {customer.lastName}</li>
                        <li><strong>Customer Email:</strong> {customer.email}</li>
                        <li><strong>Customer Phone:</strong> {customer.phoneNumber}</li>
                    </ul>
                    
       
               
                </body>
            </html>
            """
            
            # Plain text version for email clients that don't support HTML
            plain_message = f"""
            Payment {instance.status}
            
            Hello {customer_name if instance.status == 'APPROVED' else business.businessName},
            
            Payment has been {instance.status} for booking #{instance.invoice.booking.bookingId}.
            
            Payment Details:
            - Amount: ${instance.amount:.2f}
            - Payment Method: Bank Transfer
            - Transaction ID: {instance.transactionId or 'N/A'}
            - Customer Name: {customer.firstName} {customer.lastName}
            - Customer Email: {customer.email}
            - Customer Phone: {customer.phoneNumber}
            
      
            """
            
            send_email(
                from_email=f"{business.businessName} <{business.user.email}>",
                to_email=recipient_email,
                subject=subject,
                html_content=html_message,
                text_content=plain_message,
                reply_to=business.user.email
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending payment submitted email: {str(e)}")
            return False
            
    return True

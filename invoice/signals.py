from django.db.models.signals import post_save
from django.dispatch import receiver

from django.conf import settings
from bookings.models import Booking
from accounts.models import ApiCredential, Business
from datetime import datetime, timedelta
from twilio.rest import Client
from django.conf import settings
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
            
            if settings.DEBUG == False:
                # Initialize Twilio client
                client = Client(apiCreds.twilioAccountSid, apiCreds.twilioAuthToken)
                
                # Get the invoice associated with this booking
                # We need to query for it directly since the signal might fire before the reverse relation is established
                try:
                    
                    # Generate invoice link
                    invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
                    
                    # Create and send SMS
                    message = client.messages.create(
                        to=instance.booking.customer.phone_number,  # Use the booking's phone number
                        from_=apiCreds.twilioSmsNumber,
                        body=f"Hello {instance.booking.customer.get_full_name()}, your appointment with {instance.booking.business.businessName} is pending!\n\nAppointment Details:\nDate: {instance.booking.cleaningDate}\nTime: {instance.booking.startTime}\nService: {instance.booking.serviceType}\nLocation: {instance.booking.customer.get_address() or 'N/A'}\n\nTotal Amount: ${instance.amount:.2f}\n\nPlease pay to confirm your appointment. View and pay your invoice here: {invoice_link}"
                    )
                    
                    print(f"SMS sent successfully to {instance.booking.customer.phone_number}")
                    return True
                    
                except Exception as e:
                    print(f"Error accessing invoice or sending SMS: {str(e)}")
                    return False
            
            else:
                print("Debug Mode - Skipping SMS")
                
        except Exception as e:
            print(f"Error in SMS notification: {str(e)}")
            return False


@receiver(post_save, sender=Invoice)
def send_booking_confirmation_email_with_invoice(sender, instance, created, **kwargs):
    """Send HTML email confirmation with invoice details when a new booking is created"""
    if created:  # Only send email for new bookings
        try:

            invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
          

            # Create plain text email content with invoice details
            text_content = f"""APPOINTMENT CONFIRMATION

Hello {instance.booking.customer.get_full_name()},

Your appointment with {instance.booking.business.businessName} is Pending. Please Pay to confirm your appointment. Thank you for choosing our services!

APPOINTMENT DETAILS:
- Date: {format_date(instance.booking.cleaningDate)}
- Time: {format_time(instance.booking.startTime)} - {format_time(instance.booking.endTime)}
- Service Type: {instance.booking.serviceType.title()} Cleaning
- Address: {instance.booking.customer.get_address() or 'N/A'}
- Bedrooms: {instance.booking.bedrooms}
- Bathrooms: {instance.booking.bathrooms}
- Square Feet: {instance.booking.squareFeet}
- Additional Requests: {instance.booking.otherRequests}
- Addons: {instance.booking.get_all_addons()}

PRICING:
- Subtotal: ${instance.booking.totalPrice - instance.booking.tax}
- Tax: ${instance.booking.tax:.2f}
- Total Amount: ${instance.amount:.2f}

Please note that this is a pending payment. Once the payment is confirmed, your appointment will be confirmed.

To view your invoice and make a payment, please visit: {invoice_link}

If you have any questions or need to make changes to your appointment, please contact us.

We look forward to serving you!

{instance.booking.business.businessName} | {instance.booking.business.user.email}
            """
            try:
                send_email(
                    from_email=f"{instance.booking.business.user.username}@cleaningbizai.com",
                    to_email=instance.booking.customer.email,
                    subject="Appointment Confirmation",
                    text_content=text_content,
                    reply_to=instance.booking.business.user.email
                )
            except Exception as e:
                print(f"Error in API: {str(e)}")
                return False

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
          
            # Plain text email content
            plain_message = f"""
NEW BANK TRANSFER PAYMENT RECEIVED

Hello {business.user.first_name or business.businessName},

You have received a new bank transfer payment from {customer.firstName} {customer.lastName} for booking #{instance.invoice.booking.bookingId}.

PAYMENT DETAILS:
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
            customer = instance.invoice.booking.customer
            customer_name = f"{customer.first_name} {customer.last_name}"
            # Email subject and content
            subject = f"Payment {instance.status} - {customer_name if instance.status == 'APPROVED' else business.businessName}"
            recipient_email = customer.email if instance.status == 'APPROVED' else business.user.email
          
            # Plain text email content
            plain_message = f"""
PAYMENT {instance.status.upper()}

Hello {customer_name if instance.status == 'APPROVED' else business.businessName},

Payment has been {instance.status} for booking #{instance.invoice.booking.bookingId}.

PAYMENT DETAILS:
- Amount: ${instance.amount:.2f}
- Payment Method: Bank Transfer
- Transaction ID: {instance.transactionId or 'N/A'}
- Customer Name: {customer.first_name} {customer.last_name}
- Customer Email: {customer.email}
- Customer Phone: {customer.phone_number}
            """
            
            send_email(
                from_email=f"{business.businessName} <{business.user.email}>",
                to_email=recipient_email,
                subject=subject,
              
                text_content=plain_message,
                reply_to=business.user.email
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending payment submitted email: {str(e)}")
            return False
            
    return True

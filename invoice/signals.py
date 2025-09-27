from django.db.models.signals import post_save
from django.dispatch import receiver

from django.conf import settings
from bookings.models import Booking
from accounts.models import ApiCredential, Business
from bookings.utils import get_service_details
from datetime import datetime, timedelta
from twilio.rest import Client
from django.conf import settings
from .models import Invoice, Payment
from automation.utils import sendEmailtoClientInvoice
from django.utils import timezone
import json
from notification.services import NotificationService



@receiver(post_save, sender=Invoice)
def send_booking_confirmation_notification(sender, instance, created, **kwargs):
    """Send HTML email confirmation with invoice details when a new booking is created"""
    if created:  # Only send email for new bookings
        try:

            invoice_link = f"{settings.BASE_URL}/invoice/invoices/{instance.invoiceId}/preview/"
            details = get_service_details(instance.booking, 'customer')
          

            # Create plain text email content with invoice details
            text_content = f"""APPOINTMENT CONFIRMATION

Hello {instance.booking.customer.get_full_name()},

Your appointment with {instance.booking.business.businessName} is Pending. Please Pay to confirm your appointment. Thank you for choosing our services!

{details}

Please note that your slot is not confirmed until you make the payment.

To view your invoice and make a payment, please visit: {invoice_link}

If you have any questions or need to make changes to your appointment, please contact us.

We look forward to serving you!

{instance.booking.business.businessName} | {instance.booking.business.user.email}
            """
            try:

                from_email = f"{instance.booking.business.businessName} <{instance.booking.business.user.email}>"

                NotificationService.send_notification(
                    recipient=instance.booking.customer.user if instance.booking.customer.user else None,
                    notification_type=['email', 'sms'],
                    from_email=from_email,
                    subject="Cleaning Service Booking Confirmation",
                    content=text_content,
                   
                    sender=instance.booking.business,
                    email_to=instance.booking.customer.email,
                    sms_to=instance.booking.customer.phone_number,
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

Hello {business.businessName},

You have received a new bank transfer payment from {customer.first_name} {customer.last_name} for booking #{instance.invoice.booking.bookingId}.

PAYMENT DETAILS:
- Amount: ${instance.amount:.2f}
- Payment Method: Bank Transfer
- Transaction ID: {instance.transactionId or 'N/A'}
- Customer Name: {customer.first_name} {customer.last_name}
- Customer Email: {customer.email}
- Customer Phone: {customer.phone_number}

Please log in to your dashboard to review and approve this payment.
            """
            from_email=f"{business.businessName} <{business.user.email}>"
            
            NotificationService.send_notification(
                recipient=business.user,
                notification_type=['email',],
                from_email=from_email,
                subject=subject,
                content=plain_message,
               
                sender=business,
                email_to=recipient_email,
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
            
            NotificationService.send_notification(
                recipient=customer.user if customer.user else None,
                notification_type=['email', 'sms'],
                from_email=from_email,
                subject=subject,
                content=plain_message,
              
                sender=business,
                email_to=recipient_email,
                sms_to=customer.phone_number,
            )
            
            return True
            
        except Exception as e:
            print(f"Error sending payment submitted email: {str(e)}")
            return False
            
    return True

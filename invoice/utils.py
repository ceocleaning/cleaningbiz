
from django.utils import timezone
import threading

from notification.services import NotificationService


def create_and_start_thread(fn, args):
    try:

        thread = threading.Thread(target=fn, args=args)
        thread.daemon = True
        thread.start()

        return True
    
    except Exception as e:
        print(e)
        return False


def handle_payment_completed(payment):
    try:
        invoice = payment.invoice
        booking = invoice.booking
        business = booking.business
      

        from bookings.utils import send_jobs_to_cleaners
     
        
        create_and_start_thread(send_jobs_to_cleaners, args=(business, booking))
        create_and_start_thread(notify_business_owner_payment_completed, args=(business, payment, invoice, booking))
        create_and_start_thread(send_email_payment_completed, args=(payment,))

        
        return True
    except Exception as e:
        print(f"Error in payment completion handler: {str(e)}")
        return False
    
  

def notify_business_owner_payment_completed(business, payment, invoice, booking):
    """Send notification to business owner when payment is completed"""
    try:
        # Get business owner's email
        owner_email = business.user.email
        
        # Create email subject
        subject = f"New Payment Received - {business.businessName}"
        
        # Create email body
        body = f"""
        Hello {business.user.first_name if business.user.first_name else business.businessName},
        
        A new payment of {payment.amount} has been {payment.status} for booking #{booking.bookingId}.
        
        Payment Details:
        - Invoice ID: {invoice.invoiceId}
        - Payment ID: {payment.paymentId}
        - Amount: ${invoice.amount:.2f}
        - Payment Date: {payment.paidAt.strftime('%Y-%m-%d %H:%M:%S')}
        
        Customer Details:
        - Name: {booking.customer.get_full_name()}
        - Email: {booking.customer.email}
        - Phone: {booking.customer.phone_number}
        
        Booking Details:
        - Service: {booking.serviceType}
        - Service: Bedrooms: {booking.bedrooms} , Bathroom: {booking.bathrooms} , Area: {booking.squareFeet}
        - Date: {booking.cleaningDate.strftime('%Y-%m-%d')}
        - Time: {booking.startTime.strftime('%H:%M')} - {booking.endTime.strftime('%H:%M')}
        - Address: {booking.customer.get_address() or 'N/A'}
        
        You can view the full booking details in your dashboard.
        
        Thank you,
        CleaningBiz AI
        """
        
        # Send email using Django's built-in email function
        NotificationService.send_notification(
            recipient=business.user,
            notification_type=['email', 'sms'],
            from_email=from_email,
            subject=subject,
            content=body,
            
            sender=business,
            email_to=owner_email,
            sms_to=business.phone,
        )
        
        print(f"Payment notification email sent to business owner: {owner_email}")
        return True
    except Exception as e:
        print(f"Error sending payment notification to business owner: {str(e)}")
        return False



def send_email_payment_completed(instance):

    try:
        # Get the invoice and related booking
        invoice = instance.invoice
        booking = invoice.booking
        business = booking.business
        
       
        
        # Send custom payment confirmation email
        try:
           
            # Create email subject and content
            subject = f"Payment Confirmation - {business.businessName}"

            
            # Create plain text version
            text_body = f"""Payment Confirmation - {business.businessName}
            
                Hello {booking.customer.get_full_name()},

                We're pleased to confirm that your payment for the cleaning service with {business.businessName} has been successfully processed and is {instance.status}.

                Payment Details:
                - Invoice ID: {invoice.invoiceId}
                - Square Payment ID: {instance.squarePaymentId}
                - Amount Paid: ${invoice.amount:.2f}
                - Payment Date: {format_date(instance.paidAt)}
                - Payment Method: Card

                Appointment Details:
                - Date: {format_date(booking.cleaningDate)}
                - Time: {format_time(booking.startTime)} - {format_time(booking.endTime)}
                - Service: {booking.serviceType.title()} Cleaning

                Thank you for choosing {business.businessName}. We look forward to providing you with excellent service!

                If you have any questions or need to make changes to your appointment, please contact us.

                {business.businessName}
                {business.address}
                Phone: {business.phone} | Email: {business.user.email}
            """
            
            # Set up email parameters
            from_email = f"{business.businessName} <{business.user.email}>"
            reply_to_email = business.user.email
            recipient_email = booking.customer.email
            
            # Send email based on available configuration
            NotificationService.send_notification(
                recipient=booking.customer.user if booking.customer.user else None,
                notification_type=['email', 'sms'],
                from_email=from_email,
                subject=subject,
                content=text_body,
              
                sender=business,
                email_to=recipient_email,
                sms_to=booking.customer.phone_number,
            )
        
   
            
            print(f"[DEBUG] Payment confirmation email sent successfully for invoice {invoice.invoiceId}")
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to send payment confirmation email: {str(e)}")
            return False
            
    except Exception as e:
        print(f"[ERROR] Error in send_email_payment_completed: {str(e)}")






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
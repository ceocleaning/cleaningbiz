
from django.utils import timezone
from leadsAutomation.utils import send_email
import threading


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
        - Name: {booking.firstName} {booking.lastName}
        - Email: {booking.email}
        - Phone: {booking.phoneNumber}
        
        Booking Details:
        - Service: {booking.serviceType}
        - Service: Bedrooms: {booking.bedrooms} , Bathroom: {booking.bathrooms} , Area: {booking.squareFeet}
        - Date: {booking.cleaningDate.strftime('%Y-%m-%d')}
        - Time: {booking.startTime.strftime('%H:%M')} - {booking.endTime.strftime('%H:%M')}
        - Address: {booking.address1}, {booking.city}, {booking.stateOrProvince} {booking.zipCode}
        
        You can view the full booking details in your dashboard.
        
        Thank you,
        CleaningBiz AI
        """
        
        # Send email using Django's built-in email function
        send_email(
            subject=subject,
            html_content=body,
            from_email=f"{business.businessName} <{business.user.email}>",
            to_email=owner_email,
            reply_to=business.user.email
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
                    <p>We're pleased to confirm that your payment for the cleaning service with {business.businessName} has been successfully processed and is {instance.status}</p>
                    
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
                                <td>{format_date(instance.paidAt)}</td>
                            </tr>
                            <tr>
                                <td>Payment Method:</td>
                                <td>Card</td>
                            </tr>
                        </table>
                    </div>
                    
                    <div class="details">
                        <h3>Appointment Details:</h3>
                        <table>
                            <tr>
                                <td>Date:</td>
                                <td>{format_date(booking.cleaningDate)}</td>
                            </tr>
                            <tr>
                                <td>Time:</td>
                                <td>{format_time(booking.startTime)} - {format_time(booking.endTime)}</td>
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
            recipient_email = booking.email
            
            # Send email based on available configuration
            send_email(
                subject=subject,
                html_body=html_body,
                text_content=text_body,
                from_email=from_email,
                to_email=recipient_email,
                reply_to=reply_to_email
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
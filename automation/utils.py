from twilio.rest import Client
import uuid
from dotenv import load_dotenv
from django.core.mail import send_mail
from accounts.models import Business, ApiCredential
import os
from django.core.mail import EmailMultiAlternatives
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from django.conf import settings
from leadsAutomation.utils import send_email


load_dotenv()



def sendInvoicetoClient(recepientNumber, invoice, business):
    try:
        # Import needed modules
        from twilio.rest import Client

        # Get API credentials for the business
        apiCreds = ApiCredential.objects.get(business=business)
        
        # Check if Twilio credentials are configured
        if not apiCreds.twilioAccountSid or not apiCreds.twilioAuthToken or not apiCreds.twilioSmsNumber:
            print("Twilio credentials not configured for business")
            return False
        
        # Initialize Twilio client
        client = Client(apiCreds.twilioAccountSid, apiCreds.twilioAuthToken)

        # Generate invoice link
        invoice_link = f"{settings.BASE_URL}/invoice/invoices/{invoice.invoiceId}/preview/"

        # Create and send SMS
        message = client.messages.create(
            to=recepientNumber,
            from_=apiCreds.twilioSmsNumber,
            body=f"Hello {invoice.booking.firstName}, your appointment with {business.businessName} is confirmed! Your total is ${invoice.amount:.2f}. View and pay your invoice here: {invoice_link}"
        )
        
        print(f"SMS sent successfully to {recepientNumber}")
        return True
    except Exception as e:
        print(f"SMS sending error: {str(e)}")
        return False


def sendEmailtoClientInvoice(invoice, business):
    try:
     
        booking = invoice.booking
        invoice_link = f"{settings.BASE_URL}/invoice/invoices/{invoice.invoiceId}/preview/"
        
        # Create email subject and HTML body
        subject = f"Appointment Confirmation - {business.businessName}"
        html_body = f"""
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
                <p>Hello {booking.firstName} {booking.lastName},</p>
                <p>Your appointment with {business.businessName} has been confirmed. Thank you for choosing our services!</p>
                
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
                            <td>Service Type:</td>
                            <td>{booking.serviceType.title()} Cleaning</td>
                        </tr>
                        <tr>
                            <td>Address:</td>
                            <td>{booking.address1}, {booking.city}, {booking.stateOrProvince} {booking.zipCode}</td>
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
                <p>&copy; {business.businessName}  | {business.user.email}</p>
            </div>
        </body>
        </html>
        """
        
        # Plain text alternative
        text_body = f"""Hello {booking.firstName},

            Your appointment with {business.businessName} has been confirmed for {booking.cleaningDate.strftime('%A, %B %d, %Y')} at {booking.startTime.strftime('%I:%M %p')}.

            Service: {booking.serviceType.title()} Cleaning
            Address: {booking.address1}, {booking.city}, {booking.stateOrProvince} {booking.zipCode}
            Total Amount: ${invoice.amount:.2f}

            To view your invoice and make a payment, please visit: {invoice_link}

            Thank you for choosing {business.businessName}!
            """
        
        # Determine which email configuration to use
        from_email = f"{business.businessName} <{business.user.email}>"
        recipient_email = booking.email

        send_email(
            from_email=from_email,
            to_email=recipient_email,
            reply_to=business.user.email,
            subject=subject,
            html_body=html_body,
            text_content=text_body
        )

        return True
    except Exception as e:
        print(f"Email sending error: {str(e)}")
        return False


def generateAppoitnmentId():
    return str(uuid.uuid4())



def calculateAmount(bedrooms, bathrooms, area, service_type, businessSettingsObj):
    # Convert service type to match choices
    service_type = service_type.lower().replace(" ", "")
    
    bedroomPrice = businessSettingsObj.bedroomPrice
    bathroomPrice = businessSettingsObj.bathroomPrice
    depositFee = businessSettingsObj.depositFee
    taxPercent = businessSettingsObj.taxPercent
    sqftStandard = businessSettingsObj.sqftMultiplierStandard
    sqftDeep = businessSettingsObj.sqftMultiplierDeep
    sqftMoveinout = businessSettingsObj.sqftMultiplierMoveinout
    sqftAirbnb = businessSettingsObj.sqftMultiplierAirbnb

    if "deep" in service_type:
        base_price = sqftDeep * area

    elif "moveinmoveout" in service_type:
        base_price = sqftMoveinout * area

    elif "airbnb" in service_type:
        base_price = sqftAirbnb * area

    else:
        base_price = sqftStandard * area
    
    bathroomTotal = bathrooms * bathroomPrice
    bedroomTotal = bedrooms * bedroomPrice

    # Calculate the total amount
    total_amount = bedroomTotal + bathroomTotal + base_price + depositFee
    
    
    return total_amount


def calculateAddonsAmount(addons, addonsPrices):
    total = 0
    for key in addons:
        total += addons[key] * addonsPrices.get(key, 0)  # Use `.get()` to avoid KeyError
    return total


def format_phone_number(phone_number):
    """
    Clean and format a phone number to ensure it has the country code.
    
    Args:
        phone_number (str): The phone number to format
        
    Returns:
        str: Formatted phone number with country code (+1)
        
    Examples:
        >>> format_phone_number("(555) 555-5555")
        "+15555555555"
        >>> format_phone_number("5555555555")
        "+15555555555"
        >>> format_phone_number("+15555555555")
        "+15555555555"
    """
    try:
        # Remove all non-digit characters
        cleaned = ''.join(filter(str.isdigit, str(phone_number)))
        
        # If the number is 10 digits, add +1
        if len(cleaned) == 10:
            return f"+1{cleaned}"
        # If the number is 11 digits and starts with 1, add +
        elif len(cleaned) == 11 and cleaned.startswith('1'):
            return f"+{cleaned}"
        # If the number already has country code, return as is
        elif cleaned.startswith('+'):
            return cleaned
        # If the number is invalid, return None
        else:
            return None
    except Exception as e:
        print(f"Error formatting phone number: {str(e)}")
        return None

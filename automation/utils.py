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
            body=f"Hello {invoice.booking.customer.first_name}, your appointment with {business.businessName} is confirmed! Your total is ${invoice.amount:.2f}. View and pay your invoice here: {invoice_link}"
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

        
        # Plain text alternative
        text_body = f"""Hello {booking.customer.first_name},

            Your appointment with {business.businessName} has been confirmed for {booking.cleaningDate.strftime('%A, %B %d, %Y')} at {booking.startTime.strftime('%I:%M %p')}.

            Service: {booking.serviceType.title()} Cleaning
            Address: {booking.customer.get_address()}
            Total Amount: ${invoice.amount:.2f}

            To view your invoice and make a payment, please visit: {invoice_link}

            Thank you for choosing {business.businessName}!
            """
        
        # Determine which email configuration to use
        from_email = f"{business.businessName} <{business.user.email}>"
        recipient_email = booking.customer.email

        send_email(
            from_email=from_email,
            to_email=recipient_email,
            reply_to=business.user.email,
            subject=subject,
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
    base_price = businessSettingsObj.base_price
    bathroomPrice = businessSettingsObj.bathroomPrice
    depositFee = businessSettingsObj.depositFee
    taxPercent = businessSettingsObj.taxPercent
    sqftStandard = businessSettingsObj.sqftMultiplierStandard
    sqftDeep = businessSettingsObj.sqftMultiplierDeep
    sqftMoveinout = businessSettingsObj.sqftMultiplierMoveinout
    sqftAirbnb = businessSettingsObj.sqftMultiplierAirbnb

    if "deep" in service_type:
        sqft_price = sqftDeep * area

    elif "moveinmoveout" in service_type:
        sqft_price = sqftMoveinout * area

    elif "airbnb" in service_type:
        sqft_price = sqftAirbnb * area

    else:
        sqft_price = sqftStandard * area
    
    bathroomTotal = bathrooms * bathroomPrice
    bedroomTotal = bedrooms * bedroomPrice

    # Calculate the total amount
    total_amount = bedroomTotal + bathroomTotal + base_price + depositFee + sqft_price
    
    
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

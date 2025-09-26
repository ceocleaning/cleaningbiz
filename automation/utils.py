from twilio.rest import Client
import uuid
from dotenv import load_dotenv
from accounts.models import Business, ApiCredential, CustomAddons
from bookings.models import BookingCustomAddons
from django.conf import settings
from leadsAutomation.utils import send_email
from django.forms.models import model_to_dict

from decimal import Decimal



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



def calculateAmount(business, summary):
    # Convert service type to match choices
    serviceType = str(summary["serviceType"] or summary["service_type"] or "").lower().replace(" ", "")
    service_type = getServiceType(serviceType)
    businessSettingsObj = business.settings
    
    bedroomPrice = businessSettingsObj.bedroomPrice
    base_price = businessSettingsObj.base_price
    bathroomPrice = businessSettingsObj.bathroomPrice
    depositFee = businessSettingsObj.depositFee
    taxPercent = businessSettingsObj.taxPercent
    sqftStandard = businessSettingsObj.sqftMultiplierStandard
    sqftDeep = businessSettingsObj.sqftMultiplierDeep
    sqftMoveinout = businessSettingsObj.sqftMultiplierMoveinout
    sqftAirbnb = businessSettingsObj.sqftMultiplierAirbnb

    try:
        bedrooms = Decimal(summary["bedrooms"] or 0)
        bathrooms = Decimal(summary["bathrooms"] or 0)
        area = Decimal(summary["squareFeet"] or summary["area"] or 0)
    except ValueError:
        error_msg = "Invalid numeric values for bedrooms, bathrooms, or area"
        return {"success": False, "error": error_msg}

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
    base_total = bedroomTotal + bathroomTotal + base_price + depositFee + sqft_price
    addons_total = calculateAddonsAmount(businessSettingsObj, summary)
    customAddons = calculateCustomAddons(business, summary)

    bookingCustomAddons = customAddons.get("bookingCustomAddons", [])
    customAddonTotal = customAddons.get("customAddonTotal", 0)


    sub_total = base_total + addons_total + customAddonTotal
    tax = sub_total * (taxPercent / 100)
    total_amount = sub_total + tax




    response = {
        'base_price': base_price,
        'sqft_price': sqft_price,
        'bedroom_total': bedroomTotal,
        'bathroom_total': bathroomTotal,
        'addons_total': addons_total,
        'custom_addon_total': customAddonTotal,
        'sub_total': sub_total,
        'tax': tax,
        'tax_rate': taxPercent,
        'total_amount': total_amount,
        
        "custom_addons": {
            "note": "No Concern of AI in this Field (Internal use only)",
            "customAddonTotal": customAddonTotal,
            "bookingCustomAddons": bookingCustomAddons,
            },
    }
    
    
    return response


def calculateAddonsAmount(businessSettingsObj, summary):
    addonsPrices = {
        "dishes": businessSettingsObj.addonPriceDishes,
        "laundry": businessSettingsObj.addonPriceLaundry,
        "windows": businessSettingsObj.addonPriceWindow,
        "pets": businessSettingsObj.addonPricePets,
        "fridge": businessSettingsObj.addonPriceFridge,
        "oven": businessSettingsObj.addonPriceOven,
        "baseboards": businessSettingsObj.addonPriceBaseboard,
        "blinds": businessSettingsObj.addonPriceBlinds,
        "green": businessSettingsObj.addonPriceGreen,
        "cabinets": businessSettingsObj.addonPriceCabinets,
        "patio": businessSettingsObj.addonPricePatio,
        "garage": businessSettingsObj.addonPriceGarage
    }

    addons = {
        "dishes": int(summary.get("addonDishes", 0) or summary.get("dishes", 0)),
        "laundry": int(summary.get("addonLaundryLoads", 0) or summary.get("laundry", 0)),
        "windows": int(summary.get("addonWindowCleaning", 0) or summary.get("windows", 0)),
        "pets": int(summary.get("addonPetsCleaning", 0) or summary.get("pets", 0)),
        "fridge": int(summary.get("addonFridgeCleaning", 0) or summary.get("fridge", 0)),
        "oven": int(summary.get("addonOvenCleaning", 0) or summary.get("oven", 0)),
        "baseboards": int(summary.get("addonBaseboard", 0) or summary.get("baseboard", 0)),
        "blinds": int(summary.get("addonBlinds", 0) or summary.get("blinds", 0)),
        "green": int(summary.get("addonGreenCleaning", 0) or summary.get("green", 0)),
        "cabinets": int(summary.get("addonCabinetsCleaning", 0) or summary.get("cabinets", 0)),
        "patio": int(summary.get("addonPatioSweeping", 0) or summary.get("patio", 0)),
        "garage": int(summary.get("addonGarageSweeping", 0) or summary.get("garage", 0))
        }

    total = 0
    for key in addons:
        total += addons[key] * addonsPrices.get(key, 0)  # Use `.get()` to avoid KeyError
    return total



def calculateCustomAddons(business, summary):
    # Calculate custom addons
    customAddonsObj = CustomAddons.objects.filter(business=business)
    bookingCustomAddons = []
    customAddonTotal = 0

    for custom_addon in customAddonsObj:
        addon_data_name = custom_addon.addonDataName
        if addon_data_name and addon_data_name in summary:
            quantity = int(summary.get(addon_data_name, 0) or 0)
            if quantity > 0:
                addon_price = custom_addon.addonPrice
                addon_total = quantity * addon_price
                customAddonTotal += addon_total

                custom_addon_obj = BookingCustomAddons.objects.create(
                    addon=custom_addon,
                    qty=quantity
                )
                bookingCustomAddons.append(custom_addon_obj)
    
    response = {
        "customAddonTotal": customAddonTotal,
        "bookingCustomAddons": bookingCustomAddons
    }
    
    return response
    

def getServiceType(serviceType):
    if 'regular' in serviceType or 'standard' in serviceType:
        serviceType = 'standard'
    elif 'deep' in serviceType:
        serviceType = 'deep'
    elif 'moveinmoveout' in serviceType or 'move-in' in serviceType or 'moveout' in serviceType:
        serviceType = 'moveinmoveout'
    elif 'airbnb' in serviceType:
        serviceType = 'airbnb'
    else:
        serviceType = 'standard'
    
    return serviceType







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

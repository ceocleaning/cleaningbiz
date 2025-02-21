from twilio.rest import Client
import uuid
from dotenv import load_dotenv
from django.core.mail import send_mail
import os
load_dotenv()

accountSid = os.getenv("TWILIO_ACCOUNT_SID")
authToken = os.getenv("TWILIO_AUTH_TOKEN")
client = Client(accountSid, authToken)

def sendInvoicetoClient(recepientNumber, name, total_amount):
    try:
        message = client.messages.create(
        to=f"whatsapp:{recepientNumber}",
        from_="whatsapp:+14155238886",
        body=f"Hey {name}, Your Appointment is Confirmed!. Thank you for choosing us. Total amount to be paid is: {total_amount}")

        
        return 1
    except Exception as e:
        print(e)
        return 0


def sendEmailtoClientInvoice(email, name, total_amount):
    try:
        subject = f"Appointment Confirmed!"
        message = f"Hey {name}, Your Appointment is Confirmed!. Thank you for choosing us. Total amount to be paid is: {total_amount}"
        from_email = os.getenv("DEFAULT_FROM_EMAIL")
        recipient_list = [email]
        send_mail(subject, message, from_email, recipient_list)
        return 1
    except Exception as e:
        print(e)
        return 0


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
    total_amount = bedroomTotal + bathroomTotal + base_price
    
    
    return total_amount


def calculateAddonsAmount(addons, addonsPrices):
    total = 0
    for key in addons:
        total += addons[key] * addonsPrices.get(key, 0)  # Use `.get()` to avoid KeyError
    return total


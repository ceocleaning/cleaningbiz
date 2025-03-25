from email.utils import parsedate
from accounts.models import CustomAddons, BusinessSettings, ApiCredential, Business
from bookings.models import Booking, BookingCustomAddons
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from rest_framework.decorators import api_view
import json
import dateparser
from automation.api_views import get_cleaners_for_business, find_available_cleaner, is_slot_available, find_alternate_slots
from automation.utils import calculateAmount, calculateAddonsAmount, sendInvoicetoClient, sendEmailtoClientInvoice 
from automation.webhooks import send_booking_data
import traceback
import pytz
from .utils import convert_date_str_to_date
from .models import Chat



def calculate_total(business, client_phone_number, session_key=None):
    """Function to calculate total price based on user information and business settings.
    
    Args:
        business: The Business object for which to calculate the total
        client_phone_number: The phone number of the client
        OR
        session_key: The session key of the chat
    
    Returns:
        Dictionary with pricing details including base price, addons total, subtotal, tax, and total
        
    """

    print(f"[INFO] Calculating total for business: {business.businessName}")
    print(f"[INFO] Client phone number: {client_phone_number}")
    print(f"[INFO] Session key: {session_key}")

    try:
        if session_key:
            chat = Chat.objects.get(business=business, sessionKey=session_key)
        else:
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number, business=business)
        
        # Get business settings
        businessSettingsObj = BusinessSettings.objects.get(business=business)
        
        # Parse summary if it's a string
        if isinstance(chat.summary, str):
            try:
                summary = json.loads(chat.summary)
            except json.JSONDecodeError:
                summary = {}
        else:
            summary = chat.summary or {}
        
        # Normalize service type
        serviceType = summary.get("serviceType", "").lower().replace(" ", "")
        if 'regular' in serviceType or 'standard' in serviceType:
            serviceType = 'standard'
        elif 'deep' in serviceType:
            serviceType = 'deep'
        elif 'moveinmoveout' in serviceType or 'move-in' in serviceType or 'moveout' in serviceType:
            serviceType = 'moveinmoveout'
        elif 'airbnb' in serviceType:
            serviceType = 'airbnb'
        else:
            # Default to standard if no valid service type
            serviceType = 'standard'
        
        # Convert numeric fields if they're strings
        try:
            bedrooms = int(summary.get("bedrooms", 0) or 0)
            bathrooms = int(summary.get("bathrooms", 0) or 0)
            area = int(summary.get("squareFeet", 0) or 0)
        except ValueError:
            error_msg = "Invalid numeric values for bedrooms, bathrooms, or area"
            return {"success": False, "error": error_msg}
        
        # Calculate base price
        base_price = calculateAmount(
            bedrooms,
            bathrooms,
            area,
            serviceType,
            businessSettingsObj
        )
        
        # Process addons - extract from the data structure
        addons = {
            "dishes": int(summary.get("addonDishes", 0) or 0),
            "laundry": int(summary.get("addonLaundryLoads", 0) or 0),
            "windows": int(summary.get("addonWindowCleaning", 0) or 0),
            "pets": int(summary.get("addonPetsCleaning", 0) or 0),
            "fridge": int(summary.get("addonFridgeCleaning", 0) or 0),
            "oven": int(summary.get("addonOvenCleaning", 0) or 0),
            "baseboards": int(summary.get("addonBaseboard", 0) or 0),
            "blinds": int(summary.get("addonBlinds", 0) or 0),
            "green": int(summary.get("addonGreenCleaning", 0) or 0),
            "cabinets": int(summary.get("addonCabinetsCleaning", 0) or 0),
            "patio": int(summary.get("addonPatioSweeping", 0) or 0),
            "garage": int(summary.get("addonGarageSweeping", 0) or 0)
        }
        
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
        
        # Calculate addons total
        addons_total = calculateAddonsAmount(addons, addonsPrices)
        
        # Calculate custom addons (if needed)
        customAddonsObj = CustomAddons.objects.filter(business=business)
        customAddonTotal = 0
        
        # Process custom addons from chat summary
        for custom_addon in customAddonsObj:
            addon_data_name = custom_addon.addonDataName
            if addon_data_name and addon_data_name in summary:
                quantity = int(summary.get(addon_data_name, 0) or 0)
                if quantity > 0:
                    addon_price = custom_addon.addonPrice
                    addon_total = quantity * addon_price
                    customAddonTotal += addon_total
        
        # Calculate final amounts
        sub_total = base_price + addons_total + customAddonTotal
        tax = sub_total * (businessSettingsObj.taxPercent / 100)
        total = sub_total + tax
        
        # Return pricing details
        return {
            "success": True,
            "base_price": float(base_price),
            "addons_total": float(addons_total),
            "custom_addons_total": float(customAddonTotal),
            "sub_total": float(sub_total),
            "tax_percent": float(businessSettingsObj.taxPercent),
            "tax_amount": float(tax),
            "total": float(total),
        }
        
    except BusinessSettings.DoesNotExist:
        error_msg = f"Business settings not found for business: {business.businessName}"
        return {"success": False, "error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def get_current_time_in_chicago():
    """Get the current time in Chicago timezone with additional context"""
    try:
        chicago_tz = pytz.timezone('America/Chicago')
        current_time = datetime.now(chicago_tz)
        formatted_time = current_time.strftime('%Y-%m-%d %I:%M %p')
        day_of_week = current_time.strftime('%A')
        result = f"{formatted_time} ({day_of_week}) Central Time"
        return result
    except Exception as e:
        print(f"[ERROR] Error getting current time: {str(e)}")
        traceback.print_exc()
        return "Unable to retrieve current time due to an error."


def check_availability(business, date_string):
    """Function to check appointment availability using natural language date input.
    Accepts inputs like 'Tuesday 10 am', 'tomorrow 10 am', etc.
    Returns availability status and alternative slots if not available.
    
    Args:
        business: The Business object to check availability for
        date_string: String containing the date/time to check (natural language or ISO format)
        
    Returns:
        Dictionary with availability information or error details
    """
    try:
        if not date_string:
            return {"success": False, "error": "Missing datetime parameter"}
        
        # Use convert_date_str_to_date function
        converted_datetime = convert_date_str_to_date(date_string)
        # Strip any whitespace including newlines and then parse
        converted_datetime = converted_datetime.strip()
        
        try:
            parsed_datetime = datetime.fromisoformat(converted_datetime)
        except Exception as e:
            return {"success": False, "error": f"Invalid date format: {str(e)}"}

        # Get all active cleaners for the business
        cleaners = get_cleaners_for_business(business)
        
        # Check availability
        available_cleaners = []
        is_available, _ = is_slot_available(cleaners, parsed_datetime, available_cleaners)
        
        # Find alternative slots if not available
        alternative_slots = []
        if not is_available:
            alt_slots, _ = find_alternate_slots(cleaners, parsed_datetime, max_alternates=3)
            alternative_slots = alt_slots
        
        # Format the parsed datetime for response
        formatted_datetime = parsed_datetime.strftime('%Y-%m-%d %H:%M')
        
        # Return response
        response_data = {
            "success": True,
            "parsed_datetime": formatted_datetime,
            "available": is_available,
            "alternative_slots": alternative_slots,
            "cleaners": [{
                "id": c.id,
                "name": c.name
            } for c in available_cleaners]
        }
        return response_data
        
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def book_appointment(business, client_phone_number, session_key=None):
    """Function to book an appointment for the AI agent.
    Creates a booking in the system based on customer details collected by the AI agent.
    
    Args:
        business: The Business object for which to create the booking
        client_phone_number: The phone number of the client
        booking_data: Optional dictionary containing customer details and addon selections extracted from conversation
            Required fields: firstName, lastName, phoneNumber, address1, city, state, 
            serviceType, appointmentDateTime, bedrooms, bathrooms, squareFeet
    
    Returns:
        Dictionary with booking details or error information
    """

    print(f"[INFO] Booking appointment for business: {business.businessName}")
    print(f"[INFO] Client phone number: {client_phone_number}")
    print(f"[INFO] Session key: {session_key}")

    try:
        if session_key:
            chat = Chat.objects.get(business=business, sessionKey=session_key)
        else:
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number, business=business)
        
        # Parse summary if it's a string
        if isinstance(chat.summary, str):
            try:
                chat_summary = json.loads(chat.summary)
            except json.JSONDecodeError:
                chat_summary = {}
        else:
            chat_summary = chat.summary or {}
        
        # Use provided booking_data if available, otherwise use chat.summary
        data = chat_summary
        
        # Validate required fields
        required_fields = ["firstName", "lastName", "phoneNumber", "address1", "city", "state", 
                          "serviceType", "appointmentDateTime", "bedrooms", "bathrooms", "squareFeet"]
        
        missing_fields = [field for field in required_fields if field not in data or not data.get(field)]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            return {"success": False, "error": error_msg}
        
        # Get business settings
        businessSettingsObj = BusinessSettings.objects.get(business=business)
        
        # Normalize service type
        serviceType = data["serviceType"].lower().replace(" ", "")
        if 'regular' in serviceType or 'standard' in serviceType:
            serviceType = 'standard'
        elif 'deep' in serviceType:
            serviceType = 'deep'
        elif 'moveinmoveout' in serviceType or 'move-in' in serviceType or 'moveout' in serviceType:
            serviceType = 'moveinmoveout'
        elif 'airbnb' in serviceType:
            serviceType = 'airbnb'
        
        # Convert numeric fields if they're strings
        try:
            bedrooms = int(data["bedrooms"]) if data["bedrooms"] else 0
            bathrooms = int(data["bathrooms"]) if data["bathrooms"] else 0
            area = int(data["squareFeet"]) if data["squareFeet"] else 0
        except ValueError:
            error_msg = "Invalid numeric values for bedrooms, bathrooms, or area"
            return {"success": False, "error": error_msg}
        
        # Calculate base price
        calculateTotal = calculateAmount(
            bedrooms,
            bathrooms,
            area,
            serviceType,
            businessSettingsObj
        )
        
        # Process addons - extract from the data structure
        addons = {
            "dishes": int(data.get("addonDishes", 0) or 0),
            "laundry": int(data.get("addonLaundryLoads", 0) or 0),
            "windows": int(data.get("addonWindowCleaning", 0) or 0),
            "pets": int(data.get("addonPetsCleaning", 0) or 0),
            "fridge": int(data.get("addonFridgeCleaning", 0) or 0),
            "oven": int(data.get("addonOvenCleaning", 0) or 0),
            "baseboards": int(data.get("addonBaseboard", 0) or 0),
            "blinds": int(data.get("addonBlinds", 0) or 0),
            "green": int(data.get("addonGreenCleaning", 0) or 0),
            "cabinets": int(data.get("addonCabinetsCleaning", 0) or 0),
            "patio": int(data.get("addonPatioSweeping", 0) or 0),
            "garage": int(data.get("addonGarageSweeping", 0) or 0)
        }
        
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
        
        # Calculate custom addons
        customAddonsObj = CustomAddons.objects.filter(business=business)
        bookingCustomAddons = []
        customAddonTotal = 0
        
        # We'll assume custom addons are not handled through the AI agent for now
        # This can be extended later if needed
        
        # Calculate final amounts
        addons_result = calculateAddonsAmount(addons, addonsPrices)
        sub_total = calculateTotal + addons_result + customAddonTotal
        tax = sub_total * (businessSettingsObj.taxPercent / 100)
        total = sub_total + tax
        
        # Parse appointment datetime
        try:
            # Try different date formats
            converted_datetime = convert_date_str_to_date(data["appointmentDateTime"])
            # Strip any whitespace including newlines and then parse
            converted_datetime = converted_datetime.strip()
            cleaningDateTime = datetime.fromisoformat(converted_datetime)
            
            cleaningDate = cleaningDateTime.date()
            startTime = cleaningDateTime.time()
            endTime = (cleaningDateTime + timedelta(hours=1)).time()
        except Exception as e:
            error_msg = f"Invalid appointment date/time format: {str(e)}"
            return {"success": False, "error": error_msg}
        
        # Find available cleaner for the booking
        cleaners = get_cleaners_for_business(business)
        available_cleaner = find_available_cleaner(cleaners, cleaningDateTime)
        
        if not available_cleaner:
            error_msg = "No cleaners available for the requested time"
            return {"success": False, "error": error_msg}
        
        # Create booking
        newBooking = Booking.objects.create(
            business=business,
            firstName=data["firstName"],
            lastName=data["lastName"],
            email=data.get("email", ""),
            phoneNumber=data["phoneNumber"],
            address1=data["address1"],
            address2=data.get("address2", ""),
            city=data["city"],
            stateOrProvince=data["state"],
            zipCode=data.get("zipCode", ""),  # Make zipCode optional
            cleaningDate=cleaningDate,
            startTime=startTime,
            endTime=endTime,
            serviceType=serviceType,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            squareFeet=area,
            otherRequests=data.get("additionalNotes", ""),
            totalPrice=total,
            tax=tax,
            addonDishes=addons["dishes"],
            addonLaundryLoads=addons["laundry"],
            addonWindowCleaning=addons["windows"],
            addonPetsCleaning=addons["pets"],
            addonFridgeCleaning=addons["fridge"],
            addonOvenCleaning=addons["oven"],
            addonBaseboard=addons["baseboards"],
            addonBlinds=addons["blinds"],
            addonGreenCleaning=addons["green"],
            addonCabinetsCleaning=addons["cabinets"],
            addonPatioSweeping=addons["patio"],
            addonGarageSweeping=addons["garage"],
            cleaner=available_cleaner,
        )
        
        # Add custom addons
        if bookingCustomAddons:
            newBooking.customAddons.set(bookingCustomAddons)
            newBooking.save()
        
        # Send booking data to integration if needed
        send_booking_data(newBooking)
        
        # Return success response
        return {
            "success": True,
            "booking_id": newBooking.bookingId,
            "message": "Appointment booked successfully"
        }
        
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}

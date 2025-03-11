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
from automation.utils import calculateAmount, calculateAddonsAmount
from automation.webhooks import send_booking_data
import traceback
import pytz
from .utils import convert_date_str_to_date
from .models import Chat






def get_current_time_in_chicago():
    """Get the current time in Chicago timezone with additional context"""
    try:
        chicago_tz = pytz.timezone('America/Chicago')
        current_time = datetime.now(chicago_tz)
        formatted_time = current_time.strftime('%Y-%m-%d %I:%M %p')
        day_of_week = current_time.strftime('%A')
        return f"{formatted_time} ({day_of_week}) Central Time"
    except Exception as e:
        print(f"Error getting current time: {str(e)}")
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
        print(f"\n[DEBUG] check_availability called for business: {business.businessName}")
        print(f"[DEBUG] Received datetime string: {date_string}")
        
        if not date_string:
            print("[DEBUG] Missing datetime parameter")
            return {"success": False, "error": "Missing datetime parameter"}
        
        # Use convert_date_str_to_date function
        converted_datetime = convert_date_str_to_date(date_string)
        # Strip any whitespace including newlines and then parse
        converted_datetime = converted_datetime.strip()
        parsed_datetime = datetime.fromisoformat(converted_datetime)

        print(f"[DEBUG] Converted datetime: {parsed_datetime}")
        
        # Get all active cleaners for the business
        cleaners = get_cleaners_for_business(business)
        print(f"[DEBUG] Found {len(cleaners)} active cleaners")
        
        # Check availability
        available_cleaners = []
        print(f"[DEBUG] Checking availability for {parsed_datetime}")
        is_available, _ = is_slot_available(cleaners, parsed_datetime, available_cleaners)
        print(f"[DEBUG] Availability result: {is_available}, Found {len(available_cleaners)} available cleaners")
        
        # Find alternative slots if not available
        alternative_slots = []
        if not is_available:
            print("[DEBUG] Not available, finding alternative slots")
            alt_slots, _ = find_alternate_slots(cleaners, parsed_datetime, max_alternates=3)
            alternative_slots = alt_slots
            print(f"[DEBUG] Found {len(alternative_slots)} alternative slots")
        
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
        print(f"[DEBUG] Returning response: {response_data}")
        return response_data
        
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {str(e)}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}




def book_appointment(business, client_phone_number):
    """Function to book an appointment for the AI agent.
    Creates a booking in the system based on customer details collected by the AI agent.
    
    Args:
        business: The Business object for which to create the booking
        data: Dictionary containing customer details and addon selections extracted from conversation
            Required fields: firstName, lastName, phoneNumber, address1, city, state, 
            serviceType, appointmentDateTime, bedrooms, bathrooms, area
    
    Returns:
        Dictionary with booking details or error information
    """
    try:
        print("\n[DEBUG] book_appointment called for business:", business.businessName)
        print(f"[DEBUG] Args: {client_phone_number}")

        chat = Chat.objects.get(clientPhoneNumber=client_phone_number)
        data = chat.summary
        print(data)
        
        # Validate required fields
        required_fields = ["firstName", "lastName", "phoneNumber", "address1", "city", "state", 
                          "serviceType", "appointmentDateTime", "bedrooms", "bathrooms", "squareFeet"]
        
        missing_fields = [field for field in required_fields if field not in data or not data.get(field)]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(f"[DEBUG] {error_msg}")
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
            print(f"[DEBUG] {error_msg}")
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
            print(f"[DEBUG] {error_msg}")
            return {"success": False, "error": error_msg}
        
        # Find available cleaner for the booking
        cleaners = get_cleaners_for_business(business)
        available_cleaner = find_available_cleaner(cleaners, cleaningDateTime)
        
        if not available_cleaner:
            error_msg = "No cleaners available for the requested time"
            print(f"[DEBUG] {error_msg}")
            return {"success": False, "error": error_msg}
        
        # Create booking
        print("[DEBUG] Creating booking...")
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
        print(f"[DEBUG] Unexpected error in book_appointment: {str(e)}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}

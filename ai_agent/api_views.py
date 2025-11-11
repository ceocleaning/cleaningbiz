from accounts.models import BusinessSettings, Business
from bookings.models import Booking
from datetime import datetime, timedelta
import json
from automation.api_views import get_cleaners_for_business, find_available_cleaner, is_slot_available, find_alternate_slots
from automation.utils import calculateAmount, getServiceType
from django.utils import timezone
import traceback
import pytz
from .models import Chat
from accounts.timezone_utils import parse_business_datetime, convert_from_utc
from customer.utils import create_customer
from bookings.utils import get_service_details
from decimal import Decimal

from notification.services import NotificationService


def calculate_total(business, client_phone_number=None, session_key=None):
    try:
        if session_key:
            chat = Chat.objects.get(business=business, sessionKey=session_key)
        elif client_phone_number:
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number, business=business)

        # Parse summary if it's a string
        if isinstance(chat.summary, str):
            try:
                summary = json.loads(chat.summary)
            except json.JSONDecodeError:
                summary = {}
        else:
            summary = chat.summary or {}

        # Try to get customer by email to check for custom pricing
        customer = None
        if summary.get("email"):
            from customer.models import Customer
            customer = Customer.objects.filter(email=summary.get("email")).first()

        # Calculate price with customer-specific pricing if available
        amount_calculation = calculateAmount(
            business,
            summary,
            customer=customer
        )

        return {
            "success": True,
            "result": amount_calculation
        }
        
    except BusinessSettings.DoesNotExist:
        error_msg = f"Business settings not found for business: {business.businessName}"
        return {"success": False, "error": error_msg}
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def get_current_time(business=None):
    """Get the current time in business timezone with additional context"""
    try:
        # Get business timezone if available, otherwise default to Chicago
        timezone_name = 'America/Chicago'
        timezone_display = 'Central Time'
        
        if business:
            try:
                timezone_name = business.timezone
                timezone_obj = pytz.timezone(timezone_name)
                timezone_display = timezone_obj.localize(datetime.now()).tzname()
            except Exception as e:
                print(f"Error getting business timezone: {str(e)}")
        
        # Get current time in the specified timezone
        tz = pytz.timezone(timezone_name)
        current_time = datetime.now(tz)
        formatted_time = current_time.strftime('%Y-%m-%d %I:%M %p')
        day_of_week = current_time.strftime('%A')
        result = f"{formatted_time} ({day_of_week}) {timezone_display}"
        return result
    except Exception as e:
        print(f"[ERROR] Error getting current time: {str(e)}")
        traceback.print_exc()
        return "Unable to retrieve current time due to an error."


def check_availability(business, date_string):
    try:
        if not date_string:
            return {"success": False, "error": "Missing datetime parameter"}
        
        res = parse_business_datetime(date_string, business)
        print(res)


        cleaners = get_cleaners_for_business(business, assignment_check_null=True)
        
        is_available, _ = is_slot_available(cleaners, res["data"]["utc_datetime"])
        
        alternative_slots = []
        if not is_available:
            alt_slots, _ = find_alternate_slots(cleaners, res["data"]["utc_datetime"], max_alternates=3)
            alternative_slots = alt_slots
        
        formatted_datetime = res["data"]["utc_datetime"].strftime('%Y-%m-%d %H:%M')
        
        response_data = {
            "success": True,
            "parsed_datetime": formatted_datetime,
            "available": is_available,
            "alternative_slots": alternative_slots,
        }
        return response_data
        
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def book_appointment(business, client_phone_number=None, session_key=None):
    try:
        if session_key:
            chat = Chat.objects.get(business=business, sessionKey=session_key)
        elif client_phone_number:
            chat = Chat.objects.get(clientPhoneNumber=client_phone_number, business=business)
        
       
        
        if isinstance(chat.summary, str):
            try:
                chat_summary = json.loads(chat.summary)
            except json.JSONDecodeError as e:
                chat_summary = {}
        else:
            chat_summary = chat.summary or {}
        
        # Use provided booking_data if available, otherwise use chat.summary
        data = chat_summary
        
        # Validate required fields
        required_fields = ["firstName", "phoneNumber", "address1", "city", "state", 
                          "serviceType", "appointmentDateTime", "bedrooms", "bathrooms", "squareFeet"]
        
       
        
        missing_fields = [field for field in required_fields if field not in data or not data.get(field)]
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
          
            return {"success": False, "error": error_msg}
        
        
        # Normalize service type
        serviceType = data["serviceType"].lower().replace(" ", "")
        serviceType = getServiceType(serviceType)
        
        
        
        # Convert numeric fields if they're strings
        try:
            bedrooms = Decimal(data["bedrooms"]) if data["bedrooms"] else 0
            bathrooms = Decimal(data["bathrooms"]) if data["bathrooms"] else 0
            area = Decimal(data["squareFeet"]) if data["squareFeet"] else 0
           
        except ValueError as e:
            error_msg = f"Invalid numeric values for bedrooms, bathrooms, or area: {str(e)}"
            
            return {"success": False, "error": error_msg}
        
        res = parse_business_datetime(data["appointmentDateTime"], business, to_utc=True, duration_hours=1)

        
        # Find available cleaner for the booking
        cleaners = get_cleaners_for_business(business, assignment_check_null=True)
        available_cleaner = find_available_cleaner(cleaners, res["data"]["utc_datetime"])
                
        if not available_cleaner:
            error_msg = "No cleaners available for the requested time"
            return {"success": False, "error": error_msg}
        
        customer = create_customer(data, business)
        
        # Calculate price with customer-specific pricing if available
        calculateTotal = calculateAmount(business, data, customer=customer)
        
        # Convert Decimal values to float for JSON serialization
        def convert_decimals_to_float(obj):
            from django.db import models
            if isinstance(obj, dict):
                # Filter out model instances from dictionaries
                result = {}
                for k, v in obj.items():
                    converted = convert_decimals_to_float(v)
                    # Only include if not a model instance
                    if not isinstance(v, models.Model):
                        result[k] = converted
                return result
            elif isinstance(obj, list):
                # Filter out model instances from lists
                return [convert_decimals_to_float(item) for item in obj if not isinstance(item, models.Model)]
            elif isinstance(obj, Decimal):
                return float(obj)
            elif isinstance(obj, models.Model):
                # Skip Django model instances - don't include them in JSON
                return None
            return obj
        
        # Create a copy of calculateTotal and remove bookingCustomAddons before conversion
        pricing_data = calculateTotal.copy()
        if 'custom_addons' in pricing_data and isinstance(pricing_data['custom_addons'], dict):
            # Keep the custom_addons dict but remove the bookingCustomAddons list
            pricing_data['custom_addons'] = {
                k: v for k, v in pricing_data['custom_addons'].items() 
                if k != 'bookingCustomAddons'
            }
        
        pricing_snapshot = convert_decimals_to_float(pricing_data)
        
        # Create booking with customer reference
        newBooking = Booking(
            business=business,
            customer=customer,
            cleaningDate=res["data"]["utc_date"],
            startTime=res["data"]["utc_start_time"],
            endTime=res["data"]["utc_end_time"],
            serviceType=serviceType,
            bedrooms=bedrooms,
            bathrooms=bathrooms,
            squareFeet=area,
            otherRequests=data.get("otherRequests", ""),
            totalPrice=calculateTotal.get("total_amount", 0),
            tax=calculateTotal.get("tax", 0),
            used_custom_pricing=calculateTotal.get("used_custom_pricing", False),
            pricing_snapshot=pricing_snapshot,
            addonDishes=int(data.get("addonDishes", 0) or 0),
            addonLaundryLoads=int(data.get("addonLaundryLoads", 0) or 0),
            addonWindowCleaning=int(data.get("addonWindowCleaning", 0) or 0),
            addonPetsCleaning=int(data.get("addonPetsCleaning", 0) or 0),
            addonFridgeCleaning=int(data.get("addonFridgeCleaning", 0) or 0),
            addonOvenCleaning=int(data.get("addonOvenCleaning", 0) or 0),
            addonBaseboard= int(data.get("addonBaseboard", 0) or 0),
            addonBlinds=int(data.get("addonBlinds", 0) or 0),
            addonGreenCleaning=int(data.get("addonGreenCleaning", 0) or 0),
            addonCabinetsCleaning=int(data.get("addonCabinetsCleaning", 0) or 0),
            addonPatioSweeping=int(data.get("addonPatioSweeping", 0) or 0),
            addonGarageSweeping=int(data.get("addonGarageSweeping", 0) or 0),
            will_someone_be_home=data.get("willSomeoneBeHome", "").lower() in ['yes', 'true', '1'],
            key_location=data.get("keyLocation", ""),
        )

        newBooking.save()
        
        # Add custom addons from calculateTotal (already created in calculateCustomAddonsWithCustomPricing)
        bookingCustomAddons = calculateTotal.get("custom_addons", {}).get("bookingCustomAddons")
        if bookingCustomAddons:
            newBooking.customAddons.set(bookingCustomAddons)
            print(f"[DEBUG] Added {len(bookingCustomAddons)} custom addon(s) to booking {newBooking.bookingId}")
            newBooking.save()
        

        import threading 
        from automation.webhooks import send_booking_data
        webhook_thread = threading.Thread(target=send_booking_data, args=(newBooking,))
        webhook_thread.daemon = True
        webhook_thread.start()
        
        # Update chat summary with booking ID
        try:
            updated_summary = chat.summary.copy() if isinstance(chat.summary, dict) else {}
            updated_summary['bookingId'] = newBooking.bookingId
            chat.summary = updated_summary
            chat.save()
        except Exception as e:
            print(f"[ERROR] Failed to update chat summary with booking ID: {str(e)}")
            
      
        
        booking_details = {
            "bookingId": newBooking.bookingId,
            "cleaningDate": newBooking.cleaningDate.strftime('%Y-%m-%d'),
            "startTime": convert_from_utc(res["data"]["utc_datetime"], business.timezone).strftime('%H:%M'),
            "serviceType": newBooking.serviceType,
            "totalPrice": float(newBooking.totalPrice),
            "customer_name": f"{newBooking.customer.first_name} {newBooking.customer.last_name}"
        }

        # Return success response
        return {
            "success": True,
            "booking_id": newBooking.bookingId,
            "message": "Appointment booked successfully",
            "data": booking_details,
        }
        
    except Exception as e:
        print(f"[ERROR] Exception in book_appointment: {str(e)}")
        traceback.print_exc()
        return {"success": False, "error": str(e)}


def reschedule_appointment(booking_id, new_date_time, reason=None):
    try:
        booking = Booking.objects.get(bookingId=booking_id)
        cleaners = get_cleaners_for_business(booking.business)

        res = parse_business_datetime(new_date_time, booking.business)
    
        # Check availability using UTC datetime
        is_available, _ = is_slot_available(cleaners, res['data']['utc_datetime'])
        
        alternative_slots = []
        if not is_available:
            alt_slots, _ = find_alternate_slots(cleaners, res['data']['utc_datetime'], max_alternates=3)
            alternative_slots = alt_slots

            return {
                "success": False,
                "error": "The requested time is not available",
                "alternative_slots": alternative_slots
            }
        
        # Save UTC date and times to booking
        booking.cleaningDate = res['data']['utc_date']
        booking.startTime = res['data']['utc_start_time']
        booking.endTime = res['data']['utc_end_time']
        if reason:
            booking.rescheduled_reason = reason
        booking.rescheduled_at = timezone.now()
        booking.save()
        
       
        email_sent = send_reschedule_email(booking, res['data']['local_datetime'])
        
        return {
            "success": True,
            "message": "Appointment rescheduled successfully",
            "email_sent": email_sent,
        }
        
    
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}



def cancel_appointment(booking_id, reason=None):
    try:
        
        booking = Booking.objects.get(bookingId=booking_id)
        
        # Store booking details before cancellation for email
        booking_copy = booking
        
        # Mark as cancelled
        booking.cancelled_at = timezone.now()
        if reason:
            booking.cancelled_reason = reason
        booking.save()
        
        
        email_sent = send_cancel_email(booking_copy)
    
        return {
            "success": True,
            "message": "Appointment cancelled successfully",
            "email_sent": email_sent
        }
    
    except Exception as e:
        traceback.print_exc()
        return {"success": False, "error": str(e)}



def send_reschedule_email(booking, new_date_time):
    try:
        # Get business and SMTP configuration
        business = booking.business
        
        # Set up email parameters
        from_name = f"{business.businessName} <{business.user.email}>"
        recipient_email = booking.customer.email
        
        # Check if we have a recipient email
        if not recipient_email:
            print(f"[WARNING] No email address for booking {booking.bookingId}")
            return False
            
        # Create email content
        subject = f"Your Appointment Has Been Rescheduled - {business.businessName}"
        
        # Convert UTC date and time to business timezone for display
        # Get business timezone
        business_timezone = business.get_timezone()
        
        # Create datetime objects in UTC
        utc_datetime = datetime.combine(booking.cleaningDate, booking.startTime)
        utc_datetime = pytz.utc.localize(utc_datetime) if utc_datetime.tzinfo is None else utc_datetime
        
        # Convert to business timezone
        local_datetime = utc_datetime.astimezone(business_timezone)
        
        # Format the local date and time for display
        appointment_date = local_datetime.strftime("%A, %B %d, %Y")
        appointment_time = local_datetime.strftime("%I:%M %p")

        details = get_service_details(booking, 'customer')
        

        
        # Create plain text version
        text_content = f"""
        Dear {booking.customer.first_name},
        Your appointment with {business.businessName} has been successfully rescheduled.

        {details}
        

        New Date and Time: {new_date_time.strftime('%A, %B %d, %Y %I:%M %p')}

        If you need to make any changes to your appointment, please contact us at {business.user.email}.

        Thank you for choosing {business.businessName}!
        """

      
        NotificationService.send_notification(
            recipient=booking.customer.user if booking.customer.user else None,
            notification_type=['email', 'sms'],
            from_email=from_name,
            subject=subject,
            content=text_content,
            sender=business,
            email_to=recipient_email,
            sms_to=booking.customer.phone_number,
        )

        return True
    
       

            
    except Exception as e:
        print(f"[ERROR] Failed to send rescheduling email: {str(e)}")
        return False


def send_cancel_email(booking):
    try:
        # Get business and SMTP configuration
        business = booking.business
        
        # Set up email parameters
        from_name = f"{business.businessName} <{business.user.email}>"
        recipient_email = booking.customer.email
        
        # Check if we have a recipient email
        if not recipient_email:
            print(f"[WARNING] No email address for booking {booking.bookingId}")
            return False
            
        # Create email content
        subject = f"Your Appointment Has Been Canceled - {business.businessName}"
        
        # Convert UTC date and time to business timezone for display
        # Get business timezone
        business_timezone = business.get_timezone()
        
        # Create datetime objects in UTC
        utc_datetime = datetime.combine(booking.cleaningDate, booking.startTime)
        utc_datetime = pytz.utc.localize(utc_datetime) if utc_datetime.tzinfo is None else utc_datetime
        
        # Convert to business timezone
        local_datetime = utc_datetime.astimezone(business_timezone)
        
        # Format the local date and time for display
        appointment_date = local_datetime.strftime("%A, %B %d, %Y")
        appointment_time = local_datetime.strftime("%I:%M %p")


        details = get_service_details(booking, 'customer')
        

        
        # Create plain text version
        text_content = f"""
        Dear {booking.customer.get_full_name()},
        Your appointment with {business.businessName} has been canceled.
        
        {details}
        
        Thank you for choosing {business.businessName}!
        """
        
        NotificationService.send_notification(
            recipient=booking.customer.user if booking.customer.user else None,
            notification_type=['email', 'sms'],
            from_email=from_name,
            subject=subject,
            content=text_content,
           
            sender=business,
            email_to=recipient_email,
            sms_to=booking.customer.phone_number,
        )

        return True

    except Exception as e:
        print(f"[ERROR] Failed to send cancellation email: {str(e)}")
        return False
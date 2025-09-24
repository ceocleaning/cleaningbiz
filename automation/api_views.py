import os
import json
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import make_aware, is_naive
from retell import Retell
from accounts.models import Business, ApiCredential, BusinessSettings, CustomAddons
from bookings.models import Booking, BookingCustomAddons
from invoice.models import Invoice
from .models import Cleaners, CleanerAvailability
from django.conf import settings
from leadsAutomation.utils import send_email
from customer.models import Customer
import threading
from accounts.timezone_utils import parse_business_datetime
from customer.utils import create_customer


from .utils import calculateAmount, getServiceType
import pytz
import traceback

# Function to get available cleaners for a business
def get_cleaners_for_business(business, exclude_ids=None, assignment_check_null=False):
    
    all_cleaners = Cleaners.objects.filter(business=business)
    
    active_cleaners = all_cleaners.filter(isActive=True)
    
    # Apply available filter
    available_cleaners = active_cleaners
    
    cleaners = available_cleaners
    
    # Apply rating filter if needed
    if business.job_assignment == 'high_rated' and not assignment_check_null:
        max_rating = max(cleaners.values_list('rating', flat=True))
        high_rated_cleaners = cleaners.filter(rating__gte=max_rating)
 
        cleaners = high_rated_cleaners
    
    # Apply exclusion filter if needed
    if exclude_ids:
        filtered_cleaners = cleaners.exclude(id__in=exclude_ids)
        
        cleaners = filtered_cleaners
    

    return cleaners

# Function to get cleaner availabilities for a specific day
def get_cleaner_availabilities(cleaner, date_to_check):
    # Ensure date_to_check is a datetime object
    from datetime import datetime
    if isinstance(date_to_check, str):
        try:
            # Try to parse the string as a datetime
            date_to_check = datetime.strptime(date_to_check, "%Y-%m-%d %H:%M")
        except ValueError:
            # If it fails, it might be just a date string
            try:
                date_to_check = datetime.strptime(date_to_check, "%Y-%m-%d")
            except ValueError:
                # If all parsing fails, return None
                return None
    
    specific_availability = CleanerAvailability.objects.filter(
        cleaner=cleaner,
        availability_type='specific',
        specific_date=date_to_check.date()
    ).first()
    
    if specific_availability:
        # If it's an off day, return None
        if specific_availability.offDay:
            return None
        return specific_availability
    
    # Fall back to weekly schedule
    week_day = date_to_check.strftime('%A')
    weekly_availability = CleanerAvailability.objects.filter(
        cleaner=cleaner,
        availability_type='weekly',
        dayOfWeek=week_day
    ).first()
    
    # If it's an off day in the weekly schedule, return None
    if weekly_availability and weekly_availability.offDay:
        return None
    
    return weekly_availability

# Function to check if a timeslot is available
def is_slot_available(cleaners, time_to_check, available_cleaners=None):
    if available_cleaners is None:
        available_cleaners = []
    
    available_cleaners.clear()
    
    logs = []
    logs.append(f"Checking availability for {time_to_check.strftime('%Y-%m-%d %H:%M')}")
    logs.append(f"Found {len(cleaners)} cleaners to check")
    
    for cleaner in cleaners:
        logs.append(f"\nChecking cleaner: {cleaner.name}")
        
        # Get availability for this date/time
        cleaner_availability = get_cleaner_availabilities(cleaner, time_to_check)
        
        if cleaner_availability is None:
            logs.append(f"❌ {cleaner.name} doesn't work on {time_to_check.strftime('%A')} {time_to_check.strftime('%Y-%m-%d')}")
            continue

        # Check if time is within cleaner's working hours
        if not (cleaner_availability.startTime <= time_to_check.time() <= cleaner_availability.endTime):
            logs.append(f"❌ Time {time_to_check.strftime('%H:%M')} is outside {cleaner.name}'s working hours ({cleaner_availability.startTime.strftime('%H:%M')} - {cleaner_availability.endTime.strftime('%H:%M')})")
            continue

        # Check for conflicting bookings
        conflicting_booking = Booking.objects.filter(
            cleaner=cleaner,
            cleaningDate=time_to_check.date(),
            startTime__lte=time_to_check.time(),
            endTime__gt=time_to_check.time()
        ).exists()

        if conflicting_booking:
            logs.append(f"❌ {cleaner.name} has a conflicting booking at this time")
            continue

        # If we get here, the cleaner is available
        logs.append(f"✅ {cleaner.name} is available!")
        available_cleaners.append(cleaner)

    if len(available_cleaners) > 0:
        logs.append(f"\n✨ Found {len(available_cleaners)} available cleaner(s)!")
    else:
        logs.append("\n❌ No cleaners available for this time slot")

    # Return True if we found any available cleaners, along with the logs
    return len(available_cleaners) > 0, logs


# FUnction to Find All Available Cleaners for a given time slot
def find_all_available_cleaners(cleaners, time_to_check):
    print(f"Finding available cleaners at time: {time_to_check}")
    print(f"Number of cleaners to check: {cleaners.count() if hasattr(cleaners, 'count') else len(cleaners)}")
    
    available_cleaners = []
    for cleaner in cleaners:
        print(f"Checking availability for cleaner ID: {cleaner.id}")
        availability = get_cleaner_availabilities(cleaner, time_to_check)
        print(f"Cleaner {cleaner.id} availability result: {availability}")
        
        if availability is None:
            print(f"Cleaner {cleaner.id} is not available at {time_to_check}")
            continue
        
        print(f"Cleaner {cleaner.id} is available at {time_to_check}")
        available_cleaners.append(cleaner.id)
    
    print(f"Total available cleaners found: {len(available_cleaners)}")
    return available_cleaners





# Function to find an available cleaner
def find_available_cleaner(cleaners, time_to_check):
    """Find the best available cleaner for the given time slot based on rating."""
    print("\nFinding available cleaner for time:", time_to_check)
    print("Number of cleaners to check:", len(cleaners))
    
    available_cleaners = []
    
    for cleaner in cleaners:
        print("\nChecking cleaner:", cleaner.name)
        
        # Check cleaner's availability for the requested date/time
        availability = get_cleaner_availabilities(cleaner, time_to_check)

        if not availability:
            print(f"No availability found for {cleaner.name} on {time_to_check.strftime('%A')} {time_to_check.strftime('%Y-%m-%d')}")
            continue  # Skip if the cleaner is not available that day

        print(f"Found availability for {cleaner.name}: {availability.startTime} - {availability.endTime}")

        if not (availability.startTime <= time_to_check.time() <= availability.endTime):
            print(f"Time {time_to_check.time()} is outside {cleaner.name}'s working hours")
            continue

        # Check for conflicting bookings
        conflicting_booking = Booking.objects.filter(
            cleaner=cleaner,
            cleaningDate=time_to_check.date(),
            startTime__lte=time_to_check.time(),
            endTime__gte=time_to_check.time()
        ).exists()

        if conflicting_booking:
            print(f"{cleaner.name} has a conflicting booking")
            continue

        print(f"✓ {cleaner.name} is available (Rating: {cleaner.rating}/5)")
        available_cleaners.append(cleaner)

    if not available_cleaners:
        print("No available cleaners found for this time slot")
        return None
    
    # Sort available cleaners by rating (highest first)
    best_cleaner = max(available_cleaners, key=lambda c: c.rating)
    print(f"Selected best cleaner: {best_cleaner.name} with rating {best_cleaner.rating}/5")
    return best_cleaner

# Function to find alternate available slots
def find_alternate_slots(cleaners, datetimeToCheck, max_alternates=3):
    """
    Find up to `max_alternates` alternate available timeslots.
    If no slots exist on the requested day, search the next available day.
    
    Note: datetimeToCheck should already be in the business's timezone.
    """
    logs = []
    logs.append(f"\nLooking for alternate slots after {datetimeToCheck.strftime('%Y-%m-%d %H:%M')}")
    
    alternate_slots = []
    time_increment = timedelta(hours=1)
    max_attempts = 24  # Increased to search more slots
    
    # Start from the next hour
    next_time = datetimeToCheck.replace(minute=0, second=0, microsecond=0) + time_increment
    
    # Define business hours (9 AM to 5 PM by default)
    business_start_hour = 9
    business_end_hour = 17
    
    # Track days we've already checked to avoid checking the same day multiple times
    checked_days = set()
    
    while len(alternate_slots) < max_alternates and max_attempts > 0:
        available_cleaners = []
        
        # Skip times outside of business hours (9 AM - 5 PM)
        current_hour = next_time.hour
        current_date = next_time.date()
        date_str = current_date.strftime('%Y-%m-%d')
        
        # If we've already checked this day and found no slots, skip to next day
        if date_str in checked_days and current_hour >= business_end_hour:
            # Move to 9 AM the next day
            next_time = (next_time + timedelta(days=1)).replace(hour=business_start_hour, minute=0, second=0, microsecond=0)
            continue
        
        # If outside business hours, adjust time
        if current_hour < business_start_hour:
            # Move to start of business hours
            next_time = next_time.replace(hour=business_start_hour, minute=0, second=0, microsecond=0)
        elif current_hour >= business_end_hour:
            # Move to start of business hours the next day
            next_time = (next_time + timedelta(days=1)).replace(hour=business_start_hour, minute=0, second=0, microsecond=0)
            
        # Check if this slot is available
        is_available, slot_logs = is_slot_available(cleaners, next_time, available_cleaners)
        logs.extend(slot_logs)
        
        # Add the date to checked days
        checked_days.add(date_str)
        
        if is_available and len(available_cleaners) > 0:
            # Format the datetime in ISO format for consistency
            alternate_slots.append(next_time.strftime("%Y-%m-%d %I:%M %p"))
            logs.append(f"✅ Found alternate slot at {next_time.strftime('%Y-%m-%d %I:%M %p')} with {len(available_cleaners)} cleaner(s)")
        
        # Move to the next time slot
        next_time += time_increment
        max_attempts -= 1

    if len(alternate_slots) == 0:
        logs.append("❌ No alternate slots found within the search period")
    else:
        logs.append(f"✨ Found {len(alternate_slots)} alternate slot(s)")

    return alternate_slots, logs







# API endpoint to check availability

@api_view(['POST'])
def check_availability_retell(request, secretKey):
    """
    API endpoint for Retell AI to check appointment availability.
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=405)
        
        apiCreds = ApiCredential.objects.get(secretKey=secretKey)
        business = apiCreds.business

        # Parse request body
        post_data = json.loads(request.body)

        # Extract parameters
        args = post_data.get("args", {})
        cleaningDateTime = args.get("cleaningDateTime")

        if not cleaningDateTime:
            return JsonResponse({"error": "Missing required field: cleaningDateTime"}, status=400)

        # Extract timezone if provided, default to UTC
        timezone_str = args.get('timezone', 'UTC')
        
        # Parse the date
        time_to_check = datetime.fromisoformat(cleaningDateTime)
        current_year = datetime.now().year
        time_to_check = time_to_check.replace(year=current_year)
        
        res = parse_business_datetime(cleaningDateTime, business)
        
      
        cleaners = get_cleaners_for_business(business, assignment_check_null=True)
        available_cleaners = []

        # Check if the requested time is available
        is_available, availability_logs = is_slot_available(cleaners, res['data']['utc_datetime'], available_cleaners)
        
        # Base response with common fields
        response = {
            "status": "success",
            "available": is_available,
            "timeslot": res['data']['utc_datetime'].strftime("%Y-%m-%d %H:%M:%S")
        }

        # If not available, find alternate slots
        if not is_available:
            alternate_slots, alternate_logs = find_alternate_slots(cleaners, res['data']['utc_datetime'])
            response["alternates"] = alternate_slots

        return JsonResponse(response, status=200)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)



# API endpoint to check availability for the booking form
@api_view(['GET'])
def check_availability_for_booking(request):
    try:
        date_str = request.GET.get('date')
        time_str = request.GET.get('time')
        timezone_str = request.GET.get('timezone', 'UTC')
        
        if not date_str or not time_str:
            return JsonResponse({"error": "Missing date or time parameter"}, status=400)
        
        res = parse_business_datetime(date_str + ' ' + time_str, business)
        
        if hasattr(request.user, 'customer') and request.user.customer or not request.user.is_authenticated:
            print(request.GET.get("businessId"))
            business_id = request.GET.get("businessId")
            current_business = Business.objects.get(businessId=business_id)


        if not current_business:
            return JsonResponse({"error": "Business not found"}, status=404)

        cleaners = get_cleaners_for_business(current_business, assignment_check_null=True)
        
        # Check availability
        available_cleaners = []
        is_available, _ = is_slot_available(cleaners, res['data']['utc_datetime'], available_cleaners)
        
        # Find alternative slots if not available
        alternative_slots = []
        if not is_available:
            alt_slots, _ = find_alternate_slots(cleaners, res['data']['utc_datetime'], max_alternates=3)
            
            # Convert alternative slots back to business timezone for display
            formatted_alt_slots = []
            for slot in alt_slots:
                # Parse the slot string to datetime (with AM/PM format)
                try:
                    slot_dt = datetime.strptime(slot, '%Y-%m-%d %I:%M %p')
                    slot_dt_utc = pytz.UTC.localize(slot_dt)
                    slot_dt_local = slot_dt_utc.astimezone(local_tz)
                    formatted_alt_slots.append(slot_dt_local.strftime('%Y-%m-%d %I:%M %p'))
                except ValueError as e:
                    # Log the error and skip this slot
                    logger.error(f"Error parsing slot {slot}: {str(e)}")
                    continue
            
            alternative_slots = formatted_alt_slots
        
        # Return response
        return JsonResponse({
            "available": is_available,
            "alternative_slots": alternative_slots,
            
        })
    except Exception as e:
        import traceback
        print(f"Error in check_availability_for_booking: {str(e)}")
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)


# API endpoint to create a new booking from Retell
@csrf_exempt
@api_view(['POST', 'GET'])
def create_booking(request):
    try:
        post_data = json.loads(request.body)
        data = post_data.get('args', {})

        try:
            business = Business.objects.get(businessId=data['business_id'])
            businessSettingsObj = BusinessSettings.objects.get(business=business)
        except Business.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Business not found'
            }, status=404)
        
        res = parse_business_datetime(data['appointment_date_time'], business)
        
        # Find an available cleaner
        cleaners = get_cleaners_for_business(business, assignment_check_null=True)
        available_cleaner = find_available_cleaner(cleaners, res['data']['utc_datetime'])
        
        if not available_cleaner:
            # Find alternate slots
            alternate_slots, _ = find_alternate_slots(cleaners, res['data']['utc_datetime'])
            return JsonResponse({
                'success': False,
                'message': 'No cleaners available for the requested time',
                'alternateSlots': alternate_slots
            }, status=409)  # Conflict status code
        
        # Normalize service type
        service_type = data["service_type"].lower().replace(" ", "")
        service_type = getServiceType(service_type)
        

        customer = create_customer(data)

        # Create booking object with mapped fields
        booking = Booking(
            business=business,
            customer=customer,
            bedrooms=Decimal(data.get('bedrooms', 0) or 0),
            bathrooms=Decimal(data.get('bathrooms', 0) or 0),
            squareFeet=Decimal(data.get('area', 0) or 0),
            cleaningDate=res['data']['utc_datetime'],
            startTime=res['data']['utc_start_time'],
            endTime=res['data']['utc_end_time'],
            serviceType=service_type,
            recurring=data.get('recurring', 'one-time'),
            otherRequests=data.get('otherRequests', 'Not Set'),
            addonDishes = int(data.get('dishes', 0) or 0),
            addonLaundryLoads = int(data.get('laundry', 0) or 0),
            addonWindowCleaning = int(data.get('windows', 0) or 0),
            addonPetsCleaning = int(data.get('pets', 0) or 0),
            addonFridgeCleaning = int(data.get('fridge', 0) or 0),
            addonOvenCleaning = int(data.get('oven', 0) or 0),
            addonBaseboard = int(data.get('baseboard', 0) or 0),
            addonBlinds = int(data.get('blinds', 0) or 0),
            addonGreenCleaning = int(data.get('green', 0) or 0),
            addonCabinetsCleaning = int(data.get('cabinets', 0) or 0),
            addonPatioSweeping = int(data.get('patio', 0) or 0),
            addonGarageSweeping = int(data.get('garage', 0) or 0)
        )
        

        
        # Calculate price using business settings
        # Calculate base price
        amount_calculation = calculateAmount(
             business,
             booking,             
        )
        
      
        booking.totalPrice = amount_calculation['total_amount']
        booking.tax = amount_calculation['tax']
        
        # Save the booking
        booking.save()
        
        # Add custom addons if any
        bookingCustomAddons = amount_calculation['custom_addons']['bookingCustomAddons']
        if bookingCustomAddons:
            booking.customAddons.set(bookingCustomAddons)
            booking.save()
        
        # Import threading for background execution
        from .webhooks import send_booking_data
        webhook_thread = threading.Thread(target=send_booking_data, args=(booking,))
        webhook_thread.daemon = True
        webhook_thread.start()
        
        return JsonResponse({
            'success': True,
            'message': 'Booking created successfully',
            'booking': {
                'bookingId': booking.bookingId,
                'cleaningDate': booking.cleaningDate.strftime('%Y-%m-%d'),
                'startTime': booking.startTime.strftime('%H:%M'),
                'endTime': booking.endTime.strftime('%H:%M'),
                'totalPrice': float(booking.totalPrice)
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON data'
        }, status=400)
    except Exception as e:
        print(f"[DEBUG] Error creating booking: {str(e)}")
        traceback.print_exc()
        return JsonResponse({
            'success': False,
            'message': f'Error creating booking: {str(e)}'
        }, status=500)


@csrf_exempt
@api_view(['POST', 'GET'])
def sendCommercialFormLink(request):
    try:
        # Parse request data
        if request.method == 'POST':
            data = json.loads(request.body)
        else:  # GET
            data = request.GET.dict()
        
        args = data.get('args')

        name = args.get('name')
        email = args.get('email')
        business_id = args.get('business_id')
        
        # Validate required fields
        if not email:
            return JsonResponse({
                'success': False,
                'message': 'Email address is required'
            }, status=400)
        
        # Get business
        try:
            business = Business.objects.get(businessId=business_id)
        except Business.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Business not found'
            }, status=404)
        
       
        
        # Generate the commercial form link
        form_link = f"{settings.BASE_URL}/commercial-form/{business.businessId}/"
        
        # Email content
        subject = f"Commercial Cleaning Quote Request - {business.businessName}"
        
    
        
        # Plain text content
        text_content = f"""Hello {name},

            Thank you for your interest in commercial cleaning services from {business.businessName}.

            To provide you with an accurate quote for your commercial space, we need some additional information about your requirements.

            Please visit the following link to fill out our commercial cleaning questionnaire:
            {form_link}

            Once we receive your information, our team will review your requirements and provide you with a customized quote.

            If you have any questions, please don't hesitate to contact us.

            Best regards,
            The {business.businessName} Team
        """
        
        # Send the email

        send_email(
            subject=subject,
            text_content=text_content,
            from_email=f"{business.businessName} <{business.user.email}>",
            to_email=email,
            reply_to=business.user.email
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Commercial form link sent successfully',
            'email': email,
            'form_link': form_link
        })
        
    except Exception as e:
        print(f"Error sending commercial form link: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Error sending email: {str(e)}'
        }, status=500)




@csrf_exempt
@api_view(['POST'])
def reschedule_booking(request):
    try:
        request_data = json.loads(request.body)
        data = request_data.get('args')
        booking_id = data.get('booking_id')
        new_date_time = data.get('next_date_time')
        
        booking = Booking.objects.get(bookingId=booking_id)

        from ai_agent.api_views import reschedule_appointment
        reschedule_response = reschedule_appointment(booking, new_date_time)

        if reschedule_response['success']:
            return JsonResponse({'success': True, 'message': 'Booking rescheduled successfully'})
        else:
            return JsonResponse({'success': False, 'message': reschedule_response['error']}, status=500)
    

    except Exception as e:
        print(f"Error rescheduling booking: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error rescheduling booking: {str(e)}'}, status=500)




@csrf_exempt
@api_view(['POST'])
def cancel_booking(request):
    try:
        request_data = json.loads(request.body)
        data = request_data.get('args')
        booking_id = data.get('booking_id')
        
        booking = Booking.objects.filter(bookingId=booking_id).first()
        
        from ai_agent.api_views import cancel_appointment
        cancel_response = cancel_appointment(booking)

        if cancel_response['success']:
            return JsonResponse({'success': True, 'message': 'Booking cancelled successfully'})
        else:
            return JsonResponse({'success': False, 'message': cancel_response['error']}, status=500)

    except Exception as e:
        print(f"Error cancelling booking: {str(e)}")
        traceback.print_exc()
        return JsonResponse({'success': False, 'message': f'Error cancelling booking: {str(e)}'}, status=500)



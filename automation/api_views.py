import os
import json
from datetime import datetime, timedelta
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils.timezone import make_aware, is_naive
from retell import Retell
from accounts.models import Business, ApiCredential
from bookings.models import Booking
from .models import Cleaners, CleanerAvailability
import pytz

# Function to get available cleaners for a business
def get_cleaners_for_business(business):
    """ Fetch all active cleaners who are available for work. """
    print("Finding cleaners for business:", business)
    cleaners = Cleaners.objects.filter(business=business, isActive=True, isAvailable=True)
    print("Found cleaners:", cleaners)
    return cleaners

# Function to get cleaner availabilities for a specific day
def get_cleaner_availabilities(week_day):
    """ Fetch cleaner availabilities who are NOT on a day off. """
    return CleanerAvailability.objects.filter(dayOfWeek=week_day, offDay=False)

# Function to check if a timeslot is available
def is_slot_available(cleaners, time_to_check, available_cleaners=None):
    """Check if at least one cleaner is available for the given time."""
    print("\nChecking availability for time:", time_to_check)
    print("Number of cleaners to check:", len(cleaners))
    
    for cleaner in cleaners:
        print("\nChecking cleaner:", cleaner.name)
        
        # Check cleaner's availability for the requested day
        availability = CleanerAvailability.objects.filter(
            cleaner=cleaner, 
            dayOfWeek=time_to_check.strftime('%A'),
            offDay=False
        ).first()

        if not availability:
            print(f"No availability found for {cleaner.name} on {time_to_check.strftime('%A')}")
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

        print(f"✓ {cleaner.name} is available!")
        if available_cleaners is not None:
            available_cleaners.append(cleaner)
        return True

    print("No available cleaners found for this time slot")
    return False

# Function to find an available cleaner
def find_available_cleaner(cleaners, time_to_check):
    """Find an available cleaner for the given time slot."""
    print("\nFinding available cleaner for time:", time_to_check)
    print("Number of cleaners to check:", len(cleaners))
    
    for cleaner in cleaners:
        print("\nChecking cleaner:", cleaner.name)
        
        # Check cleaner's availability for the requested day
        availability = CleanerAvailability.objects.filter(
            cleaner=cleaner, 
            dayOfWeek=time_to_check.strftime('%A'),
            offDay=False
        ).first()

        if not availability:
            print(f"No availability found for {cleaner.name} on {time_to_check.strftime('%A')}")
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

        print(f"✓ Found available cleaner: {cleaner.name}")
        return cleaner

    print("No available cleaners found for this time slot")
    return None

# Function to find alternate available slots
def find_alternate_slots(cleaners, datetimeToCheck, max_alternates=3):
    """
    Find up to `max_alternates` alternate available timeslots.
    If no slots exist on the requested day, search the next available day.
    
    Note: datetimeToCheck should already be in the business's timezone.
    """
    alternate_slots = []
    time_increment = timedelta(hours=1)
    max_attempts = 10
    next_time = datetimeToCheck + time_increment
    available_cleaners = []

    while len(alternate_slots) < max_alternates and max_attempts > 0:
        if is_slot_available(cleaners, next_time, available_cleaners):
            alternate_slots.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))

        latest_end_time = max(get_cleaner_availabilities(next_time.strftime('%A'))
                              .values_list('endTime', flat=True), default=None)

        if latest_end_time and next_time.time() >= latest_end_time:
            break

        next_time += time_increment
        max_attempts -= 1

    if len(alternate_slots) < max_alternates:
        next_available_day = datetimeToCheck + timedelta(days=1)
        day_attempts = 7

        while day_attempts > 0:
            next_weekDay = next_available_day.strftime('%A')
            available_cleaners = get_cleaner_availabilities(next_weekDay)

            for availability in available_cleaners:
                # Create a new datetime object with the start time from availability
                slot_time = next_available_day.replace(
                    hour=availability.startTime.hour, 
                    minute=availability.startTime.minute,
                    second=0,
                    microsecond=0
                )
                
                while slot_time.time() < availability.endTime:
                    temp_cleaners = []
                    if is_slot_available(cleaners, slot_time, temp_cleaners):
                        alternate_slots.append(slot_time.strftime("%Y-%m-%d %H:%M:%S"))
                    if len(alternate_slots) >= max_alternates:
                        return alternate_slots
                    slot_time += time_increment

            next_available_day += timedelta(days=1)
            day_attempts -= 1

    return alternate_slots[:max_alternates]

# API endpoint to check availability
@csrf_exempt
def check_availability_retell(request, secretKey):
    """
    API endpoint for Retell AI to check appointment availability.
    Takes into account the business's timezone for accurate availability checks.
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=405)
        
        apiCreds = ApiCredential.objects.get(secretKey=secretKey)
        business = apiCreds.business

        # Parse request body
        post_data = json.loads(request.body)

        retell = Retell(api_key=apiCreds.retellAPIKey)

        # Verify request signature
        valid_signature = retell.verify(
            json.dumps(post_data, separators=(",", ":"), ensure_ascii=False),
            api_key=str(apiCreds.retellAPIKey),
            signature=str(request.headers.get("X-Retell-Signature")),
        )

        if not valid_signature:
            return JsonResponse({"error": "Unauthorized request"}, status=401)

        # Extract parameters
        args = post_data.get("args", {})
        cleaningDateTime = args.get("cleaningDateTime")
        request_timezone = args.get("timezone")  # Get timezone from request if provided

        if not cleaningDateTime:
            return JsonResponse({"error": "Missing required field: cleaningDateTime"}, status=400)

        # Get business timezone (default to UTC if not set)
        business_timezone = business.timezone or 'UTC'
        
        # If request_timezone is provided, we'll use it for interpreting the input time
        # but we'll still use the business timezone for checking availability
        input_timezone = request_timezone or business_timezone
        

        
        # Parse the input datetime - remove Z to handle it as a local time in the input timezone
        input_datetime_str = cleaningDateTime.replace("Z", "")
        
        # Create a timezone-aware datetime in the input timezone
        input_tz = pytz.timezone(input_timezone)
        business_tz = pytz.timezone(business_timezone)
        
        # Parse the datetime and make it timezone-aware in the input timezone
        naive_dt = datetime.fromisoformat(input_datetime_str)
        input_aware_dt = input_tz.localize(naive_dt)
        
        print(f"Input Aware DateTime: {input_aware_dt}")
        
        # Convert to business timezone for availability checking
        business_datetime = input_aware_dt.astimezone(business_tz)
       

        weekDay = business_datetime.strftime('%A')
    

        cleaners = get_cleaners_for_business(business)
        available_cleaners = []

        # Check if the requested time is available
        if is_slot_available(cleaners, business_datetime, available_cleaners):
            response = {
                "status": "success",
                "available": True,
                "timeslot": business_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            }

            return JsonResponse(response, status=200)

        # Find alternate available slots
        alternate_slots = find_alternate_slots(cleaners, business_datetime)
        
        # Format alternate slots with timezone info
        formatted_alternates = []
        for slot in alternate_slots:
            # Convert string back to datetime
            slot_dt = datetime.strptime(slot, "%Y-%m-%d %H:%M:%S")
            # Make timezone aware in business timezone
            slot_dt = business_tz.localize(slot_dt)
            formatted_alternates.append(slot_dt.strftime("%Y-%m-%d %H:%M:%S"))

        return JsonResponse({
            "status": "success",
            "available": False,
            "timeslot": business_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "alternates": formatted_alternates
        }, status=200)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

# Test endpoint to check availability without Retell signature verification
@csrf_exempt
def test_check_availability(request, secretKey):
    """
    Test endpoint for checking appointment availability without Retell signature verification.
    This is only for testing purposes and should not be used in production.
    """
    try:
        if request.method != "POST":
            return JsonResponse({"error": "Invalid request method"}, status=405)
        
        # Try to get API credentials
        try:
            apiCreds = ApiCredential.objects.get(secretKey=secretKey)
            business = apiCreds.business
        except ApiCredential.DoesNotExist:
            return JsonResponse({"error": "Invalid secret key"}, status=401)

        # Parse request body
        post_data = json.loads(request.body)
        
        # Extract parameters
        args = post_data.get("args", {})
        cleaningDateTime = args.get("cleaningDateTime")
        request_timezone = args.get("timezone")  # Get timezone from request

        if not cleaningDateTime:
            return JsonResponse({"error": "Missing required field: cleaningDateTime"}, status=400)

        # Get business timezone (default to UTC if not set)
        business_timezone = business.timezone or 'UTC'
        
        # If request_timezone is provided, we'll use it for interpreting the input time
        # but we'll still use the business timezone for checking availability
        input_timezone = request_timezone or business_timezone
        
       
        
        # Parse the input datetime - remove Z to handle it as a local time in the input timezone
        input_datetime_str = cleaningDateTime.replace("Z", "")
        
        # Create a timezone-aware datetime in the input timezone
        input_tz = pytz.timezone(input_timezone)
        business_tz = pytz.timezone(business_timezone)
        
        # Parse the datetime and make it timezone-aware in the input timezone
        naive_dt = datetime.fromisoformat(input_datetime_str)
        input_aware_dt = input_tz.localize(naive_dt)
       
        # Convert to business timezone for availability checking
        business_datetime = input_aware_dt.astimezone(business_tz)

        weekDay = business_datetime.strftime('%A')

        cleaners = get_cleaners_for_business(business)
        available_cleaners = []

        # Check if the requested time is available
        if is_slot_available(cleaners, business_datetime, available_cleaners):
            response = {
                "status": "success",
                "available": True,
                "timeslot": business_datetime.strftime("%Y-%m-%d %H:%M:%S"),
                "timezone": business_timezone,
                "cleaners": [{"id": c.id, "name": c.name} for c in available_cleaners],
                "alternates": []
            }
 
            return JsonResponse(response, status=200)

        # Find alternate available slots
        alternate_slots = find_alternate_slots(cleaners, business_datetime)
        
        # Format alternate slots with timezone info
        formatted_alternates = []
        for slot in alternate_slots:
            # Convert string back to datetime
            slot_dt = datetime.strptime(slot, "%Y-%m-%d %H:%M:%S")
            # Make timezone aware in business timezone
            slot_dt = business_tz.localize(slot_dt)
            formatted_alternates.append(slot_dt.strftime("%Y-%m-%d %H:%M:%S"))

        return JsonResponse({
            "status": "success",
            "available": False,
            "timeslot": business_datetime.strftime("%Y-%m-%d %H:%M:%S"),
            "timezone": business_timezone,
            "alternates": formatted_alternates
        }, status=200)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

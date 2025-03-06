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
def get_cleaner_availabilities(cleaner, date_to_check):
    """ 
    Fetch cleaner availabilities for a specific date.
    First checks for specific date exception, then falls back to weekly schedule.
    Returns None if the cleaner is off on the requested date.
    """
    # First check for specific date exception
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
    """
    Check if at least one cleaner is available for the given time.
    Returns True if any cleaner is available, False otherwise.
    Also populates available_cleaners list with all cleaners available for this slot.
    """
    if available_cleaners is None:
        available_cleaners = []
    
    # Clear the list to ensure we don't append to existing data
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

# Function to find an available cleaner
def find_available_cleaner(cleaners, time_to_check):
    """Find an available cleaner for the given time slot."""
    print("\nFinding available cleaner for time:", time_to_check)
    print("Number of cleaners to check:", len(cleaners))
    
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
from rest_framework.decorators import api_view
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

        if not cleaningDateTime:
            return JsonResponse({"error": "Missing required field: cleaningDateTime"}, status=400)

        time_to_check = datetime.fromisoformat(cleaningDateTime)
        cleaners = get_cleaners_for_business(business)
        available_cleaners = []

        # Check if the requested time is available
        is_available, availability_logs = is_slot_available(cleaners, time_to_check, available_cleaners)
        
        # Base response with common fields
        response = {
            "status": "success",
            "available": is_available,
            "timeslot": time_to_check.strftime("%Y-%m-%d %H:%M:%S"),
            "cleaners": [{"id": c.id, "name": c.name} for c in available_cleaners],
        }

        # If not available, find alternate slots
        if not is_available:
            alternate_slots, alternate_logs = find_alternate_slots(cleaners, time_to_check)
            response["alternates"] = alternate_slots

        return JsonResponse(response, status=200)

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

        if not cleaningDateTime:
            return JsonResponse({"error": "Missing required field: cleaningDateTime"}, status=400)

        cleaners = get_cleaners_for_business(business)
        time_to_check = datetime.fromisoformat(cleaningDateTime)
        available_cleaners = []

        # Check if the requested time is available
        is_available, availability_logs = is_slot_available(cleaners, time_to_check, available_cleaners)
        
        # Base response with common fields
        response = {
            "status": "success",
            "available": is_available,
            "timeslot": time_to_check.strftime("%Y-%m-%d %I:%M %p"),
            "cleaners": [{"id": c.id, "name": c.name} for c in available_cleaners],
            "logs": availability_logs
        }

        # If not available, find alternate slots
        if not is_available:
            alternate_slots, alternate_logs = find_alternate_slots(cleaners, time_to_check)
            response["alternates"] = alternate_slots
            response["logs"].extend(alternate_logs)

        return JsonResponse(response, status=200)

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        return JsonResponse({"error": str(e)}, status=500)

# API endpoint to check availability for the booking form
@api_view(['GET'])
def check_availability_for_booking(request):
    """
    API endpoint to check if a timeslot is available for booking.
    Returns availability status and alternative slots if not available.
    """
    try:
        # Get date and time from request
        date_str = request.GET.get('date')
        time_str = request.GET.get('time')
        
        if not date_str or not time_str:
            return JsonResponse({"error": "Missing date or time parameter"}, status=400)
        
        # Parse date and time
        date_obj = datetime.strptime(date_str, '%Y-%m-%d').date()
        time_obj = datetime.strptime(time_str, '%H:%M').time()
        
        # Combine into a datetime object
        datetime_to_check = datetime.combine(date_obj, time_obj)
        
        # Get all active cleaners
        cleaners = Cleaners.objects.filter(isActive=True, isAvailable=True)
        
        # Check availability
        available_cleaners = []
        is_available, _ = is_slot_available(cleaners, datetime_to_check, available_cleaners)
        
        # Find alternative slots if not available
        alternative_slots = []
        if not is_available:
            alt_slots, _ = find_alternate_slots(cleaners, datetime_to_check, max_alternates=3)
            alternative_slots = alt_slots
        
        # Return response
        return JsonResponse({
            "available": is_available,
            "alternative_slots": alternative_slots,
            "cleaners": [{
                "id": c.id,
                "name": c.name
            } for c in available_cleaners]
        })
        
    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

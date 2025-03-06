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
        # Get the day of week
        week_day = time_to_check.strftime('%A')
        logs.append(f"\nChecking cleaner: {cleaner.name}")
        
        # Check if cleaner works on this day
        if not get_cleaner_availabilities(week_day).filter(cleaner=cleaner).exists():
            logs.append(f"❌ {cleaner.name} doesn't work on {week_day}")
            continue

        # Check if time is within cleaner's working hours
        cleaner_availability = get_cleaner_availabilities(week_day).filter(cleaner=cleaner).first()
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
    logs = []
    logs.append(f"\nLooking for alternate slots after {datetimeToCheck.strftime('%Y-%m-%d %H:%M')}")
    
    alternate_slots = []
    time_increment = timedelta(hours=1)
    max_attempts = 10
    next_time = datetimeToCheck.replace(minute=0, second=0, microsecond=0) + time_increment
    available_cleaners = []

    while len(alternate_slots) < max_alternates and max_attempts > 0:
        is_available, slot_logs = is_slot_available(cleaners, next_time, available_cleaners)
        logs.extend(slot_logs)
        
        if is_available:
            alternate_slots.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))
            logs.append(f"✅ Found alternate slot at {next_time.strftime('%Y-%m-%d %H:%M')}")
        
        next_time += time_increment
        max_attempts -= 1

    if len(alternate_slots) == 0:
        logs.append("❌ No alternate slots found within the next few hours")
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
            "timeslot": time_to_check.strftime("%Y-%m-%d %H:%M:%S"),
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

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

# Function to get available cleaners for a business
def get_cleaners_for_business(business):
    """ Fetch all active cleaners who are NOT on vacation (isAvailable=False). """
    return Cleaners.objects.filter(business=business, isActive=True, isAvailable=False)

# Function to get cleaner availabilities for a specific day
def get_cleaner_availabilities(week_day):
    """ Fetch cleaner availabilities who are NOT on a day off. """
    return CleanerAvailability.objects.filter(dayOfWeek=week_day, offDay=False)

# Function to check if a timeslot is available
def is_slot_available(cleaners, time_to_check):
    """Check if at least one cleaner is available for the given time."""
    for cleaner in cleaners:
        # Skip cleaner if they are unavailable (vacation)
        if cleaner.isAvailable:
            continue  

        # Check cleaner's availability for the requested day
        availability = CleanerAvailability.objects.filter(
            cleaner=cleaner, dayOfWeek=time_to_check.strftime('%A'), offDay=False
        ).first()
        if not availability:
            continue  # Skip if the cleaner is not available that day

        # Ensure time falls within working hours
        if not (availability.startTime <= time_to_check.time() < availability.endTime):
            continue

        # Check for conflicting bookings
        conflicting_booking = Booking.objects.filter(
            cleaner=cleaner,
            cleaningDate=time_to_check.date(),
            startTime__lte=time_to_check.time(),
            endTime__gt=time_to_check.time()
        ).exists()

        print("📌 Conflicting Booking:", conflicting_booking)

        if not conflicting_booking:
            return True  # Found an available cleaner

    return False  # No available cleaner found

# Function to find alternate available slots
def find_alternate_slots(cleaners, datetimeToCheck, max_alternates=3):
    """
    Find up to `max_alternates` alternate available timeslots.
    If no slots exist on the requested day, search the next available day.
    """
    alternate_slots = []
    time_increment = timedelta(hours=1)
    max_attempts = 10
    next_time = datetimeToCheck + time_increment

    while len(alternate_slots) < max_alternates and max_attempts > 0:
        if is_slot_available(cleaners, next_time):
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
                slot_time = next_available_day.replace(hour=availability.startTime.hour, minute=0)
                while slot_time.time() < availability.endTime:
                    if is_slot_available(cleaners, slot_time):
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

        # Convert string to datetime
        datetimeToCheck = datetime.fromisoformat(cleaningDateTime.replace("Z", "+00:00"))
        if is_naive(datetimeToCheck):
            datetimeToCheck = make_aware(datetimeToCheck)

        weekDay = datetimeToCheck.strftime('%A')

        print("📌 Processed Date:", datetimeToCheck)

        cleaners = get_cleaners_for_business(business)

        # Check if the requested time is available
        if is_slot_available(cleaners, datetimeToCheck):
            return JsonResponse({
                "status": "success",
                "available": True,
                "timeslot": datetimeToCheck.strftime("%Y-%m-%d %H:%M:%S"),
                "alternates": []
            }, status=200)

        # Find alternate available slots
        alternate_slots = find_alternate_slots(cleaners, datetimeToCheck)

        return JsonResponse({
            "status": "success",
            "available": False,
            "timeslot": datetimeToCheck.strftime("%Y-%m-%d %H:%M:%S"),
            "alternates": alternate_slots
        }, status=200)

    except Exception as e:
        return JsonResponse({"error": str(e)}, status=500)

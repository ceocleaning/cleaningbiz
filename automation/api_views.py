from rest_framework.response import Response
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
import dateparser
from django.utils import timezone

from accounts.models import ApiCredential, Business
from bookings.models import Booking 
from .models import Cleaners, CleanerAvailability


def get_cleaners_for_business(business):
    """ Fetch all active cleaners for the given business. """
    return Cleaners.objects.filter(business=business, isActive=True)


def get_cleaner_availabilities(week_day):
    """ Fetch all cleaner availabilities for the given day. """
    return CleanerAvailability.objects.filter(dayOfWeek=week_day)


def is_slot_available(cleaners, time_to_check):
    """
    Check if at least one cleaner is available for the given time.
    """
    for cleaner in cleaners:
        # Fetch cleaner availability for the given day
        availability = CleanerAvailability.objects.filter(
            cleaner=cleaner, 
            dayOfWeek=time_to_check.strftime('%A')
        ).first()

        if not availability:
            continue  # Skip if the cleaner is not available that day

        # Ensure time falls within working hours
        if not (availability.startTime <= time_to_check.time() < availability.endTime):
            continue

        # Check if cleaner has an overlapping booking
        conflicting_booking = Booking.objects.filter(
            cleaner=cleaner,
            cleaningDate=time_to_check.date(),
            startTime__lte=time_to_check.time(),
            endTime__gt=time_to_check.time()
        ).exists()

        if not conflicting_booking:
            return True  # Found an available cleaner

    return False  # No available cleaner found


def find_alternate_slots(cleaners, datetimeToCheck, max_alternates=3):
    """
    Find up to `max_alternates` alternate available timeslots.
    If no slots exist on the requested day, search the next available day.
    """
    alternate_slots = []
    time_increment = timedelta(hours=1)
    max_attempts = 10  # Prevent infinite loops
    next_time = datetimeToCheck + time_increment  # Start searching from the next hour

    while len(alternate_slots) < max_alternates and max_attempts > 0:
        if is_slot_available(cleaners, next_time):
            alternate_slots.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))

        # Stop checking beyond last working hour
        latest_end_time = max(get_cleaner_availabilities(next_time.strftime('%A'))
                              .values_list('endTime', flat=True), default=None)

        if latest_end_time and next_time.time() >= latest_end_time:
            break

        next_time += time_increment
        max_attempts -= 1

    # If no slots found today, look for the next available day's slots
    if len(alternate_slots) < max_alternates:
        next_available_day = datetimeToCheck + timedelta(days=1)
        day_attempts = 7  # Prevent infinite loops

        while day_attempts > 0:
            next_weekDay = next_available_day.strftime('%A')
            available_cleaners = get_cleaner_availabilities(next_weekDay)

            for availability in available_cleaners:
                slot_time = next_available_day.replace(hour=availability.startTime.hour, minute=0)

                while slot_time.time() < availability.endTime:
                    if is_slot_available(cleaners, slot_time):
                        alternate_slots.append(slot_time.strftime("%Y-%m-%d %H:%M:%S"))

                    if len(alternate_slots) >= max_alternates:
                        return alternate_slots  # Stop once we have enough slots

                    slot_time += time_increment  # Move to the next hourly slot

            # Move to the next day
            next_available_day += timedelta(days=1)
            day_attempts -= 1

    return alternate_slots[:max_alternates]


@api_view(['POST'])
def checkAvailability(request, secretKey):
    """
    Check if there is an available cleaner for the given 60-minute timeslot.
    If unavailable, suggest up to three alternative timeslots.
    """
    try:
        # Validate business using request user
        business = ApiCredential.objects.filter(secretKey=secretKey).first().business
        if not business:
            return Response({'status': 'error', 'message': 'Invalid secret key'}, status=400)

        # Extract and parse datetime from request
        datetimeToCheck_str = request.data.get('datetime')
        if not datetimeToCheck_str:
            return Response({'status': 'error', 'message': 'Datetime is required'}, status=400)

        datetimeToCheck = dateparser.parse(datetimeToCheck_str)
        if not datetimeToCheck:
            return Response({'status': 'error', 'message': 'Invalid datetime format'}, status=400)

        # Round time to the nearest full hour (force 60-minute slots)
        datetimeToCheck = datetimeToCheck.replace(minute=0, second=0, microsecond=0)
        weekDay = datetimeToCheck.strftime('%A')

        # Fetch all active cleaners for the business
        cleaners = get_cleaners_for_business(business)

        # Check if the requested time is available
        if is_slot_available(cleaners, datetimeToCheck):
            return Response({
                'status': 'success',
                'available': True,
                'timeslot': datetimeToCheck.strftime('%Y-%m-%d %H:%M:%S'),
                'alternates': []
            }, status=200)

        # Find alternate available slots
        alternate_slots = find_alternate_slots(cleaners, datetimeToCheck)

        return Response({
            'status': 'success',
            'available': False,
            'timeslot': datetimeToCheck.strftime('%Y-%m-%d %H:%M:%S'),
            'alternates': alternate_slots
        }, status=200)

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)

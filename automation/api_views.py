from rest_framework.response import Response
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
import dateparser
from django.utils import timezone

from accounts.models import Business
from bookings.models import Booking 
from .models import Cleaners, CleanerAvailability

@api_view(['GET'])
def checkAvailability(request):
    """
    Check if there is an available cleaner for the given 60-minute timeslot.
    If unavailable, suggest up to three alternative timeslots, including from the next available day.
    """
    try:
        # Get the current datetime
        current_datetime = timezone.now()

        # Validate business using request user
        business = Business.objects.filter(user=request.user).first()
        if not business:
            return Response({'status': 'error', 'message': 'Invalid secret key'}, status=400)

        # Extract and parse datetime from request
        datetimeToCheck_str = request.GET.get('datetime')
        if not datetimeToCheck_str:
            return Response({'status': 'error', 'message': 'Datetime is required'}, status=400)

        datetimeToCheck = dateparser.parse(datetimeToCheck_str)
        if not datetimeToCheck:
            return Response({'status': 'error', 'message': 'Invalid datetime format'}, status=400)

        # **Round time to the nearest full hour** (force 60-minute slots)
        datetimeToCheck = datetimeToCheck.replace(minute=0, second=0, microsecond=0)

        weekDay = datetimeToCheck.strftime('%A')  # Get day name (e.g., "Monday")

        print("Requested Day: ", weekDay, "Rounded Time:", datetimeToCheck.time())

        # Get all active cleaners
        cleaners = Cleaners.objects.filter(business=business, isActive=True)

        # Function to check if a specific time slot is available
        def is_slot_available(time_to_check):
            for cleaner in cleaners:
                # Get the cleaner's working hours
                availability = CleanerAvailability.objects.filter(
                    cleaner=cleaner, 
                    dayOfWeek=time_to_check.strftime('%A')
                ).first()

                if not availability:
                    continue  # Skip if cleaner is not available that day

                # Ensure the time is within working hours
                if not (availability.startTime <= time_to_check.time() < availability.endTime):
                    continue  # Skip if outside working hours

                # Check for conflicting bookings
                conflicting_booking = Booking.objects.filter(
                    cleaner=cleaner,
                    cleaningDate=time_to_check.date(),
                    startTime__lte=time_to_check.time(),
                    endTime__gt=time_to_check.time()
                )

                if not conflicting_booking.exists():
                    return True  # Found an available cleaner

            return False  # No available cleaner found

        # **Check if the requested time is available**
        if is_slot_available(datetimeToCheck):
            return Response({
                'status': 'success',
                'available': True,
                'timeslot': datetimeToCheck.strftime('%Y-%m-%d %H:%M:%S'),
                'alternates': []
            }, status=200)

        # **If requested time is unavailable, find up to three alternative slots (including from the next day if needed)**
        alternate_slots = []
        time_increment = timedelta(hours=1)  # Each timeslot is 60 minutes
        max_attempts = 10  # Prevent infinite loop

        next_time = datetimeToCheck + time_increment  # Start from the next available slot

        while len(alternate_slots) < 3 and max_attempts > 0:
            if is_slot_available(next_time):
                alternate_slots.append(next_time.strftime("%Y-%m-%d %H:%M:%S"))
            
            # Move to next hour but **do not exceed cleaner's max working hours**
            latest_end_time = max(CleanerAvailability.objects.filter(dayOfWeek=weekDay).values_list('endTime', flat=True), default=None)
            if latest_end_time and next_time.time() >= latest_end_time:
                break  # Stop checking beyond last working hour

            next_time += time_increment
            max_attempts -= 1  # Prevent infinite loop

        # **If no timeslots are available on the requested day, look for the next available day within working hours**
        if len(alternate_slots) < 3:
            print("No more slots found on", weekDay, "- Searching next available day...")

            next_available_day = datetimeToCheck + timedelta(days=1)  # Start searching from the next day
            day_attempts = 7  # Prevent infinite loop (limit to 1-week search)

            while day_attempts > 0:
                next_weekDay = next_available_day.strftime('%A')

                # Get available slots for this day within working hours
                available_cleaners = CleanerAvailability.objects.filter(dayOfWeek=next_weekDay)

                for availability in available_cleaners:
                    slot_time = next_available_day.replace(hour=availability.startTime.hour, minute=0)
                    while slot_time.time() < availability.endTime:
                        if is_slot_available(slot_time):
                            alternate_slots.append(slot_time.strftime("%Y-%m-%d %H:%M:%S"))

                        if len(alternate_slots) >= 3:
                            break  # Stop once we have 3 alternates

                        slot_time += time_increment  # Move to the next hourly slot

                if len(alternate_slots) >= 3:
                    break  # Stop searching once 3 alternate slots are found

                # Move to the next day
                next_available_day += timedelta(days=1)
                day_attempts -= 1

        return Response({
            'status': 'success',
            'available': False,
            'timeslot': datetimeToCheck.strftime('%Y-%m-%d %H:%M:%S'),
            'alternates': alternate_slots[:3]
        }, status=200)

    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)

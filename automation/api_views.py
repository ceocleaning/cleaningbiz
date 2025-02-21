from rest_framework.response import Response
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
import pytz
from rest_framework.views import csrf_exempt
import dateparser
from django.utils import timezone
from .utils import generateAppoitnmentId, sendInvoicetoClient, sendEmailtoClientInvoice

from bookings.models import Booking

def parse_time_input(time_str):
    """
    Parse various time input formats and return a timezone-aware datetime object
    """
    if not time_str:
        return None
        
    # Try parsing with dateparser
    settings = {
        'TIMEZONE': 'Asia/Kolkata',
        'RETURN_AS_TIMEZONE_AWARE': True,
        'PREFER_DATES_FROM': 'future'
    }
    
    parsed_date = dateparser.parse(time_str, settings=settings)
    
    if not parsed_date:
        return None
        
    # If time is not specified in the input, assume it's at the start of the hour
    if time_str.lower().find('am') == -1 and time_str.lower().find('pm') == -1 and \
       time_str.find(':') == -1:
        # Set time to 9 AM if only date is provided
        parsed_date = parsed_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    return parsed_date

@csrf_exempt
@api_view(['POST'])
def getAvailability(request):
    data = request.data
    start_time_str = data.get('start_date')
    print(start_time_str)
    
    if not start_time_str:
        return Response({'error': 'start_date is required'}, status=400)
    
    # Parse the input date string
    start_time = parse_time_input(start_time_str)
    print(start_time)
    
    if not start_time:
        return Response({
            'error': 'Could not parse the date and time. Please provide a valid format like "Tuesday 3 PM" or "2025-01-30 15:00"'
        }, status=400)
    
    # Ensure we're working with UTC
    start_time = start_time.astimezone(pytz.UTC)
    
    # Check if requested time is within working hours (9 AM to 5 PM)
    local_time = start_time.astimezone(pytz.timezone('Asia/Kolkata'))
    if local_time.hour < 9 or local_time.hour >= 17:
        return Response({
            'error': 'Appointments are only available between 9 AM and 5 PM',
            'requested_time': local_time.strftime('%Y-%m-%d %I:%M %p')
        }, status=400)
    
    # Check if the requested time slot is available
    end_time = start_time + timedelta(hours=1)
    existing_appointment = Appointment.objects.filter(
        startDateTime__lt=end_time,
        endTime__gt=start_time
    ).first()
    
    if not existing_appointment:
        availability_data = {
            'status': 'success',
            'is_available': True,
            'requested_slot': {
                'start': start_time.isoformat(),
                'end': end_time.isoformat(),
                'local_time': local_time.strftime('%Y-%m-%d %I:%M %p')
            }
        }

        print(availability_data)
        return Response(availability_data)
    
    # If not available, find next 3 available slots
    alternative_slots = []
    current_time = start_time
    
    while len(alternative_slots) < 3:
        current_time += timedelta(hours=1)
        local_time = current_time.astimezone(pytz.timezone('Asia/Kolkata'))
        
        # Skip if outside working hours
        if local_time.hour < 9 or local_time.hour >= 17:
            current_time = local_time.replace(hour=9, minute=0, second=0, microsecond=0)
            current_time = current_time + timedelta(days=1)
            current_time = current_time.astimezone(pytz.UTC)
            continue
        
        slot_end = current_time + timedelta(hours=1)
        is_slot_available = not Appointment.objects.filter(
            startDateTime__lt=slot_end,
            endTime__gt=current_time
        ).exists()
        
        if is_slot_available:
            slot_local_time = current_time.astimezone(pytz.timezone('Asia/Kolkata'))
            alternative_slots.append({
                'start': current_time.isoformat(),
                'end': slot_end.isoformat(),
                'local_time': slot_local_time.strftime('%Y-%m-%d %I:%M %p')
            })
    
    availability_data = {
        'is_available': False,
        'requested_slot': {
            'start': start_time.isoformat(),
            'end': end_time.isoformat(),
            'local_time': local_time.strftime('%Y-%m-%d %I:%M %p')
        },
        'alternative_slots': alternative_slots
    }
    
    print(availability_data)
    return Response(availability_data)




@csrf_exempt
@api_view(['POST'])
def addAppointment(request):
    data = request.data
    
    try:
        print(data)
        return Response({'status': 'success', 'details': 'Appointment added successfully'}, status=200)
    
    except Exception as e:
        print(e)
        return Response({'status': 'error', 'details': str(e)}, status=500)
  
    
   
    





@api_view(['POST'])
@csrf_exempt
def getInvoiceLink(request):
    try:
        data = request.data
        serial_number = data.get('serial_number')

      
        return Response({
            'invoice_link': "wwww.google.com",
            'status': 'success',
            }, status=200)
        
    except Exception as e:
        return Response({
            'status': 'error',
            'details': str(e)
        }, status=500)
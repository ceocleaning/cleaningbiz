import json
import re
from datetime import datetime
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone
import pytz

from .utils import convert_date_str_to_date

from .agent_tools.tools import CheckAvailabilityTool, BookAppointmentTool, RescheduleAppointmentTool, CancelAppointmentTool, GetServiceItemsTool
from bookings.models import Booking
from business.models import Business

@csrf_exempt
@require_http_methods(["POST"])
def check_availability(request):
    """
    API endpoint for Retell to check appointment availability
    Expected JSON format:
    {
        "date_time_str": "2025-05-10 14:00",
        "business_id": "business_id"
    }
    """
    try:
        body = json.loads(request.body)
        data = body.get('args', {})
        # Process check_availability request with data
        
        # Extract data from request
        date_time_str = data.get('date_time_str')
        business_id = data.get('business_id')
        
        if not date_time_str or not business_id:
            return JsonResponse({
                'success': False,
                'message': 'Missing required fields: date_time_str and business_id are required'
            }, status=400)
        
        # Parse the date_time_str using the utility function
        try:
            # Convert to standard format using the utility function
            iso_datetime = convert_date_str_to_date(date_time_str)
            
            # Parse the standardized datetime string
            parsed_date_time = datetime.strptime(iso_datetime, '%Y-%m-%d %H:%M:%S')
            
            # Extract date and time components
            date_str = parsed_date_time.strftime('%Y-%m-%d')
            time_str = parsed_date_time.strftime('%H:%M')
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error parsing date and time: {str(e)}'
            }, status=400)
        
        # Use the CheckAvailabilityTool to check availability
        availability_tool = CheckAvailabilityTool()
        result = availability_tool._run(
            date=date_str,
            time=time_str,
            business_id=business_id
        )
        
        # Determine if the slot is available based on the result message
        is_available = 'is available' in result.lower()
        
        return JsonResponse({
            'success': True,
            'is_available': is_available,
            'message': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def book_appointment(request):
    """
    API endpoint for Retell to book an appointment
    Expected JSON format:
    {
        "name": "John Doe",
        "email": "john@example.com",
        "phone": "+1234567890",
        "type_of_service": "Deep Cleaning",
        "bedrooms": 3,
        "bathroom": 2,
        "square_feet": 1500,
        "appointment_date_time": "2025-05-10 14:00",
        "city": "New York",
        "business_id": "business_id"
    }
    """
    try:
        post_data = json.loads(request.body)
        data = post_data.get('args', {})
        # Process book_appointment request with data
        
        # Extract required fields
        required_fields = [
            'name', 'phone', 'type_of_service', 'appointment_date_time', 'business_id'
        ]
        
        missing_fields = [field for field in required_fields if field not in data or not data[field]]
        if missing_fields:
            return JsonResponse({
                'success': False,
                'message': f'Missing required fields: {", ".join(missing_fields)}'
            }, status=400)
        
        business = Business.objects.get(id=data['business_id'])
        # Parse the appointment_date_time using the utility function
        try:
            # Convert to standard format using the utility function
            iso_datetime = convert_date_str_to_date(data['appointment_date_time'])
            
            # Parse the standardized datetime string
            parsed_date_time = datetime.strptime(iso_datetime, '%Y-%m-%d %H:%M:%S')
            
            # Extract date and time components
            date_str = parsed_date_time.strftime('%Y-%m-%d')
            time_str = parsed_date_time.strftime('%H:%M')
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error parsing appointment date and time: {str(e)}'
            }, status=400)
        
        # Prepare service items if provided
        from business.models import ServiceItem

        service_items_qs = ServiceItem.objects.filter(
            business=business,
            is_active=True
        )

        service_items = []
        for item in service_items_qs:
            if item.identifier in data:
                value = data[item.identifier]
                
                # Handle different field types
                if item.field_type == 'number':
                    # For number fields, value is the quantity
                    service_items.append({
                        'identifier': item.identifier,
                        'value': str(value),
                        'quantity': 1
                    })
                elif item.field_type == 'boolean':
                    # For boolean fields, convert to yes/no
                    bool_value = 'yes' if str(value).lower() in ['true', '1', 'yes', 'y'] else 'no'
                    service_items.append({
                        'identifier': item.identifier,
                        'value': bool_value,
                        'quantity': 1
                    })
                elif item.field_type == 'select':
                    # For select fields, use the selected option
                    service_items.append({
                        'identifier': item.identifier,
                        'value': str(value),
                        'quantity': 1
                    })
                elif item.field_type in ['text', 'textarea']:
                    # For text fields, use the text value
                    service_items.append({
                        'identifier': item.identifier,
                        'value': str(value),
                        'quantity': 1
                    })
                else:
                    # Fallback for unknown types
                    service_items.append({
                        'identifier': item.identifier,
                        'value': str(value),
                        'quantity': 1
                    })

        
        # Use the BookAppointmentTool to book the appointment
        booking_tool = BookAppointmentTool()
        result = booking_tool._run(
            date=date_str,
            time=time_str,
            service_name=data['type_of_service'],
            business_id=data['business_id'],
            customer_name=data['name'],
            customer_phone=data['phone'],
            customer_email=data.get('email', ''),
            service_items=service_items if service_items else None,
            notes=f"Bedrooms: {data.get('bedrooms', 'N/A')}, Bathrooms: {data.get('bathroom', 'N/A')}, Square Feet: {data.get('square_feet', 'N/A')}, City: {data.get('city', 'N/A')}"
        )
        
        # Check if booking was successful
        booking_successful = 'BOOKING_CONFIRMED' in result or 'booked successfully' in result.lower()
        
        # Extract booking ID if available
        booking_id = None
        if booking_successful:
            import re
            # Try new format first: "Booking ID: book_xxxxx"
            booking_id_match = re.search(r'Booking ID:\s*([\w-]+)', result)
            if booking_id_match:
                booking_id = booking_id_match.group(1)
        
        return JsonResponse({
            'success': booking_successful,
            'booking_id': booking_id,
            'message': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def cancel_appointment(request):
    """
    API endpoint for Retell to cancel an appointment
    Expected JSON format:
    {
        "booking_id": "booking_id",
        "business_id": "business_id",
        "reason": "Customer requested cancellation"
    }
    """
    try:
        data = json.loads(request.body)
        # Process cancel_appointment request with data
        
        # Extract required fields
        booking_id = data.get('booking_id')
        business_id = data.get('business_id')
        reason = data.get('reason')
        
        if not booking_id or not business_id:
            return JsonResponse({
                'success': False,
                'message': 'Missing required fields: booking_id and business_id are required'
            }, status=400)
        
        # Use the CancelAppointmentTool to cancel the appointment
        cancel_tool = CancelAppointmentTool()
        result = cancel_tool._run(
            booking_id=booking_id,
            business_id=business_id,
            reason=reason
        )
        
        # Check if cancellation was successful
        cancellation_successful = 'cancelled successfully' in result.lower()
        
        return JsonResponse({
            'success': cancellation_successful,
            'message': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["POST"])
def reschedule_appointment(request):
    """
    API endpoint for Retell to reschedule an appointment
    Expected JSON format:
    {
        "booking_id": "booking_id",
        "business_id": "business_id",
        "new_date_time": "2025-05-15 16:00"
    }
    """
    try:
        data = json.loads(request.body)
        # Process reschedule_appointment request with data
        
        # Extract required fields
        booking_id = data.get('booking_id')
        business_id = data.get('business_id')
        new_date_time = data.get('new_date_time')
        
        if not booking_id or not business_id or not new_date_time:
            return JsonResponse({
                'success': False,
                'message': 'Missing required fields: booking_id, business_id, and new_date_time are required'
            }, status=400)
        
        # Parse the new_date_time using the utility function
        try:
            # Convert to standard format using the utility function
            iso_datetime = convert_date_str_to_date(new_date_time)
            
            # Parse the standardized datetime string
            parsed_date_time = datetime.strptime(iso_datetime, '%Y-%m-%d %H:%M:%S')
            
            # Extract date and time components
            new_date_str = parsed_date_time.strftime('%Y-%m-%d')
            new_time_str = parsed_date_time.strftime('%H:%M')
            
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error parsing new date and time: {str(e)}'
            }, status=400)
        
        # Use the RescheduleAppointmentTool to reschedule the appointment
        reschedule_tool = RescheduleAppointmentTool()
        result = reschedule_tool._run(
            booking_id=booking_id,
            business_id=business_id,
            new_date=new_date_str,
            new_time=new_time_str
        )
        
        # Check if rescheduling was successful
        reschedule_successful = 'rescheduled successfully' in result.lower()
        
        return JsonResponse({
            'success': reschedule_successful,
            'message': result
        })
        
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'message': 'Invalid JSON in request body'
        }, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

@csrf_exempt
@require_http_methods(["GET"])
def get_appointment(request, booking_id):
    """
    API endpoint for Retell to get appointment details
    """
    try:
        # Process get_appointment request for booking_id
        
        if not booking_id:
            return JsonResponse({
                'success': False,
                'message': 'Missing required parameter: booking_id'
            }, status=400)
        
        try:
            booking = Booking.objects.get(id=booking_id)
        except Booking.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': f'Booking with ID {booking_id} not found'
            }, status=404)
        
        # Format the appointment details
        appointment_details = {
            'booking_id': str(booking.id),
            'customer_name': booking.name,
            'customer_email': booking.email,
            'customer_phone': booking.phone_number,
            'service': booking.service_offering.name if booking.service_offering else 'N/A',
            'date': booking.booking_date.strftime('%Y-%m-%d'),
            'time': booking.start_time.strftime('%H:%M'),
            'end_time': booking.end_time.strftime('%H:%M'),
            'status': booking.get_status_display(),
            'notes': booking.notes,
            'business_id': str(booking.business.id),
            'business_name': booking.business.name
        }
        
        return JsonResponse({
            'success': True,
            'appointment': appointment_details
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)

from rest_framework.response import Response
from rest_framework.decorators import api_view
from datetime import datetime, timedelta
import pytz
from rest_framework.views import csrf_exempt
import dateparser
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from decimal import Decimal

from .coupon_utils import validate_coupon as validate_coupon_util

from customer.models import Customer




@api_view(['POST'])
def calculateTotal(request):
    try:
        pass
    except Exception as e:
        return Response({'status': 'error', 'message': str(e)}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def validate_coupon(request):
    """
    API endpoint to validate a coupon code
    Expected POST data:
    - coupon_code: The coupon code to validate
    - business_id: The business ID (optional, for backward compatibility)
    - customer_id: The customer ID (optional for new customers)
    - booking_amount: The booking subtotal amount
    - service_type: The service type (optional)
    """
    try:
        import json
        
        # Debug: Print the raw request body
        print("=" * 50)
        print("COUPON VALIDATION REQUEST")
        print("=" * 50)
        print(f"Request body: {request.body}")
        
        data = json.loads(request.body)
        print(f"Parsed data: {data}")
        
        coupon_code = data.get('coupon_code', '').strip()
        customer_id = data.get('customer_id')
        booking_amount = data.get('booking_amount', 0)
        service_type = data.get('service_type')
        
        print(f"Coupon code: '{coupon_code}'")
        print(f"Customer ID: {customer_id}")
        print(f"Booking amount: {booking_amount} (type: {type(booking_amount)})")
        print(f"Service type: {service_type}")
        
        if not coupon_code:
            print("ERROR: No coupon code provided")
            return JsonResponse({
                'success': False,
                'message': 'Please enter a coupon code'
            }, status=400)
        
        # Convert booking_amount to Decimal, handle empty or invalid values
        try:
            booking_amount = Decimal(str(booking_amount)) if booking_amount else Decimal('0')
            print(f"Converted booking amount to Decimal: {booking_amount}")
        except (ValueError, TypeError) as e:
            print(f"ERROR: Invalid booking amount: {booking_amount}, Error: {e}")
            return JsonResponse({
                'success': False,
                'message': 'Invalid booking amount'
            }, status=400)
        
        # Get customer if provided
        customer = None
        if customer_id:
            try:
                customer = Customer.objects.get(id=customer_id)
                print(f"Customer found: {customer}")
            except Customer.DoesNotExist:
                print("Customer not found, treating as new customer")
                pass  # New customer, skip customer-specific checks
        
        # Use utility function to validate coupon
        print(f"Calling validate_coupon_util with:")
        print(f"  - coupon_code: {coupon_code}")
        print(f"  - customer: {customer}")
        print(f"  - booking_amount: {booking_amount}")
        print(f"  - service_type: {service_type}")
        
        validation_result = validate_coupon_util(
            coupon_code=coupon_code,
            customer=customer,
            booking_amount=booking_amount,
            service_type=service_type
        )
        
        print(f"Validation result: {validation_result}")
        
        if not validation_result['valid']:
            print(f"Validation failed: {validation_result['message']}")
            return JsonResponse({
                'success': False,
                'message': validation_result['message']
            })
        
        coupon = validation_result['coupon']
        discount_amount = validation_result['discount_amount']
        
        print(f"Validation successful! Discount: ${discount_amount}")
        print("=" * 50)
        
        return JsonResponse({
            'success': True,
            'message': 'Coupon applied successfully!',
            'coupon': {
                'code': coupon.code,
                'discount_type': coupon.discount_type,
                'discount_value': float(coupon.discount_value),
                'discount_amount': float(discount_amount),
                'description': coupon.get_discount_display()
            }
        })
        
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
        print("=" * 50)
        return JsonResponse({
            'success': False,
            'message': 'Invalid request data'
        }, status=400)
    except Exception as e:
        print(f"EXCEPTION: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()
        print("=" * 50)
        return JsonResponse({
            'success': False,
            'message': f'An error occurred: {str(e)}'
        }, status=500)
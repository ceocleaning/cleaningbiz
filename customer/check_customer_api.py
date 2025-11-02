"""
API endpoint to check if a customer exists by email
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
import json
from accounts.models import Business
from customer.models import Customer


@csrf_exempt
@require_http_methods(["POST"])
def check_customer(request):
    """
    Check if a customer exists by email for a specific business.
    Used by embeddable booking form to detect existing customers.
    
    POST Body:
    {
        "email": "customer@example.com",
        "business_id": "business-uuid"
    }
    
    Response:
    {
        "customer_id": "customer-uuid" or null,
        "exists": true/false
    }
    """
    try:
        data = json.loads(request.body)
        email = data.get('email')
        business_id = data.get('business_id')
        
        if not email or not business_id:
            return JsonResponse({
                'success': False,
                'error': 'Email and business_id are required'
            }, status=400)
        
        # Try to find customer by email and business
        try:
            business = Business.objects.get(businessId=business_id)
            customer = Customer.objects.get(email=email, businesses=business)
            
            # Prepare customer data including address information
            customer_data = {
                'success': True,
                'customer_id': str(customer.id),
                'exists': True,
                'customer_info': {
                    'first_name': customer.first_name or '',
                    'last_name': customer.last_name or '',
                    'email': customer.email or '',
                    'phone_number': customer.phone_number or '',
                    'address': customer.address or '',
                    'city': customer.city or '',
                    'state': customer.state_or_province or '',
                    'zip_code': customer.zip_code or '',
                }
            }
            
            return JsonResponse(customer_data)
        except Customer.DoesNotExist:
            return JsonResponse({
                'success': True,
                'customer_id': None,
                'exists': False
            })
        except Business.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Business not found'
            }, status=404)
            
    except json.JSONDecodeError:
        return JsonResponse({
            'success': False,
            'error': 'Invalid JSON'
        }, status=400)
    except Exception as e:
        print(str(e))
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

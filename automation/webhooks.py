from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt    
from django.db import transaction
from django.core.cache import cache
from asgiref.sync import sync_to_async
import json
import threading
from datetime import datetime, timedelta
from django.utils.timezone import make_aware, is_naive

from rest_framework import status
from .models import *
from .api_views import get_cleaners_for_business, find_available_cleaner

from accounts.models import ApiCredential, Business, BusinessSettings, CustomAddons
from bookings.models import Booking, BookingCustomAddons
from .utils import calculateAmount, calculateAddonsAmount
from integrations.models import PlatformIntegration, DataMapping, IntegrationLog
from retell_agent.models import RetellAgent
from subscription.models import UsageTracker
from retell import Retell
from django.conf import settings

@csrf_exempt
def thumbtack_webhook(request, secretKey):
    verifySecretKey = ApiCredential.objects.filter(secretKey=secretKey)
    if not verifySecretKey.exists():
        return JsonResponse({'message': 'Secret Not Verified'},status=500)

    business = verifySecretKey.business

    if request.method == 'POST':
        data = json.loads(request.body)
        print(data)
    
    return JsonResponse({'status': 'success'}, status=200)




@csrf_exempt
def handle_retell_webhook(request, secretKey):
    """Handle incoming Retell webhook requests"""
    if request.method != 'POST':
        return HttpResponse(status=405)
        
    try:
        if not request.body:
            return HttpResponse(status=400)
        
        # Quick validation of credentials
        apiCredentialObj = ApiCredential.objects.filter(secretKey=secretKey).first()
        if not apiCredentialObj:
            return HttpResponse(status=401)  # Unauthorized
            
        # Parse and validate basic request structure
        post_data = json.loads(request.body)
        event = post_data.get("event")
        if not event:
            return HttpResponse(status=400)
            
        # Start processing in a background thread
        webhook_data = {
            "post_data": post_data,
            "api_credential_id": apiCredentialObj.id
        }
        thread = threading.Thread(target=process_webhook_data, args=(webhook_data,))
        thread.start()
        
        # Return immediate success response
        return HttpResponse(status=200)

    except json.JSONDecodeError:
        return HttpResponse(status=400)
    except Exception as e:
        return HttpResponse(status=500)

@transaction.atomic
def process_webhook_data(webhook_data):
    """Process webhook data in a background thread"""
    try:
        post_data = webhook_data["post_data"]
        api_credential_id = webhook_data["api_credential_id"]

        print(f"Processing webhook data: {post_data}")
        
        # Get API credentials and business
        apiCredentialObj = ApiCredential.objects.get(id=api_credential_id)
        businessObj = apiCredentialObj.business
        
        event = post_data.get("event")
        call_data = post_data.get("call", {})
        call_id = call_data.get("call_id") or call_data.get("id", "")
      
        if event == 'call_ended':
            print(f"Call ended: {call_id}")
            
            # Get timestamps directly from the webhook payload
            start_timestamp = call_data.get("start_timestamp")
            end_timestamp = call_data.get("end_timestamp")
            
            if start_timestamp and end_timestamp:
                # Convert milliseconds to seconds and make timezone-aware
                start_time = make_aware(datetime.fromtimestamp(start_timestamp / 1000))
                end_time = make_aware(datetime.fromtimestamp(end_timestamp / 1000))
                
                # Calculate duration in minutes
                duration = end_time - start_time
                minutes = max(1, round(duration.total_seconds() / 60))
                
                # Track usage
                UsageTracker.increment_minutes(businessObj, minutes)
                print(f"Call {call_id} lasted {minutes} minutes")
                
                # Log the details for debugging
                print(f"Start time: {start_time}, End time: {end_time}, Duration: {duration}")
            else:
                # Fallback to a default value if timestamps are missing
                UsageTracker.increment_minutes(businessObj, 1)
                print(f"Used fallback duration of 1 minute for call {call_id} (missing timestamps)")
    
    except Exception as e:
        print(f"Error processing webhook: {str(e)}")
        import traceback
        print(traceback.format_exc())



# Sending Data to External Sources
def create_mapped_payload(booking_data, integration):
    """Create payload based on user-defined field mappings"""
    mappings = DataMapping.objects.filter(platform=integration)
    payload = {}
    
    # Convert datetime fields to string format
    if isinstance(booking_data["cleaningDate"], datetime):
        booking_data = dict(booking_data)  # Create a copy to avoid modifying the original
        booking_data["cleaningDate"] = booking_data["cleaningDate"].date().isoformat()
        booking_data["startTime"] = booking_data["startTime"].time().strftime("%H:%M:%S")
        booking_data["endTime"] = (booking_data["startTime"] + timedelta(minutes=60)).time().strftime("%H:%M:%S")

    # Apply mappings
    for mapping in mappings:
        source_value = booking_data.get(mapping.source_field)
        
        # Skip if source field doesn't exist
        if source_value is None and not mapping.default_value:
            if mapping.is_required:
                raise ValueError(f"Required field {mapping.source_field} not found in booking data")
            continue
            
        # Use default value if source is None
        if source_value is None:
            source_value = mapping.default_value
                
        # Handle nested fields
        if mapping.parent_path:
            parts = mapping.parent_path.split('.')
            current = payload
            for part in parts[:-1]:
                if part not in current:
                    current[part] = {}
                current = current[part]
            if parts[-1] not in current:
                current[parts[-1]] = {}
            current[parts[-1]][mapping.target_field] = source_value
        else:
            payload[mapping.target_field] = source_value
            
    return payload



def send_booking_data(booking):
    """Send booking data to integration webhook"""
    try:
        # Get all active integrations for the business
        integrations = PlatformIntegration.objects.filter(
            business=booking.business,
            is_active=True
        )
        
        if not integrations.exists():
            print(f"No active integrations found for business {booking.business.businessName}")
            return

        results = {
            'workflow': {'success': [], 'failed': []},
            'direct_api': {'success': [], 'failed': []}
        }
        
        print(f"Processing {integrations.count()} integrations for business {booking.business.businessName}")
        
        for integration in integrations:
            try:
                integration_type = 'workflow' if integration.platform_type == 'workflow' else 'direct_api'
                print(f"Processing {integration_type} integration: {integration.name}")
                
                if integration.platform_type == 'workflow':
                    # For workflow platforms, use the default payload structure
                    payload = {
                        "firstName": booking.firstName,
                        "lastName": booking.lastName,
                        "email": booking.email,
                        "phoneNumber": booking.phoneNumber,
                        "address1": booking.address1,
                        "address2": booking.address2,
                        "city": booking.city,
                        "stateOrProvince": booking.stateOrProvince,
                        "zipCode": booking.zipCode,
                        "bedrooms": booking.bedrooms,
                        "bathrooms": booking.bathrooms,
                        "squareFeet": booking.squareFeet,
                        "serviceType": booking.serviceType,
                        "cleaningDate": booking.cleaningDate.strftime('%Y-%m-%d') if booking.cleaningDate else None,
                        "startTime": booking.startTime.strftime('%H:%M') if booking.startTime else None,
                        "endTime": booking.endTime.strftime('%H:%M') if booking.endTime else None,
                        "totalPrice": float(booking.totalPrice),
                        "tax": float(booking.tax or 0),
                        "addonDishes": booking.addonDishes,
                        "addonLaundryLoads": booking.addonLaundryLoads,
                        "addonWindowCleaning": booking.addonWindowCleaning,
                        "addonPetsCleaning": booking.addonPetsCleaning,
                        "addonFridgeCleaning": booking.addonFridgeCleaning,
                        "addonOvenCleaning": booking.addonOvenCleaning,
                        "addonBaseboard": booking.addonBaseboard,
                        "addonBlinds": booking.addonBlinds,
                        "addonGreenCleaning": booking.addonGreenCleaning,
                        "addonCabinetsCleaning": booking.addonCabinetsCleaning,
                        "addonPatioSweeping": booking.addonPatioSweeping,
                        "addonGarageSweeping": booking.addonGarageSweeping
                    }
                    
                    print(f"Sending data to workflow webhook: {integration.webhook_url}")
                    # Send to webhook URL
                    response = requests.post(
                        integration.webhook_url,
                        json=payload,
                        headers={"Content-Type": "application/json"},
                        timeout=30
                    )
                    
                else:  # direct_api
                    # Create payload using field mappings
                    print(f"Creating mapped payload for {integration.name}")
                    # Convert date fields to string format before creating mapped payload
                    booking_dict = booking.__dict__.copy()
                    if 'cleaningDate' in booking_dict:
                        booking_dict['cleaningDate'] = booking.cleaningDate.strftime('%Y-%m-%d') if booking.cleaningDate else None
                    if 'startTime' in booking_dict:
                        booking_dict['startTime'] = booking.startTime.strftime('%H:%M') if booking.startTime else None
                    if 'endTime' in booking_dict:
                        booking_dict['endTime'] = booking.endTime.strftime('%H:%M') if booking.endTime else None
                    
                    payload = create_mapped_payload(booking_dict, integration)
                    
                    # Send to base URL
                    headers = {"Content-Type": "application/json"}
                    
                    # Add authentication if configured
                    if integration.auth_type == 'token' and integration.auth_data.get('token'):
                        headers['Authorization'] = f"Bearer {integration.auth_data['token']}"
                    
                    print(f"Sending data to API endpoint: {integration.base_url}")
                    response = requests.post(
                        integration.base_url,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                
                response.raise_for_status()
                print(f"Successfully sent booking data to {integration.name}", response.text)
                
                # Log successful integration
                IntegrationLog.objects.create(
                    platform=integration,
                    status='success',
                    request_data=payload,
                    response_data=response.json() if response.text else None
                )
                
                results[integration_type]['success'].append({
                    'name': integration.name,
                    'response': response.text,
                    'status_code': response.status_code
                })
                
            except Exception as e:
                error_msg = f"Error sending booking data to {integration.name}: {str(e)}"
                print(error_msg)
                
                # Log failed integration
                IntegrationLog.objects.create(
                    platform=integration,
                    status='failed',
                    request_data=payload if 'payload' in locals() else {},
                    error_message=str(e)
                )
                
                results[integration_type]['failed'].append({
                    'name': integration.name,
                    'error': str(e)
                })
                continue

        # Print summary
        print("\nIntegration Summary:")
        for int_type in ['workflow', 'direct_api']:
            print(f"\n{int_type.upper()} Integrations:")
            print(f"Success: {len(results[int_type]['success'])} integration(s)")
            print(f"Failed: {len(results[int_type]['failed'])} integration(s)")
            
            if results[int_type]['failed']:
                print("\nFailed integrations:")
                for fail in results[int_type]['failed']:
                    print(f"- {fail['name']}: {fail['error']}")

        return results

    except Exception as e:
        print(f"Error in send_booking_data: {str(e)}")
        raise Exception(f"Error in send_booking_data: {str(e)}")

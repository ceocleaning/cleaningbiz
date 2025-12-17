from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt    
import requests
from django.db import transaction
from django.core.cache import cache
from asgiref.sync import sync_to_async
import json
import threading
from datetime import datetime, timedelta
from django.utils.timezone import make_aware, is_naive
import os

from rest_framework import status
from .models import *

from accounts.models import ApiCredential, Business, BusinessSettings, CustomAddons
from bookings.models import Booking, BookingCustomAddons
from .utils import calculateAmount, calculateAddonsAmount
from integrations.models import PlatformIntegration, DataMapping, IntegrationLog
from integrations.utils import log_integration_activity
from retell_agent.models import RetellAgent
from subscription.models import UsageTracker
from retell import Retell
from django.conf import settings
from openai import OpenAI
from .utils import format_phone_number
from ai_agent.utils import convert_date_str_to_date
from accounts.timezone_utils import convert_to_utc

@csrf_exempt
def thumbtack_webhook(request, secretKey):
    """Handle incoming lead data from Thumbtack"""
    verifySecretKey = ApiCredential.objects.filter(secretKey=secretKey)
    if not verifySecretKey.exists():
        return JsonResponse({'message': 'Secret Key Not Verified'}, status=500)

    business = verifySecretKey.first().business

    if request.method == 'POST':
        # Initialize webhook log
        webhook_log = None
        
        try:
            # Extract request metadata
            metadata = {
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'content_type': request.META.get('CONTENT_TYPE'),
                'http_method': request.method,
                'headers': {
                    'content_length': request.META.get('CONTENT_LENGTH'),
                    'http_accept': request.META.get('HTTP_ACCEPT'),
                    'http_host': request.META.get('HTTP_HOST'),
                }
            }
            data = json.loads(request.body)
            print(f"Received Thumbtack webhook: {data}")
            
            # Create webhook log entry with pending status
            webhook_log = LeadsWebhookLog.objects.create(
                business=business,
                lead_source='thumbtack',
                status='pending',
                webhook_data={
                    'raw_data': data,
                    'metadata': metadata
                }
            )
            
            # Extract required fields from the webhook payload
            lead_data = data.get('data', {})
            customer_data = lead_data.get('customer', {})
            request_data = lead_data.get('request', {})
            location_data = request_data.get('location', {})
            booking_data = request_data.get('booking', {})
            estimate_data = lead_data.get('estimate', {})
            
            # Process details from request data
            details_list = request_data.get('details', [])
            details_dict = {}
            
            # Extract questions and answers from details
            for detail in details_list:
                question = detail.get('question', '')
                answer = detail.get('answer', '')
                if question and answer:
                    details_dict[question] = answer
            
            # Create separate tracking for category information
            category = request_data.get('category', {})
            category_name = category.get('name', 'Unknown') if category else 'Unknown'
            
            # Create separate tracking for proposed times
            proposed_times = request_data.get('proposedTimes', [])
            proposed_start_datetime_str = proposed_times[0].get('start')
            proposed_end_datetime_str = proposed_times[0].get('end')
            
            # Extract proposed start and end datetime
            proposed_start = None
            proposed_end = None
            
            if proposed_start_datetime_str:
                try:
                    proposed_start = datetime.fromisoformat(proposed_start_datetime_str.replace('Z', '+00:00'))
                except Exception as e:
                    print(f"Error parsing proposed start datetime: {e}")
            
            if proposed_end_datetime_str:
                try:
                    proposed_end = datetime.fromisoformat(proposed_end_datetime_str.replace('Z', '+00:00'))
                except Exception as e:
                    print(f"Error parsing proposed end datetime: {e}")
            

            # Parse estimated price
            estimated_price = None
            if estimate_data.get('total'):
                try:
                    # Remove currency symbol and commas
                    price_str = estimate_data.get('total', '0')
                    # Handle both $1,234.56 and 1234.56 formats
                    price_str = price_str.replace('$', '').replace(',', '')
                    estimated_price = float(price_str)
                except ValueError:
                    estimated_price = None
            
            
            # Create formatted notes from important details
            notes = request_data.get('description', '')
            notes += f"Service: {category_name}\n"
            notes += f"Location: {location_data.get('city', 'N/A')}, {location_data.get('state', 'N/A')}\n"
            notes += f"Estimate: {estimate_data.get('total', 'N/A')}\n\n"
            
           
                
            # Add estimate details to notes
            if estimate_data:
                notes += "\nEstimate Details:\n"
                notes += f"- Type: {estimate_data.get('type', 'N/A')}\n"
                notes += f"- Total: {estimate_data.get('total', 'N/A')}\n"
                notes += f"- Price Per Unit: {estimate_data.get('pricePerUnit', 'N/A')}\n"
                notes += f"- Unit Quantity: {estimate_data.get('unitQuantity', 'N/A')}\n"
                notes += f"- Unit Name: {estimate_data.get('unitName', 'N/A')}\n"
            
            lead = Lead.objects.create(
                business=business,
                name=f"{customer_data.get('firstName', '')} {customer_data.get('lastName', '')}".strip(),
                email=customer_data.get('email', None),  # May be None
                phone_number=customer_data.get('Phone', ''),
                
                # Address fields
                address1=location_data.get('address1', ''),
                address2=location_data.get('address2', ''),
                city=location_data.get('city', ''),
                state=location_data.get('state', ''),
                zipCode=location_data.get('zipCode', ''),
                
                # Store only request details in the JSONField
                details=details_dict,
                
                # Store datetime information
                proposed_start_datetime=proposed_start,
                proposed_end_datetime=proposed_end,
                
                # Notes and source
                notes=notes,
                content=json.dumps(data, indent=2),  # Store raw JSON as content
                source="Thumbtack",
                
                
                # Pricing
                estimatedPrice=estimated_price
            )
            
            print(f"Successfully created Thumbtack lead: {lead.leadId}")
            
            # Update webhook log to success
            if webhook_log:
                webhook_log.status = 'success'
                webhook_log.webhook_data['lead_id'] = lead.leadId
                webhook_log.save()
            
            # Track usage
            try:
                from subscription.models import UsageTracker
                UsageTracker.increment_leads(business=business, increment_by=1)
            except Exception as e:
                print(f"Error tracking lead usage: {e}")
                
            return JsonResponse({'status': 'success', 'lead_id': lead.leadId}, status=200)
            
        except Exception as e:
            print(f"Error processing Thumbtack webhook: {str(e)}")
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)
            
            # Update webhook log to failed
            if webhook_log:
                webhook_log.status = 'failed'
                webhook_log.error_message = str(e)
                webhook_log.error_code = type(e).__name__
                webhook_log.webhook_data['traceback'] = error_traceback
                webhook_log.save()
            
            return JsonResponse({'message': f'Error: {str(e)}'}, status=500)
    
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

    try:
    
        # Convert datetime fields to string format
        if "cleaningDate" in booking_data and isinstance(booking_data["cleaningDate"], datetime):
            booking_data = dict(booking_data)  # Create a copy to avoid modifying the original
            booking_data["cleaningDate"] = booking_data["cleaningDate"].date().isoformat()
            
            if "startTime" in booking_data and booking_data["startTime"]:
                # Store the datetime object before converting to string
                start_time_dt = booking_data["startTime"]
                # Calculate end time using the datetime object
                end_time_dt = start_time_dt + timedelta(minutes=60)
                # Convert to string format after calculations
                booking_data["startTime"] = start_time_dt
                booking_data["endTime"] = end_time_dt
        
        # Process mappings
        for mapping in mappings:
            # Check if it's a customer field using dot notation (customer.field_name)
            if '.' in mapping.source_field and mapping.source_field.startswith('customer.'):
                # Split to get the relationship and field name
                _, field_name = mapping.source_field.split('.', 1)
                
                # Check if customer data is available in booking_data
                if hasattr(booking_data, 'customer') and booking_data.customer:
                    value = getattr(booking_data.customer, field_name, mapping.default_value)
                else:
                    value = mapping.default_value
            else:
                # Regular booking field
                if isinstance(booking_data, dict):
                    value = booking_data.get(mapping.source_field, mapping.default_value)
                else:
                    value = getattr(booking_data, mapping.source_field, mapping.default_value)
            
            # Handle nested paths
            if mapping.parent_path:
                path_parts = mapping.parent_path.split('.')
                current_dict = payload
                
                # Create nested structure
                for part in path_parts:
                    if part not in current_dict:
                        current_dict[part] = {}
                    current_dict = current_dict[part]
                
                current_dict[mapping.target_field] = value
            else:
                payload[mapping.target_field] = value
        
        return payload
    except Exception as e:
        import traceback
        print(traceback.format_exc())
        
        print(f"Error creating payload: {str(e)}")
        return {}



@csrf_exempt
def chatgpt_analysis_webhook(request, secretKey):
    """Handle incoming JSON data, analyze it with ChatGPT, and store structured response in Lead model"""
    # Verify secret key
    verifySecretKey = ApiCredential.objects.filter(secretKey=secretKey)
    if not verifySecretKey.exists():
        return JsonResponse({'message': 'Secret Key Not Verified'}, status=401)

    business = verifySecretKey.first().business

    if request.method == 'POST':
        # Initialize webhook log
        webhook_log = None
        
        try:
            # Extract request metadata
            metadata = {
                'ip_address': request.META.get('REMOTE_ADDR'),
                'user_agent': request.META.get('HTTP_USER_AGENT'),
                'content_type': request.META.get('CONTENT_TYPE'),
                'http_method': request.method,
                'headers': {
                    'content_length': request.META.get('CONTENT_LENGTH'),
                    'http_accept': request.META.get('HTTP_ACCEPT'),
                    'http_host': request.META.get('HTTP_HOST'),
                }
            }
            # Parse incoming JSON data
            data = json.loads(request.body)
            print(f"Received data for ChatGPT analysis: {data}")
            
            # Create webhook log entry with pending status
            webhook_log = LeadsWebhookLog.objects.create(
                business=business,
                lead_source='manual_webhook',
                status='pending',
                webhook_data={
                    'raw_data': data,
                    'metadata': metadata
                }
            )
            
            # Initialize OpenAI client
            client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
            
            # Define the system prompt for analysis
            system_prompt = """
            You are a data extraction assistant. Your task is to analyze the provided JSON data 
            and extract structured information for a cleaning service lead. Extract the following fields 
            if available (leave blank if not found):
            
            1. name: Full name of the customer (String)
            2. email: Customer's email address (String)
            3. phone_number: Customer's phone number (String)
            4. bedrooms: Number of bedrooms (Number)
            5. bathrooms: Number of bathrooms (Number)
            6. squareFeet: Size of the property in square feet (Number)
            7. type_of_cleaning: Type of cleaning service requested (String)
            8. address1: Street address (String)
            9. address2: Apartment/unit number or additional address info (String)
            10. city: City name (String)
            11. state: State name (String)
            12. zipCode: ZIP/Postal code (String)
            13. proposed_start_datetime: Proposed/Preferred start date and time 
                    Discription: This is the date and time when the customer wants the cleaning to start. It Could be in any format. Human readable format or ISO format.
            14. proposed_end_datetime: Proposed/Preferred end date and time
                    Discription: This is the date and time when the customer wants the cleaning to end. It Could be in any format. Human readable format or ISO format.
            15. estimatedPrice: Estimated price for the service (Number)
            16. notes: Any additional notes or special requests (String)
            17. source: Source of the lead (if available, otherwise use "API") (String)
            
            Return ONLY a JSON object with these fields. Do not include any explanations or additional text.
            """
            
            # Call ChatGPT API to analyze the data
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Analyze this data: {json.dumps(data)}"}
                ],
                response_format={"type": "json_object"}
            )
            
            # Parse the structured response
            structured_data = json.loads(response.choices[0].message.content)
            print(f"Structured data from ChatGPT: {structured_data}")

            # Validate incoming data
            missing_fields = []
            if not structured_data.get('name'):
                missing_fields.append('name')
            if not structured_data.get('email'):
                missing_fields.append('email')
            if not structured_data.get('phone_number'):
                missing_fields.append('phone_number')

            if missing_fields:
                # Update webhook log to failed for validation error
                if webhook_log:
                    webhook_log.status = 'failed'
                    webhook_log.error_message = f'Missing required fields: {", ".join(missing_fields)}'
                    webhook_log.error_code = 'VALIDATION_ERROR'
                    webhook_log.webhook_data['missing_fields'] = missing_fields
                    webhook_log.save()
                
                return JsonResponse({
                    'message': 'Invalid Data',
                    'missing_fields': missing_fields
                }, status=400)
            
            # Extract fields for Lead model
            lead_data = {
                'business': business,
                'name': structured_data.get('name', ''),
                'email': structured_data.get('email'),
                'phone_number': format_phone_number(structured_data.get('phone_number', '')) if structured_data.get('phone_number') else None,
                'bedrooms': int(structured_data.get('bedrooms')) if structured_data.get('bedrooms') else None,
                'bathrooms': int(structured_data.get('bathrooms')) if structured_data.get('bathrooms') else None,
                'squareFeet': int(structured_data.get('squareFeet')) if structured_data.get('squareFeet') else None,
                'type_of_cleaning': structured_data.get('type_of_cleaning'),
                'address1': structured_data.get('address1'),
                'address2': structured_data.get('address2'),
                'city': structured_data.get('city'),
                'state': structured_data.get('state'),
                'zipCode': structured_data.get('zipCode'),
                'estimatedPrice': int(structured_data.get('estimatedPrice')) if structured_data.get('estimatedPrice') else None,
                'notes': structured_data.get('notes'),
                'content': json.dumps(data, indent=2),  # Store original JSON
                'source': structured_data.get('source', 'API'),
                'details': data,  # Store full original data in details field

            }


            
            # Handle datetime fields if present
            proposed_start = structured_data.get('proposed_start_datetime')
            if proposed_start:
                try:
                    proposed_start_datetime = convert_date_str_to_date(proposed_start, business)
                    utc_proposed_start_datetime = convert_to_utc(proposed_start_datetime, business.get_timezone())
                    lead_data['proposed_start_datetime'] = utc_proposed_start_datetime
                except Exception as e:
                    print(f"Error parsing proposed start datetime: {e}")
            
            proposed_end = structured_data.get('proposed_end_datetime')
            if proposed_end:
                try:
                    proposed_end_datetime = convert_date_str_to_date(proposed_end, business)
                    utc_proposed_end_datetime = convert_to_utc(proposed_end_datetime, business.get_timezone())
                    lead_data['proposed_end_datetime'] = utc_proposed_end_datetime

                except Exception as e:
                    print(f"Error parsing proposed end datetime: {e}")
            
            # Create the Lead object
            lead = Lead.objects.create(**lead_data)
            print(f"Successfully created lead from ChatGPT analysis: {lead.leadId}")
            
            # Update webhook log to success
            if webhook_log:
                webhook_log.status = 'success'
                webhook_log.webhook_data['lead_id'] = lead.leadId
                webhook_log.webhook_data['structured_data'] = structured_data
                webhook_log.save()
            
            # Track usage
            try:
                UsageTracker.increment_leads(business=business, increment_by=1)
            except Exception as e:
                print(f"Error tracking lead usage: {e}")
                
            return JsonResponse({
                'status': 'success', 
                'lead_id': lead.leadId,
                'lead_data': structured_data
            }, status=200)
            
        except json.JSONDecodeError as e:
            # Update webhook log to failed for JSON decode error
            if webhook_log:
                webhook_log.status = 'failed'
                webhook_log.error_message = 'Invalid JSON data'
                webhook_log.error_code = 'JSON_DECODE_ERROR'
                webhook_log.save()
            
            return JsonResponse({'message': 'Invalid JSON data'}, status=400)
        except Exception as e:
            print(f"Error processing ChatGPT analysis webhook: {str(e)}")
            import traceback
            error_traceback = traceback.format_exc()
            print(error_traceback)
            
            # Update webhook log to failed
            if webhook_log:
                webhook_log.status = 'failed'
                webhook_log.error_message = str(e)
                webhook_log.error_code = type(e).__name__
                webhook_log.webhook_data['traceback'] = error_traceback
                webhook_log.save()
            
            return JsonResponse({'message': f'Error: {str(e)}'}, status=500)
    
    return JsonResponse({'message': 'Method not allowed'}, status=405)


def convert_to_json_serializable(obj):
    """Convert non-JSON-serializable objects to JSON-serializable types"""
    from decimal import Decimal
    
    if isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, dict):
        return {key: convert_to_json_serializable(value) for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [convert_to_json_serializable(item) for item in obj]
    else:
        return obj

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
                        "firstName": booking.customer.first_name,
                        "lastName": booking.customer.last_name,
                        "email": booking.customer.email,
                        "phoneNumber": booking.customer.phone_number,
                        "address": booking.customer.address,
                        "city": booking.customer.city,
                        "stateOrProvince": booking.customer.state_or_province,
                        "zipCode": booking.customer.zip_code,
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
                    
                    # Convert payload to JSON-serializable format
                    payload = convert_to_json_serializable(payload)
                    
                    print(f"Sending data to workflow webhook: {integration.webhook_url}")
                    # Prepare headers
                    headers = {"Content-Type": "application/json"}
                    
                    # Add custom headers from integration if available
                    if integration.headers:
                        headers.update(integration.headers)
                    
                    # Send to webhook URL
                    response = requests.post(
                        integration.webhook_url,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )

                    # Safely parse JSON response
                    response_data = None
                    if response.text:
                        try:
                            response_data = response.json()
                        except (ValueError, requests.exceptions.JSONDecodeError):
                            # Response is not JSON, store as text
                            response_data = {'raw_response': response.text}
                    
                    # Log successful integration
                    if response.status_code in [200, 201]:
                        log_integration_activity(
                            platform=integration,
                            status='success',
                            request_data=payload,
                            response_data=response_data
                        )
                    
                    # Log failed integration
                    else:
                        log_integration_activity(
                            platform=integration,
                            status='failed',
                            request_data=payload,
                            error_message=response.text
                        )
                    
                else:  # direct_api
                    # Create payload using field mappings
                    print(f"Creating mapped payload for {integration.name}")
                    # Convert date fields to string format before creating mapped payload
                    booking_dict = booking.__dict__.copy()
                    
                    # Add customer object to booking_dict for dot notation access
                    booking_dict['customer'] = booking.customer
                    
                
                    payload = create_mapped_payload(booking_dict, integration)
                    
                    # Convert payload to JSON-serializable format
                    payload = convert_to_json_serializable(payload)
                    
                    # Send to base URL
                    headers = {"Content-Type": "application/json"}
                    
                   
                    
                    # Add custom headers from integration if available
                    if integration.headers:
                        headers.update(integration.headers)
                    
                    print(f"Sending data to API endpoint: {integration.base_url}")
                    response = requests.post(
                        integration.base_url,
                        json=payload,
                        headers=headers,
                        timeout=30
                    )
                
                    # Safely parse JSON response
                    response_data = None
                    if response.text:
                        try:
                            response_data = response.json()
                        except (ValueError, requests.exceptions.JSONDecodeError):
                            # Response is not JSON, store as text
                            response_data = {'raw_response': response.text}
                    
                    # Log successful integration
                    if response.status_code in [200, 201]:
                        log_integration_activity(
                            platform=integration,
                            status='success',
                            request_data=payload,
                            response_data=response_data
                        )
                    
                    # Log failed integration
                    else:
                        log_integration_activity(
                            platform=integration,
                            status='failed',
                            request_data=payload,
                            error_message=response.text
                        )
                    
                
                results[integration_type]['success'].append({
                    'name': integration.name,
                    'response': response.text,
                    'status_code': response.status_code
                })
                
            except Exception as e:
                import traceback
                print(traceback.format_exc())
                error_msg = f"Error sending booking data to {integration.name}: {str(e)}"
                print(error_msg)
                
                # Log failed integration
                log_integration_activity(
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

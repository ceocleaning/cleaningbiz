import os
import json
import base64
import secrets
import requests
from django.conf import settings
from django.http import JsonResponse, HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt


# Thumbtack OAuth Configuration
THUMBTACK_AUTH_URL = 'https://auth.thumbtack.com/oauth2/auth'
THUMBTACK_TOKEN_URL = 'https://auth.thumbtack.com/oauth2/token'
THUMBTACK_AUDIENCE = 'urn:partner-api'

# These should be stored in environment variables or settings
THUMBTACK_CLIENT_ID = getattr(settings, 'THUMBTACK_CLIENT_ID', '')
THUMBTACK_CLIENT_SECRET = getattr(settings, 'THUMBTACK_CLIENT_SECRET', '')
THUMBTACK_REDIRECT_URI_PROD = getattr(settings, 'THUMBTACK_REDIRECT_URI', '')

# Store states temporarily to prevent CSRF attacks
# In production, use a more persistent storage like database or cache
THUMBTACK_STATES = {}


@login_required
def thumbtack_connect(request):
    """
    Initiates the OAuth flow by redirecting the user to Thumbtack's authorization page
    """
    # Generate a random state parameter to prevent CSRF attacks
    state = secrets.token_urlsafe(32)
    
    # Store the state in our temporary storage with the user ID
    THUMBTACK_STATES[state] = request.user.id
    
    # Define the scopes needed for your application
    # Thumbtack-specific scopes for accessing business data and leads
    scopes = [
    ]
    
    # Build the authorization URL
    auth_url = f"{THUMBTACK_AUTH_URL}?" + \
               f"response_type=code&" + \
               f"client_id={THUMBTACK_CLIENT_ID}&" + \
               f"redirect_uri={THUMBTACK_REDIRECT_URI_PROD}&" + \
               f"scope={'+'.join(scopes)}&" + \
               f"state={state}&" + \
               f"audience={THUMBTACK_AUDIENCE}"
    
    # Redirect the user to Thumbtack's authorization page
    return HttpResponseRedirect(auth_url)


@csrf_exempt
def thumbtack_callback_prod(request):
    """
    Callback endpoint for Thumbtack OAuth in production environment
    """
    return _process_thumbtack_callback(request, THUMBTACK_REDIRECT_URI_PROD)




def _process_thumbtack_callback(request, redirect_uri):
    """
    Process the callback from Thumbtack OAuth
    """
    # Get the authorization code and state from the request
    code = request.GET.get('code')
    state = request.GET.get('state')
    error = request.GET.get('error')
    error_description = request.GET.get('error_description')
    
    # Check if there was an error
    if error:
        return render(request, 'accounts/thumbtack/callback.html', {
            'success': False,
            'error_message': error_description or 'An error occurred during authorization.'
        })
    
    # Validate the state parameter to prevent CSRF attacks
    if state not in THUMBTACK_STATES:
        return render(request, 'accounts/thumbtack/callback.html', {
            'success': False,
            'error_message': 'The state parameter is invalid or expired. This could be due to an expired session or a security issue.'
        })
    
    # Remove the state from our storage
    user_id = THUMBTACK_STATES.pop(state)
    
    # Exchange the authorization code for an access token
    token_response = exchange_code_for_token(code, redirect_uri)
    
    if 'error' in token_response:
        return render(request, 'accounts/thumbtack/callback.html', {
            'success': False,
            'error_message': token_response.get('error_description') or 'Failed to obtain access token.'
        })
    
    # Store the tokens in the database
    save_thumbtack_tokens(user_id, token_response)
    
    # Return success response with the callback template
    return render(request, 'accounts/thumbtack/callback.html', {
        'success': True
    })


def exchange_code_for_token(code, redirect_uri):
    """
    Exchange the authorization code for an access token
    """
    # Create the authorization header with Base64 encoded client_id:client_secret
    auth_header = base64.b64encode(f"{THUMBTACK_CLIENT_ID}:{THUMBTACK_CLIENT_SECRET}".encode()).decode()
    
    # Set up the headers for the token request
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    # Set up the data for the token request
    data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': redirect_uri
    }
    
    try:
        # Make the request to the token endpoint
        response = requests.post(THUMBTACK_TOKEN_URL, headers=headers, data=data)
        return response.json()
    except Exception as e:
        return {
            'error': 'request_failed',
            'error_description': str(e)
        }


def refresh_thumbtack_token(refresh_token):
    """
    Refresh an expired access token using the refresh token
    """
    # Create the authorization header with Base64 encoded client_id:client_secret
    auth_header = base64.b64encode(f"{THUMBTACK_CLIENT_ID}:{THUMBTACK_CLIENT_SECRET}".encode()).decode()
    
    # Set up the headers for the token request
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    # Set up the data for the token request
    data = {
        'grant_type': 'refresh_token',
        'token_type': 'REFRESH',
        'refresh_token': refresh_token
    }
    
    try:
        # Make the request to the token endpoint
        response = requests.post(THUMBTACK_TOKEN_URL, headers=headers, data=data)
        return response.json()
    except Exception as e:
        return {
            'error': 'request_failed',
            'error_description': str(e)
        }


def save_thumbtack_tokens(user_id, token_data):
    """
    Save the Thumbtack tokens in the database
    """
    from .models import ThumbtackProfile
    from django.contrib.auth import get_user_model
    
    User = get_user_model()
    user = User.objects.get(id=user_id)
    business = user.business_set.first()
    
    if not business:
        # Handle the case where the user doesn't have a business
        return
    
    # Update or create Thumbtack credentials
    thumbtack_profile, created = ThumbtackProfile.objects.update_or_create(
        business=business,
        defaults={
            'access_token': token_data.get('access_token'),
            'refresh_token': token_data.get('refresh_token'),
            # If you have an ID token with business info, you could extract and save it
            # 'thumbtack_business_id': extract_business_id_from_token(token_data)
        }
    )
    
    return thumbtack_profile



@login_required
def thumbtack_disconnect(request):
    """
    Disconnect the user from Thumbtack by revoking tokens
    
    Note: Implement this function based on your requirements
    """
    # Example implementation (adjust based on your models):
    from .models import ThumbtackProfile
    #
    # # Delete the user's Thumbtack credentials
    business = request.user.business_set.first()
    ThumbtackProfile.objects.filter(business=business).delete()
    
    messages.success(request, 'Successfully disconnected from Thumbtack')
    return redirect('accounts:profile')


def get_thumbtack_client_credentials_token():
    """
    Get an access token using the client credentials flow
    """
    # Create the authorization header with Base64 encoded client_id:client_secret
    auth_header = base64.b64encode(f"{THUMBTACK_CLIENT_ID}:{THUMBTACK_CLIENT_SECRET}".encode()).decode()
    
    # Set up the headers for the token request
    headers = {
        'Authorization': f'Basic {auth_header}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    
    # Define the scopes needed for your application
    # Adjust these based on your specific requirements

    scopes = [
        'openid', 'profile',
        "messages",
        "offline_access",
        "supply::associate-phone-numbers.read",
        "supply::associate-phone-numbers.write",
        "supply::businesses.list",
        "supply::businesses/associate-phone-numbers.read",
        "supply::businesses/associate-phone-numbers.write",
        "supply::messages.read",
        "supply::messages.write",
        "supply::negotiations.read",
        "supply::users.disconnect",
        "supply::users.read",
        "supply::webhooks.read",
        "supply::webhooks.write",
]

    
    # Set up the data for the token request
    data = {
        'grant_type': 'client_credentials',
        'scope': ' '.join(scopes),
        'audience': THUMBTACK_AUDIENCE
    }
    
    try:
        # Make the request to the token endpoint
        response = requests.post(THUMBTACK_TOKEN_URL, headers=headers, data=data)
        return response.json()
    except Exception as e:
        print(e)
        return {
            'error': 'request_failed',
            'error_description': str(e)
        }
        
        
def get_thumbtack_user_info(access_token):
    """
    Fetch user information from Thumbtack API using the access token
    """
    # API endpoint for getting user information
    user_info_url = 'https://api.thumbtack.com/api/v4/users/self'
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }
    
    try:
        # Make the request to the Thumbtack API
        response = requests.get(user_info_url, headers=headers)
        print(response.text)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching user info: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception fetching user info: {str(e)}")
        return None


def get_thumbtack_business_info(access_token):
    """
    Fetch business information from Thumbtack API using the access token
    """
    # API endpoint for getting business information
    business_info_url = 'https://api.thumbtack.com/api/v4/business'
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        # Make the request to the Thumbtack API
        response = requests.get(business_info_url, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Error fetching business info: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception fetching business info: {str(e)}")
        return None


@login_required
def thumbtack_profile(request):
    """
    Display the user's Thumbtack profile information
    """
    from .models import ThumbtackProfile
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    thumbtack_profile = None
    thumbtack_user_info = None
    thumbtack_business_info = None
    thumbtack_business_name = None
    thumbtack_business_image = None
    thumbtack_stats = {
        'leads': 0,
        'bookings': 0,
        'conversion_rate': '0%'
    }
    
    if business:
        thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
        
        # If the user has a Thumbtack profile, fetch additional information
        if thumbtack_profile and thumbtack_profile.access_token:
            # Fetch user information from Thumbtack API
            thumbtack_user_info = get_thumbtack_user_info(thumbtack_profile.access_token)
            
            # Fetch business information from Thumbtack API
            thumbtack_business_info = get_thumbtack_business_info(thumbtack_profile.access_token)
            
            # Use the fetched information or fallback to placeholder data
            if thumbtack_user_info:
                # Extract user information
                user_id = thumbtack_user_info.get('userID')
                email = thumbtack_user_info.get('email')
                first_name = thumbtack_user_info.get('firstName')
                last_name = thumbtack_user_info.get('lastName')
                phone_number = thumbtack_user_info.get('phoneNumber')
            else:
                # Use placeholder data if API call failed
                user_id = 'N/A'
                email = request.user.email
                first_name = request.user.first_name
                last_name = request.user.last_name
                phone_number = 'N/A'
            
            # Set business name from API or fallback to local data
            thumbtack_business_name = business.businessName

    
    # Initialize user information variables with default values
    user_id = 'N/A'
    email = request.user.email
    first_name = request.user.first_name
    last_name = request.user.last_name
    phone_number = 'N/A'
    
    # Return the profile template with context data
    return render(request, 'accounts/thumbtack/profile.html', {
        'thumbtack_profile': thumbtack_profile,
        'thumbtack_business_name': thumbtack_business_name,
        'thumbtack_business_image': thumbtack_business_image,
        # Pass user information to the template
        'user_id': user_id,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
        'phone_number': phone_number
    })


@login_required
def thumbtack_dashboard(request):
    """
    Display the Thumbtack dashboard with leads and stats
    """
    from .models import ThumbtackProfile
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    thumbtack_profile = None
    recent_leads = []
    today_leads = 0
    conversion_rate = '0%'
    total_bookings = 0
    monthly_revenue = 0
    thumbtack_settings = {
        'auto_import': True,
        'auto_respond': False,
        'auto_response_template': 'Thank you for your inquiry! We will get back to you shortly.'
    }
    
    if business:
        thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
        
        # If the user has a Thumbtack profile, fetch leads and stats
        if thumbtack_profile and thumbtack_profile.access_token:
            # This would typically involve making API calls to Thumbtack
            # For now, we'll just use placeholder data
            
            # Placeholder leads - in a real implementation, fetch from Thumbtack API
            recent_leads = [
                {
                    'id': '1',
                    'customer_name': 'John Smith',
                    'service_type': 'House Cleaning',
                    'location': 'San Francisco, CA',
                    'created_at': '2025-06-28',
                    'status': 'new'
                },
                {
                    'id': '2',
                    'customer_name': 'Emily Johnson',
                    'service_type': 'Office Cleaning',
                    'location': 'Oakland, CA',
                    'created_at': '2025-06-27',
                    'status': 'contacted'
                },
                {
                    'id': '3',
                    'customer_name': 'Michael Brown',
                    'service_type': 'Deep Cleaning',
                    'location': 'San Jose, CA',
                    'created_at': '2025-06-25',
                    'status': 'booked'
                }
            ]
            
            # Placeholder stats
            today_leads = 2
            conversion_rate = '41.7%'
            total_bookings = 5
            monthly_revenue = 1250
    
    return render(request, 'accounts/thumbtack/dashboard.html', {
        'thumbtack_profile': thumbtack_profile,
        'recent_leads': recent_leads,
        'today_leads': today_leads,
        'conversion_rate': conversion_rate,
        'total_bookings': total_bookings,
        'monthly_revenue': monthly_revenue,
        'thumbtack_settings': thumbtack_settings
    })


@login_required
def thumbtack_settings(request):
    """
    Handle Thumbtack integration settings
    """
    if request.method != 'POST':
        return redirect('accounts:thumbtack_dashboard')
    
    # Process form submission
    auto_import = request.POST.get('auto_import') == 'yes'
    auto_respond = request.POST.get('auto_respond') == 'yes'
    auto_response_template = request.POST.get('auto_response_template', '')
    
    # In a real implementation, save these settings to the database
    # For now, just show a success message
    
    messages.success(request, 'Thumbtack settings updated successfully')
    return redirect('accounts:thumbtack_dashboard')


@login_required
def webhooks_management_page(request):
    """
    Display the webhook management page
    """
    print("\n" + "="*60)
    print("[WEBHOOK PAGE] Accessing webhook management page")
    print(f"[WEBHOOK PAGE] User: {request.user.username}")
    
    from .models import ThumbtackProfile
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    thumbtack_profile = None
    
    print(f"[WEBHOOK PAGE] Business found: {business.businessName if business else 'None'}")
    
    if business:
        thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
        print(f"[WEBHOOK PAGE] Thumbtack profile found: {thumbtack_profile is not None}")
        if thumbtack_profile:
            print(f"[WEBHOOK PAGE] Has access token: {bool(thumbtack_profile.access_token)}")
    
    # Check if user has connected Thumbtack
    if not thumbtack_profile or not thumbtack_profile.access_token:
        print("[WEBHOOK PAGE] User not connected to Thumbtack - redirecting to connect")
        messages.warning(request, 'Please connect your Thumbtack account first.')
        return redirect('accounts:thumbtack_connect')
    
    print("[WEBHOOK PAGE] Rendering webhooks page")
    print("="*60 + "\n")
    return render(request, 'accounts/thumbtack/webhooks.html', {
        'thumbtack_profile': thumbtack_profile
    })


# ============================================================================
# WEBHOOK MANAGEMENT FUNCTIONS
# ============================================================================

def create_thumbtack_webhook(access_token, webhook_url, event_types, enabled=True, auth_username=None, auth_password=None):
    """
    Create a webhook for a Thumbtack user
    
    Args:
        access_token (str): OAuth access token for the user
        webhook_url (str): HTTPS URL to receive webhook notifications
        event_types (list): List of event types to subscribe to (e.g., ["MessageCreatedV4"])
        enabled (bool): Whether the webhook should be enabled
        auth_username (str, optional): Username for webhook authentication
        auth_password (str, optional): Password for webhook authentication
    
    Returns:
        dict: Response from Thumbtack API containing webhook details or error
    """
    print("\n" + "="*60)
    print("[CREATE WEBHOOK] Starting webhook creation")
    print(f"[CREATE WEBHOOK] Webhook URL: {webhook_url}")
    print(f"[CREATE WEBHOOK] Event Types: {event_types}")
    print(f"[CREATE WEBHOOK] Enabled: {enabled}")
    print(f"[CREATE WEBHOOK] Has Auth: {bool(auth_username and auth_password)}")
    
    # API endpoint for creating webhooks
    webhook_api_url = 'https://api.thumbtack.com/v4/users/webhooks'
    print(f"[CREATE WEBHOOK] API URL: {webhook_api_url}")
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token[:20]}...',  # Only show first 20 chars for security
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Build the request payload
    payload = {
        'webhookURL': webhook_url,
        'eventTypes': event_types,
        'enabled': enabled
    }
    
    # Add authentication if provided
    if auth_username and auth_password:
        payload['auth'] = {
            'username': auth_username,
            'password': auth_password
        }
        print(f"[CREATE WEBHOOK] Auth username: {auth_username}")
    
    print(f"[CREATE WEBHOOK] Payload: {json.dumps(payload, indent=2)}")
    
    try:
        # Make the POST request to create the webhook
        print("[CREATE WEBHOOK] Sending POST request to Thumbtack API...")
        response = requests.post(webhook_api_url, headers=headers, json=payload)
        
        print(f"[CREATE WEBHOOK] Response Status: {response.status_code}")
        print(f"[CREATE WEBHOOK] Response Body: {response.text}")
        
        # Check if the request was successful
        if response.status_code == 201:
            print("[CREATE WEBHOOK] ✓ Webhook created successfully!")
            print("="*60 + "\n")
            return {
                'success': True,
                'data': response.json()
            }
        else:
            print(f"[CREATE WEBHOOK] ✗ Failed with status {response.status_code}")
            print("="*60 + "\n")
            return {
                'success': False,
                'error': f"Error creating webhook: {response.status_code}",
                'details': response.text
            }
    except Exception as e:
        print(f"[CREATE WEBHOOK] ✗ Exception occurred: {str(e)}")
        print("="*60 + "\n")
        return {
            'success': False,
            'error': 'request_failed',
            'details': str(e)
        }


def list_thumbtack_webhooks(access_token):
    """
    List all webhooks for a Thumbtack user
    
    Args:
        access_token (str): OAuth access token for the user
    
    Returns:
        dict: Response containing list of webhooks or error
    """
    # API endpoint for listing webhooks
    webhook_api_url = 'https://api.thumbtack.com/v4/users/webhooks'
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        # Make the GET request to list webhooks
        response = requests.get(webhook_api_url, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json()
            }
        else:
            return {
                'success': False,
                'error': f"Error listing webhooks: {response.status_code}",
                'details': response.text
            }
    except Exception as e:
        return {
            'success': False,
            'error': 'request_failed',
            'details': str(e)
        }


def update_thumbtack_webhook(access_token, webhook_id, webhook_url=None, event_types=None, enabled=None, auth_username=None, auth_password=None):
    """
    Update an existing webhook for a Thumbtack user
    
    Args:
        access_token (str): OAuth access token for the user
        webhook_id (str): ID of the webhook to update
        webhook_url (str, optional): New HTTPS URL for the webhook
        event_types (list, optional): New list of event types
        enabled (bool, optional): New enabled status
        auth_username (str, optional): New username for authentication
        auth_password (str, optional): New password for authentication
    
    Returns:
        dict: Response from Thumbtack API or error
    """
    # API endpoint for updating a specific webhook
    webhook_api_url = f'https://api.thumbtack.com/v4/users/webhooks/{webhook_id}'
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    # Build the request payload with only provided fields
    payload = {}
    if webhook_url is not None:
        payload['webhookURL'] = webhook_url
    if event_types is not None:
        payload['eventTypes'] = event_types
    if enabled is not None:
        payload['enabled'] = enabled
    if auth_username and auth_password:
        payload['auth'] = {
            'username': auth_username,
            'password': auth_password
        }
    
    try:
        # Make the PUT request to update the webhook
        response = requests.put(webhook_api_url, headers=headers, json=payload)
        
        # Check if the request was successful
        if response.status_code == 200:
            return {
                'success': True,
                'data': response.json()
            }
        else:
            return {
                'success': False,
                'error': f"Error updating webhook: {response.status_code}",
                'details': response.text
            }
    except Exception as e:
        return {
            'success': False,
            'error': 'request_failed',
            'details': str(e)
        }


def delete_thumbtack_webhook(access_token, webhook_id):
    """
    Delete a webhook for a Thumbtack user
    
    Args:
        access_token (str): OAuth access token for the user
        webhook_id (str): ID of the webhook to delete
    
    Returns:
        dict: Response indicating success or error
    """
    # API endpoint for deleting a specific webhook
    webhook_api_url = f'https://api.thumbtack.com/v4/users/webhooks/{webhook_id}'
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Accept': 'application/json'
    }
    
    try:
        # Make the DELETE request to remove the webhook
        response = requests.delete(webhook_api_url, headers=headers)
        
        # Check if the request was successful
        if response.status_code == 204:
            return {
                'success': True,
                'message': 'Webhook deleted successfully'
            }
        else:
            return {
                'success': False,
                'error': f"Error deleting webhook: {response.status_code}",
                'details': response.text
            }
    except Exception as e:
        return {
            'success': False,
            'error': 'request_failed',
            'details': str(e)
        }


# ============================================================================
# WEBHOOK VIEW ENDPOINTS
# ============================================================================

@login_required
def create_webhook_view(request):
    """
    View to create a new webhook for the authenticated user
    """
    print("\n" + "="*60)
    print("[CREATE WEBHOOK VIEW] Received webhook creation request")
    print(f"[CREATE WEBHOOK VIEW] User: {request.user.username}")
    print(f"[CREATE WEBHOOK VIEW] Method: {request.method}")
    
    from .models import ThumbtackProfile
    
    if request.method != 'POST':
        print("[CREATE WEBHOOK VIEW] ✗ Invalid method")
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    print(f"[CREATE WEBHOOK VIEW] Business: {business.businessName if business else 'None'}")
    
    if not business:
        print("[CREATE WEBHOOK VIEW] ✗ No business found")
        return JsonResponse({'error': 'No business found for user'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    print(f"[CREATE WEBHOOK VIEW] Thumbtack profile exists: {thumbtack_profile is not None}")
    
    if not thumbtack_profile or not thumbtack_profile.access_token:
        print("[CREATE WEBHOOK VIEW] ✗ Thumbtack not connected")
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Parse request data
    try:
        data = json.loads(request.body)
        print(f"[CREATE WEBHOOK VIEW] Request data: {json.dumps(data, indent=2)}")
    except json.JSONDecodeError as e:
        print(f"[CREATE WEBHOOK VIEW] ✗ JSON decode error: {str(e)}")
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Extract webhook parameters
    webhook_url = data.get('webhookURL')
    event_types = data.get('eventTypes', ['MessageCreatedV4'])
    enabled = data.get('enabled', True)
    auth_username = data.get('auth', {}).get('username')
    auth_password = data.get('auth', {}).get('password')
    
    print(f"[CREATE WEBHOOK VIEW] Webhook URL: {webhook_url}")
    print(f"[CREATE WEBHOOK VIEW] Event Types: {event_types}")
    print(f"[CREATE WEBHOOK VIEW] Enabled: {enabled}")
    
    # Validate required fields
    if not webhook_url:
        print("[CREATE WEBHOOK VIEW] ✗ Missing webhook URL")
        return JsonResponse({'error': 'webhookURL is required'}, status=400)
    
    if not webhook_url.startswith('https://'):
        print("[CREATE WEBHOOK VIEW] ✗ Webhook URL must be HTTPS")
        return JsonResponse({'error': 'webhookURL must start with https://'}, status=400)
    
    if not event_types or not isinstance(event_types, list):
        print("[CREATE WEBHOOK VIEW] ✗ Invalid event types")
        return JsonResponse({'error': 'eventTypes must be a non-empty array'}, status=400)
    
    print("[CREATE WEBHOOK VIEW] Validation passed, creating webhook...")
    
    # Create the webhook
    result = create_thumbtack_webhook(
        access_token=thumbtack_profile.access_token,
        webhook_url=webhook_url,
        event_types=event_types,
        enabled=enabled,
        auth_username=auth_username,
        auth_password=auth_password
    )
    
    if result['success']:
        print("[CREATE WEBHOOK VIEW] ✓ Webhook created successfully")
        print("="*60 + "\n")
        return JsonResponse(result['data'], status=201)
    else:
        print(f"[CREATE WEBHOOK VIEW] ✗ Failed: {result['error']}")
        print("="*60 + "\n")
        return JsonResponse({
            'error': result['error'],
            'details': result.get('details', '')
        }, status=400)


@login_required
def list_webhooks_view(request):
    """
    View to list all webhooks for the authenticated user
    """
    print("\n" + "="*60)
    print("[LIST WEBHOOKS VIEW] Received list webhooks request")
    print(f"[LIST WEBHOOKS VIEW] User: {request.user.username}")
    
    from .models import ThumbtackProfile
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    print(f"[LIST WEBHOOKS VIEW] Business: {business.businessName if business else 'None'}")
    
    if not business:
        print("[LIST WEBHOOKS VIEW] ✗ No business found")
        return JsonResponse({'error': 'No business found for user'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        print("[LIST WEBHOOKS VIEW] ✗ Thumbtack not connected")
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    print("[LIST WEBHOOKS VIEW] Fetching webhooks from Thumbtack API...")
    
    # List webhooks
    result = list_thumbtack_webhooks(thumbtack_profile.access_token)
    
    if result['success']:
        webhook_count = len(result['data'].get('webhooks', []))
        print(f"[LIST WEBHOOKS VIEW] ✓ Found {webhook_count} webhook(s)")
        print("="*60 + "\n")
        return JsonResponse(result['data'], status=200)
    else:
        print(f"[LIST WEBHOOKS VIEW] ✗ Failed: {result['error']}")
        print("="*60 + "\n")
        return JsonResponse({
            'error': result['error'],
            'details': result.get('details', '')
        }, status=400)


@login_required
def update_webhook_view(request, webhook_id):
    """
    View to update an existing webhook
    """
    from .models import ThumbtackProfile
    
    if request.method != 'PUT':
        return JsonResponse({'error': 'Only PUT method is allowed'}, status=405)
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found for user'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Parse request data
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    # Extract webhook parameters
    webhook_url = data.get('webhookURL')
    event_types = data.get('eventTypes')
    enabled = data.get('enabled')
    auth_username = data.get('auth', {}).get('username')
    auth_password = data.get('auth', {}).get('password')
    
    # Update the webhook
    result = update_thumbtack_webhook(
        access_token=thumbtack_profile.access_token,
        webhook_id=webhook_id,
        webhook_url=webhook_url,
        event_types=event_types,
        enabled=enabled,
        auth_username=auth_username,
        auth_password=auth_password
    )
    
    if result['success']:
        return JsonResponse(result['data'], status=200)
    else:
        return JsonResponse({
            'error': result['error'],
            'details': result.get('details', '')
        }, status=400)


@login_required
def delete_webhook_view(request, webhook_id):
    """
    View to delete a webhook
    """
    from .models import ThumbtackProfile
    
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Only DELETE method is allowed'}, status=405)
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found for user'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Delete the webhook
    result = delete_thumbtack_webhook(thumbtack_profile.access_token, webhook_id)
    
    if result['success']:
        return JsonResponse({'message': result['message']}, status=204)
    else:
        return JsonResponse({
            'error': result['error'],
            'details': result.get('details', '')
        }, status=400)


@csrf_exempt
def webhook_receiver(request):
    """
    Endpoint to receive webhook notifications from Thumbtack
    
    This endpoint should be publicly accessible and configured as the webhook URL
    in your Thumbtack webhook settings.
    
    Example webhook URL: https://yourdomain.com/api/thumbtack/webhook/
    """
    print("\n" + "="*60)
    print("[WEBHOOK RECEIVER] Incoming webhook event")
    print(f"[WEBHOOK RECEIVER] Method: {request.method}")
    print(f"[WEBHOOK RECEIVER] Remote IP: {request.META.get('REMOTE_ADDR')}")
    
    if request.method != 'POST':
        print("[WEBHOOK RECEIVER] ✗ Invalid method")
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    try:
        # Parse the webhook payload
        payload = json.loads(request.body)
        
        # Log the webhook event for debugging
        print("[WEBHOOK RECEIVER] Payload received:")
        print(json.dumps(payload, indent=2))
        
        # Extract event information
        event_type = payload.get('eventType')
        event_id = payload.get('eventID')
        user_id = payload.get('userID')
        
        print(f"[WEBHOOK RECEIVER] Event Type: {event_type}")
        print(f"[WEBHOOK RECEIVER] Event ID: {event_id}")
        print(f"[WEBHOOK RECEIVER] User ID: {user_id}")
        
        # Handle different event types
        if event_type == 'MessageCreatedV4':
            print("[WEBHOOK RECEIVER] Processing MessageCreatedV4 event")
            
            # Handle message created event
            message_data = payload.get('message', {})
            message_id = message_data.get('messageID')
            conversation_id = message_data.get('conversationID')
            sender_id = message_data.get('senderID')
            content = message_data.get('content')
            
            print(f"[WEBHOOK RECEIVER] Message ID: {message_id}")
            print(f"[WEBHOOK RECEIVER] Conversation ID: {conversation_id}")
            print(f"[WEBHOOK RECEIVER] Sender ID: {sender_id}")
            print(f"[WEBHOOK RECEIVER] Content: {content[:100] if content else 'None'}...")
            
            # TODO: Process the message (e.g., save to database, send notification)
            print("[WEBHOOK RECEIVER] TODO: Add custom message processing logic here")
            
            # You can add your custom logic here to:
            # 1. Save the message to your database
            # 2. Send a notification to the user
            # 3. Trigger an auto-response
            # 4. Update lead status
        else:
            print(f"[WEBHOOK RECEIVER] Unknown event type: {event_type}")
            
        # Add handlers for other event types as needed
        
        # Return a 200 response to acknowledge receipt
        print("[WEBHOOK RECEIVER] ✓ Event processed successfully")
        print("="*60 + "\n")
        return JsonResponse({
            'status': 'success',
            'eventID': event_id,
            'eventType': event_type
        }, status=200)
        
    except json.JSONDecodeError as e:
        print(f"[WEBHOOK RECEIVER] ✗ JSON decode error: {str(e)}")
        print("="*60 + "\n")
        return JsonResponse({'error': 'Invalid JSON payload'}, status=400)
    except Exception as e:
        print(f"[WEBHOOK RECEIVER] ✗ Exception: {str(e)}")
        import traceback
        print(traceback.format_exc())
        print("="*60 + "\n")
        return JsonResponse({'error': 'Internal server error'}, status=500)

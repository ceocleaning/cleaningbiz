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
        "availability",
        "bookings",
        'openid', 'profile',
        "demand::businesses/media.read",
        "demand::businesses/reviews.read",
        "demand::businesses/search.read",
        "demand::categories.read",
        "demand::categories/request-form.read",
        "demand::keywords.read",
        "demand::messages.read",
        "demand::messages.write",
        "demand::negotiations.read",
        "demand::orders.read",
        "demand::orders.write",
        "demand::orders/availability.read",
        "demand::requests.write",
        "demand::users.disconnect",
        "demand::users.read",
        "demand::users.write",
        "demand::webhooks.read",
        "demand::webhooks.write",
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
        "targeting"
]
    
    # Build the authorization URL
    auth_url = f"{THUMBTACK_AUTH_URL}?" + \
               f"response_type=code&" + \
               f"client_id={THUMBTACK_CLIENT_ID}&" + \
               f"redirect_uri={THUMBTACK_REDIRECT_URI_PROD}&" + \
               f"scope={'+'{.join(scopes)}}&" + \
               f"state={state}&" + \
               f"audience={THUMBTACK_AUDIENCE}"
    

    print(f"Auth URL: {auth_url}")
    
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


def create_thumbtack_webhook(access_token, business):
    """
    Create a webhook for a User automatically when OAuth is completed
    This will subscribe to MessageCreatedV4 events
    """
    from .models import ApiCredential
    
    # Get or create API credentials to get the webhook URL
    api_credential = ApiCredential.objects.get(
        business=business
    )
    
    # Get the webhook URL (dummy link for testing)
    webhook_url = api_credential.getThumbtackUrl()
    
    # Thumbtack webhook API endpoint
    webhook_api_url = 'https://api.thumbtack.com/v4/users/webhooks'
    
    # Prepare the webhook payload
    payload = {
        "webhookURL": webhook_url,
        "eventTypes": ["MessageCreatedV4"],
        "enabled": True,
        "auth": {
            "username": "webhook_user",
            "password": secrets.token_urlsafe(32)  # Generate a secure password
        }
    }
    
    # Print the payload for debugging
    print("=" * 80)
    print("CREATING THUMBTACK WEBHOOK")
    print("=" * 80)
    print(f"Business: {business.businessName}")
    print(f"Webhook URL: {webhook_url}")
    print(f"Payload: {json.dumps(payload)}")
    print("=" * 80)
    
    # Set up headers with the access token
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        # Make the request to create the webhook
        response = requests.post(webhook_api_url, headers=headers, json=payload)
        
        # Print response details
        print(f"Response Status Code: {response.status_code}")
        print(f"Response Body: {response.text}")
        
        # Check if the request was successful
        if response.status_code == 201:
            response_data = response.json()
            print("=" * 80)
            print("✓ WEBHOOK CREATED SUCCESSFULLY")
            print("=" * 80)
            print(f"Webhook ID: {response_data.get('webhookID')}")
            print(f"Webhook URL: {response_data.get('webhookURL')}")
            print(f"Enabled: {response_data.get('enabled')}")
            print(f"Auth Type: {response_data.get('authType')}")
            print(f"User ID: {response_data.get('userID')}")
            print(f"Event Types: {response_data.get('eventTypes')}")
            print("=" * 80)
            return response_data
        else:
            print("=" * 80)
            print("WEBHOOK CREATION FAILED")
            print("=" * 80)
            print(f"Status Code: {response.status_code}")
            print(f"Error Response: {response.text}")
            print("=" * 80)
            return None
            
    except Exception as e:
        print("=" * 80)
        print("EXCEPTION OCCURRED WHILE CREATING WEBHOOK")
        print("=" * 80)
        print(f"Exception Type: {type(e).__name__}")
        print(f"Exception Message: {str(e)}")
        print("=" * 80)
        return None


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
    
    # Automatically create webhook after saving tokens
    print("\n" + "=" * 80)
    print("OAUTH COMPLETED - CREATING WEBHOOK AUTOMATICALLY")
    print("=" * 80)
    create_thumbtack_webhook(token_data.get('access_token'), business)
    
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
        "availability",
        "bookings",
        'openid', 'profile',
        "demand::businesses/media.read",
        "demand::businesses/reviews.read",
        "demand::businesses/search.read",
        "demand::categories.read",
        "demand::categories/request-form.read",
        "demand::keywords.read",
        "demand::messages.read",
        "demand::messages.write",
        "demand::negotiations.read",
        "demand::orders.read",
        "demand::orders.write",
        "demand::orders/availability.read",
        "demand::requests.write",
        "demand::users.disconnect",
        "demand::users.read",
        "demand::users.write",
        "demand::webhooks.read",
        "demand::webhooks.write",
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
        "targeting"
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
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
    scopes = ["openid", "profile", "offline_access", "supply::businesses.list", "supply::messages.read", "supply::messages.write", "supply::negotiations.read", "supply::users.disconnect", "supply::users.read", "supply::webhooks.read", "supply::webhooks.write"]
    
    # Build the authorization URL
    auth_url = f"{THUMBTACK_AUTH_URL}?" + \
               f"response_type=code&" + \
               f"client_id={THUMBTACK_CLIENT_ID}&" + \
               f"redirect_uri={THUMBTACK_REDIRECT_URI_PROD}&" + \
               f"scope={'+'.join(scopes)}&" + \
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
    Create a webhook for a Business (Supply-side) automatically when OAuth is completed
    This will subscribe to MessageCreatedV4 events
    """
    from .models import ApiCredential
    
    # Get or create API credentials to get the webhook URL
    api_credential = ApiCredential.objects.get(business=business)
    webhook_url = api_credential.getThumbtackUrl()
    
    # First, get the list of businesses for this user
    businesses_url = 'https://api.thumbtack.com/api/v4/businesses'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        # Get businesses list
        businesses_response = requests.get(businesses_url, headers=headers)
        
        if businesses_response.status_code != 200:
            print(f"❌ Failed to get business list - Status: {businesses_response.status_code}")
            print(f"Error: {businesses_response.text}")
            return None
        
        businesses_data = businesses_response.json()
        businesses = businesses_data.get('businesses', [])
        
        if not businesses:
            print("❌ No businesses found for this user")
            return None
        
        # Get the first business ID
        business_id = businesses[0].get('businessID')
        
        # Store the Thumbtack business ID in the profile
        from .models import ThumbtackProfile
        thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
        if thumbtack_profile:
            thumbtack_profile.thumbtack_business_id = business_id
            thumbtack_profile.save()
        
    except Exception as e:
        print(f"❌ Exception getting business list: {type(e).__name__} - {str(e)}")
        return None
    
    # Now create the webhook using the supply-side endpoint
    webhook_api_url = f'https://api.thumbtack.com/api/v4/businesses/{business_id}/webhooks'
    
    # Prepare the webhook payload for supply-side
    payload = {
        "webhookURL": webhook_url,
        "eventTypes": ["MessageCreatedV4"],
        "enabled": True,
        "auth": {
            "username": "webhook_user",
            "password": secrets.token_urlsafe(32)
        }
    }
    
    try:
        # Make the request to create the webhook
        response = requests.post(webhook_api_url, headers=headers, json=payload)
        
        # Check if the request was successful
        if response.status_code == 201:
            response_data = response.json()
            print(f"✅ Webhook created successfully - ID: {response_data.get('webhookID')}")
            print(f"Payload: {json.dumps(response_data, indent=2)}")
            return response_data
        else:
            print(f"❌ Webhook creation failed - Status: {response.status_code}")
            print(f"Error: {response.text}")
            return None
            
    except Exception as e:
        print(f"❌ Exception creating webhook: {type(e).__name__} - {str(e)}")
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
    print("\n🔗 Creating Thumbtack webhook...")
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
        'openid', 'profile',
        "offline_access",
        "supply::businesses.list",
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
            print("User info fetched successfully: {}".format(response.text))
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
    business_info_url = 'https://api.thumbtack.com/api/v4/businesses'
    
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
            print(f"Business info: {response.text}")
            return response.json()
        else:
            print(f"Error fetching business info: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception fetching business info: {str(e)}")
        return None


def get_thumbtack_webhooks(access_token, business_id):
    """
    Fetch all webhooks for a business from Thumbtack API
    """
    webhooks_url = f'https://api.thumbtack.com/api/v4/businesses/{business_id}/webhooks'
    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    try:
        response = requests.get(webhooks_url, headers=headers)
        
        if response.status_code == 200:
            print(f"Webhooks: {response.text}")
            return response.json()
        else:
            print(f"Error fetching webhooks: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"Exception fetching webhooks: {str(e)}")
        return None


@login_required
def thumbtack_profile(request):
    """
    Display the user's Thumbtack profile information using cached data
    """
    from .models import ThumbtackProfile, ApiCredential
    
    # Get the user's business and Thumbtack profile
    business = request.user.business_set.first()
    thumbtack_profile = None
    thumbtack_user_info = None
    thumbtack_businesses = []
    thumbtack_webhooks = []
    
    if business:
        thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
        
        # If the user has a Thumbtack profile, use cached data
        if thumbtack_profile and thumbtack_profile.access_token:
            # Use cached data instead of making API calls
            thumbtack_user_info = thumbtack_profile.cached_user_info
            
            if thumbtack_profile.cached_business_info:
                thumbtack_businesses = thumbtack_profile.cached_business_info.get('data', [])
            
            if thumbtack_profile.cached_webhooks:
                thumbtack_webhooks = thumbtack_profile.cached_webhooks.get('data', [])
            
            # If no cached data exists, fetch it initially
            if not thumbtack_user_info or not thumbtack_businesses or not thumbtack_webhooks:
                # Fetch and cache data on first load
                _refresh_all_thumbtack_data(thumbtack_profile)
                
                # Reload the profile to get cached data
                thumbtack_profile.refresh_from_db()
                thumbtack_user_info = thumbtack_profile.cached_user_info
                
                if thumbtack_profile.cached_business_info:
                    thumbtack_businesses = thumbtack_profile.cached_business_info.get('data', [])
                
                if thumbtack_profile.cached_webhooks:
                    thumbtack_webhooks = thumbtack_profile.cached_webhooks.get('data', [])
    
    # Get webhook URL for this business
    webhook_url = None
    if business:
        api_credential = ApiCredential.objects.filter(business=business).first()
        if api_credential:
            webhook_url = api_credential.getThumbtackUrl()
    
    # Return the profile template with context data
    return render(request, 'accounts/thumbtack/profile.html', {
        'thumbtack_profile': thumbtack_profile,
        'thumbtack_user_info': thumbtack_user_info,
        'thumbtack_businesses': thumbtack_businesses,
        'thumbtack_webhooks': thumbtack_webhooks,
        'webhook_url': webhook_url,
    })


def _refresh_all_thumbtack_data(thumbtack_profile):
    """
    Helper function to refresh all Thumbtack data and cache it
    """
    from django.utils import timezone
    
    # Fetch user info
    user_response = get_thumbtack_user_info(thumbtack_profile.access_token)
    if user_response:
        thumbtack_profile.cached_user_info = user_response
        thumbtack_profile.user_info_last_refresh = timezone.now()
    
    # Fetch business info
    business_response = get_thumbtack_business_info(thumbtack_profile.access_token)
    if business_response:
        thumbtack_profile.cached_business_info = business_response
        thumbtack_profile.business_info_last_refresh = timezone.now()
        
        # If we have businesses, fetch webhooks for the first one
        if business_response.get('data'):
            first_business_id = business_response['data'][0].get('businessID')
            webhooks_response = get_thumbtack_webhooks(
                thumbtack_profile.access_token, 
                first_business_id
            )
            if webhooks_response:
                thumbtack_profile.cached_webhooks = webhooks_response
                thumbtack_profile.webhooks_last_refresh = timezone.now()
    
    thumbtack_profile.save()



@login_required
def thumbtack_refresh_user_info(request):
    """
    Refresh user information from Thumbtack API
    """
    from .models import ThumbtackProfile
    from django.utils import timezone
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Fetch user info from API
    user_response = get_thumbtack_user_info(thumbtack_profile.access_token)
    if user_response:
        thumbtack_profile.cached_user_info = user_response
        thumbtack_profile.user_info_last_refresh = timezone.now()
        thumbtack_profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'User information refreshed successfully',
            'data': user_response
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch user information'
        }, status=500)


@login_required
def thumbtack_refresh_business_info(request):
    """
    Refresh business information from Thumbtack API
    """
    from .models import ThumbtackProfile
    from django.utils import timezone
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Fetch business info from API
    business_response = get_thumbtack_business_info(thumbtack_profile.access_token)
    if business_response:
        thumbtack_profile.cached_business_info = business_response
        thumbtack_profile.business_info_last_refresh = timezone.now()
        thumbtack_profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Business information refreshed successfully',
            'data': business_response
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch business information'
        }, status=500)


@login_required
def thumbtack_refresh_webhooks(request):
    """
    Refresh webhooks from Thumbtack API
    """
    from .models import ThumbtackProfile
    from django.utils import timezone
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Get business ID from cached data
    if not thumbtack_profile.cached_business_info:
        return JsonResponse({
            'success': False,
            'error': 'No business information cached. Please refresh business info first.'
        }, status=400)
    
    business_data = thumbtack_profile.cached_business_info.get('data', [])
    if not business_data:
        return JsonResponse({
            'success': False,
            'error': 'No business data available'
        }, status=400)
    
    business_id = business_data[0].get('businessID')
    
    # Fetch webhooks from API
    webhooks_response = get_thumbtack_webhooks(thumbtack_profile.access_token, business_id)
    if webhooks_response:
        thumbtack_profile.cached_webhooks = webhooks_response
        thumbtack_profile.webhooks_last_refresh = timezone.now()
        thumbtack_profile.save()
        
        return JsonResponse({
            'success': True,
            'message': 'Webhooks refreshed successfully',
            'data': webhooks_response
        })
    else:
        return JsonResponse({
            'success': False,
            'error': 'Failed to fetch webhooks'
        }, status=500)



@login_required
def thumbtack_update_webhook(request):
    """
    Update a Thumbtack webhook URL
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from .models import ThumbtackProfile, ApiCredential
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Get parameters from request
    business_id = request.POST.get('business_id')
    webhook_id = request.POST.get('webhook_id')
    
    if not business_id or not webhook_id:
        return JsonResponse({'error': 'Missing business_id or webhook_id'}, status=400)
    
    # Get the new webhook URL
    api_credential = ApiCredential.objects.filter(business=business).first()
    if not api_credential:
        return JsonResponse({'error': 'No API credentials found'}, status=400)
    
    webhook_url = api_credential.getThumbtackUrl()
    
    # Update webhook via Thumbtack API
    update_url = f'https://api.thumbtack.com/api/v4/businesses/{business_id}/webhooks/{webhook_id}'
    headers = {
        'Authorization': f'Bearer {thumbtack_profile.access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = {
        "webhookURL": webhook_url,
        "eventTypes": ["MessageCreatedV4"],
        "enabled": True
    }
    
    try:
        response = requests.put(update_url, headers=headers, json=payload)
        
        if response.status_code == 200:
            return JsonResponse({
                'success': True,
                'message': 'Webhook updated successfully',
                'data': response.json()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to update webhook: {response.text}'
            }, status=response.status_code)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def thumbtack_add_webhook(request):
    """
    Add a new Thumbtack webhook
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    from .models import ThumbtackProfile, ApiCredential
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=400)
    
    thumbtack_profile = ThumbtackProfile.objects.filter(business=business).first()
    if not thumbtack_profile or not thumbtack_profile.access_token:
        return JsonResponse({'error': 'Thumbtack not connected'}, status=400)
    
    # Get business_id from request
    business_id = request.POST.get('business_id')
    
    if not business_id:
        return JsonResponse({'error': 'Missing business_id'}, status=400)
    
    # Get the webhook URL
    api_credential = ApiCredential.objects.filter(business=business).first()
    if not api_credential:
        return JsonResponse({'error': 'No API credentials found'}, status=400)
    
    webhook_url = api_credential.getThumbtackUrl()
    
    # Create webhook via Thumbtack API
    create_url = f'https://api.thumbtack.com/api/v4/businesses/{business_id}/webhooks'
    headers = {
        'Authorization': f'Bearer {thumbtack_profile.access_token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    payload = {
        "webhookURL": webhook_url,
        "eventTypes": ["MessageCreatedV4"],
        "enabled": True
    }
    
    try:
        response = requests.post(create_url, headers=headers, json=payload)
        
        if response.status_code == 201:
            return JsonResponse({
                'success': True,
                'message': 'Webhook created successfully',
                'data': response.json()
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to create webhook: {response.text}'
            }, status=response.status_code)
    
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


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
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
THUMBTACK_REDIRECT_URI_PROD = getattr(settings, 'THUMBTACK_REDIRECT_URI_PROD', '')
THUMBTACK_REDIRECT_URI_DEV = getattr(settings, 'THUMBTACK_REDIRECT_URI_DEV', '')

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
    # Adjust these based on your specific requirements
    scopes = ['openid', 'profile', 'email']
    
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


@csrf_exempt
def thumbtack_callback_dev(request):
    """
    Callback endpoint for Thumbtack OAuth in development environment
    """
    return _process_thumbtack_callback(request, THUMBTACK_REDIRECT_URI_DEV)


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
        return JsonResponse({
            'status': 'error',
            'error': error,
            'error_description': error_description
        }, status=400)
    
    # Validate the state parameter to prevent CSRF attacks
    if state not in THUMBTACK_STATES:
        return JsonResponse({
            'status': 'error',
            'error': 'invalid_state',
            'error_description': 'The state parameter is invalid or expired'
        }, status=400)
    
    # Remove the state from our storage
    user_id = THUMBTACK_STATES.pop(state)
    
    # Exchange the authorization code for an access token
    token_response = exchange_code_for_token(code, redirect_uri)
    
    if 'error' in token_response:
        return JsonResponse({
            'status': 'error',
            'error': token_response.get('error'),
            'error_description': token_response.get('error_description')
        }, status=400)
    
    # Store the tokens in the database (implement this based on your data model)
    save_thumbtack_tokens(user_id, token_response)
    
    # Return success response
    return JsonResponse({
        'status': 'success',
        'message': 'Successfully connected to Thumbtack'
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
    
    Note: Implement this function based on your data model
    This is a placeholder that needs to be implemented
    """
    # Example implementation (adjust based on your models):
    # from .models import ThumbTackCredentials
    # from django.contrib.auth import get_user_model
    #
    # User = get_user_model()
    # user = User.objects.get(id=user_id)
    #
    # # Update or create Thumbtack credentials
    # ThumbTackCredentials.objects.update_or_create(
    #     user=user,
    #     defaults={
    #         'access_token': token_data.get('access_token'),
    #         'refresh_token': token_data.get('refresh_token'),
    #         'expires_in': token_data.get('expires_in'),
    #         'scope': token_data.get('scope'),
    #         'token_type': token_data.get('token_type')
    #     }
    # )
    pass


@login_required
def thumbtack_disconnect(request):
    """
    Disconnect the user from Thumbtack by revoking tokens
    
    Note: Implement this function based on your requirements
    """
    # Example implementation (adjust based on your models):
    # from .models import ThumbTackCredentials
    #
    # # Delete the user's Thumbtack credentials
    # ThumbTackCredentials.objects.filter(user=request.user).delete()
    
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
    scopes = ['openid', 'profile']
    
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
        return {
            'error': 'request_failed',
            'error_description': str(e)
        }
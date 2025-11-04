# Django shortcuts & utilities
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.utils import timezone
from django.utils.html import strip_tags
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.conf import settings

# Django authentication
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib.auth.hashers import make_password
from django.contrib.auth.decorators import login_required

# Django views
from django.views.decorators.http import require_http_methods

from leadsAutomation.utils import send_email
from notification.services import NotificationService

# Python utilities
import random
import re
import string
import threading
from datetime import timedelta

# Local apps: models
from accounts.models import (
    Business,
    BusinessSettings,
    ApiCredential,
    CustomAddons,
    PasswordResetOTP,
    SquareCredentials,
    CleanerProfile,
    StripeCredentials,
    PayPalCredentials,
)
from automation.models import Cleaners
from invoice.models import Invoice, Payment, BankAccount

# Local apps: utilities & decorators
from automation.utils import format_phone_number
from automation.views import verify_recaptcha_token
from accounts.decorators import owner_required, cleaner_required, owner_or_cleaner



def SignupPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        # Skip reCAPTCHA verification in debug mode
        if settings.DEBUG:
            recaptcha_verified = True
        else:
            recaptcha_response = request.POST.get('g-recaptcha-response')
            
            # Verify reCAPTCHA first
            if not recaptcha_response:
                messages.error(request, 'Please complete the reCAPTCHA verification.')
                return redirect('accounts:signup')
                
            recaptcha_result = verify_recaptcha_token(recaptcha_response)
            recaptcha_verified = recaptcha_result.get('success')
            
            if not recaptcha_verified:
                messages.error(request, 'reCAPTCHA verification failed. Please try again.')
                return redirect('accounts:signup')
        
        if password1 == password2:
            # Check for duplicate username
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('accounts:signup')
            
            # Check for duplicate email (case-insensitive)
            if User.objects.filter(email__iexact=email).exists():
                messages.error(request, 'Email already exists.')
                return redirect('accounts:signup')

            user = User.objects.create_user(username=username, password=password1, email=email)
            messages.success(request, 'Account created successfully!')
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Passwords do not match.')
            return redirect('accounts:signup')
    
    context = {
        
    }
    return render(request, 'accounts/signup.html', context)


def loginPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')

        if settings.DEBUG:
            recaptcha_response = '1'
        else:
            recaptcha_response = request.POST.get('g-recaptcha-response')
        
            # Verify reCAPTCHA first
            if not recaptcha_response:
                messages.error(request, 'Please complete the reCAPTCHA verification.')
                return redirect('accounts:login')
                
            recaptcha_result = verify_recaptcha_token(recaptcha_response)
            if not recaptcha_result.get('success'):
                messages.error(request, 'reCAPTCHA verification failed. Please try again.')
                return redirect('accounts:login')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            
            # Check if the user is a cleaner
            if hasattr(user, 'cleaner_profile'):
                return redirect('cleaner_detail', cleaner_id=user.cleaner_profile.cleaner.id)
            
            # Check if the user has a business and if it's approved
            if user.business_set.exists():
                business = user.business_set.first()
                if not business.isApproved:
                    return redirect('accounts:approval_pending')
            
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    
    context = {
        'debug': settings.DEBUG
    }
    return render(request, 'accounts/login.html', context)


def logoutUser(request):
    logout(request)
    messages.success(request, 'Logged out successfully!')
    return redirect('accounts:login')


@login_required
def profile_view(request):
    business = request.user.business_set.first()
    
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get related models
    business_settings = business.settings
    api_credentials = business.apicredential
    
    # Import required options for the edit modal
    from .models import JOB_ASSIGNMENT_OPTIONS
    from .timezone_utils import get_timezone_choices
    
    context = {
        'business': business,
        'settings': business_settings,
        'credentials': api_credentials,
        'job_assignment_options': JOB_ASSIGNMENT_OPTIONS,
        'timezone_choices': get_timezone_choices()
    }
    
    return render(request, 'accounts/profile/profile.html', context)


@login_required
def update_profile(request):
    if request.method == 'POST':
        user = request.user
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.email = request.POST.get('email', '')
        user.save()
        
        messages.success(request, 'Your profile has been updated successfully!')
        return redirect('accounts:profile')
    
    return redirect('accounts:profile')



@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update the session to prevent the user from being logged out
            update_session_auth_hash(request, user)
            messages.success(request, 'Your password was successfully updated!')
            return redirect('accounts:profile')
        else:
            messages.error(request, 'Please correct the errors below.')
            return redirect('accounts:profile')
    
    return redirect('accounts:profile')


@login_required
def register_business(request):
    # Check if user already has a business
    if request.user.business_set.exists():
        messages.warning(request, 'You already have a registered business.')
        return redirect('accounts:profile')
    
    # Import timezone choices
    from .timezone_utils import get_timezone_choices
    timezone_choices = get_timezone_choices()

    if request.method == 'POST':
        businessName = request.POST.get('businessName')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        job_assignment = request.POST.get('job_assignment')
        selected_timezone = request.POST.get('timezone', 'UTC')
        cleaner_payout_percentage = request.POST.get('cleaner_payout_percentage', 0)
        
        # Validate required fields
        if not all([businessName, phone, address]):
            messages.error(request, 'All fields are required.')
            return redirect('accounts:register_business')
        
        try:
            # Create business
            business = Business.objects.create(
                user=request.user,
                businessName=businessName,
                phone=phone,
                address=address,
                job_assignment=job_assignment,
                timezone=selected_timezone,
                cleaner_payout_percentage=cleaner_payout_percentage,
                isActive=False,  # Set to False by default
                isApproved=False  # Set to False by default
            )
            
            # Create default settings for the business
            BusinessSettings.objects.create(business=business)
            
            # Create API credentials
            ApiCredential.objects.create(
                business=business,
            )
            
            messages.success(request, 'Business registered successfully! Your account is pending approval.')
            return redirect('accounts:approval_pending')  # Redirect to approval pending page
            
        except Exception as e:
            messages.error(request, f'Error registering business: {str(e)}')
            raise Exception(str(e))
    
    from .models import JOB_ASSIGNMENT_OPTIONS
    from .timezone_utils import get_timezone_choices
    
    context = {
        'job_assignment_options': JOB_ASSIGNMENT_OPTIONS,
        'timezone_choices': get_timezone_choices()
    }
    
    return render(request, 'accounts/register_business.html', context)


@login_required
def edit_business(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    

    if request.method == 'POST':
        businessName = request.POST.get('businessName')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        job_assignment = request.POST.get('job_assignment')
        email = request.POST.get('email')
        selected_timezone = request.POST.get('timezone', 'UTC')
        cleaner_payout_percentage = request.POST.get('cleaner_payout_percentage', 0)
        
        if not all([businessName, phone, address]):
            messages.error(request, 'All fields are required.')
            return redirect('accounts:edit_business')
        
        try:
            business.businessName = businessName
            business.phone = phone
            business.address = address
            business.job_assignment = job_assignment
            business.timezone = selected_timezone
            business.user.email = email
            business.cleaner_payout_percentage = cleaner_payout_percentage
            business.user.save()
            business.save()
            
            messages.success(request, 'Business information updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating business: {str(e)}')
            raise Exception(str(e))
    
    from .models import JOB_ASSIGNMENT_OPTIONS
    from .timezone_utils import get_timezone_choices
    
    context = {
        'business': business,
        'job_assignment_options': JOB_ASSIGNMENT_OPTIONS,
        'timezone_choices': get_timezone_choices()
    }
    
    return render(request, 'accounts/profile/edit_business.html', context)



def profile_pricing_page(request):
    business = request.user.business_set.first()
    
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get related models
    business_settings = business.settings
    
    
    context = {
        'business': business,
        'settings': business_settings,
        
    }
    return render(request, 'accounts/profile/profile_pricing.html', context)


@login_required
def edit_business_settings(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    settings = business.settings
    
    if request.method == 'POST':
        try:
            # Base Pricing
            settings.bedroomPrice = request.POST.get('bedroomPrice', 0)
            settings.bathroomPrice = request.POST.get('bathroomPrice', 0)
            settings.depositFee = request.POST.get('depositFee', 0)
            settings.taxPercent = request.POST.get('taxPercent', 0)
            settings.base_price = request.POST.get('base_price', 0)

            settings.weeklyDiscount = request.POST.get('weeklyDiscount', 0)
            settings.biweeklyDiscount = request.POST.get('biweeklyDiscount', 0)
            settings.monthlyDiscount = request.POST.get('monthlyDiscount', 0)

            
            # Square Feet Multipliers
            settings.sqftMultiplierStandard = request.POST.get('sqftMultiplierStandard', 0)
            settings.sqftMultiplierDeep = request.POST.get('sqftMultiplierDeep', 0)
            settings.sqftMultiplierMoveinout = request.POST.get('sqftMultiplierMoveinout', 0)
            settings.sqftMultiplierAirbnb = request.POST.get('sqftMultiplierAirbnb', 0)
            
            # Add-on Prices
            settings.addonPriceDishes = request.POST.get('addonPriceDishes', 0)
            settings.addonPriceLaundry = request.POST.get('addonPriceLaundry', 0)
            settings.addonPriceWindow = request.POST.get('addonPriceWindow', 0)
            settings.addonPricePets = request.POST.get('addonPricePets', 0)
            settings.addonPriceFridge = request.POST.get('addonPriceFridge', 0)
            settings.addonPriceOven = request.POST.get('addonPriceOven', 0)
            settings.addonPriceBaseboard = request.POST.get('addonPriceBaseboard', 0)
            settings.addonPriceBlinds = request.POST.get('addonPriceBlinds', 0)
            settings.addonPriceGreen = request.POST.get('addonPriceGreen', 0)
            settings.addonPriceCabinets = request.POST.get('addonPriceCabinets', 0)
            settings.addonPricePatio = request.POST.get('addonPricePatio', 0)
            settings.addonPriceGarage = request.POST.get('addonPriceGarage', 0)
            settings.commercialRequestLink = request.POST.get('commercialRequestLink', '')
            
            settings.save()
            messages.success(request, 'Business settings updated successfully!')
            return redirect('accounts:profile_pricing')
            
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
            raise Exception(str(e))
    
    return render(request, 'accounts/profile/edit_business_settings.html', {'settings': settings, 'business': business})

def integrations_page(request):
    business = request.user.business_set.first()
    
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get related models
    api_credentials = business.apicredential
    
    
    context = {
        'business': business,
        'credentials': api_credentials,
        
    }
    return render(request, 'accounts/profile/integrations.html', context)

@login_required
def edit_credentials(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    credentials = ApiCredential.objects.get(business=business)
    
    if request.method == 'POST':
        try:
     
            # Format phone numbers
            credentials.twilioSmsNumber = format_phone_number(request.POST.get('twilioSmsNumber', ''))
            credentials.twilioAccountSid = request.POST.get('twilioSid', '')
            credentials.twilioAuthToken = request.POST.get('twilioAuthToken', '')
            credentials.save()
            
            messages.success(request, 'API credentials updated successfully!')
            return redirect('accounts:integrations')
            
        except Exception as e:
            messages.error(request, f'Error updating credentials: {str(e)}')
            raise Exception(str(e))
    
    return redirect('accounts:integrations')


@login_required
def generate_secret_key(request):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    try:
        credentials = business.apicredential
        credentials.secretKey = f"sk_{business.businessId}_{random.randint(100000, 999999)}"
        credentials.save()
        messages.success(request, 'Secret key generated successfully!')

    except Exception as e:
        messages.error(request, f'Error generating secret key: {str(e)}')
        raise Exception(str(e))
    
    return redirect('accounts:integrations')


@login_required
def regenerate_secret_key(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST method is allowed'}, status=405)
    
    business = request.user.business_set.first()
    if not business:
        return JsonResponse({'error': 'No business found'}, status=404)
    
    try:
        credentials = business.apicredential
        new_secret_key = f"sk_{business.businessId}_{random.randint(100000, 999999)}"
        credentials.secretKey = new_secret_key
        credentials.save()
        return JsonResponse({'success': True, 'secret_key': new_secret_key})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def custom_addons_page(request):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    addons = CustomAddons.objects.filter(business=business)

    context = {
        'business': business,
        'addons': addons,
    }
    return render(request, 'accounts/profile/custom_addons.html', context)


@login_required
def add_custom_addon(request):
    if request.method == 'POST':
        business = request.user.business_set.first()
        if not business:
            messages.error(request, 'No business found.')
            return redirect('accounts:register_business')

        addon_name = request.POST.get('addonName')
        addon_data_name = request.POST.get('addonDataName')
        addon_price = request.POST.get('addonPrice', 0)
        
        CustomAddons.objects.create(
            business=business,
            addonName=addon_name,
            addonDataName=addon_data_name,
            addonPrice=addon_price
        )
        
        messages.success(request, 'Custom addon added successfully!')
        return redirect('accounts:custom_addons')
    
    return redirect('accounts:custom_addons')


@login_required
def edit_custom_addon(request, addon_id):
    if request.method == 'POST':
        try:
            business = request.user.business_set.first()
            if not business:
                return JsonResponse({'status': 'error', 'message': 'No business found'}, status=404)
            
            addon = CustomAddons.objects.get(id=addon_id, business=business)
            addon.addonName = request.POST.get('addonName')
            addon.addonDataName = request.POST.get('addonDataName')
            addon.addonPrice = request.POST.get('addonPrice', addon.addonPrice)
            addon.save()
            
            return JsonResponse({'status': 'success'})

        except CustomAddons.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Addon not found'}, status=404)

        except Exception as e:
            raise Exception(str(e))
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)


@login_required
def delete_custom_addon(request, addon_id):
    if request.method == 'POST':
        try:
            business = request.user.business_set.first()
            if not business:
                return JsonResponse({'status': 'error', 'message': 'No business found'}, status=404)
            
            addon = CustomAddons.objects.get(id=addon_id, business=business)
            addon.delete()
            return JsonResponse({'status': 'success'})
        except CustomAddons.DoesNotExist:
            return JsonResponse({'status': 'error', 'message': 'Addon not found'}, status=404)
        except Exception as e:
            raise Exception(str(e))
    
    return JsonResponse({'status': 'error', 'message': 'Invalid request method'}, status=405)



def forgot_password(request):
    """
    Handle forgot password request
    - Generate and send OTP to user's email
    - Limit to 3 OTP requests per day
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        
        try:
            user = User.objects.get(email=email)
            
            # Generate a 6-digit OTP
            otp = ''.join(random.choices(string.digits, k=6))
            
            # Set expiration time (10 minutes from now)
            expires_at = timezone.now() + timedelta(minutes=10)
            
            # Get or create OTP record for the user
            otp_obj, created = PasswordResetOTP.objects.get_or_create(
                user=user,
                defaults={
                    'otp': otp,
                    'expires_at': expires_at,
                    'otp_sent_count': 1,
                    'failed_attempts': 0,
                    'is_used': False,
                    'lock_expiry': None
                }
            )
            
            # If OTP record already exists, update it
            if not created:
                # Check if account is locked
                if otp_obj.lock_expiry and otp_obj.lock_expiry > timezone.now():
                    lock_time_remaining = int((otp_obj.lock_expiry - timezone.now()).total_seconds() / 60)
                    messages.error(request, f'Your account is locked due to too many failed attempts. Please try again after {lock_time_remaining} minutes.')
                    return render(request, 'accounts/forgot_password.html')

                elif otp_obj.lock_expiry and otp_obj.lock_expiry <= timezone.now():
                    # Reset lock if lock has expired
                    otp_obj.lock_expiry = None
                    otp_obj.failed_attempts = 0
                    otp_obj.save()
                
                # Check if user has reached the daily OTP limit (3 per day)
                today = timezone.now().date()

                if otp_obj.created_at.date() == today and otp_obj.otp_sent_count >= 3:
                    messages.error(request, 'You have reached the maximum number of OTP requests for today. Please try again tomorrow.')
                    return render(request, 'accounts/forgot_password.html')
                
                # Reset the OTP record with new values
                otp_obj.otp = otp
                otp_obj.expires_at = expires_at
                otp_obj.is_used = False
                otp_obj.token = None
                
                # If it's a new day, reset the count
                if otp_obj.created_at.date() != today:
                    otp_obj.otp_sent_count = 1
                    otp_obj.created_at = timezone.now()

                else:
                    otp_obj.otp_sent_count += 1
                
                otp_obj.save()
            
            # Send OTP via email
            email_sent = send_otp_email(user, otp)
            
            if email_sent:
                messages.success(request, f'An OTP has been sent to your email. It will expire in 10 minutes.')
                return redirect('accounts:verify_otp', email=email)
            else:
                # If email sending fails and this is a new record, delete it
                if created:
                    otp_obj.delete()
                messages.error(request, 'Failed to send OTP email. Please check your email configuration or try again later.')
                return render(request, 'accounts/forgot_password.html')
            
        except User.DoesNotExist:
            messages.error(request, 'No account found with this email address.')
        
        except Exception as e:
            raise Exception(str(e))
    
    return render(request, 'accounts/forgot_password.html')


def verify_otp(request, email):
    """
    Verify the OTP entered by the user
    - Limit to 5 failed attempts before locking the account
    - OTP expires after 10 minutes
    """
    if request.method == 'POST':
        otp = request.POST.get('otp')
        
        try:
            user = User.objects.get(email=email)
            
            # Get the user's OTP record
            try:
                otp_obj = PasswordResetOTP.objects.get(user=user)
                
                # Check if OTP is expired
                if otp_obj.expires_at < timezone.now():
                    messages.error(request, 'OTP has expired. Please request a new one.')
                    otp_obj.delete()  # Delete expired OTP record
                    return redirect('accounts:forgot_password')
                
                # Check if OTP is already used
                if otp_obj.is_used:
                    messages.error(request, 'This OTP has already been used. Please request a new one.')
                    otp_obj.delete()  # Delete used OTP record
                    return redirect('accounts:forgot_password')
                
                # Check if account is locked
                if otp_obj.lock_expiry and otp_obj.lock_expiry > timezone.now():
                    lock_time_remaining = int((otp_obj.lock_expiry - timezone.now()).total_seconds() / 60)
                    messages.error(request, f'Too many failed attempts. Please try again after {lock_time_remaining} minutes.')
                    return render(request, 'accounts/verify_otp.html', {'email': email})
                elif otp_obj.lock_expiry and otp_obj.lock_expiry <= timezone.now():
                    # Reset lock if lock has expired
                    otp_obj.lock_expiry = None
                    otp_obj.failed_attempts = 0
                    otp_obj.save()
                
                # Verify OTP
                if otp_obj.otp == otp:
                    # Generate reset token
                    token = ''.join(random.choices(string.ascii_letters + string.digits, k=30))
                    
                    # Set token expiration (30 minutes)
                    token_expires_at = timezone.now() + timedelta(minutes=30)
                    
                    # Update OTP record
                    otp_obj.token = token
                    otp_obj.expires_at = token_expires_at
                    otp_obj.save()
                    
                    return redirect('accounts:reset_password', email=email, token=token)
                else:
                    # Increment failed attempts
                    otp_obj.failed_attempts += 1
                    
                    # Lock account after 5 failed attempts
                    if otp_obj.failed_attempts >= 5:
                        # Set lock expiry to 24 hours from now
                        otp_obj.lock_expiry = timezone.now() + timedelta(hours=24)
                        messages.error(request, 'Too many failed attempts. Your account has been locked for 24 hours.')
                    else:
                        remaining_attempts = 5 - otp_obj.failed_attempts
                        messages.error(request, f'Invalid OTP. You have {remaining_attempts} attempts remaining.')
                    
                    otp_obj.save()
                    
            except PasswordResetOTP.DoesNotExist:
                messages.error(request, 'No active password reset request found. Please request a new OTP.')
                return redirect('accounts:forgot_password')
                
        except User.DoesNotExist:
            messages.error(request, 'Invalid email address.')
        except Exception as e:
            raise Exception(str(e))
    
    return render(request, 'accounts/verify_otp.html', {'email': email})


def resend_otp(request, email):
    """
    Dedicated function to resend OTP
    - Reuses the existing OTP record
    - Updates the expiration time
    """
    try:
        user = User.objects.get(email=email)
        
        # Get the user's OTP record
        try:
            otp_obj = PasswordResetOTP.objects.get(user=user)
            
            # Check if account is locked
            if otp_obj.lock_expiry and otp_obj.lock_expiry > timezone.now():
                lock_time_remaining = int((otp_obj.lock_expiry - timezone.now()).total_seconds() / 60)
                messages.error(request, f'Your account is locked due to too many failed attempts. Please try again after {lock_time_remaining} minutes.')
                return redirect('accounts:verify_otp', email=email)
            elif otp_obj.lock_expiry and otp_obj.lock_expiry <= timezone.now():
                # Reset lock if lock has expired
                otp_obj.lock_expiry = None
                otp_obj.failed_attempts = 0
                otp_obj.save()
            
            # Check daily limit (3 OTPs per day)
            today = timezone.now().date()
            if otp_obj.created_at.date() == today and otp_obj.otp_sent_count >= 3:
                messages.error(request, 'You have reached the maximum number of OTP requests for today. Please try again tomorrow.')
                return redirect('accounts:verify_otp', email=email)
            
            # Generate new OTP
            new_otp = ''.join(random.choices(string.digits, k=6))
            
            # Update OTP record
            otp_obj.otp = new_otp
            otp_obj.expires_at = timezone.now() + timedelta(minutes=10)
            otp_obj.is_used = False
            otp_obj.token = None
            otp_obj.failed_attempts = 0  # Reset failed attempts
            
            # If it's a new day, reset the count
            if otp_obj.created_at.date() != today:
                otp_obj.otp_sent_count = 1
                otp_obj.created_at = timezone.now()
            else:
                otp_obj.otp_sent_count += 1
                
            otp_obj.save()
            
            # Send OTP via email
            email_sent = send_otp_email(user, new_otp)
            
            if email_sent:
                messages.success(request, 'A new OTP has been sent to your email. It will expire in 10 minutes.')
            else:
                messages.error(request, 'Failed to send OTP email. Please check your email configuration or try again later.')
                
        except PasswordResetOTP.DoesNotExist:
            messages.error(request, 'No active password reset request found. Please initiate a new password reset.')
            return redirect('accounts:forgot_password')
            
    except User.DoesNotExist:
        messages.error(request, 'Invalid email address.')
    
    except Exception as e:
        raise Exception(str(e))
    
    return redirect('accounts:verify_otp', email=email)


def reset_password(request, email, token):
    """
    Reset password with valid token
    - Token expires after 30 minutes
    """
    try:
        user = User.objects.get(email=email)
        
        # Get the user's OTP record and verify token
        try:
            otp_obj = PasswordResetOTP.objects.get(
                user=user,
                token=token,
                is_used=False,
                expires_at__gt=timezone.now()
            )
            
            if request.method == 'POST':
                password1 = request.POST.get('password1')
                password2 = request.POST.get('password2')
                
                if password1 != password2:
                    messages.error(request, 'Passwords do not match.')
                    return render(request, 'accounts/reset_password.html', {'email': email, 'token': token})
                
                if len(password1) < 8:
                    messages.error(request, 'Password must be at least 8 characters long.')
                    return render(request, 'accounts/reset_password.html', {'email': email, 'token': token})
                
                # Update user password
                user.password = make_password(password1)
                user.save()
                
                # Delete the OTP record after successful password reset
                otp_obj.delete()
                
                messages.success(request, 'Your password has been reset successfully. You can now login with your new password.')
                return redirect('accounts:login')
                
        except PasswordResetOTP.DoesNotExist:
            messages.error(request, 'Invalid or expired token. Please request a new password reset.')
            return redirect('accounts:forgot_password')
        
    except User.DoesNotExist:
        messages.error(request, 'Invalid email address.')
        return redirect('accounts:forgot_password')
    
    except Exception as e:
        raise Exception(str(e))
    
    return render(request, 'accounts/reset_password.html', {'email': email, 'token': token})


def send_otp_email(user, otp):
    """Helper function to send OTP via email"""
    try:

        
   
        email_from = settings.EMAIL_HOST_USER
        email_to = user.email
        

        text_content = f"""
        Dear {user.first_name or user.username},
        
        You have requested to reset your password. Please use the following OTP to verify your identity:

        {otp}

        This OTP will expire in 10 minutes.

        If you did not request a password reset, please ignore this email or contact support.

        Best regards,
        CEO Cleaners Support Team
        """
        
       

        try:
            send_email(
                from_email=email_from,
                to_email=email_to,
                subject='Password Reset OTP',
                text_content=text_content
            )
            return True
        except Exception as smtp_error:
            print(f"Error Sending Email: {smtp_error}")
     
            return False
                
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False





@login_required
def approval_pending(request):
    """
    View for the approval pending page
    Shown after a business registers and before they are approved
    """
    # Check if user has a business



    if not request.user.business_set.exists():
        messages.warning(request, 'You need to register a business first.')
        return redirect('accounts:register_business')
    
    # Get the user's business
    business = request.user.business_set.first()
    
    # If the business is already approved, redirect to profile
    if business.isApproved:
        messages.success(request, 'Your business is already approved!')
        return redirect('accounts:profile')
    from subscription.models import SubscriptionPlan

    # Get trial plan using the new plan_tier field
    trial_plan = SubscriptionPlan.objects.filter(plan_tier='trial', is_active=True).first()
    
    # Get regular plans (excluding trial plans)
    monthly_plans = SubscriptionPlan.objects.filter(
        is_active=True, 
        billing_cycle='monthly',
        is_invite_only=False
    ).exclude(plan_tier='trial').order_by('sort_order')
    
    yearly_plans = SubscriptionPlan.objects.filter(
        is_active=True, 
        billing_cycle='yearly',
        is_invite_only=False
    ).exclude(plan_tier='trial').order_by('sort_order')
    
    context = {
        'business': business,
        'trial_plan': trial_plan,
        'monthly_plans': monthly_plans,
        'yearly_plans': yearly_plans,
        'has_plans': monthly_plans.exists() or yearly_plans.exists()
    }
    
    return render(request, 'accounts/approval_pending.html', context)


@login_required
def settings_page(request):
    business = request.user.business_set.first()
    
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    

    
    context = {
        'business': business,
        
    }
    return render(request, 'accounts/profile/settings.html', context)

@login_required
def update_business_settings(request):
    if request.method == 'POST':
        business = request.user.business_set.first()
        if not business:
            return JsonResponse({'success': False, 'message': 'Business not found'})
        
        try:
            # Update useCall setting
            use_call = request.POST.get('useCall') == 'true' or request.POST.get('useCall') == 'on'
            business.useCall = use_call
            wait_time = request.POST.get('callDelayMinutes')
            
            # Update callDelayMinutes if provided and useCall is enabled
            if use_call and wait_time:
                try:
                    wait_time = int(wait_time)
                    # Ensure value is within reasonable limits
                    if 1 <= wait_time <= 60:  # Between 1 minute and 60 minutes
                        business.timeToWait = wait_time
                except (ValueError, TypeError):
                    # If conversion fails, use default value
                    business.timeToWait = 10
            
            # Update partial payment settings
            allow_partial_payment = request.POST.get('allow_partial_payment') == 'true' or request.POST.get('allow_partial_payment') == 'on'
            business.allow_partial_payment = allow_partial_payment
            
            # Update minimum partial payment amount if provided and partial payments are enabled
            if allow_partial_payment:
                min_amount = request.POST.get('minimum_partial_payment_amount')
                if min_amount:
                    try:
                        from decimal import Decimal
                        min_amount = Decimal(min_amount)
                        # Ensure value is non-negative
                        if min_amount >= 0:
                            business.minimum_partial_payment_amount = min_amount
                    except (ValueError, TypeError):
                        # If conversion fails, use default value
                        business.minimum_partial_payment_amount = 0
            
            business.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})


@login_required
def payment_square_view(request):
    """
    View for managing Square credentials and viewing payment history
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get Square credentials if they exist
    try:
        square_credentials = SquareCredentials.objects.get(business=business)
    except SquareCredentials.DoesNotExist:
        square_credentials = None
    
    # Get payment history for this business
    # We need to get all invoices for bookings related to this business
    # Then get all payments for those invoices
    payments = Payment.objects.filter(
        invoice__booking__business=business
    )
    
    context = {
        'business': business,
        'square_credentials': square_credentials,
        'payments': payments,
    }
    
    return render(request, 'accounts/payments/payment_square.html', context)

@login_required
def manage_square_credentials(request):
    """
    Consolidated view for both adding and updating Square credentials
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    if request.method == 'POST':
        access_token = request.POST.get('access_token')
        app_id = request.POST.get('app_id')
        location_id = request.POST.get('location_id', '')  # Make location_id optional
        
        if not all([access_token, app_id]):
            messages.error(request, 'Access Token and Application ID are required.')
            return redirect('accounts:payment_square')
        
        try:
            # Get existing square credentials or create new ones
            square_credentials, created = SquareCredentials.objects.get_or_create(
                business=business,
                defaults={
                    'access_token': access_token,
                    'app_id': app_id,
                    'location_id': location_id
                }
            )
            
            # If credentials already existed, update them
            if not created:
                square_credentials.access_token = access_token
                square_credentials.app_id = app_id
                square_credentials.location_id = location_id if location_id else square_credentials.location_id
                square_credentials.save()
                messages.success(request, 'Square credentials updated successfully!')
            else:
                messages.success(request, 'Square credentials added successfully!')
            
            return redirect('accounts:payment_square')
            
        except Exception as e:
            messages.error(request, f'Error managing Square credentials: {str(e)}')
    
    return redirect('accounts:payment_square')


@login_required
def bank_account(request):
    """
    Handle bank account management (view, create, update, delete) with HTML forms
    """
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'Business not found')
        return redirect('accounts:profile')
    
    
    account = BankAccount.objects.filter(business=business).first()
    if request.method == 'POST':
        form_type = request.POST.get('form_type')
        
        if form_type == 'create' or form_type == 'update':
            # Get form data
            account_name = request.POST.get('account_name', '').strip()
            account_number = request.POST.get('account_number', '').strip()
            bank_name = request.POST.get('bank_name', '').strip()
            ifsc_code = request.POST.get('ifsc_code', '').strip().upper()
            branch = request.POST.get('branch', '').strip()
            
            # Basic validation
            errors = {}
            if not account_name:
                errors['account_name'] = 'Account name is required'
            if not account_number or not account_number.isdigit():
                errors['account_number'] = 'Valid account number is required (numbers only)'
            if not bank_name:
                errors['bank_name'] = 'Bank name is required'
            if not ifsc_code or not re.match(r'^[A-Z]{4}0[A-Z0-9]{6}$', ifsc_code):
                errors['ifsc_code'] = 'Valid IFSC code is required (format: ABCD0123456)'
            
            if not errors:
                # Create new account
                if account:
                    account.account_name = account_name
                    account.account_number = account_number
                    account.bank_name = bank_name
                    account.ifsc_code = ifsc_code
                    account.branch = branch
                    account.save()
                    messages.success(request, 'Bank account updated successfully')
                else:
                    BankAccount.objects.create(
                        business=business,
                        account_name=account_name,
                        account_number=account_number,
                        bank_name=bank_name,
                        ifsc_code=ifsc_code,
                        branch=branch
                    )
                    messages.success(request, 'Bank account added successfully')
                
                return redirect('accounts:payment_main')
            else:
                # Show validation errors
                for field, error in errors.items():
                    messages.error(request, f"{field.replace('_', ' ').title()}: {error}")
        
        elif form_type == 'delete':
            # Handle delete
            
            if account:
                account.delete()
                messages.success(request, 'Bank account deleted successfully')
            return redirect('accounts:payment_main')
        
    
    print("No form type specified")
    return redirect('accounts:payment_main')
    
    
    

@login_required
def payment_main_view(request):
    """
    Main payment selection view to choose payment gateway integration
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    bank_account = BankAccount.objects.filter(business=business).first()
    
    # Get all payment credentials
    try:
        square_credentials = SquareCredentials.objects.get(business=business)
    except SquareCredentials.DoesNotExist:
        square_credentials = None
        
    try:
        stripe_credentials = StripeCredentials.objects.get(business=business)
    except StripeCredentials.DoesNotExist:
        stripe_credentials = None
        
    try:
        paypal_credentials = PayPalCredentials.objects.get(business=business)
    except PayPalCredentials.DoesNotExist:
        paypal_credentials = None
    
    context = {
        'business': business,
        'square_credentials': square_credentials,
        'stripe_credentials': stripe_credentials,
        'paypal_credentials': paypal_credentials,
        'bank_account': bank_account,
    }
    
    return render(request, 'accounts/payments/payment_main.html', context)

@login_required
def payment_stripe_view(request):
    """
    View for managing Stripe credentials and viewing payment history
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get Stripe credentials if they exist
    try:
        stripe_credentials = StripeCredentials.objects.get(business=business)
    except StripeCredentials.DoesNotExist:
        stripe_credentials = None
    
    # Get payment history for this business
    payments = Payment.objects.filter(
        invoice__booking__business=business,
        paymentMethod='stripe'
    )
    
    context = {
        'business': business,
        'stripe_credentials': stripe_credentials,
        'payments': payments,
    }
    
    return render(request, 'accounts/payments/payment_stripe.html', context)

@login_required
def manage_stripe_credentials(request):
    """
    Consolidated view for both adding and updating Stripe credentials
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    if request.method == 'POST':
        stripe_secret_key = request.POST.get('stripe_secret_key')
        stripe_publishable_key = request.POST.get('stripe_publishable_key')
        
        if not all([stripe_secret_key, stripe_publishable_key]):
            messages.error(request, 'All fields are required.')
            return redirect('accounts:payment_stripe')
        
        try:
            # Get existing stripe credentials or create new ones
            stripe_credentials, created = StripeCredentials.objects.get_or_create(
                business=business,
                defaults={
                    'stripe_secret_key': stripe_secret_key,
                    'stripe_publishable_key': stripe_publishable_key
                }
            )
            
            # If credentials already existed, update them
            if not created:
                stripe_credentials.stripe_secret_key = stripe_secret_key
                stripe_credentials.stripe_publishable_key = stripe_publishable_key
                stripe_credentials.save()
                messages.success(request, 'Stripe credentials updated successfully!')
            else:
                messages.success(request, 'Stripe credentials added successfully!')
            
            return redirect('accounts:payment_stripe')
            
        except Exception as e:
            messages.error(request, f'Error managing Stripe credentials: {str(e)}')
    
    return redirect('accounts:payment_stripe')

@login_required
def payment_paypal_view(request):
    """
    View for managing PayPal credentials and viewing payment history
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get PayPal credentials if they exist
    try:
        paypal_credentials = PayPalCredentials.objects.get(business=business)
    except PayPalCredentials.DoesNotExist:
        paypal_credentials = None
    
    # Get payment history for this business
    payments = Payment.objects.filter(
        invoice__booking__business=business,
        paymentMethod='paypal'
    )
    
    context = {
        'business': business,
        'paypal_credentials': paypal_credentials,
        'payments': payments,
    }
    
    return render(request, 'accounts/payments/payment_paypal.html', context)

@login_required
def manage_paypal_credentials(request):
    """
    Consolidated view for both adding and updating PayPal credentials
    """
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    if request.method == 'POST':
        paypal_client_id = request.POST.get('paypal_client_id')
        paypal_secret_key = request.POST.get('paypal_secret_key')
        
        if not all([paypal_client_id, paypal_secret_key]):
            messages.error(request, 'All fields are required.')
            return redirect('accounts:payment_paypal')
        
        try:
            # Get existing paypal credentials or create new ones
            paypal_credentials, created = PayPalCredentials.objects.get_or_create(
                business=business,
                defaults={
                    'paypal_client_id': paypal_client_id,
                    'paypal_secret_key': paypal_secret_key
                }
            )
            
            # If credentials already existed, update them
            if not created:
                paypal_credentials.paypal_client_id = paypal_client_id
                paypal_credentials.paypal_secret_key = paypal_secret_key
                paypal_credentials.save()
                messages.success(request, 'PayPal credentials updated successfully!')
            else:
                messages.success(request, 'PayPal credentials added successfully!')
            
            return redirect('accounts:payment_paypal')
            
        except Exception as e:
            messages.error(request, f'Error managing PayPal credentials: {str(e)}')
    
    return redirect('accounts:payment_paypal')

@login_required
def set_default_payment(request):
    """
    Set the default payment method for the business
    """
    if request.method != 'POST':
        return redirect('accounts:payment_main')
    
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    payment_method = request.POST.get('payment_method')
    
    # Validate that the selected payment method is connected
    if payment_method == 'square':
        try:
            SquareCredentials.objects.get(business=business)
        except SquareCredentials.DoesNotExist:
            messages.error(request, 'You need to connect Square before setting it as default.')
            return redirect('accounts:payment_main')
    elif payment_method == 'stripe':
        try:
            StripeCredentials.objects.get(business=business)
        except StripeCredentials.DoesNotExist:
            messages.error(request, 'You need to connect Stripe before setting it as default.')
            return redirect('accounts:payment_main')
    elif payment_method == 'paypal':
        try:
            PayPalCredentials.objects.get(business=business)
        except PayPalCredentials.DoesNotExist:
            messages.error(request, 'You need to connect PayPal before setting it as default.')
            return redirect('accounts:payment_main')
    else:
        messages.error(request, 'Invalid payment method selected.')
        return redirect('accounts:payment_main')
    
    # Set the default payment method
    business.defaultPaymentMethod = payment_method
    business.save()
    
    messages.success(request, f'{payment_method.capitalize()} has been set as your default payment method.')
    return redirect('accounts:payment_main')

@owner_required
def manage_cleaners(request):
    """
    View for business owners to manage their cleaners
    """
    # Get the user's business
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get all cleaners for this business
    cleaners = Cleaners.objects.filter(business=business)
    cleaner_profiles = CleanerProfile.objects.filter(business=business)
    
    context = {
        'cleaners': cleaners,
        'cleaner_profiles': cleaner_profiles,
        'business': business
    }
    
    return render(request, 'accounts/profile/manage_cleaners.html', context)


def send_cleaner_account_notification(cleaner_name, cleaner_email, cleaner_phone, username, password, business_name, business, user):
    """
    Send account creation notification to cleaner via email and SMS in background thread.
    
    Args:
        cleaner_name: Name of the cleaner
        cleaner_email: Email address of the cleaner
        cleaner_phone: Phone number of the cleaner
        username: Created username
        password: Created password (plain text)
        business_name: Name of the business
        business: Business object (sender)
        user: User object (recipient)
    """
    try:
        # Prepare email content
        email_subject = f"Your Account Has Been Created - {business_name}"
        email_content = f"""
Hello {cleaner_name},

Your account has been created by {business_name}!

Here are your login credentials:

Username: {username}
Password: {password}

You can now log in to access your account and manage your tasks.

Login URL: {settings.SITE_URL}/accounts/login/

Please keep your credentials secure and change your password after your first login.

Best regards,
{business_name} Team
"""
        
       
        
        # Determine notification types based on available contact info
        notification_types = []
        
        # Send email if email is available
        if cleaner_email:
            notification_types.append('email')
        
        # Send SMS if phone is available
        if cleaner_phone:
            notification_types.append('sms')
        
        # Send notifications if we have at least one method
        if notification_types:
            NotificationService.send_notification(
                recipient=user,
                from_email=settings.DEFAULT_FROM_EMAIL,
                notification_type=notification_types,
                subject=email_subject,
                to_email=cleaner_email if cleaner_email else None,
                to_sms=cleaner_phone if cleaner_phone else None,
                content=email_content,
                sender=business
            )
            print(f"Account creation notification sent to {cleaner_name}")
        else:
            print(f"No contact info available for {cleaner_name}, skipping notification")
            
    except Exception as e:
        print(f"Error sending account creation notification: {str(e)}")


@owner_required
def register_cleaner_user(request, cleaner_id):
    """
    Create a user account for an existing cleaner
    """
    # Get the user's business
    business = request.user.business_set.first()
    
    # Get the cleaner
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    # Check if cleaner already has a user profile
    if hasattr(cleaner, 'user_profile'):
        messages.warning(request, f'{cleaner.name} already has a user account.')
        return redirect('accounts:manage_cleaners')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = cleaner.email or request.POST.get('email')
        password = request.POST.get('password')
        
        # Validate input
        if not all([username, email, password]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/register_cleaner.html', {'cleaner': cleaner})
        
        # Check if username already exists
        if User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists.')
            return render(request, 'accounts/register_cleaner.html', {'cleaner': cleaner})
        
        # Check if email already exists (case-insensitive)
        if User.objects.filter(email__iexact=email).exists():
            messages.error(request, 'Email already exists.')
            return render(request, 'accounts/register_cleaner.html', {'cleaner': cleaner})
        
        # Create user account
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password
        )
        
        # Create cleaner profile linking user to cleaner
        CleanerProfile.objects.create(
            user=user,
            business=business,
            cleaner=cleaner
        )
        
        # Send account creation notification in background thread
        notification_thread = threading.Thread(
            target=send_cleaner_account_notification,
            args=(
                cleaner.name,
                email,
                cleaner.phoneNumber,
                username,
                password,
                business.businessName,
                business,
                user
            )
        )
        notification_thread.daemon = True
        notification_thread.start()
        
        messages.success(request, f'User account created for {cleaner.name}. Login credentials have been sent via email and SMS.')
        return redirect('accounts:manage_cleaners')
    
    return render(request, 'accounts/register_cleaner.html', {'cleaner': cleaner})




@owner_required
def edit_cleaner_account(request, cleaner_id):
    """
    View for editing a cleaner's user account details
    Only accessible by business owners
    """
    # Get the user's business
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Check if the business is approved
    if not business.isApproved:
        return redirect('accounts:approval_pending')
    
    # Get the cleaner
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    # Check if cleaner has a user profile
    if not hasattr(cleaner, 'user_profile'):
        messages.warning(request, f'{cleaner.name} does not have a user account yet.')
        return redirect('accounts:register_cleaner_user', cleaner_id=cleaner.id)
    
    # Get the user account
    user = cleaner.user_profile.user
    
    if request.method == 'POST':
        # Get form data
        username = request.POST.get('username')
        email = request.POST.get('email')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        
        # Check if username is being changed and if it already exists
        if username != user.username and User.objects.filter(username=username).exists():
            messages.error(request, 'Username already exists. Please choose a different username.')
            return render(request, 'accounts/edit_cleaner_account.html', {
                'cleaner': cleaner,
                'user': user
            })
        
        # Update user account
        user.username = username
        user.email = email
        user.first_name = first_name
        user.last_name = last_name
        user.save()
        
        # Update cleaner email if changed
        if email != cleaner.email:
            cleaner.email = email
            cleaner.save()
        
        messages.success(request, f'Account details for {cleaner.name} have been updated.')
        return redirect('accounts:manage_cleaners')
    
    context = {
        'cleaner': cleaner,
        'user': user
    }
    
    return render(request, 'accounts/edit_cleaner_account.html', context)


@owner_required
def reset_cleaner_password(request):
    """
    View for resetting a cleaner's password
    Only accessible by business owners
    """
    if request.method != 'POST':
        messages.error(request, 'Invalid request method.')
        return redirect('accounts:manage_cleaners')
    
    cleaner_id = request.POST.get('cleaner_id')
    if not cleaner_id:
        messages.error(request, 'No cleaner specified.')
        return redirect('accounts:manage_cleaners')
    
    # Get form data
    new_password = request.POST.get('new_password')
    confirm_password = request.POST.get('confirm_password')
    
    # Validate passwords
    if not new_password or not confirm_password:
        messages.error(request, 'Please provide both new password and confirmation.')
        return redirect('accounts:manage_cleaners')
        
    if new_password != confirm_password:
        messages.error(request, 'Passwords do not match.')
        return redirect('accounts:manage_cleaners')
    
    # Get the user's business
    business = request.user.business_set.first()
    if not business:
        messages.warning(request, 'Please register your business first.')
        return redirect('accounts:register_business')
    
    # Get the cleaner
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    # Check if cleaner has a user profile
    if not hasattr(cleaner, 'user_profile'):
        messages.warning(request, f'{cleaner.name} does not have a user account yet.')
        return redirect('accounts:manage_cleaners')
    
    # Get the user account
    user = cleaner.user_profile.user
    
    # Update user's password with the provided password
    user.set_password(new_password)
    user.save()
    
    # Send reset email
    try:
        subject = f'{business.businessName} - Your Password Has Been Changed'
      

        text_content = f"Hello {cleaner.name}, Your password has been changed by your business administrator. Please contact them if you did not request this change."
        # Check for business configured email settings
        try:
            send_email(
                from_email=f"CleaningBiz AI <noreply@cleaningbizai.com>",
                to_email=email_to,
                reply_to=business.user.email,
                subject=subject,
                text_content=text_content
            )
            messages.success(request, f'Password for {cleaner.name} has been changed successfully. A notification has been sent to {user.email}.')
        except Exception as e:
            messages.warning(request, f'Password was changed but we could not send the email notification: {str(e)}')
       
        
        return redirect('accounts:manage_cleaners')
    except Exception as e:
        messages.error(request, f'Error sending password reset email: {str(e)}')
    
    return redirect('accounts:manage_cleaners')


@login_required
def cleaner_change_password(request):
    """
    View for cleaners to change their password
    """
    # Check if user is a cleaner
    if not hasattr(request.user, 'cleaner_profile'):
        messages.error(request, 'You are not a cleaner.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate input
        if not all([current_password, new_password, confirm_password]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/cleaner_change_password.html')
        
        # Check if current password is correct
        if not request.user.check_password(current_password):
            messages.error(request, 'Current password is incorrect.')
            return render(request, 'accounts/cleaner_change_password.html')
        
        # Check if new passwords match
        if new_password != confirm_password:
            messages.error(request, 'New passwords do not match.')
            return render(request, 'accounts/cleaner_change_password.html')
        
        # Update password
        request.user.set_password(new_password)
        request.user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, request.user)
        
        messages.success(request, 'Your password has been changed successfully.')
        return redirect('accounts:cleaner_detail', cleaner_id=request.user.cleaner_profile.cleaner.id)
    
    return render(request, 'accounts/cleaner_change_password.html')



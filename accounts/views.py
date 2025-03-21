from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from accounts.models import Business, BusinessSettings, ApiCredential, CustomAddons, PasswordResetOTP, SMTPConfig
import random
from django.http import JsonResponse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from django.utils.html import strip_tags
from django.utils import timezone
from django.contrib.auth.hashers import make_password
from datetime import timedelta
import string
from django.conf import settings
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.core.mail import send_mail


def SignupPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if password1 == password2:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('accounts:signup')

            user = User.objects.create_user(username=username, password=password1, email=email)
            messages.success(request, 'Account created successfully!')
            login(request, user)
            return redirect('home')
        else:
            messages.error(request, 'Passwords do not match.')
            return redirect('accounts:signup')
    
    return render(request, 'accounts/signup.html')


def loginPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, 'Logged in successfully!')
            
            # Check if the user has a business and if it's approved
            if user.business_set.exists():
                business = user.business_set.first()
                if not business.isApproved:
                    return redirect('accounts:approval_pending')
            
            return redirect('home')
        else:
            messages.error(request, 'Invalid username or password.')
    
    return render(request, 'accounts/login.html')


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
    
    
    context = {
        'business': business,
        'settings': business_settings,
        'credentials': api_credentials,
        
    }
    
    return render(request, 'accounts/profile.html', context)


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
def update_credentials(request):
    if request.method == 'POST':
        credentials, created = ApiCredential.objects.get_or_create(user=request.user)
        
        # Update credentials fields
        credentials.apiKey = request.POST.get('apiKey', '')
        credentials.auth_token = request.POST.get('auth_token', '')
        credentials.twilio_number = request.POST.get('twilio_number', '')
        credentials.twilio_whatsapp_number = request.POST.get('twilio_whatsapp_number', '')
        credentials.save()
        
        messages.success(request, 'Your API credentials have been updated successfully!')
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
    

    if request.method == 'POST':
        businessName = request.POST.get('businessName')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        
        # Validate required fields
        if not all([businessName, phone, address]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/register_business.html')
        
        try:
            # Create business
            business = Business.objects.create(
                user=request.user,
                businessName=businessName,
                phone=phone,
                address=address,
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
    
    return render(request, 'accounts/register_business.html')


@login_required
def edit_business(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    

    if request.method == 'POST':
        businessName = request.POST.get('businessName')
        phone = request.POST.get('phone')
        address = request.POST.get('address')
        email = request.POST.get('email')
        
        if not all([businessName, phone, address]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/edit_business.html', {'business': business})
        
        try:
            business.businessName = businessName
            business.phone = phone
            business.address = address
            business.user.email = email
            business.user.save()
            business.save()
            
            messages.success(request, 'Business information updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating business: {str(e)}')
            raise Exception(str(e))
    
    return render(request, 'accounts/edit_business.html', {'business': business})


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
            
            settings.save()
            messages.success(request, 'Business settings updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating settings: {str(e)}')
            raise Exception(str(e))
    
    return render(request, 'accounts/edit_business_settings.html', {'settings': settings, 'business': business})


@login_required
def edit_credentials(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    credentials = ApiCredential.objects.get(business=business)
    
    if request.method == 'POST':
        try:
            credentials.retellAPIKey = request.POST.get('retellAPIKey', '')
            credentials.voiceAgentNumber = request.POST.get('voiceAgentNumber', '')
            credentials.twilioSmsNumber = request.POST.get('twilioSmsNumber', '')
            credentials.twilioAccountSid = request.POST.get('twilioSid', '')
            credentials.twilioAuthToken = request.POST.get('twilioAuthToken', '')
            credentials.save()
            
            messages.success(request, 'API credentials updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating credentials: {str(e)}')
            raise Exception(str(e))
    
    return render(request, 'accounts/edit_credentials.html', {'credentials': credentials, 'business': business})


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
    
    return redirect('accounts:profile')


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
        return redirect('accounts:profile')
    
    return redirect('accounts:profile')


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


@login_required
def test_email_settings(request):
    """Test email settings for the business"""
    if not request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request'
        }, status=400)

    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method'
        }, status=400)

    try:
        business = request.user.business_set.first()
        if not business:
            return JsonResponse({
                'success': False,
                'message': 'No business found. Please set up your business first.'
            })

        smtpConfig = SMTPConfig.objects.get(business=business)
        
        if not smtpConfig.host or not smtpConfig.port or not smtpConfig.username or not smtpConfig.password:
            return JsonResponse({
                'success': False,
                'message': 'Email credentials not configured. Please set up your email credentials first.'
            })

        # Create test email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Test Email - {business.businessName}'
        
        # Use from_name if available, otherwise use username
        from_email = smtpConfig.username
        if smtpConfig.from_name:
            from_email = f"{smtpConfig.from_name} <{smtpConfig.username}>"
        msg['From'] = from_email
        
        msg['To'] = request.user.email
        
        # Add Reply-To header if configured
        if smtpConfig.reply_to:
            msg['Reply-To'] = smtpConfig.reply_to

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Test Email</h2>
            <p>Dear {request.user.first_name or request.user.username},</p>
            <p>This is a test email from your cleaning business management system.</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Email Configuration Details:</h3>
                <p><strong>Business Name:</strong> {business.businessName}</p>
                <p><strong>Email Address:</strong> {smtpConfig.username}</p>
                <p><strong>From Name:</strong> {smtpConfig.from_name or 'Not set'}</p>
                <p><strong>Reply-To:</strong> {smtpConfig.reply_to or 'Not set'}</p>
                <p><strong>SMTP Server:</strong> {smtpConfig.host}</p>
            </div>
            
            <p>If you received this email, your email settings are configured correctly!</p>
            
            <p>Best regards,<br>
            Your Business Management System</p>
        </body>
        </html>
        """
        
        text_content = strip_tags(html_content)

        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        msg.attach(part1)
        msg.attach(part2)

        # Send test email
        smtp_server = smtplib.SMTP(smtpConfig.host, smtpConfig.port)
        smtp_server.starttls()
        smtp_server.login(smtpConfig.username, smtpConfig.password)
        smtp_server.send_message(msg)
        smtp_server.quit()

        return JsonResponse({
            'success': True,
            'message': f'Test email sent successfully to {request.user.email}'
        })

    except SMTPConfig.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Email credentials not found. Please configure your email settings.'
        })
    except smtplib.SMTPAuthenticationError:
        return JsonResponse({
            'success': False,
            'message': 'Gmail authentication failed. Please check your email and app password.'
        })
    except Exception as e:
        raise Exception(str(e))


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
        # Get email settings from Django settings
        sender_email = "8bpcoins4u@gmail.com"  # Hardcoded for testing
        sender_password = "xori gjys nikt qoyo"  # Hardcoded for testing
        
        # Check if email credentials are configured
        if not sender_email or not sender_password:
            # Log the error
            print("Email credentials not configured in settings")
            return False
        
        # Create email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = 'Password Reset OTP'
        msg['From'] = sender_email
        msg['To'] = user.email
        
        # Email content
        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Password Reset OTP</h2>
            <p>Dear {user.first_name or user.username},</p>
            <p>You have requested to reset your password. Please use the following OTP to verify your identity:</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0; text-align: center;">
                <h1 style="font-size: 32px; letter-spacing: 5px;">{otp}</h1>
            </div>
            
            <p>This OTP will expire in 10 minutes.</p>
            <p>If you did not request a password reset, please ignore this email or contact support.</p>
            
            <p>Best regards,<br>
            CEO Cleaners Support Team</p>
        </body>
        </html>
        """
        
        text_content = strip_tags(html_content)
        
        part1 = MIMEText(text_content, 'plain')
        part2 = MIMEText(html_content, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # For debugging
        print(f"Attempting to send email from: {sender_email}")
        
        # Skip Django's email system and use direct SMTP since we know it works
        try:
            smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
            smtp_server.starttls()
            smtp_server.login(sender_email, sender_password)
            smtp_server.send_message(msg)
            smtp_server.quit()
            print("Email sent successfully using direct SMTP")
            return True
        except Exception as smtp_error:
            print(f"SMTP error: {smtp_error}")
            print("Gmail authentication failed. Please check:")
            print("1. Make sure you're using an App Password if 2-Step Verification is enabled")
            print("2. Verify the email and password in your .env file are correct")
            print("3. Check that 'Less secure app access' is enabled if not using 2-Step Verification")
            return False
                
    except Exception as e:
        print(f"Error sending OTP email: {e}")
        return False




# Views for Creating SMTPConfig, Updating, Deleting


@login_required
def smtp_config(request):
    business = request.user.business_set.first()
    if not business:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'No business found.'
            }, status=400)
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    smtp_config, created = SMTPConfig.objects.get_or_create(business=business)
    
    if request.method == 'POST':
        smtp_config.host = request.POST.get('host', '')
        smtp_config.port = request.POST.get('port', '')
        smtp_config.username = request.POST.get('username', '')
        smtp_config.password = request.POST.get('password', '')
        smtp_config.from_name = request.POST.get('from_name', '')
        smtp_config.reply_to = request.POST.get('reply_to', '')
        smtp_config.save()
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': True,
                'message': 'SMTP configuration updated successfully!'
            })
        
        messages.success(request, 'SMTP configuration updated successfully!')
        return redirect('accounts:smtp_config')
    
    return render(request, 'accounts/smtp_config.html', {'smtp_config': smtp_config})


@login_required
def delete_smtp_config(request):
    business = request.user.business_set.first()
    if not business:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'No business found.'
            }, status=400)
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    try:
        smtp_config = SMTPConfig.objects.get(business=business)
        
        if request.method == 'POST':
            smtp_config.delete()
            
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': True,
                    'message': 'SMTP configuration deleted successfully!'
                })
            
            messages.success(request, 'SMTP configuration deleted successfully!')
            return redirect('accounts:smtp_config')
    except SMTPConfig.DoesNotExist:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({
                'success': False,
                'message': 'SMTP configuration not found.'
            }, status=404)
    
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': False,
            'message': 'Invalid request method.'
        }, status=400)
        
    return redirect('accounts:smtp_config')


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
    
    return render(request, 'accounts/approval_pending.html', {'business': business})



@login_required
def admin_business_approval(request):
    """
    Admin view to manage business approvals
    Only accessible to superusers
    """
    # Check if user is a superuser
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page.')
        return redirect('accounts:profile')
    
    # Get status filter from query params
    status = request.GET.get('status', 'all')
    
    # Get all businesses
    businesses_query = Business.objects.all().order_by('-createdAt')
    
    # Apply filters
    if status == 'pending':
        businesses_query = businesses_query.filter(isApproved=False, isActive=True)
    elif status == 'approved':
        businesses_query = businesses_query.filter(isApproved=True)
    elif status == 'rejected':
        businesses_query = businesses_query.filter(isActive=False)
    
    # Count for each status
    all_count = Business.objects.count()
    pending_count = Business.objects.filter(isApproved=False, isActive=True).count()
    approved_count = Business.objects.filter(isApproved=True).count()
    rejected_count = Business.objects.filter(isActive=False).count()
    
    # Pagination
    paginator = Paginator(businesses_query, 10)  # Show 10 businesses per page
    page = request.GET.get('page')
    
    try:
        businesses = paginator.page(page)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        businesses = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page of results
        businesses = paginator.page(paginator.num_pages)
    
    context = {
        'businesses': businesses,
        'status': status,
        'all_count': all_count,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'rejected_count': rejected_count,
    }
    
    return render(request, 'accounts/admin_business_approval.html', context)


@login_required
def approve_business(request, business_id):
    """
    Approve a business
    Only accessible to superusers
    """
    # Check if user is a superuser
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        business = get_object_or_404(Business, id=business_id)
        business.isApproved = True
        business.isActive = True
        business.save()
        
        # Send email notification to business owner
        try:
            subject = 'Your Business Has Been Approved!'
            message = f"""Hello {business.user.username},

Congratulations! Your business '{business.businessName}' has been approved by our team.

You now have full access to all features of CleaningBiz AI. Log in to your account to get started.

Thank you for choosing CleaningBiz AI!

Best regards,
The CleaningBiz AI Team
"""
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [business.user.email]
            send_mail(subject, message, from_email, recipient_list)
        except Exception as e:
            # Log the error but don't stop the approval process
            print(f"Error sending approval email: {str(e)}")
        
        messages.success(request, f"Business '{business.businessName}' has been approved successfully.")
    
    return redirect('accounts:admin_business_approval')


@login_required
def reject_business(request, business_id):
    """
    Reject a business
    Only accessible to superusers
    """
    # Check if user is a superuser
    if not request.user.is_superuser:
        messages.error(request, 'You do not have permission to perform this action.')
        return redirect('accounts:profile')
    
    if request.method == 'POST':
        business = get_object_or_404(Business, id=business_id)
        business.isApproved = False
        business.isActive = False
        business.save()
        
        # Send email notification to business owner
        try:
            subject = 'Your Business Registration Has Been Rejected'
            message = f"""Hello {business.user.username},

We regret to inform you that your business '{business.businessName}' registration has been rejected by our team.

If you believe this is an error or would like to discuss this further, please contact our support team at support@cleaningbizai.com.

Thank you for your understanding.

Best regards,
The CleaningBiz AI Team
"""
            from_email = settings.DEFAULT_FROM_EMAIL
            recipient_list = [business.user.email]
            send_mail(subject, message, from_email, recipient_list)
        except Exception as e:
            # Log the error but don't stop the rejection process
            print(f"Error sending rejection email: {str(e)}")
        
        messages.warning(request, f"Business '{business.businessName}' has been rejected.")
    
    return redirect('accounts:admin_business_approval')


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
            
            business.save()
            
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

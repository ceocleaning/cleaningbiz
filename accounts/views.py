from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.forms import PasswordChangeForm
from accounts.models import Business, BusinessSettings, BookingIntegration, ApiCredential, CustomAddons
import random
from django.http import JsonResponse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import smtplib
from django.utils.html import strip_tags


def SignupPage(request):
    if request.user.is_authenticated:
        return redirect('home')
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password1 = request.POST.get('password1')
        password2 = request.POST.get('password2')
        
        if password1 == password2:
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists.')
                return redirect('accounts:signup')

            user = User.objects.create_user(username=username, password=password1)
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
    
    # Get related models
    business_settings = business.settings
    api_credentials = business.apicredential
    booking_integrations = business.bookingIntegrations.all()
    
    context = {
        'business': business,
        'settings': business_settings,
        'credentials': api_credentials,
        'integrations': booking_integrations,
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
                address=address
            )
            
            # Create default settings for the business
            BusinessSettings.objects.create(business=business)
            
            # Create API credentials
            ApiCredential.objects.create(
                business=business,
            )
            
            messages.success(request, 'Business registered successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error registering business: {str(e)}')
            return render(request, 'accounts/register_business.html')
    
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
        
        if not all([businessName, phone, address]):
            messages.error(request, 'All fields are required.')
            return render(request, 'accounts/edit_business.html', {'business': business})
        
        try:
            business.businessName = businessName
            business.phone = phone
            business.address = address
            business.save()
            
            messages.success(request, 'Business information updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating business: {str(e)}')
    
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
    
    return render(request, 'accounts/edit_business_settings.html', {'settings': settings})


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
            credentials.gmail_host_user = request.POST.get('gmail_host_user', '')
            credentials.gmail_host_password = request.POST.get('gmail_host_password', '')
            credentials.save()
            
            messages.success(request, 'API credentials updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating credentials: {str(e)}')
    
    return render(request, 'accounts/edit_credentials.html', {'credentials': credentials})


@login_required
def add_integration(request):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    if request.method == 'POST':
        try:
            integration = BookingIntegration(
                business=business,
                serviceName=request.POST.get('serviceName'),
                apiKey=request.POST.get('apiKey'),
                webhookUrl=request.POST.get('webhookUrl')
            )
            integration.save()

            business.bookingIntegrations.add(integration)
            
            messages.success(request, 'Integration added successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error adding integration: {str(e)}')
    
    return render(request, 'accounts/add_integration.html')


@login_required
def edit_integration(request, pk):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    integration = get_object_or_404(BookingIntegration, pk=pk, business=business)
    
    if request.method == 'POST':
        try:
            integration.serviceName = request.POST.get('serviceName')
            integration.apiKey = request.POST.get('apiKey')
            integration.webhookUrl = request.POST.get('webhookUrl')
            integration.save()
            
            messages.success(request, 'Integration updated successfully!')
            return redirect('accounts:profile')
            
        except Exception as e:
            messages.error(request, f'Error updating integration: {str(e)}')
    
    return render(request, 'accounts/edit_integration.html', {'integration': integration})


@login_required
def delete_integration(request, pk):
    business = request.user.business_set.first()
    if not business:
        return redirect('accounts:register_business')
    
    integration = get_object_or_404(BookingIntegration, pk=pk, business=business)
    
    try:
        integration.delete()
        messages.success(request, 'Integration deleted successfully!')
    except Exception as e:
        messages.error(request, f'Error deleting integration: {str(e)}')
    
    return redirect('accounts:profile')


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
    
    return redirect('accounts:profile')


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
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
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
            return JsonResponse({'status': 'error', 'message': str(e)}, status=500)
    
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

        api_credentials = ApiCredential.objects.get(business=business)
        
        if not api_credentials.gmail_host_user or not api_credentials.gmail_host_password:
            return JsonResponse({
                'success': False,
                'message': 'Email credentials not configured. Please set up your email credentials first.'
            })

        # Create test email
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'Test Email - {business.businessName}'
        msg['From'] = api_credentials.gmail_host_user
        msg['To'] = request.user.email

        html_content = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <h2>Test Email</h2>
            <p>Dear {request.user.first_name or request.user.username},</p>
            <p>This is a test email from your cleaning business management system.</p>
            
            <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3>Email Configuration Details:</h3>
                <p><strong>Business Name:</strong> {business.businessName}</p>
                <p><strong>Email Address:</strong> {api_credentials.gmail_host_user}</p>
                <p><strong>SMTP Server:</strong> smtp.gmail.com</p>
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
        smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
        smtp_server.starttls()
        smtp_server.login(api_credentials.gmail_host_user, api_credentials.gmail_host_password)
        smtp_server.send_message(msg)
        smtp_server.quit()

        return JsonResponse({
            'success': True,
            'message': f'Test email sent successfully to {request.user.email}'
        })

    except ApiCredential.DoesNotExist:
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
        return JsonResponse({
            'success': False,
            'message': f'Error sending test email: {str(e)}'
        })
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction

from accounts.decorators import customer_required
from customer.models import Customer, Review
from bookings.models import Booking
from invoice.models import Invoice
from accounts.timezone_utils import get_timezone_choices

def customer_signup(request):
    """
    View for customer signup
    Creates a new user, adds them to the Customer group,
    and creates a Customer profile or links to an existing one
    """
    if request.method == 'POST':
        # Get form data
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        password = request.POST.get('password')
        confirm_password = request.POST.get('confirm_password')
        
        # Validate form data
        if not all([first_name, last_name, email, phone, password, confirm_password]):
            messages.error(request, 'All fields are required')
            return render(request, 'customer/auth/signup.html')
        
        if password != confirm_password:
            messages.error(request, 'Passwords do not match')
            return render(request, 'customer/auth/signup.html')
        
        # Check if user already exists of group customer
        if User.objects.filter(email=email, groups__name='Customer').exists():
            messages.error(request, 'Email already registered')
            return render(request, 'customer/auth/signup.html')
        
        try:
            # Format phone number for consistency
            from automation.utils import format_phone_number
            formatted_phone = format_phone_number(phone) or phone
            
            # Check if there are existing customer records before creating the user
            # First try to find by email
            existing_customers = Customer.objects.filter(email=email, user__isnull=True)
            
            if not existing_customers.exists() and formatted_phone:
                # Try to find by phone number if email search failed
                existing_customers = Customer.objects.filter(
                    phone_number=formatted_phone,
                    user__isnull=True
                )
            
            with transaction.atomic():
                # Create user
                user = User.objects.create_user(
                    username=email,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                
                # Add user to Customer group
                customer_group, created = Group.objects.get_or_create(name='Customer')
                user.groups.add(customer_group)
                
                if existing_customers.exists():
                    # Get the first matching customer record
                    customer = existing_customers.first()
                    
                    # Link the customer record to the user
                    customer.user = user
                    customer.save()
                    
                    # Show a message about the linked record
                    messages.info(request, 'We found an existing customer record that matches your information and linked it to your account.')
                else:
                    # Create a new customer profile
                    customer = Customer.objects.create(
                        user=user,
                        first_name=first_name,
                        last_name=last_name,
                        email=email,
                        phone_number=formatted_phone
                    )
                
                # Store success message in a variable to add after login
                success_message = 'Account created successfully! Welcome to CleaningBiz.'
                
                # Determine the redirect URL before login
                if existing_customers.exists():
                    redirect_url = reverse('customer:linked_businesses') + '?from_signup=true'
                else:
                    redirect_url = reverse('customer:dashboard')
                
                # Log the user in - this must be the last operation before redirect
                login(request, user)
                
                # Add the success message and redirect
                messages.success(request, success_message)
                return redirect(redirect_url)
                
        except Exception as e:
            messages.error(request, f'An error occurred: {str(e)}')
            return render(request, 'customer/auth/signup.html')
    
    return render(request, 'customer/auth/signup.html')

def customer_login(request):
    """
    View for customer login
    Authenticates the user and redirects to the customer dashboard
    Also checks if there are any unlinked customer records that match the user's email
    """
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        if not all([email, password]):
            messages.error(request, 'Email and password are required')
            return render(request, 'customer/auth/login.html')
        
        # Authenticate user
        user = authenticate(request, username=email, password=password)
        
        if user is not None:
            # Check if user is in Customer group
            if user.groups.filter(name='Customer').exists():
                # Check if the user has a customer profile
                has_customer_profile = hasattr(user, 'customer')
                
                # Check if there are any unlinked customer records with this email
                unlinked_customers = Customer.objects.filter(email=email, user__isnull=True)
                
                # Prepare redirect and messages before login
                if not has_customer_profile and unlinked_customers.exists():
                    # Prepare session data and redirect info
                    redirect_url = reverse('customer:link_account')
                    info_message = f'We found {unlinked_customers.count()} existing customer record(s) that match your email. Would you like to link them to your account?'
                    
                    # Login the user
                    login(request, user)
                    
                    # Now set session data after login
                    request.session['unlinked_customers_found'] = True
                    request.session['unlinked_customers_count'] = unlinked_customers.count()
                    
                    # Add message and redirect
                    messages.info(request, info_message)
                    return redirect(redirect_url)
                else:
                    # Standard login flow
                    login(request, user)
                    messages.success(request, 'Login successful!')
                    return redirect(reverse('customer:dashboard'))
            else:
                messages.error(request, 'This account is not registered as a customer')
                return render(request, 'customer/auth/login.html')
        else:
            messages.error(request, 'Invalid email or password')
            return render(request, 'customer/auth/login.html')
    
    return render(request, 'customer/auth/login.html', {'show_link_option': True})



@login_required(login_url='customer:login')
def customer_logout(request):
    """
    View for customer logout
    Logs out the user and redirects to the login page
    """
    logout(request)
    messages.success(request, 'You have been successfully logged out.')
    return redirect('customer:login')



@login_required(login_url='customer:login')
@customer_required
def profile(request):
    """
    View for customer profile
    Displays and allows editing of customer information
    """
    try:
        customer = request.user.customer
    except:
        messages.warning(request, 'Customer profile not found.')
        return redirect('customer:dashboard')
    
    if request.method == 'POST':
        # Update customer profile
        customer.first_name = request.POST.get('first_name')
        customer.last_name = request.POST.get('last_name')
        customer.email = request.POST.get('email')
        
        # Combine country code and phone number with leading plus sign
        country_code = request.POST.get('country_code')
        phone = request.POST.get('phone')
        
        # Format the complete phone number
        if country_code and phone:
            customer.phone_number = f'+{country_code} {phone}'
        elif phone:  # Fallback if no country code
            if not phone.startswith('+'):
                phone = '+1 ' + phone  # Default to US/Canada
            customer.phone_number = phone
        
        customer.address = request.POST.get('address')
        customer.city = request.POST.get('city')
        customer.state_or_province = request.POST.get('state_or_province')
        customer.zip_code = request.POST.get('zip_code')
        customer.timezone = request.POST.get('timezone', 'UTC')
        customer.save()
        
        # Update user model as well
        user = request.user
        user.first_name = request.POST.get('first_name')
        user.last_name = request.POST.get('last_name')
        user.email = request.POST.get('email')
        user.save()
        
        messages.success(request, 'Profile updated successfully!')
        return redirect('customer:profile')
    


    # Placeholder data for account summary
    context = {
        'customer': customer,
        'total_bookings': 0,  # Replace with actual query
        'completed_services': 0,  # Replace with actual query
        'pending_invoices': 0,  # Replace with actual query
        'timezone_choices': get_timezone_choices(),
    }
    
    return render(request, 'customer/profile.html', context)


@login_required(login_url='customer:login')
@customer_required
def change_password(request):
    """
    View for changing customer password
    """
    if request.method == 'POST':
        current_password = request.POST.get('current_password')
        new_password = request.POST.get('new_password')
        confirm_new_password = request.POST.get('confirm_new_password')
        
        # Validate input
        if not all([current_password, new_password, confirm_new_password]):
            messages.error(request, 'All fields are required')
            return redirect('customer:profile')
        
        if new_password != confirm_new_password:
            messages.error(request, 'New passwords do not match')
            return redirect('customer:profile')
        
        # Check current password
        user = request.user
        if not user.check_password(current_password):
            messages.error(request, 'Current password is incorrect')
            return redirect('customer:profile')
        
        # Update password
        user.set_password(new_password)
        user.save()
        
        # Update session to prevent logout
        update_session_auth_hash(request, user)
        
        messages.success(request, 'Password changed successfully!')
        return redirect('customer:profile')
    
    return redirect('customer:profile')
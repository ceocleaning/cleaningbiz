from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from django.views.decorators.http import require_http_methods
from django.http import JsonResponse
from django.contrib.auth.models import User, Group

from customer.models import Customer
from accounts.models import Business


@transaction.atomic
def link_customer_account(request):
    """
    View for linking an existing customer record to a user account.
    This is used when a customer who was previously added by a business
    wants to create their own account on CleaningBiz AI.
    """
    # Check if we have unlinked customers from the login process
    unlinked_customers_found = request.session.get('unlinked_customers_found', False)
    
    if request.method == 'POST':
        # If we have unlinked customers from the login process, use the user's email
        if unlinked_customers_found:
            email = request.user.email
            phone_number = request.POST.get('phone_number', '')
        else:
            email = request.POST.get('email')
            phone_number = request.POST.get('phone_number')
        
        # Find customer record that matches email or phone number
        matching_customer = Customer.objects.filter(
            email=email, 
            user__isnull=True
        ).first()
        
        if not matching_customer and phone_number:
            # Try to find by phone number if email search failed
            matching_customer = Customer.objects.filter(
                phone_number=phone_number,
                user__isnull=True
            ).first()
        
        if not matching_customer:
            messages.error(request, 'No matching customer record found. Please contact the business owner.')
            return redirect('customer:link_account')
        
        # Get the customer group
        customer_group, created = Group.objects.get_or_create(name='Customer')
        
        # Add the user to the customer group
        request.user.groups.add(customer_group)
        
        # Link the customer record to the user account
        matching_customer.user = request.user
        matching_customer.save()
        
        # Count linked businesses
        business_count = matching_customer.businesses.count()
        
        # Prepare success message and redirect URL
        success_message = f'Your account has been successfully linked! You have access to {business_count} business(es).'
        
        # Determine the source of the linking (login or direct) and set redirect URL
        if unlinked_customers_found:
            redirect_url = reverse('customer:linked_businesses') + '?from_login=true'
        else:
            redirect_url = reverse('customer:linked_businesses')
        
        # Clear session data
        if 'unlinked_customers_found' in request.session:
            del request.session['unlinked_customers_found']
        if 'unlinked_customers_count' in request.session:
            del request.session['unlinked_customers_count']
        
        # Add message and redirect
        messages.success(request, success_message)
        return redirect(redirect_url)
    
    # For GET requests, show the form
    # If we have unlinked customers from the login process, pre-fill the email field
    context = {}
    if unlinked_customers_found:
        context['email'] = request.user.email
        context['email_readonly'] = True
    
    return render(request, 'customer/account_linking.html', context)


@require_http_methods(["GET"])
def check_existing_customer(request):
    """
    AJAX endpoint to check if a customer record exists for the given email or phone number.
    """
    email = request.GET.get('email', '')
    phone = request.GET.get('phone', '')
    
    if not email and not phone:
        return JsonResponse({'exists': False, 'message': 'Please provide an email or phone number.'})
    
    # Check if a customer record exists with this email or phone
    customer = Customer.objects.filter(email=email, user__isnull=True).first()
    
    if not customer and phone:
        customer = Customer.objects.filter(phone_number=phone, user__isnull=True).first()
    
    customer_exists = customer is not None
    
    if customer_exists:
        return JsonResponse({
            'exists': True, 
            'message': 'A customer record was found! You can link your account.'
        })
    else:
        return JsonResponse({
            'exists': False, 
            'message': 'No matching customer records found. Please contact the business owner.'
        })

@login_required
def view_linked_businesses(request):
    """
    View to display all businesses that the customer has bookings with.
    """
    try:
        customer = request.user.customer
        businesses = Business.objects.filter(bookings__customer=customer).distinct()
        
        context = {
            'businesses': businesses
        }
        
        return render(request, 'customer/linked_businesses.html', context)
    except:
        messages.warning(request, 'You do not have a customer profile yet.')
        return redirect('customer:link_account')

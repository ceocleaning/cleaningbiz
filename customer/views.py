from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from accounts.decorators import customer_required

from bookings.models import Booking
from invoice.models import Invoice


@login_required
@customer_required
def dashboard(request):
    """
    Customer dashboard view - only accessible to users in the Customer group
    Shows upcoming bookings, recent invoices, and service history
    """
    # Get the customer associated with the logged-in user
    try:
        customer = request.user.customer
    except:
        # If no customer profile exists, redirect to complete profile
        messages.warning(request, 'Please complete your customer profile.')
        return redirect('home')  # Replace with profile completion URL when available
    
    # Get upcoming bookings (placeholder - replace with actual query)
    upcoming_bookings = Booking.objects.filter(customer=customer, isCompleted=False).order_by('-createdAt')[:5]
    
    # Get recent invoices (placeholder - replace with actual query)
    recent_invoices = Invoice.objects.filter(booking__customer=customer).order_by('-createdAt')[:5]
    
    # Get service history (placeholder - replace with actual query)
    service_history = Booking.objects.filter(customer=customer, isCompleted=True).order_by('-createdAt')[:5]
    
    context = {
        'customer': customer,
        'upcoming_bookings': upcoming_bookings,
        'recent_invoices': recent_invoices,
        'service_history': service_history,
    }
    
    return render(request, 'customer/dashboard.html', context)



from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.db import transaction
from decimal import Decimal
import json

from accounts.decorators import customer_required
from accounts.models import Business, BusinessSettings, CustomAddons
from bookings.models import Booking, BookingCustomAddons
from customer.models import Customer
from bookings.timezone_utils import convert_local_to_utc
from automation.utils import format_phone_number
from invoice.models import Invoice
from datetime import datetime, timedelta
from django.utils import timezone

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


@customer_required
def customer_bookings(request):
    try:
        customer = request.user.customer
    except:
        messages.warning(request, 'Please complete your customer profile.')
        return redirect('home')
    
    # Get all bookings for the user's customer
    all_bookings = Booking.objects.filter(customer=customer)

    cancelled_bookings = all_bookings.filter(cancelled_at__isnull=False)
    
    today = timezone.now().date()
    
    # Upcoming bookings (not completed and future date)
    upcoming_bookings = all_bookings.filter(
        isCompleted=False,
        cleaningDate__gte=today,
        invoice__isnull=True,
        invoice__isPaid=False
    ).order_by('cleaningDate', 'startTime')
    
    # Upcoming paid bookings (not completed, future date, with paid invoice)
    upcoming_paid_bookings = all_bookings.filter(
        isCompleted=False,
        cleaningDate__gte=today,
        invoice__isnull=False,
        invoice__isPaid=True
    ).order_by('cleaningDate', 'startTime')
    
    # Completed bookings (isCompleted=True and past date)
    completed_bookings = all_bookings.filter(
        isCompleted=True,
    ).order_by('-cleaningDate', '-startTime')
    
    # Past bookings (past date and paid)
    past_bookings = all_bookings.filter(
        cleaningDate__lt=today,
        invoice__isnull=False,
        invoice__isPaid=True
    ).order_by('-cleaningDate', '-startTime')
    
    # Pending bookings (unpaid invoices)
    pending_bookings = all_bookings.filter(
        isCompleted=False,
        invoice__isnull=False,
        invoice__isPaid=False
    ).order_by('cleaningDate', 'startTime')
    
    # Counts for the dashboard cards
    total_bookings = all_bookings.count()
    pending_count = pending_bookings.count()
    completed_count = completed_bookings.count()
    upcoming_paid_count = upcoming_paid_bookings.count()
    
    # Count for past bookings
    past_bookings_count = past_bookings.count()
    
    # Count for cancelled bookings
    cancelled_bookings_count = cancelled_bookings.count()
    
    context = {
        'all_bookings': all_bookings,
        'upcoming_bookings': upcoming_bookings,
        'upcoming_paid_bookings': upcoming_paid_bookings,
        'completed_bookings': completed_bookings,
        'pending_bookings': pending_bookings,
        'past_bookings': past_bookings,
        'total_bookings': total_bookings,
        'pending_count': pending_count,
        'completed_count': completed_count,
        'upcoming_paid_count': upcoming_paid_count,
        'past_bookings_count': past_bookings_count,
        'cancelled_bookings_count': cancelled_bookings_count,
        'cancelled_bookings': cancelled_bookings,
        'today': today,
    }
    return render(request, 'customer/bookings.html', context)


@login_required
@customer_required
def businesses_list(request):
    """
    View to display all approved businesses for customer booking
    """
    # Get all approved businesses
    businesses = Business.objects.filter(isApproved=True, isActive=True)
    
    # Search functionality
    search_query = request.GET.get('search', '')
    if search_query:
        businesses = businesses.filter(
            businessName__icontains=search_query
        ) | businesses.filter(
            address__icontains=search_query
        )
    
    # Prepare business data with additional information
    business_data = []
    for business in businesses:
        # Get services provided
        services_provided = []
        try:
            settings = business.settings
            
            # Check which services are provided based on sqft multipliers
            if settings.sqftMultiplierStandard > 0:
                services_provided.append('Standard Cleaning')
            if settings.sqftMultiplierDeep > 0:
                services_provided.append('Deep Cleaning')
            if settings.sqftMultiplierMoveinout > 0:
                services_provided.append('Move In/Out')
            if settings.sqftMultiplierAirbnb > 0:
                services_provided.append('Airbnb Cleaning')
            
            # Count addons
            addon_count = 0
            addon_fields = [
                'addonPriceDishes', 'addonPriceLaundry', 'addonPriceWindow',
                'addonPricePets', 'addonPriceFridge', 'addonPriceOven',
                'addonPriceBaseboard', 'addonPriceBlinds', 'addonPriceGreen',
                'addonPriceCabinets', 'addonPriceGarage', 'addonPricePatio'
            ]
            
            # Count standard addons
            for field in addon_fields:
                if getattr(settings, field, 0) > 0:
                    addon_count += 1
            
            # Count custom addons
            custom_addons_count = settings.customAddons.count()
            total_addons = addon_count + custom_addons_count
            
            # Get visible addons (up to 3)
            visible_addons = []
            for field, display_name in [
                ('addonPriceDishes', 'Dishes'),
                ('addonPriceLaundry', 'Laundry'),
                ('addonPriceWindow', 'Windows'),
                ('addonPricePets', 'Pets'),
                ('addonPriceFridge', 'Fridge'),
                ('addonPriceOven', 'Oven')
            ]:
                if getattr(settings, field, 0) > 0 and len(visible_addons) < 3:
                    visible_addons.append(display_name)
            
            # Add custom addons if we have less than 3
            if len(visible_addons) < 3:
                for addon in settings.customAddons.all()[:3-len(visible_addons)]:
                    visible_addons.append(addon.addonName)
            
        except BusinessSettings.DoesNotExist:
            services_provided = []
            total_addons = 0
            visible_addons = []
        
        # Count bookings
        booking_count = Booking.objects.filter(business=business).count()
        
        # Add dummy reviews (will be replaced later)
        dummy_reviews = {
            'count': 5,  # Random number of reviews
            'rating': 4.5  # Random rating
        }
        
        business_data.append({
            'business': business,
            'services_provided': services_provided,
            'total_addons': total_addons,
            'visible_addons': visible_addons,
            'booking_count': booking_count,
            'reviews': dummy_reviews
        })
    
    context = {
        'business_data': business_data,
        'search_query': search_query
    }
    
    return render(request, 'customer/businesses_list.html', context)


@login_required
@customer_required
@require_http_methods(["GET", "POST"])
@transaction.atomic
def add_booking(request, business_id):
    """
    View to handle booking creation for customers
    """
    # Get business ID from URL parameter
    business = get_object_or_404(Business, businessId=business_id, isApproved=True, isActive=True)
    
    if not business:
        messages.error(request, 'Business not found')
        return redirect('customer:businesses_list')
    
    # Get business settings for pricing
    try:
        business_settings = BusinessSettings.objects.get(business=business)
    except BusinessSettings.DoesNotExist:
        messages.error(request, 'Business settings not found')
        return redirect('customer:businesses_list')
    
    # Get custom add-ons for this business
    custom_addons = CustomAddons.objects.filter(business=business)
    
    # Get today's date for minimum date in form
    today = datetime.now()
    
    if request.method == 'POST':
        try:
            # Get price details from form
            total_price = float(request.POST.get('totalAmount', '0'))
            tax = float(request.POST.get('tax', '0'))
            
            # Format phone number
            phone_number = request.POST.get('phoneNumber')
            if phone_number:
                phone_number = format_phone_number(phone_number)
            
            if not phone_number:
                messages.error(request, 'Please enter a valid phone number.')
                return redirect('customer:add_booking')
            
            # Get cleaning date and time
            cleaning_date = request.POST.get('cleaningDate')
            start_time = request.POST.get('startTime')
            
            # Convert cleaning date and time from business timezone to UTC
            start_time_utc = convert_local_to_utc(
                cleaning_date,
                start_time,
                business.timezone
            ).time()
            
            # Set end time to 1 hour after start time
            end_time_utc = (datetime.strptime(start_time_utc.strftime('%H:%M'), '%H:%M') + timedelta(hours=1)).strftime('%H:%M')
            
            # Check if we need to use existing customer or create new one
            use_my_info = request.POST.get('useMyInfo') == 'on'
            
            if use_my_info and hasattr(request.user, 'customer'):
                # Use the logged-in customer
                customer = request.user.customer
            else:
                # Try to find customer by email or create new one
                customer_email = request.POST.get('email')
                try:
                    customer = Customer.objects.get(email=customer_email)
                except Customer.DoesNotExist:
                    # Create new customer
                    customer = Customer.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        first_name=request.POST.get('firstName'),
                        last_name=request.POST.get('lastName'),
                        email=customer_email,
                        phone_number=phone_number,
                        address=request.POST.get('address1'),
                        city=request.POST.get('city'),
                        state_or_province=request.POST.get('stateOrProvince'),
                        zip_code=request.POST.get('zipCode')
                    )
            
            # Create the booking
            booking = Booking.objects.create(
                business=business,
                customer=customer,
                bedrooms=int(request.POST.get('bedrooms', 0)),
                bathrooms=int(request.POST.get('bathrooms', 0)),
                squareFeet=int(request.POST.get('squareFeet', 0)),
                serviceType=request.POST.get('serviceType'),
                cleaningDate=cleaning_date,
                startTime=start_time_utc,
                endTime=end_time_utc,
                recurring=request.POST.get('recurring'),
                paymentMethod='creditcard',  # Default payment method
                otherRequests=request.POST.get('otherRequests', ''),
                tax=tax,
                totalPrice=total_price
            )
            
            # Handle standard add-ons
            addon_fields = [
                'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
                'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
                'addonBaseboard', 'addonBlinds'
            ]
            
            for field in addon_fields:
                value = int(request.POST.get(field, 0))
                if value > 0:
                    setattr(booking, field, value)
            
            booking.save()
            
            # Handle custom add-ons
            for addon in custom_addons:
                quantity_str = request.POST.get(f'custom_addon_qty_{addon.id}', '0').strip()
                quantity = int(quantity_str) if quantity_str else 0
                
                if quantity > 0:
                    new_custom_booking_addon = BookingCustomAddons.objects.create(
                        addon=addon,
                        qty=quantity
                    )
                    booking.customAddons.add(new_custom_booking_addon)
            
            messages.success(request, 'Booking created successfully!')
            return redirect('customer:dashboard')
            
        except Exception as e:
            messages.error(request, f'Error creating booking: {str(e)}')
            return redirect('customer:businesses_list')
    
    # For GET requests, prepare pricing data for JavaScript
    prices = {
        'base_price': float(business_settings.base_price),
        'bedrooms': float(business_settings.bedroomPrice),
        'bathrooms': float(business_settings.bathroomPrice),
        'sqftMultiplierStandard': float(business_settings.sqftMultiplierStandard),
        'sqftMultiplierDeep': float(business_settings.sqftMultiplierDeep),
        'sqftMultiplierMoveinout': float(business_settings.sqftMultiplierMoveinout),
        'sqftMultiplierAirbnb': float(business_settings.sqftMultiplierAirbnb),
        'addonPriceDishes': float(business_settings.addonPriceDishes),
        'addonPriceLaundry': float(business_settings.addonPriceLaundry),
        'addonPriceWindow': float(business_settings.addonPriceWindow),
        'addonPricePets': float(business_settings.addonPricePets),
        'addonPriceFridge': float(business_settings.addonPriceFridge),
        'addonPriceOven': float(business_settings.addonPriceOven),
        'addonPriceBaseboard': float(business_settings.addonPriceBaseboard),
        'addonPriceBlinds': float(business_settings.addonPriceBlinds),
        'tax': float(business_settings.taxPercent)
    }
    
    context = {
        'business': business,
        'customAddons': custom_addons,
        'prices': json.dumps(prices),
        'today': today
    }
    
    return render(request, 'customer/add_booking.html', context)


@customer_required
def booking_detail(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId, customer=request.user.customer)
    context = {
        'booking': booking
    }
    return render(request, 'customer/booking_detail.html', context)



def edit_booking(request, bookingId):
    pass
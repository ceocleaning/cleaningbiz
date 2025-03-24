from datetime import timedelta
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Booking, BookingCustomAddons
from invoice.models import Invoice, Payment
from accounts.models import Business, BusinessSettings, CustomAddons
from automation.models import CleanerAvailability, Cleaners
from decimal import Decimal
import json
from datetime import datetime
from django.db.models import Min, Count

def all_bookings(request):
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    # Get all bookings for the user's business
    all_bookings = Booking.objects.filter(business__user=request.user)
    
    # Get current date for filtering
    today = datetime.now().date()
    
    # Upcoming bookings (not completed and future date)
    upcoming_bookings = all_bookings.filter(
        isCompleted=False,
        cleaningDate__gte=today
    ).order_by('cleaningDate', 'startTime')
    
    # Completed bookings (isCompleted=True and past date)
    completed_bookings = all_bookings.filter(
        isCompleted=True,
        cleaningDate__lt=today
    ).order_by('-cleaningDate', '-startTime')
    
    # Pending bookings (unpaid invoices)
    pending_bookings = all_bookings.filter(
        invoice__isnull=False,  # Has an invoice
        invoice__isPaid=False,  # Invoice is not paid
    ).order_by('cleaningDate', 'startTime')
    
    # Counts for the dashboard cards
    total_bookings = all_bookings.count()
    pending_count = all_bookings.filter(isCompleted=False).count()
    completed_count = all_bookings.filter(isCompleted=True).count()
    
    context = {
        'upcoming_bookings': upcoming_bookings,
        'completed_bookings': completed_bookings,
        'pending_bookings': pending_bookings,
        'total_bookings': total_bookings,
        'pending_count': pending_count,
        'completed_count': completed_count
    }
    return render(request, 'bookings.html', context)

@login_required
def customers(request):
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    # Get all bookings for the user's business
    bookings = Booking.objects.filter(business__user=request.user)
    
    # Dictionary to store unique customers
    unique_customers = {}
    
    # Process bookings to extract unique customers by email or phone
    for booking in bookings:
        # Skip if no email and no phone
        if not booking.email and not booking.phoneNumber:
            continue
            
        # Create a unique key based on email or phone
        key = booking.email if booking.email else booking.phoneNumber
        
        if key not in unique_customers:
            # First occurrence - create new customer entry
            unique_customers[key] = {
                'firstName': booking.firstName,
                'lastName': booking.lastName,
                'email': booking.email,
                'phoneNumber': booking.phoneNumber,
                'joinedDate': booking.createdAt,
                'bookingCount': 1,
                'totalSpent': booking.totalPrice,
                'identifier': key  # Store identifier for linking to detail page
            }
        else:
            # Update existing customer with additional booking info
            unique_customers[key]['bookingCount'] += 1
            unique_customers[key]['totalSpent'] += booking.totalPrice
            # Keep the earliest created date as joined date
            if booking.createdAt < unique_customers[key]['joinedDate']:
                unique_customers[key]['joinedDate'] = booking.createdAt
    
    # Convert dictionary to list for template
    customers_list = list(unique_customers.values())
    
    # Sort customers by joined date (newest first)
    customers_list.sort(key=lambda x: x['joinedDate'], reverse=True)
    
    context = {
        'customers': customers_list,
        'total_customers': len(customers_list)
    }
    
    return render(request, 'customers.html', context)

@login_required
def customer_detail(request, identifier):
    """View for displaying a specific customer's details and booking history."""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    # Determine if identifier is an email or phone
    if '@' in identifier:
        # It's an email
        bookings = Booking.objects.filter(business__user=request.user, email=identifier).order_by('-createdAt')
        identifier_type = 'email'
    else:
        # It's a phone number
        bookings = Booking.objects.filter(business__user=request.user, phoneNumber=identifier).order_by('-createdAt')
        identifier_type = 'phone'
    
    if not bookings.exists():
        messages.error(request, 'Customer not found.')
        return redirect('bookings:customers')
    
    # Get customer details from the most recent booking
    most_recent_booking = bookings.first()
    
    # Calculate statistics
    total_spent = sum(booking.totalPrice for booking in bookings)
    completed_bookings = bookings.filter(isCompleted=True).count()
    pending_bookings = bookings.filter(isCompleted=False).count()
    
    # Find the first booking to determine join date
    first_booking = bookings.order_by('createdAt').first()
    join_date = first_booking.createdAt if first_booking else None
    
    # Service type distribution
    service_stats = {}
    for booking in bookings:
        service_type = booking.get_serviceType_display()
        if service_type in service_stats:
            service_stats[service_type] += 1
        else:
            service_stats[service_type] = 1
    
    context = {
        'customer': {
            'firstName': most_recent_booking.firstName,
            'lastName': most_recent_booking.lastName,
            'email': most_recent_booking.email,
            'phoneNumber': most_recent_booking.phoneNumber,
            'companyName': most_recent_booking.companyName,
            'joinDate': join_date,
            'identifier': identifier,
            'identifier_type': identifier_type
        },
        'bookings': bookings,
        'stats': {
            'totalBookings': bookings.count(),
            'completedBookings': completed_bookings,
            'pendingBookings': pending_bookings,
            'totalSpent': total_spent,
            'avgBookingValue': total_spent / bookings.count() if bookings.count() > 0 else 0,
            'serviceStats': service_stats
        }
    }
    
    return render(request, 'customer_detail.html', context)

@require_http_methods(["GET", "POST"])
@transaction.atomic
def create_booking(request):
    business = Business.objects.get(user=request.user)
    business_settings = BusinessSettings.objects.get(business=business)
    customAddons = CustomAddons.objects.filter(business=business)
    if request.method == 'POST':
        try:
            # Get price details from form
            totalPrice = Decimal(request.POST.get('totalAmount', '0'))
            tax = Decimal(request.POST.get('tax', '0'))
          

            # Create the booking
            booking = Booking.objects.create(
                business=business,
                firstName=request.POST.get('firstName'),
                lastName=request.POST.get('lastName'),
                email=request.POST.get('email'),
                phoneNumber=request.POST.get('phoneNumber'),
                companyName=request.POST.get('companyName', ''),

                address1=request.POST.get('address1'),
                city=request.POST.get('city'),
                stateOrProvince=request.POST.get('stateOrProvince'),
                zipCode=request.POST.get('zipCode'),

                bedrooms=int(request.POST.get('bedrooms', 0)),
                bathrooms=int(request.POST.get('bathrooms', 0)),
                squareFeet=int(request.POST.get('squareFeet', 0)),

                serviceType=request.POST.get('serviceType'),
                cleaningDate=request.POST.get('cleaningDate'),
                startTime=request.POST.get('startTime'),
                endTime=(datetime.strptime(request.POST.get('startTime'), '%H:%M') + timedelta(hours=1)).strftime('%H:%M'),
                recurring=request.POST.get('recurring'),
                paymentMethod=request.POST.get('paymentMethod', 'creditcard'),

                otherRequests=request.POST.get('otherRequests', ''),
                tax=tax,
                totalPrice=totalPrice
            )
            
            # Assign cleaner if selected
            cleaner_id = request.POST.get('selectedCleaner')
            if cleaner_id:
                try:
                    cleaner = Cleaners.objects.get(id=cleaner_id)
                    booking.cleaner = cleaner
                    booking.save()
                except Cleaners.DoesNotExist:
                    pass  # Silently ignore if cleaner doesn't exist

            # Handle standard add-ons
            addon_fields = [
                'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
                'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
                'addonBaseboard', 'addonBlinds', 'addonGreenCleaning',
                'addonCabinetsCleaning', 'addonPatioSweeping', 'addonGarageSweeping'
            ]
            
            for field in addon_fields:
                value = int(request.POST.get(field, 0))
                if value > 0:
                    setattr(booking, field, value)
            
            booking.save()

            for addon in customAddons:
                quantity = int(request.POST.get(f'custom_addon_qty_{addon.id}', 0))
                if quantity > 0:
                    newCustomBookingAddon = BookingCustomAddons.objects.create(
                        addon=addon,
                        qty=quantity
                    )
                    booking.customAddons.add(newCustomBookingAddon)


            messages.success(request, 'Booking created successfully!')
            return redirect('bookings:booking_detail', bookingId=booking.bookingId)
            
        except Exception as e:
            raise Exception(f'Error creating booking: {str(e)}')
    
    
    prices = {
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
        'addonPriceGreen': float(business_settings.addonPriceGreen),
        'addonPriceCabinets': float(business_settings.addonPriceCabinets),
        'addonPricePatio': float(business_settings.addonPricePatio),
        'addonPriceGarage': float(business_settings.addonPriceGarage),
        'tax': float(business_settings.taxPercent)
    }

    context = {
        'customAddons': customAddons,
        'prices': json.dumps(prices)
    }

    return render(request, 'create_booking.html', context)

@require_http_methods(["GET", "POST"])
@transaction.atomic
def edit_booking(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    business = booking.business
    business_settings = BusinessSettings.objects.get(business=business)
    customAddons = CustomAddons.objects.filter(business=business)
    
    # Check if user has permission to edit this booking
    if booking.business not in request.user.business_set.all():
        messages.error(request, 'You do not have permission to edit this booking')
        return redirect('bookings:all_bookings')
    
    if request.method == "POST":
        try:
            # Get price details from form
            totalPrice = Decimal(request.POST.get('totalAmount', '0'))
            tax = Decimal(request.POST.get('tax', '0'))

            # Update booking details
            booking.firstName = request.POST.get('firstName')
            booking.lastName = request.POST.get('lastName')
            booking.email = request.POST.get('email')
            booking.phoneNumber = request.POST.get('phoneNumber')
            booking.companyName = request.POST.get('companyName', '')

            booking.address1 = request.POST.get('address1')
            booking.city = request.POST.get('city')
            booking.stateOrProvince = request.POST.get('stateOrProvince')
            booking.zipCode = request.POST.get('zipCode')

            # Handle numeric fields with proper default values
            booking.bedrooms = int(request.POST.get('bedrooms', '0').strip() or '0')
            booking.bathrooms = int(request.POST.get('bathrooms', '0').strip() or '0')
            booking.squareFeet = int(request.POST.get('squareFeet', '0').strip() or '0')

            booking.serviceType = request.POST.get('serviceType')
            booking.cleaningDate = request.POST.get('cleaningDate')
            booking.startTime = request.POST.get('startTime')
            booking.recurring = request.POST.get('recurring')

            booking.otherRequests = request.POST.get('otherRequests', '')
            booking.tax = tax
            booking.totalPrice = totalPrice

            # Assign cleaner if selected
            cleaner_id = request.POST.get('selectedCleaner')
            if cleaner_id:
                try:
                    cleaner = Cleaners.objects.get(id=cleaner_id)
                    booking.cleaner = cleaner
                    booking.save()
                except Cleaners.DoesNotExist:
                    pass  # Silently ignore if cleaner doesn't exist

            # Handle standard add-ons with proper default values
            addon_fields = [
                'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
                'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
                'addonBaseboard', 'addonBlinds', 'addonGreenCleaning',
                'addonCabinetsCleaning', 'addonPatioSweeping', 'addonGarageSweeping'
            ]
            
            for field in addon_fields:
                value = request.POST.get(field, '0').strip() or '0'
                setattr(booking, field, int(value))
            
            # Clear existing custom add-ons
            booking.customAddons.clear()

            # Add new custom add-ons
            for addon in customAddons:
                quantity = int(request.POST.get(f'custom_addon_qty_{addon.id}', 0))
                if quantity > 0:
                    newCustomBookingAddon = BookingCustomAddons.objects.create(
                        addon=addon,
                        qty=quantity
                    )
                    booking.customAddons.add(newCustomBookingAddon)

            booking.save()

            #Update Invoice
            invoice = Invoice.objects.filter(booking=booking)
            if invoice.exists():
                invoice = invoice.first()
                invoice.amount = totalPrice
                invoice.save()

            messages.success(request, 'Booking updated successfully!')
            return redirect('bookings:booking_detail', bookingId=booking.bookingId)
            
        except Exception as e:
            raise Exception(f'Error updating booking: {str(e)}')

    # For GET request, prepare the context
    prices = {
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
        'addonPriceGreen': float(business_settings.addonPriceGreen),
        'addonPriceCabinets': float(business_settings.addonPriceCabinets),
        'addonPricePatio': float(business_settings.addonPricePatio),
        'addonPriceGarage': float(business_settings.addonPriceGarage),
        'tax': float(business_settings.taxPercent)
    }

    context = {
        'booking': booking,
        'customAddons': customAddons,
        'prices': json.dumps(prices),
        'existing_custom_addons': {addon.addon.id: addon.qty for addon in booking.customAddons.all()}
    }

    return render(request, 'edit_booking.html', context)


def mark_completed(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    booking.isCompleted = True
    booking.save()
    messages.success(request, 'Booking marked as completed!')
    return redirect('bookings:all_bookings')


def delete_booking(request, bookingId):
    try:
        booking = get_object_or_404(Booking, bookingId=bookingId)
        booking.delete()
        messages.success(request, 'Booking deleted successfully!')
        return redirect('bookings:all_bookings')
    except Booking.DoesNotExist:
        messages.error(request, 'Booking not found')
        return redirect('bookings:all_bookings')



@login_required
def booking_detail(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    context = {
        'booking': booking
    }
    return render(request, 'booking_detail.html', context)

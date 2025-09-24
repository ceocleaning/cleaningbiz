from datetime import timedelta, datetime, date
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from .models import Booking, BookingCustomAddons
from invoice.models import Invoice, Payment
from accounts.models import Business, BusinessSettings, CustomAddons
from automation.models import CleanerAvailability, Cleaners, OpenJob
from customer.models import Customer
from decimal import Decimal
import json
from django.db.models import Min, Count
from django.http import JsonResponse
from automation.utils import format_phone_number
from django.utils import timezone
import pytz

@login_required
def all_bookings(request):
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    # Get the business and its timezone
    business = request.user.business_set.first()
    
    # Get all bookings for the user's business
    all_bookings = Booking.objects.filter(business__user=request.user)

    cancelled_bookings = all_bookings.filter(cancelled_at__isnull=False)
    
    # Get current date in business's timezone
    today = business.get_local_time().date()
    
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
        'business': business  # Add business to context for template filters
    }
    return render(request, 'bookings/bookings.html', context)

@login_required
def customers(request):
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    # Get the business for the current user
    business = request.user.business_set.first()
    
    # Get all unique customers who have bookings with this business
    customers_with_bookings = Customer.objects.filter(
        booking__business=business
    ).distinct()
    
    # Create a list to store customer data with booking statistics
    customers_list = []
    
    for customer in customers_with_bookings:
        # Get all bookings for this customer with this business
        customer_bookings = Booking.objects.filter(
            business=business,
            customer=customer
        )
        
        # Calculate statistics
        booking_count = customer_bookings.count()
        total_spent = sum(booking.totalPrice for booking in customer_bookings)
        
        # Get the earliest booking date as joined date
        first_booking = customer_bookings.order_by('createdAt').first()
        joined_date = first_booking.createdAt if first_booking else customer.created_at
        
        # Create identifier for customer detail page
        identifier = customer.email if customer.email else customer.phone_number
        
        # Add customer to the list
        customers_list.append({
            'firstName': customer.first_name,
            'lastName': customer.last_name,
            'email': customer.email,
            'phoneNumber': customer.phone_number,
            'joinedDate': joined_date,
            'bookingCount': booking_count,
            'totalSpent': total_spent,
            'identifier': identifier,
            'customer_id': customer.id  # Include customer ID for direct reference
        })
    
    # Sort customers by joined date (newest first)
    customers_list.sort(key=lambda x: x['joinedDate'], reverse=True)
    
    context = {
        'customers': customers_list,
        'total_customers': len(customers_list)
    }
    
    return render(request, 'bookings/customers.html', context)

@login_required
def customer_detail(request, identifier):
    """View for displaying a specific customer's details and booking history."""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    
    # Determine if identifier is an email or phone
    if '@' in identifier:
        # It's an email
        try:
            customer = Customer.objects.get(email=identifier)
            identifier_type = 'email'
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
            return redirect('bookings:customers')
    else:
        # It's a phone number
        try:
            customer = Customer.objects.get(phone_number=identifier)
            identifier_type = 'phone'
        except Customer.DoesNotExist:
            messages.error(request, 'Customer not found.')
            return redirect('bookings:customers')
    
    # Get all bookings for this customer with this business
    bookings = Booking.objects.filter(
        business=business,
        customer=customer
    ).order_by('-createdAt')
    
    if not bookings.exists():
        messages.error(request, 'No bookings found for this customer with your business.')
        return redirect('bookings:customers')
    
    # Calculate statistics
    total_spent = sum(booking.totalPrice for booking in bookings)
    completed_bookings = bookings.filter(isCompleted=True).count()
    pending_bookings = bookings.filter(isCompleted=False).count()
    
    # Find the first booking to determine join date
    first_booking = bookings.order_by('createdAt').first()
    join_date = first_booking.createdAt if first_booking else customer.created_at
    
    # Service type distribution
    service_stats = {}
    for booking in bookings:
        service_type = booking.get_serviceType_display()
        if service_type in service_stats:
            service_stats[service_type] += 1
        else:
            service_stats[service_type] = 1
    
    # Get company name from most recent booking if available
    most_recent_booking = bookings.first()
    company_name = most_recent_booking.companyName if most_recent_booking and hasattr(most_recent_booking, 'companyName') else ''
    
    context = {
        'customer': {
            'firstName': customer.first_name,
            'lastName': customer.last_name,
            'email': customer.email,
            'phoneNumber': customer.phone_number,
            'companyName': company_name,
            'joinDate': join_date,
            'identifier': identifier,
            'identifier_type': identifier_type,
            'address': customer.address,
            'city': customer.city,
            'state': customer.state_or_province,
            'zipCode': customer.zip_code
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
    
    return render(request, 'bookings/customer_detail.html', context)




@require_http_methods(["GET", "POST"])
@login_required
@transaction.atomic
def create_booking(request):
    from datetime import datetime, timedelta
    import pytz
    from accounts.timezone_utils import convert_to_utc

    redirect_url = request.GET.get('next')

  
    
    business = Business.objects.get(user=request.user)
    business_settings = BusinessSettings.objects.get(business=business)
    # Get business timezone from model or form submission
    business_timezone = business.timezone
    
  
    customAddons = CustomAddons.objects.filter(business=business)
    if request.method == 'POST':
        try:
            # Get price details from form
            totalPrice = Decimal(request.POST.get('totalAmount', '0'))
            tax = Decimal(request.POST.get('tax', '0'))
            
            
            cleaningDate = request.POST.get('cleaningDate')
            start_time = request.POST.get('startTime')



            # Convert cleaning date and time from business timezone to UTC
            start_time_utc = convert_to_utc(
                cleaningDate + ' ' + start_time,
                business_timezone
            ).time()

            end_time_utc = (datetime.strptime(start_time_utc.strftime('%H:%M'), '%H:%M') + timedelta(hours=1)).strftime('%H:%M')



            # Check customer type selection
            customer_type = request.POST.get('customerType')
            
            if customer_type == 'regular':
                # Get existing customer by ID
                customer_id = request.POST.get('customerId')
                try:
                    customer = Customer.objects.get(id=customer_id)
                except Customer.DoesNotExist:
                    messages.error(request, 'Selected customer not found.')
                    return redirect('bookings:create_booking')
            else:
                # Create new customer
                customer_email = request.POST.get('email')
                phone_number = request.POST.get('phoneNumber')
                if phone_number:
                    phone_number = format_phone_number(phone_number)

                if not phone_number:
                    messages.error(request, 'Please enter a valid US phone number.')
                    return redirect('bookings:create_booking')
                
                try:
                    customer = Customer.objects.get(email=customer_email)
                except Customer.DoesNotExist:
                    customer = None
                
                if not customer:
                    customer = Customer.objects.create(
                        first_name=request.POST.get('firstName'),
                        last_name=request.POST.get('lastName'),
                        email=customer_email,
                        phone_number=request.POST.get('phoneNumber'),
                        address=request.POST.get('address1'),
                        city=request.POST.get('city'),
                        state_or_province=request.POST.get('stateOrProvince'),
                        zip_code=request.POST.get('zipCode'),
                    )
            
            # Create the booking
            booking = Booking.objects.create(
                business=business,
                customer=customer,
                bedrooms=Decimal(request.POST.get('bedrooms', 0)),
                bathrooms=Decimal(request.POST.get('bathrooms', 0)),
                squareFeet=Decimal(request.POST.get('squareFeet', 0)),

                serviceType=request.POST.get('serviceType'),
                # Convert cleaning date and time from business timezone to UTC
                cleaningDate=cleaningDate,
                startTime=start_time_utc,
                endTime=end_time_utc,
              
                recurring=request.POST.get('recurring'),
                paymentMethod=request.POST.get('paymentMethod', 'creditcard'),

                otherRequests=request.POST.get('otherRequests', ''),
                tax=tax,
                totalPrice=totalPrice
            )
            
            
            

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
                quantity_str = request.POST.get(f'custom_addon_qty_{addon.id}', '0').strip()
                # Handle empty string case by defaulting to 0
                quantity = int(quantity_str) if quantity_str else 0
                if quantity > 0:
                    newCustomBookingAddon = BookingCustomAddons.objects.create(
                        addon=addon,
                        qty=quantity
                    )
                    booking.customAddons.add(newCustomBookingAddon)
            

            # Import threading for background execution
            import threading
            from automation.webhooks import send_booking_data
            webhook_thread = threading.Thread(target=send_booking_data, args=(booking,))
            webhook_thread.daemon = True
            webhook_thread.start()
            
          


            messages.success(request, 'Booking created successfully!')
            return redirect(redirect_url if redirect_url else 'bookings:booking_detail', bookingId=booking.bookingId)
        
        except Business.DoesNotExist:
            messages.error(request, 'Business not found')
            return redirect(redirect_url if redirect_url else 'bookings:all_bookings')
            
        except Exception as e:
            messages.error(request, f'Error creating booking: {str(e)}')
            return redirect(redirect_url if redirect_url else 'bookings:all_bookings')
    
    
    prices = {
        'bedrooms': float(business_settings.bedroomPrice),
        'bathrooms': float(business_settings.bathroomPrice),
        'sqftMultiplierStandard': float(business_settings.sqftMultiplierStandard),
        'sqftMultiplierDeep': float(business_settings.sqftMultiplierDeep),
        'sqftMultiplierMoveinout': float(business_settings.sqftMultiplierMoveinout),
        'sqftMultiplierAirbnb': float(business_settings.sqftMultiplierAirbnb),
        'base_price': float(business_settings.base_price),

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

    # Get all customers for this business
    customers = Customer.objects.filter(booking__business=business).distinct()
    
    context = {
        'customAddons': customAddons,
        'prices': json.dumps(prices),
        'business_timezone': business_timezone,
        'customers': customers,
        'today': date.today()
    }

    return render(request, 'bookings/create_booking.html', context)



@require_http_methods(["GET", "POST"])
@login_required
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
            booking.customer.first_name = request.POST.get('firstName')
            booking.customer.last_name = request.POST.get('lastName')
            booking.customer.email = request.POST.get('email')
            phone_number = request.POST.get('phoneNumber')
            if phone_number:
                phone_number = format_phone_number(phone_number)

            if not phone_number:
                messages.error(request, 'Please enter a valid US phone number.')
                return redirect('bookings:edit_booking', bookingId=bookingId)
            booking.customer.phone_number = phone_number

            booking.customer.address = request.POST.get('address1')
            booking.customer.city = request.POST.get('city')
            booking.customer.state_or_province = request.POST.get('stateOrProvince')
            booking.customer.zip_code = request.POST.get('zipCode')

            # Handle numeric fields with proper default values
            booking.bedrooms = Decimal(request.POST.get('bedrooms', '0').strip() or '0')
            booking.bathrooms = Decimal(request.POST.get('bathrooms', '0').strip() or '0')
            booking.squareFeet = Decimal(request.POST.get('squareFeet', '0').strip() or '0')

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
                quantity_str = request.POST.get(f'custom_addon_qty_{addon.id}', '0').strip()
                # Handle empty string case by defaulting to 0
                quantity = int(quantity_str) if quantity_str else 0
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
        'customAddons': customAddons,
        'prices': json.dumps(prices),
        'today': timezone.now().date(),
        'business_timezone': business_timezone
    }

    return render(request, 'bookings/create_booking.html', context)

# ... (rest of the code remains the same)
def mark_completed(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    booking.isCompleted = True
    booking.save()
    messages.success(request, 'Booking marked as completed!')
    return redirect('bookings:all_bookings')


def delete_booking(request, bookingId):
    try:
        booking = get_object_or_404(Booking, bookingId=bookingId)
        if request.user == booking.business.user or booking.customer.user == request.user:
            booking.delete()
            messages.success(request, 'Booking deleted successfully!')
        else:
            messages.error(request, 'You do not have permission to delete this booking')
        
        

    except Booking.DoesNotExist:
        messages.error(request, 'Booking not found')
    
    if hasattr(request.user, 'customer') and request.user.customer:
        return redirect('customer:bookings')

    return redirect('bookings:all_bookings')



@login_required
def booking_detail(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    context = {
        'booking': booking
    }
    return render(request, 'bookings/booking_detail.html', context)


@require_http_methods(["POST"])
@login_required
def bulk_delete_bookings(request):
    try:
        data = json.loads(request.body)
        booking_ids = data.get('booking_ids', [])
        
        if not booking_ids:
            return JsonResponse({'success': False, 'error': 'No bookings selected'})
        
        # Get bookings that belong to the user's business
        bookings = Booking.objects.filter(
            bookingId__in=booking_ids
        )

        if hasattr(request.user, 'customer') and request.user.customer:
            bookings = bookings.filter(customer=request.user.customer)
        else:
            bookings = bookings.filter(business__user=request.user)
        
        # Delete the bookings
        deleted_count = bookings.count()
        bookings.delete()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully deleted {deleted_count} booking(s)'
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'success': False, 'error': 'Invalid JSON data'})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

@login_required
def booking_calendar(request):
    """
    Display a Google Calendar style view of all bookings.
    """
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    
    # Get the month and year from the request, default to current month
    today = timezone.now().date()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    # Calculate first day of the month and last day of the month
    first_day = date(year, month, 1)
    
    # Calculate last day of month
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    last_day = date(next_year, next_month, 1) - timedelta(days=1)
    
    # Calculate previous and next month for navigation
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    # Get month name
    month_name = first_day.strftime('%B')
    
    # Get day names for the calendar header
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Calculate the first day to display (might be from the previous month)
    first_weekday = first_day.weekday()
    # Adjust for Sunday as first day (Python uses Monday=0, Sunday=6)
    first_display_day = first_day - timedelta(days=(first_weekday + 1) % 7)
    
    # Query all bookings for this business in the displayed period
    # Include 6 weeks to cover the entire month view
    display_end = first_display_day + timedelta(days=42)  # Max 6 weeks
    
    bookings = Booking.objects.filter(
        business=business,
        cleaningDate__gte=first_display_day,
        cleaningDate__lte=display_end
    ).select_related('cleaner').order_by('startTime')
    
    # Define working hours for the day columns (6 AM to 11 PM)
    working_hours = list(range(6, 24))  # 6 AM to 11 PM
    
    # Get current time in business timezone for the now indicator
    utc_now = timezone.now()
    business_timezone = business.get_timezone()
    local_now = utc_now.astimezone(business_timezone)
    
    current_hour = local_now.hour
    current_minute = local_now.minute
    # Calculate position for the now indicator (pixels from top)
    current_time_position = (current_hour - working_hours[0]) * 60 + current_minute
    
    # Organize bookings by date
    bookings_by_date = {}
    for booking in bookings:
        if booking.cleaningDate not in bookings_by_date:
            bookings_by_date[booking.cleaningDate] = []
        
        status = "Pending"
        if booking.isCompleted:
            status = "Completed"
        elif hasattr(booking, 'invoice') and booking.invoice:
            if booking.invoice.isPaid:
                status = "Paid"
            else:
                status = "Unpaid"
        
        # Convert UTC times to business timezone
        business_timezone = business.get_timezone()
        
        # Create datetime objects in UTC
        utc_start_datetime = datetime.combine(booking.cleaningDate, booking.startTime)
        utc_start_datetime = pytz.utc.localize(utc_start_datetime) if utc_start_datetime.tzinfo is None else utc_start_datetime
        
        # Convert to business timezone
        local_start_datetime = utc_start_datetime.astimezone(business_timezone)
        
        # Get the time component for positioning
        start_time_obj = datetime.strptime(local_start_datetime.strftime('%H:%M'), '%H:%M')
        
        # Handle end time
        if booking.endTime:
            utc_end_datetime = datetime.combine(booking.cleaningDate, booking.endTime)
            utc_end_datetime = pytz.utc.localize(utc_end_datetime) if utc_end_datetime.tzinfo is None else utc_end_datetime
            local_end_datetime = utc_end_datetime.astimezone(business_timezone)
            end_time_obj = datetime.strptime(local_end_datetime.strftime('%H:%M'), '%H:%M')
        else:
            # Default to 1 hour duration if no end time
            end_time_obj = start_time_obj + timedelta(hours=1)
        
        # Calculate hours and minutes for positioning
        hour = start_time_obj.hour
        minute = start_time_obj.minute
        
        # Calculate duration in minutes
        duration_minutes = (end_time_obj.hour * 60 + end_time_obj.minute) - (hour * 60 + minute)
        # Convert to pixels (1 minute = 1 pixel in height)
        duration_pixels = max(25, duration_minutes)  # Minimum height of 25px
        
        bookings_by_date[booking.cleaningDate].append({
            'id': booking.bookingId,
            'time': local_start_datetime.time(),  # Use local time instead of UTC
            'hour': hour,  # For positioning in the correct hour row
            'minute': minute,  # For positioning within the hour
            'duration': duration_pixels,  # For determining height of booking
            'client_name': booking.customer.get_full_name() if booking.customer else "Unassigned",
            'service_type': booking.get_serviceType_display(),
            'status': status,
            'cleaner': booking.cleaner.name if booking.cleaner else "Unassigned"
        })
    
    # Build the calendar
    calendar_weeks = []
    current_day = first_display_day
    
    for _ in range(6):  # Maximum 6 weeks in a month view
        week = []
        for i in range(7):  # 7 days in a week
            # Get the weekday index (0=Sunday, 1=Monday, etc)
            weekday = current_day.weekday()
            # Adjust from Python's Monday=0 to Sunday=0
            weekday = (weekday + 1) % 7
            
            day_data = {
                'day': current_day.day,
                'date': current_day,
                'weekday': weekday,  # Add the weekday index
                'formatted_date': current_day.strftime('%B %d, %Y'),
                'other_month': current_day.month != month,
                'is_today': current_day == today,
                'bookings': bookings_by_date.get(current_day, [])
            }
            week.append(day_data)
            current_day += timedelta(days=1)
        
        calendar_weeks.append(week)
        
        # If we've gone past the end of the month and completed a week, we can stop
        if current_day.month != month and current_day.weekday() == 6:
            break
    
    context = {
        'month_name': month_name,
        'year': year,
        'day_names': day_names,
        'calendar_weeks': calendar_weeks,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year,
        'working_hours': working_hours,
        'current_time_position': current_time_position
    }
    
    return render(request, 'bookings/booking_calendar.html', context)


# Embed Booking Widget instructions page
@login_required
def embed_booking_widget(request):
    return render(request, 'bookings/embed_booking_widget.html')


@login_required
def booking_history_data(request):
    """
    API endpoint to fetch booking history data for the customer dashboard chart.
    Returns monthly booking counts and payment amounts for the last 6 months.
    """
    from django.db.models import Count, Sum
    from django.db.models.functions import TruncMonth
    import datetime
    
    # Determine if the request is from a customer or business user
    if hasattr(request.user, 'customer') and request.user.customer:
        # Customer view - show their own booking history
        customer = request.user.customer
        
        # Get the last 6 months of data
        end_date = datetime.date.today()
        start_date = (end_date - datetime.timedelta(days=180))  # Approximately 6 months
        
        # Get bookings for this customer in the date range
        bookings = Booking.objects.filter(
            customer=customer
        )
        
        # Group by month and count bookings
        booking_counts = bookings.annotate(
            month=TruncMonth('cleaningDate')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('month')
        
        # Get payment amounts by month
        payment_amounts = bookings.annotate(
            month=TruncMonth('cleaningDate')
        ).values('month').annotate(
            amount=Sum('totalPrice')
        ).order_by('month')
        
    else:
        # Business view - not applicable for this endpoint
        return JsonResponse({'error': 'This endpoint is only available for customer users'}, status=403)
    
    # Format the data for the chart
    months = []
    booking_counts_data = []
    payment_amounts_data = []
    
    # Create a dictionary to easily look up values by month
    counts_by_month = {item['month'].strftime('%Y-%m'): item['count'] for item in booking_counts}
    amounts_by_month = {item['month'].strftime('%Y-%m'): float(item['amount']) for item in payment_amounts}
    
    # Generate data for the last 6 months, including months with zero bookings
    for i in range(5, -1, -1):
        # Calculate month date
        month_date = end_date - datetime.timedelta(days=i*30)  # Approximate
        month_key = month_date.strftime('%Y-%m')
        month_name = month_date.strftime('%b')  # Short month name
        
        months.append(month_name)
        booking_counts_data.append(counts_by_month.get(month_key, 0))
        payment_amounts_data.append(amounts_by_month.get(month_key, 0))
    
    # Return the formatted data
    return JsonResponse({
        'months': months,
        'bookingCounts': booking_counts_data,
        'paymentAmounts': payment_amounts_data
    })

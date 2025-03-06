from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
import logging
from .models import Lead, Cleaners, CleanerAvailability
from bookings.models import Booking
from accounts.models import ApiCredential, Business
from retell import Retell
import random
import pytz

logger = logging.getLogger(__name__)

@login_required(login_url='accounts:login')
def home(request):
    # Get the user's business
    business = request.user.business_set.first()

    if not business:
        return redirect('accounts:register_business')

    bookings = Booking.objects.filter(business=business).order_by('-createdAt')
    leads = Lead.objects.filter(business=business).order_by('-createdAt')
    converted_leads = leads.filter(isConverted=True)
    total_leads = leads.count()
    credentials = ApiCredential.objects.filter(business=business).first()

    context = {
        'leads': leads, 
        'bookings': bookings,
        'credentials': credentials,
        'total_leads': total_leads,
        'converted_leads': converted_leads.count(),
        'total_bookings': bookings.count()
    }
    return render(request, 'home.html', context)    







@login_required
def all_leads(request):
    if not request.user.business_set.first():
        return redirect('accounts:register_business')
    leads = Lead.objects.filter(business__user=request.user).order_by('-createdAt')
    context = {
        'leads': leads
    }
    return render(request, 'leads.html', context)


@login_required
def lead_detail(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    context = {
        'lead': lead
    }
    return render(request, 'lead_detail.html', context)


@login_required
def create_lead(request):
    if request.method == 'POST':
        try:
            lead = Lead.objects.create(
              
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phone_number=request.POST.get('phone_number'),
                source=request.POST.get('source'),
                notes=request.POST.get('notes'),
                content=request.POST.get('content'),
                business=request.user.business_set.first()
            )
            messages.success(request, f'Lead {lead.leadId} created successfully!')
            return redirect('lead_detail', leadId=lead.leadId)
        except Exception as e:
            messages.error(request, f'Error creating lead: {str(e)}')
            return redirect('create_lead')
    
    return render(request, 'create_lead.html')


@login_required
def update_lead(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    
    if request.method == 'POST':
        try:
            lead.name = request.POST.get('name')
            lead.email = request.POST.get('email')
            lead.phone_number = request.POST.get('phone_number')
            lead.source = request.POST.get('source')
            lead.notes = request.POST.get('notes')
            lead.content = request.POST.get('content')
            lead.isConverted = 'isConverted' in request.POST
            lead.save()
            
            messages.success(request, f'Lead {lead.leadId} updated successfully!')
            return redirect('lead_detail', leadId=lead.leadId)
        except Exception as e:
            messages.error(request, f'Error updating lead: {str(e)}')
    
    context = {
        'lead': lead
    }
    return render(request, 'update_lead.html', context)


@login_required
def delete_lead(request, leadId):
    lead = get_object_or_404(Lead, leadId=leadId)
    
    if request.method == 'POST':
        try:
            lead.delete()
            messages.success(request, 'Lead deleted successfully!')
            return redirect('all_leads')
        except Exception as e:
            messages.error(request, f'Error deleting lead: {str(e)}')
            return redirect('lead_detail', leadId=leadId)
    
    return redirect('lead_detail', leadId=leadId)


@login_required
def cleaners_list(request):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    cleaners = Cleaners.objects.filter(business=business)
    
    # Get availability for each cleaner
    for cleaner in cleaners:
        cleaner.availabilities = CleanerAvailability.objects.filter(cleaner=cleaner).order_by('dayOfWeek')
    
    context = {
        'cleaners': cleaners,
        'title': 'Cleaners',
    }
    return render(request, 'automation/cleaners.html', context)


@login_required
def add_cleaner(request):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    if request.method == 'POST':
        try:
            # Create cleaner
            cleaner = Cleaners.objects.create(
                business=business,
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phoneNumber=request.POST.get('phoneNumber'),
                isActive=True
            )
            
            # Create default availability for each day
            weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            default_start_time = '09:00'
            default_end_time = '17:00'
            
            for day in weekdays:
                CleanerAvailability.objects.create(
                    cleaner=cleaner,
                    availability_type='weekly',
                    dayOfWeek=day,
                    startTime=default_start_time,
                    endTime=default_end_time
                )
            
            messages.success(request, 'Cleaner added successfully.')
            return redirect('cleaner_detail', cleaner_id=cleaner.id)
            
        except Exception as e:
            messages.error(request, f'Error adding cleaner: {str(e)}')
            return redirect('cleaners_list')
    
    return redirect('cleaners_list')


@login_required
def cleaner_detail(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    # Define the correct order of days
    day_order = {
        'Monday': 0,
        'Tuesday': 1,
        'Wednesday': 2,
        'Thursday': 3,
        'Friday': 4,
        'Saturday': 5,
        'Sunday': 6
    }
    
    # Get cleaner's availability schedule - keep the QuerySet for filtering later
    weekly_availabilities_queryset = CleanerAvailability.objects.filter(
        cleaner=cleaner, 
        availability_type='weekly'
    )
    
    # Create a sorted list for display
    weekly_availabilities = sorted(weekly_availabilities_queryset, key=lambda x: day_order.get(x.dayOfWeek, 7))
    
    specific_availabilities = CleanerAvailability.objects.filter(
        cleaner=cleaner, 
        availability_type='specific'
    ).order_by('specific_date')
    
    # Get current date and time
    now = timezone.now()
    current_date = now.date()
    current_time = now.time()
    
    # Check if a specific date was provided in the URL
    date_str = request.GET.get('date', None)
    if date_str:
        try:
            # Parse the date from the URL parameter
            selected_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        except ValueError:
            # If date is invalid, default to current date
            selected_date = current_date
    else:
        # Default to current date if no date parameter
        selected_date = current_date
    
    # Calculate the date of Monday for the week containing the selected date
    selected_weekday_num = selected_date.weekday()
    monday_date = selected_date - timedelta(days=selected_weekday_num)
    
    # Calculate the date of Sunday for this week
    sunday_date = monday_date + timedelta(days=6)
    
    # Calculate dates for previous and next week navigation
    prev_week_monday = monday_date - timedelta(days=7)
    next_week_monday = monday_date + timedelta(days=7)
    
    # Group specific date exceptions by weekday for easy lookup
    specific_by_weekday = {}
    current_week_exceptions_by_weekday = {}
    
    for avail in specific_availabilities:
        weekday = avail.specific_date.strftime('%A')
        
        # Add to general exceptions dictionary
        if weekday not in specific_by_weekday:
            specific_by_weekday[weekday] = []
        specific_by_weekday[weekday].append(avail)
        
        # Add to current week exceptions dictionary if the date is in the current week
        if monday_date <= avail.specific_date <= sunday_date:
            if weekday not in current_week_exceptions_by_weekday:
                current_week_exceptions_by_weekday[weekday] = []
            current_week_exceptions_by_weekday[weekday].append(avail)
    
    logger.info(f"Fetching bookings for cleaner {cleaner.name} at {now}")
    
    # Get cleaner's current booking (if any)
    current_booking = Booking.objects.filter(
        cleaner=cleaner,
        cleaningDate=current_date,
        startTime__lte=current_time,
        endTime__gt=current_time
    ).first()
    
    if current_booking:
        logger.info(f"Current booking found: {current_booking.id}")
    
    # Get upcoming bookings (future bookings)
    upcoming_bookings = Booking.objects.filter(
        cleaner=cleaner
    ).filter(
        # Future dates OR current date with future start time
        models.Q(cleaningDate__gt=current_date) |
        models.Q(cleaningDate=current_date, startTime__gt=current_time)
    ).exclude(
        id=current_booking.id if current_booking else None
    ).order_by('cleaningDate', 'startTime')[:5]
    
    logger.info(f"Found {upcoming_bookings.count()} upcoming bookings")
    
    # Get past bookings
    past_bookings = Booking.objects.filter(
        cleaner=cleaner
    ).filter(
        # Past dates OR current date with past end time
        models.Q(cleaningDate__lt=current_date) |
        models.Q(cleaningDate=current_date, endTime__lte=current_time)
    ).exclude(
        id=current_booking.id if current_booking else None
    ).order_by('-cleaningDate', '-startTime')[:5]
    
    logger.info(f"Found {past_bookings.count()} past bookings")
    
    # Calculate availability status
    is_available = True
    current_weekday = now.strftime('%A')
    
    # First check if there's a specific date entry for today
    today_specific_availability = specific_availabilities.filter(specific_date=current_date).first()
    
    if today_specific_availability:
        # Specific date entry takes precedence
        is_available = (
            not today_specific_availability.offDay and
            today_specific_availability.startTime <= current_time <= today_specific_availability.endTime
            and not current_booking
        )
    else:
        # Fall back to weekly schedule
        today_weekly_availability = weekly_availabilities_queryset.filter(dayOfWeek=current_weekday).first()
        if today_weekly_availability:
            is_available = (
                not today_weekly_availability.offDay and
                today_weekly_availability.startTime <= current_time <= today_weekly_availability.endTime
                and not current_booking
            )
        else:
            is_available = False
    
    context = {
        'cleaner': cleaner,
        'weekly_availabilities': weekly_availabilities,
        'specific_availabilities': specific_availabilities,
        'specific_by_weekday': specific_by_weekday,
        'current_week_exceptions_by_weekday': current_week_exceptions_by_weekday,
        'current_booking': current_booking,
        'upcoming_bookings': upcoming_bookings,
        'past_bookings': past_bookings,
        'is_available': is_available,
        'today': current_date,
        'monday_date': monday_date,
        'sunday_date': sunday_date,
        'prev_week_monday': prev_week_monday,
        'next_week_monday': next_week_monday,
        'title': f'Cleaner - {cleaner.name}',
    }
    
    return render(request, 'automation/cleaner_detail.html', context)


@login_required
def update_cleaner_profile(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            # Update basic info
            cleaner.name = request.POST.get('name')
            cleaner.email = request.POST.get('email')
            cleaner.phoneNumber = request.POST.get('phoneNumber')
            cleaner.isActive = request.POST.get('isActive') == 'on'
            cleaner.save()
            
            messages.success(request, 'Cleaner profile updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating cleaner profile: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def update_cleaner_schedule(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            # Get form data for weekly schedule
            days = request.POST.getlist('dayOfWeek[]')
            start_times = request.POST.getlist('startTime[]')
            end_times = request.POST.getlist('endTime[]')
            off_days = request.POST.getlist('offDay[]')  # Get off days
            
            # Get specific date exceptions if present
            specific_dates = request.POST.getlist('specific_date[]', [])
            specific_start_times = request.POST.getlist('specific_startTime[]', [])
            specific_end_times = request.POST.getlist('specific_endTime[]', [])
            specific_off_days = request.POST.getlist('specific_offDay[]', [])
            
            # Delete existing weekly availabilities
            CleanerAvailability.objects.filter(cleaner=cleaner, availability_type='weekly').delete()
            
            # Define the correct order of days
            day_order = {
                'Monday': 0,
                'Tuesday': 1,
                'Wednesday': 2,
                'Thursday': 3,
                'Friday': 4,
                'Saturday': 5,
                'Sunday': 6
            }
            
            # Create new weekly availabilities
            for i, day in enumerate(sorted(days, key=lambda x: day_order.get(x, 7))):
                is_off_day = day in off_days
                CleanerAvailability.objects.create(
                    cleaner=cleaner,
                    availability_type='weekly',
                    dayOfWeek=day,
                    startTime=start_times[i] if not is_off_day else None,
                    endTime=end_times[i] if not is_off_day else None,
                    offDay=is_off_day
                )
            
            # Process specific date exceptions
            if specific_dates:
                # Create or update specific date exceptions
                for i, date_str in enumerate(specific_dates):
                    if not date_str:  # Skip empty dates
                        continue
                        
                    specific_date = datetime.strptime(date_str, '%Y-%m-%d').date()
                    is_off_day = date_str in specific_off_days
                    
                    # Check if entry already exists
                    existing = CleanerAvailability.objects.filter(
                        cleaner=cleaner,
                        availability_type='specific',
                        specific_date=specific_date
                    ).first()
                    
                    if existing:
                        # Update existing
                        existing.startTime = specific_start_times[i] if not is_off_day else None
                        existing.endTime = specific_end_times[i] if not is_off_day else None
                        existing.offDay = is_off_day
                        existing.save()
                    else:
                        # Create new
                        CleanerAvailability.objects.create(
                            cleaner=cleaner,
                            availability_type='specific',
                            specific_date=specific_date,
                            startTime=specific_start_times[i] if not is_off_day else None,
                            endTime=specific_end_times[i] if not is_off_day else None,
                            offDay=is_off_day
                        )
            
            messages.success(request, 'Cleaner schedule updated successfully.')
        except Exception as e:
            messages.error(request, f'Error updating cleaner schedule: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def add_specific_date(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            specific_date = request.POST.get('specific_date')
            start_time = request.POST.get('start_time')
            end_time = request.POST.get('end_time')
            is_off_day = request.POST.get('is_off_day') == 'on'
            
            if not specific_date:
                raise ValueError('Date is required')
                
            # Convert to date object
            date_obj = datetime.strptime(specific_date, '%Y-%m-%d').date()
            
            # Check if entry already exists
            existing = CleanerAvailability.objects.filter(
                cleaner=cleaner,
                availability_type='specific',
                specific_date=date_obj
            ).first()
            
            if existing:
                # Update existing
                existing.startTime = start_time if not is_off_day else None
                existing.endTime = end_time if not is_off_day else None
                existing.offDay = is_off_day
                existing.save()
                messages.success(request, f'Updated exception for {specific_date}')
            else:
                # Create new
                CleanerAvailability.objects.create(
                    cleaner=cleaner,
                    availability_type='specific',
                    specific_date=date_obj,
                    startTime=start_time if not is_off_day else None,
                    endTime=end_time if not is_off_day else None,
                    offDay=is_off_day
                )
                messages.success(request, f'Added exception for {specific_date}')
                
        except Exception as e:
            messages.error(request, f'Error adding date exception: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def delete_specific_date(request, cleaner_id, exception_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    exception = get_object_or_404(CleanerAvailability, id=exception_id, cleaner=cleaner, availability_type='specific')
    
    try:
        date_str = exception.specific_date.strftime('%Y-%m-%d')
        exception.delete()
        messages.success(request, f'Removed exception for {date_str}')
    except Exception as e:
        messages.error(request, f'Error removing date exception: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def toggle_cleaner_availability(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            # Toggle availability
            cleaner.isAvailable = not cleaner.isAvailable
            cleaner.save()
            
            status = "available" if cleaner.isAvailable else "unavailable"
            messages.success(request, f'Cleaner marked as {status} successfully.')
        except Exception as e:
            messages.error(request, f'Error updating cleaner availability: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def delete_cleaner(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            cleaner_name = cleaner.name
            cleaner.delete()
            messages.success(request, f'Cleaner "{cleaner_name}" has been deleted successfully.')
            return redirect('cleaners_list')
        except Exception as e:
            messages.error(request, f'Error deleting cleaner: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def toggle_cleaner_active(request, cleaner_id):
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    if request.method == 'POST':
        try:
            # Toggle active status
            cleaner.isActive = not cleaner.isActive
            cleaner.save()
            
            status = "active" if cleaner.isActive else "inactive"
            messages.success(request, f'Cleaner marked as {status} successfully.')
        except Exception as e:
            messages.error(request, f'Error updating cleaner status: {str(e)}')
    
    return redirect('cleaner_detail', cleaner_id=cleaner.id)


@login_required
def test_availability_api(request):
    """
    Render a page to test the Retell availability API.
    """
    
    business = request.user.business_set.first()
    apiCred = ApiCredential.objects.filter(business=business).first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    context = {
        'business': business,
        'secretKey': apiCred.secretKey,
    }
    
    return render(request, 'automation/test_availability_api.html', context)


@login_required
def test_features(request):
    """
    Render a page that lists all available test features.
    """
    return render(request, 'automation/test_features.html')

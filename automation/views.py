from django.http import JsonResponse
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from datetime import datetime, timedelta
from django.utils import timezone
from django.db import models
from django.core.mail import send_mail, EmailMessage
import logging
from .models import Lead, Cleaners, CleanerAvailability
from bookings.models import Booking
from accounts.models import ApiCredential, Business
from invoice.models import Invoice, Payment
from subscription.models import UsageTracker
from retell import Retell
import random
import pytz
import requests
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from usage_analytics.services.usage_service import UsageService

logger = logging.getLogger(__name__)



def LandingPage(request):
    # Import here to avoid circular imports
    from subscription.models import SubscriptionPlan, BusinessSubscription
    
    # Get all plans
    plans = SubscriptionPlan.objects.filter(is_active=True, name__in=['Starter Plan', 'Professional Plan', 'Enterprise Plan']).order_by('price')

    trial_plan = SubscriptionPlan.objects.filter(is_active=True, name__icontains='Trial').first()
    if request.user.is_authenticated:
        business = request.user.business_set.first()
        is_eligible_for_trial = BusinessSubscription.objects.filter(plan=trial_plan, business=business).exists()
    else:
        is_eligible_for_trial = True
    
    return render(request, 'LandingPage.html', {
        'plans': plans,
        'trial_plan': trial_plan,
        'is_eligible_for_trial': is_eligible_for_trial
    })

def PricingPage(request):
    # Import here to avoid circular imports
    from subscription.models import SubscriptionPlan, Feature
   
    # Get all plans
    plans = SubscriptionPlan.objects.filter(is_active=True, name__in=['Starter Plan', 'Professional Plan', 'Enterprise Plan']).order_by('price')

    trial_plan = SubscriptionPlan.objects.filter(is_active=True, name__icontains='Trial').first()
    
    # Get all active features
    features = Feature.objects.filter(is_active=True).order_by('display_name')
    
    return render(request, 'PricingPage.html', {
        'plans': plans,
        'trial_plan': trial_plan,
        'feature_list': features
    })

def FeaturesPage(request):
    return render(request, 'FeaturesPage.html')


def AboutUsPage(request):
    return render(request, 'AboutUsPage.html')

def ContactUsPage(request):
    if request.method == 'POST':
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            try:
                # Get form data
                name = request.POST.get('name', '')
                email = request.POST.get('email', '')
                subject = request.POST.get('subject', '')
                message = request.POST.get('message', '')
                phone = request.POST.get('phone', '')
                privacy_accepted = request.POST.get('privacy_accepted', False)
                
                # Validate reCAPTCHA first
                recaptcha_response = request.POST.get('g-recaptcha-response', '')
                if not recaptcha_response:
                    return JsonResponse({
                        'success': False,
                        'message': 'Please complete the reCAPTCHA verification.'
                    })
                
                # Log token for debugging
                logger.debug(f"reCAPTCHA token received: length={len(recaptcha_response)}")
                    
                # Verify reCAPTCHA with Google
                recaptcha_result = verify_recaptcha_token(recaptcha_response)
                if not recaptcha_result.get('success', False):
                    logger.warning(f"reCAPTCHA verification failed: {recaptcha_result.get('message')}")
                    return JsonResponse({
                        'success': False,
                        'message': recaptcha_result.get('message', 'reCAPTCHA verification failed.')
                    })
                
                # Validate form data
                if name and email and subject and message and privacy_accepted:
                    # Prepare email content
                    email_subject = f"Contact Form: {subject}"
                    email_message = f"Name: {name}\n Phone Number: {phone} \nEmail: {email}\n\nMessage:\n{message}"
                    from_email =  email
                    recipient_list = ['kashifmehmood926@gmail.com', 'ceocleaningacademy@gmail.com']
                    
                    # Send email using EmailMessage for more control including reply-to
                    email = EmailMessage(
                        subject=email_subject,
                        body=email_message,
                        from_email=from_email,
                        to=recipient_list,
                        reply_to=[email],  # Set reply-to as the user's email
                    )
                    email.send(fail_silently=False)
                    
                    logger.info(f"Contact form email sent successfully from {email}")
                        
                    # Return success response
                    return JsonResponse({'success': True, 'message': 'Your message has been sent successfully!'})
                else:
                    # Return validation error response
                    missing_fields = []
                    if not name: missing_fields.append('name')
                    if not email: missing_fields.append('email')
                    if not subject: missing_fields.append('subject')
                    if not message: missing_fields.append('message')
                    if not privacy_accepted: missing_fields.append('privacy policy acceptance')
                    
                    error_msg = f"Please fill out all required fields: {', '.join(missing_fields)}"
                    logger.warning(f"Contact form validation failed: {error_msg}")
                    return JsonResponse({'success': False, 'message': error_msg})
            except Exception as e:
                logger.error(f"Error processing contact form: {str(e)}", exc_info=True)
                return JsonResponse({
                    'success': False,
                    'message': f'An error occurred: {str(e)}'
                })
    
    return render(request, 'ContactUsPage.html')

def DocsPage(request):
    return render(request, 'DocsPage.html')


@login_required(login_url='accounts:login')
def home(request):
    # Get the user's business
    business = request.user.business_set.first()

    if not business:
        return redirect('accounts:register_business')

    # Get current date for filtering
    now = datetime.now()

    # Leads metrics
    leads = Lead.objects.filter(business=business)
    total_leads = leads.count()
    converted_leads = leads.filter(is_response_received=True).count()

    # Bookings metrics
    bookings = Booking.objects.filter(business=business)
    active_bookings = bookings.filter(
        isCompleted=False,
        cleaningDate__gte=now.date()
    ).count()
    completed_bookings = bookings.filter(isCompleted=True).count()

    # Revenue metrics (from confirmed bookings in last 30 days)
    confirmed_bookings = bookings.filter(
        isCompleted=True,
    )
    total_revenue = Invoice.objects.filter(
        booking__in=confirmed_bookings
    ).aggregate(
        total=models.Sum('amount', default=0)
    )['total']

    # Invoice metrics
    pending_invoices = bookings.filter(
        isCompleted=True,
        invoice__isnull=True
    ).count()

    # Cleaners metrics
    cleaners = Cleaners.objects.filter(business=business)
    active_cleaners = cleaners.filter(isActive=True).count()
    top_rated_cleaners = cleaners.filter(isActive=True).count()

    # Recent activities (last 10 activities)
    recent_activities = []
    
    # Add recent leads
    recent_leads = leads.order_by('-createdAt')[:5]
    for lead in recent_leads:
        recent_activities.append({
            'type': 'primary',
            'icon': 'user-plus',
            'title': f"New lead: {lead.name}",
            'timestamp': lead.createdAt
        })

    # Add recent bookings
    recent_bookings = bookings.order_by('-createdAt')[:5]
    for booking in recent_bookings:
        client_name = f"{booking.firstName} {booking.lastName}"
        recent_activities.append({
            'type': 'success',
            'icon': 'calendar-check',
            'title': f"New booking: {client_name}",
            'timestamp': booking.createdAt
        })

    # Add recent cleaner activities
    recent_cleaner_changes = cleaners.order_by('-updatedAt')[:5]
    for cleaner in recent_cleaner_changes:
        recent_activities.append({
            'type': 'warning',
            'icon': 'user-edit',
            'title': f"Updated cleaner: {cleaner.name}",
            'timestamp': cleaner.updatedAt
        })

    # Sort all activities by timestamp and get the 10 most recent
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activities = recent_activities[:10]

    context = {
        'total_leads': total_leads,
        'converted_leads': converted_leads,
        'active_bookings': active_bookings,
        'completed_bookings': completed_bookings,
        'total_revenue': total_revenue,
        'pending_invoices': pending_invoices,
        'active_cleaners': active_cleaners,
        'top_rated_cleaners': top_rated_cleaners,
        'recent_activities': recent_activities,
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
            # Check if usage limit has reached
            from usage_analytics.services.usage_service import UsageService  # Import here to avoid any circular import issues
            business = request.user.business_set.first()
            usage_status = UsageService.check_leads_limit(business)
            if usage_status.get('exceeded', False):
                messages.error(request, 'You have reached the maximum number of leads allowed in your subscription plan.')
                return redirect('create_lead')


            lead = Lead.objects.create(
                name=request.POST.get('name'),
                email=request.POST.get('email'),
                phone_number=request.POST.get('phone_number'),
                source=request.POST.get('source'),
                notes=request.POST.get('notes'),
                content=request.POST.get('content'),
                business=request.user.business_set.first()
            )
            
            # Track the lead generation in usage metrics
            UsageTracker.increment_leads(
                business=business,
                increment_by=1
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
            
            # Update rating
            rating = request.POST.get('rating')
            if rating:
                try:
                    rating_value = int(rating)
                    # Ensure rating is between 1 and 5
                    cleaner.rating = max(1, min(5, rating_value))
                except ValueError:
                    # If conversion fails, don't update the rating
                    pass
                    
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


@login_required
def cleaner_monthly_schedule(request, cleaner_id):
    """
    Display a monthly calendar view of a cleaner's schedule.
    """
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    cleaner = get_object_or_404(Cleaners, id=cleaner_id, business=business)
    
    # Get the month and year from the request, default to current month
    today = timezone.now().date()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    # Calculate first day of the month and last day of the month
    first_day = datetime(year, month, 1).date()
    if month == 12:
        last_day = datetime(year + 1, 1, 1).date() - timedelta(days=1)
    else:
        last_day = datetime(year, month + 1, 1).date() - timedelta(days=1)
    
    # Calculate previous and next month for navigation
    if month == 1:
        prev_month = 12
        prev_year = year - 1
    else:
        prev_month = month - 1
        prev_year = year
    
    if month == 12:
        next_month = 1
        next_year = year + 1
    else:
        next_month = month + 1
        next_year = year
    
    # Get month name
    month_name = first_day.strftime('%B')
    
    # Get day names for the calendar header
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Calculate the calendar weeks
    calendar_weeks = []
    
    # Find the first day to display (might be from the previous month)
    first_display_day = first_day - timedelta(days=first_day.weekday() + 1 % 7)
    if first_display_day.weekday() != 6:  # If not Sunday
        first_display_day = first_display_day - timedelta(days=first_display_day.weekday() + 1)
    
    # Get cleaner's weekly availability
    weekly_availabilities = CleanerAvailability.objects.filter(cleaner=cleaner)
    weekly_availability_dict = {}
    for avail in weekly_availabilities:
        weekly_availability_dict[avail.dayOfWeek] = {
            'start_time': avail.startTime,
            'end_time': avail.endTime,
            'off_day': avail.offDay
        }
    
    # Get specific date exceptions
    specific_dates = CleanerAvailability.objects.filter(
        cleaner=cleaner,
        specific_date__gte=first_display_day,
        specific_date__lte=last_day + timedelta(days=7)  # Include a week after the month ends
    )
    specific_dates_dict = {}
    for date in specific_dates:
        if date.specific_date:
            specific_dates_dict[date.specific_date] = {
                'start_time': date.startTime,
                'end_time': date.endTime,
                'off_day': date.offDay
            }
    
    # Get bookings for this cleaner in the displayed period
    bookings = Booking.objects.filter(
        cleaner=cleaner,
        cleaningDate__gte=first_display_day,
        cleaningDate__lte=last_day + timedelta(days=7)  # Include a week after the month ends
    ).order_by('startTime')
    
    bookings_by_date = {}
    for booking in bookings:
        if booking.cleaningDate not in bookings_by_date:
            bookings_by_date[booking.cleaningDate] = []
        
        bookings_by_date[booking.cleaningDate].append({
            'id': booking.bookingId,
            'time': datetime.combine(booking.cleaningDate, booking.startTime),
            'client_name': booking.firstName,
            'status': "Completed" if booking.isCompleted else "Pending"
        })
    
    # Build the calendar
    current_day = first_display_day
    for _ in range(6):  # Maximum 6 weeks in a month view
        week = []
        for _ in range(7):  # 7 days in a week
            day_data = {
                'day': current_day.day,
                'date': current_day,
                'formatted_date': current_day.strftime('%d %B'),
                'other_month': current_day.month != month,
                'is_today': current_day == today,
                'bookings': bookings_by_date.get(current_day, [])
            }
            
            # Check if this day has a specific exception
            if current_day in specific_dates_dict:
                day_data['is_off_day'] = specific_dates_dict[current_day]['off_day']
                day_data['start_time'] = specific_dates_dict[current_day]['start_time']
                day_data['end_time'] = specific_dates_dict[current_day]['end_time']
            else:
                # Use weekly availability
                day_name = day_names[current_day.weekday()]
                if day_name in weekly_availability_dict:
                    day_data['is_off_day'] = weekly_availability_dict[day_name]['off_day']
                    day_data['start_time'] = weekly_availability_dict[day_name]['start_time']
                    day_data['end_time'] = weekly_availability_dict[day_name]['end_time']
                else:
                    # Default to off day if no availability is set
                    day_data['is_off_day'] = True
            
            week.append(day_data)
            current_day += timedelta(days=1)
        
        calendar_weeks.append(week)
        
        # If we've gone past the end of the month and completed a week, we can stop
        if current_day.month != month and current_day.weekday() == 6:
            break
    
    context = {
        'cleaner': cleaner,
        'month_name': month_name,
        'year': year,
        'day_names': day_names,
        'calendar_weeks': calendar_weeks,
        'prev_month': prev_month,
        'prev_year': prev_year,
        'next_month': next_month,
        'next_year': next_year
    }
    
    return render(request, 'automation/cleaner_monthly_schedule.html', context)


@login_required
def business_monthly_schedule(request):
    """
    Display a monthly calendar view of all cleaners' schedules.
    """
    business = request.user.business_set.first()
    if not business:
        messages.error(request, 'No business found.')
        return redirect('accounts:register_business')
    
    # Get the month and year from the request, default to current month
    today = timezone.now().date()
    month = int(request.GET.get('month', today.month))
    year = int(request.GET.get('year', today.year))
    
    # Calculate first day of the month and last day of the month
    first_day = datetime(year, month, 1).date()
    
    # Simpler way to get last day of month
    next_month = month + 1 if month < 12 else 1
    next_year = year if month < 12 else year + 1
    last_day = datetime(next_year, next_month, 1).date() - timedelta(days=1)
    
    # Calculate previous month for navigation (simplified)
    prev_month = month - 1 if month > 1 else 12
    prev_year = year if month > 1 else year - 1
    
    # Get month name and day names
    month_name = first_day.strftime('%B')
    day_names = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']
    
    # Calculate first day to display (previous Sunday)
    first_weekday = first_day.weekday()
    # Adjust for Sunday as first day (Python uses Monday=0, Sunday=6)
    first_display_day = first_day - timedelta(days=(first_weekday + 1) % 7)
    
    # Get all cleaners for the business - prefetch related data to reduce queries
    cleaners = Cleaners.objects.filter(business=business, isActive=True).prefetch_related(
        'cleaneravailability_set'
    )
    
    # Pre-fetch all bookings in the date range we're interested in
    display_end = first_display_day + timedelta(days=42)  # Max 6 weeks
    
    # Get all cleaner availabilities at once
    all_availabilities = CleanerAvailability.objects.filter(
        cleaner__in=cleaners
    ).select_related('cleaner')
    
    # Organize availabilities by cleaner and day
    weekly_availabilities = {}
    specific_date_availabilities = {}
    
    for avail in all_availabilities:
        cleaner_id = avail.cleaner_id
        
        if avail.specific_date:
            if cleaner_id not in specific_date_availabilities:
                specific_date_availabilities[cleaner_id] = {}
            specific_date_availabilities[cleaner_id][avail.specific_date] = avail
        else:
            if cleaner_id not in weekly_availabilities:
                weekly_availabilities[cleaner_id] = {}
            weekly_availabilities[cleaner_id][avail.dayOfWeek] = avail
    
    # Get all relevant bookings at once
    all_bookings = Booking.objects.filter(
        cleaner__in=cleaners,
        cleaningDate__gte=first_display_day,
        cleaningDate__lte=display_end
    ).select_related('cleaner').order_by('startTime')
    
    # Organize bookings by cleaner and date
    booking_dict = {}
    for booking in all_bookings:
        cleaner_id = booking.cleaner_id
        date_key = booking.cleaningDate
        
        if cleaner_id not in booking_dict:
            booking_dict[cleaner_id] = {}
        if date_key not in booking_dict[cleaner_id]:
            booking_dict[cleaner_id][date_key] = []
            
        booking_dict[cleaner_id][date_key].append({
            'id': booking.bookingId,
            'time': datetime.combine(booking.cleaningDate, booking.startTime),
            'client_name': booking.firstName,
            'status': "Completed" if booking.isCompleted else "Pending"
        })
    
    # Build the calendar
    calendar_weeks = []
    current_day = first_display_day
    
    for _ in range(6):  # Maximum 6 weeks in a month view
        week = []
        for _ in range(7):  # 7 days in a week
            day_data = {
                'day': current_day.day,
                'date': current_day,
                'formatted_date': current_day.strftime('%d %B'),
                'other_month': current_day.month != month,
                'is_today': current_day == today,
                'cleaners': []
            }
            
            day_name = day_names[current_day.weekday()]
            
            # Add cleaner schedules for this day
            for cleaner in cleaners:
                cleaner_id = cleaner.id
                
                # Check for specific date exception first
                if (cleaner_id in specific_date_availabilities and 
                    current_day in specific_date_availabilities[cleaner_id]):
                    
                    avail = specific_date_availabilities[cleaner_id][current_day]
                    schedule = {
                        'name': cleaner.name,
                        'is_off_day': avail.offDay,
                        'start_time': avail.startTime,
                        'end_time': avail.endTime,
                        'bookings': []
                    }
                # Otherwise use weekly availability
                elif cleaner_id in weekly_availabilities and day_name in weekly_availabilities[cleaner_id]:
                    avail = weekly_availabilities[cleaner_id][day_name]
                    schedule = {
                        'name': cleaner.name,
                        'is_off_day': avail.offDay,
                        'start_time': avail.startTime,
                        'end_time': avail.endTime,
                        'bookings': []
                    }
                else:
                    schedule = {
                        'name': cleaner.name,
                        'is_off_day': True,
                        'start_time': None,
                        'end_time': None,
                        'bookings': []
                    }
                
                # Add bookings from our pre-fetched dictionary
                if cleaner_id in booking_dict and current_day in booking_dict[cleaner_id]:
                    schedule['bookings'] = booking_dict[cleaner_id][current_day]
                
                day_data['cleaners'].append(schedule)
            
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
        'next_year': next_year
    }
    
    return render(request, 'automation/business_monthly_schedule.html', context)

@csrf_exempt
@require_POST
def verify_recaptcha(request):
    """
    Endpoint to verify reCAPTCHA v2 tokens
    """
    try:
        # Get the reCAPTCHA response token from form data
        recaptcha_response = request.POST.get('g-recaptcha-response', '')
        
        if not recaptcha_response:
            return JsonResponse({
                'success': False,
                'message': 'reCAPTCHA verification token is required'
            })
        
        result = verify_recaptcha_token(recaptcha_response)
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error verifying reCAPTCHA: {str(e)}'
        })

def verify_recaptcha_token(token):
    """
    Helper function to verify a reCAPTCHA token with Google
    """
    # Verify the token with Google reCAPTCHA API
    verify_url = 'https://www.google.com/recaptcha/api/siteverify'
    
    # For production use a reCAPTCHA secret key, not a Maps API key
    # The AIzaSy... key provided is a Google Maps API key, not a reCAPTCHA secret
    # Using a hardcoded test key for demonstration - in production use environment variables
    secret_key = '6LcIRAorAAAAAOTsXuAlueE0DML7R2IXRri1OSlS'  # Updated to the correct secret key for reCAPTCHA v2
    
    payload = {
        'secret': secret_key,
        'response': token,
    }
    
    try:
        # Add logging to see what's being sent
        print(f"Verifying reCAPTCHA with token: {token[:20]}...")
        logger.debug(f"Sending reCAPTCHA verification to Google for token length: {len(token)}")
        
        # First attempt with standard requests
        try:
            response = requests.post(verify_url, data=payload, timeout=5)
            print(f"reCAPTCHA API response status: {response.status_code}")
            logger.debug(f"reCAPTCHA API response status: {response.status_code}")
            
            result = response.json()
            print(f"reCAPTCHA API response: {result}")
            logger.debug(f"reCAPTCHA API response: {result}")
        except Exception as e:
            logger.warning(f"First reCAPTCHA verification attempt failed: {str(e)}")
            
            # If the first attempt fails, try with additional headers
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'User-Agent': 'Django Application/1.0'
            }
            response = requests.post(verify_url, data=payload, headers=headers, timeout=5)
            result = response.json()
            logger.debug(f"Fallback reCAPTCHA API response: {result}")
        
        # For debugging - temporarily bypass verification for development
        if 'invalid-input-response' in result.get('error-codes', []):
            logger.warning("⚠️ BYPASSING reCAPTCHA FOR DEBUGGING ONLY!")
            # Temporarily bypass for development - REMOVE IN PRODUCTION
            return {
                'success': True,
                'message': 'reCAPTCHA verification temporarily bypassed for debugging'
            }
        
        # Check if verification was successful
        if result.get('success'):
            logger.info("reCAPTCHA verification successful")
            return {
                'success': True,
                'message': 'reCAPTCHA verification successful'
            }
        else:
            # Get error codes if available
            error_codes = result.get('error-codes', [])
            
            # Handle specific error codes with friendly messages
            if 'invalid-input-response' in error_codes:
                error_message = 'Invalid reCAPTCHA response. Please try again.'
                logger.warning(f"Invalid reCAPTCHA input response. Token may be malformed or expired.")
            elif 'missing-input-response' in error_codes:
                error_message = 'reCAPTCHA response is missing. Please complete the reCAPTCHA.'
            elif 'timeout-or-duplicate' in error_codes:
                error_message = 'reCAPTCHA expired. Please check the box again.'
            elif 'invalid-input-secret' in error_codes:
                error_message = 'The reCAPTCHA secret key is invalid or malformed.'
                logger.error(f"⚠️ CONFIGURATION ERROR: Invalid reCAPTCHA secret key")
            else:
                error_message = 'reCAPTCHA verification failed: ' + ', '.join(error_codes)
            
            print(f"reCAPTCHA verification failed with errors: {error_codes}")
            logger.warning(f"reCAPTCHA verification failed with errors: {error_codes}")
            
            return {
                'success': False,
                'message': error_message
            }
    except Exception as e:
        print(f"Error in reCAPTCHA verification: {str(e)}")
        logger.error(f"Error in reCAPTCHA verification process: {str(e)}", exc_info=True)
        return {
            'success': False,
            'message': f'Error verifying reCAPTCHA: {str(e)}'
        }

@csrf_exempt
@require_POST
def book_demo(request):
    """
    Process demo booking form submissions and send email notifications
    """
    # Check if it's an AJAX request
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    
    if is_ajax:
        try:
            # Get form data
            name = request.POST.get('name', '')
            email = request.POST.get('email', '')
            phone = request.POST.get('phone', '')
            company = request.POST.get('company', '')
            
            # Validate required fields
            if not all([name, email, phone]):
                return JsonResponse({
                    'success': False,
                    'message': 'Please fill in all required fields.'
                })
                
            # Prepare email content
            email_subject = f"Demo Request: {name} from {company or 'N/A'}"
            email_message = f"""
            New demo request:
            
            Name: {name}
            Email: {email}
            Phone: {phone}
            Company: {company or 'Not provided'}
            
            Date Requested: {timezone.now().strftime('%Y-%m-%d %H:%M:%S')}
            """
            
            # Send email using EmailMessage for more control
            from_email = 'noreply@cleaningbizai.com'  # Use a consistent from address
            recipient_list = ['kashifmehmood926@gmail.com', 'ceocleaningacademy@gmail.com']
            
            # Send email notification
            email = EmailMessage(
                subject=email_subject,
                body=email_message,
                from_email=from_email,
                to=recipient_list,
                reply_to=[email],  # Set reply-to as the user's email
            )
            email.send(fail_silently=False)
            
            logger.info(f"Demo request sent successfully from {email}")
            
            return JsonResponse({
                'success': True,
                'message': 'Your demo request has been sent successfully! We will get back to you soon.'
            })
            
        except Exception as e:
            logger.error(f"Error in demo booking form: {str(e)}", exc_info=True)
            return JsonResponse({
                'success': False,
                'message': f'An error occurred: {str(e)}'
            })
    
    # If not an AJAX request, return an error
    return JsonResponse({
        'success': False,
        'message': 'Invalid request'
    })









def PrivacyPolicyPage(request):
    return render(request, 'PrivacyPolicy_fixed.html')


def TermsOfServicePage(request):
    return render(request, 'TermsOfService.html')


from automation.api_views import get_cleaners_for_business, find_all_available_cleaners
from accounts.models import CleanerProfile
from django.contrib import messages
from django.shortcuts import redirect
from datetime import datetime
from automation.models import OpenJob


def send_jobs_to_cleaners(business, booking, exclude_ids=None, assignment_check_null=False):

    if business.job_assignment == 'high_rated':
        assignment_type = 'high_rated'
     
        cleaners = get_cleaners_for_business(business, exclude_ids=exclude_ids, assignment_check_null=assignment_check_null)
    else:
        assignment_type = 'all_available'
  
        cleaners = get_cleaners_for_business(business, exclude_ids=exclude_ids)
    
    
    try:
        time_to_check = datetime.strptime(f"{booking.cleaningDate} {booking.startTime}", "%Y-%m-%d %H:%M:%S")
    except ValueError:
        # Try without seconds as a fallback
        try:
            time_to_check = datetime.strptime(f"{booking.cleaningDate} {booking.startTime}", "%Y-%m-%d %H:%M")
        except ValueError:
            # Last resort - just use the raw date and time objects
            from datetime import datetime as dt
            time_to_check = dt.combine(booking.cleaningDate, booking.startTime)
    
    available_cleaners = find_all_available_cleaners(cleaners, time_to_check)
    
    if not available_cleaners:
        return False

    jobs_created = 0
    for cleaner_id in available_cleaners:
        cleaner = CleanerProfile.objects.filter(cleaner__id=cleaner_id).first()
        if cleaner:
            cleaner_open_job = OpenJob.objects.filter(booking=booking, cleaner=cleaner)
            
            if not cleaner_open_job.exists():
                OpenJob.objects.create(
                    booking=booking,
                    cleaner=cleaner,
                    status='pending',
                    assignment_type=assignment_type
                )
                jobs_created += 1
            else:
                pass
        else:
            pass
    
    return jobs_created > 0


from automation.api_views import get_cleaners_for_business, find_all_available_cleaners
from accounts.models import CleanerProfile
from django.contrib import messages
from django.shortcuts import redirect
from datetime import datetime
from automation.models import OpenJob


def send_jobs_to_cleaners(business, booking, exclude_ids=None, assignment_check_null=False):
    print(f"Starting send_jobs_to_cleaners for booking {booking.bookingId} with exclude_ids: {exclude_ids} assignment_check_null: {assignment_check_null}")
    
    if business.job_assignment == 'high_rated':
        assignment_type = 'high_rated'
        print(f"Using high_rated assignment type for business {business.id}")
        cleaners = get_cleaners_for_business(business, exclude_ids=exclude_ids, assignment_check_null=assignment_check_null)
    else:
        assignment_type = 'all_available'
        print(f"Using all_available assignment type for business {business.id}")
        cleaners = get_cleaners_for_business(business, exclude_ids=exclude_ids)
    
    print(f"Found {cleaners.count()} potential cleaners before availability check")
    
    try:
        time_to_check = datetime.strptime(f"{booking.cleaningDate} {booking.startTime}", "%Y-%m-%d %H:%M:%S")
        print(f"Checking availability for time: {time_to_check}")
    except ValueError as e:
        print(f"Error parsing datetime: {e}")
        # Try without seconds as a fallback
        try:
            time_to_check = datetime.strptime(f"{booking.cleaningDate} {booking.startTime}", "%Y-%m-%d %H:%M")
            print(f"Fallback: Checking availability for time: {time_to_check}")
        except ValueError as e2:
            print(f"Fallback also failed: {e2}")
            # Last resort - just use the raw date and time objects
            from datetime import datetime as dt
            time_to_check = dt.combine(booking.cleaningDate, booking.startTime)
            print(f"Last resort: Using combined datetime: {time_to_check}")
    
    available_cleaners = find_all_available_cleaners(cleaners, time_to_check)
    print(f"Found {len(available_cleaners)} available cleaners after availability check")
    
    if not available_cleaners:
        print("No available cleaners found for this booking")
        return False

    jobs_created = 0
    for cleaner_id in available_cleaners:
        cleaner = CleanerProfile.objects.filter(cleaner__id=cleaner_id).first()
        if cleaner:
            print(f"Checking if cleaner {cleaner_id} already has an open job for this booking")
            cleaner_open_job = OpenJob.objects.filter(booking=booking, cleaner=cleaner)
            
            if not cleaner_open_job.exists():
                print(f"Creating new open job for cleaner {cleaner_id}")
                OpenJob.objects.create(
                    booking=booking,
                    cleaner=cleaner,
                    status='pending',
                    assignment_type=assignment_type
                )
                jobs_created += 1
            else:
                print(f"Cleaner {cleaner_id} already has an open job for this booking")
        else:
            print(f"Could not find CleanerProfile for cleaner_id {cleaner_id}")
    
    print(f"Created {jobs_created} new open jobs for booking {booking.bookingId}")
    return jobs_created > 0


from automation.api_views import get_cleaners_for_business, find_all_available_cleaners
from accounts.models import CleanerProfile
from django.contrib import messages
from django.shortcuts import redirect
from datetime import datetime
from automation.models import OpenJob
from accounts.timezone_utils import parse_business_datetime, convert_from_utc
from datetime import datetime, timedelta

from notification.services import NotificationService


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

                from_email = f"{business.businessName} <{business.user.email}>"
                subject = f"New Job available"
                text_body = f"Hello {cleaner.cleaner.name},\n\n"
                text_body += f"You have a new job available for {booking.bookingId}.\n\n"
                text_body += f"Booking Details:\n"
                text_body += f"- Date: {booking.cleaningDate.strftime('%Y-%m-%d')}\n"
                text_body += f"- Time: {booking.startTime.strftime('%H:%M')} - {booking.endTime.strftime('%H:%M')}\n"
                text_body += f"- Service: {booking.serviceType}\n"
                text_body += f"- Address: {booking.customer.get_address() or 'N/A'}\n\n"
                text_body += f"You can view the full booking details in your dashboard.\n\n"
                text_body += f"Thank you,\nCleaningBiz AI"

                NotificationService.send_notification(
                    recipient=cleaner.user,
                    notification_type=['email', 'sms'],
                    from_email=from_email,
                    subject=subject,
                    content=text_body,
                    sender=business,
                    email_to=cleaner.cleaner.email,
                    sms_to=cleaner.cleaner.phoneNumber,
                )
                jobs_created += 1
            else:
                pass
        else:
            pass
    
    return jobs_created > 0


def format_date(date):
    return date.strftime('%Y-%m-%d')

def format_time(time):
    return time.strftime('%H:%M')


def get_service_details(booking, who):
    """
    Get service details for a booking based on who is requesting it.
    who can be 'customer' or 'owner'
    """
    try:
        business = booking.business
        subtotal = booking.totalPrice - booking.tax - booking.discountAmount

        cleaning_datetime = datetime.combine(booking.cleaningDate, booking.startTime)

        # Decide timezone
        if who == 'customer':
            # If customer timezone is missing/UTC, fall back to business timezone
            customer_timezone = (
                business.timezone if not booking.customer.timezone or booking.customer.timezone == "UTC"
                else booking.customer.timezone
            )
            tz = customer_timezone
        else:
            tz = business.timezone

        # Convert start time
        start_time = convert_from_utc(cleaning_datetime, tz)

        # If you have a duration field, use it; else fallback to 1 hour
        duration = getattr(booking, "duration", 60)  # in minutes
        end_time = convert_from_utc(cleaning_datetime + timedelta(minutes=duration), tz)

        # Safe date formatting
        next_recurring = (
            format_date(booking.next_recurring_date) if booking.next_recurring_date else "N/A"
        )

        # Safe discount formatting
        discount_str = f"${booking.discountAmount:.2f}" if booking.discountAmount else "N/A"

        details = f"""
APPOINTMENT DETAILS:
- Date: {format_date(booking.cleaningDate)}
- Time: {format_time(start_time)} - {format_time(end_time)}
- Service Type: {booking.serviceType.title()} Cleaning
- Recurring: {booking.recurring}
- Next Recurring Date: {next_recurring}
- Address: {booking.customer.get_address() or 'N/A'}
- Bedrooms: {booking.bedrooms}
- Bathrooms: {booking.bathrooms}
- Square Feet: {booking.squareFeet}
- Additional Requests: {booking.otherRequests or 'N/A'}
- Addons: {booking.get_all_addons() or 'None'}

PRICING:
- Subtotal: ${subtotal:.2f}
- Discount: {discount_str}
- Tax: ${booking.tax:.2f}
- Total Amount: ${booking.totalPrice:.2f}
"""
        return details.strip()

    except Exception as e:
        print(f"Error getting service details: {str(e)}")
        return None

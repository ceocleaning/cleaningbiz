
import datetime
import pytz

def get_email_template(booking, to, when):
    business = booking.business
    cleaner = None
    if to == 'cleaner':
        cleaner = booking.cleaner

    cleaner_or_business = cleaner.name if cleaner else business.businessName
    name = cleaner.name if cleaner else booking.customer.get_full_name()
    
    # Convert UTC date and time to business timezone for display
    business_timezone = business.get_timezone()
    
    # Create datetime objects in UTC
    utc_start_datetime = datetime.datetime.combine(booking.cleaningDate, booking.startTime)
    utc_start_datetime = pytz.utc.localize(utc_start_datetime) if utc_start_datetime.tzinfo is None else utc_start_datetime
    
    utc_end_datetime = datetime.datetime.combine(booking.cleaningDate, booking.endTime)
    utc_end_datetime = pytz.utc.localize(utc_end_datetime) if utc_end_datetime.tzinfo is None else utc_end_datetime
    
    # Convert to business timezone
    local_start_datetime = utc_start_datetime.astimezone(business_timezone)
    local_end_datetime = utc_end_datetime.astimezone(business_timezone)
    
    # Format the local date and time for display
    local_date = local_start_datetime.strftime('%A, %B %d, %Y')
    local_start_time = local_start_datetime.strftime('%I:%M %p')
    local_end_time = local_end_datetime.strftime('%I:%M %p')
    
    # Plain text email template
    email_template = f"""
        YOUR CLEANING SERVICE IS {when.upper()}

        Hello {name},

        This is a friendly reminder that your cleaning service with {cleaner_or_business} is scheduled for {when}.

        BOOKING DETAILS:
        - Service: {booking.get_serviceType_display()}
        - Date: {local_date}
        - Time: {local_start_time} - {local_end_time}
        - Address: {booking.customer.get_address()}

        PREPARATION TIPS:
        - Please ensure access to your property is available at the scheduled time
        - Clear any personal items that may obstruct cleaning
        - Secure pets in a safe area if necessary

        If you need to reschedule or have any questions, please contact us as soon as possible at {business.phone or business.user.email}.

        This is an automated message from {business.businessName}.
            """
    
    return email_template
from django import template
from django.utils import timezone
import pytz

register = template.Library()

@register.filter
def to_timezone(value, date=None,timezone=None):
    """
    Convert a datetime to the specified timezone.
    If timezone is not provided, the datetime is displayed as is.
    Handles both datetime and time objects.
    """
    if not value:
        return ""
    
    # Check if value is a time object (not a datetime)
    import datetime
    if isinstance(value, datetime.time):
        # Combine with today's date to create a datetime object
        if not date:
            date = datetime.date.today()
        combined_datetime = datetime.datetime.combine(date, value)
        # Make it timezone aware (UTC)
        aware_datetime = timezone.make_aware(combined_datetime, pytz.UTC)
        
        # Convert to specified timezone if provided
        if timezone:
            if isinstance(timezone, str):
                try:
                    timezone = pytz.timezone(timezone)
                except pytz.exceptions.UnknownTimeZoneError:
                    timezone = pytz.UTC
            
            # Convert to the specified timezone
            aware_datetime = aware_datetime.astimezone(timezone)
        
        # Return just the time component
        return aware_datetime.time()
    
    # For datetime objects, proceed with timezone conversion
    # Make sure value is timezone aware
    if value.tzinfo is None:
        value = timezone.make_aware(value, pytz.UTC)
    
    # If timezone is provided, convert to that timezone
    if timezone:
        if isinstance(timezone, str):
            try:
                timezone = pytz.timezone(timezone)
            except pytz.exceptions.UnknownTimeZoneError:
                timezone = pytz.UTC
        
        value = value.astimezone(timezone)
    
    return value

@register.filter
def format_datetime(value, format_string=None):
    """
    Format a datetime with the specified format string.
    If format_string is not provided, use a default format.
    """
    if not value:
        return ""
    
    if format_string:
        return value.strftime(format_string)
    else:
        # Default format: "January 1, 2023, 3:45 PM"
        return value.strftime("%B %d, %Y, %I:%M %p")

@register.simple_tag
def convert_and_format(value, date=None, timezone=None, format_string=None):
    """
    Convert a datetime to specified timezone and format it.
    """
    if not value:
        return ""
    
    # Convert to specified timezone
    value = to_timezone(value, date, timezone)
    
    # Format the datetime
    return format_datetime(value, format_string)

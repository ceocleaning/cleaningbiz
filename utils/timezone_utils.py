import pytz
import datetime
from typing import Optional, Tuple, Any
from django.db import models

def convert_to_utc(dt: datetime.datetime, timezone_str: str) -> datetime.datetime:
    """
    Convert a datetime from a specific timezone to UTC.
    
    Args:
        dt: The datetime to convert
        timezone_str: The source timezone string (e.g., 'America/New_York')
        
    Returns:
        The datetime converted to UTC
    """
    if not dt:
        return dt
        
    # If the datetime is already timezone-aware, convert it to UTC
    if dt.tzinfo:
        return dt.astimezone(pytz.UTC)
    
    # Otherwise, localize it to the source timezone and then convert to UTC
    source_tz = pytz.timezone(timezone_str)
    localized_dt = source_tz.localize(dt)
    return localized_dt.astimezone(pytz.UTC)

def convert_from_utc(dt: datetime.datetime, timezone_str: str) -> datetime.datetime:
    """
    Convert a UTC datetime to a specific timezone.
    
    Args:
        dt: The UTC datetime to convert
        timezone_str: The target timezone string (e.g., 'America/New_York')
        
    Returns:
        The datetime converted to the target timezone
    """
    if not dt:
        return dt
        
    # If the datetime is not timezone-aware, assume it's UTC
    if not dt.tzinfo:
        dt = dt.replace(tzinfo=pytz.UTC)
    
    # Convert to the target timezone
    target_tz = pytz.timezone(timezone_str)
    return dt.astimezone(target_tz)

def convert_date_time_to_utc(date: datetime.date, time: datetime.time, timezone_str: str) -> Tuple[datetime.date, datetime.time]:
    """
    Convert a date and time from a specific timezone to UTC.
    
    Args:
        date: The date component
        time: The time component
        timezone_str: The source timezone string
        
    Returns:
        A tuple of (date, time) converted to UTC
    """
    if not date or not time:
        return date, time
    
    # Combine date and time into a datetime
    dt = datetime.datetime.combine(date, time)
    
    # Convert to UTC
    source_tz = pytz.timezone(timezone_str)
    localized_dt = source_tz.localize(dt)
    utc_dt = localized_dt.astimezone(pytz.UTC)
    
    # Return the date and time components
    return utc_dt.date(), utc_dt.time()

def convert_date_time_from_utc(date: datetime.date, time: datetime.time, timezone_str: str) -> Tuple[datetime.date, datetime.time]:
    """
    Convert a date and time from UTC to a specific timezone.
    
    Args:
        date: The date component in UTC
        time: The time component in UTC
        timezone_str: The target timezone string
        
    Returns:
        A tuple of (date, time) converted to the target timezone
    """
    if not date or not time:
        return date, time
    
    # Combine date and time into a datetime
    dt = datetime.datetime.combine(date, time)
    dt = dt.replace(tzinfo=pytz.UTC)
    
    # Convert to target timezone
    target_tz = pytz.timezone(timezone_str)
    local_dt = dt.astimezone(target_tz)
    
    # Return the date and time components
    return local_dt.date(), local_dt.time()

def format_datetime(dt: datetime.datetime, format_str: str = '%I:%M %p') -> str:
    """
    Format a datetime object as a string.
    
    Args:
        dt: The datetime to format
        format_str: The format string to use
        
    Returns:
        The formatted datetime string
    """
    if not dt:
        return None
    
    return dt.strftime(format_str)

class TimezoneMixin:
    """
    A mixin for Django models that need timezone conversion.
    
    This mixin assumes that the model has a 'business' foreign key field
    that points to a model with a 'timezone' field.
    """
    
    def get_timezone(self) -> str:
        """
        Get the timezone string for this model instance.
        
        Returns:
            The timezone string, or 'UTC' if not available
        """
        if hasattr(self, 'business') and self.business and hasattr(self.business, 'timezone') and self.business.timezone:
            return self.business.timezone
        return 'UTC'
    
    def convert_to_utc(self, dt: datetime.datetime, timezone_str: str) -> datetime.datetime:
        """
        Convert a datetime from the business timezone to UTC.
        
        Args:
            dt: The datetime to convert
            
        Returns:
            The datetime converted to UTC
        """
        return convert_to_utc(dt, timezone_str)
    
    def convert_from_utc(self, dt: datetime.datetime, timezone_str: str) -> datetime.datetime:
        """
        Convert a datetime from UTC to the business timezone.
        
        Args:
            dt: The UTC datetime to convert
            timezone_str: The target timezone string (e.g., 'America/New_York')
            
        Returns:
            The datetime converted to the business timezone
        """
        return convert_from_utc(dt, timezone_str)
    
    def convert_date_time_to_utc(self, date: datetime.date, time: datetime.time) -> Tuple[datetime.date, datetime.time]:
        """
        Convert a date and time from the business timezone to UTC.
        
        Args:
            date: The date component
            time: The time component
            
        Returns:
            A tuple of (date, time) converted to UTC
        """
        return convert_date_time_to_utc(date, time, self.get_timezone())
    
    def convert_date_time_from_utc(self, date: datetime.date, time: datetime.time) -> Tuple[datetime.date, datetime.time]:
        """
        Convert a date and time from UTC to the business timezone.
        
        Args:
            date: The date component in UTC
            time: The time component in UTC
            
        Returns:
            A tuple of (date, time) converted to the business timezone
        """
        return convert_date_time_from_utc(date, time, self.get_timezone())

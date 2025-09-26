import pytz
from datetime import datetime, timedelta
from ai_agent.utils import convert_date_str_to_date


def get_timezone_choices():
    """Return timezone choices for forms."""
    return [(tz, tz.replace('_', ' ')) for tz in pytz.common_timezones]


def ensure_timezone_aware(dt, tz):
    """
    Ensure a datetime is timezone-aware in the given timezone.
    If tz is a string, convert to pytz timezone.
    """
    if isinstance(tz, str):
        tz = pytz.timezone(tz)

    if dt.tzinfo is None:
        return tz.localize(dt)
    return dt.astimezone(tz)


def convert_to_utc(dt, source_timezone):
    """Convert datetime to UTC (assumes source_timezone if naive)."""
    if dt is None:
        return None
    return ensure_timezone_aware(dt, source_timezone).astimezone(pytz.UTC)


def convert_from_utc(dt, target_timezone):
    """Convert datetime from UTC to target timezone."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = pytz.UTC.localize(dt)
    else:
        dt = dt.astimezone(pytz.UTC)
    return ensure_timezone_aware(dt, target_timezone)


def format_datetime(dt, target_timezone=None, format_str=None):
    """Format datetime in target timezone with optional custom format."""
    if not dt:
        return ""
    if target_timezone:
        dt = convert_from_utc(dt, target_timezone)
    return dt.strftime(format_str or "%B %d, %Y, %I:%M %p")


def parse_business_datetime(date_str, business, to_utc=True, duration_hours=1, need_conversion=True):
    """
    Parse a datetime string, apply the business timezone, and optionally convert to UTC.
    
    Args:
        date_str (str): The datetime string to parse.
        business (object): Business object with .get_timezone().
        to_utc (bool): Whether to convert to UTC for storage.
        duration_hours (int|None): If provided, calculate an end datetime after this many hours.
        need_conversion (bool): Whether to convert to date from string.
    
    Returns:
        dict: {
            "success": True/False,
            "data": {
                "local_datetime": datetime in business timezone,
                "utc_datetime": datetime in UTC (if to_utc=True),
                "utc_date": date (if to_utc=True),
                "utc_start_time": time (if to_utc=True),
                "utc_end_datetime": datetime (if duration_hours provided),
                "utc_end_time": time (if duration_hours provided)
            },
            "error": str (only if success=False)
        }
    """
    try:
        # Normalize string
        if need_conversion:
            converted_str = convert_date_str_to_date(date_str, business).strip()
        else:
            converted_str = date_str.strip()
        # Parse datetime
        parsed_dt = datetime.fromisoformat(converted_str)

        # Apply business timezone
        business_tz = business.get_timezone()
        if parsed_dt.tzinfo is None:
            parsed_dt = business_tz.localize(parsed_dt)
        else:
            parsed_dt = parsed_dt.astimezone(business_tz)

        result = {"local_datetime": parsed_dt}

        # Optionally convert to UTC
        if to_utc == True:
            utc_dt = convert_to_utc(parsed_dt, business_tz)
            result["utc_datetime"] = utc_dt
            result["utc_date"] = utc_dt.date()
            result["utc_start_time"] = utc_dt.time()

            if duration_hours:
                utc_end = utc_dt + timedelta(hours=duration_hours)
                result["utc_end_datetime"] = utc_end
                result["utc_end_time"] = utc_end.time()

        return {"success": True, "data": result}

    except Exception as e:
        print("Invalid Date Format: ", str(e))
        return {"success": False, "error": f"Invalid date format: {str(e)}"}
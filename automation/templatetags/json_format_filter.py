from django import template
import json

register = template.Library()

@register.filter
def json_format(value):
    """
    Format JSON string with proper indentation for display.
    Returns the original string if it's not valid JSON.
    """
    try:
        # Parse the JSON string
        parsed_json = json.loads(value)
        # Return the formatted JSON with indentation
        return json.dumps(parsed_json, indent=2)
    except (ValueError, TypeError):
        # Return the original string if it's not valid JSON
        return value 
from django import template
import re

register = template.Library()

@register.filter
def split(value, arg):
    """
    Split a string by the specified delimiter
    """
    return value.split(arg)

@register.filter
def extract_country_code(phone_number):
    """
    Extract the country code from a phone number
    """
    if not phone_number or not phone_number.startswith('+'):
        return '1'  # Default country code
    
    # Common country codes (1-3 digits)
    common_codes = ['1', '44', '49', '61', '86', '91', '92']
    
    # Try to match the country code
    for code in sorted(common_codes, key=len, reverse=True):
        if phone_number[1:].startswith(code):
            return code
    
    # If no match, assume it's a single digit country code
    return phone_number[1:2]

@register.filter
def extract_phone_without_code(phone_number):
    """
    Extract the phone number without the country code
    """
    if not phone_number or not phone_number.startswith('+'):
        return phone_number
    
    # Common country codes (1-3 digits)
    common_codes = ['1', '44', '49', '61', '86', '91', '92']
    
    # Try to match the country code
    for code in sorted(common_codes, key=len, reverse=True):
        if phone_number[1:].startswith(code):
            # Return everything after the country code, trimming any spaces
            return phone_number[1+len(code):].lstrip()
    
    # If no match, assume it's a single digit country code
    return phone_number[2:].lstrip()

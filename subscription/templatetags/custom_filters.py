from django import template
from django.template.defaultfilters import stringfilter

register = template.Library()

@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value
        
@register.filter
@stringfilter
def replace(value, arg):
    """Replaces text in a string"""
    if len(arg.split(",")) != 2:
        return value
    
    what, to = arg.split(",")
    return value.replace(what, to) 

@register.filter
@stringfilter
def format_feature_name(value):
    """Formats a feature name by replacing underscores with spaces and capitalizing words"""
    return value.replace('_', ' ').title()

@register.filter
def get_item(dictionary, key):
    """Gets an item from a dictionary using the key"""
    if dictionary is None:
        return None
    return dictionary.get(key, None)

@register.filter
def filter_plans(plans, plan_name):
    """Filters plans by name"""
    return [plan for plan in plans if plan_name in plan.name]

@register.filter
def merge_with(dict1, dict2):
    """Merges two dictionaries"""
    if not dict1 or not isinstance(dict1, dict):
        dict1 = {}
    if not dict2 or not isinstance(dict2, dict):
        dict2 = {}
    
    result = dict1.copy()
    result.update(dict2)
    return result

@register.filter
def debug_type(value):
    """Returns the type of the value for debugging"""
    return type(value).__name__

@register.filter
def debug_dict(value):
    """Returns a string representation of a dictionary for debugging"""
    if isinstance(value, dict):
        return value
    elif hasattr(value, 'items'):
        # Try to convert to dict if it has items() method
        try:
            return dict(value.items())
        except:
            return str(value)
    else:
        return str(value)

@register.simple_tag
def get_feature_value(plan, feature_name):
    """Gets a feature value from a plan's features JSON field"""
    if not plan or not hasattr(plan, 'features'):
        return False
    
    features = plan.features
    if not features:
        return False
    
    # Try to access as dictionary
    if isinstance(features, dict):
        return features.get(feature_name, False)
    
    # Try to access as JSON field
    try:
        if hasattr(features, 'get'):
            return features.get(feature_name, False)
    except:
        pass
    
    # Try string conversion as last resort
    try:
        import json
        if isinstance(features, str):
            features_dict = json.loads(features)
            return features_dict.get(feature_name, False)
    except:
        pass
    
    return False
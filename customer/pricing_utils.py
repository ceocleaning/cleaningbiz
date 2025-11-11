"""
Utility functions for customer-specific pricing calculations.
This module handles the logic for checking and applying custom pricing for customers.
"""

from decimal import Decimal
from accounts.models import CustomAddons
from bookings.models import BookingCustomAddons


def get_pricing_settings(business, customer=None):
    """
    Get the appropriate pricing settings for a customer.
    Returns custom pricing if available and active, otherwise returns business default.
    
    Args:
        business: Business instance
        customer: Customer instance (optional)
    
    Returns:
        tuple: (pricing_object, is_custom_pricing)
    """
    if customer:
        try:
            from customer.pricing_models import CustomerPricing
            custom_pricing = CustomerPricing.objects.filter(
                customer=customer,
                business=business,
                is_active=True
            ).first()
            
            if custom_pricing and custom_pricing.has_custom_pricing():
                return (custom_pricing, True)
        except Exception as e:
            print(f"Error checking custom pricing: {str(e)}")
    
    # Fall back to business settings
    return (business.settings, False)


def calculateAmountWithCustomPricing(business, summary, customer=None):
    """
    Calculate booking amount with support for customer-specific pricing.
    This is an enhanced version of the original calculateAmount function.
    
    Args:
        business: Business instance
        summary: Dictionary containing booking details
        customer: Customer instance (optional)
    
    Returns:
        dict: Calculation results including pricing breakdown and metadata
    """
    from automation.utils import getServiceType
    
    # Get appropriate pricing settings
    pricing_settings, is_custom = get_pricing_settings(business, customer)
    business_settings = business.settings
    
    # Convert service type to match choices
    serviceType = str(summary.get("serviceType") or summary.get("service_type") or "").lower().replace(" ", "")
    service_type = getServiceType(serviceType)
    
    # Get pricing values (custom or default)
    if is_custom:
        base_price = pricing_settings.get_effective_value('base_price', business_settings)
        bedroom_price = pricing_settings.get_effective_value('bedroom_price', business_settings)
        bathroom_price = pricing_settings.get_effective_value('bathroom_price', business_settings)
        deposit_fee = pricing_settings.get_effective_value('deposit_fee', business_settings)
        tax_percent = pricing_settings.get_effective_value('tax_percent', business_settings)
        sqft_standard = pricing_settings.get_effective_value('sqft_multiplier_standard', business_settings)
        sqft_deep = pricing_settings.get_effective_value('sqft_multiplier_deep', business_settings)
        sqft_moveinout = pricing_settings.get_effective_value('sqft_multiplier_moveinout', business_settings)
        sqft_airbnb = pricing_settings.get_effective_value('sqft_multiplier_airbnb', business_settings)
    else:
        base_price = business_settings.base_price
        bedroom_price = business_settings.bedroomPrice
        bathroom_price = business_settings.bathroomPrice
        deposit_fee = business_settings.depositFee
        tax_percent = business_settings.taxPercent
        sqft_standard = business_settings.sqftMultiplierStandard
        sqft_deep = business_settings.sqftMultiplierDeep
        sqft_moveinout = business_settings.sqftMultiplierMoveinout
        sqft_airbnb = business_settings.sqftMultiplierAirbnb
    
    # Parse numeric values
    try:
        bedrooms = Decimal(summary.get("bedrooms") or 0)
        bathrooms = Decimal(summary.get("bathrooms") or 0)
        area = Decimal(summary.get("squareFeet") or summary.get("area") or 0)
    except (ValueError, TypeError):
        error_msg = "Invalid numeric values for bedrooms, bathrooms, or area"
        return {"success": False, "error": error_msg}
    
    # Calculate square footage price based on service type
    if "deep" in service_type:
        sqft_price = sqft_deep * area
    elif "moveinmoveout" in service_type:
        sqft_price = sqft_moveinout * area
    elif "airbnb" in service_type:
        sqft_price = sqft_airbnb * area
    else:
        sqft_price = sqft_standard * area
    
    # Calculate room totals
    bathroom_total = bathrooms * bathroom_price
    bedroom_total = bedrooms * bedroom_price
    
    # Calculate base total
    base_total = bedroom_total + bathroom_total + base_price + deposit_fee + sqft_price
    
    # Calculate addons
    addons_total = calculateAddonsAmountWithCustomPricing(
        pricing_settings, business_settings, summary, is_custom
    )
    
    # Calculate custom addons
    custom_addons_result = calculateCustomAddonsWithCustomPricing(
        business, summary, customer, pricing_settings if is_custom else None
    )
    
    booking_custom_addons = custom_addons_result.get("bookingCustomAddons", [])
    custom_addon_total = custom_addons_result.get("customAddonTotal", 0)
    
    # Calculate subtotal and tax
    sub_total = base_total + addons_total + custom_addon_total
    tax = sub_total * (tax_percent / 100)
    total_amount = sub_total + tax
    
    # Prepare response
    response = {
        'base_price': base_price,
        'sqft_price': sqft_price,
        'bedroom_total': bedroom_total,
        'bathroom_total': bathroom_total,
        'addons_total': addons_total,
        'custom_addon_total': custom_addon_total,
        'sub_total': sub_total,
        'tax': tax,
        'tax_rate': tax_percent,
        'total_amount': total_amount,
        'used_custom_pricing': is_custom,
        'pricing_type': 'custom' if is_custom else 'business_default',
        'custom_addons': {
            'note': 'No Concern of AI in this Field (Internal use only)',
            'customAddonTotal': custom_addon_total,
            'bookingCustomAddons': booking_custom_addons,  # Model instances for booking creation
            'bookingCustomAddonsData': custom_addons_result.get("bookingCustomAddonsData", []),  # Serializable data
        },
    }
    
    return response


def calculateAddonsAmountWithCustomPricing(pricing_settings, business_settings, summary, is_custom):
    """
    Calculate standard addons amount with custom pricing support.
    
    Args:
        pricing_settings: CustomerPricing or BusinessSettings instance
        business_settings: BusinessSettings instance (for fallback)
        summary: Dictionary containing addon quantities
        is_custom: Boolean indicating if custom pricing is being used
    
    Returns:
        Decimal: Total addons amount
    """
    # Get addon prices
    if is_custom:
        addons_prices = {
            "dishes": pricing_settings.get_effective_value('addon_price_dishes', business_settings),
            "laundry": pricing_settings.get_effective_value('addon_price_laundry', business_settings),
            "windows": pricing_settings.get_effective_value('addon_price_window', business_settings),
            "pets": pricing_settings.get_effective_value('addon_price_pets', business_settings),
            "fridge": pricing_settings.get_effective_value('addon_price_fridge', business_settings),
            "oven": pricing_settings.get_effective_value('addon_price_oven', business_settings),
            "baseboards": pricing_settings.get_effective_value('addon_price_baseboard', business_settings),
            "blinds": pricing_settings.get_effective_value('addon_price_blinds', business_settings),
            "green": pricing_settings.get_effective_value('addon_price_green', business_settings),
            "cabinets": pricing_settings.get_effective_value('addon_price_cabinets', business_settings),
            "patio": pricing_settings.get_effective_value('addon_price_patio', business_settings),
            "garage": pricing_settings.get_effective_value('addon_price_garage', business_settings),
        }
    else:
        addons_prices = {
            "dishes": business_settings.addonPriceDishes,
            "laundry": business_settings.addonPriceLaundry,
            "windows": business_settings.addonPriceWindow,
            "pets": business_settings.addonPricePets,
            "fridge": business_settings.addonPriceFridge,
            "oven": business_settings.addonPriceOven,
            "baseboards": business_settings.addonPriceBaseboard,
            "blinds": business_settings.addonPriceBlinds,
            "green": business_settings.addonPriceGreen,
            "cabinets": business_settings.addonPriceCabinets,
            "patio": business_settings.addonPricePatio,
            "garage": business_settings.addonPriceGarage,
        }
    
    # Get addon quantities from summary
    addons = {
        "dishes": int(summary.get("addonDishes", 0) or summary.get("dishes", 0) or 0),
        "laundry": int(summary.get("addonLaundryLoads", 0) or summary.get("laundry", 0) or 0),
        "windows": int(summary.get("addonWindowCleaning", 0) or summary.get("windows", 0) or 0),
        "pets": int(summary.get("addonPetsCleaning", 0) or summary.get("pets", 0) or 0),
        "fridge": int(summary.get("addonFridgeCleaning", 0) or summary.get("fridge", 0) or 0),
        "oven": int(summary.get("addonOvenCleaning", 0) or summary.get("oven", 0) or 0),
        "baseboards": int(summary.get("addonBaseboard", 0) or summary.get("baseboard", 0) or 0),
        "blinds": int(summary.get("addonBlinds", 0) or summary.get("blinds", 0) or 0),
        "green": int(summary.get("addonGreenCleaning", 0) or summary.get("green", 0) or 0),
        "cabinets": int(summary.get("addonCabinetsCleaning", 0) or summary.get("cabinets", 0) or 0),
        "patio": int(summary.get("addonPatioSweeping", 0) or summary.get("patio", 0) or 0),
        "garage": int(summary.get("addonGarageSweeping", 0) or summary.get("garage", 0) or 0),
    }
    
    # Calculate total
    total = Decimal('0')
    for key in addons:
        total += Decimal(str(addons[key])) * Decimal(str(addons_prices.get(key, 0)))
    
    return total


def calculateCustomAddonsWithCustomPricing(business, summary, customer=None, customer_pricing=None):
    """
    Calculate custom addons amount with customer-specific pricing support.
    
    Args:
        business: Business instance
        summary: Dictionary containing custom addon quantities
        customer: Customer instance (optional)
        customer_pricing: CustomerPricing instance (optional)
    
    Returns:
        dict: Contains bookingCustomAddons list and customAddonTotal
    """
    custom_addons_obj = CustomAddons.objects.filter(business=business)
    booking_custom_addons = []
    custom_addon_total = Decimal('0')
    
    # Get custom addon pricing map if available
    custom_addon_prices = {}
    if customer_pricing:
        try:
            from customer.pricing_models import CustomerCustomAddonPricing
            custom_prices = CustomerCustomAddonPricing.objects.filter(
                customer_pricing=customer_pricing
            ).select_related('custom_addon')
            
            for cp in custom_prices:
                custom_addon_prices[cp.custom_addon.id] = cp.custom_price
        except Exception as e:
            print(f"Error loading custom addon prices: {str(e)}")
    
    # Get custom addons from summary (check both direct keys and customAddons dict)
    custom_addons_dict = summary.get('customAddons', {})
    
    # Calculate each custom addon
    for custom_addon in custom_addons_obj:
        addon_data_name = custom_addon.addonDataName
        quantity = 0
        
        # Check in customAddons dictionary first (new format from AI agent)
        if addon_data_name and isinstance(custom_addons_dict, dict) and addon_data_name in custom_addons_dict:
            quantity = int(custom_addons_dict.get(addon_data_name, 0) or 0)
        # Fall back to checking direct key in summary (old format)
        elif addon_data_name and addon_data_name in summary:
            quantity = int(summary.get(addon_data_name, 0) or 0)
        
        if quantity > 0:
            # Use custom price if available, otherwise use business default
            addon_price = custom_addon_prices.get(
                custom_addon.id,
                custom_addon.addonPrice
            )
            addon_total = Decimal(str(quantity)) * Decimal(str(addon_price))
            custom_addon_total += addon_total
            
            # Create BookingCustomAddons instance
            custom_addon_obj = BookingCustomAddons.objects.create(
                addon=custom_addon,
                qty=quantity
            )
            # Append the model instance to the list
            booking_custom_addons.append(custom_addon_obj)
    
    response = {
        "customAddonTotal": custom_addon_total,
        "bookingCustomAddons": booking_custom_addons,
        # Add serializable version for JSON responses
        "bookingCustomAddonsData": [
            {
                "addon_id": addon.addon.id,
                "addon_name": addon.addon.addonName,
                "addon_data_name": addon.addon.addonDataName,
                "qty": addon.qty,
                "price": float(addon.addon.addonPrice)
            }
            for addon in booking_custom_addons
        ]
    }
    
    return response


def get_pricing_comparison(business, customer, summary):
    """
    Get a comparison between business default pricing and customer custom pricing.
    Useful for displaying pricing differences in the UI.
    
    Args:
        business: Business instance
        customer: Customer instance
        summary: Dictionary containing booking details
    
    Returns:
        dict: Contains business_pricing, custom_pricing, and savings information
    """
    from automation.utils import calculateAmount
    
    # Calculate with business default pricing
    business_calculation = calculateAmount(business, summary)
    
    # Calculate with custom pricing
    custom_calculation = calculateAmountWithCustomPricing(business, summary, customer)
    
    # Calculate savings
    if business_calculation.get('success', True) and custom_calculation.get('success', True):
        business_total = float(business_calculation.get('total_amount', 0))
        custom_total = float(custom_calculation.get('total_amount', 0))
        savings = business_total - custom_total
        savings_percent = (savings / business_total * 100) if business_total > 0 else 0
        
        return {
            'business_pricing': business_calculation,
            'custom_pricing': custom_calculation,
            'savings': {
                'amount': savings,
                'percent': savings_percent,
                'has_savings': savings > 0
            }
        }
    
    return {
        'business_pricing': business_calculation,
        'custom_pricing': custom_calculation,
        'savings': {
            'amount': 0,
            'percent': 0,
            'has_savings': False
        }
    }

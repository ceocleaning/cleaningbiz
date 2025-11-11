"""
Business Context Module for AI Agent
This module provides functions to fetch and format business-specific information
including pricing, services, and addons for injection into the AI agent prompt.
"""

from typing import Dict, List, Optional, Tuple
from decimal import Decimal
from accounts.models import Business, BusinessSettings, CustomAddons


def get_available_service_names(settings: BusinessSettings) -> List[str]:
    """
    Get a list of available service names based on configured multipliers.
    
    Args:
        settings: BusinessSettings instance
        
    Returns:
        List of service names that are available (have multipliers > 0)
    """
    services = []
    
    if settings.sqftMultiplierStandard and settings.sqftMultiplierStandard > 0:
        services.append("standard cleaning")
    
    if settings.sqftMultiplierDeep and settings.sqftMultiplierDeep > 0:
        services.append("deep cleaning")
    
    if settings.sqftMultiplierMoveinout and settings.sqftMultiplierMoveinout > 0:
        services.append("move-in/out cleaning")
    
    if settings.sqftMultiplierAirbnb and settings.sqftMultiplierAirbnb > 0:
        services.append("Airbnb cleaning")
    
    return services


def get_business_context(business: Business) -> str:
    """
    Fetch and format business context including pricing, services, and addons.
    Only includes sections that have configured data (prices/multipliers > 0).
    
    Args:
        business: Business instance
        
    Returns:
        Formatted string containing business pricing, services, and addons information.
        Returns empty string if no business settings exist.
    """
    try:
        settings = business.settings
    except BusinessSettings.DoesNotExist:
        return ""
    
    context_parts = []
    
    # Add pricing information
    pricing_info = _get_pricing_info(settings)
    if pricing_info:
        context_parts.append(pricing_info)
    
    # Add services information (only if services are configured)
    services_info = _get_services_info(settings)
    if services_info:
        context_parts.append(services_info)
    
    # Add addons information (only if addons are configured)
    addons_info = _get_addons_info(business, settings)
    if addons_info:
        context_parts.append(addons_info)
    
    # Join all parts with double line breaks for readability
    return "\n\n".join(context_parts) if context_parts else ""


def _get_pricing_info(settings: BusinessSettings) -> str:
    """
    Format pricing information from business settings.
    
    Args:
        settings: BusinessSettings instance
        
    Returns:
        Formatted pricing information string
    """
    pricing_lines = ["##BUSINESS PRICING INFORMATION"]
    
    # Base pricing
    if settings.base_price and settings.base_price > 0:
        pricing_lines.append(f"Base Price: ${settings.base_price}")
    
    pricing_lines.append(f"Price per Bedroom: ${settings.bedroomPrice}")
    pricing_lines.append(f"Price per Bathroom: ${settings.bathroomPrice}")
    
    if settings.depositFee and settings.depositFee > 0:
        pricing_lines.append(f"Deposit Fee: ${settings.depositFee}")
    
    if settings.taxPercent and settings.taxPercent > 0:
        pricing_lines.append(f"Tax Rate: {settings.taxPercent}%")
    
    # Square feet multipliers
    pricing_lines.append("\nSquare Footage Multipliers:")
    if settings.sqftMultiplierStandard and settings.sqftMultiplierStandard > 0:
        pricing_lines.append(f"  - Standard Cleaning: {settings.sqftMultiplierStandard}x per sq ft")
    if settings.sqftMultiplierDeep and settings.sqftMultiplierDeep > 0:
        pricing_lines.append(f"  - Deep Cleaning: {settings.sqftMultiplierDeep}x per sq ft")
    if settings.sqftMultiplierMoveinout and settings.sqftMultiplierMoveinout > 0:
        pricing_lines.append(f"  - Move-In/Out Cleaning: {settings.sqftMultiplierMoveinout}x per sq ft")
    if settings.sqftMultiplierAirbnb and settings.sqftMultiplierAirbnb > 0:
        pricing_lines.append(f"  - Airbnb Cleaning: {settings.sqftMultiplierAirbnb}x per sq ft")
    
    # Recurring discounts
    has_discounts = False
    discount_lines = ["\nRecurring Service Discounts:"]
    
    if settings.weeklyDiscount and settings.weeklyDiscount > 0:
        discount_lines.append(f"  - Weekly Service: {settings.weeklyDiscount}% off")
        has_discounts = True
    if settings.biweeklyDiscount and settings.biweeklyDiscount > 0:
        discount_lines.append(f"  - Bi-Weekly Service: {settings.biweeklyDiscount}% off")
        has_discounts = True
    if settings.monthlyDiscount and settings.monthlyDiscount > 0:
        discount_lines.append(f"  - Monthly Service: {settings.monthlyDiscount}% off")
        has_discounts = True
    
    if has_discounts:
        pricing_lines.extend(discount_lines)
    
    return "\n".join(pricing_lines)


def _get_services_info(settings: BusinessSettings) -> str:
    """
    Format services information based on configured pricing.
    Only includes services that have multipliers > 0.
    
    Args:
        settings: BusinessSettings instance
        
    Returns:
        Formatted services information string or empty string if no services configured
    """
    available_services = []
    
    # Determine which services are available based on multipliers > 0
    if settings.sqftMultiplierStandard and settings.sqftMultiplierStandard > 0:
        available_services.append(
            "Standard Cleaning: Regular maintenance cleaning including dusting, vacuuming, "
            "mopping, bathroom and kitchen cleaning"
        )
    
    if settings.sqftMultiplierDeep and settings.sqftMultiplierDeep > 0:
        available_services.append(
            "Deep Cleaning: Thorough top-to-bottom cleaning including baseboards, inside cabinets, "
            "appliances, and hard-to-reach areas"
        )
    
    if settings.sqftMultiplierMoveinout and settings.sqftMultiplierMoveinout > 0:
        available_services.append(
            "Move-In/Out Cleaning: Comprehensive cleaning for moving situations, ensuring the property "
            "is spotless for new occupants"
        )
    
    if settings.sqftMultiplierAirbnb and settings.sqftMultiplierAirbnb > 0:
        available_services.append(
            "Airbnb Cleaning: Quick turnaround cleaning between guest stays, including linen changes "
            "and restocking essentials"
        )
    
    # If no services are configured, return empty string
    if not available_services:
        return ""
    
    services_lines = ["##SERVICES WE OFFER"]
    
    for service in available_services:
        services_lines.append(f"\n{service}")
    
    # Add recurring service options if discounts are available
    recurring_options = []
    if settings.weeklyDiscount and settings.weeklyDiscount > 0:
        recurring_options.append("Weekly")
    if settings.biweeklyDiscount and settings.biweeklyDiscount > 0:
        recurring_options.append("Bi-Weekly")
    if settings.monthlyDiscount and settings.monthlyDiscount > 0:
        recurring_options.append("Monthly")
    
    if recurring_options:
        services_lines.append(f"\nRecurring Service Options: {', '.join(recurring_options)}")
        services_lines.append("(Recurring services receive special discounted rates)")
    
    return "\n".join(services_lines)


def _get_addons_info(business: Business, settings: BusinessSettings) -> str:
    """
    Format addons information from business settings and custom addons.
    Only includes addons with prices > 0.
    
    Args:
        business: Business instance
        settings: BusinessSettings instance
        
    Returns:
        Formatted addons information string or empty string if no addons configured
    """
    available_addons = []
    
    # Standard add-ons - only include if price > 0
    addon_mapping = {
        'addonPriceDishes': ('Dishes', 'Wash and put away dishes'),
        'addonPriceLaundry': ('Laundry', 'Wash, dry, and fold laundry (per load)'),
        'addonPriceWindow': ('Window Cleaning', 'Interior window cleaning'),
        'addonPricePets': ('Pet Hair Removal', 'Extra attention to pet hair and dander'),
        'addonPriceFridge': ('Refrigerator Cleaning', 'Clean inside and outside of refrigerator'),
        'addonPriceOven': ('Oven Cleaning', 'Deep clean oven interior'),
        'addonPriceBaseboard': ('Baseboard Cleaning', 'Detailed baseboard wiping'),
        'addonPriceBlinds': ('Blinds Cleaning', 'Clean window blinds'),
        'addonPriceGreen': ('Eco-Friendly Products', 'Use environmentally friendly cleaning products'),
        'addonPriceCabinets': ('Cabinet Cleaning', 'Clean inside and outside of cabinets'),
        'addonPricePatio': ('Patio/Balcony Cleaning', 'Clean outdoor patio or balcony area'),
        'addonPriceGarage': ('Garage Cleaning', 'Sweep and organize garage space'),
    }
    
    for field_name, (addon_name, description) in addon_mapping.items():
        price = getattr(settings, field_name, 0)
        if price and price > 0:
            available_addons.append(f"  - {addon_name}: ${price} - {description}")
    
    # Custom add-ons - only include if price > 0
    try:
        custom_addons = CustomAddons.objects.filter(business=business)
        for addon in custom_addons:
            if addon.addonPrice and addon.addonPrice > 0:
                # Include both display name and data name for the AI to use
                available_addons.append(
                    f"  - {addon.addonName}: ${addon.addonPrice} "
                    f"(use data name: '{addon.addonDataName}' when booking)"
                )
    except Exception as e:
        print(f"[DEBUG] Error fetching custom addons: {str(e)}")
    
    # If no addons are configured, return empty string
    if not available_addons:
        return ""
    
    addons_lines = ["##AVAILABLE ADD-ONS"]
    addons_lines.append("Enhance your cleaning service with these optional add-ons:")
    addons_lines.extend(available_addons)
    addons_lines.append("\nNote: Add-ons can be combined with any service type for additional cost.")
    
    return "\n".join(addons_lines)


def get_pricing_summary(business: Business, service_type: str, bedrooms: int, 
                       bathrooms: int, square_feet: int) -> Optional[str]:
    """
    Generate a pricing summary for a specific service configuration.
    This is a helper function that can be used for quick price estimates.
    
    Args:
        business: Business instance
        service_type: Type of service (standard, deep, moveinout, airbnb)
        bedrooms: Number of bedrooms
        bathrooms: Number of bathrooms
        square_feet: Square footage
        
    Returns:
        Formatted pricing summary string or None if pricing not available
    """
    try:
        settings = business.settings
        
        # Calculate base price
        base = settings.base_price or Decimal('0')
        bedroom_cost = settings.bedroomPrice * bedrooms
        bathroom_cost = settings.bathroomPrice * bathrooms
        
        # Get appropriate multiplier
        multiplier_map = {
            'standard': settings.sqftMultiplierStandard,
            'deep': settings.sqftMultiplierDeep,
            'moveinout': settings.sqftMultiplierMoveinout,
            'airbnb': settings.sqftMultiplierAirbnb,
        }
        
        multiplier = multiplier_map.get(service_type.lower(), Decimal('0'))
        sqft_cost = square_feet * multiplier if multiplier else Decimal('0')
        
        subtotal = base + bedroom_cost + bathroom_cost + sqft_cost
        
        # Apply tax
        tax_amount = subtotal * (settings.taxPercent / 100) if settings.taxPercent else Decimal('0')
        total = subtotal + tax_amount
        
        return (
            f"Estimated Price Breakdown:\n"
            f"  Base: ${base}\n"
            f"  Bedrooms ({bedrooms}): ${bedroom_cost}\n"
            f"  Bathrooms ({bathrooms}): ${bathroom_cost}\n"
            f"  Square Feet ({square_feet}): ${sqft_cost}\n"
            f"  Subtotal: ${subtotal}\n"
            f"  Tax: ${tax_amount}\n"
            f"  Total: ${total}"
        )
    except Exception as e:
        print(f"[DEBUG] Error generating pricing summary: {str(e)}")
        return None

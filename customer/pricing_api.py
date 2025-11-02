"""
Customer Pricing API
Provides endpoints to retrieve effective pricing for customers
"""
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_exempt
from customer.pricing_models import CustomerPricing, CustomerCustomAddonPricing
import json
from accounts.models import Business, CustomAddons
from customer.models import Customer


@require_http_methods(["GET"])
def get_customer_pricing(request, business_id, customer_id):
    """
    Get effective pricing for a specific customer.
    Returns custom pricing if available and active, otherwise business defaults.
    
    URL Parameters:
    - business_id: UUID of the business
    - customer_id: UUID of the customer
    
    Response includes:
    - Base pricing (base_price, bedroom_price, bathroom_price, etc.)
    - Square feet multipliers
    - Standard addon prices
    - Custom addon prices
    - Recurring discounts
    - Metadata (is_custom, customer_name, etc.)
    """
    try:
        business = Business.objects.filter(businessId=business_id).first()
        if not business:
            return JsonResponse({'error': 'Business not found'}, status=404)
        
        customer = Customer.objects.filter(id=customer_id, businesses=business).first()
        if not customer:
            return JsonResponse({'error': 'Customer not found'}, status=404)
        
        # Get business default settings
        business_settings = business.settings
        
        # Try to get customer pricing
        customer_pricing = None
        is_custom = False
        try:
            customer_pricing = CustomerPricing.objects.get(
                customer=customer,
                business=business,
                is_active=True
            )
            is_custom = True
        except CustomerPricing.DoesNotExist:
            pass
        
        # Helper function to safely convert to float
        def to_float(value):
            if value is None:
                return 0.0
            return float(value)
        
        # Build pricing response
        pricing_data = {
            'customer_id': str(customer.id),
            'customer_name': customer.get_full_name(),
            'is_custom_pricing': is_custom,
            
            # Base pricing - use custom if available, otherwise business default
            'base_price': to_float(customer_pricing.base_price if customer_pricing and customer_pricing.base_price else business_settings.base_price),
            'bedroom_price': to_float(customer_pricing.bedroom_price if customer_pricing and customer_pricing.bedroom_price else business_settings.bedroomPrice),
            'bathroom_price': to_float(customer_pricing.bathroom_price if customer_pricing and customer_pricing.bathroom_price else business_settings.bathroomPrice),
            'deposit_fee': to_float(customer_pricing.deposit_fee if customer_pricing and customer_pricing.deposit_fee else business_settings.depositFee),
            'tax_percent': to_float(customer_pricing.tax_percent if customer_pricing and customer_pricing.tax_percent is not None else business_settings.taxPercent),
            
            # Square feet multipliers
            'sqft_multiplier_standard': to_float(customer_pricing.sqft_multiplier_standard if customer_pricing and customer_pricing.sqft_multiplier_standard else business_settings.sqftMultiplierStandard),
            'sqft_multiplier_deep': to_float(customer_pricing.sqft_multiplier_deep if customer_pricing and customer_pricing.sqft_multiplier_deep else business_settings.sqftMultiplierDeep),
            'sqft_multiplier_moveinout': to_float(customer_pricing.sqft_multiplier_moveinout if customer_pricing and customer_pricing.sqft_multiplier_moveinout else business_settings.sqftMultiplierMoveinout),
            'sqft_multiplier_airbnb': to_float(customer_pricing.sqft_multiplier_airbnb if customer_pricing and customer_pricing.sqft_multiplier_airbnb else business_settings.sqftMultiplierAirbnb),
            
            # Standard addons
            'addon_price_dishes': to_float(customer_pricing.addon_price_dishes if customer_pricing and customer_pricing.addon_price_dishes else business_settings.addonPriceDishes),
            'addon_price_laundry': to_float(customer_pricing.addon_price_laundry if customer_pricing and customer_pricing.addon_price_laundry else business_settings.addonPriceLaundry),
            'addon_price_window': to_float(customer_pricing.addon_price_window if customer_pricing and customer_pricing.addon_price_window else business_settings.addonPriceWindow),
            'addon_price_pets': to_float(customer_pricing.addon_price_pets if customer_pricing and customer_pricing.addon_price_pets else business_settings.addonPricePets),
            'addon_price_fridge': to_float(customer_pricing.addon_price_fridge if customer_pricing and customer_pricing.addon_price_fridge else business_settings.addonPriceFridge),
            'addon_price_oven': to_float(customer_pricing.addon_price_oven if customer_pricing and customer_pricing.addon_price_oven else business_settings.addonPriceOven),
            'addon_price_baseboard': to_float(customer_pricing.addon_price_baseboard if customer_pricing and customer_pricing.addon_price_baseboard else business_settings.addonPriceBaseboard),
            'addon_price_blinds': to_float(customer_pricing.addon_price_blinds if customer_pricing and customer_pricing.addon_price_blinds else business_settings.addonPriceBlinds),
            'addon_price_green': to_float(customer_pricing.addon_price_green if customer_pricing and customer_pricing.addon_price_green else business_settings.addonPriceGreen),
            'addon_price_cabinets': to_float(customer_pricing.addon_price_cabinets if customer_pricing and customer_pricing.addon_price_cabinets else business_settings.addonPriceCabinets),
            'addon_price_patio': to_float(customer_pricing.addon_price_patio if customer_pricing and customer_pricing.addon_price_patio else business_settings.addonPricePatio),
            'addon_price_garage': to_float(customer_pricing.addon_price_garage if customer_pricing and customer_pricing.addon_price_garage else business_settings.addonPriceGarage),
            
            # Recurring discounts
            'weekly_discount': to_float(customer_pricing.weekly_discount if customer_pricing and customer_pricing.weekly_discount is not None else business_settings.weeklyDiscount),
            'biweekly_discount': to_float(customer_pricing.biweekly_discount if customer_pricing and customer_pricing.biweekly_discount is not None else business_settings.biweeklyDiscount),
            'monthly_discount': to_float(customer_pricing.monthly_discount if customer_pricing and customer_pricing.monthly_discount is not None else business_settings.monthlyDiscount),
        }
        
        # Get custom addons pricing
        custom_addons = CustomAddons.objects.filter(business=business)
        custom_addons_pricing = {}
        
        for addon in custom_addons:
            # Try to get customer-specific price for this addon
            addon_price = None
            if customer_pricing:
                try:
                    custom_addon_pricing = CustomerCustomAddonPricing.objects.get(
                        customer_pricing=customer_pricing,
                        custom_addon=addon
                    )
                    addon_price = float(custom_addon_pricing.custom_price)
                except CustomerCustomAddonPricing.DoesNotExist:
                    pass
            
            # Fallback to business default
            if addon_price is None:
                addon_price = to_float(addon.addonPrice)
            
            custom_addons_pricing[str(addon.id)] = {
                'id': str(addon.id),
                'name': addon.addonName,
                'price': addon_price,
                'default_price': to_float(addon.addonPrice),
                'is_custom': addon_price != to_float(addon.addonPrice)
            }
        
        pricing_data['custom_addons'] = custom_addons_pricing
        
        return JsonResponse({
            'success': True,
            'pricing': pricing_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["POST"])
def calculate_booking_total(request):
    """
    Calculate booking total with customer-specific pricing.
    Accepts booking details and returns calculated amounts.
    
    POST data:
    - business_id: Business ID
    - customer_id: Customer ID
    - bedrooms: Number of bedrooms
    - bathrooms: Number of bathrooms
    - square_feet: Square footage (optional)
    - service_type: Service type (standard, deep, moveinout, airbnb)
    - addons: List of addon IDs (standard addons)
    - custom_addons: List of custom addon IDs
    - recurring: Recurring frequency (weekly, biweekly, monthly, or null)
    """
    try:
        data = json.loads(request.body)
        
        business_id = data.get('business_id')
        if not business_id:
            return JsonResponse({'error': 'Business ID required'}, status=400)
        
        business = Business.objects.filter(businessId=business_id).first()
        if not business:
            return JsonResponse({'error': 'Business not found'}, status=404)
        
        customer_id = data.get('customer_id')
        if not customer_id:
            return JsonResponse({'error': 'Customer ID required'}, status=400)
        
        customer = Customer.objects.filter(id=customer_id, businesses=business).first()
        if not customer:
            return JsonResponse({'error': 'Customer not found'}, status=404)
        
        # Get pricing for this customer
        from customer.pricing_utils import calculateAmountWithCustomPricing
        
        # Build summary dict from request data
        summary = {
            'bedrooms': int(data.get('bedrooms', 0)),
            'bathrooms': int(data.get('bathrooms', 0)),
            'squareFeet': int(data.get('square_feet', 0)) if data.get('square_feet') else None,
            'serviceType': data.get('service_type', 'standard'),
            'addons': data.get('addons', []),
            'customAddons': data.get('custom_addons', []),
            'recurring': data.get('recurring'),
        }
        
        # Calculate amounts
        result = calculateAmountWithCustomPricing(summary, customer, business)
        
        # Helper function to safely convert to float
        def to_float(value):
            if value is None:
                return 0.0
            return float(value)
        
        return JsonResponse({
            'success': True,
            'calculation': {
                'subtotal': to_float(result['subtotal']),
                'tax': to_float(result['tax']),
                'total': to_float(result['total']),
                'deposit': to_float(result.get('deposit', 0)),
                'breakdown': {
                    'base_price': to_float(result.get('base_price', 0)),
                    'bedroom_total': to_float(result.get('bedroom_total', 0)),
                    'bathroom_total': to_float(result.get('bathroom_total', 0)),
                    'sqft_total': to_float(result.get('sqft_total', 0)),
                    'addons_total': to_float(result.get('addons_total', 0)),
                    'custom_addons_total': to_float(result.get('custom_addons_total', 0)),
                    'recurring_discount': to_float(result.get('recurring_discount', 0)),
                },
                'is_custom_pricing': result.get('used_custom_pricing', False),
                'tax_percent': to_float(result.get('tax_percent', 0)),
            }
        })
        
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@require_http_methods(["GET"])
def get_all_pricing(request, business_id):
    """
    Get business default pricing.
    Useful for forms that need to show default pricing initially.
    
    URL Parameters:
    - business_id: UUID of the business
    """
    try:
        business = Business.objects.filter(businessId=business_id).first()
        if not business:
            return JsonResponse({'error': 'Business not found'}, status=404)
        
        business_settings = business.settings
        
        # Helper function to safely convert to float
        def to_float(value):
            if value is None:
                return 0.0
            return float(value)
        
        pricing_data = {
            'is_custom_pricing': False,
            
            # Base pricing
            'base_price': to_float(business_settings.base_price),
            'bedroom_price': to_float(business_settings.bedroomPrice),
            'bathroom_price': to_float(business_settings.bathroomPrice),
            'deposit_fee': to_float(business_settings.depositFee),
            'tax_percent': to_float(business_settings.taxPercent),
            
            # Square feet multipliers
            'sqft_multiplier_standard': to_float(business_settings.sqftMultiplierStandard),
            'sqft_multiplier_deep': to_float(business_settings.sqftMultiplierDeep),
            'sqft_multiplier_moveinout': to_float(business_settings.sqftMultiplierMoveinout),
            'sqft_multiplier_airbnb': to_float(business_settings.sqftMultiplierAirbnb),
            
            # Standard addons
            'addon_price_dishes': to_float(business_settings.addonPriceDishes),
            'addon_price_laundry': to_float(business_settings.addonPriceLaundry),
            'addon_price_window': to_float(business_settings.addonPriceWindow),
            'addon_price_pets': to_float(business_settings.addonPricePets),
            'addon_price_fridge': to_float(business_settings.addonPriceFridge),
            'addon_price_oven': to_float(business_settings.addonPriceOven),
            'addon_price_baseboard': to_float(business_settings.addonPriceBaseboard),
            'addon_price_blinds': to_float(business_settings.addonPriceBlinds),
            'addon_price_green': to_float(business_settings.addonPriceGreen),
            'addon_price_cabinets': to_float(business_settings.addonPriceCabinets),
            'addon_price_patio': to_float(business_settings.addonPricePatio),
            'addon_price_garage': to_float(business_settings.addonPriceGarage),
            
            # Recurring discounts
            'weekly_discount': to_float(business_settings.weeklyDiscount),
            'biweekly_discount': to_float(business_settings.biweeklyDiscount),
            'monthly_discount': to_float(business_settings.monthlyDiscount),
        }
        
        # Get custom addons
        custom_addons = CustomAddons.objects.filter(business=business)
        custom_addons_pricing = {}
        
        for addon in custom_addons:
            custom_addons_pricing[str(addon.id)] = {
                'id': str(addon.id),
                'name': addon.addonName,
                'price': to_float(addon.addonPrice),
                'default_price': to_float(addon.addonPrice),
                'is_custom': False
            }
        
        pricing_data['custom_addons'] = custom_addons_pricing
        
        return JsonResponse({
            'success': True,
            'pricing': pricing_data
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

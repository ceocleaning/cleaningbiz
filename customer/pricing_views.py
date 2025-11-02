"""
Views for managing customer-specific pricing.
Allows business users to set, update, and delete custom pricing for customers.
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.db import transaction
from django.views.decorators.http import require_http_methods
from decimal import Decimal, InvalidOperation
import json

from accounts.models import Business, CustomAddons
from customer.models import Customer
from customer.pricing_models import CustomerPricing, CustomerCustomAddonPricing
from customer.pricing_utils import get_pricing_comparison


@login_required
def customer_pricing_list(request):
    """
    Display list of all customers with custom pricing.
    Shows which customers have custom pricing enabled.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        messages.error(request, "Business not found")
        return redirect('accounts:dashboard')
    
    # Get all customers linked to this business
    customers = Customer.objects.filter(businesses=business).prefetch_related('custom_pricings')
    
    # Separate customers with and without custom pricing for THIS business
    customers_with_pricing = []
    customers_without_pricing = []
    
    for customer in customers:
        # Get pricing for this specific business
        pricing = customer.custom_pricings.filter(business=business, is_active=True).first()
        
        if pricing:
            customers_with_pricing.append({
                'customer': customer,
                'pricing': pricing,
                'is_active': pricing.is_active,
                'has_custom_values': pricing.has_custom_pricing()
            })
        else:
            customers_without_pricing.append(customer)
    
    context = {
        'business': business,
        'customers_with_pricing': customers_with_pricing,
        'customers_without_pricing': customers_without_pricing,
        'total_customers': customers.count(),
        'custom_pricing_count': len(customers_with_pricing),
    }
    
    return render(request, 'customer/pricing/list.html', context)


@login_required
def customer_pricing_detail(request, customer_id):
    """
    Display and edit custom pricing for a specific customer.
    Shows comparison between business default and custom pricing.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        messages.error(request, "Business not found")
        return redirect('accounts:dashboard')
    
    customer = get_object_or_404(Customer, id=customer_id, businesses=business)
    
    # Try to get existing customer pricing, don't auto-create
    try:
        customer_pricing = CustomerPricing.objects.get(
            customer=customer,
            business=business
        )
        created = False
    except CustomerPricing.DoesNotExist:
        # Create a new instance but don't save it yet
        customer_pricing = CustomerPricing(
            customer=customer,
            business=business,
            created_by=request.user,
            is_active=False  # Inactive by default
        )
        created = True
    
    # Get business settings for comparison
    business_settings = business.settings
    
    # Get custom addons with their pricing
    custom_addons_list = []
    custom_addons = CustomAddons.objects.filter(business=business)
    
    if not created:
        addon_prices = CustomerCustomAddonPricing.objects.filter(
            customer_pricing=customer_pricing
        ).select_related('custom_addon')
        
        # Create a dict for quick lookup
        addon_pricing_dict = {ap.custom_addon.id: ap.custom_price for ap in addon_prices}
        
        # Build list with pricing info
        for addon in custom_addons:
            custom_addons_list.append({
                'addon': addon,
                'custom_price': addon_pricing_dict.get(addon.id, None)
            })
    else:
        # No custom pricing yet, just pass addons
        for addon in custom_addons:
            custom_addons_list.append({
                'addon': addon,
                'custom_price': None
            })
    
    context = {
        'business': business,
        'customer': customer,
        'customer_pricing': customer_pricing,
        'business_settings': business_settings,
        'custom_addons_list': custom_addons_list,
        'is_new': created  # Flag to indicate if this is a new pricing record
    }
    
    return render(request, 'customer/pricing/detail.html', context)


@login_required
@require_http_methods(["POST"])
def customer_pricing_update(request, customer_id):
    """
    Update custom pricing for a customer.
    Handles both base pricing and addon pricing.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        return JsonResponse({'success': False, 'error': 'Business not found'}, status=404)
    
    customer = get_object_or_404(Customer, id=customer_id, businesses=business)
    
    try:
        with transaction.atomic():
            # Get or create customer pricing (only create when actually saving)
            try:
                customer_pricing = CustomerPricing.objects.get(
                    customer=customer,
                    business=business
                )
            except CustomerPricing.DoesNotExist:
                customer_pricing = CustomerPricing(
                    customer=customer,
                    business=business,
                    created_by=request.user,
                    is_active=False  # Inactive by default, admin must activate
                )
            
            # Update is_active status
            customer_pricing.is_active = request.POST.get('is_active') == 'true'
            
            # Update base pricing fields
            pricing_fields = [
                'base_price', 'bedroom_price', 'bathroom_price', 'deposit_fee',
                'tax_percent', 'sqft_multiplier_standard', 'sqft_multiplier_deep',
                'sqft_multiplier_moveinout', 'sqft_multiplier_airbnb',
                'weekly_discount', 'biweekly_discount', 'monthly_discount',
                'addon_price_dishes', 'addon_price_laundry', 'addon_price_window',
                'addon_price_pets', 'addon_price_fridge', 'addon_price_oven',
                'addon_price_baseboard', 'addon_price_blinds', 'addon_price_green',
                'addon_price_cabinets', 'addon_price_patio', 'addon_price_garage'
            ]
            
            for field in pricing_fields:
                value = request.POST.get(field, '').strip()
                if value:
                    try:
                        setattr(customer_pricing, field, Decimal(value))
                    except (InvalidOperation, ValueError):
                        return JsonResponse({
                            'success': False,
                            'error': f'Invalid value for {field}'
                        }, status=400)
                else:
                    setattr(customer_pricing, field, None)
            
            # Update notes
            customer_pricing.notes = request.POST.get('notes', '')
            customer_pricing.save()
            
            # Update custom addon pricing
            custom_addons = CustomAddons.objects.filter(business=business)
            for addon in custom_addons:
                addon_price_key = f'custom_addon_{addon.id}'
                addon_price_value = request.POST.get(addon_price_key, '').strip()
                
                if addon_price_value:
                    try:
                        price = Decimal(addon_price_value)
                        CustomerCustomAddonPricing.objects.update_or_create(
                            customer_pricing=customer_pricing,
                            custom_addon=addon,
                            defaults={'custom_price': price}
                        )
                    except (InvalidOperation, ValueError):
                        return JsonResponse({
                            'success': False,
                            'error': f'Invalid price for {addon.addonName}'
                        }, status=400)
                else:
                    # Delete if exists and value is empty
                    CustomerCustomAddonPricing.objects.filter(
                        customer_pricing=customer_pricing,
                        custom_addon=addon
                    ).delete()
            
            messages.success(request, f'Custom pricing updated for {customer.get_full_name()}')
            return JsonResponse({
                'success': True,
                'message': 'Pricing updated successfully'
            })
            
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def customer_pricing_toggle(request, customer_id):
    """
    Toggle custom pricing on/off for a customer.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        return JsonResponse({'success': False, 'error': 'Business not found'}, status=404)
    
    customer = get_object_or_404(Customer, id=customer_id, businesses=business)
    
    try:
        customer_pricing = CustomerPricing.objects.get(
            customer=customer,
            business=business
        )
        
        customer_pricing.is_active = not customer_pricing.is_active
        customer_pricing.save()
        
        status = "enabled" if customer_pricing.is_active else "disabled"
        messages.success(request, f'Custom pricing {status} for {customer.get_full_name()}')
        
        return JsonResponse({
            'success': True,
            'is_active': customer_pricing.is_active,
            'message': f'Custom pricing {status}'
        })
        
    except CustomerPricing.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Custom pricing not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
@require_http_methods(["POST"])
def customer_pricing_delete(request, customer_id):
    """
    Delete custom pricing for a customer.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        return JsonResponse({'success': False, 'error': 'Business not found'}, status=404)
    
    customer = get_object_or_404(Customer, id=customer_id, businesses=business)
    
    try:
        customer_pricing = CustomerPricing.objects.get(
            customer=customer,
            business=business
        )
        
        customer_name = customer.get_full_name()
        customer_pricing.delete()
        
        messages.success(request, f'Custom pricing deleted for {customer_name}')
        
        return JsonResponse({
            'success': True,
            'message': 'Custom pricing deleted'
        })
        
    except CustomerPricing.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Custom pricing not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)


@login_required
def customer_pricing_comparison(request, customer_id):
    """
    API endpoint to get pricing comparison between business default and custom pricing.
    """
    business = Business.objects.filter(user=request.user).first()
    
    if not business:
        return JsonResponse({'success': False, 'error': 'Business not found'}, status=404)
    
    customer = get_object_or_404(Customer, id=customer_id, businesses=business)
    
    try:
        # Get booking details from request
        summary = {
            'serviceType': request.GET.get('service_type', 'standard'),
            'bedrooms': request.GET.get('bedrooms', 0),
            'bathrooms': request.GET.get('bathrooms', 0),
            'squareFeet': request.GET.get('square_feet', 0),
            'addonDishes': request.GET.get('addon_dishes', 0),
            'addonLaundryLoads': request.GET.get('addon_laundry', 0),
            'addonWindowCleaning': request.GET.get('addon_windows', 0),
            'addonPetsCleaning': request.GET.get('addon_pets', 0),
            'addonFridgeCleaning': request.GET.get('addon_fridge', 0),
            'addonOvenCleaning': request.GET.get('addon_oven', 0),
            'addonBaseboard': request.GET.get('addon_baseboard', 0),
            'addonBlinds': request.GET.get('addon_blinds', 0),
            'addonGreenCleaning': request.GET.get('addon_green', 0),
            'addonCabinetsCleaning': request.GET.get('addon_cabinets', 0),
            'addonPatioSweeping': request.GET.get('addon_patio', 0),
            'addonGarageSweeping': request.GET.get('addon_garage', 0),
        }
        
        comparison = get_pricing_comparison(business, customer, summary)
        
        return JsonResponse({
            'success': True,
            'comparison': {
                'business_total': float(comparison['business_pricing'].get('total_amount', 0)),
                'custom_total': float(comparison['custom_pricing'].get('total_amount', 0)),
                'savings_amount': float(comparison['savings']['amount']),
                'savings_percent': float(comparison['savings']['percent']),
                'has_savings': comparison['savings']['has_savings']
            }
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=500)

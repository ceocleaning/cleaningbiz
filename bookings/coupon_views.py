from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Sum
from django.utils import timezone
from datetime import timedelta, datetime
from decimal import Decimal

from .models import Coupon, CouponUsage
from accounts.models import Business
from customer.models import Customer


@login_required
def coupon_list(request):
    """List all coupons for the business"""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    
    # Get filter parameters
    status_filter = request.GET.get('status', 'all')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    coupons = Coupon.objects.filter(business=business).annotate(
        total_usage=Count('usages'),
        total_discount_given=Sum('usages__discount_amount')
    )
    
    # Apply filters
    if status_filter != 'all':
        coupons = coupons.filter(status=status_filter)
    
    if search_query:
        coupons = coupons.filter(
            Q(code__icontains=search_query) |
            Q(description__icontains=search_query)
        )
    
    # Update expired coupons
    now = timezone.now()
    expired_coupons = coupons.filter(valid_until__lt=now, status='active')
    expired_coupons.update(status='expired')
    
    # Refresh queryset after update
    coupons = coupons.order_by('-created_at')
    
    # Calculate statistics
    active_count = coupons.filter(status='active').count()
    expired_count = coupons.filter(status='expired').count()
    inactive_count = coupons.filter(status='inactive').count()
    
    context = {
        'coupons': coupons,
        'active_count': active_count,
        'expired_count': expired_count,
        'inactive_count': inactive_count,
        'status_filter': status_filter,
        'search_query': search_query,
        'business': business,
    }
    
    return render(request, 'bookings/coupons/list.html', context)


@login_required
def coupon_create(request):
    """Create a new coupon"""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    
    if request.method == 'POST':
        try:
            # Get form data
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            discount_type = request.POST.get('discount_type')
            discount_value = Decimal(request.POST.get('discount_value', 0))
            max_uses = request.POST.get('max_uses')
            max_uses_per_customer = int(request.POST.get('max_uses_per_customer', 1))
            valid_from = request.POST.get('valid_from')
            valid_until = request.POST.get('valid_until')
            min_booking_amount = request.POST.get('min_booking_amount')
            is_active = request.POST.get('is_active') == 'on'
            
            # Validation
            if not code:
                messages.error(request, 'Coupon code is required')
                return redirect('bookings:coupon_create')
            
            if Coupon.objects.filter(code=code).exists():
                messages.error(request, 'A coupon with this code already exists')
                return redirect('bookings:coupon_create')
            
            if discount_type == 'percentage' and (discount_value < 0 or discount_value > 100):
                messages.error(request, 'Percentage discount must be between 0 and 100')
                return redirect('bookings:coupon_create')
            
            # Parse datetime strings to timezone-aware datetime objects
            valid_from_dt = timezone.make_aware(datetime.strptime(valid_from, '%Y-%m-%dT%H:%M'))
            valid_until_dt = timezone.make_aware(datetime.strptime(valid_until, '%Y-%m-%dT%H:%M'))
            
            # Create coupon
            coupon = Coupon.objects.create(
                business=business,
                code=code,
                description=description,
                discount_type=discount_type,
                discount_value=discount_value,
                max_uses=int(max_uses) if max_uses else None,
                max_uses_per_customer=max_uses_per_customer,
                valid_from=valid_from_dt,
                valid_until=valid_until_dt,
                min_booking_amount=Decimal(min_booking_amount) if min_booking_amount else None,
                is_active=is_active,
                created_by=request.user
            )
            
            messages.success(request, f'Coupon "{code}" created successfully!')
            return redirect('bookings:coupon_list')
            
        except Exception as e:
            messages.error(request, f'Error creating coupon: {str(e)}')
            return redirect('bookings:coupon_create')
    
    context = {
        'business': business,
    }
    
    return render(request, 'bookings/coupons/create.html', context)


@login_required
def coupon_edit(request, coupon_id):
    """Edit an existing coupon"""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    coupon = get_object_or_404(Coupon, id=coupon_id, business=business)
    
    if request.method == 'POST':
        try:
            # Get form data
            code = request.POST.get('code', '').strip().upper()
            description = request.POST.get('description', '').strip()
            discount_type = request.POST.get('discount_type')
            discount_value = Decimal(request.POST.get('discount_value', 0))
            max_uses = request.POST.get('max_uses')
            max_uses_per_customer = int(request.POST.get('max_uses_per_customer', 1))
            valid_from = request.POST.get('valid_from')
            valid_until = request.POST.get('valid_until')
            min_booking_amount = request.POST.get('min_booking_amount')
            is_active = request.POST.get('is_active') == 'on'
            
            # Validation
            if not code:
                messages.error(request, 'Coupon code is required')
                return redirect('bookings:coupon_edit', coupon_id=coupon_id)
            
            # Check if code is being changed and if it already exists
            if code != coupon.code and Coupon.objects.filter(code=code).exists():
                messages.error(request, 'A coupon with this code already exists')
                return redirect('bookings:coupon_edit', coupon_id=coupon_id)
            
            if discount_type == 'percentage' and (discount_value < 0 or discount_value > 100):
                messages.error(request, 'Percentage discount must be between 0 and 100')
                return redirect('bookings:coupon_edit', coupon_id=coupon_id)
            
            # Parse datetime strings to timezone-aware datetime objects
            valid_from_dt = timezone.make_aware(datetime.strptime(valid_from, '%Y-%m-%dT%H:%M'))
            valid_until_dt = timezone.make_aware(datetime.strptime(valid_until, '%Y-%m-%dT%H:%M'))
            
            # Update coupon
            coupon.code = code
            coupon.description = description
            coupon.discount_type = discount_type
            coupon.discount_value = discount_value
            coupon.max_uses = int(max_uses) if max_uses else None
            coupon.max_uses_per_customer = max_uses_per_customer
            coupon.valid_from = valid_from_dt
            coupon.valid_until = valid_until_dt
            coupon.min_booking_amount = Decimal(min_booking_amount) if min_booking_amount else None
            coupon.is_active = is_active
            coupon.save()
            
            messages.success(request, f'Coupon "{code}" updated successfully!')
            return redirect('bookings:coupon_list')
            
        except Exception as e:
            messages.error(request, f'Error updating coupon: {str(e)}')
            return redirect('bookings:coupon_edit', coupon_id=coupon_id)
    
    context = {
        'business': business,
        'coupon': coupon,
    }
    
    return render(request, 'bookings/coupons/edit.html', context)


@login_required
def coupon_detail(request, coupon_id):
    """View coupon details and usage statistics"""
    if not Business.objects.filter(user=request.user).exists():
        return redirect('accounts:register_business')
    
    business = request.user.business_set.first()
    coupon = get_object_or_404(Coupon, id=coupon_id, business=business)
    
    # Get usage statistics
    usages = CouponUsage.objects.filter(coupon=coupon).select_related(
        'customer', 'booking'
    ).order_by('-applied_at')
    
    total_discount_given = sum(usage.discount_amount for usage in usages)
    unique_customers = usages.values('customer').distinct().count()
    
    # Calculate usage by date (last 30 days)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    recent_usages = usages.filter(applied_at__gte=thirty_days_ago)
    
    context = {
        'business': business,
        'coupon': coupon,
        'usages': usages[:50],  # Limit to 50 most recent
        'total_usages': usages.count(),
        'total_discount_given': total_discount_given,
        'unique_customers': unique_customers,
        'recent_usages_count': recent_usages.count(),
    }
    
    return render(request, 'bookings/coupons/detail.html', context)


@login_required
@require_http_methods(["POST"])
def coupon_delete(request, coupon_id):
    """Delete a coupon"""
    if not Business.objects.filter(user=request.user).exists():
        return JsonResponse({'success': False, 'message': 'Business not found'}, status=404)
    
    business = request.user.business_set.first()
    coupon = get_object_or_404(Coupon, id=coupon_id, business=business)
    
    try:
        code = coupon.code
        coupon.delete()
        messages.success(request, f'Coupon "{code}" deleted successfully!')
        return JsonResponse({'success': True, 'message': 'Coupon deleted successfully'})
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


@login_required
@require_http_methods(["POST"])
def coupon_toggle_status(request, coupon_id):
    """Toggle coupon active status"""
    if not Business.objects.filter(user=request.user).exists():
        return JsonResponse({'success': False, 'message': 'Business not found'}, status=404)
    
    business = request.user.business_set.first()
    coupon = get_object_or_404(Coupon, id=coupon_id, business=business)
    
    try:
        coupon.is_active = not coupon.is_active
        coupon.save()
        
        status = 'activated' if coupon.is_active else 'deactivated'
        messages.success(request, f'Coupon "{coupon.code}" {status} successfully!')
        
        return JsonResponse({
            'success': True,
            'message': f'Coupon {status}',
            'is_active': coupon.is_active
        })
    except Exception as e:
        return JsonResponse({'success': False, 'message': str(e)}, status=500)

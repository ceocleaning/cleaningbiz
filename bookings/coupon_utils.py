"""
Utility functions for coupon handling
"""
from decimal import Decimal
from django.core.exceptions import ValidationError
from .models import Coupon, CouponUsage


def apply_coupon_to_booking(coupon_code, booking, customer, booking_amount):
    """
    Apply a coupon to a booking and record the usage.
    
    Args:
        coupon_code (str): The coupon code to apply
        booking (Booking): The booking instance
        customer (Customer): The customer using the coupon
        booking_amount (Decimal): The booking amount before coupon discount
        
    Returns:
        tuple: (success: bool, discount_amount: Decimal, message: str, coupon: Coupon or None)
    """
    if not coupon_code or not coupon_code.strip():
        return False, Decimal('0'), 'No coupon code provided', None
    
    coupon_code = coupon_code.strip().upper()
    
    try:
        # Get the coupon by code only (no business filter)
        coupon = Coupon.objects.get(code=coupon_code)
        
        # Validate coupon is valid
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return False, Decimal('0'), message, None
        
        # Validate customer can use this coupon
        can_use, message = coupon.can_be_used_by_customer(customer)
        if not can_use:
            return False, Decimal('0'), message, None
        
        # Validate coupon can be applied to this booking amount
        can_apply, message = coupon.can_apply_to_booking(
            booking_amount, 
            booking.serviceType if hasattr(booking, 'serviceType') else None
        )
        if not can_apply:
            return False, Decimal('0'), message, None
        
        # Calculate discount
        discount_amount = coupon.calculate_discount(booking_amount)
        
        # Record coupon usage
        try:
            CouponUsage.objects.create(
                coupon=coupon,
                booking=booking,
                customer=customer,
                discount_amount=discount_amount
            )
            
            # Increment coupon usage counter
            coupon.current_uses += 1
            coupon.save()
            
            return True, discount_amount, f'Coupon {coupon.code} applied successfully!', coupon
            
        except Exception as e:
            return False, Decimal('0'), f'Error recording coupon usage: {str(e)}', None
            
    except Coupon.DoesNotExist:
        return False, Decimal('0'), 'Invalid coupon code', None
    except Exception as e:
        return False, Decimal('0'), f'Error applying coupon: {str(e)}', None


def validate_coupon(coupon_code, customer=None, booking_amount=None, service_type=None):
    """
    Validate a coupon code without applying it.
    
    Args:
        coupon_code (str): The coupon code to validate
        customer (Customer, optional): The customer who wants to use the coupon
        booking_amount (Decimal, optional): The booking amount to check against minimum
        service_type (str, optional): The service type to check restrictions
        
    Returns:
        dict: {
            'valid': bool,
            'message': str,
            'coupon': Coupon or None,
            'discount_amount': Decimal (if booking_amount provided)
        }
    """
    if not coupon_code or not coupon_code.strip():
        return {
            'valid': False,
            'message': 'Please enter a coupon code',
            'coupon': None,
            'discount_amount': Decimal('0')
        }
    
    coupon_code = coupon_code.strip().upper()
    
    try:
        # Get the coupon by code only
        coupon = Coupon.objects.get(code=coupon_code)
        
        # Check if coupon is valid
        is_valid, message = coupon.is_valid()
        if not is_valid:
            return {
                'valid': False,
                'message': message,
                'coupon': None,
                'discount_amount': Decimal('0')
            }
        
        # Check customer-specific restrictions if customer provided
        if customer:
            can_use, message = coupon.can_be_used_by_customer(customer)
            if not can_use:
                return {
                    'valid': False,
                    'message': message,
                    'coupon': None,
                    'discount_amount': Decimal('0')
                }
        
        # Check booking amount and service type restrictions if provided
        if booking_amount is not None:
            can_apply, message = coupon.can_apply_to_booking(booking_amount, service_type)
            if not can_apply:
                return {
                    'valid': False,
                    'message': message,
                    'coupon': None,
                    'discount_amount': Decimal('0')
                }
            
            # Calculate discount
            discount_amount = coupon.calculate_discount(booking_amount)
        else:
            discount_amount = Decimal('0')
        
        return {
            'valid': True,
            'message': 'Coupon is valid',
            'coupon': coupon,
            'discount_amount': discount_amount
        }
        
    except Coupon.DoesNotExist:
        return {
            'valid': False,
            'message': 'Invalid coupon code',
            'coupon': None,
            'discount_amount': Decimal('0')
        }
    except Exception as e:
        return {
            'valid': False,
            'message': f'Error validating coupon: {str(e)}',
            'coupon': None,
            'discount_amount': Decimal('0')
        }


def get_coupon_by_code(coupon_code):
    """
    Get a coupon by its code.
    
    Args:
        coupon_code (str): The coupon code
        
    Returns:
        Coupon or None: The coupon instance if found, None otherwise
    """
    if not coupon_code or not coupon_code.strip():
        return None
    
    coupon_code = coupon_code.strip().upper()
    
    try:
        return Coupon.objects.get(code=coupon_code)
    except Coupon.DoesNotExist:
        return None


def calculate_coupon_discount(coupon_code, booking_amount):
    """
    Calculate the discount amount for a given coupon and booking amount.
    
    Args:
        coupon_code (str): The coupon code
        booking_amount (Decimal): The booking amount
        
    Returns:
        tuple: (discount_amount: Decimal, success: bool, message: str)
    """
    coupon = get_coupon_by_code(coupon_code)
    
    if not coupon:
        return Decimal('0'), False, 'Invalid coupon code'
    
    # Check if coupon is valid
    is_valid, message = coupon.is_valid()
    if not is_valid:
        return Decimal('0'), False, message
    
    # Calculate discount
    discount_amount = coupon.calculate_discount(booking_amount)
    
    return discount_amount, True, 'Discount calculated successfully'


def get_customer_coupon_usage(customer, coupon=None):
    """
    Get coupon usage statistics for a customer.
    
    Args:
        customer (Customer): The customer
        coupon (Coupon, optional): Specific coupon to check usage for
        
    Returns:
        dict: Usage statistics
    """
    if coupon:
        usage_count = CouponUsage.objects.filter(
            customer=customer,
            coupon=coupon
        ).count()
        
        total_discount = sum(
            usage.discount_amount 
            for usage in CouponUsage.objects.filter(customer=customer, coupon=coupon)
        )
        
        return {
            'usage_count': usage_count,
            'total_discount': total_discount,
            'can_use_again': usage_count < coupon.max_uses_per_customer
        }
    else:
        # Get all coupon usage for customer
        all_usages = CouponUsage.objects.filter(customer=customer)
        
        return {
            'total_coupons_used': all_usages.values('coupon').distinct().count(),
            'total_times_used': all_usages.count(),
            'total_discount_received': sum(usage.discount_amount for usage in all_usages)
        }


def remove_coupon_from_booking(booking):
    """
    Remove coupon usage from a booking (useful for cancellations/refunds).
    
    Args:
        booking (Booking): The booking instance
        
    Returns:
        tuple: (success: bool, message: str)
    """
    try:
        coupon_usage = CouponUsage.objects.filter(booking=booking).first()
        
        if not coupon_usage:
            return True, 'No coupon was applied to this booking'
        
        coupon = coupon_usage.coupon
        
        # Decrement coupon usage counter
        if coupon.current_uses > 0:
            coupon.current_uses -= 1
            coupon.save()
        
        # Delete the usage record
        coupon_usage.delete()
        
        return True, f'Coupon {coupon.code} removed from booking'
        
    except Exception as e:
        return False, f'Error removing coupon: {str(e)}'

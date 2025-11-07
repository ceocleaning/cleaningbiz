from rest_framework import status
from rest_framework.decorators import api_view, permission_classes, authentication_classes
from rest_framework.response import Response
from rest_framework.permissions import AllowAny
from rest_framework.authentication import SessionAuthentication
from django.shortcuts import get_object_or_404
from django.db import transaction
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from datetime import datetime, timedelta
from decimal import Decimal
import pytz
import json

from accounts.models import Business, BusinessSettings, CustomAddons
from bookings.models import Booking, BookingCustomAddons
from bookings.coupon_utils import validate_coupon, apply_coupon_to_booking
from customer.models import Customer
from customer.serializers import BookingSerializer, CustomerSerializer
from automation.utils import format_phone_number
from invoice.models import Invoice
from accounts.timezone_utils import convert_to_utc


class CsrfExemptSessionAuthentication(SessionAuthentication):
    """Session authentication without CSRF check"""
    def enforce_csrf(self, request):
        return  # Skip CSRF check


@api_view(['GET', 'POST'])
@authentication_classes([CsrfExemptSessionAuthentication])
@permission_classes([AllowAny])
@transaction.atomic
def booking_api(request, business_id):
    """
    API endpoint to handle booking creation for customers
    GET: Returns business details and pricing information
    POST: Creates a new booking
    """
    # Get business from URL parameter
    business = get_object_or_404(Business, businessId=business_id, isApproved=True, isActive=True)
    
    # Get business settings for pricing
    try:
        business_settings = BusinessSettings.objects.get(business=business)
    except BusinessSettings.DoesNotExist:
        return Response(
            {"error": "Business settings not found"},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get custom add-ons for this business
    custom_addons = CustomAddons.objects.filter(business=business)
    
    if request.method == 'GET':
        # Prepare pricing data for frontend
        prices = {
            'base_price': float(business_settings.base_price),
            'bedrooms': float(business_settings.bedroomPrice),
            'bathrooms': float(business_settings.bathroomPrice),
            'sqftMultiplierStandard': float(business_settings.sqftMultiplierStandard),
            'sqftMultiplierDeep': float(business_settings.sqftMultiplierDeep),
            'sqftMultiplierMoveinout': float(business_settings.sqftMultiplierMoveinout),
            'sqftMultiplierAirbnb': float(business_settings.sqftMultiplierAirbnb),
            'addonPriceDishes': float(business_settings.addonPriceDishes),
            'addonPriceLaundry': float(business_settings.addonPriceLaundry),
            'addonPriceWindow': float(business_settings.addonPriceWindow),
            'addonPricePets': float(business_settings.addonPricePets),
            'addonPriceFridge': float(business_settings.addonPriceFridge),
            'addonPriceOven': float(business_settings.addonPriceOven),
            'addonPriceBaseboard': float(business_settings.addonPriceBaseboard),
            'addonPriceBlinds': float(business_settings.addonPriceBlinds),
            'tax': float(business_settings.taxPercent)
        }
        
        # Prepare custom addons data
        custom_addons_data = []
        for addon in custom_addons:
            custom_addons_data.append({
                'id': addon.id,
                'addonName': addon.addonName,
                'addonPrice': float(addon.addonPrice)
            })
        
        # Prepare business data
        business_data = {
            'businessId': business.businessId,
            'businessName': business.businessName,
            'address': business.address,
            'timezone': business.timezone,
        }
        
        return Response({
            'business': business_data,
            'prices': prices,
            'customAddons': custom_addons_data
        })
    
    elif request.method == 'POST':
        try:
            data = request.data
            
            # Get price details from request (already calculated on frontend with coupon applied)
            subtotal = Decimal(str(data.get('subtotal', '0')))
            tax = Decimal(str(data.get('tax', '0')))
            total_price = Decimal(str(data.get('totalAmount', '0')))
            
            # Format phone number
            phone_number = data.get('phoneNumber')
            if phone_number:
                phone_number = format_phone_number(phone_number)
            
            if not phone_number:
                return Response(
                    {"error": "Please enter a valid phone number."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get cleaning date and time
            cleaning_date = data.get('cleaningDate')
            start_time = data.get('startTime')
            
            # Parse the datetime string in business timezone
            business_tz = pytz.timezone(business.timezone)
            datetime_str = f"{cleaning_date} {start_time}"
            
            # Create naive datetime and localize to business timezone
            naive_datetime = datetime.strptime(datetime_str, '%Y-%m-%d %H:%M')
            localized_datetime = business_tz.localize(naive_datetime)
            
            # Convert to UTC
            datetime_utc = localized_datetime.astimezone(pytz.UTC)
            
            # Extract date and time components
            cleaning_date_utc = datetime_utc.date()
            start_time_utc = datetime_utc.time()
            
            # Set end time to 1 hour after start time
            end_datetime_utc = datetime_utc + timedelta(hours=1)
            end_time_utc = end_datetime_utc.time()
            
            # Try to find customer by email or create new one
            customer_email = data.get('email')
            try:
                customer = Customer.objects.get(email=customer_email)
            except Customer.DoesNotExist:
                # Create new customer
                customer = Customer.objects.create(
                    user=request.user if request.user.is_authenticated else None,
                    first_name=data.get('firstName'),
                    last_name=data.get('lastName'),
                    email=customer_email,
                    phone_number=phone_number,
                    address=data.get('address'),
                    city=data.get('city'),
                    state_or_province=data.get('stateOrProvince'),
                    zip_code=data.get('zipCode')
                )
            
            # Handle coupon if applied
            applied_coupon_code = data.get('appliedCouponCode', '').strip()
            coupon_discount_amount = Decimal(str(data.get('couponDiscountAmount', '0')))
            
            # Validate coupon before creating booking
            validated_coupon = None
            if applied_coupon_code:
                # For validation, use subtotal before coupon (add back the coupon discount)
                subtotal_before_coupon = subtotal + coupon_discount_amount
                
                validation_result = validate_coupon(
                    coupon_code=applied_coupon_code,
                    customer=customer,
                    booking_amount=subtotal_before_coupon,
                    service_type=data.get('serviceType')
                )
                
                if not validation_result['valid']:
                    # Coupon validation failed, but continue with booking without coupon
                    coupon_discount_amount = Decimal('0')
                    validated_coupon = None
                else:
                    # Use validated coupon object
                    validated_coupon = validation_result['coupon']
            
            # Create the booking
            booking = Booking.objects.create(
                business=business,
                customer=customer,
                bedrooms=int(data.get('bedrooms', 0)),
                bathrooms=int(data.get('bathrooms', 0)),
                squareFeet=int(data.get('squareFeet', 0)),
                serviceType=data.get('serviceType'),
                cleaningDate=cleaning_date_utc,
                startTime=start_time_utc,
                endTime=end_time_utc,
                recurring=data.get('recurring'),
                paymentMethod='creditcard',  # Default payment method
                otherRequests=data.get('otherRequests', ''),
                tax=tax,
                totalPrice=total_price,
                applied_coupon=validated_coupon,
                coupon_discount_amount=coupon_discount_amount
            )
            
            # Handle standard add-ons
            addon_fields = [
                'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
                'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
                'addonBaseboard', 'addonBlinds'
            ]
            
            for field in addon_fields:
                value = int(data.get(field, 0))
                if value > 0:
                    setattr(booking, field, value)
            
            booking.save()
            
            # Handle custom add-ons
            for addon in custom_addons:
                addon_id = str(addon.id)
                quantity_key = f'custom_addon_qty_{addon_id}'
                quantity = int(data.get(quantity_key, 0))
                
                if quantity > 0:
                    new_custom_booking_addon = BookingCustomAddons.objects.create(
                        addon=addon,
                        qty=quantity
                    )
                    booking.customAddons.add(new_custom_booking_addon)
            
            # Record coupon usage if coupon was applied
            coupon_message = None
            if applied_coupon_code and coupon_discount_amount > 0:
                success, discount, message, coupon = apply_coupon_to_booking(
                    coupon_code=applied_coupon_code,
                    booking=booking,
                    customer=customer,
                    booking_amount=subtotal + coupon_discount_amount  # Original amount before coupon
                )
                
                if success:
                    coupon_message = message
            
            # The invoice will be created automatically by the signal handler
            # Get the invoice that was created by the signal
            invoice = Invoice.objects.get(booking=booking)
            
            response_data = {
                'success': True,
                'message': 'Booking created successfully!',
                'bookingId': booking.bookingId,
                'invoiceId': invoice.invoiceId
            }
            
            if coupon_message:
                response_data['couponMessage'] = coupon_message
            
            return Response(response_data, status=status.HTTP_201_CREATED)
            
        except Exception as e:
            return Response(
                {"error": f"Error creating booking: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

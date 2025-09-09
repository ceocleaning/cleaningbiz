from rest_framework import serializers
from bookings.models import Booking, BookingCustomAddons
from customer.models import Customer
from accounts.models import CustomAddons

class CustomerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Customer
        fields = ['first_name', 'last_name', 'email', 'phone_number', 'address', 'city', 'state_or_province', 'zip_code']

class CustomAddonSerializer(serializers.ModelSerializer):
    qty = serializers.IntegerField(required=False, default=0)
    
    class Meta:
        model = CustomAddons
        fields = ['id', 'addonName', 'addonPrice', 'qty']

class BookingCustomAddonSerializer(serializers.ModelSerializer):
    addon = CustomAddonSerializer()
    
    class Meta:
        model = BookingCustomAddons
        fields = ['addon', 'qty']

class BookingSerializer(serializers.ModelSerializer):
    customer = CustomerSerializer()
    customAddons = BookingCustomAddonSerializer(many=True, required=False)
    
    class Meta:
        model = Booking
        fields = [
            'business', 'customer', 'bedrooms', 'bathrooms', 'squareFeet',
            'serviceType', 'cleaningDate', 'startTime', 'endTime', 'recurring',
            'paymentMethod', 'otherRequests', 'tax', 'totalPrice',
            'addonDishes', 'addonLaundryLoads', 'addonWindowCleaning',
            'addonPetsCleaning', 'addonFridgeCleaning', 'addonOvenCleaning',
            'addonBaseboard', 'addonBlinds', 'customAddons'
        ]
        read_only_fields = ['bookingId']

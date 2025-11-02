from django.db import models
from decimal import Decimal


class CustomerPricing(models.Model):
    """
    Custom pricing configuration for individual customers.
    Allows businesses to offer discounted or custom rates to specific customers.
    Now supports one customer having different pricing with multiple businesses.
    """
    customer = models.ForeignKey(
        'customer.Customer', 
        on_delete=models.CASCADE, 
        related_name='custom_pricings'
    )
    business = models.ForeignKey(
        'accounts.Business', 
        on_delete=models.CASCADE, 
        related_name='customer_pricings'
    )
    
    # Toggle to enable/disable custom pricing
    is_active = models.BooleanField(
        default=False,
        help_text="Enable or disable custom pricing for this customer"
    )
    
    # Base Pricing
    base_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom base price (leave blank to use business default)"
    )
    bedroom_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom price per bedroom (leave blank to use business default)"
    )
    bathroom_price = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom price per bathroom (leave blank to use business default)"
    )
    deposit_fee = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom deposit fee (leave blank to use business default)"
    )
    tax_percent = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom tax percentage (leave blank to use business default)"
    )
    
    # Square Feet Multipliers
    sqft_multiplier_standard = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom square feet multiplier for standard cleaning"
    )
    sqft_multiplier_deep = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom square feet multiplier for deep cleaning"
    )
    sqft_multiplier_moveinout = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom square feet multiplier for move-in/out cleaning"
    )
    sqft_multiplier_airbnb = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom square feet multiplier for Airbnb cleaning"
    )
    
    # Recurring Discounts
    weekly_discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom weekly discount percentage"
    )
    biweekly_discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom bi-weekly discount percentage"
    )
    monthly_discount = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Custom monthly discount percentage"
    )
    
    # Add-on Prices
    addon_price_dishes = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_laundry = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_window = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_pets = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_fridge = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_oven = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_baseboard = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_blinds = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_green = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_cabinets = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_patio = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    addon_price_garage = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        null=True, 
        blank=True
    )
    
    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Internal notes about this custom pricing"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_by = models.ForeignKey(
        'auth.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_customer_pricings'
    )
    
    class Meta:
        verbose_name = "Customer Pricing"
        verbose_name_plural = "Customer Pricings"
        unique_together = ['customer', 'business']
        ordering = ['-created_at']
    
    def __str__(self):
        status = "Active" if self.is_active else "Inactive"
        return f"Custom Pricing for {self.customer.get_full_name()} ({status})"
    
    def get_effective_value(self, field_name, business_settings):
        """
        Get the effective value for a pricing field.
        Returns custom value if set, otherwise falls back to business default.
        """
        custom_value = getattr(self, field_name, None)
        if custom_value is not None:
            return custom_value
        
        # Map customer pricing fields to business settings fields
        field_mapping = {
            'base_price': 'base_price',
            'bedroom_price': 'bedroomPrice',
            'bathroom_price': 'bathroomPrice',
            'deposit_fee': 'depositFee',
            'tax_percent': 'taxPercent',
            'sqft_multiplier_standard': 'sqftMultiplierStandard',
            'sqft_multiplier_deep': 'sqftMultiplierDeep',
            'sqft_multiplier_moveinout': 'sqftMultiplierMoveinout',
            'sqft_multiplier_airbnb': 'sqftMultiplierAirbnb',
            'weekly_discount': 'weeklyDiscount',
            'biweekly_discount': 'biweeklyDiscount',
            'monthly_discount': 'monthlyDiscount',
            'addon_price_dishes': 'addonPriceDishes',
            'addon_price_laundry': 'addonPriceLaundry',
            'addon_price_window': 'addonPriceWindow',
            'addon_price_pets': 'addonPricePets',
            'addon_price_fridge': 'addonPriceFridge',
            'addon_price_oven': 'addonPriceOven',
            'addon_price_baseboard': 'addonPriceBaseboard',
            'addon_price_blinds': 'addonPriceBlinds',
            'addon_price_green': 'addonPriceGreen',
            'addon_price_cabinets': 'addonPriceCabinets',
            'addon_price_patio': 'addonPricePatio',
            'addon_price_garage': 'addonPriceGarage',
        }
        
        business_field = field_mapping.get(field_name)
        if business_field and business_settings:
            return getattr(business_settings, business_field, 0)
        
        return Decimal('0')
    
    def has_custom_pricing(self):
        """Check if any custom pricing fields are set"""
        fields_to_check = [
            'base_price', 'bedroom_price', 'bathroom_price', 'deposit_fee',
            'tax_percent', 'sqft_multiplier_standard', 'sqft_multiplier_deep',
            'sqft_multiplier_moveinout', 'sqft_multiplier_airbnb',
            'weekly_discount', 'biweekly_discount', 'monthly_discount',
            'addon_price_dishes', 'addon_price_laundry', 'addon_price_window',
            'addon_price_pets', 'addon_price_fridge', 'addon_price_oven',
            'addon_price_baseboard', 'addon_price_blinds', 'addon_price_green',
            'addon_price_cabinets', 'addon_price_patio', 'addon_price_garage'
        ]
        
        for field in fields_to_check:
            if getattr(self, field, None) is not None:
                return True
        return False
    
    @classmethod
    def get_pricing_for_booking(cls, customer, business):
        """
        Get the appropriate pricing configuration for a booking.
        
        This method handles the multi-business scenario where a customer may have
        different custom pricing with different businesses:
        
        - If the customer has active custom pricing with THIS business → use custom pricing
        - If the customer has NO custom pricing with THIS business → use business standard pricing
        - Each business-customer relationship has independent pricing
        
        Args:
            customer: Customer instance
            business: Business instance
        
        Returns:
            tuple: (pricing_object, is_custom_pricing: bool)
                - pricing_object: CustomerPricing or BusinessSettings instance
                - is_custom_pricing: True if custom pricing is being used
        
        Example:
            Customer A books with Business 1 (has custom pricing) → uses custom pricing
            Customer A books with Business 2 (no custom pricing) → uses standard pricing
        """
        try:
            custom_pricing = cls.objects.filter(
                customer=customer,
                business=business,
                is_active=True
            ).first()
            
            if custom_pricing and custom_pricing.has_custom_pricing():
                return (custom_pricing, True)
        except Exception as e:
            print(f"Error retrieving custom pricing: {str(e)}")
        
        # Fall back to business standard pricing
        return (business.settings, False)


class CustomerCustomAddonPricing(models.Model):
    """
    Custom pricing for business custom addons for specific customers.
    """
    customer_pricing = models.ForeignKey(
        CustomerPricing,
        on_delete=models.CASCADE,
        related_name='custom_addon_prices'
    )
    custom_addon = models.ForeignKey(
        'accounts.CustomAddons',
        on_delete=models.CASCADE
    )
    custom_price = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        help_text="Custom price for this addon for this customer"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Customer Custom Addon Pricing"
        verbose_name_plural = "Customer Custom Addon Pricings"
        unique_together = ['customer_pricing', 'custom_addon']
        ordering = ['custom_addon__addonName']
    
    def __str__(self):
        return f"{self.custom_addon.addonName} - ${self.custom_price} for {self.customer_pricing.customer.get_full_name()}"

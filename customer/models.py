from django.db import models
from django.contrib.auth.models import User
import uuid

# Create your models here.

class Customer(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    businesses = models.ManyToManyField('accounts.Business', related_name='customers', blank=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True, related_name='customer')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    email = models.EmailField(null=True, blank=True)
    phone_number = models.CharField(max_length=15)

    address = models.CharField(max_length=255, null=True, blank=True)
    city = models.CharField(max_length=100, null=True, blank=True)
    state_or_province = models.CharField(max_length=100, null=True, blank=True)
    zip_code = models.CharField(max_length=10, null=True, blank=True)

    timezone = models.CharField(max_length=100, default='UTC')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Customer'
        verbose_name_plural = 'Customers'

    
    def get_full_name(self):
        return self.first_name + ' ' + self.last_name
    

    def get_address(self):
        return f"{self.address}, {self.city}, {self.state_or_province} {self.zip_code}"
    

    def __str__(self):
        return self.get_full_name()
    
    def has_custom_pricing_for_business(self, business):
        """
        Check if this customer has active custom pricing for a specific business.
        
        Args:
            business: Business instance
        
        Returns:
            bool: True if active custom pricing exists for this business
        """
        try:
            from customer.pricing_models import CustomerPricing
            return CustomerPricing.objects.filter(
                customer=self,
                business=business,
                is_active=True
            ).exists()
        except Exception:
            return False
    
    def get_custom_pricing_for_business(self, business):
        """
        Get the custom pricing configuration for this customer with a specific business.
        
        Args:
            business: Business instance
        
        Returns:
            CustomerPricing instance or None
        """
        try:
            from customer.pricing_models import CustomerPricing
            return CustomerPricing.objects.filter(
                customer=self,
                business=business,
                is_active=True
            ).first()
        except Exception:
            return None
    
    def get_all_businesses(self):
        """
        Get all businesses this customer is linked to.
        
        Returns:
            QuerySet of Business instances
        """
        return self.businesses.all()


class Review(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    booking = models.ForeignKey('bookings.Booking', on_delete=models.CASCADE, null=True, blank=True, related_name='reviews')
    review = models.TextField()
    rating = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Review'
        verbose_name_plural = 'Reviews'
    
    def __str__(self):
        return self.user.get_full_name() + ' - ' + self.review[:50] + '...'

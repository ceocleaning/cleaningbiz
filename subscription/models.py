from django.db import models
from django.utils import timezone
from django.contrib.auth import get_user_model
from accounts.models import Business
import json

User = get_user_model()

class SubscriptionPlan(models.Model):
    """Model representing the different subscription plans available."""
    BILLING_CYCLE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
    ]
    
    name = models.CharField(max_length=100)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    billing_cycle = models.CharField(max_length=10, choices=BILLING_CYCLE_CHOICES, default='monthly')
    voice_minutes = models.IntegerField(default=0)
    voice_calls = models.IntegerField(default=0)
    sms_messages = models.IntegerField(default=0)
    features = models.JSONField(default=dict)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_billing_cycle_display()}) - ${self.price}"

class BusinessSubscription(models.Model):
    """Model representing a business's subscription to a plan."""
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('cancelled', 'Cancelled'),
        ('past_due', 'Past Due'),
        ('trialing', 'Trialing'),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='subscriptions')
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, related_name='business_subscriptions')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(null=True, blank=True)
    stripe_subscription_id = models.CharField(max_length=100, blank=True, null=True)
    stripe_customer_id = models.CharField(max_length=100, blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business.businessName} - {self.plan.name} ({self.status})"
    
    def is_subscription_active(self):
        """Check if the subscription is currently active."""
        if not self.is_active:
            return False
        if self.status != 'active' and self.status != 'trialing':
            return False
        if self.end_date and self.end_date < timezone.now():
            return False
        return True
    
    def days_remaining(self):
        """Calculate days remaining in the current billing cycle."""
        if not self.end_date:
            return None
        if self.end_date < timezone.now():
            return 0
        delta = self.end_date - timezone.now()
        return delta.days

class UsageTracker(models.Model):
    """Model for tracking usage metrics for a business."""
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='usage_metrics')
    date = models.DateField(default=timezone.now)
    metrics = models.JSONField(default=dict)  # Stores voice_minutes, voice_calls, sms_messages
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('business', 'date')
    
    def __str__(self):
        return f"Usage for {self.business.businessName} on {self.date}"
    
    @classmethod
    def increment_metric(cls, business, metric_name, increment_by=1):
        """Increment a specific usage metric for the business on the current date."""
        today = timezone.now().date()
        usage, created = cls.objects.get_or_create(
            business=business,
            date=today,
            defaults={'metrics': {}}
        )
        
        metrics = usage.metrics
        current_value = metrics.get(metric_name, 0)
        metrics[metric_name] = current_value + increment_by
        usage.metrics = metrics
        usage.save()
        
        return usage
    
    @classmethod
    def get_usage_summary(cls, business, start_date=None, end_date=None):
        """Get a summary of usage metrics for a business within a date range."""
        if not start_date:
            start_date = timezone.now().date().replace(day=1)  # First day of current month
        if not end_date:
            end_date = timezone.now().date()
            
        usage_records = cls.objects.filter(
            business=business,
            date__gte=start_date,
            date__lte=end_date
        )
        
        summary = {
            'voice_minutes': 0,
            'voice_calls': 0,
            'sms_messages': 0
        }
        
        for record in usage_records:
            metrics = record.metrics
            summary['voice_minutes'] += metrics.get('voice_minutes', 0)
            summary['voice_calls'] += metrics.get('voice_calls', 0)
            summary['sms_messages'] += metrics.get('sms_messages', 0)
            
        return summary

class BillingHistory(models.Model):
    """Model for tracking billing history and invoices."""
    STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('pending', 'Pending'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
    ]
    
    business = models.ForeignKey(Business, on_delete=models.CASCADE, related_name='billing_records')
    subscription = models.ForeignKey(BusinessSubscription, on_delete=models.SET_NULL, null=True, related_name='billing_records')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    invoice_url = models.URLField(blank=True, null=True)
    billing_date = models.DateTimeField(default=timezone.now)
    details = models.JSONField(default=dict)  # For storing additional invoice details
    stripe_invoice_id = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Invoice #{self.id} - {self.business.businessName} (${self.amount})"

from django.utils import timezone
from datetime import datetime, timedelta
from subscription.models import UsageTracker

class UsageService:
    """Service class for tracking and retrieving usage metrics."""
    
    @staticmethod
    def track_voice_call(business, duration_seconds=0):
        """
        Track a voice call usage.
        
        Args:
            business: The business making the call
            duration_seconds: Duration of the call in seconds
        """
        # Track call count
        UsageTracker.increment_metric(
            business=business,
            metric_name='voice_calls',
            increment_by=1
        )
        
        # Track call minutes (rounded up to nearest minute)
        minutes = (duration_seconds + 59) // 60  # Round up
        if minutes > 0:
            UsageTracker.increment_metric(
                business=business,
                metric_name='voice_minutes',
                increment_by=minutes
            )
        
        return True
    
    @staticmethod
    def track_sms_message(business, count=1):
        """
        Track SMS message usage.
        
        Args:
            business: The business sending the message
            count: Number of messages to track
        """
        UsageTracker.increment_metric(
            business=business,
            metric_name='sms_messages',
            increment_by=count
        )
        
        return True
    
    @staticmethod
    def get_business_usage(business, start_date=None, end_date=None):
        """
        Get usage metrics for a business within a date range.
        
        Args:
            business: The business to get metrics for
            start_date: Start date for metrics (default: first day of current month)
            end_date: End date for metrics (default: today)
        
        Returns:
            Dict with usage metrics
        """
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()
            
        return UsageTracker.get_usage_summary(
            business=business,
            start_date=start_date,
            end_date=end_date
        )
    
    @staticmethod
    def check_usage_limits(business):
        """
        Check if a business has exceeded its usage limits.
        
        Args:
            business: The business to check
        
        Returns:
            Dict with usage status and limit information
        """
        # Get current subscription
        try:
            from subscription.models import BusinessSubscription
            subscription = BusinessSubscription.objects.filter(
                business=business,
                is_active=True
            ).latest('created_at')
            
            if not subscription or not subscription.is_subscription_active():
                return {
                    'has_active_subscription': False,
                    'limits_exceeded': True,
                    'message': 'No active subscription found.'
                }
            
            # Get current usage
            current_usage = UsageTracker.get_usage_summary(business=business)
            
            # Check limits
            voice_minutes_exceeded = current_usage['voice_minutes'] > subscription.plan.voice_minutes
            voice_calls_exceeded = current_usage['voice_calls'] > subscription.plan.voice_calls
            sms_messages_exceeded = current_usage['sms_messages'] > subscription.plan.sms_messages
            
            limits_exceeded = voice_minutes_exceeded or voice_calls_exceeded or sms_messages_exceeded
            
            return {
                'has_active_subscription': True,
                'limits_exceeded': limits_exceeded,
                'voice_minutes': {
                    'used': current_usage['voice_minutes'],
                    'limit': subscription.plan.voice_minutes,
                    'exceeded': voice_minutes_exceeded
                },
                'voice_calls': {
                    'used': current_usage['voice_calls'],
                    'limit': subscription.plan.voice_calls,
                    'exceeded': voice_calls_exceeded
                },
                'sms_messages': {
                    'used': current_usage['sms_messages'],
                    'limit': subscription.plan.sms_messages,
                    'exceeded': sms_messages_exceeded
                }
            }
            
        except BusinessSubscription.DoesNotExist:
            return {
                'has_active_subscription': False,
                'limits_exceeded': True,
                'message': 'No active subscription found.'
            } 
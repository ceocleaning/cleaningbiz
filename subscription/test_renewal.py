"""
Test script to manually trigger the subscription renewal process.
Run this script to test the auto-renewal functionality without waiting for the scheduled task.
"""

import os
import django
import sys


# Set up Django environment
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'leadsAutomation.settings')
django.setup()

from django.utils import timezone
from datetime import timedelta
from subscription.models import BusinessSubscription
from django.db.models import Q
from subscription.tasks import process_subscription_renewals
from django_q.tasks import schedule
from django_q.models import Schedule

def test_renewal_process():
    """
    Test the subscription renewal process by:
    1. Finding all active subscriptions
    2. Optionally modifying their end dates for testing
    3. Running the renewal process
    """
    print("===== SUBSCRIPTION RENEWAL TEST =====")
    
    # Run the renewal process
    print("\nRunning subscription renewal process...")
    process_subscription_renewals()
    print("Renewal process completed!")

    try:
        
      
        next_run = timezone.now().replace(hour=12, minute=30, second=0, microsecond=0)
        if next_run <= timezone.now():
            next_run += timedelta(days=1)
            
        schedule(
            name='Subscription Renewals',
            func='subscription.tasks.process_subscription_renewals',
            schedule_type='D', 
            next_run=next_run,
            repeats=-1  
        )
            
    except Exception as e:
        print(f"Failed to schedule process_subscription_renewals task: {str(e)}")

if __name__ == "__main__":
    test_renewal_process()

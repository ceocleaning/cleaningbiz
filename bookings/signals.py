# Create a signal when booking is updated
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from invoice.models import Invoice
from django_q.tasks import schedule, Schedule
from datetime import datetime, timedelta
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

@receiver(post_save, sender=Booking)
def create_invoice_for_booking(sender, instance, created, **kwargs):
    """Create an invoice when a new booking is created"""
    if created:
        try:
            # Check if an invoice already exists for this booking
            if not hasattr(instance, 'invoice'):
                # Calculate the total amount from the booking
                total_amount = instance.totalPrice
                
                # Create a new invoice
                invoice = Invoice.objects.create(
                    booking=instance,
                    amount=total_amount,
                )

                # Schedule to Django-Q scheduler
                schedule(
                    'bookings.tasks.send_payment_reminder',  
                    instance.bookingId,  
                    schedule_type='O',
                    next_run=timezone.now() + timedelta(hours=2),
                )
                
                # Check if delete_unpaid_bookings is already scheduled
                schedule_delete_unpaid_bookings()
                
        except Exception as e:
            print(f"[ERROR] Error creating invoice for booking {instance.bookingId}: {str(e)}")


def schedule_delete_unpaid_bookings():
    """
    Check if delete_unpaid_bookings task is already scheduled.
    If not, schedule it to run hourly.
    """
    try:
        # Check if the task is already scheduled
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.delete_unpaid_bookings',
            schedule_type=Schedule.HOURLY
        ).first()
        
        if not existing_schedule:
            # Schedule the task to run hourly
            schedule_id = schedule(
                'bookings.tasks.delete_unpaid_bookings',
                schedule_type='H',  # Hourly
                repeats=-1  # Repeat indefinitely
            )
            print(f"[INFO] Scheduled delete_unpaid_bookings task with ID: {schedule_id}")
        else:
            print(f"[INFO] delete_unpaid_bookings task already scheduled with ID: {existing_schedule.id}")
            
    except Exception as e:
        print(f"[ERROR] Failed to schedule delete_unpaid_bookings task: {str(e)}")


# Connect the signal
post_save.connect(create_invoice_for_booking, sender=Booking)

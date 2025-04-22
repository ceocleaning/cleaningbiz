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

                
                # Schedule recurring tasks if not already scheduled
                schedule_delete_unpaid_bookings()
                schedule_day_before_reminder()
                schedule_hour_before_reminder()
                schedule_post_service_followup()
                
        except Exception as e:
            logger.error(f"Error creating invoice for booking {instance.bookingId}: {str(e)}")


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
            schedule(
                'bookings.tasks.delete_unpaid_bookings',
                schedule_type='H',  # Hourly
                repeats=-1  # Repeat indefinitely
            )
            
    except Exception as e:
        logger.error(f"Failed to schedule delete_unpaid_bookings task: {str(e)}")


def schedule_day_before_reminder():
    try:
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.send_day_before_reminder',
            schedule_type=Schedule.DAILY
        ).first()
        
        if not existing_schedule:
            next_run = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
            if next_run <= timezone.now():
                next_run += timedelta(days=1)
                
            schedule(
                'bookings.tasks.send_day_before_reminder',
                schedule_type='D', 
                next_run=next_run,
                repeats=-1
            )
            
    except Exception as e:
        logger.error(f"Failed to schedule send_day_before_reminder task: {str(e)}")


def schedule_hour_before_reminder():
    try:
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.send_hour_before_reminder',
            schedule_type=Schedule.HOURLY
        ).first()
        
        if not existing_schedule:
            schedule(
                'bookings.tasks.send_hour_before_reminder',
                schedule_type='H', 
                repeats=-1  
            )
            
    except Exception as e:
        logger.error(f"Failed to schedule send_hour_before_reminder task: {str(e)}")


def schedule_post_service_followup():
    try:
        
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.send_post_service_followup',
            schedule_type=Schedule.DAILY
        ).first()
        
        if not existing_schedule:
            next_run = timezone.now().replace(hour=12, minute=0, second=0, microsecond=0)
            if next_run <= timezone.now():
                next_run += timedelta(days=1)
                
            schedule(
                'bookings.tasks.send_post_service_followup',
                schedule_type='D', 
                next_run=next_run,
                repeats=-1  
            )
            
    except Exception as e:
        logger.error(f"Failed to schedule send_post_service_followup task: {str(e)}")


# Connect the signal
post_save.connect(create_invoice_for_booking, sender=Booking)

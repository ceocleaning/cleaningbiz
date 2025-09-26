from django_q.tasks import schedule
from django_q.models import Schedule
from django.utils import timezone

def schedule_recurring_bookings_task():
    """
    Schedule the recurring bookings task to run daily at midnight.
    This function should be called once when the application starts.
    """
    # Check if the schedule already exists
    if not Schedule.objects.filter(func="bookings.tasks.process_recurring_bookings").exists():
        # Schedule the function to run daily at midnight
        midnight = timezone.localtime(timezone.now()).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        
        schedule(
            "bookings.tasks.process_recurring_bookings",
            schedule_type=Schedule.DAILY,
            next_run=midnight,
            repeats=-1,  # Run indefinitely
        )
        print("Scheduled process_recurring_bookings task to run daily at midnight")

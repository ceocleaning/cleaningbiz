from django.core.management.base import BaseCommand
from bookings.tasks import process_recurring_bookings

class Command(BaseCommand):
    help = 'Runs the process_recurring_bookings task directly.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('--- Running process_recurring_bookings task ---'))
        try:
            bookings_created_count = process_recurring_bookings()
            self.stdout.write(self.style.SUCCESS(f'--- Task finished. Bookings created: {bookings_created_count} ---'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'An error occurred while running the task: {e}'))

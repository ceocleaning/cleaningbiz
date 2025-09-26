from django.core.management.base import BaseCommand
from automation.tasks import check_booking_cleaner_assignment


class Command(BaseCommand):
    help = 'Manually run the booking cleaner assignment check task'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting booking cleaner assignment check...'))
        result = check_booking_cleaner_assignment()
        if result == 0:
            self.stdout.write(self.style.SUCCESS('Successfully completed booking cleaner assignment check'))
        else:
            self.stdout.write(self.style.ERROR('Error running booking cleaner assignment check'))

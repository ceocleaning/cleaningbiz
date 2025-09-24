from django.core.management.base import BaseCommand
from notification.tasks import process_pending_notifications, clean_old_notifications

class Command(BaseCommand):
    help = 'Process pending notifications and clean up old ones'

    def add_arguments(self, parser):
        parser.add_argument(
            '--max',
            type=int,
            default=100,
            help='Maximum number of notifications to process in one batch'
        )
        parser.add_argument(
            '--clean',
            action='store_true',
            help='Clean up old read notifications'
        )
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days to keep read notifications'
        )

    def handle(self, *args, **options):
        max_count = options['max']
        
        self.stdout.write(f"Processing up to {max_count} pending notifications...")
        process_pending_notifications(max_count)
        self.stdout.write(self.style.SUCCESS("Finished processing notifications"))
        
        if options['clean']:
            days = options['days']
            self.stdout.write(f"Cleaning up notifications older than {days} days...")
            count = clean_old_notifications(days)
            self.stdout.write(self.style.SUCCESS(f"Deleted {count} old notifications"))

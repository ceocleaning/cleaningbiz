from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, User
from accounts.models import Business, CleanerProfile

class Command(BaseCommand):
    help = 'Assigns users to Owner or Cleaner groups based on their roles'

    def handle(self, *args, **options):
        self.stdout.write('Starting to assign users to groups...')
        
        # Create groups if they don't exist
        owner_group, created = Group.objects.get_or_create(name='Owner')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Owner group'))
        
        cleaner_group, created = Group.objects.get_or_create(name='Cleaner')
        if created:
            self.stdout.write(self.style.SUCCESS('Created Cleaner group'))
        
        # Assign business owners to Owner group
        owners_count = 0
        for business in Business.objects.all():
            if business.user and not business.user.groups.filter(name='Owner').exists():
                business.user.groups.add(owner_group)
                owners_count += 1
                self.stdout.write(f'Assigned user {business.user.username} to Owner group')
        
        # Assign cleaners to Cleaner group
        cleaners_count = 0
        for cleaner_profile in CleanerProfile.objects.all():
            if cleaner_profile.user and not cleaner_profile.user.groups.filter(name='Cleaner').exists():
                cleaner_profile.user.groups.add(cleaner_group)
                cleaners_count += 1
                self.stdout.write(f'Assigned user {cleaner_profile.user.username} to Cleaner group')
        
        # Check superusers - optionally assign them to Owner group if they don't have a role
        for user in User.objects.filter(is_superuser=True):
            if not user.groups.exists():
                user.groups.add(owner_group)
                owners_count += 1
                self.stdout.write(f'Assigned superuser {user.username} to Owner group')
        
        # Summary
        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {owners_count} users to Owner group'))
        self.stdout.write(self.style.SUCCESS(f'Successfully assigned {cleaners_count} users to Cleaner group'))
        self.stdout.write(self.style.SUCCESS('Done!')) 
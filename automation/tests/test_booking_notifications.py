from django.test import TestCase
from django.utils import timezone
from datetime import timedelta
from unittest.mock import patch, MagicMock
from automation.tasks import check_booking_cleaner_assignment
from automation.models import OpenJob, BookingNotificationTracker
from bookings.models import Booking
from accounts.models import Business, User, CleanerProfile
from customer.models import Customer


class BookingNotificationTests(TestCase):
    def setUp(self):
        # Create test user
        self.user = User.objects.create_user(
            username='testuser',
            email='test@example.com',
            password='testpassword'
        )
        
        # Create test business
        self.business = Business.objects.create(
            user=self.user,
            businessName='Test Business',
            email='business@example.com'
        )
        
        # Create test customer
        self.customer = Customer.objects.create(
            business=self.business,
            first_name='Test',
            last_name='Customer',
            email='customer@example.com'
        )
        
        # Create test booking (6 hours from now)
        start_time = timezone.now() + timedelta(hours=6)
        self.booking = Booking.objects.create(
            business=self.business,
            customer=self.customer,
            cleaningDate=start_time.date(),
            startTime=start_time.time(),
            serviceType='standard'
        )
        
        # Mock the is_paid method to return True
        self.booking.is_paid = MagicMock(return_value=True)
        
    @patch('automation.tasks.NotificationService.send_notification')
    def test_check_booking_cleaner_assignment(self, mock_send_notification):
        # Create open job for the booking
        open_job = OpenJob.objects.create(
            booking=self.booking,
            cleaner=CleanerProfile.objects.create(user=self.user),
            status='pending'
        )
        
        # Run the task
        check_booking_cleaner_assignment()
        
        # Check that notification was sent
        mock_send_notification.assert_called_once()
        
        # Check that tracker was created
        tracker = BookingNotificationTracker.objects.filter(
            booking=self.booking,
            notification_type='cleaner_assignment_check'
        )
        self.assertTrue(tracker.exists())
        
        # Run the task again
        check_booking_cleaner_assignment()
        
        # Check that notification was only sent once (no additional calls)
        mock_send_notification.assert_called_once()

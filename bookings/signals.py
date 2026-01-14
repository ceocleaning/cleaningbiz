# Create a signal when booking is updated
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from invoice.models import Invoice
from django_q.tasks import schedule, Schedule
from datetime import datetime, timedelta
from django.utils import timezone
from django.conf import settings
import requests
import stripe
import json
from base64 import b64encode
from square.client import Client


@receiver(post_save, sender=Booking)
def capture_payment_on_completion(sender, instance, created, **kwargs):
    """Capture authorized payment when booking is marked as completed"""
    if not created and instance.isCompleted:
        try:
            invoice = getattr(instance, 'invoice', None)
            if not invoice:
                return

            authorized_payments = invoice.payments.filter(status='AUTHORIZED')
            
            for payment in authorized_payments:
                if payment.paymentMethod == 'Square':
                    capture_square_payment(payment)
                elif payment.paymentMethod == 'Stripe':
                    capture_stripe_payment(payment)
                elif payment.paymentMethod == 'PayPal':
                    capture_paypal_payment(payment)
                    
        except Exception as e:
            print(f"Error capturing payment for booking {instance.bookingId}: {str(e)}")


def capture_square_payment(payment):
    """Capture a Square authorized payment"""
    try:
        business = payment.invoice.booking.business
        creds = business.square_credentials
        
        client = Client(
            access_token=creds.access_token,
            environment='sandbox' if settings.DEBUG else 'production'
        )
        
        result = client.payments.complete_payment(
            payment_id=payment.squarePaymentId,
            body={}
        )
        
        if result.is_success():
            payment.status = 'COMPLETED'
            payment.paidAt = timezone.now()
            payment.save()
            payment.invoice.update_payment_status()
            print(f"Square payment {payment.paymentId} captured successfully")
        else:
            print(f"Failed to capture Square payment {payment.paymentId}: {result.errors}")
            
    except Exception as e:
        print(f"Exception capturing Square payment {payment.paymentId}: {str(e)}")


def capture_stripe_payment(payment):
    """Capture a Stripe authorized payment"""
    try:
        business = payment.invoice.booking.business
        creds = business.stripe_credentials
        
        stripe.api_key = creds.stripe_secret_key
        
        payment_intent = stripe.PaymentIntent.capture(
            payment.transactionId,
            amount_to_capture=int(payment.amount * 100)
        )
        
        if payment_intent.status == 'succeeded':
            payment.status = 'COMPLETED'
            payment.paidAt = timezone.now()
            payment.save()
            payment.invoice.update_payment_status()
            print(f"Stripe payment {payment.paymentId} captured successfully")
        else:
            print(f"Stripe capture status: {payment_intent.status} for payment {payment.paymentId}")
            
    except Exception as e:
        print(f"Exception capturing Stripe payment {payment.paymentId}: {str(e)}")


def capture_paypal_payment(payment):
    """Capture a PayPal authorized payment"""
    try:
        business = payment.invoice.booking.business
        creds = business.paypal_credentials
        
        # Determine environment (sandbox or production)
        base_url = 'https://api-m.sandbox.paypal.com' if settings.DEBUG else 'https://api-m.paypal.com'
        
        # Get OAuth token
        auth = b64encode(f"{creds.paypal_client_id}:{creds.paypal_secret_key}".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        token_response = requests.post(
            f"{base_url}/v1/oauth2/token",
            headers=headers,
            data="grant_type=client_credentials"
        )
        
        if token_response.status_code != 200:
            print(f"PayPal OAuth failed for payment {payment.paymentId}")
            return

        access_token = token_response.json()['access_token']
        
        # Capture the authorization
        # If transactionId stores the order ID, we might need to capture the order
        # If it stores the authorization ID, we capture the authorization
        # Based on payment_views.py logic, it seems they store order_id in transactionId
        
        capture_headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Try to capture Order first
        capture_url = f"{base_url}/v2/checkout/orders/{payment.transactionId}/capture"
        response = requests.post(capture_url, headers=capture_headers)
        
        if response.status_code in [200, 201]:
            payment.status = 'COMPLETED'
            payment.paidAt = timezone.now()
            payment.save()
            payment.invoice.update_payment_status()
            print(f"PayPal payment {payment.paymentId} captured successfully")
        else:
            # Maybe it's an authorization ID instead of an Order ID?
            auth_capture_url = f"{base_url}/v2/payments/authorizations/{payment.transactionId}/capture"
            auth_response = requests.post(auth_capture_url, headers=capture_headers, json={})
            
            if auth_response.status_code in [200, 201]:
                payment.status = 'COMPLETED'
                payment.paidAt = timezone.now()
                payment.save()
                payment.invoice.update_payment_status()
                print(f"PayPal authorization {payment.paymentId} captured successfully")
            else:
                print(f"Failed to capture PayPal payment {payment.paymentId}. Order API: {response.status_code}, Auth API: {auth_response.status_code}")
                
    except Exception as e:
        print(f"Exception capturing PayPal payment {payment.paymentId}: {str(e)}")


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
            print(f"Error creating invoice for booking {instance.bookingId}: {str(e)}")


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
        print(f"Failed to schedule delete_unpaid_bookings task: {str(e)}")


def schedule_day_before_reminder():
    try:
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.send_day_before_reminder'
        ).first()
        
        if not existing_schedule:
            next_run = timezone.now().replace(hour=10, minute=0, second=0, microsecond=0)
            if next_run <= timezone.now():
                next_run += timedelta(days=1)
                
            schedule(
                'bookings.tasks.send_day_before_reminder',
                schedule_type=Schedule.DAILY, 
                repeats=-1,
                next_run=next_run
            )
            
    except Exception as e:
        print(f"Failed to schedule send_day_before_reminder task: {str(e)}")


def schedule_hour_before_reminder():
    try:
        existing_schedule = Schedule.objects.filter(
            func='bookings.tasks.send_hour_before_reminder'
        ).first()
        
        if not existing_schedule:
            schedule(
                'bookings.tasks.send_hour_before_reminder',
                schedule_type=Schedule.DAILY, 
                repeats=-1,
                next_run=timezone.now() + timedelta(minutes=60)
            )
            
    except Exception as e:
        print(f"Failed to schedule send_hour_before_reminder task: {str(e)}")


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
        print(f"Failed to schedule send_post_service_followup task: {str(e)}")


# Connect the signal

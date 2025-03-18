# Create a signal when booking is updated
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Booking
from invoice.models import Invoice


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
                    amount=total_amount
                )
                print(f"[DEBUG] Created invoice {invoice.invoiceId} for booking {instance.bookingId}")
        except Exception as e:
            print(f"[ERROR] Error creating invoice for booking {instance.bookingId}: {str(e)}")


# Connect the signal
post_save.connect(create_invoice_for_booking, sender=Booking)

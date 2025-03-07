from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.contrib import messages
import datetime
import json
import uuid
from square.client import Client
from .models import Invoice, Payment

@require_http_methods(["POST"])
def process_payment(request, invoiceId):
    """Process a Square payment for an invoice"""
    try:
        # Get the invoice
        invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
        
        # Parse the request body
        data = json.loads(request.body)
        source_id = data.get('sourceId')
        
        if not source_id:
            return JsonResponse({'success': False, 'error': 'No payment source provided'}, status=400)

        # Initialize Square client
        client = Client(
            access_token=settings.SQUARE_ACCESS_TOKEN,
            environment='sandbox'  # Change to 'production' for live payments
        )

        # Create unique idempotency key using timestamp and UUID
        idempotency_key = f"INVOICE_{invoice.invoiceId}_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

        # Create the payment
        payment_api = client.payments
        result = payment_api.create_payment(
            body={
                "source_id": source_id,
                "amount_money": {
                    "amount": int(invoice.amount * 100),  # Convert to cents
                    "currency": "USD"
                },
                "idempotency_key": idempotency_key,
                "note": f"Payment for invoice {invoice.invoiceId}"
            }
        )

        if result.is_success():
            # Save payment details
            payment = Payment.objects.create(
                invoice=invoice,
                amount=invoice.amount,
                paymentMethod='Square',
                squarePaymentId=result.body['payment']['id'],
                paidAt=datetime.datetime.now()
            )
            
            # Mark invoice as paid
            invoice.isPaid = True
            invoice.save()

            return JsonResponse({
                'success': True,
                'payment_id': payment.paymentId
            })
        else:
            # Get error message from Square response
            error_message = "Payment processing failed"
            if result.errors:
                error = result.errors[0]
                error_message = error.get('detail', error.get('category', 'Unknown error occurred'))
            
            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=400)

    except Exception as e:
        # Log the error for debugging
        print(f"Payment processing error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while processing your payment. Please try again.'
        }, status=500)
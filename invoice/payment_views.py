from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_http_methods
from django.conf import settings
from django.utils import timezone
import json
import uuid
from square.client import Client
from .models import Invoice, Payment
from accounts.models import Business, SquareCredentials, PayPalCredentials
from .utils import handle_payment_completed
import threading
from decimal import Decimal



# SQUARE PAYMENT VIEWS
@require_http_methods(["POST"])
def process_payment(request):
    """Process a Square payment for an invoice with option to authorize only or make partial payment"""
    try:
        # Parse the request body
        data = json.loads(request.body)
        source_id = data.get('sourceId')
        invoice_id = data.get('invoiceId')
        auto_complete = data.get('autoComplete', True)
        payment_type = data.get('paymentType', 'full')  # 'full' or 'partial'
        amount = Decimal(str(data.get('amount', 0)))  # Amount for partial payment
        tip_amount = Decimal(str(data.get('tipAmount', 0)))  # Tip amount

        # Get the invoice
        invoice = get_object_or_404(Invoice, invoiceId=invoice_id)
        business = invoice.booking.business
        square_credentials = business.square_credentials

        if not source_id:
            return JsonResponse({'success': False, 'error': 'No payment source provided'}, status=400)

        # Determine payment amount based on payment type
        if payment_type == 'partial':
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid payment amount'
                }, status=400)
            
            # Check if amount is greater than remaining amount
            if invoice.is_partially_paid():
                remaining_amount = invoice.get_remaining_amount()
                if amount > remaining_amount:
                    return JsonResponse({
                        'success': False,
                        'error': f'Payment amount exceeds remaining balance of ${remaining_amount}'
                    }, status=400)
            elif amount > invoice.amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Payment amount exceeds invoice total of ${invoice.amount}'
                }, status=400)
            
            payment_amount = amount
        else:  # full payment
            if invoice.is_partially_paid():
                payment_amount = invoice.get_remaining_amount()
            else:
                payment_amount = invoice.amount

        # Initialize Square client
        client = Client(
            access_token=square_credentials.access_token,
            environment='sandbox' if settings.DEBUG else 'production'
        )

        # Create unique idempotency key
        idempotency_key = f"INVOICE_{invoice.invoiceId}_{timezone.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

        # For partial payments, we need to handle tips differently
        # Tips should be paid in full with the first payment
        total_charge_amount = payment_amount
        
        # Only add tip if this is not a subsequent partial payment
        if not (payment_type == 'partial' and invoice.is_partially_paid()):
            total_charge_amount += tip_amount
        
        # Prepare payment body
        payment_body = {
            "source_id": source_id,
            "amount_money": {
                "amount": int(total_charge_amount * 100),  # Convert to cents
                "currency": "USD"
            },
            "idempotency_key": idempotency_key,
            "note": f"{payment_type.capitalize()} payment for invoice {invoice.invoiceId}{' with tip' if tip_amount > 0 else ''}",
            "autocomplete": auto_complete  # This controls whether payment is completed immediately
        }

        # Create the payment
        payment_api = client.payments
        result = payment_api.create_payment(body=payment_body)

        if result.is_success():
            payment_data = result.body['payment']

            # If tip amount is provided, update the booking using TipService
            booking = invoice.booking
            if tip_amount > 0:
                from .services import TipService
                
                # Convert to Decimal for precision
                tip_decimal = Decimal(str(tip_amount))
                
                # Validate tip amount
                invoice_amount = Decimal(str(invoice.amount / 100))  # Convert from cents to dollars
                is_valid, error_message = TipService.validate_tip_amount(tip_decimal, invoice_amount)
                
                if not is_valid:
                    return JsonResponse({
                        'success': False,
                        'error': f'Invalid tip amount: {error_message}'
                    }, status=400)
                
                # Add tip to booking using service
                booking, invoice = TipService.add_tip_to_booking(booking, tip_decimal)
            
            # Create payment record without timezone conversion
            payment = Payment.objects.create(
                invoice=invoice,
                amount=total_charge_amount,  # Use total_charge_amount which includes tip
                paymentMethod='Square',
                squarePaymentId=payment_data['id'],
                status='COMPLETED' if auto_complete else 'AUTHORIZED',
                payment_type=payment_type
            )

            # Only mark invoice as paid if payment is completed
            if auto_complete:
                payment.paidAt = timezone.now()
                # Update invoice payment status
                invoice.update_payment_status()
            
            payment_thread = threading.Thread(target=handle_payment_completed, args=(payment,))
            payment_thread.daemon = True
            payment_thread.start()
            
            return JsonResponse({
                'success': True,
                'payment_id': payment.paymentId,
                'status': payment_data['status'],
                'payment_type': payment_type
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



@require_http_methods(["POST"])
def process_manual_payment(request):
    """Process payments (Square, Cash, Bank Transfer) for an invoice"""
    try:
        data = json.loads(request.body)
        invoice_id = data.get('invoiceId')
        payment_method = data.get('paymentMethod')
        amount = Decimal(str(data.get('amount', 0)))
        transaction_id = data.get('transactionId')
        square_payment_id = data.get('squarePaymentId')

        # Validate required fields
        if not all([invoice_id, payment_method, amount]):
            return JsonResponse({
                'success': False,
                'error': 'Missing required fields'
            }, status=400)

        # Get the invoice
        invoice = get_object_or_404(Invoice, invoiceId=invoice_id)
        business = invoice.booking.business
        square_credentials = SquareCredentials.objects.filter(business=business).first()

        # Check if this is an existing Square payment with AUTHORIZED status
        if payment_method == 'Square' and square_payment_id:
            try:
                # Find the existing payment
                payment = Payment.objects.get(invoice=invoice, squarePaymentId=square_payment_id, status='AUTHORIZED')

                # Initialize Square client
                client = Client(
                    access_token=square_credentials.access_token,
                    environment='sandbox' if settings.DEBUG else 'production'
                )

                # Complete the payment in Square
                result = client.payments.complete_payment(
                    payment_id=payment.squarePaymentId,
                    body={}
                )

                if result.is_success():
                    # Update payment status
                    payment.status = 'COMPLETED'
                    payment.paidAt = timezone.now()
                    payment.save()

                    # Mark invoice as paid
                    invoice.isPaid = True
                    invoice.save()

                    return JsonResponse({
                        'success': True,
                        'message': 'Square payment completed successfully'
                    })
                else:
                    error_message = "Payment completion failed"
                    if result.errors:
                        error = result.errors[0]
                        error_message = error.get('detail', error.get('category', 'Unknown error occurred'))

                    return JsonResponse({
                        'success': False,
                        'error': error_message
                    }, status=400)
            except Payment.DoesNotExist:
                # If payment doesn't exist, continue with creating a new payment
                pass
            except Exception as e:
                print(f"Square payment completion error: {str(e)}")
                return JsonResponse({
                    'success': False,
                    'error': f'Error completing Square payment: {str(e)}'
                }, status=500)

        # Create payment record
        payment = Payment.objects.create(
            invoice=invoice,
            amount=amount,
            paymentMethod=payment_method,
            transactionId=transaction_id if payment_method == 'Bank Transfer' else None,
            squarePaymentId=square_payment_id if payment_method == 'Square' else None,
            status='COMPLETED',
            paidAt=timezone.now()
        )

        # Mark invoice as paid
        invoice.isPaid = True
        invoice.save()

        payment_thread = threading.Thread(target=handle_payment_completed, args=(payment,))
        payment_thread.daemon = True
        payment_thread.start()

        return JsonResponse({
            'success': True,
            'message': f'{payment_method} payment processed successfully'
        })

    except Exception as e:
        print(f"Payment processing error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while processing the payment.'
        }, status=500)




# STRIPE PAYMENT VIEWS
@require_http_methods(["POST"])
def process_stripe_payment(request):
    """Process a Stripe payment for an invoice with option to authorize only or make partial payment"""
    try:
        # Parse the request body
        data = json.loads(request.body)
        payment_method_id = data.get('payment_method_id')
        invoice_id = data.get('invoice_id')
        auto_complete = data.get('auto_complete', True)
        payment_type = data.get('payment_type', 'full')  # 'full' or 'partial'
        amount = Decimal(str(data.get('amount', 0)))  # Amount for partial payment
        tip_amount = Decimal(str(data.get('tip_amount', 0)))  # Tip amount

        print("Tip amount:", tip_amount)
        # Get the invoice
        invoice = get_object_or_404(Invoice, invoiceId=invoice_id)
        business = invoice.booking.business

        # Get Stripe credentials
        try:
            stripe_credentials = business.stripe_credentials
        except:
            return JsonResponse({
                'success': False,
                'error': 'Stripe credentials not found for this business'
            }, status=400)

        if not payment_method_id:
            return JsonResponse({
                'success': False,
                'error': 'No payment method provided'
            }, status=400)

        # Determine payment amount based on payment type
        if payment_type == 'partial':
            if amount <= 0:
                return JsonResponse({
                    'success': False,
                    'error': 'Invalid payment amount'
                }, status=400)
            
            # Check if amount is greater than remaining amount
            if invoice.is_partially_paid():
                remaining_amount = invoice.get_remaining_amount()
                if amount > remaining_amount:
                    return JsonResponse({
                        'success': False,
                        'error': f'Payment amount exceeds remaining balance of ${remaining_amount}'
                    }, status=400)
            elif amount > invoice.amount:
                return JsonResponse({
                    'success': False,
                    'error': f'Payment amount exceeds invoice total of ${invoice.amount}'
                }, status=400)
            
            payment_amount = amount
        else:  # full payment
            if invoice.is_partially_paid():
                payment_amount = invoice.get_remaining_amount()
            else:
                payment_amount = invoice.amount

        import stripe
        stripe.api_key = stripe_credentials.stripe_secret_key

        idempotency_key = f"invoice_{invoice.invoiceId}_{timezone.now().strftime('%Y%m%d%H%M%S')}_{str(uuid.uuid4())[:8]}"

        try:
            # For partial payments, we need to handle tips differently
            # Tips should be paid in full with the first payment
            total_charge_amount = payment_amount
            
            # Only add tip if this is not a subsequent partial payment
            if not (payment_type == 'partial' and invoice.is_partially_paid()):
                total_charge_amount += tip_amount
            
            print("Payment type:", payment_type)
            print("Invoice is partially paid:", invoice.is_partially_paid())
            print("Total charge amount:", total_charge_amount)
            print("Tip amount:", tip_amount)
            print("Payment amount:", payment_amount)

            amount_in_cents = int(total_charge_amount * 100)

            if auto_complete:
                payment_intent = stripe.PaymentIntent.create(
                    amount=amount_in_cents,
                    currency='usd',
                    payment_method=payment_method_id,
                    confirm=True,
                    description=f"{payment_type.capitalize()} payment for invoice {invoice.invoiceId}",
                    metadata={
                        'invoice_id': invoice.invoiceId,
                        'business_id': business.businessId,
                        'payment_type': payment_type
                    },
                    idempotency_key=idempotency_key,
                    automatic_payment_methods={
                        'enabled': True,
                        'allow_redirects': 'never'
                    }
                )

                if payment_intent.status == 'succeeded':
                    # If tip amount is provided, update the booking using TipService
                    booking = invoice.booking
                    if tip_amount > 0:
                        from .services import TipService
                        
                        # Convert to Decimal for precision
                        tip_decimal = Decimal(tip_amount)
                        
                        # Validate tip amount
                        invoice_amount = Decimal(invoice.amount)
                        is_valid, error_message = TipService.validate_tip_amount(tip_decimal, invoice_amount)
                        
                        if not is_valid:
                            return JsonResponse({
                                'success': False,
                                'error': f'Invalid tip amount: {error_message}'
                            }, status=400)
                        
                        # Add tip to booking using service
                        booking, invoice = TipService.add_tip_to_booking(booking, tip_decimal)
                    
                    payment = Payment.objects.create(
                        invoice=invoice,
                        amount=total_charge_amount,
                        paymentMethod='Stripe',
                        transactionId=payment_intent.id,
                        status='COMPLETED',
                        paidAt=timezone.now(),
                        payment_type=payment_type
                    )

                    # Update invoice payment status
                    invoice.update_payment_status()

                    payment_thread = threading.Thread(target=handle_payment_completed, args=(payment,))
                    payment_thread.daemon = True
                    payment_thread.start()

                    return JsonResponse({
                        'success': True,
                        'payment_id': payment.paymentId,
                        'status': 'COMPLETED',
                        'payment_type': payment_type
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f'Payment failed. Status: {payment_intent.status}'
                    }, status=400)

            else:  # Authorize only
                # For authorization, we always use the full remaining amount
                if invoice.is_partially_paid():
                    auth_amount = invoice.get_remaining_amount()
                    # For subsequent partial payments, don't include tip
                    auth_amount_with_tip = auth_amount
                else:
                    auth_amount = invoice.amount
                    # Include tip in the authorization amount
                    auth_amount_with_tip = auth_amount + tip_amount
                
                print("Authorization amount:", auth_amount)
                print("Tip amount for authorization:", tip_amount)
                print("Total authorization amount with tip:", auth_amount_with_tip)
                
                auth_amount_in_cents = int(auth_amount_with_tip * 100)
                
                payment_intent = stripe.PaymentIntent.create(
                    amount=auth_amount_in_cents,
                    currency='usd',
                    payment_method=payment_method_id,
                    confirmation_method='manual',
                    capture_method='manual',
                    confirm=True,
                    payment_method_types=["card"],
                    description=f"Authorization for invoice {invoice.invoiceId}",
                    metadata={
                        'invoice_id': invoice.invoiceId,
                        'business_id': business.businessId
                    },
                    idempotency_key=idempotency_key
                )

                print("Payment intent created successfully")
                print(payment_intent)

                if payment_intent.status in ['requires_capture', 'succeeded']:
                    # If tip amount is provided, update the booking using TipService
                    booking = invoice.booking
                    if tip_amount > 0 and not invoice.is_partially_paid():
                        from .services import TipService
                        
                        # Convert to Decimal for precision
                        tip_decimal = Decimal(tip_amount)
                        
                        # Validate tip amount
                        invoice_amount = Decimal(invoice.amount)
                        is_valid, error_message = TipService.validate_tip_amount(tip_decimal, invoice_amount)
                        
                        if not is_valid:
                            return JsonResponse({
                                'success': False,
                                'error': f'Invalid tip amount: {error_message}'
                            }, status=400)
                        
                        # Add tip to booking using service
                        booking, invoice = TipService.add_tip_to_booking(booking, tip_decimal)
                    
                    payment = Payment.objects.create(
                        invoice=invoice,
                        amount=auth_amount_with_tip,  # Use amount with tip
                        paymentMethod='Stripe',
                        transactionId=payment_intent.id,
                        status='AUTHORIZED',
                        payment_type='authorized'
                    )

                    print("Payment authorized successfully")
                    print("Adding handle_payment_completed thread")
                    payment_thread = threading.Thread(target=handle_payment_completed, args=(payment,))
                    payment_thread.daemon = True
                    payment_thread.start()

                    return JsonResponse({
                        'success': True,
                        'payment_id': payment.paymentId,
                        'status': 'AUTHORIZED'
                    })
                else:
                    return JsonResponse({
                        'success': False,
                        'error': f'Authorization failed. Status: {payment_intent.status}'
                    }, status=400)

        except stripe.error.CardError as e:
            error_message = e.error.message
            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=400)
        except stripe.error.StripeError as e:
            return JsonResponse({
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }, status=400)

    except Exception as e:
        print(f"Stripe payment processing error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while processing your payment. Please try again.'
        }, status=500)


@require_http_methods(["POST"])
def capture_stripe_payment(request):
    try:
        data = json.loads(request.body)
        payment_id = data.get('payment_id')

        payment = get_object_or_404(Payment, paymentId=payment_id, status='AUTHORIZED')
        invoice = payment.invoice
        business = invoice.booking.business

        try:
            stripe_credentials = business.stripe_credentials
        except:
            return JsonResponse({
                'success': False,
                'error': 'Stripe credentials not found for this business'
            }, status=400)

        # Import Stripe
        import stripe

        # Set the Stripe API key
        stripe.api_key = stripe_credentials.stripe_secret_key

        try:
            payment_intent = stripe.PaymentIntent.capture(
                payment.transactionId,
                amount_to_capture=int(payment.amount * 100)
            )

            if payment_intent.status == 'succeeded':
                payment.status = 'COMPLETED'
                payment.paidAt = timezone.now()
                payment.save()

                invoice.isPaid = True
                invoice.save()

                return JsonResponse({
                    'success': True,
                    'message': 'Payment captured successfully'
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': f'Payment capture failed. Status: {payment_intent.status}'
                }, status=400)

        except stripe.error.StripeError as e:
            return JsonResponse({
                'success': False,
                'error': f'Stripe error: {str(e)}'
            }, status=400)

    except Exception as e:
        print(f"Stripe payment capture error: {str(e)}")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while capturing the payment.'
        }, status=500)


# PAYPAL PAYMENT VIEWS
@require_http_methods(["POST"])
def process_paypal_payment(request):
    """Process a PayPal payment for an invoice with support for partial payments"""
    print("\n\n===== PAYPAL PAYMENT PROCESSING STARTED =====")
    try:
        # Parse the request body
        data = json.loads(request.body)
        order_id = data.get('orderID')
        invoice_id = data.get('invoiceId')
        manual_verification = data.get('manualVerification', False)
        payment_type = data.get('paymentType', 'full')  # 'full' or 'partial'
        tip_amount = Decimal(str(data.get('tipAmount', 0)))  # Tip amount
        print(f"PayPal payment request received - Order ID: {order_id}, Invoice ID: {invoice_id}, Manual: {manual_verification}, Type: {payment_type}")

        # Get the invoice
        invoice = get_object_or_404(Invoice, invoiceId=invoice_id)
        business = invoice.booking.business
        print(f"Invoice found - Amount: ${invoice.amount}, Business: {business.businessName}")

        # Get PayPal credentials
        try:
            paypal_credentials = business.paypal_credentials
            print(f"PayPal credentials found for business - Client ID: {paypal_credentials.paypal_client_id}")
        except Exception as cred_error:
            print(f"PayPal credentials error: {str(cred_error)}")
            return JsonResponse({
                'success': False,
                'error': 'PayPal credentials not found for this business'
            }, status=400)

        if not order_id:
            return JsonResponse({
                'success': False,
                'error': 'No PayPal order ID provided'
            }, status=400)

        # Verify payment with PayPal API
        import requests
        from base64 import b64encode

        # Determine environment (sandbox or production)
        base_url = 'https://api-m.sandbox.paypal.com' if settings.DEBUG else 'https://api-m.paypal.com'
        print(f"Using PayPal API URL: {base_url} (DEBUG={settings.DEBUG})")
        
        # Get OAuth token
        auth = b64encode(f"{paypal_credentials.paypal_client_id}:{paypal_credentials.paypal_secret_key}".encode()).decode()
        headers = {
            'Authorization': f'Basic {auth}',
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        # Get access token
        print("Requesting PayPal OAuth token...")
        token_response = requests.post(
            f"{base_url}/v1/oauth2/token",
            headers=headers,
            data="grant_type=client_credentials"
        )
        
        print(f"PayPal OAuth response status: {token_response.status_code}")
        if token_response.status_code != 200:
            error_details = token_response.text
            print(f"PayPal OAuth error: {error_details}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to authenticate with PayPal API'
            }, status=500)
            
        token_data = token_response.json()
        access_token = token_data['access_token']
        print(f"PayPal OAuth token obtained successfully. Token type: {token_data.get('token_type', 'unknown')}")
        
        # Verify order details
        order_headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        print(f"Verifying PayPal order {order_id}...")
        order_response = requests.get(
            f"{base_url}/v2/checkout/orders/{order_id}",
            headers=order_headers
        )
        
        print(f"PayPal order verification response status: {order_response.status_code}")
        if order_response.status_code != 200:
            error_details = order_response.text
            print(f"PayPal order verification error: {error_details}")
            return JsonResponse({
                'success': False,
                'error': 'Failed to verify order with PayPal'
            }, status=500)
            
        order_data = order_response.json()
        print(f"PayPal order data received - Status: {order_data.get('status', 'unknown')}")
        
        # Verify payment status
        order_status = order_data.get('status', 'unknown')
        print(f"Verifying PayPal payment status: {order_status}")
        
        # If this is a manual verification and the status is APPROVED, we'll accept it
        # This handles cases where the client-side capture failed but payment was actually processed
        if order_status != 'COMPLETED':
            if manual_verification and order_status == 'APPROVED':
                print(f"Manual verification: Accepting APPROVED status as valid for order {order_id}")
                # Continue processing as if completed
            else:
                print(f"Payment not completed. Current status: {order_status}")
                return JsonResponse({
                    'success': False,
                    'error': f'Payment not completed. Current status: {order_status}'
                }, status=400)
            
        # Verify payment amount
        try:
            payment_units = order_data['purchase_units'][0]
            payment_amount = Decimal(str(payment_units['amount']['value']))
            payment_currency = payment_units['amount']['currency_code']
            
            # Determine expected amount based on payment type
            if payment_type == 'partial':
                # For partial payments, we just verify the amount is not more than the invoice total
                # or remaining amount if partially paid
                if invoice.is_partially_paid():
                    remaining_amount = invoice.get_remaining_amount()
                    if payment_amount > remaining_amount:
                        print(f"Payment amount exceeds remaining balance - Received: ${payment_amount}, Remaining: ${remaining_amount}")
                        return JsonResponse({
                            'success': False,
                            'error': f'Payment amount exceeds remaining balance of ${remaining_amount}'
                        }, status=400)
                elif payment_amount > invoice.amount:
                    print(f"Payment amount exceeds invoice total - Received: ${payment_amount}, Total: ${invoice.amount}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Payment amount exceeds invoice total of ${invoice.amount}'
                    }, status=400)
                expected_amount = payment_amount  # The amount sent is what we expect
            else:  # full payment
                if invoice.is_partially_paid():
                    expected_amount = invoice.get_remaining_amount()
                else:
                    expected_amount = invoice.amount
                
                # For partial payments, we need to handle tips differently
                # Tips should be paid in full with the first payment
                if payment_type == 'partial' and invoice.is_partially_paid():
                    # For subsequent partial payments, don't expect tip
                    expected_amount_with_tip = expected_amount
                else:
                    # For first payment or full payment, include tip
                    expected_amount_with_tip = expected_amount + tip_amount
                
                # Allow for small rounding differences (within 1 cent)
                if abs(payment_amount - expected_amount_with_tip) > Decimal('0.01'):
                    print(f"Payment amount mismatch - Expected: ${expected_amount_with_tip} (including ${tip_amount} tip), Received: ${payment_amount}")
                    return JsonResponse({
                        'success': False,
                        'error': f'Payment amount mismatch. Expected: ${expected_amount_with_tip} (including ${tip_amount} tip), Received: ${payment_amount}'
                    }, status=400)
            
            print(f"Payment amount verification successful - Amount: ${payment_amount}")
        except (KeyError, IndexError) as e:
            print(f"Could not verify payment amount: {str(e)}")
            print(f"Order data structure: {order_data}")
            return JsonResponse({
                'success': False,
                'error': 'Could not verify payment amount'
            }, status=400)

        # If tip amount is provided, update the booking using TipService
        booking = invoice.booking
        if tip_amount > 0:
            print(f"Adding tip amount of ${tip_amount} to booking using TipService")
            from .services import TipService
            
            # Convert to Decimal for precision
            tip_decimal = Decimal(str(tip_amount))
            
            # Validate tip amount
            invoice_amount = Decimal(str(invoice.amount / 100))  # Convert from cents to dollars
            is_valid, error_message = TipService.validate_tip_amount(tip_decimal, invoice_amount)
            
            if not is_valid:
                print(f"Invalid tip amount: {error_message}")
                return JsonResponse({
                    'success': False,
                    'error': f'Invalid tip amount: {error_message}'
                }, status=400)
            
            # Add tip to booking using service
            booking, invoice = TipService.add_tip_to_booking(booking, tip_decimal)
            print(f"Updated invoice amount to include tip: ${invoice.amount/100:.2f}")
        
        # Create payment record
        print("Creating payment record in database...")
        payment = Payment.objects.create(
            invoice=invoice,
            amount=payment_amount,
            paymentMethod='PayPal',
            transactionId=order_id,
            status='COMPLETED',
            paidAt=timezone.now(),
            payment_type=payment_type
        )
        print(f"Payment record created - ID: {payment.paymentId}")

        # Update invoice payment status
        print(f"Updating invoice {invoice.invoiceId} payment status")
        invoice.update_payment_status()
        print("Invoice updated successfully")
        
        payment_thread = threading.Thread(target=handle_payment_completed, args=(payment,))
        payment_thread.daemon = True
        payment_thread.start()

        print("Payment processing completed successfully")
        print("===== PAYPAL PAYMENT PROCESSING COMPLETED =====\n")
        return JsonResponse({
            'success': True,
            'payment_id': payment.paymentId,
            'status': 'COMPLETED',
            'payment_type': payment_type
        })

    except Exception as e:
        import traceback
        error_traceback = traceback.format_exc()
        print(f"PayPal payment processing error: {str(e)}")
        print(f"Error traceback: {error_traceback}")
        print("===== PAYPAL PAYMENT PROCESSING FAILED =====\n")
        return JsonResponse({
            'success': False,
            'error': 'An unexpected error occurred while processing your payment. Please try again.'
        }, status=500)
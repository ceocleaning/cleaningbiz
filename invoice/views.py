from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from django.http import HttpResponse, JsonResponse
from .models import Invoice, Payment
from bookings.models import Booking
import datetime
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from io import BytesIO
from django.views.decorators.http import require_http_methods
from django.db import transaction
from accounts.models import Business, BusinessSettings, BookingIntegration, ApiCredential, CustomAddons
import uuid
from django.utils import timezone
from django.template.loader import render_to_string
import os
from datetime import datetime
from reportlab.lib import colors
from reportlab.lib.units import inch, cm
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT
import io
from PIL import Image
import requests
from decimal import Decimal
from django.core.serializers.json import DjangoJSONEncoder
import json
import random




@login_required
def all_invoices(request):
    if not request.user.business_set.first():
        return redirect('accounts:register_business')

    invoices = Invoice.objects.select_related('booking').filter(booking__business__user=request.user).order_by('createdAt')
    pending_invoices = invoices.filter(isPaid=False).count()
    paid_invoices = invoices.filter(isPaid=True).count()
    
    context = {
        'invoices': invoices,
        'pending_invoices': pending_invoices,
        'paid_invoices': paid_invoices
    }
    return render(request, 'invoices.html', context)

@login_required
def create_invoice(request, bookingId):
    bookingObj = get_object_or_404(Booking, bookingId=bookingId)
    if request.method == 'POST':
        amount = request.POST.get('amount')
        
        try:
            invoice = Invoice.objects.create(
                booking=bookingObj,
                amount=bookingObj.totalPrice
            )
            messages.success(request, f'Invoice {invoice.invoiceId} created successfully!')
            return redirect('invoice:invoice_detail', invoiceId=invoice.invoiceId)
        except Booking.DoesNotExist:
            messages.error(request, 'Booking not found.')
            return redirect('invoice:create_invoice')
            
    context = {
        'booking': bookingObj,
    }
    return render(request, 'create_invoice.html', context)

@login_required
def edit_invoice(request, invoiceId):
    invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
    
    if request.method == 'POST':
        amount = request.POST.get('amount')
        is_paid = request.POST.get('isPaid') == 'on'
        
        invoice.amount = amount
        invoice.isPaid = is_paid
        invoice.save()
        
        messages.success(request, f'Invoice {invoice.invoiceId} updated successfully!')
        return redirect('invoice:invoice_detail', invoiceId=invoice.invoiceId)
    
    context = {
        'invoice': invoice
    }
    return render(request, 'update_invoice.html', context)


def delete_invoice(request, invoiceId):
    try:
        invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
        invoice.delete()
        messages.success(request, 'Invoice deleted successfully!')
        return redirect('bookings:all_invoices')
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found')
        return redirect('invoice:all_invoices')


@login_required
def booking_detail(request, bookingId):
    booking = get_object_or_404(Booking, bookingId=bookingId)
    context = {
        'booking': booking
    }
    return render(request, 'booking_detail.html', context)

@login_required
def invoice_detail(request, invoiceId):
    invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
    context = {
        'invoice': invoice,
        'SQUARE_APP_ID': settings.SQUARE_APP_ID,
        'SQUARE_LOCATION_ID': settings.SQUARE_LOCATION_ID,
        'SQUARE_ENVIRONMENT': settings.SQUARE_ENVIRONMENT,
    }
    return render(request, 'invoice_detail.html', context)


def invoice_preview(request, invoiceId):
    try:
        invoice = Invoice.objects.get(invoiceId=invoiceId)
        booking = invoice.booking
        business = booking.business

        # Only include add-ons with values > 0
        addons = [
            addon for addon in [
                ['Dishes', invoice.booking.addonDishes],
                ['Laundry Loads', invoice.booking.addonLaundryLoads],
                ['Window Cleaning', invoice.booking.addonWindowCleaning],
                ['Pets Cleaning', invoice.booking.addonPetsCleaning],
                ['Fridge Cleaning', invoice.booking.addonFridgeCleaning],
                ['Oven Cleaning', invoice.booking.addonOvenCleaning],
                ['Baseboard', invoice.booking.addonBaseboard],
                ['Blinds', invoice.booking.addonBlinds],
                ['Green Cleaning', invoice.booking.addonGreenCleaning],
                ['Cabinets Cleaning', invoice.booking.addonCabinetsCleaning],
                ['Patio Sweeping', invoice.booking.addonPatioSweeping],
                ['Garage Sweeping', invoice.booking.addonGarageSweeping],
            ] if addon[1] is not None and addon[1] > 0
        ]

        context = {
            'invoice': invoice,
            'booking': booking,
            'business': business,
            'addons': addons,
            'settings': {
                'SQUARE_APP_ID': settings.SQUARE_APP_ID
            }
        }
        return render(request, 'invoice_preview.html', context)
    except Invoice.DoesNotExist:
        messages.error(request, 'Invoice not found.')
        return redirect('invoice:all_invoices')

@login_required
def mark_invoice_paid(request, invoiceId):
    if request.method == 'POST':
        invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
        payment_method = request.POST.get('paymentMethod')
        amount = request.POST.get('amount')

        payment = Payment.objects.create(
            invoice=invoice,
            paymentMethod=payment_method,
            amount=amount,
            paidAt=timezone.now()
        )
        
        invoice.isPaid = True
        invoice.payment_details = payment
        invoice.save()
        
        messages.success(request, f'Invoice {invoice.invoiceId} marked as paid successfully!')
        return redirect('invoice:invoice_detail', invoiceId=invoice.invoiceId)
    
    return redirect('invoice:invoice_detail', invoiceId=invoiceId)

@login_required
def generate_pdf(request, invoiceId):
    # Get the invoice
    invoice = get_object_or_404(Invoice, invoiceId=invoiceId)
    
    # Create a buffer to receive PDF data
    buffer = io.BytesIO()
    
    # Create the PDF object using ReportLab
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30
    )
    
    # Container for the 'Flowable' objects
    elements = []
    
    # Styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=20,
        spaceAfter=20,
        alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        name='RightAlign',
        parent=styles['Normal'],
        alignment=TA_RIGHT
    ))
    styles.add(ParagraphStyle(
        name='SmallText',
        parent=styles['Normal'],
        fontSize=8,
        alignment=TA_CENTER
    ))
    
    # Create header table for logo and company info
    try:
        # Download and process logo
        logo_response = requests.get("https://i.imgur.com/8bWQUQX.png")
        logo_data = io.BytesIO(logo_response.content)
        logo_img = RLImage(logo_data, width=100, height=40)
        
        header_data = [
            [logo_img,
             Paragraph("CEO Cleaners<br/>123 Business Street<br/>New York, NY 10001<br/>Phone: (555) 123-4567<br/>Email: info@ceocleaners.com", 
                      ParagraphStyle('CompanyInfo', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT))]
        ]
    except:
        # If logo fails to load, use text instead
        header_data = [
            [Paragraph("CEO Cleaners", styles['CustomTitle']),
             Paragraph("CEO Cleaners<br/>123 Business Street<br/>New York, NY 10001<br/>Phone: (555) 123-4567<br/>Email: info@ceocleaners.com", 
                      ParagraphStyle('CompanyInfo', parent=styles['Normal'], fontSize=9, alignment=TA_RIGHT))]
        ]

    header_table = Table(header_data, colWidths=[doc.width/2.0]*2)
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 20))
    
    # Add invoice header with status
    status_color = colors.green if invoice.isPaid else colors.red
    invoice_header = [
        [Paragraph(f"<font size=16><b>INVOICE #{invoice.invoiceId}</b></font>", styles['Normal']),
         Paragraph(f"<font size=16 color={status_color}><b>{'PAID' if invoice.isPaid else 'UNPAID'}</b></font>", styles['RightAlign'])]
    ]
    header_table = Table(invoice_header, colWidths=[doc.width/2.0]*2)
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, 0), 'LEFT'),
        ('ALIGN', (1, 0), (1, 0), 'RIGHT'),
    ]))
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    
    # Add invoice details and client info in a table
    details_data = [
        ['Invoice Date:', invoice.createdAt.strftime('%B %d, %Y'), 'Bill To:', ''],
        ['Due Date:', (invoice.createdAt + timezone.timedelta(days=30)).strftime('%B %d, %Y'), invoice.booking.name, ''],
        ['', '', invoice.booking.email, ''],
        ['', '', invoice.booking.phoneNumber, ''],
    ]
    
    details_table = Table(details_data, colWidths=[doc.width/6.0, doc.width/3.0, doc.width/6.0, doc.width/3.0])
    details_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        ('ALIGN', (2, 0), (3, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('TOPPADDING', (0, 0), (-1, -1), 1),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 1),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.grey),
        ('TEXTCOLOR', (2, 0), (2, -1), colors.grey),
    ]))
    elements.append(details_table)
    elements.append(Spacer(1, 20))
    
    # Add service details
    service_data = [
        ['Description', 'Details', 'Amount'],
        [
            Paragraph(f"<b>{invoice.booking.get_serviceType_display()}</b>", styles['Normal']),
            Paragraph(f"""
                Date: {invoice.booking.cleaningDateTime.strftime('%B %d, %Y')}<br/>
                Time: {invoice.booking.cleaningDateTime.strftime('%I:%M %p')}<br/>
                Bedrooms: {invoice.booking.bedrooms}<br/>
                Bathrooms: {invoice.booking.bathrooms}<br/>
                Area: {invoice.booking.squareFeet} sq ft
            """, styles['Normal']),
            Paragraph(f"<b>${invoice.amount}</b>", styles['RightAlign'])
        ],
    ]
    
    # Calculate totals
    service_data.extend([
        ['', Paragraph('<b>Subtotal:</b>', styles['RightAlign']), Paragraph(f"<b>${invoice.amount}</b>", styles['RightAlign'])],
        ['', Paragraph('<b>Tax (0%):</b>', styles['RightAlign']), Paragraph('<b>$0.00</b>', styles['RightAlign'])],
        ['', Paragraph('<b>Total:</b>', styles['RightAlign']), Paragraph(f"<b>${invoice.amount}</b>", styles['RightAlign'])],
    ])
    
    service_table = Table(service_data, colWidths=[doc.width/3.0, doc.width/3.0, doc.width/3.0])
    service_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.black),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, 1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, 1), colors.black),
        ('ALIGN', (0, 1), (-1, -1), 'LEFT'),
        ('GRID', (0, 0), (-1, -2), 0.25, colors.black),
        ('LINEBELOW', (0, -1), (-1, -1), 1, colors.black),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(service_table)
    
    # Add payment instructions
    elements.append(Spacer(1, 20))
    payment_data = [
        [Paragraph("<b>Payment Instructions</b>", styles['Normal']),
         Paragraph("<b>Note</b>", styles['Normal'])],
        [Paragraph("""
            <b>Bank Transfer:</b><br/>
            Bank: Example Bank<br/>
            Account Name: CEO Cleaners LLC<br/>
            Account Number: XXXX-XXXX-XXXX-1234<br/>
            Routing Number: XXX-XXX-XXX
        """, styles['Normal']),
         Paragraph("""
            1. Please include invoice number in payment reference<br/>
            2. Payment is due within 30 days<br/>
            3. Late payments may incur additional fees
         """, styles['Normal'])]
    ]
    
    payment_table = Table(payment_data, colWidths=[doc.width/2.0]*2)
    payment_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.25, colors.grey),
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f8f9fa')),
    ]))
    elements.append(payment_table)
    
    # Add thank you note at the bottom
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Thank You for Your Business!", styles['CustomTitle']))
    elements.append(Paragraph("If you have any questions about this invoice, please contact us at (555) 123-4567 or info@ceocleaners.com", 
                            styles['SmallText']))
    
    # Build PDF
    doc.build(elements)
    
    # FileResponse sets the Content-Disposition header so that browsers
    # present the option to save the file.
    buffer.seek(0)
    filename = f"Invoice_{invoice.invoiceId}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    return HttpResponse(
        buffer.getvalue(),
        content_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )

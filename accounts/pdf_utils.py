"""
PDF generation utilities for business pricing export
"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from django.http import HttpResponse
from datetime import datetime
import io
from accounts.models import CustomAddons

def generate_pricing_pdf(business):
    """
    Generate a PDF document containing all pricing information for a business.
    
    Args:
        business: Business model instance
        
    Returns:
        HttpResponse with PDF content
    """
    # Get business settings
    try:
        settings = business.settings
    except:
        return None
    
    # Create buffer for PDF
    buffer = io.BytesIO()
    
    # Create PDF document
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    # Container for flowable objects
    elements = []
    
    # Define styles
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name='CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=20,
        alignment=TA_CENTER,
        textColor=colors.HexColor('#1aad8c')
    ))
    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=16,
        spaceAfter=12,
        spaceBefore=20,
        textColor=colors.HexColor('#1aad8c'),
        borderPadding=10
    ))
    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading3'],
        fontSize=12,
        spaceAfter=8,
        textColor=colors.HexColor('#666666')
    ))
    
    # Add title
    elements.append(Paragraph(f"<b>{business.businessName}</b>", styles['CustomTitle']))
    elements.append(Paragraph("Pricing Configuration", styles['CustomTitle']))
    elements.append(Spacer(1, 10))
    
    # Add generation date
    date_style = ParagraphStyle('DateStyle', parent=styles['Normal'], fontSize=10, alignment=TA_CENTER, textColor=colors.grey)
    elements.append(Paragraph(f"Generated on {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", date_style))
    elements.append(Spacer(1, 20))
    
    # ===== BASE PRICING SECTION =====
    elements.append(Paragraph("<b>Base Pricing</b>", styles['SectionHeader']))
    
    base_pricing_data = [
        ['Item', 'Price'],
        ['Base Price (Optional)', f"${settings.base_price if settings.base_price else '0.00'}"],
        ['Price per Bedroom', f"${settings.bedroomPrice}"],
        ['Price per Bathroom', f"${settings.bathroomPrice}"],
        ['Deposit Fee', f"${settings.depositFee}"],
        ['Tax Percentage', f"{settings.taxPercent}%"],
    ]
    
    base_table = Table(base_pricing_data, colWidths=[doc.width*0.6, doc.width*0.4])
    base_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1aad8c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#1aad8c')),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(base_table)
    elements.append(Spacer(1, 20))
    
    # ===== SQFT MULTIPLIERS SECTION =====
    elements.append(Paragraph("<b>Square Feet Multipliers</b>", styles['SectionHeader']))
    
    multiplier_data = [
        ['Service Type', 'Multiplier'],
        ['Standard Cleaning', f"{settings.sqftMultiplierStandard}x"],
        ['Deep Cleaning', f"{settings.sqftMultiplierDeep}x"],
        ['Move In/Out Cleaning', f"{settings.sqftMultiplierMoveinout}x"],
        ['Airbnb Cleaning', f"{settings.sqftMultiplierAirbnb}x"],
    ]
    
    multiplier_table = Table(multiplier_data, colWidths=[doc.width*0.6, doc.width*0.4])
    multiplier_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1aad8c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#1aad8c')),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(multiplier_table)
    elements.append(Spacer(1, 20))
    
    # ===== RECURRING DISCOUNTS SECTION =====
    elements.append(Paragraph("<b>Recurring Service Discounts</b>", styles['SectionHeader']))
    
    discount_data = [
        ['Frequency', 'Discount'],
        ['Weekly Service', f"{settings.weeklyDiscount}%"],
        ['Bi-weekly Service', f"{settings.biweeklyDiscount}%"],
        ['Monthly Service', f"{settings.monthlyDiscount}%"],
    ]
    
    discount_table = Table(discount_data, colWidths=[doc.width*0.6, doc.width*0.4])
    discount_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1aad8c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#1aad8c')),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(discount_table)
    elements.append(Spacer(1, 20))
    
    # ===== ADD-ON SERVICES SECTION =====
    elements.append(Paragraph("<b>Add-on Services</b>", styles['SectionHeader']))
    
    addon_data = [
        ['Add-on Service', 'Price'],
        ['Dishes', f"${settings.addonPriceDishes}"],
        ['Laundry', f"${settings.addonPriceLaundry}"],
        ['Window Cleaning', f"${settings.addonPriceWindow}"],
        ['Pet Cleaning', f"${settings.addonPricePets}"],
        ['Fridge Cleaning', f"${settings.addonPriceFridge}"],
        ['Oven Cleaning', f"${settings.addonPriceOven}"],
        ['Baseboard Cleaning', f"${settings.addonPriceBaseboard}"],
        ['Blinds Cleaning', f"${settings.addonPriceBlinds}"],
        ['Green Cleaning Products', f"${settings.addonPriceGreen}"],
        ['Cabinet Cleaning', f"${settings.addonPriceCabinets}"],
        ['Patio Sweeping', f"${settings.addonPricePatio}"],
        ['Garage Sweeping', f"${settings.addonPriceGarage}"],
    ]
    
    addon_table = Table(addon_data, colWidths=[doc.width*0.6, doc.width*0.4])
    addon_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1aad8c')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
        ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#1aad8c')),
        ('TOPPADDING', (0, 1), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
    ]))
    elements.append(addon_table)
    
    # ===== CUSTOM ADD-ONS SECTION =====
    custom_addons = business.business_custom_addons.all()
    if custom_addons.exists():
        elements.append(Spacer(1, 20))
        elements.append(Paragraph("<b>Custom Add-on Services</b>", styles['SectionHeader']))
        
        custom_addon_data = [['Custom Add-on Name', 'Price']]
        for addon in custom_addons:
            custom_addon_data.append([addon.addonName, f"${addon.addonPrice}"])
        
        custom_addon_table = Table(custom_addon_data, colWidths=[doc.width*0.6, doc.width*0.4])
        custom_addon_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1aad8c')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('FONTNAME', (1, 1), (1, -1), 'Helvetica-Bold'),
            ('TEXTCOLOR', (1, 1), (1, -1), colors.HexColor('#1aad8c')),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        elements.append(custom_addon_table)
    
    # Add footer
    elements.append(Spacer(1, 30))
    footer_style = ParagraphStyle('Footer', parent=styles['Normal'], fontSize=9, alignment=TA_CENTER, textColor=colors.grey)
    elements.append(Paragraph(f"This pricing sheet is confidential and proprietary to {business.businessName}", footer_style))
    elements.append(Paragraph(f"Contact: {business.phone} | {business.user.email}", footer_style))
    
    # Build PDF
    doc.build(elements)
    
    # Get PDF data
    buffer.seek(0)
    pdf_data = buffer.getvalue()
    buffer.close()
    
    # Create filename
    filename = f"Pricing_{business.businessName.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"
    
    # Create HTTP response
    response = HttpResponse(
        pdf_data,
        content_type='application/pdf',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'}
    )
    
    return response

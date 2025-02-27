from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.conf import settings
from .models import Booking
from accounts.models import ApiCredential
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

@receiver(post_save, sender=Booking)
def send_booking_confirmation_email(sender, instance, created, **kwargs):
    """Send confirmation email when a new booking is created"""
    if created:  # Only send email for new bookings
        try:
            # Get the business's email credentials
            api_credentials = ApiCredential.objects.get(business=instance.business)
            
            if not api_credentials.gmail_host_user or not api_credentials.gmail_host_password:
                print("Email credentials not configured for business")
                return

            # Create the email
            msg = MIMEMultipart('alternative')
            msg['Subject'] = f'Booking Confirmation - {instance.business.businessName}'
            msg['From'] = api_credentials.gmail_host_user
            msg['To'] = instance.email

            # Create HTML email content
            html_content = f"""
            <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <h2>Booking Confirmation</h2>
                <p>Dear {instance.firstName} {instance.lastName},</p>
                <p>Thank you for booking with {instance.business.businessName}. Here are your booking details:</p>
                
                <div style="background-color: #f9f9f9; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <h3>Booking Details:</h3>
                    <p><strong>Service Type:</strong> {instance.serviceType}</p>
                    <p><strong>Date & Time:</strong> {instance.cleaningDateTime.strftime('%B %d, %Y at %I:%M %p')}</p>
                    <p><strong>Location:</strong><br>
                    {instance.address1}<br>
                    {instance.address2 if instance.address2 else ''}<br>
                    {instance.city}, {instance.stateOrProvince} {instance.zipCode}</p>
                    
                    <h4>Property Details:</h4>
                    <p>Bedrooms: {instance.bedrooms}<br>
                    Bathrooms: {instance.bathrooms}<br>
                    Square Feet: {instance.squareFeet}</p>
                    
                    <h4>Selected Add-ons:</h4>
                    <ul style="list-style-type: none; padding-left: 0;">
                        {f'<li>✓ Dishes</li>' if instance.addonDishes else ''}
                        {f'<li>✓ Laundry ({instance.addonLaundryLoads} loads)</li>' if instance.addonLaundryLoads else ''}
                        {f'<li>✓ Window Cleaning</li>' if instance.addonWindowCleaning else ''}
                        {f'<li>✓ Pet Cleaning</li>' if instance.addonPetsCleaning else ''}
                        {f'<li>✓ Fridge Cleaning</li>' if instance.addonFridgeCleaning else ''}
                        {f'<li>✓ Oven Cleaning</li>' if instance.addonOvenCleaning else ''}
                        {f'<li>✓ Baseboard Cleaning</li>' if instance.addonBaseboard else ''}
                        {f'<li>✓ Blinds Cleaning</li>' if instance.addonBlinds else ''}
                        {f'<li>✓ Green Cleaning</li>' if instance.addonGreenCleaning else ''}
                        {f'<li>✓ Cabinets Cleaning</li>' if instance.addonCabinetsCleaning else ''}
                        {f'<li>✓ Patio Sweeping</li>' if instance.addonPatioSweeping else ''}
                        {f'<li>✓ Garage Sweeping</li>' if instance.addonGarageSweeping else ''}
                    </ul>
                    
                    <h4>Pricing:</h4>
                    <p>
                    Total: ${instance.totalPrice}<br>
                    {f'Tax: ${instance.tax}' if instance.tax else ''}
                    </p>
                </div>
                
                <p>If you need to make any changes to your booking or have any questions, please contact us.</p>
                
                <p>Best regards,<br>
                {instance.business.businessName} Team</p>
            </body>
            </html>
            """
            
            # Create plain text version
            text_content = strip_tags(html_content)

            # Attach both plain text and HTML versions
            part1 = MIMEText(text_content, 'plain')
            part2 = MIMEText(html_content, 'html')
            msg.attach(part1)
            msg.attach(part2)

            # Set up SMTP connection
            smtp_server = smtplib.SMTP('smtp.gmail.com', 587)
            smtp_server.starttls()
            smtp_server.login(api_credentials.gmail_host_user, api_credentials.gmail_host_password)
            
            # Send email
            smtp_server.send_message(msg)
            smtp_server.quit()
            
            print(f"Booking confirmation email sent to {instance.email}")
            
        except ApiCredential.DoesNotExist:
            print("API credentials not found for business")
        except Exception as e:
            print(f"Error sending booking confirmation email: {str(e)}")
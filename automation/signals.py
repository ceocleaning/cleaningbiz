from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import EmailMessage
from .models import Lead
from django.conf import settings
from retell import Retell
import os




# @receiver(post_save, sender=Lead)
# def set_status_and_send_email(sender, instance, created, **kwargs):
#     print("Signal received!")
#     if created:
#         try:
#             # Update emailSentAt field
#             instance.emailSentAt = timezone.now()
#             instance.save(update_fields=['emailSentAt'])

#             # Prepare email details
#             subject = f"Hey {instance.name}, Book your appointment now!"
#             html_content = f"""
#             <html>
#                 <body>
#                     <p>Dear {instance.name},</p>
#                     <p>Looking for a spotless home or office? We’ve got you covered!</p>
#                     <p>
#                         Book your cleaning service in just a few clicks.
#                         Talk to our AI assistant, customize your needs, and schedule your appointment effortlessly:
#                     </p>
#                     <a href="https://0d2c-39-47-5-96.ngrok-free.app/chatbot/"
#                        style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
#                        Book Now
#                     </a>
#                     <p>We look forward to making your space shine!</p>
#                     <p>Best regards,<br>Jazmine<br>CEO CLEANING</p>
#                 </body>
#             </html>
#             """

#             # Send email
#             email = EmailMessage(
#                 subject,
#                 html_content,
#                 settings.EMAIL_HOST_USER,  # Replace with your sender email
#                 [instance.email,],  # Recipient list
#             )
#             email.content_subtype = "html"  # Important: Indicate the email is in HTML format
#             email.send()

#             print("HTML Email sent successfully!")

#         except Exception as e:
#             print(f"Error sending email: {e}")



@receiver(post_save, sender=Lead)
def set_status_and_send_email(sender, instance, created, **kwargs):
    apicreds = ApiCredential.objects.get(business=instance.business)
    client = Retell(api_key=apicreds.retellAPIKey)
    print("Signal received!")
    if created:
        try:
            call_response = client.call.create_phone_call(
                from_number=instance.voiceAgentNumber,
                to_number=instance.phoneNumber
            )
            print(call_response)

        except Exception as e:
            print(f"Error sending email: {e}")
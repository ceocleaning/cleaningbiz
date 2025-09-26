import json
from datetime import datetime
from django.utils import timezone
from django.template.loader import render_to_string
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from twilio.rest import Client

from .models import Notification
from leadsAutomation.utils import send_email as send_email_util

class NotificationService:
    """
    Centralized service for sending all types of notifications
    """
    
    @classmethod
    def send_notification(cls, recipient, from_email, notification_type, subject, to_email=None, email_to=None, to_sms=None, sms_to=None, content=None, sender=None):
        """
        Central method to send any type of notification
        
        Parameters:
        - recipient: User object who will receive the notification
        - notification_type: List of notification types ('email', 'sms')
        - subject: Subject line for the notification
        - content: Plain text content (optional if template is provided)
        - template_name: Path to template for rendering content (optional)
        """
        
        # Create notification record
        notification = Notification(
            sender=sender,
            recipient=recipient,
            notification_type='in_app',
            subject=subject,
            content=content,

        )

        if to_email or email_to:
            notification.email_to = to_email or email_to
        if to_sms or sms_to:
            notification.sms_to = to_sms or sms_to
        
       
        
        # Save notification
        notification.save()
        
        # Send notification based on type
        result = None

        for n_type in notification_type:
            if n_type == 'email':
                result = cls._send_email_notification(notification, from_email)
            elif n_type == 'sms':
                result = cls._send_sms_notification(notification)
        
                
            
        
        notification.sent_at = timezone.now()
        notification.save()
        return result
            
    @classmethod
    def _send_email_notification(cls, notification, from_email):
        """Send an email notification using the existing email utility"""
        try:
            
            # Send email using existing utility
            result = send_email_util(
                from_email=from_email,
                to_email=notification.email_to,
                subject=notification.subject,
                text_content=notification.content,
                reply_to=notification.sender.user.email,
            )

            print("Email sent successfully to", notification.email_to)
            
            return result
        except Exception as e:
            print(e)
            return {'success': False, 'error': str(e)}
        
    @classmethod
    def _send_sms_notification(cls, notification):
        try:
            # The sender is already a Business object, so we access apicredentials directly
            api_cred = notification.sender.apicredential
                        
            if api_cred.twilioAccountSid and api_cred.twilioAuthToken and api_cred.twilioSmsNumber:
                # Initialize Twilio client
                twilioAccountSid = api_cred.twilioAccountSid.encode('utf-8')
                twilioAuthToken = api_cred.twilioAuthToken.encode('utf-8')
                client = Client(twilioAccountSid, twilioAuthToken)
                
                # Send SMS
                message = client.messages.create(
                    body=notification.content,
                    from_=api_cred.twilioSmsNumber,
                    to=notification.sms_to,
                )
            
                return {'success': True, 'message': 'SMS notification would be sent (not implemented)'}
    
        except Exception as e:
            print(e)
            return {'success': False, 'error': str(e)}
            
        
        


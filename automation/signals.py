from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from django.core.mail import EmailMessage
from .models import Lead
from django.conf import settings
from retell import Retell
import os
import requests
from django.core.mail import send_mail
from accounts.models import ApiCredential
from .tasks import send_call_to_lead
from django_q.tasks import schedule

import datetime






@receiver(post_save, sender=Lead)
def set_status_and_send_email(sender, instance, created, **kwargs):
    if created:
        print("Lead created:", instance)
        schedule(
            'automation.tasks.send_call_to_lead',  
            instance.id,  
            schedule_type='O',
            next_run=timezone.now() + datetime.timedelta(seconds=60),
            )
        print("Call scheduled for lead")
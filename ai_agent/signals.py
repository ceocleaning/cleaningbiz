from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Chat, Messages
from subscription.models import UsageTracker

from datetime import datetime

@receiver(post_save, sender=Chat)
def update_chat_summary(sender, instance, created, **kwargs):
    if created:
        pass
    else:
        print("--------------------------------")
        print(f"[DEBUG] Chat updated: {instance.id} at {datetime.now()}")
        print(instance.summary)
        print("--------------------------------")


@receiver(pre_save, sender=Chat)
def save_chat_summary(sender, instance, **kwargs):
    if instance.id:
        # Get previous instance
        previous_instance = Chat.objects.get(id=instance.id)
        
        # Only restore previous summary if the new summary is empty or None
        if not instance.summary and previous_instance.summary:
            print(f"[DEBUG] Restoring previous summary from signal - Chat ID: {instance.id}")
            instance.summary = previous_instance.summary
        elif instance.summary:
            print(f"[DEBUG] Using new summary from signal - Chat ID: {instance.id}")

@receiver(post_save, sender=Messages)
def track_usage(sender, instance,created, **kwargs):
    if created:
        # Track SMS usage
        UsageTracker.increment_metric(instance.chat.business, 'sms_messages')


# Generated by Django 5.1.6 on 2025-06-20 09:28

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0017_setupfee'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='subscriptionplan',
            name='slug',
        ),
    ]

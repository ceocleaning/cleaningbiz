# Generated by Django 5.1.6 on 2025-03-21 20:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0023_business_usecall'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='timeToWait',
            field=models.IntegerField(default=0),
        ),
    ]

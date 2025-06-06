# Generated by Django 5.1.6 on 2025-05-18 12:43

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0034_business_job_assignment'),
        ('bookings', '0012_booking_arrival_confirmed_at_booking_completed_at'),
    ]

    operations = [
        migrations.CreateModel(
            name='CleanerPayout',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('payout_id', models.CharField(max_length=20, unique=True)),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10)),
                ('status', models.CharField(choices=[('pending', 'Pending'), ('paid', 'Paid'), ('cancelled', 'Cancelled')], default='pending', max_length=20)),
                ('payment_method', models.CharField(blank=True, max_length=50, null=True)),
                ('payment_reference', models.CharField(blank=True, max_length=255, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('paid_at', models.DateTimeField(blank=True, null=True)),
                ('notes', models.TextField(blank=True, null=True)),
                ('bookings', models.ManyToManyField(related_name='payouts', to='bookings.booking')),
                ('business', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payouts', to='accounts.business')),
                ('cleaner_profile', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='payouts', to='accounts.cleanerprofile')),
            ],
        ),
    ]

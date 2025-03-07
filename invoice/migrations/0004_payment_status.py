# Generated by Django 5.1.6 on 2025-03-07 20:06

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('invoice', '0003_alter_payment_squarepaymentid'),
    ]

    operations = [
        migrations.AddField(
            model_name='payment',
            name='status',
            field=models.CharField(choices=[('PENDING', 'Pending'), ('AUTHORIZED', 'Authorized'), ('COMPLETED', 'Completed'), ('FAILED', 'Failed'), ('CANCELLED', 'Cancelled')], default='PENDING', max_length=20),
        ),
    ]

# Generated by Django 5.1.6 on 2025-04-07 10:36

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('accounts', '0026_business_square_card_id_business_square_customer_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='business',
            name='isRejected',
            field=models.BooleanField(default=False),
        ),
    ]

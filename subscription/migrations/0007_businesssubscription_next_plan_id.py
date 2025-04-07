# Generated by Django 5.1.6 on 2025-04-05 18:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0006_billinghistory_square_invoice_id_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='businesssubscription',
            name='next_plan_id',
            field=models.IntegerField(blank=True, help_text='ID of the plan to change to at next billing date', null=True),
        ),
    ]

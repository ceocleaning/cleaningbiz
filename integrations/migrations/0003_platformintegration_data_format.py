# Generated by Django 5.1.6 on 2025-02-27 12:20

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0002_alter_datamapping_options_datamapping_order_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='platformintegration',
            name='data_format',
            field=models.CharField(choices=[('flat', 'Flat Structure (Regular)'), ('nested', 'Nested Objects')], default='flat', help_text='Choose how the data should be structured when sent to the API', max_length=10),
        ),
    ]

# Generated by Django 5.1.6 on 2025-02-27 14:46

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integrations', '0007_platformintegration_platform_type_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='datamapping',
            name='transformation_rule',
        ),
    ]

# Generated by Django 5.1.6 on 2025-04-07 13:01

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('subscription', '0009_remove_feature_category'),
    ]

    operations = [
        migrations.CreateModel(
            name='TrialPlan',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(default='30-Day Trial', max_length=100)),
                ('description', models.TextField(default='Try our service for 30 days')),
                ('price', models.DecimalField(decimal_places=2, default=30.0, max_digits=10)),
                ('duration_days', models.IntegerField(default=30)),
                ('voice_minutes', models.IntegerField(default=100)),
                ('sms_messages', models.IntegerField(default=100)),
                ('agents', models.IntegerField(default=1)),
                ('leads', models.IntegerField(default=50)),
                ('features', models.JSONField(default=dict)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='businesssubscription',
            name='is_trial',
            field=models.BooleanField(default=False, help_text='Whether this subscription is a trial'),
        ),
        migrations.AddField(
            model_name='businesssubscription',
            name='trial_end_date',
            field=models.DateTimeField(blank=True, help_text='Date when the trial ends', null=True),
        ),
        migrations.AlterField(
            model_name='businesssubscription',
            name='status',
            field=models.CharField(choices=[('active', 'Active'), ('cancelled', 'Cancelled'), ('past_due', 'Past Due'), ('trialing', 'Trialing'), ('trial', 'Trial'), ('ended', 'Ended')], default='active', max_length=20),
        ),
    ]

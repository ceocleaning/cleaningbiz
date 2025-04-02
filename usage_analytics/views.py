from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json

from subscription.models import BusinessSubscription, UsageTracker

# Create your views here.

@login_required
def usage_overview(request):
    """Main usage overview dashboard."""
    business = request.user.business_set.first()
    
    # Get current subscription
    try:
        subscription = BusinessSubscription.objects.filter(
            business=business,
            is_active=True
        ).latest('created_at')
        
        subscription_data = {
            'name': subscription.plan.name,
            'price': subscription.plan.price,
            'status': subscription.status,
            'next_billing_date': subscription.end_date,
            'voice_minutes_limit': subscription.plan.voice_minutes,
            'voice_calls_limit': subscription.plan.voice_calls,
            'sms_messages_limit': subscription.plan.sms_messages,
        }
    except BusinessSubscription.DoesNotExist:
        subscription_data = {
            'name': 'No Active Plan',
            'price': 0,
            'status': 'inactive',
            'next_billing_date': None,
            'voice_minutes_limit': 0,
            'voice_calls_limit': 0,
            'sms_messages_limit': 0,
        }
    
    # Get usage summary for current month
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_of_month,
        end_date=today
    )
    
    # Calculate usage percentages
    voice_calls_percentage = min(round((usage_summary['voice_calls'] / subscription_data['voice_calls_limit']) * 100, 0), 100) if subscription_data['voice_calls_limit'] > 0 else 0
    voice_minutes_percentage = min(round((usage_summary['voice_minutes'] / subscription_data['voice_minutes_limit']) * 100, 0), 100) if subscription_data['voice_minutes_limit'] > 0 else 0
    sms_messages_percentage = min(round((usage_summary['sms_messages'] / subscription_data['sms_messages_limit']) * 100, 0), 100) if subscription_data['sms_messages_limit'] > 0 else 0
    
    context = {
        'active_page': 'usage_overview',
        'title': 'Usage Overview',
        'subscription': subscription_data,
        'usage': {
            'voice_calls': {
                'used': usage_summary['voice_calls'],
                'limit': subscription_data['voice_calls_limit'],
                'percentage': voice_calls_percentage
            },
            'voice_minutes': {
                'used': usage_summary['voice_minutes'],
                'limit': subscription_data['voice_minutes_limit'],
                'percentage': voice_minutes_percentage
            },
            'sms_messages': {
                'used': usage_summary['sms_messages'],
                'limit': subscription_data['sms_messages_limit'],
                'percentage': sms_messages_percentage
            }
        },
        # Voice module key metrics
        'voice_metrics': {
            'total_calls': usage_summary['voice_calls'],
            'total_minutes': usage_summary['voice_minutes'],
            'avg_duration': f"{usage_summary['voice_minutes'] / usage_summary['voice_calls'] if usage_summary['voice_calls'] > 0 else 0:.1f}m",
            'success_rate': '87%'
        },
        # SMS module key metrics
        'sms_metrics': {
            'total_messages': usage_summary['sms_messages'],
            'response_rate': '85%',
            'avg_response_time': '45s',
            'conversion_rate': '32%'
        }
    }
    
    return render(request, 'usage_analytics/overview.html', context)

@login_required
def voice_analytics(request):
    """Detailed voice analytics page."""
    business = request.user.business_set.first()        
    
    # Get usage summary for current month
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_of_month,
        end_date=today
    )
    
    # Calculate average call duration
    avg_duration_minutes = usage_summary['voice_minutes'] / usage_summary['voice_calls'] if usage_summary['voice_calls'] > 0 else 0
    avg_duration_seconds = int(avg_duration_minutes * 60)
    avg_duration_formatted = f"{int(avg_duration_minutes)}m {avg_duration_seconds % 60}s"
    
    # Call outcome breakdown (sample data)
    call_outcomes = {
        'completed': 65,
        'failed': 15,
        'no_answer': 12,
        'busy': 8
    }
    
    # Call duration distribution (sample data)
    call_duration_distribution = {
        '< 1m': 10,
        '1-2m': 25,
        '2-3m': 35,
        '3-5m': 30,
        '5-10m': 15,
        '> 10m': 5
    }
    
    context = {
        'active_page': 'voice_analytics',
        'title': 'Voice Analytics',
        'voice_stats': {
            'total_calls': usage_summary['voice_calls'],
            'total_minutes': usage_summary['voice_minutes'],
            'avg_duration': avg_duration_formatted,
            'success_rate': '87%'
        },
        'call_outcomes': call_outcomes,
        'call_duration_distribution': call_duration_distribution
    }
    
    return render(request, 'usage_analytics/voice_analytics.html', context)

@login_required
def sms_analytics(request):
    """Detailed SMS analytics page."""
    business = request.user.business_set.first()
    
    # Get usage summary for current month
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_of_month,
        end_date=today
    )
    
    # Message status breakdown (sample data)
    message_status = {
        'delivered': 97,
        'read': 85,
        'responded': 68,
        'failed': 3
    }
    
    # Response time distribution (sample data)
    response_time_distribution = {
        '<30s': 320,
        '30s-1m': 250,
        '1m-5m': 180,
        '5m-30m': 90,
        '30m-1h': 45,
        '>1h': 15
    }
    
    # Customer engagement (sample data)
    customer_engagement = {
        'high': 37,
        'medium': 39,
        'low': 24
    }
    
    context = {
        'active_page': 'sms_analytics',
        'title': 'SMS Analytics',
        'sms_stats': {
            'total_messages': usage_summary['sms_messages'],
            'response_rate': '85%',
            'avg_response_time': '45s',
            'conversion_rate': '32%'
        },
        'message_status': message_status,
        'response_time_distribution': response_time_distribution,
        'customer_engagement': customer_engagement
    }
    
    return render(request, 'usage_analytics/sms_analytics.html', context)

@login_required
def get_usage_data(request):
    """API endpoint to retrieve usage data for charts and metrics."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = (timezone.now() - timedelta(days=30)).date()
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get actual usage data for the date range
    usage_records = UsageTracker.objects.filter(
        business=business,
        date__gte=start_date,
        date__lte=end_date
    ).order_by('date')
    
    # Prepare data structure for charts
    dates = []
    voice_calls_data = []
    voice_minutes_data = []
    sms_messages_data = []
    
    current_date = start_date
    date_data_map = {record.date: record.metrics for record in usage_records}
    
    while current_date <= end_date:
        dates.append(current_date.strftime('%Y-%m-%d'))
        
        if current_date in date_data_map:
            metrics = date_data_map[current_date]
            voice_calls_data.append(metrics.get('voice_calls', 0))
            voice_minutes_data.append(metrics.get('voice_minutes', 0))
            sms_messages_data.append(metrics.get('sms_messages', 0))
        else:
            # No data for this date, use zeros
            voice_calls_data.append(0)
            voice_minutes_data.append(0)
            sms_messages_data.append(0)
        
        current_date += timedelta(days=1)
    
    # If no real data, generate some sample data
    if not usage_records:
        voice_calls_data = [int(i * 1.5) for i in range(len(dates))]
        voice_minutes_data = [call * 10 + 5 for call in voice_calls_data]
        sms_messages_data = [int(i * 3.5) for i in range(len(dates))]
    
    # Calculate summary metrics
    total_voice_calls = sum(voice_calls_data)
    total_voice_minutes = sum(voice_minutes_data)
    total_sms_messages = sum(sms_messages_data)
    
    # Voice call status breakdown
    voice_call_status = {
        'completed': int(total_voice_calls * 0.85),
        'failed': int(total_voice_calls * 0.05),
        'no_answer': int(total_voice_calls * 0.07),
        'busy': int(total_voice_calls * 0.03)
    }
    
    # SMS status breakdown
    sms_status = {
        'delivered': int(total_sms_messages * 0.97),
        'read': int(total_sms_messages * 0.85),
        'responded': int(total_sms_messages * 0.68),
        'failed': int(total_sms_messages * 0.03)
    }
    
    # Response time distribution
    response_time_distribution = {
        '<30s': 320,
        '30s-1m': 250,
        '1m-5m': 180,
        '5m-30m': 90,
        '30m-1h': 45,
        '>1h': 15
    }
    
    # Customer engagement
    customer_engagement = {
        'high': 37,
        'medium': 39,
        'low': 24
    }
    
    response_data = {
        'dates': dates,
        'voice_calls': voice_calls_data,
        'voice_minutes': voice_minutes_data,
        'sms_messages': sms_messages_data,
        'summary': {
            'total_voice_calls': total_voice_calls,
            'total_voice_minutes': total_voice_minutes,
            'total_sms_messages': total_sms_messages,
            'voice_call_status': voice_call_status,
            'sms_status': sms_status,
            'response_rate': 85,
            'avg_response_time': 45,
            'conversion_rate': 32
        },
        'response_time_distribution': response_time_distribution,
        'customer_engagement': customer_engagement
    }
    
    return JsonResponse(response_data)

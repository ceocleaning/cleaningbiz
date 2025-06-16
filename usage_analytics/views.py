from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from datetime import datetime, timedelta
import json
import random

from subscription.models import BusinessSubscription, UsageTracker
from .services.usage_service import UsageService
from .services.retell_api_service import RetellAPIService

# Create your views here.

@login_required
def usage_overview(request):
    """Main usage overview dashboard."""
    business = request.user.business_set.first()
    
    # Get current subscription using the active_subscription method
    subscription = business.active_subscription()
    
    if subscription and subscription.is_subscription_active():
        # Get features from M2M relationship
        features = subscription.plan.features.filter(is_active=True)
        feature_list = [feature.name for feature in features]
        
        subscription_data = {
            'name': subscription.plan.name,
            'price': subscription.plan.price,
            'status': subscription.status,
            'next_billing_date': subscription.next_billing_date or subscription.end_date,
            'start_date': subscription.start_date,
            'voice_minutes_limit': subscription.plan.voice_minutes,
            'sms_messages_limit': subscription.plan.sms_messages,
            'agents_limit': subscription.plan.agents,
            'leads_limit': subscription.plan.leads,
            'cleaners_limit': subscription.plan.cleaners,
            'features': feature_list
        }
    else:
        subscription_data = {
            'name': 'No Active Plan',
            'price': 0,
            'status': 'inactive',
            'next_billing_date': None,
            'start_date': None,
            'voice_minutes_limit': 0,
            'sms_messages_limit': 0,
            'agents_limit': 0,
            'leads_limit': 0,
            'cleaners_limit': 0,
            'features': []
        }
    
    # Get usage summary for current month
    today = timezone.now().date()
    start_of_month = today.replace(day=1)
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_of_month,
        end_date=today
    )
    
    # Calculate usage percentages with safety checks
    voice_minutes_percentage = min(round((usage_summary.get('total', {}).get('voice_minutes', 0) / subscription_data['voice_minutes_limit']) * 100, 0), 100) if subscription_data['voice_minutes_limit'] > 0 else 0
    sms_messages_percentage = min(round((usage_summary.get('total', {}).get('sms_messages', 0) / subscription_data['sms_messages_limit']) * 100, 0), 100) if subscription_data['sms_messages_limit'] > 0 else 0
    agents_percentage = min(round((usage_summary.get('total', {}).get('active_agents', 0) / subscription_data['agents_limit']) * 100, 0), 100) if subscription_data['agents_limit'] > 0 else 0
    leads_percentage = min(round((usage_summary.get('total', {}).get('leads_generated', 0) / subscription_data['leads_limit']) * 100, 0), 100) if subscription_data['leads_limit'] > 0 else 0
    cleaners_percentage = min(round((usage_summary.get('total', {}).get('cleaners', 0) / subscription_data['cleaners_limit']) * 100, 0), 100) if subscription_data['cleaners_limit'] > 0 else 0
    # Get recent activities (calls and SMS)
    recent_activities = UsageService.get_recent_activities(business, limit=10)
    
    # Calculate average call duration properly
    total_calls = RetellAPIService.list_calls(business=business, limit=100)
    total_calls_count = len(total_calls)
    total_minutes = usage_summary.get('total', {}).get('voice_minutes', 0)
    avg_duration = f"{round(total_minutes / total_calls_count, 1)}m" if total_calls_count > 0 else "0m"
    
    context = {
        'active_page': 'usage_overview',
        'title': 'Usage Overview',
        'subscription': subscription_data,
        'usage': {
            'voice_minutes': {
                'used': int(total_minutes),
                'limit': subscription_data['voice_minutes_limit'],
                'percentage': voice_minutes_percentage
            },
            'sms_messages': {
                'used': usage_summary.get('total', {}).get('sms_messages', 0),
                'limit': subscription_data['sms_messages_limit'],
                'percentage': sms_messages_percentage
            },
            'agents': {
                'used': usage_summary.get('total', {}).get('active_agents', 0),
                'limit': subscription_data['agents_limit'],
                'percentage': agents_percentage
            },
            'leads': {
                'used': usage_summary.get('total', {}).get('leads_generated', 0),
                'limit': subscription_data['leads_limit'],
                'percentage': leads_percentage
            },
            'cleaners': {
                'used': usage_summary.get('total', {}).get('cleaners', 0),
                'limit': subscription_data['cleaners_limit'],
                'percentage': cleaners_percentage
            }
        },
        # Voice module key metrics
        'voice_metrics': {
            'total_calls': total_calls_count,
            'total_minutes': usage_summary.get('total', {}).get('voice_minutes', 0),
            'avg_duration': avg_duration,
            'success_rate': f"{round(usage_summary.get('total', {}).get('successful_calls', 0) / total_calls_count * 100 if total_calls_count > 0 else 0)}%"
        },
        # SMS module key metrics
        'sms_metrics': {
            'total_messages': usage_summary.get('total', {}).get('sms_messages', 0),
            'response_rate': f"{round(usage_summary.get('total', {}).get('sms_responses', 0) / usage_summary.get('total', {}).get('sms_messages', 1) * 100 if usage_summary.get('total', {}).get('sms_messages', 0) > 0 else 0)}%",
            'avg_response_time': f"{usage_summary.get('total', {}).get('avg_response_time', 0)}s",
            'conversion_rate': f"{round(usage_summary.get('total', {}).get('sms_conversions', 0) / usage_summary.get('total', {}).get('sms_messages', 1) * 100 if usage_summary.get('total', {}).get('sms_messages', 0) > 0 else 0)}%"
        },
        # Recent activities
        'recent_activities': recent_activities
    }
    
    return render(request, 'usage_analytics/overview.html', context)

@login_required
def voice_analytics(request):
    """View for voice analytics dashboard."""
    business = request.user.business_set.first()
    
    # Get the current subscription for the business
    subscription = business.active_subscription()
    
    # Prepare context with only the subscription data
    context = {
        'subscription': subscription,
    }
    
    return render(request, 'usage_analytics/voice_analytics.html', context)

@login_required
def get_voice_analytics(request):
    """API endpoint to retrieve voice analytics summary data."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            # Handle different date formats
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                start_date = datetime.strptime(start_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = (timezone.now() - timedelta(days=30)).date()
            
        if end_date_str:
            # Handle different date formats
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                end_date = datetime.strptime(end_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
            
        print(f"Voice Analytics - Date range: {start_date} to {end_date}")
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        print(f"Received start_date: {start_date_str}")
        print(f"Received end_date: {end_date_str}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get usage summary for the date range
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get call data from Retell API
    from .services.retell_api_service import RetellAPIService
    calls = RetellAPIService.list_calls(
        business=business, 
        start_date=start_date, 
        end_date=end_date,
        limit=100
    )
    
    # Calculate metrics
    total_calls = len(calls)
    total_data = usage_summary.get('total', {})
    total_voice_minutes = int(total_data.get('voice_minutes', 0))  # Convert to integer to remove decimal points
    
    # Calculate average call duration
    avg_duration = round(total_voice_minutes / total_calls, 1) if total_calls > 0 else 0
    
    # Prepare the response data with just the summary metrics
    response_data = {
        'total_calls': total_calls,
        'total_minutes': total_voice_minutes,
        'avg_duration': avg_duration,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    }
    
    return JsonResponse(response_data)

@login_required
def get_call_outcomes(request):
    """API endpoint to get call outcomes data with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Get call outcomes distribution
    call_outcomes = RetellAPIService.get_call_outcomes(calls)
    
    # Calculate percentages for the frontend
    total_calls = sum(call_outcomes.values())
    call_outcomes_percentage = {}
    
    if total_calls > 0:
        for outcome, count in call_outcomes.items():
            call_outcomes_percentage[outcome] = round((count / total_calls) * 100, 0)
    else:
        call_outcomes_percentage = {
            "completed": 0,
            "failed": 0,
            "no_answer": 0,
            "busy": 0
        }
    
    # Return the data
    return JsonResponse({
        'call_outcomes': call_outcomes,
        'call_outcomes_percentage': call_outcomes_percentage,
        'total_calls': total_calls,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_call_duration_distribution(request):
    """API endpoint to get call duration distribution data with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Get call duration distribution
    duration_distribution = RetellAPIService.get_call_duration_distribution(calls)
    
    # Return the data
    return JsonResponse({
        'call_duration_distribution': duration_distribution,
        'total_calls': len(calls),
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_call_success_rate(request):
    """API endpoint to get call success rate with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Calculate success rate
    success_rate = RetellAPIService.calculate_success_rate(calls)
    
    # Return the data
    return JsonResponse({
        'success_rate': success_rate,
        'total_calls': len(calls),
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_disconnection_reasons(request):
    """API endpoint to get call disconnection reason distribution with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Get disconnection reason distribution
    disconnection_reasons = RetellAPIService.get_disconnection_reasons(calls)
    
    # Calculate percentages for the frontend
    total_calls_with_reasons = sum(disconnection_reasons.values())
    disconnection_reasons_percentage = {}
    
    if total_calls_with_reasons > 0:
        for reason, count in disconnection_reasons.items():
            disconnection_reasons_percentage[reason] = round((count / total_calls_with_reasons) * 100, 1)
    
    # Return the data
    return JsonResponse({
        'disconnection_reasons': disconnection_reasons,
        'disconnection_reasons_percentage': disconnection_reasons_percentage,
        'total_calls': len(calls),
        'total_calls_with_reasons': total_calls_with_reasons,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def sms_analytics(request):
    """Detailed SMS analytics page."""
    business = request.user.business_set.first()
    
    # Get the current subscription for the business
    subscription = business.active_subscription()
    
    # Prepare context with only the subscription data
    context = {
        'subscription': subscription,
    }
    
    return render(request, 'usage_analytics/sms_analytics.html', context)

@login_required
def get_sms_analytics(request):
    """API endpoint to retrieve SMS analytics summary data."""
    business = request.user.business_set.first()
    subscription = business.active_subscription()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            start_date = (timezone.now() - timedelta(days=30)).date()
        
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()

    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        print(f"Received start_date: {start_date_str}")
        print(f"Received end_date: {end_date_str}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    try:
        # Get usage summary from UsageTracker
        usage_summary = UsageTracker.get_usage_summary(
            business=business,
            start_date=start_date,
            end_date=end_date
        )
        
        # Get total SMS messages from usage summary
        total_messages = usage_summary.get('total', {}).get('sms_messages', 0)
        
        # Calculate conversion rate by checking chat status
        from ai_agent.models import Chat
        
        # Convert dates to datetime for proper filtering
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get all chats for this business within the date range
        total_chats = Chat.objects.filter(
            business=business,
            createdAt__gte=start_datetime,
            createdAt__lte=end_datetime
        ).count()
        
        # Get chats with status 'booked'
        booked_chats = Chat.objects.filter(
            business=business,
            createdAt__gte=start_datetime,
            createdAt__lte=end_datetime,
            status='booked'
        ).count()
        
        # Calculate conversion rate
        conversion_rate = round((booked_chats / total_chats * 100), 1) if total_chats > 0 else 0
        
        print(f"DEBUG: Total chats: {total_chats}, Booked chats: {booked_chats}, Conversion rate: {conversion_rate}%")
        
        # Prepare response data
        response_data = {
            'total_messages': total_messages,
            'conversion_rate': {
                'value': conversion_rate,
                'unit': '%'
            },
            'total_chats': total_chats,
            'booked_chats': booked_chats,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            },
            'subscription': {
                'start_date': subscription.start_date.strftime('%Y-%m-%d'),
                'end_date': subscription.next_billing_date.strftime('%Y-%m-%d')
            }
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        print(f"Error in get_sms_analytics: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_usage_data(request):
    """API endpoint to retrieve usage data for charts and metrics."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            # Handle different date formats
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                start_date = datetime.strptime(start_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = (timezone.now() - timedelta(days=30)).date()
            
        if end_date_str:
            # Handle different date formats
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                end_date = datetime.strptime(end_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
            
        print(f"Parsed date range: {start_date} to {end_date}")
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        print(f"Received start_date: {start_date_str}")
        print(f"Received end_date: {end_date_str}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get usage summary for the date range
    usage_summary = UsageTracker.get_usage_summary(
        business=business,
        start_date=start_date,
        end_date=end_date
    )
    
    # Get daily metrics for charts
    dates = []
    voice_minutes_data = []
    sms_messages_data = []
    agents_data = []
    leads_data = []
    cleaners_data = []
    
    # Process daily data from usage summary
    daily_data = usage_summary.get('daily', [])
    
    # Create a dictionary to map dates to their data for easier lookup
    daily_data_dict = {}
    for entry in daily_data:
        date_str = entry['date'].strftime('%Y-%m-%d') if hasattr(entry['date'], 'strftime') else entry['date']
        daily_data_dict[date_str] = entry['metrics']
    
    current_date = start_date
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(date_str)
        
        # Get metrics for the current date if available
        day_data = daily_data_dict.get(date_str, {})
        voice_minutes_data.append(day_data.get('voice_minutes', 0))
        sms_messages_data.append(day_data.get('sms_messages', 0))
        agents_data.append(day_data.get('active_agents', 0))
        leads_data.append(day_data.get('leads_generated', 0))
        cleaners_data.append(day_data.get('cleaners', 0))
        current_date += timedelta(days=1)
    
    # Get current subscription using the active_subscription method
    subscription = business.active_subscription()
    
    if subscription and subscription.is_subscription_active():
        # Get features from M2M relationship
        features = subscription.plan.features.filter(is_active=True)
        feature_list = [feature.name for feature in features]
        
        subscription_data = {
            'name': subscription.plan.name,
            'price': float(subscription.plan.price),
            'status': subscription.status,
            'next_billing_date': subscription.next_billing_date.strftime('%Y-%m-%d') if subscription.next_billing_date else None,
            'start_date': subscription.start_date.strftime('%Y-%m-%d'),
            'voice_minutes_limit': subscription.plan.voice_minutes,
            'sms_messages_limit': subscription.plan.sms_messages,
            'agents_limit': subscription.plan.agents,
            'leads_limit': subscription.plan.leads,
            'cleaners_limit': subscription.plan.cleaners,
            'features': feature_list
        }
    else:
        subscription_data = {
            'name': 'No Active Plan',
            'price': 0,
            'status': 'inactive',
            'next_billing_date': None,
            'start_date': None,
            'voice_minutes_limit': 0,
            'sms_messages_limit': 0,
            'agents_limit': 0,
            'leads_limit': 0,
            'cleaners_limit': 0,
            'features': []
        }
    
    # Get recent activities
    recent_activities = UsageService.get_recent_activities(business, limit=10)
    activity_data = []
    
    for activity in recent_activities:
        activity_data.append({
            'type': activity.get('type'),
            'contact': activity.get('contact'),
            'status': activity.get('status'),
            'timestamp': activity.get('timestamp').strftime('%Y-%m-%d %H:%M:%S') if activity.get('timestamp') else None,
            'preview': activity.get('preview', ''),
            'duration': activity.get('duration', 'N/A')
        })
    
    # Get call data from Retell API
    from .services.retell_api_service import RetellAPIService
    total_calls = RetellAPIService.list_calls(business=business, limit=100, start_date=start_date, end_date=end_date)
    total_calls_count = len(total_calls)
    
    # Calculate metrics
    total_data = usage_summary.get('total', {})
    total_voice_minutes = total_data.get('voice_minutes', 0)
    total_sms_messages = total_data.get('sms_messages', 0)
    total_agents = total_data.get('active_agents', 0)
    print(f"Total Agents - GET USAGE DATA: {total_agents}")
    total_leads = total_data.get('leads_generated', 0)
    total_cleaners = total_data.get('cleaners', 0)
    # Calculate average call duration
    avg_duration = f"{round(total_voice_minutes / total_calls_count, 1)}m" if total_calls_count > 0 else "0m"
    
    # Prepare the response data
    response_data = {
        'dates': dates,
        'voice_minutes': voice_minutes_data,
        'sms_messages': sms_messages_data,
        'agents': agents_data,
        'leads': leads_data,
        'cleaners': cleaners_data,
        'subscription': subscription_data,
        'usage_summary': usage_summary,
        'recent_activities': activity_data,
        'voice_metrics': {
            'total_calls': total_calls_count,
            'total_minutes': total_voice_minutes,
            'avg_duration': avg_duration,
            'success_rate': f"{round(total_data.get('successful_calls', 0) / total_calls_count * 100 if total_calls_count > 0 else 0)}%"
        },
        'sms_metrics': {
            'total_messages': total_sms_messages,
            'response_rate': f"{round(total_data.get('sms_responses', 0) / total_sms_messages * 100 if total_sms_messages > 0 else 0)}%",
            'avg_response_time': f"{total_data.get('avg_response_time', 0)}s",
            'conversion_rate': f"{round(total_data.get('sms_conversions', 0) / total_sms_messages * 100 if total_sms_messages > 0 else 0)}%"
        },
        'agent_metrics': {
            'total_agents': total_agents,
            'usage_percentage': f"{round(total_agents / subscription_data['agents_limit'] * 100 if subscription_data['agents_limit'] > 0 else 0)}%",
            'features_count': len(subscription_data['features'])
        },
        'lead_metrics': {
            'total_leads': total_leads,
            'usage_percentage': f"{round(total_leads / subscription_data['leads_limit'] * 100 if subscription_data['leads_limit'] > 0 else 0)}%",
            'conversion_rate': f"{round(total_data.get('lead_conversions', 0) / total_leads * 100 if total_leads > 0 else 0)}%"
        },
        'cleaner_metrics': {
            'total_cleaners': total_cleaners,
            'usage_percentage': f"{round(total_cleaners / subscription_data['cleaners_limit'] * 100 if subscription_data['cleaners_limit'] > 0 else 0)}%",
            'features_count': len(subscription_data['features'])
        }
    }
    
    return JsonResponse(response_data)

@login_required
def get_sentiment_distribution(request):
    """API endpoint to get user sentiment distribution with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Get sentiment distribution
    sentiment_distribution = RetellAPIService.get_sentiment_distribution(calls)
    
    # Calculate percentages for the frontend
    total_calls = len(calls)
    sentiment_distribution_percentage = {}
    
    if total_calls > 0:
        for sentiment, count in sentiment_distribution.items():
            sentiment_distribution_percentage[sentiment] = round((count / total_calls) * 100, 1)
    
    # Return the data
    return JsonResponse({
        'sentiment_distribution': sentiment_distribution,
        'sentiment_distribution_percentage': sentiment_distribution_percentage,
        'total_calls': total_calls,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_call_success_distribution(request):
    """API endpoint to get call success distribution with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=200  # Increase limit to get more accurate statistics
    )
    
    # Get call success distribution
    success_distribution = RetellAPIService.get_call_success_distribution(calls)
    
    # Calculate percentages for the frontend
    total_calls = len(calls)
    success_distribution_percentage = {}
    
    if total_calls > 0:
        for status, count in success_distribution.items():
            success_distribution_percentage[status] = round((count / total_calls) * 100, 1)
    
    # Return the data
    return JsonResponse({
        'success_distribution': success_distribution,
        'success_distribution_percentage': success_distribution_percentage,
        'total_calls': total_calls,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_recent_calls(request):
    """API endpoint to get recent calls with date range filtering."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Parse date strings to date objects
    try:
        if start_date_str:
            start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription period if available, otherwise start of month
            if hasattr(business, 'businesssubscription'):
                start_date = business.businesssubscription.start_date
            else:
                start_date = timezone.now().date().replace(day=1)
            
        if end_date_str:
            end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        else:
            # Default to subscription end date if available, otherwise today
            if hasattr(business, 'businesssubscription'):
                end_date = business.businesssubscription.end_date
            else:
                end_date = timezone.now().date()
    except ValueError:
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Convert date objects to datetime objects for Retell API
    start_datetime = datetime.combine(start_date, datetime.min.time())
    end_datetime = datetime.combine(end_date, datetime.max.time())
    
    # Get call data from Retell API with a limit for recent calls
    calls = RetellAPIService.list_calls(
        business=business,
        start_date=start_datetime,
        end_date=end_datetime,
        limit=20  # Limit to the most recent calls
    )
    
    # Get detailed call information
    call_details = RetellAPIService.get_call_details(calls)
    
    # Return the data
    return JsonResponse({
        'recent_calls': call_details,
        'total_calls': len(calls),
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    })

@login_required
def get_call_volume(request):
    """API endpoint to retrieve call volume data for the chart."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        if start_date_str:
            # Handle different date formats
            try:
                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                start_date = datetime.strptime(start_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            # Default to last 30 days
            start_date = (timezone.now() - timedelta(days=30)).date()
            
        if end_date_str:
            # Handle different date formats
            try:
                end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
            except ValueError:
                # Try alternative format
                end_date = datetime.strptime(end_date_str.split(' ')[0], '%Y-%m-%d').date()
        else:
            end_date = timezone.now().date()
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    # Get call data from Retell API
    from .services.retell_api_service import RetellAPIService
    calls = RetellAPIService.list_calls(
        business=business, 
        start_date=start_date, 
        end_date=end_date,
        limit=100
    )
    
    # Calculate daily call volume
    dates = []
    call_volume = []
    voice_minutes = []
    
    current_date = start_date
    daily_calls = {}
    daily_minutes = {}
    
    # Group calls by date
    for call in calls:
        call_date = datetime.fromtimestamp(call.get('start_timestamp', 0) / 1000).date()
        date_str = call_date.strftime('%Y-%m-%d')
        
        # Count calls
        if date_str in daily_calls:
            daily_calls[date_str] += 1
        else:
            daily_calls[date_str] = 1
        
        # Sum minutes
        duration_ms = call.get('duration', 0)  # Duration in milliseconds
        duration_min = duration_ms / (1000 * 60)  # Convert to minutes
        
        if date_str in daily_minutes:
            daily_minutes[date_str] += duration_min
        else:
            daily_minutes[date_str] = duration_min
    
    # Fill in the date range
    while current_date <= end_date:
        date_str = current_date.strftime('%Y-%m-%d')
        dates.append(date_str)
        call_volume.append(daily_calls.get(date_str, 0))
        voice_minutes.append(int(round(daily_minutes.get(date_str, 0))))  # Round to integer
        current_date += timedelta(days=1)
    
    # Prepare the response data
    response_data = {
        'dates': dates,
        'call_volume': call_volume,
        'voice_minutes': voice_minutes,
        'date_range': {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
    }
    
    return JsonResponse(response_data)

@login_required
def get_sms_volume(request):
    """API endpoint to retrieve SMS message volume data for the chart."""
    business = request.user.business_set.first()
    
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    try:
        # Get usage summary from UsageTracker
        usage_summary = UsageTracker.get_usage_summary(
            business=business,
            start_date=start_date,
            end_date=end_date
        )
        
        # Calculate daily SMS message volume from the daily breakdown
        dates = []
        sms_volume = []
        
        # Create a dictionary to map dates to their SMS message counts
        daily_sms = {}
        
        # Process daily data from the usage summary
        for daily_entry in usage_summary.get('daily', []):
            date_obj = daily_entry.get('date')
            if date_obj:
                date_str = date_obj.strftime('%Y-%m-%d')
                metrics = daily_entry.get('metrics', {})
                daily_sms[date_str] = int(metrics.get('sms_messages', 0))
        
        # Fill in the date range with zeros for missing dates
        current_date = start_date
        while current_date <= end_date:
            date_str = current_date.strftime('%Y-%m-%d')
            dates.append(date_str)
            sms_volume.append(daily_sms.get(date_str, 0))
            current_date += timedelta(days=1)
        
        # Prepare the response data
        response_data = {
            'dates': dates,
            'sms_volume': sms_volume,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        print(f"Error in get_sms_volume: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_sms_response_rate(request):
    """API endpoint to retrieve SMS response rate data."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    try:
        # Import needed models
        from ai_agent.models import Chat, Messages
        
        # Convert dates to datetime for proper filtering
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get all chats for this business within the date range
        chats = Chat.objects.filter(
            business=business,
            createdAt__gte=start_datetime,
            createdAt__lte=end_datetime
        )
        
        total_assistant_messages = 0
        total_user_responses = 0
        
        # Process each chat
        for chat in chats:
            # Get all messages in this chat ordered by creation time
            messages = Messages.objects.filter(chat=chat).order_by('createdAt')
            
            # Track the last role to identify response patterns
            last_role = None
            
            for message in messages:
                if message.role == 'assistant':
                    total_assistant_messages += 1
                    last_role = 'assistant'
                elif message.role == 'user' and last_role == 'assistant':
                    # This is a user responding to an assistant message
                    total_user_responses += 1
                    last_role = 'user'
                elif message.role == 'user':
                    last_role = 'user'
        
        # Calculate response rate
        response_rate = (total_user_responses / total_assistant_messages * 100) if total_assistant_messages > 0 else 0
        response_rate = round(response_rate, 1)
        
        print(f"DEBUG: Total assistant messages: {total_assistant_messages}, Total user responses: {total_user_responses}")
        print(f"DEBUG: Response rate: {response_rate}%")
        
        # Prepare response data
        response_data = {
            'response_rate': {
                'value': response_rate,
                'unit': '%'
            },
            'total_messages': total_assistant_messages,
            'total_responses': total_user_responses,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }

        print("SMS response rate data:", response_data)
        
        return JsonResponse(response_data)
    except Exception as e:
        print(f"Error in get_sms_response_rate: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_sms_response_time(request):
    """API endpoint to retrieve SMS response time data."""
    business = request.user.business_set.first()
    
    # Parse date range from request
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
    end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
    
    try:
        # Get usage summary from UsageTracker
        from ai_agent.models import Chat, Messages
        
        # Convert dates to datetime for proper filtering
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get all chats for this business within the date range
        chats = Chat.objects.filter(
            business=business,
            createdAt__gte=start_datetime,
            createdAt__lte=end_datetime
        )
        
        # Track response times
        response_times = []
        total_response_time = 0
        total_responses = 0
        
        # Process each chat
        for chat in chats:
            # Get all messages in this chat ordered by creation time
            messages = list(Messages.objects.filter(chat=chat).order_by('createdAt'))
            
            # Need at least 2 messages to calculate response time
            if len(messages) < 2:
                continue
            
            # Track the last assistant message time
            last_assistant_msg_time = None
            
            # Analyze message sequence to find response times
            for message in messages:
                if message.role == 'assistant':
                    last_assistant_msg_time = message.createdAt
                elif message.role == 'user' and last_assistant_msg_time:
                    # Calculate time difference in seconds
                    time_diff = (message.createdAt - last_assistant_msg_time).total_seconds()
                    
                    # Only count reasonable response times (less than 24 hours)
                    if 0 < time_diff < 86400:  # 86400 seconds = 24 hours
                        response_times.append(time_diff)
                        total_response_time += time_diff
                        total_responses += 1
                        
                    # Reset after finding a response
                    last_assistant_msg_time = None
        
        # Calculate overall average response time in minutes
        overall_avg_response_time = round(total_response_time / total_responses / 60) if total_responses > 0 else 0
        
        print(f"DEBUG: Total responses: {total_responses}, Total response time: {total_response_time}")
        
        # Get response time distribution from actual data
        response_time_distribution = {}
        
        # Define time buckets (in minutes)
        time_buckets = {
            'under_5min': 0,
            '5_15min': 0,
            '15_30min': 0,
            '30_60min': 0,
            'over_60min': 0
        }
        
        # Categorize response times into buckets
        for time_in_seconds in response_times:
            time_in_minutes = time_in_seconds / 60
            
            if time_in_minutes < 5:
                time_buckets['under_5min'] += 1
            elif time_in_minutes < 15:
                time_buckets['5_15min'] += 1
            elif time_in_minutes < 30:
                time_buckets['15_30min'] += 1
            elif time_in_minutes < 60:
                time_buckets['30_60min'] += 1
            else:
                time_buckets['over_60min'] += 1
        
        # Calculate percentages for each bucket
        for bucket, count in time_buckets.items():
            percentage = (count / total_responses * 100) if total_responses > 0 else 0
            response_time_distribution[bucket] = round(percentage, 1)
        
        # Prepare the response data
        response_data = {
            'avg_response_time': {
                'value': overall_avg_response_time,
                'unit': 'min'
            },
            'response_time_distribution': response_time_distribution,
            'total_responses': total_responses,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }
        
        return JsonResponse(response_data)
    except Exception as e:
        print(f"Error in get_sms_response_time: {str(e)}")
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def get_recent_sms_messages(request):
    """API endpoint to retrieve recent SMS messages."""
    business = request.user.business_set.first()
    
    # Get date range parameters
    start_date_str = request.GET.get('start_date')
    end_date_str = request.GET.get('end_date')
    
    # Get current subscription
    subscription = business.active_subscription()
    

    
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()
        
    except ValueError as e:
        print(f"Date parsing error: {str(e)}")
        return JsonResponse({'error': 'Invalid date format'}, status=400)
    
    try:
        # Convert date objects to datetime objects for querying
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.max.time())
        
        # Get SMS messages from the database
        # Assuming you have a Message model or similar
        from ai_agent.models import Messages

        
        messages = Messages.objects.filter(
            chat__business=business,
            createdAt__gte=start_datetime,
            createdAt__lte=end_datetime
        ).order_by('-createdAt')[:10]  # Get the 10 most recent messages
        
        # Format the messages for the response
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'contact': msg.chat.clientPhoneNumber,
                'message_preview': msg.message[:100] + '...' if len(msg.message) > 100 else msg.message,
                'sent_at': msg.createdAt.strftime('%b %d, %Y, %I:%M %p'),
                'is_today': msg.createdAt.date() == timezone.now().date(),
                'is_yesterday': msg.createdAt.date() == (timezone.now().date() - timedelta(days=1))
            })

        # If no messages found, return an empty list (not dummy data)
        if not message_list:
            return JsonResponse({
                'messages': [],
                'date_range': {
                    'start_date': start_date.strftime('%Y-%m-%d'),
                    'end_date': end_date.strftime('%Y-%m-%d')
                }
            })
        
        return JsonResponse({
            'messages': message_list,
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        })
    except Exception as e:
        print(f"Error in get_recent_sms_messages: {str(e)}")
        # Return an empty list instead of dummy data
        return JsonResponse({
            'messages': [],
            'error': str(e),
            'date_range': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
        }, status=500)

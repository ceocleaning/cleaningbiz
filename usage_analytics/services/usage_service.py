from django.utils import timezone
from datetime import datetime, timedelta
from subscription.models import UsageTracker
from django.utils.timezone import make_aware, is_aware
import requests
import json
import logging
from django.conf import settings
from retell_agent.models import RetellAgent

logger = logging.getLogger(__name__)

class UsageService:
    """Service class for tracking and retrieving usage metrics."""
    
    @staticmethod
    def track_voice_call(business, duration_seconds=0):
        """
        Track a voice call usage.
        
        Args:
            business: The business making the call
            duration_seconds: Duration of the call in seconds
        """
        # Track call count
        UsageTracker.increment_metric(
            business=business,
            metric_name='voice_calls',
            increment_by=1
        )
        
        # Track call minutes (rounded up to nearest minute)
        minutes = (duration_seconds + 59) // 60  # Round up
        if minutes > 0:
            UsageTracker.increment_metric(
                business=business,
                metric_name='voice_minutes',
                increment_by=minutes
            )
        
        return True
    
    @staticmethod
    def track_sms_message(business, count=1):
        """
        Track SMS message usage.
        
        Args:
            business: The business sending the message
            count: Number of messages to track
        """
        UsageTracker.increment_metric(
            business=business,
            metric_name='sms_messages',
            increment_by=count
        )
        
        return True
    
    @staticmethod
    def track_active_agent(business, count=1):
        """
        Track active Retell agent usage.
        
        Args:
            business: The business using the agent
            count: Number of agents to track (default: 1)
        """
        UsageTracker.increment_agents(
            business=business,
            increment_by=count
        )
        
        return True
    
    @staticmethod
    def track_lead_generated(business, count=1):
        """
        Track leads generated.
        
        Args:
            business: The business generating the lead
            count: Number of leads to track (default: 1)
        """
        UsageTracker.increment_leads(
            business=business,
            increment_by=count
        )
        
        return True
    
    @staticmethod
    def check_voice_minutes_limit(business):
        """
        Check if a business has exceeded its voice minutes limit.
        
        Args:
            business: The business to check
            
        Returns:
            Dict with limit details
        """
        import traceback
        
        try:
            # Get active subscription
            active_subscription = business.active_subscription()
            
            # If no subscription, return no limit exceeded
            if not active_subscription:
                print(f"[DEBUG] No active subscription found for {business.businessName}")
                return {
                    'limit': 0,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get plan
            plan = active_subscription.plan
            voice_minutes_limit = getattr(plan, 'voice_minutes', 0)
            
            if voice_minutes_limit <= 0:  # No limit or invalid limit
                return {
                    'limit': voice_minutes_limit,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get usage data
            start_date = active_subscription.start_date
            end_date = active_subscription.end_date
            usage = UsageTracker.get_usage_summary(
                business=business,
                start_date=start_date,
                end_date=end_date
            )
                
            voice_minutes_used = usage.get('total', {}).get('voice_minutes', 0)
            exceeded = voice_minutes_used > voice_minutes_limit
            
            print(f"[DEBUG] Voice minutes: Used {voice_minutes_used}/{voice_minutes_limit} - Exceeded: {exceeded}")
            
            return {
                'limit': voice_minutes_limit,
                'used': voice_minutes_used,
                'exceeded': exceeded
            }
        except Exception as e:
            print(f"[ERROR] Error checking voice minutes limit: {str(e)}")
            print(traceback.format_exc())
            return {
                'limit': 0,
                'used': 0,
                'exceeded': False,
                'error': str(e)
            }
    
    @staticmethod
    def check_sms_messages_limit(business):
        """
        Check if a business has exceeded its SMS messages limit.
        
        Args:
            business: The business to check
            
        Returns:
            Dict with limit details
        """
        import traceback
        from subscription.models import BusinessSubscription
        from datetime import datetime
        
        try:
            # Get active subscription
            active_subscription = business.active_subscription()
            
            # If no subscription, return no limit exceeded
            if not active_subscription:
                print(f"[DEBUG] No active subscription found for {business.businessName}")
                return {
                    'limit': 0,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get plan
            plan = active_subscription.plan
            sms_messages_limit = plan.sms_messages
            
            if sms_messages_limit <= 0:  # No limit or invalid limit
                return {
                    'limit': sms_messages_limit,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get usage data
            start_date = active_subscription.start_date
            end_date = active_subscription.end_date
            usage = UsageTracker.get_usage_summary(
                business=business,
                start_date=start_date,
                end_date=end_date
            )
                
            sms_messages_used = usage.get('total', {}).get('sms_messages', 0)
            exceeded = sms_messages_used > sms_messages_limit
            
            print(f"[DEBUG] SMS messages: Used {sms_messages_used}/{sms_messages_limit} - Exceeded: {exceeded}")
            
            return {
                'limit': sms_messages_limit,
                'used': sms_messages_used,
                'exceeded': exceeded
            }
        except Exception as e:
            print(f"[ERROR] Error checking SMS messages limit: {str(e)}")
            print(traceback.format_exc())
            return {
                'limit': 0,
                'used': 0,
                'exceeded': False,
                'error': str(e)
            }
    
    @staticmethod
    def check_active_agents_limit(business):
        """
        Check if a business has exceeded its active agents limit.
        
        Args:
            business: The business to check
            
        Returns:
            Dict with limit details
        """
        import traceback
        from subscription.models import BusinessSubscription
        
        try:
            # Get active subscription
            active_subscription = business.active_subscription()
            
            # If no subscription, return no limit exceeded
            if not active_subscription:
                print(f"[DEBUG] No active subscription found for {business.businessName}")
                return {
                    'limit': 0,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get plan
            plan = active_subscription.plan
            agents_limit = getattr(plan, 'agents', 0)
            
            if agents_limit <= 0:  # No limit or invalid limit
                return {
                    'limit': agents_limit,
                    'used': 0,
                    'exceeded': False
                }
                
            # Count active agents directly from the database
            from retell_agent.models import RetellAgent
            active_agents = RetellAgent.objects.filter(business=business).count()
            exceeded = active_agents >= agents_limit
            
            print(f"[DEBUG] Active agents: Used {active_agents}/{agents_limit} - Exceeded: {exceeded}")
            
            return {
                'limit': agents_limit,
                'used': active_agents,
                'exceeded': exceeded
            }
        except Exception as e:
            print(f"[ERROR] Error checking active agents limit: {str(e)}")
            print(traceback.format_exc())
            return {
                'limit': 0,
                'used': 0,
                'exceeded': False,
                'error': str(e)
            }
    
    @staticmethod
    def check_leads_limit(business):
        """
        Check if a business has exceeded its leads limit.
        
        Args:
            business: The business to check
            
        Returns:
            Dict with limit details
        """
        import traceback
        from subscription.models import BusinessSubscription
        from datetime import datetime
        
        try:
            # Get active subscription
            active_subscription = business.active_subscription()
            
            # If no subscription, return no limit exceeded
            if not active_subscription:
                print(f"[DEBUG] No active subscription found for {business.businessName}")
                return {
                    'limit': 0,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get plan
            plan = active_subscription.plan
            leads_limit = plan.leads
            
            if leads_limit <= 0:  # No limit or invalid limit
                return {
                    'limit': leads_limit,
                    'used': 0,
                    'exceeded': False
                }
            
            # Get usage data
            start_date = active_subscription.start_date
            end_date = active_subscription.end_date
            usage = UsageTracker.get_usage_summary(
                business=business,
                start_date=start_date,
                end_date=end_date
            )

            print(f"[DEBUG] Usage data: {usage}")
                
            leads_generated = usage.get('total', {}).get('leads_generated', 0)
            exceeded = leads_generated > leads_limit
            
            print(f"[DEBUG] Leads generated: Used {leads_generated}/{leads_limit} - Exceeded: {exceeded}")
            
            return {
                'limit': leads_limit,
                'used': leads_generated,
                'exceeded': exceeded
            }
        except Exception as e:
            print(f"[ERROR] Error checking leads limit: {str(e)}")
            print(traceback.format_exc())
            return {
                'limit': 0,
                'used': 0,
                'exceeded': False,
                'error': str(e)
            }
    
    @staticmethod
    def get_business_usage(business, start_date=None, end_date=None):
        """
        Get usage metrics for a business within a date range.
        
        Args:
            business: The business to get metrics for
            start_date: Start date for metrics (default: first day of current month)
            end_date: End date for metrics (default: today)
        
        Returns:
            Dict with usage metrics
        """
        if not start_date:
            start_date = timezone.now().date().replace(day=1)
        if not end_date:
            end_date = timezone.now().date()
            
        return UsageTracker.get_usage_summary(
            business=business,
            start_date=start_date,
            end_date=end_date
        )
    
    @staticmethod
    def get_recent_activities(business, limit=10):
        """
        Get recent call and SMS activities for a business.
        
        Args:
            business: The business to get activities for
            limit: Maximum number of activities to return
            
        Returns:
            List of activity items with type, contact, status, etc.
        """
        from ai_agent.models import Messages, Chat
        
        activities = []
        
        # Get SMS messages - directly filter messages by business
        messages = Messages.objects.filter(
            chat__business=business,  # Filter messages by business directly
            role__in=['assistant', 'user']
        ).exclude(
            is_first_message=True
        ).select_related(
            'chat'  # Use select_related to optimize the query
        ).order_by(
            '-createdAt'
        )[:20]  # Get more messages initially for better mix
        
        # Process messages
        for message in messages:
            # Ensure timestamp is timezone-aware
            message_timestamp = message.createdAt
            if not is_aware(message_timestamp):
                message_timestamp = make_aware(message_timestamp)
            
            # Limit message preview to 20 characters
            preview = message.message[:20] + ('...' if len(message.message) > 20 else '')
            
            # Add message to activities
            activities.append({
                'type': 'sms',
                'contact': message.chat.clientPhoneNumber or f"WebChat: {message.chat.sessionKey}",
                'status': 'Sent' if message.role == 'assistant' else 'Received',
                'preview': preview,
                'agent': 'AI Assistant' if message.role == 'assistant' else 'Customer',
                'timestamp': message_timestamp,
                'chat_id': message.chat.id
            })
        
        # Get Retell calls
        try:
            # Get the Retell agent for this business
            agents = RetellAgent.objects.filter(business=business)
            
            if agents.exists():
                for agent in agents:
                    # Only proceed if we have an agent_id
                    if not agent.agent_id:
                        continue
                    
                    # Prepare the API request to Retell
                    headers = {
                        'Content-Type': 'application/json',
                        'Authorization': f'Bearer {settings.RETELL_API_KEY}'
                    }
                    
                    # Simplified payload with minimal filtering
                    payload = {
                        "filter_criteria": {
                            "agent_id": [agent.agent_id]
                        },
                        "sort_order": "descending",
                        "limit": 20
                    }
                    
                    try:
                        response = requests.post(
                            'https://api.retellai.com/v2/list-calls',
                            headers=headers,
                            json=payload,
                            timeout=5  # Reduced timeout for faster response
                        )
                        
                        if response.status_code == 200:
                            call_data = response.json()
                            
                            # Handle the case where the API returns a list instead of a dict with 'calls' key
                            calls = []
                            if isinstance(call_data, list):
                                calls = call_data
                            else:
                                calls = call_data.get('calls', [])
                            
                            for call in calls:
                                # Calculate call duration if timestamps are available
                                duration_seconds = 0
                                duration_text = "N/A"
                                
                                start_timestamp = call.get('start_timestamp')
                                end_timestamp = call.get('end_timestamp')
                                
                                if start_timestamp and end_timestamp:
                                    duration_seconds = (end_timestamp - start_timestamp) // 1000
                                    minutes = duration_seconds // 60
                                    seconds = duration_seconds % 60
                                    duration_text = f"{minutes}m {seconds}s"
                                
                                # Convert timestamp to datetime and ensure it's timezone-aware
                                call_time = timezone.now()  # Default to current time if no timestamp
                                if start_timestamp:
                                    # Create timezone-aware datetime
                                    naive_time = datetime.fromtimestamp(start_timestamp / 1000)
                                    call_time = make_aware(naive_time)
                                
                                # Get the phone number with proper formatting
                                to_number = call.get('to_number', 'Unknown')
                                if to_number and not to_number.startswith('+'):
                                    to_number = f"+{to_number}"
                                
                                # Determine correct status based on call data
                                status = call.get('call_status', 'Unknown')
                               
                                activities.append({
                                    'type': 'voice',
                                    'contact': to_number,
                                    'status': status,
                                    'duration': duration_text,
                                    'duration_seconds': duration_seconds,
                                    'agent': agent.agent_name,
                                    'timestamp': call_time,
                                    'call_id': call.get('call_id')
                                })
                    except requests.exceptions.RequestException:
                        # Silently handle request errors to improve performance
                        pass
        except Exception:
            # Silently handle exceptions to improve performance
            pass
        
        # Ensure all timestamps are timezone-aware before sorting
        for activity in activities:
            if not is_aware(activity['timestamp']):
                activity['timestamp'] = make_aware(activity['timestamp'])
        
        # Sort all activities by timestamp (newest first)
        activities.sort(key=lambda x: x['timestamp'], reverse=True)
        
        # Ensure we have a mix of both types in the final result
        if len(activities) > limit:
            # Get voice and SMS activities separately
            voice_activities = [a for a in activities if a['type'] == 'voice']
            sms_activities = [a for a in activities if a['type'] == 'sms']
            
            # If we have both types, ensure we include some of each
            if voice_activities and sms_activities:
                # Aim for a balanced mix, but respect the original sorting
                result = []
                voice_count = min(limit // 2, len(voice_activities))
                sms_count = min(limit - voice_count, len(sms_activities))
                
                # If we couldn't get enough SMS, add more voice
                if sms_count < limit - voice_count:
                    voice_count = min(limit - sms_count, len(voice_activities))
                
                # Add the selected activities
                result.extend(voice_activities[:voice_count])
                result.extend(sms_activities[:sms_count])
                
                # Re-sort the combined result
                result.sort(key=lambda x: x['timestamp'], reverse=True)
                
                return result
        
        # Return only the requested number of activities
        return activities[:limit]
    
    @staticmethod
    def check_usage_limits(business):
        """
        Check if a business has exceeded its usage limits.
        
        Args:
            business: The business to check
        
        Returns:
            Dict with usage status and limit information
        """
        # Get current subscription
        try:
            from subscription.models import BusinessSubscription
            subscription = BusinessSubscription.objects.filter(
                business=business,
                is_active=True
            ).latest('created_at')
            
            if not subscription or not subscription.is_subscription_active():
                return {
                    'has_active_subscription': False,
                    'limits_exceeded': True,
                    'message': 'No active subscription found.'
                }
            
            # Get current usage
            current_usage = UsageTracker.get_usage_summary(business=business)
            
            # Check limits
            voice_minutes_exceeded = current_usage['voice_minutes'] > subscription.plan.voice_minutes
            voice_calls_exceeded = current_usage['voice_calls'] > subscription.plan.voice_calls
            sms_messages_exceeded = current_usage['sms_messages'] > subscription.plan.sms_messages
            
            limits_exceeded = voice_minutes_exceeded or voice_calls_exceeded or sms_messages_exceeded
            
            return {
                'has_active_subscription': True,
                'limits_exceeded': limits_exceeded,
                'voice_minutes': {
                    'used': current_usage['voice_minutes'],
                    'limit': subscription.plan.voice_minutes,
                    'exceeded': voice_minutes_exceeded
                },
                'voice_calls': {
                    'used': current_usage['voice_calls'],
                    'limit': subscription.plan.voice_calls,
                    'exceeded': voice_calls_exceeded
                },
                'sms_messages': {
                    'used': current_usage['sms_messages'],
                    'limit': subscription.plan.sms_messages,
                    'exceeded': sms_messages_exceeded
                }
            }
            
        except BusinessSubscription.DoesNotExist:
            return {
                'has_active_subscription': False,
                'limits_exceeded': True,
                'message': 'No active subscription found.'
            }

import requests
import logging
from django.conf import settings
from datetime import datetime
from django.utils.timezone import make_aware

logger = logging.getLogger(__name__)

class RetellAPIService:
    """Service for interacting with the Retell API."""
    
    @staticmethod
    def list_calls(business, start_date=None, end_date=None, limit=100):
        """
        Retrieve call data from Retell API with filtering by business agent ID and date range.
        
        Args:
            business: The business to get calls for
            start_date: Start date for filtering (datetime object)
            end_date: End date for filtering (datetime object)
            limit: Maximum number of calls to retrieve
            
        Returns:
            List of call data dictionaries
        """
        from retell_agent.models import RetellAgent
        
        # Get all Retell agents for this business
        agents = RetellAgent.objects.filter(business=business)
        
        if not agents.exists():
            logger.warning(f"No Retell agents found for business {business.id}")
            return []
        
        # Collect all agent IDs
        agent_ids = [agent.agent_id for agent in agents if agent.agent_id]
        
        if not agent_ids:
            logger.warning(f"No valid agent IDs found for business {business.id}")
            return []
        
        # Prepare filter criteria
        filter_criteria = {
            "agent_id": agent_ids,
        }
        
        # Add date range filtering if provided
        if start_date or end_date:
            timestamp_filter = {}
            
            if start_date:
                # Convert to milliseconds timestamp
                start_timestamp = int(start_date.timestamp() * 1000)
                timestamp_filter["lower_threshold"] = start_timestamp
                
            if end_date:
                # Convert to milliseconds timestamp
                end_timestamp = int(end_date.timestamp() * 1000)
                timestamp_filter["upper_threshold"] = end_timestamp
                
            if timestamp_filter:
                filter_criteria["start_timestamp"] = timestamp_filter
        
        # Prepare the API request
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {settings.RETELL_API_KEY}'
        }
        
        payload = {
            "filter_criteria": filter_criteria,
            "sort_order": "descending",
            "limit": limit
        }
        
        try:
            response = requests.post(
                'https://api.retellai.com/v2/list-calls',
                headers=headers,
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                call_data = response.json()
                
                # Handle the case where the API returns a list instead of a dict with 'calls' key
                calls = []
                if isinstance(call_data, list):
                    calls = call_data
                else:
                    calls = call_data.get('calls', [])
                
                return calls
            else:
                logger.error(f"Error retrieving calls from Retell API: {response.text}")
                return []
                
        except requests.exceptions.RequestException as e:
            logger.exception(f"Request exception when calling Retell API: {str(e)}")
            return []
    
    @staticmethod
    def get_call_outcomes(calls):
        """
        Analyze call data to extract call outcomes distribution.
        
        Args:
            calls: List of call data from Retell API
            
        Returns:
            Dictionary with call outcome counts
        """
        outcomes = {
            "registered": 0,
            "ongoing": 0,
            "ended": 0,
            "error": 0
        }
        
        for call in calls:
            # Get the call status directly
            call_status = call.get('call_status', '').lower()
            
            if call_status == 'registered':
                outcomes['registered'] += 1
            elif call_status == 'ongoing':
                outcomes['ongoing'] += 1
            elif call_status == 'ended':
                outcomes['ended'] += 1
            elif call_status == 'error':
                outcomes['error'] += 1
            else:
                # For any unknown status, count as error
                outcomes['error'] += 1
        
        return outcomes
    
    @staticmethod
    def get_disconnection_reasons(calls):
        """
        Analyze call data to extract disconnection reason distribution.
        
        Args:
            calls: List of call data from Retell API
            
        Returns:
            Dictionary with disconnection reason counts
        """
        reasons = {
            "user_hangup": 0,
            "agent_hangup": 0,
            "call_transfer": 0,
            "voicemail_reached": 0,
            "inactivity": 0,
            "machine_detected": 0,
            "max_duration_reached": 0,
            "concurrency_limit_reached": 0,
            "no_valid_payment": 0,
            "scam_detected": 0,
            "error_inbound_webhook": 0,
            "dial_busy": 0,
            "dial_failed": 0,
            "dial_no_answer": 0,
            "other": 0
        }
        
        for call in calls:
            # Get the disconnection reason
            reason = call.get('disconnection_reason', '').lower()
            
            if reason in reasons:
                reasons[reason] += 1
            elif reason:
                reasons['other'] += 1
        
        # Remove reasons with zero counts to keep the chart clean
        return {k: v for k, v in reasons.items() if v > 0}
    
    @staticmethod
    def calculate_success_rate(calls):
        """
        Calculate call success rate based on call data.
        
        Args:
            calls: List of call data from Retell API
            
        Returns:
            Success rate as a percentage
        """
        if not calls:
            return 0
        
        successful_calls = 0
        for call in calls:
            # A call is considered successful if it has call_successful=true or if it ended normally
            call_analysis = call.get('call_analysis', {})
            call_successful = call_analysis.get('call_successful', False)
            call_status = call.get('call_status', '').lower()
            disconnection_reason = call.get('disconnection_reason', '').lower()
            
            # Count as successful if explicitly marked as successful or ended with normal reasons
            if call_successful or (call_status == 'ended' and disconnection_reason in ['user_hangup', 'agent_hangup', 'call_transfer']):
                successful_calls += 1
        
        # Calculate success rate as a percentage
        success_rate = (successful_calls / len(calls)) * 100
        return round(success_rate, 1)
    
    @staticmethod
    def get_call_duration_distribution(calls):
        """
        Analyze call data to extract call duration distribution.
        
        Args:
            calls: List of call data from Retell API
            
        Returns:
            Dictionary with duration ranges and counts
        """
        duration_distribution = {
            '< 1m': 0,
            '1-2m': 0,
            '2-3m': 0,
            '3-5m': 0,
            '5-10m': 0,
            '> 10m': 0
        }
        
        for call in calls:
            # Calculate call duration if timestamps are available
            start_timestamp = call.get('start_timestamp')
            end_timestamp = call.get('end_timestamp')
            
            if start_timestamp and end_timestamp:
                duration_seconds = (end_timestamp - start_timestamp) // 1000
                duration_minutes = duration_seconds / 60
                
                # Categorize by duration
                if duration_minutes < 1:
                    duration_distribution['< 1m'] += 1
                elif duration_minutes < 2:
                    duration_distribution['1-2m'] += 1
                elif duration_minutes < 3:
                    duration_distribution['2-3m'] += 1
                elif duration_minutes < 5:
                    duration_distribution['3-5m'] += 1
                elif duration_minutes < 10:
                    duration_distribution['5-10m'] += 1
                else:
                    duration_distribution['> 10m'] += 1
        
        return duration_distribution
    
    @staticmethod
    def get_call_details(calls):
        """Extract detailed information from calls for the recent calls table."""
        call_details = []
        
        for call in calls:
            # Extract basic call information
            call_id = call.get('call_id', 'Unknown')
            call_type = call.get('call_type', 'Unknown')
            call_status = call.get('call_status', 'Unknown')
            
            # Extract timestamps and calculate duration
            start_timestamp = call.get('start_timestamp')
            end_timestamp = call.get('end_timestamp')
            duration = 0
            
            if start_timestamp and end_timestamp:
                duration = (end_timestamp - start_timestamp) / 1000  # Convert ms to seconds
            
            # Format timestamps for display
            start_time = "N/A"
            if start_timestamp:
                start_time = datetime.fromtimestamp(start_timestamp / 1000).strftime('%b %d, %Y %I:%M %p')
            
            # Extract customer name if available
            customer_name = "Unknown"
            retell_vars = call.get('retell_llm_dynamic_variables', {})
            if retell_vars and 'customer_name' in retell_vars:
                customer_name = retell_vars.get('customer_name')
            
            # Extract call analysis data
            call_analysis = call.get('call_analysis', {})
            user_sentiment = call_analysis.get('user_sentiment', 'Unknown')
            call_successful = call_analysis.get('call_successful', False)
            call_summary = call_analysis.get('call_summary', 'No summary available')
            
            # Extract disconnection reason
            disconnection_reason = call.get('disconnection_reason', 'Unknown')
            
            # Create a formatted call detail object
            call_detail = {
                'call_id': call_id,
                'call_type': call_type,
                'call_status': call_status,
                'start_time': start_time,
                'duration': duration,
                'duration_formatted': f"{int(duration // 60)}m {int(duration % 60)}s",
                'customer_name': customer_name,
                'user_sentiment': user_sentiment,
                'call_successful': call_successful,
                'call_summary': call_summary,
                'disconnection_reason': disconnection_reason,
                'transcript': call.get('transcript', 'No transcript available'),
                'recording_url': call.get('recording_url', '')
            }
            
            call_details.append(call_detail)
        
        return call_details
        
    @staticmethod
    def get_sentiment_distribution(calls):
        """Analyze calls to extract user sentiment distribution."""
        sentiment_counts = {
            'Positive': 0,
            'Neutral': 0,
            'Negative': 0,
            'Unknown': 0
        }
        
        for call in calls:
            call_analysis = call.get('call_analysis', {})
            sentiment = call_analysis.get('user_sentiment', 'Unknown')
            
            # Map sentiment to our categories
            if sentiment in sentiment_counts:
                sentiment_counts[sentiment] += 1
            else:
                sentiment_counts['Unknown'] += 1
        
        return sentiment_counts
    
    @staticmethod
    def get_call_success_distribution(calls):
        """Analyze calls to extract call success distribution."""
        success_counts = {
            'Successful': 0,
            'Unsuccessful': 0,
            'Unknown': 0
        }
        
        for call in calls:
            call_analysis = call.get('call_analysis', {})
            call_successful = call_analysis.get('call_successful')
         
            if call_successful is True:
                success_counts['Successful'] += 1
            elif call_successful is False:
                success_counts['Unsuccessful'] += 1
            else:
                success_counts['Unknown'] += 1
        
        return success_counts

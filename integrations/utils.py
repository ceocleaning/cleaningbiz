from .models import IntegrationLog

def log_integration_activity(platform, status, request_data, response_data=None, error_message=None):
    """
    Create a log entry for integration activity.
    
    Args:
        platform: The PlatformIntegration instance
        status: String status ('success', 'failed', or 'pending')
        request_data: The data sent to the integration (dict)
        response_data: Optional response data received from the integration (dict or None)
        error_message: Optional error message if the integration failed (str or None)
    
    Returns:
        IntegrationLog: The created log entry
    """
    log_entry = IntegrationLog.objects.create(
        platform=platform,
        status=status,
        request_data=request_data,
        response_data=response_data,
        error_message=error_message
    )
    
    return log_entry 
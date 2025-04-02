from django.http import JsonResponse
from django.urls import resolve
from django.utils.deprecation import MiddlewareMixin
from .services import UsageService

class UsageLimitMiddleware(MiddlewareMixin):
    """Middleware to check if a business has exceeded their usage limits."""
    
    def process_view(self, request, view_func, view_args, view_kwargs):
        """Check usage limits before voice and SMS API requests."""
        # Skip if not authenticated
        if not request.user.is_authenticated:
            return None
            
        try:
            # Resolve the URL to get the view name
            url_name = resolve(request.path_info).url_name
            
            # Only check certain views related to voice and SMS functionality
            if url_name in ['send_sms', 'make_call', 'voice_webhook', 'sms_webhook']:
                # Get the business
                business = request.user.business_set.first()
                
                # Check usage limits
                usage_status = UsageService.check_usage_limits(business)
                
                # If limits exceeded, return error response
                if usage_status.get('limits_exceeded', False):
                    return JsonResponse({
                        'error': 'Usage limits exceeded',
                        'details': usage_status
                    }, status=402)  # 402 Payment Required
        except:
            # If any error occurs, just continue
            pass
            
        return None 
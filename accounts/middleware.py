from django.shortcuts import redirect
from django.urls import resolve, reverse
from django.contrib import messages


class BusinessApprovalMiddleware:
    """
    Middleware to check if a business is approved before allowing access to certain views.
    If the business is not approved, the user is redirected to the approval_pending page.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Skip middleware if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Get current URL name
        current_url = resolve(request.path_info).url_name
        
        # List of URLs that should be accessible without approval
        exempt_urls = [
            'login', 'logout', 'signup', 'register_business', 
            'approval_pending', 'profile', 'update_profile', 'change_password',
            'forgot_password', 'verify_otp', 'resend_otp', 'reset_password',
            'admin:index', 'admin:login'
        ]
        
        # Allow access to admin URLs
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        # Allow access to exempt URLs
        if current_url in exempt_urls:
            return self.get_response(request)
        
        # Check if user has a business
        if hasattr(request.user, 'business_set') and request.user.business_set.exists():
            business = request.user.business_set.first()
            
            # If business is not approved, redirect to approval_pending
            if not business.isApproved and current_url != 'approval_pending':
                messages.warning(request, 'Your business is pending approval. You will have access to all features once approved.')
                return redirect('accounts:approval_pending')
        
        return self.get_response(request)

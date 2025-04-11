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
            'admin:index', 'admin:login', 'manage_cleaners', 'cleaner_detail'
        ]
        
        # Allow access to admin URLs
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        # Allow access to exempt URLs
        if current_url in exempt_urls:
            return self.get_response(request)
        
        # Check if the user is a cleaner
        if hasattr(request.user, 'cleaner_profile'):
            # List of URL patterns that cleaners are allowed to access
            cleaner_allowed_patterns = [
                '/accounts/logout/',
                '/accounts/profile/change-password/',
                '/accounts/cleaners/'
            ]
            
            # Check if current path starts with allowed patterns
            path_allowed = False
            for pattern in cleaner_allowed_patterns:
                if request.path.startswith(pattern):
                    path_allowed = True
                    break
            
            # If cleaner is trying to access cleaner_detail, make sure it's their own detail page
            if current_url == 'cleaner_detail' or ('cleaners' in request.path and str(request.user.cleaner_profile.cleaner.id) in request.path):
                cleaner_id = request.user.cleaner_profile.cleaner.id
                # Allow access to their own detail page
                if str(cleaner_id) in request.path:
                    return self.get_response(request)
            
            # If path is not allowed and not their detail page, redirect
            if not path_allowed:
                messages.error(request, 'You do not have permission to access this page.')
                return redirect('cleaner_detail', cleaner_id=request.user.cleaner_profile.cleaner.id)
        
        # Check if user has a business
        if hasattr(request.user, 'business_set') and request.user.business_set.exists():
            business = request.user.business_set.first()
            
            # If business is not approved, redirect to approval_pending
            if not business.isApproved and current_url != 'approval_pending':
                messages.warning(request, 'Your business is pending approval. You will have access to all features once approved.')
                return redirect('accounts:approval_pending')
            
            # If this is a business owner, they should have access to all pages including manage_cleaners
            return self.get_response(request)
        
        return self.get_response(request)

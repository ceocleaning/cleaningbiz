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
        # Skip middleware if user is not authenticated or is admin
        if not request.user.is_authenticated or request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
            
        # Skip for cleaner users - they'll be handled by CleanerAccessMiddleware
        if hasattr(request.user, 'cleaner_profile'):
            return self.get_response(request)
            
        # List of URLs that should be accessible without approval
        exempt_urls = [
            'login', 'logout', 'signup', 'register_business', 
            'approval_pending', 'profile', 'update_profile', 'change_password',
            'forgot_password', 'verify_otp', 'resend_otp', 'reset_password',
            'admin:index', 'admin:login'
        ]
        
        # Also skip if URL is exempt or is admin URL
        try:
            current_url = resolve(request.path_info).url_name
            if current_url in exempt_urls or request.path.startswith('/admin/'):
                return self.get_response(request)
        except:
            # If URL can't be resolved, just continue
            pass
            
        # Check if user has a business
        if hasattr(request.user, 'business_set') and request.user.business_set.exists():
            business = request.user.business_set.first()
            
            # If business is not approved, redirect to approval_pending
            try:
                current_url = resolve(request.path_info).url_name
                if not business.isApproved and current_url != 'approval_pending':
                    messages.warning(request, 'Your business is pending approval. You will have access to all features once approved.')
                    return redirect('accounts:approval_pending')
            except:
                pass
        
        # Business owner with approved business - allow access to all pages
        return self.get_response(request)


class CleanerAccessMiddleware:
    """
    Middleware to restrict cleaners to only access their own pages and data.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Skip middleware if user is not authenticated or is admin
        if not request.user.is_authenticated or request.user.is_staff or request.user.is_superuser:
            return self.get_response(request)
            
        # Only process for cleaner users
        if not hasattr(request.user, 'cleaner_profile'):
            return self.get_response(request)
            
        cleaner_id = str(request.user.cleaner_profile.cleaner.id)
        
        # List of URLs that are always accessible
        exempt_urls = [
            'login', 'logout', 
            'change_password', 'LandingPage', 
            'PricingPage', 'FeaturesPage', 'AboutUsPage',
            'ContactUsPage', 'DocsPage', 'PrivacyPolicyPage', 
            'TermsOfServicePage', 'sitemap'
        ]
        
        # Check if we're already on a cleaner detail page to avoid redirect loops
        try:
            current_url = resolve(request.path_info).url_name
            
            # If on exempt URL, allow access
            if current_url in exempt_urls:
                return self.get_response(request)
                
            # If already on cleaner detail page for the correct cleaner, allow access
            if current_url == 'cleaner_detail':
                path_parts = request.path.strip('/').split('/')
                if 'cleaners' in path_parts and cleaner_id in path_parts:
                    return self.get_response(request)
        except:
            # If URL can't be resolved, continue with other checks
            pass
            
        # Check allowed path patterns
        allowed_paths = [
            '/accounts/logout/',
            '/accounts/profile/change-password/',
            '/',  # Home page
        ]
        
        for path in allowed_paths:
            if request.path.startswith(path):
                return self.get_response(request)
                
        # Allow access to cleaner's own URLs
        if '/cleaners/' in request.path and cleaner_id in request.path:
            return self.get_response(request)
            
        # Not allowed - redirect to appropriate cleaner detail page
        # Determine correct URL namespace based on current path
        if request.path.startswith('/cleaners/'):
            redirect_url = reverse('cleaner_detail', kwargs={'cleaner_id': cleaner_id})
        else:
            redirect_url = reverse('accounts:cleaner_detail', kwargs={'cleaner_id': cleaner_id})
            
        # Only show error message if not already redirecting to a cleaner detail page
        if resolve(request.path_info).url_name != 'cleaner_detail':
            messages.error(request, 'You do not have permission to access this page.')
            
        return redirect(redirect_url)

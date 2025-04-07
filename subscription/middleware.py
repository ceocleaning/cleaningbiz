from django.shortcuts import redirect
from django.contrib import messages
from django.urls import resolve

class SubscriptionRequiredMiddleware:
    """
    Middleware to check if a business has an active subscription before allowing access to landing pages.
    If the business doesn't have an active subscription, the user is redirected to the subscription selection page.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
        # Define allowed public pages that don't require subscription
        self.allowed_public_paths = [
            '/',
            '/pricing/',
            '/features/',
            '/docs/',
            '/contact-us/',
            '/about-us/',
            '/privacy-policy/',
            '/terms-of-service/',
        ]
        
        # URLs that should be accessible without a subscription
        self.exempt_urls = [
            'login', 'register', 'logout', 'signup', 'register_business', 
            'approval_pending', 'profile', 'update_profile', 'change_password',
            'forgot_password', 'verify_otp', 'resend_otp', 'reset_password',
            'admin:index', 'admin:login', 'subscription_management', 'select_plan',
            'process_payment', 'subscription_success', 'billing_history',
            'change_plan', 'cancel_subscription', 'get_subscription_data',
            'track_usage', 'home', 'contact', 'about', 'features', 'pricing', 'docs'
        ]
        
    def __call__(self, request):
        # Skip middleware if user is not authenticated
        if not request.user.is_authenticated:
            return self.get_response(request)
        
        # Get current URL name and path
        try:
            current_url = resolve(request.path_info).url_name
        except:
            current_url = None
        
        current_path = request.path
        
        # Allow access to admin URLs
        if request.path.startswith('/admin/'):
            return self.get_response(request)
        
        # Allow access to exempt URLs
        if current_url in self.exempt_urls:
            return self.get_response(request)
        
        # Allow access to subscription URLs
        if request.path.startswith('/subscription/'):
            return self.get_response(request)
            
        # Allow access to authentication URLs
        if request.path.startswith('/account/'):
            return self.get_response(request)
        
        if request.path.startswith('/admin-dashboard/'):
            return self.get_response(request)
            
        # Allow access to specified public pages
        if any(current_path == path for path in self.allowed_public_paths):
            return self.get_response(request)
            
        # Check if user has a business
        if hasattr(request.user, 'business_set') and request.user.business_set.exists():
            business = request.user.business_set.first()
            
            # Get active subscription
            subscription = business.active_subscription()
            print(subscription)
            
            # If no active subscription or subscription is not active, redirect to subscription page
            if not subscription or not subscription.is_subscription_active():
                messages.warning(request, 'You need an active subscription to access this page.')
                return redirect('subscription:subscription_management')
       
        else:
            messages.warning(request, 'You need a business account with an active subscription to access this page.')
            return redirect('subscription:subscription_management')
        
        return self.get_response(request)

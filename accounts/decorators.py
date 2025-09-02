from django.shortcuts import redirect
from django.contrib import messages
from django.http import HttpResponse
from functools import wraps

def group_required(group_name):
    """
    Decorator for views that checks if a user is in a particular group,
    redirecting to the login page if necessary.
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Check if user is authenticated
            if not request.user.is_authenticated:
                messages.error(request, 'Please log in to access this page.')
                return redirect('accounts:login')
            
            # Check if user is in the required group
            if not request.user.groups.filter(name=group_name).exists():
                messages.error(request, 'You do not have permission to access this page.')
                
                # Redirect cleaners to their detail page
                if request.user.groups.filter(name='Cleaner').exists() and hasattr(request.user, 'cleaner_profile'):
                    return redirect('accounts:cleaner_detail', cleaner_id=request.user.cleaner_profile.cleaner.id)
                    
                # Redirect owners to their profile
                if request.user.groups.filter(name='Owner').exists():
                    return redirect('accounts:profile')
                    
                # Default redirect to home
                return redirect('home')
                
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

def owner_required(view_func):
    """
    Decorator for views that require the user to be a business owner
    """
    return group_required('Owner')(view_func)

def cleaner_required(view_func):
    """
    Decorator for views that require the user to be a cleaner
    """
    return group_required('Cleaner')(view_func)

def customer_required(view_func):
    """
    Decorator for views that require the user to be a customer
    """
    return group_required('Customer')(view_func)

def owner_or_cleaner(view_func):
    """
    Decorator for views that can be accessed by both owners and cleaners
    but with different behavior based on role
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            messages.error(request, 'Please log in to access this page.')
            return redirect('accounts:login')
        
        # Check if user is in either Owner or Cleaner group
        is_owner = request.user.groups.filter(name='Owner').exists() or request.user.is_superuser
        is_cleaner = request.user.groups.filter(name='Cleaner').exists()
        
        if not (is_owner or is_cleaner):
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('home')
            
        # For cleaner detail views, ensure cleaners only access their own pages
        if is_cleaner and 'cleaner_id' in kwargs and hasattr(request.user, 'cleaner_profile'):
            # Cleaners can only access their own detail page
            cleaner_id = kwargs.get('cleaner_id')
            user_cleaner_id = request.user.cleaner_profile.cleaner.id
            
            if str(cleaner_id) != str(user_cleaner_id):
                messages.error(request, 'You can only view your own details.')
                # Use the correct URL namespace to avoid redirect loops
                return redirect('accounts:cleaner_detail', cleaner_id=user_cleaner_id)
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view 

def owner_or_customer(view_func):
    """
    Decorator for views that can be accessed by both owners and customers
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Check if user is authenticated
        if not request.user.is_authenticated:
            return redirect('landing-page')
        
        # Check if user is in either Owner or Customer group
        is_owner = request.user.groups.filter(name='Owner').exists() or request.user.is_superuser
        is_customer = request.user.groups.filter(name='Customer').exists()
        
        if not (is_owner or is_customer):
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('home')
            
        return view_func(request, *args, **kwargs)
    return _wrapped_view
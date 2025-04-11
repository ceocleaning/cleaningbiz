from django.shortcuts import redirect
from django.contrib import messages
from functools import wraps
from django.contrib.auth.decorators import login_required
from django.urls import reverse

def cleaner_or_owner(view_func):
    """
    Decorator that ensures a user is either the owner of the business or the cleaner
    whose detail is being viewed. Must be used on views with cleaner_id parameter.
    """
    @wraps(view_func)
    @login_required
    def _wrapped_view(request, cleaner_id, *args, **kwargs):
        # Check if user is a cleaner
        is_cleaner = hasattr(request.user, 'cleaner_profile')
        
        if is_cleaner:
            # Cleaners can only access their own data
            if int(cleaner_id) != request.user.cleaner_profile.cleaner.id:
                messages.error(request, 'You do not have permission to access this page.')
                # Use the automation app URL - the namespace is not needed
                return redirect('cleaner_detail', cleaner_id=request.user.cleaner_profile.cleaner.id)
        elif not request.user.business_set.exists():
            # User is neither a cleaner nor a business owner
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('home')
        
        # User is a business owner or the cleaner whose page is being accessed
        return view_func(request, cleaner_id, *args, **kwargs)
    
    return _wrapped_view 
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
        # Check if user is a cleaner by group membership and profile
        is_cleaner = request.user.groups.filter(name='Cleaner').exists() and hasattr(request.user, 'cleaner_profile')
        # Check if user is an owner
        is_owner = request.user.groups.filter(name='Owner').exists() or request.user.is_superuser
        
        if is_cleaner:
            # Cleaners can only access their own data
            if int(cleaner_id) != request.user.cleaner_profile.cleaner.id:
                messages.error(request, 'You do not have permission to access this page.')
                # Use the automation app URL - the namespace is not needed
                return redirect('cleaner_detail', cleaner_id=request.user.cleaner_profile.cleaner.id)
        elif is_owner:
            # Owners can access all pages, so we continue
            pass
        else:
            # User is neither a cleaner nor a business owner
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('home')
        
        # User is a business owner or the cleaner whose page is being accessed
        return view_func(request, cleaner_id, *args, **kwargs)
    
    return _wrapped_view 
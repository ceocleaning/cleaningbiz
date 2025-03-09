import traceback
import sys
import datetime
from django.shortcuts import render
from django.core.mail import send_mail
from django.conf import settings
from django.views.decorators.csrf import requires_csrf_token

def send_error_notification(request, error_code, error_traceback=None):
    """
    Helper function to send email notifications for all error types.
    """
    # Get request information
    path = request.path
    method = request.method
    user = request.user.username if request.user.is_authenticated else 'Anonymous'
    user_agent = request.META.get('HTTP_USER_AGENT', 'Unknown')
    ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
    
    # Get current time
    error_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Prepare email content
    subject = f'[CEO Cleaners] {error_code} Error at {path}'
    
    message = f"""A {error_code} error occurred:

Path: {path}
Method: {method}
User: {user}
IP Address: {ip_address}
User Agent: {user_agent}
Time: {error_time}
"""
    
    # Add traceback for 500 errors
    if error_traceback:
        message += f"\nTraceback:\n{error_traceback}"
    
    # Send email notification
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[settings.DEFAULT_FROM_EMAIL],  # Send to admin email
            fail_silently=True,
        )
    except Exception as e:
        # If email sending fails, we don't want to cause another error
        pass
    
    return error_time

@requires_csrf_token
def handler500(request, exception=None):
    """
    Custom 500 error handler that sends an email notification
    and renders a custom error page.
    """
    # Get the error traceback
    error_traceback = traceback.format_exception(*sys.exc_info())
    error_traceback_str = ''.join(error_traceback)
    
    # Send notification and get error time
    error_time = send_error_notification(request, '500', error_traceback_str)
    
    # Render the error page
    return render(request, 'error_page.html', {
        'error_code': '500',
        'error_time': error_time,
    }, status=500)

@requires_csrf_token
def handler404(request, exception=None):
    """
    Custom 404 error handler.
    """
    # Send notification and get error time
    error_time = send_error_notification(request, '404')
    
    return render(request, 'error_page.html', {
        'error_code': '404',
        'error_time': error_time,
    }, status=404)

@requires_csrf_token
def handler403(request, exception=None):
    """
    Custom 403 error handler.
    """
    # Send notification and get error time
    error_time = send_error_notification(request, '403')
    
    return render(request, 'error_page.html', {
        'error_code': '403',
        'error_time': error_time,
    }, status=403)

@requires_csrf_token
def handler400(request, exception=None):
    """
    Custom 400 error handler.
    """
    # Send notification and get error time
    error_time = send_error_notification(request, '400')
    
    return render(request, 'error_page.html', {
        'error_code': '400',
        'error_time': error_time,
    }, status=400)

import sys
from django.views.debug import technical_500_response
from django.conf import settings

class UserBasedExceptionMiddleware:
    """
    Middleware that displays Django's exception page even when DEBUG is False,
    ensuring template errors are always shown in detail.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        # Always show detailed error pages regardless of DEBUG setting
        if settings.DEBUG or request.user.is_superuser:
            return technical_500_response(request, *sys.exc_info())
        return None

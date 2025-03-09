from django.http import HttpResponse

def test_error_view(request):
    """
    A test view that intentionally raises an exception to test the error handling system.
    This should only be used for testing purposes and should be removed in production.
    """
    # Intentionally raise an exception
    raise Exception("This is a test exception to verify the error handling system.")
    
    # This code will never be reached
    return HttpResponse("This should never be displayed.")

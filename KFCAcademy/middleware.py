from sentry_sdk import capture_message, capture_exception
from django.core.exceptions import DisallowedHost
from django.http import JsonResponse

class SentryErrorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if 400 <= response.status_code < 600:  # Log 400 and 500 errors
            error_message = f"Error {response.status_code} occurred for path: {request.path}"
            if response.status_code >= 500:
                capture_message(error_message, level="error")
            elif response.status_code >= 400:
                capture_message(error_message, level="warning")
        return response

    def process_exception(self, request, exception):
        capture_exception(exception)  # Log the exception details
        return JsonResponse(
            {"error": "A server error occurred"},
            status=500,
        )

class HandleDisallowedHostMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
        except DisallowedHost:
            # You can log this or return a generic response
            return JsonResponse(
                {"error": "Invalid host header."},
                status=400,
            )
        return response

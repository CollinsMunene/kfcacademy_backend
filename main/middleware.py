
import logging
from rest_framework.permissions import BasePermission
from KFCAcademy.serializers import get_role_permissions
from django.utils.translation import gettext_lazy as _

from main.signals import set_current_user

import time
import traceback
import psutil

logger = logging.getLogger(__name__)

# class HasPermission(BasePermission):
#     """
#     Requires views to define:
#         required_permissions = [
#             {"action": "CREATE", "module": "INSTITUTIONS"},
#             {"action": "READ", "module": "USERS"}
#         ]
#     """

#     message = _("You do not have permission to perform this action.")

#     def has_permission(self, request, view):
#         required_permissions = getattr(view, "required_permissions", [])

#         if not required_permissions:
#             return True  # unrestricted

#         user = request.user
#         if not user or not user.is_authenticated:
#             logger.warning("Permission denied: unauthenticated user")
#             return False

#         try:
#             role_info = get_role_permissions(user)
#             # Expecting something like:
#             # role_info = {
#             #   "permissions": [
#             #       {"action": "CREATE", "module": "INSTITUTIONS", "standard": "ISO"},
#             #       {"action": "READ", "module": "USERS", "standard": "GDPR"}
#             #   ]
#             # }
#             user_permissions = role_info.get("permissions", [])
#         except Exception as e:
#             logger.error(
#                 f"Error getting role permissions for user {getattr(user, 'id', None)}: {e}"
#             )
#             return False

#         # Normalize into a set of tuples for easier checking
#         user_perm_set = {
#             (perm["action"], perm["module"], perm.get("standard"))
#             for perm in user_permissions
#         }

#         for req in required_permissions:
#             required_tuple = (
#                 req.get("action"),
#                 req.get("module"),
#                 req.get("standard"),
#             )
#             if required_tuple in user_perm_set:
#                 return True

#         logger.info(
#             f"Permission denied for user {getattr(user, 'id', None)}: "
#             f"missing {required_permissions}"
#         )
#         return False


class CurrentUserLoggingMiddleware:
    """
    Middleware to set current user in thread-local storage for logging purposes.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if hasattr(request, 'user') and request.user.is_authenticated:
            logger.info(f'[MIDDLEWARE] Setting current user: {request.user}')
            set_current_user(request.user)
        else:
            logger.info('[MIDDLEWARE] No authenticated user found, setting None')
            set_current_user(None)
        response = self.get_response(request)
        return response

class RequestTimingMiddleware:
    """
    Logs every request to Graylog with structured JSON:
    - endpoint, method, status_code, response_time_ms
    - user_id
    - exception info (if any)
    - system metrics: CPU %, memory %, optionally disk %
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        start_time = time.time()
        exception_info = None
        response = None

        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            exception_info = {
                "type": type(e).__name__,
                "message": str(e),
                "stack": traceback.format_exc()
            }
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)

            # System metrics at the time of request
            system_metrics = {
                "cpu_percent": psutil.cpu_percent(interval=None),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage("/").percent
            }

            # Build extra fields for structured logging
            extra_fields = {
                "endpoint": request.path,
                "method": request.method,
                "status_code": getattr(response, "status_code", 500),
                "response_time_ms": duration_ms,
                "user_id": getattr(request.user, "id", None),
                "cpu_percent": system_metrics["cpu_percent"],
                "memory_percent": system_metrics["memory_percent"],
                "disk_percent": system_metrics["disk_percent"]
            }

            if exception_info:
                extra_fields["exception_type"] = exception_info["type"]
                extra_fields["exception_message"] = exception_info["message"]
                extra_fields["exception_stack"] = exception_info["stack"]

            # Log with structured fields
            logger.info("Request processed", extra=extra_fields)
  
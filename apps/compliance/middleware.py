import json
from django.utils.deprecation import MiddlewareMixin


class AuditMiddleware(MiddlewareMixin):
    """Attaches request context to the current thread for signal-based audit logging."""

    _thread_locals = None

    def __init__(self, get_response):
        super().__init__(get_response)
        import threading
        AuditMiddleware._thread_locals = threading.local()

    def process_request(self, request):
        AuditMiddleware._thread_locals.request = request

    def process_response(self, request, response):
        if hasattr(AuditMiddleware._thread_locals, 'request'):
            del AuditMiddleware._thread_locals.request
        return response

    @classmethod
    def get_current_request(cls):
        if cls._thread_locals is None:
            return None
        return getattr(cls._thread_locals, 'request', None)

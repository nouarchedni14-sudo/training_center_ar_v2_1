from core.services.health_service import record_runtime_error


class SystemErrorLoggingMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_exception(self, request, exception):
        try:
            record_runtime_error(exception, request=request, source="middleware")
        except Exception:
            pass
        return None

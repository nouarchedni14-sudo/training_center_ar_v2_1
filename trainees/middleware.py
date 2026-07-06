from django.utils import translation
from django.urls import resolve

from .audit_runtime import clear_current_request, set_current_request, write_comprehensive_audit


class ForceArabicAdminMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        translation.activate('ar')
        request.LANGUAGE_CODE = 'ar'
        response = self.get_response(request)
        if hasattr(response, 'set_cookie'):
            response.set_cookie('django_language', 'ar')
        return response


def _audit_client_ip(request):
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return (request.META.get('REMOTE_ADDR') or '').strip() or None


class RequestAuditMiddleware:
    SKIP_PREFIXES = ('/static/', '/media/')
    SKIP_EXACT = ('/favicon.ico',)

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path or ''
        if path.startswith(self.SKIP_PREFIXES) or path in self.SKIP_EXACT:
            return self.get_response(request)

        set_current_request(request)
        try:
            try:
                resolver_match = resolve(path)
                view_name = resolver_match.view_name or resolver_match.url_name or ''
                kwargs = resolver_match.kwargs or {}
                object_pk = kwargs.get('pk') or kwargs.get('id') or kwargs.get('object_id') or ''
            except Exception:
                view_name = ''
                object_pk = ''

            method = (request.method or 'GET').upper()
            is_mutation = method in {'POST', 'PUT', 'PATCH', 'DELETE'}
            action = 'mutation' if is_mutation else 'screen_view'
            screen_name = view_name or path
            ip_address = _audit_client_ip(request)
            session_key = getattr(getattr(request, 'session', None), 'session_key', '') or ''
            user_agent = request.META.get('HTTP_USER_AGENT', '')

            response = None
            success = True
            status_code = None
            details = ''
            try:
                response = self.get_response(request)
                status_code = getattr(response, 'status_code', None)
                success = bool(status_code is None or status_code < 400)
                details = f'{method} {path}'
                return response
            except Exception as exc:
                success = False
                status_code = 500
                action = 'error'
                details = f'{method} {path} - {exc.__class__.__name__}: {exc}'
                raise
            finally:
                user = getattr(request, 'user', None)
                write_comprehensive_audit(
                    user=user,
                    action=action,
                    method=method,
                    status_code=status_code,
                    success=success,
                    screen_name=screen_name,
                    view_name=view_name,
                    model_label='',
                    object_pk=str(object_pk or ''),
                    object_repr='',
                    path=path,
                    query_string=request.META.get('QUERY_STRING', ''),
                    details=details,
                    ip_address=ip_address,
                    user_agent=user_agent,
                    session_key=session_key,
                )
        finally:
            clear_current_request()

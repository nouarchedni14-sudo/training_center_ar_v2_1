from __future__ import annotations

from django.shortcuts import redirect
from django.urls import reverse

from core.services.license_service import get_license_status, request_path_is_license_exempt


class LicenseEnforcementMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request_path_is_license_exempt(getattr(request, "path", "")):
            return self.get_response(request)

        user = getattr(request, "user", None)
        if not getattr(user, "is_authenticated", False):
            return self.get_response(request)
        if getattr(user, "is_superuser", False):
            return self.get_response(request)

        status = get_license_status()
        if status.get("enforcement_required") and not status.get("is_valid"):
            license_url = reverse("system_license")
            return redirect(f"{license_url}?blocked=1")
        return self.get_response(request)

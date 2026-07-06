from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.shortcuts import redirect, render

from core.models import SystemErrorLog, SystemHealthLog
from core.services.health_service import collect_health_snapshot


@login_required
@permission_required("core.view_system_health", raise_exception=True)
def system_health_view(request):
    snapshot = None

    if request.method == "POST" and request.POST.get("action") == "run_health_check":
        snapshot = collect_health_snapshot()
        if snapshot["overall_level"] == SystemHealthLog.LEVEL_OK:
            messages.success(request, "تم تشغيل فحص صحة النظام بنجاح، وكل المؤشرات الأساسية سليمة.")
        elif snapshot["overall_level"] == SystemHealthLog.LEVEL_WARNING:
            messages.warning(request, "تم تشغيل الفحص، لكن توجد ملاحظات تحتاج مراجعة.")
        else:
            messages.error(request, "تم تشغيل الفحص، وتم العثور على أخطاء تتطلب معالجة.")
        return redirect("system_health")

    latest_logs = list(SystemHealthLog.objects.all()[:20])
    if latest_logs:
        latest_by_component = {}
        for item in latest_logs:
            latest_by_component.setdefault(item.component, item)
        checks = [
            {
                "component": component,
                "label": item.component,
                "level": item.level,
                "message": item.message,
                "details": item.details,
            }
            for component, item in latest_by_component.items()
        ]
        has_error = any(item["level"] == SystemHealthLog.LEVEL_ERROR for item in checks)
        has_warning = any(item["level"] == SystemHealthLog.LEVEL_WARNING for item in checks)
        if has_error:
            overall_level = SystemHealthLog.LEVEL_ERROR
            overall_label = "آخر فحص يحتوي على أخطاء"
        elif has_warning:
            overall_level = SystemHealthLog.LEVEL_WARNING
            overall_label = "آخر فحص يحتوي على تحذيرات"
        else:
            overall_level = SystemHealthLog.LEVEL_OK
            overall_label = "آخر فحص سليم"
        snapshot = {
            "checks": checks,
            "overall_level": overall_level,
            "overall_label": overall_label,
            "ok_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_OK),
            "warning_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_WARNING),
            "error_count": sum(1 for item in checks if item["level"] == SystemHealthLog.LEVEL_ERROR),
        }

    context = {
        "title": "صحة النظام",
        "snapshot": snapshot,
        "health_logs": SystemHealthLog.objects.all()[:30],
        "error_logs": SystemErrorLog.objects.all()[:20],
    }
    return render(request, "core/system_health.html", context)

from __future__ import annotations

from pathlib import Path
import subprocess

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import FileResponse, Http404, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt

from core.forms import LicenseInfoForm, LocalUpdateUploadForm
from core.models import LicenseInfo, SystemConfiguration, SystemErrorLog, SystemHealthLog, UpdateCheckLog
from core.services.backup_service import (
    create_database_backup,
    get_backup_by_name,
    latest_backup,
    list_backups,
    restore_database_backup,
    serialize_backup,
)
from core.services.health_service import collect_health_snapshot
from core.services.license_service import get_license_status
from core.services.local_update_service import clear_pending_state, download_remote_update_and_prepare, ensure_pending_script, launch_pending_update, load_pending_state, prepare_local_update
from core.services.update_service import check_for_updates, central_update_download_headers, discover_runtime_version, sync_runtime_version_state, update_connectivity_status, update_status_summary

try:
    from launcher.runtime_state import read_runtime_state, request_shutdown
except Exception:  # noqa: BLE001
    def read_runtime_state():
        return {}

    def request_shutdown():
        return None


def _staff_user(user):
    return bool(user.is_authenticated and user.is_staff)



def _perm(user, code):
    return bool(user.is_superuser or user.has_perm(code))



def _system_permissions(user):
    return {
        "manage_settings": _perm(user, "core.manage_system_settings"),
        "check_updates": _perm(user, "core.check_system_updates"),
        "view_health": _perm(user, "core.view_system_health"),
        "manage_license": _perm(user, "core.manage_license_info"),
        "view_backup": bool(getattr(user, "is_staff", False)),
    }


@login_required
@user_passes_test(_staff_user)
def system_dashboard_view(request):
    config = SystemConfiguration.get_solo()
    perms = _system_permissions(request.user)
    pending_update = load_pending_state()
    sync_runtime_version_state(config, pending_update)
    pending_update = load_pending_state()
    update_summary = update_status_summary(config, pending_update)
    recent_logs = UpdateCheckLog.objects.all()[:5]
    recent_errors = SystemErrorLog.objects.filter(resolved=False)[:5]
    backup_file = latest_backup()

    summary = {
        **update_summary,
        "last_update_check_at": config.last_update_check_at,
        "pending_local_update": pending_update,
        "latest_backup": serialize_backup(backup_file) if backup_file else None,
        "license": LicenseInfo.get_solo(),
        "license_status": get_license_status(),
        "health_errors_count": SystemHealthLog.objects.filter(level=SystemHealthLog.LEVEL_ERROR).count(),
        "open_errors_count": SystemErrorLog.objects.filter(resolved=False).count(),
    }
    context = {
        "title": "مركز النظام",
        "config": config,
        "summary": summary,
        "system_perms": perms,
        "recent_logs": recent_logs,
        "recent_errors": recent_errors,
    }
    return render(request, "core/system_dashboard.html", context)


@login_required
@user_passes_test(_staff_user)
def system_settings_view(request):
    config = SystemConfiguration.get_solo()
    pending_update = load_pending_state()
    runtime_version = sync_runtime_version_state(config, pending_update)

    if request.method == "POST" and request.POST.get("action") == "check_updates":
        result = check_for_updates(force=True)
        if result.get("ok"):
            messages.success(request, result.get("message") or "تم فحص التحديثات بنجاح.")
        else:
            messages.warning(request, result.get("message") or "تعذر فحص التحديثات الآن.")
        return redirect("system_settings")

    logs = UpdateCheckLog.objects.all()[:10]
    context = {
        "title": "إعدادات النظام والتحديثات",
        "config": config,
        "logs": logs,
        "display_current_version": runtime_version,
        "update_connectivity": update_connectivity_status(config),
        "system_perms": _system_permissions(request.user),
        "license_status": get_license_status(),
    }
    return render(request, "core/system_settings.html", context)


@login_required
@user_passes_test(_staff_user)
def system_health_view(request):
    snapshot = None
    if request.method == "POST" and request.POST.get("action") == "run_health_check":
        snapshot = collect_health_snapshot()
        failed = [item for item in snapshot.get("checks", []) if not item.get("ok")]
        if failed:
            messages.warning(request, "تم تشغيل الفحص، ويوجد عناصر تحتاج مراجعة.")
        else:
            messages.success(request, "تم تشغيل فحص صحة النظام بنجاح.")
        return redirect("system_health")

    context = {
        "title": "صحة النظام",
        "snapshot": snapshot,
        "health_logs": SystemHealthLog.objects.all()[:30],
        "error_logs": SystemErrorLog.objects.all()[:30],
    }
    return render(request, "core/system_health.html", context)


@login_required
@user_passes_test(_staff_user)
def system_backup_view(request):
    if request.method == "POST":
        action = request.POST.get("action")
        if action == "create_backup":
            try:
                backup_file = create_database_backup()
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"فشل إنشاء النسخة الاحتياطية: {exc}")
            else:
                messages.success(request, f"تم إنشاء نسخة احتياطية جديدة: {backup_file.name}")
            return redirect("system_backup")

        if action == "restore_backup":
            filename = (request.POST.get("filename") or "").strip()
            try:
                restored = restore_database_backup(filename)
            except FileNotFoundError:
                messages.error(request, "ملف النسخة الاحتياطية المحدد غير موجود.")
            except Exception as exc:  # noqa: BLE001
                messages.error(request, f"فشل استرجاع النسخة الاحتياطية: {exc}")
            else:
                messages.success(request, f"تم استرجاع قاعدة البيانات من النسخة: {restored.name}")
            return redirect("system_backup")

    backups = [serialize_backup(item) for item in list_backups(50)]
    context = {
        "title": "النسخ الاحتياطي",
        "backups": backups,
        "latest_backup": backups[0] if backups else None,
    }
    return render(request, "core/system_backup.html", context)


@login_required
@user_passes_test(_staff_user)
def system_backup_download(request, filename: str):
    backup_path = get_backup_by_name(filename)
    if not backup_path:
        raise Http404("ملف النسخة الاحتياطية غير موجود.")
    return FileResponse(
        backup_path.open("rb"),
        as_attachment=True,
        filename=backup_path.name,
        content_type="application/octet-stream",
    )


@login_required
@user_passes_test(_staff_user)
def system_backup_download_prepare(request, filename: str):
    backup_path = get_backup_by_name(filename)
    if not backup_path:
        return JsonResponse({"ok": False, "message": "ملف النسخة الاحتياطية غير موجود."}, status=404)
    return JsonResponse({
        "ok": True,
        "message": "تم تجهيز النسخة الاحتياطية للتنزيل.",
        "download_url": request.build_absolute_uri(
            redirect("system_backup_download", filename=backup_path.name).url
        ),
        "filename": backup_path.name,
    })


@login_required
@user_passes_test(_staff_user)
def system_license_view(request):
    config = SystemConfiguration.get_solo()
    license_info = LicenseInfo.get_solo()

    if request.method == "POST":
        form = LicenseInfoForm(request.POST, instance=license_info)
        if form.is_valid():
            form.save()
            messages.success(request, "تم حفظ بيانات الترخيص بنجاح.")
            return redirect("system_license")
        messages.error(request, "تعذر حفظ بيانات الترخيص. راجع الحقول المطلوبة.")
    else:
        form = LicenseInfoForm(instance=license_info)

    license_status = get_license_status(license_info)
    if request.GET.get("blocked") == "1":
        messages.warning(request, "تم منع الوصول إلى بقية أجزاء النظام مؤقتًا لأن حالة الترخيص الحالية غير صالحة.")

    context = {
        "title": "الترخيص والنسخة",
        "config": config,
        "form": form,
        "license_status": license_status,
        "system_perms": _system_permissions(request.user),
    }
    return render(request, "core/system_license.html", context)


@login_required
@user_passes_test(_staff_user)
def system_updates_view(request):
    config = SystemConfiguration.get_solo()
    pending_update = load_pending_state()
    runtime_version = sync_runtime_version_state(config, pending_update)
    pending_update = load_pending_state()

    if request.method == "POST":
        action = (request.POST.get("action") or "").strip()

        if action == "check_updates":
            result = check_for_updates(force=True)
            if result.get("ok"):
                messages.success(request, result.get("message") or "تم فحص التحديثات بنجاح.")
            else:
                messages.warning(request, result.get("message") or "تعذر فحص التحديثات الآن.")
            return redirect("system_updates")

        if action == "download_and_prepare":
            result = check_for_updates(force=True)
            if not result.get("ok"):
                messages.warning(request, result.get("message") or "تعذر فحص التحديثات الآن.")
                return redirect("system_updates")

            payload = result.get("payload") or {}
            download_url = str(payload.get("download_url") or config.update_download_url or "").strip()
            expected_version = str(payload.get("latest_version") or payload.get("version") or config.latest_version or "").strip()
            expected_sha256 = str(payload.get("sha256") or payload.get("checksum") or "").strip()
            package_name = str(payload.get("package_name") or payload.get("file_name") or "").strip()
            notes = str(payload.get("release_notes") or payload.get("notes") or payload.get("message") or "").strip()

            if not download_url:
                messages.error(request, "يوجد تحديث جديد، لكن رابط تنزيله غير متوفر في خادم التحديث.")
                return redirect("system_updates")

            request_headers = central_update_download_headers() if payload.get("download_requires_sync_auth") else None
            try:
                pending_update = download_remote_update_and_prepare(
                    download_url=download_url,
                    current_version=config.current_version or getattr(config, "current_version", "1.0.0"),
                    expected_version=expected_version,
                    expected_sha256=expected_sha256,
                    package_name=package_name,
                    notes=notes,
                    request_headers=request_headers,
                )
            except Exception as exc:
                messages.error(request, f"فشل تنزيل وتجهيز التحديث: {exc}")
            else:
                if pending_update.get("install_kind") == "installer":
                    messages.success(request, "تم تنزيل المُثبت الجديد وتجهيزه للتشغيل عبر ملف خارجي.")
                elif pending_update.get("package_type") == "partial":
                    messages.success(request, "تم تنزيل تحديث جزئي وتجهيزه للتطبيق عبر المحدث الخارجي.")
                else:
                    messages.success(request, "تم تنزيل حزمة التحديث وتجهيزها للتطبيق عبر المحدث الخارجي.")
                messages.info(request, "يمكنك الآن تشغيل ملف تطبيق التحديث من نفس الصفحة لإكمال العملية بأمان.")
            return redirect("system_updates")

        if action == "clear_pending_update":
            clear_pending_state()
            messages.success(request, "تم حذف ملفات التحديث المجهّز ومسح حالته المؤقتة.")
            return redirect("system_updates")

        if action == "apply_pending_update":
            if not pending_update or not pending_update.get("script_path"):
                messages.warning(request, "لا يوجد تحديث مجهز حاليًا لتطبيقه.")
                return redirect("system_updates")
            return render(request, "core/update_starting.html", {
                "title": "بدء تطبيق التحديث",
                "pending_update": pending_update,
                "start_url": redirect("system_start_pending_update").url,
                "cancel_url": redirect("system_updates").url,
                "countdown_seconds": 15,
            })

    context = {
        "title": "مركز التحديثات",
        "config": config,
        "pending_update": pending_update,
        "update_summary": update_status_summary(config, pending_update),
        "update_connectivity": update_connectivity_status(config),
        "logs": UpdateCheckLog.objects.all()[:20],
    }
    return render(request, "core/system_updates.html", context)


@login_required
@user_passes_test(_staff_user)
def system_local_update_view(request):
    config = SystemConfiguration.get_solo()
    pending_update = load_pending_state()
    runtime_version = sync_runtime_version_state(config, pending_update)
    pending_update = load_pending_state()

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "clear_local_update":
            clear_pending_state()
            messages.success(request, "تم حذف التحديث المحلي المجهز.")
            return redirect("system_local_update")

        if action == "apply_pending_update":
            if not pending_update or not pending_update.get("script_path"):
                messages.warning(request, "لا يوجد تحديث مجهز حاليًا لتطبيقه.")
                return redirect("system_local_update")
            return render(request, "core/update_starting.html", {
                "title": "بدء تطبيق التحديث",
                "pending_update": pending_update,
                "start_url": redirect("system_start_pending_update").url,
                "cancel_url": redirect("system_local_update").url,
                "countdown_seconds": 15,
            })

        form = LocalUpdateUploadForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                pending_update = prepare_local_update(form.cleaned_data["update_file"], config.current_version or getattr(config, "current_version", "1.0.0"))
            except Exception as exc:
                messages.error(request, f"فشل التحقق من ملف التحديث: {exc}")
            else:
                pending_version = str(pending_update.get("version") or "").strip()
                if pending_version and pending_version != (config.latest_version or "").strip():
                    config.latest_version = pending_version
                    config.update_available = True
                    config.update_message = f"تم تجهيز تحديث محلي إلى الإصدار {pending_version}."
                    config.save(update_fields=["latest_version", "update_available", "update_message", "updated_at"])
                if pending_update.get("package_type") == "partial":
                    messages.success(request, "تم التحقق من ملف تحديث جزئي وتجهيزه للتطبيق بنجاح.")
                else:
                    messages.success(request, "تم التحقق من ملف التحديث بنجاح وتجهيزه للتطبيق.")
            return redirect("system_local_update")
        messages.error(request, "فشل التحقق من ملف التحديث. تأكد من أن الملف بصيغة ZIP وأنه يحتوي على manifest.json ومجلد app.")
        return redirect("system_local_update")

    form = LocalUpdateUploadForm()
    context = {
        "title": "التحديث المحلي",
        "config": config,
        "form": form,
        "pending_update": pending_update,
        "display_current_version": runtime_version,
    }
    return render(request, "core/local_update.html", context)




@login_required
@user_passes_test(_staff_user)
def system_start_pending_update(request):
    if request.method != "POST":
        return redirect("system_updates")
    pending_update = load_pending_state()
    if not pending_update or not pending_update.get("script_path"):
        messages.warning(request, "لا يوجد تحديث مجهز حاليًا لتطبيقه.")
        return redirect("system_updates")
    try:
        pending_update = launch_pending_update()
    except Exception as exc:
        messages.error(request, f"تعذر تشغيل أداة التحديث الخارجية: {exc}")
        source = str((request.POST.get("source") or "")).strip()
        return redirect(source or "system_updates")
    return render(request, "core/update_started.html", {
        "title": "تم تشغيل التحديث",
        "pending_update": pending_update,
    })




@csrf_exempt
@login_required
@user_passes_test(_staff_user)
def system_finalize_update_shutdown(request):
    if request.method != "POST":
        return JsonResponse({"ok": False, "message": "طريقة الطلب غير مسموحة."}, status=405)

    state = read_runtime_state() or {}
    launcher_pid = state.get("launcher_pid")
    server_pid = state.get("server_pid")

    try:
        request_shutdown()
    except Exception:
        pass

    commands = ["Start-Sleep -Seconds 4"]
    if launcher_pid:
        commands.append(f"Stop-Process -Id {int(launcher_pid)} -Force -ErrorAction SilentlyContinue")
    if server_pid:
        commands.append(f"Stop-Process -Id {int(server_pid)} -Force -ErrorAction SilentlyContinue")
    commands.append("Get-Process -Name 'TrainingCenter' -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue")
    ps_script = '; '.join(commands)

    try:
        subprocess.Popen(
            [
                "powershell.exe",
                "-WindowStyle",
                "Hidden",
                "-ExecutionPolicy",
                "Bypass",
                "-Command",
                ps_script,
            ],
            shell=False,
            creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) | getattr(subprocess, "DETACHED_PROCESS", 0),
        )
    except Exception as exc:  # noqa: BLE001
        return JsonResponse({"ok": False, "message": f"تعذر جدولة إغلاق البرنامج: {exc}"}, status=500)

    return JsonResponse({"ok": True, "message": "تمت جدولة إغلاق البرنامج لإكمال التحديث."})

@login_required
@user_passes_test(_staff_user)
def system_local_update_script_download(request):
    pending_update = load_pending_state()
    if not pending_update or not pending_update.get("script_path"):
        messages.warning(request, "لا يوجد ملف تحديث محلي مجهز حالياً.")
        return redirect("system_local_update")

    try:
        script_path = ensure_pending_script(pending_update)
    except Exception as exc:
        messages.error(request, f"تعذر تجهيز ملف تشغيل التحديث: {exc}")
        return redirect("system_local_update")

    download_name = script_path.name if script_path.suffix else "apply_local_update.ps1"

    try:
        downloads_dir = Path.home() / "Downloads"
        downloads_dir.mkdir(parents=True, exist_ok=True)
        target_path = downloads_dir / download_name
        target_path.write_bytes(script_path.read_bytes())
        messages.success(request, f"تم نسخ ملف التشغيل إلى: {target_path}")
    except Exception:
        target_path = None

    response = FileResponse(script_path.open("rb"), as_attachment=True, filename=download_name, content_type="application/octet-stream")
    if target_path is not None:
        response["X-Local-Saved-To"] = str(target_path)
    return response



def _runtime_status_payload(request=None):
    from django.db import connections
    from django.db.utils import OperationalError
    from pathlib import Path

    db_ok = True
    db_error = ""
    try:
        with connections["default"].cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except OperationalError as exc:
        db_ok = False
        db_error = str(exc)
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_error = str(exc)

    media_root = Path(getattr(settings, "MEDIA_ROOT", ""))
    static_root = Path(getattr(settings, "STATIC_ROOT", ""))
    media_ok = media_root.exists() and media_root.is_dir()
    static_ok = static_root.exists() and static_root.is_dir()
    payload = {
        "ok": db_ok and media_ok and static_ok,
        "app_mode": getattr(settings, "APP_MODE", "unknown"),
        "database": {
            "ok": db_ok,
            "engine": settings.DATABASES["default"]["ENGINE"],
            "name": str(settings.DATABASES["default"].get("NAME", "")),
            "error": db_error,
        },
        "media": {
            "ok": media_ok,
            "path": str(media_root),
        },
        "staticfiles": {
            "ok": static_ok,
            "path": str(static_root),
        },
    }
    if request is not None:
        payload["server"] = {
            "host": request.get_host(),
            "path": request.path,
        }
    return payload


def healthz_view(request):
    payload = _runtime_status_payload(request)
    status = 200 if payload.get("ok") else 503
    return JsonResponse(payload, status=status)


def readyz_view(request):
    payload = _runtime_status_payload(request)
    ready = bool(payload.get("database", {}).get("ok"))
    payload["ready"] = ready
    status = 200 if ready else 503
    return JsonResponse(payload, status=status)


# Backward-compatible aliases used by older URL configs
healthz = healthz_view
readyz = readyz_view

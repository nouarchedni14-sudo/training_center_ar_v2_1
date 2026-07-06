from collections import Counter

from django.contrib import messages
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from .activity import client_ip, log_activity
from .models import ActivityLog, حضوري_أولي, تمهين, دفعة, مسائي_ومعابر
from .permissions import (
    build_access_summary,
    can_access_admin_panel,
    get_access_denied_message,
    is_access_within_schedule,
    visible_programs,
)


def _user_force_password_change(user):
    if not getattr(user, "is_authenticated", False):
        return False
    try:
        return bool(user.access_profile.force_password_change)
    except Exception:
        return False


def _access_state_ui(state):
    state_map = {
        "active": {"badge_class": "success", "title": "الصلاحية نشطة", "hint": "يمكنك استعمال الأقسام المسموح بها الآن."},
        "pending": {"badge_class": "warning", "title": "الصلاحية لم تبدأ بعد", "hint": "الحساب موجود لكن تاريخ البداية لم يصل بعد."},
        "expired": {"badge_class": "danger", "title": "الصلاحية منتهية", "hint": "يجب على المدير تمديد الصلاحية أو تجديدها."},
        "disabled": {"badge_class": "danger", "title": "الصلاحية معطلة", "hint": "تم إيقاف الصلاحيات لهذا الحساب يدويًا."},
        "missing": {"badge_class": "", "title": "لا يوجد ملف صلاحيات", "hint": "أنشئ ملف صلاحيات لهذا المستخدم من لوحة الإدارة."},
        "superuser": {"badge_class": "", "title": "مدير عام", "hint": "هذا الحساب يملك صلاحيات كاملة على النظام."},
        "anonymous": {"badge_class": "", "title": "غير مسجل الدخول", "hint": "سجّل الدخول لعرض تفاصيل الحساب."},
    }
    return state_map.get(state, {"badge_class": "", "title": "حالة غير معروفة", "hint": "تعذر تحديد حالة الحساب."})


def build_account_context(user):
    summary = build_access_summary(user)
    permission_cards = [
        {"label": "لوحة الإدارة", "value": "مسموح" if summary["can_access_admin"] else "غير مسموح", "active": summary["can_access_admin"]},
        {"label": "التقارير", "value": "مسموح" if summary["can_view_reports"] else "غير مسموح", "active": summary["can_view_reports"]},
        {"label": "التصدير", "value": "مسموح" if summary["can_export_data"] else "غير مسموح", "active": summary["can_export_data"]},
        {"label": "البرامج المتاحة", "value": str(len(summary["allowed_programs"])), "active": bool(summary["allowed_programs"])},
    ]
    return {
        "access_summary": summary,
        "access_ui": _access_state_ui(summary["state"]),
        "permission_cards": permission_cards,
        "allowed_programs_verbose": summary["allowed_programs"],
    }


@login_required
def account_overview(request):
    context = build_account_context(request.user)
    context["title"] = "حالة الحساب والصلاحيات"
    return render(request, "trainees/account_overview.html", context)


def login_view(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    if request.method == "POST":
        username = request.POST.get("username", "").strip()
        password = request.POST.get("password", "")
        user = authenticate(request, username=username, password=password)
        if user:
            if not is_access_within_schedule(user):
                denied_message = get_access_denied_message(user)
                ActivityLog.objects.create(
                    user=user,
                    action="access_denied",
                    program="",
                    object_repr="منع دخول",
                    details=f"تم منع الدخول بعد نجاح التحقق من كلمة المرور. السبب: {denied_message}",
                    path=(request.path or "")[:255],
                    ip_address=client_ip(request),
                )
                from .models import UserAccountAuditLog, serialize_sensitive_account_state

                profile = getattr(user, "access_profile", None)
                UserAccountAuditLog.objects.create(
                    actor=None,
                    target_user=user,
                    action="login_denied_window",
                    changed_fields=[],
                    before_data=serialize_sensitive_account_state(profile) if profile else {},
                    after_data={},
                    notes=f"تم رفض تسجيل الدخول بسبب نافذة الصلاحية. السبب: {denied_message}",
                    ip_address=client_ip(request),
                )
                denied_context = build_account_context(user)
                denied_context.update({
                    "title": "تعذر تسجيل الدخول",
                    "error": denied_message,
                    "show_login_actions": True,
                    "username": username,
                })
                return render(request, "trainees/access_status.html", denied_context)

            login(request, user)
            log_activity(request, "login", details="تسجيل دخول ناجح")
            if _user_force_password_change(user):
                messages.warning(request, "يجب تغيير كلمة المرور من لوحة الإدارة بواسطة المدير أو عبر صفحة الإدارة.")
            return redirect("dashboard")

        ActivityLog.objects.create(
            user=None,
            action="login_failed",
            program="",
            object_repr="محاولة دخول فاشلة",
            details=f"فشل تسجيل الدخول للحساب: {username}",
            path=(request.path or "")[:255],
            ip_address=client_ip(request),
        )
        return render(request, "trainees/login.html", {"error": "اسم المستخدم أو كلمة المرور غير صحيحة"})

    return render(request, "trainees/login.html")


def logout_view(request):
    if request.user.is_authenticated:
        log_activity(request, "logout", details="تسجيل خروج")
    logout(request)
    return redirect("login")


@login_required
def dashboard(request):
    from .views import _get_ordered_rows, _refresh_rows_live_semesters

    today = timezone.localdate()
    cards = []
    semester_stats = []
    promotion_stats = []
    allowed_programs = visible_programs(request.user)

    semester_rank = {
        "الأول": 1,
        "الثاني": 2,
        "الثالث": 3,
        "الرابع": 4,
        "الخامس": 5,
    }

    if not allowed_programs and not can_access_admin_panel(request.user):
        messages.error(request, "لم تُمنح لك أي صلاحية بعد. تواصل مع مدير النظام.")

    for code, label, model_cls in [
        ("initial", "الحضوري الأولي", حضوري_أولي),
        ("apprentice", "التكوين عن طريق التمهين", تمهين),
        ("evening", "الدروس المسائية", مسائي_ومعابر),
        ("crossing", "المعابر", مسائي_ومعابر),
    ]:
        if code not in allowed_programs and not request.user.is_superuser:
            continue

        current_qs = _get_ordered_rows(model_cls, code, graduates=False)
        graduate_qs = _get_ordered_rows(model_cls, code, graduates=True)
        current_rows = _refresh_rows_live_semesters(list(current_qs), model_cls)

        cards.append({
            "code": code,
            "label": label,
            "current_count": len(current_rows),
            "graduate_count": graduate_qs.count(),
            "total_count": model_cls.objects.count(),
        })

        sem_counter = Counter()
        promotion_counter = Counter()
        for obj in current_rows:
            sem = (getattr(obj, "السداسي", "") or "").strip()
            if sem:
                sem_counter[sem] += 1
            promotion = getattr(obj, "الدفعة", None)
            if promotion and (getattr(promotion, "اسم_الدفعة", None) or getattr(promotion, "السنة", None)):
                promotion_counter[(promotion.اسم_الدفعة, promotion.السنة)] += 1

        semester_items = [
            {"السداسي": sem, "total": total}
            for sem, total in sorted(sem_counter.items(), key=lambda item: (semester_rank.get(item[0], 99), item[0]))
        ]
        promotion_items = [
            {"الدفعة__اسم_الدفعة": name, "الدفعة__السنة": year, "total": total}
            for (name, year), total in sorted(
                promotion_counter.items(),
                key=lambda item: (
                    -(item[0][1] or 0),
                    str(item[0][0] or ""),
                )
            )[:8]
        ]

        semester_stats.append({
            "label": label,
            "items": semester_items,
        })
        promotion_stats.append({
            "label": label,
            "items": promotion_items,
        })

    log_activity(request, "view", details="عرض الرئيسية")
    dashboard_context = {
        "cards": cards,
        "semester_stats": semester_stats,
        "promotion_stats": promotion_stats,
        "promotion_count": دفعة.objects.count(),
        "today": today,
        "allowed_programs": allowed_programs,
        "admin_access": can_access_admin_panel(request.user),
    }
    dashboard_context.update(build_account_context(request.user))
    dashboard_context["quick_links"] = [
        {"label": "حالة الحساب", "url": reverse("account_overview")},
        {"label": "لوحة الغيابات", "url": reverse("attendance_home")} if allowed_programs else None,
        {"label": "لوحة الإدارة", "url": "/admin/"} if can_access_admin_panel(request.user) else None,
    ]
    dashboard_context["quick_links"] = [item for item in dashboard_context["quick_links"] if item]
    return render(request, "trainees/dashboard.html", dashboard_context)

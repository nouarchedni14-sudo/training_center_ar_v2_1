from django.contrib import admin
from django.urls import include, path
from django.conf import settings
from django.conf.urls.static import static
from django.views.static import serve as static_serve
from django.shortcuts import redirect
import os

from core.views import healthz_view, readyz_view


def _central_redirect(request, *args, **kwargs):
    return redirect("central_dashboard")


def _office_dismissal_redirect(request, program):
    """تحويل زر مقرر الفصل داخل المكتب المحلي إلى صفحة مقرر الفصل الصحيحة."""
    program = str(program or "").strip()
    if program not in {"initial", "apprentice", "evening", "crossing"}:
        return redirect("management_overview")
    return redirect(f"/attendance/{program}/dismissal/?scope=current")


def _office_sanctions_redirect(request, program):
    """تحويل زر العقوبات داخل المكتب المحلي إلى صفحة العقوبات الصحيحة."""
    program = str(program or "").strip()
    if program not in {"initial", "apprentice", "evening", "crossing"}:
        return redirect("management_overview")
    return redirect(f"/attendance/{program}/sanctions/?scope=current&archive_state=active")


# في وضع الخادم المركزي لا نعرض واجهة المكاتب المحلية.
# المركزي هو برنامج المطور فقط: إدارة المكاتب، التراخيص، التحديثات، والمزامنة.
if str(getattr(settings, "APP_MODE", "")).strip().lower() == "central_server":
    from sync_core import central_views
    import core.urls as core_urls

    # الخادم المركزي خاص بلوحة المطور فقط.
    # لا نربط هنا صفحات المتكوّنين أو مقرر الفصل حتى لا تختلط قاعدة بيانات المركزي
    # مع قاعدة بيانات المكتب المحلي، وحتى لا يدخل مستخدمو المكاتب إلى لوحة المطور.
    urlpatterns = [
        path("healthz/", healthz_view, name="healthz"),
        path("readyz/", readyz_view, name="readyz"),

        path("", central_views.central_dashboard, name="home"),
        path("central/", central_views.central_dashboard, name="central_dashboard"),
        path("central/offices/", central_views.central_offices, name="central_offices"),
        path("central/offices/new/", central_views.central_office_new, name="central_office_new"),
        path("central/offices/cleanup-orphan-users/", central_views.central_cleanup_orphan_office_users, name="central_cleanup_orphan_office_users"),
        path("central/offices/users/new/", central_views.central_office_user_new, name="central_office_user_new"),
        path("central/trainee-manager/", central_views.central_trainee_manager_picker, name="central_trainee_manager_picker"),
        path("central/offices/<int:pk>/open/", central_views.central_office_open, name="central_office_open"),
        path("central/offices/<int:pk>/stop/", central_views.central_office_stop, name="central_office_stop"),
        path("central/offices/stop-all/", central_views.central_offices_stop_all, name="central_offices_stop_all"),
        path("central/offices/<int:pk>/sync-now/", central_views.central_office_sync_now, name="central_office_sync_now"),
        path("central/offices/<int:pk>/pull-audit/", central_views.central_office_pull_audit, name="central_office_pull_audit"),
        path("central/offices/<int:pk>/delete/", central_views.central_office_delete, name="central_office_delete"),
        path("central/offices/<int:pk>/root-delete/", central_views.central_office_root_delete, name="central_office_root_delete"),
        path("central/devices/", central_views.central_devices, name="central_devices"),
        path("central/devices/<int:pk>/approve/", central_views.central_device_approve, name="central_device_approve"),
        path("central/devices/<int:pk>/reject/", central_views.central_device_reject, name="central_device_reject"),
        path("central/devices/<int:pk>/delete/", central_views.central_device_delete, name="central_device_delete"),
        path("central/offices/<int:pk>/users/", central_views.central_office_users, name="central_office_users"),
        path("central/offices/<int:pk>/users/<str:username>/edit/", central_views.central_office_user_edit, name="central_office_user_edit"),
        path("central/offices/<int:pk>/", central_views.central_office_edit, name="central_office_edit"),
        path("central/updates/", central_views.central_updates, name="central_updates"),
        path("central/updates/new/", central_views.central_update_edit, name="central_update_new"),
        path("central/updates/<int:pk>/", central_views.central_update_edit, name="central_update_edit"),

        # Aliases للروابط القديمة داخل لوحة المطور فقط.
        path("dashboard/", central_views.central_dashboard, name="dashboard"),
        path("admin/quick/initial/", _central_redirect, name="admin_quick_initial"),
        path("admin/quick/apprentice/", _central_redirect, name="admin_quick_apprentice"),
        path("admin/quick/evening/", _central_redirect, name="admin_quick_evening"),
        path("admin/quick/crossing/", _central_redirect, name="admin_quick_crossing"),
        path("admin/quick/<str:program>/<str:status>/", _central_redirect, name="admin_quick_filtered"),

        path("system/", include(core_urls)),
        path("admin/", admin.site.urls),
        path("api/", include("sync_core.urls")),
    ]
else:
    import core.urls as core_urls
    from trainees.views import (
        login_view,
        developer_login_view,
        logout_view,
        dashboard,
        account_overview,
        management_overview,
        initial_list,
        apprentice_list,
        evening_list,
        crossing_list,
        program_graduates_list,
        admin_quick_initial,
        admin_quick_apprentice,
        admin_quick_evening,
        admin_quick_crossing,
        admin_quick_filtered,
        trainee_add,
        trainee_edit,
        trainee_media_upload,
        trainee_delete,
        recompute_semesters_ui,
        export_program_data,
        attendance_home,
        attendance_program,
        attendance_stats,
        attendance_actions,
        attendance_slot_actions,
        attendance_actions_preview,
        attendance_action_edit,
        attendance_actions_bulk_edit,
        attendance_action_archive_toggle,
        attendance_action_delete,
        attendance_action_delete_direct,
        attendance_action_print,
        attendance_actions_bulk,
        dismissal_decisions,
        dismissal_decisions_bulk,
        dismissal_decisions_bulk_edit,
        dismissal_decisions_preview,
        dismissal_decisions_archive,
        dismissal_decisions_archive_bulk,
        sanction_records,
        sanction_records_bulk,
        sanction_records_bulk_edit,
        sanction_records_preview,
        saved_attendance_stats_archive,
        saved_attendance_stats_export,
        attendance_export,
        error_403,
        error_404,
        error_500,
    )


    from trainees.user_attendance_summary_views import (
        user_attendance_summary,
        user_attendance_summary_print,
        user_attendance_summary_export,
        user_attendance_summary_archive,
        user_attendance_summary_archive_create,
        user_attendance_summary_archive_detail,
    )

    from trainees.summons_views import summons_records, summons_records_bulk, summons_records_bulk_edit, summons_records_preview

    from trainees.attendance_initial_slots import initial_slots, initial_slots_stats, initial_slots_export, initial_slots_sync_actions
    from trainees.attendance_apprentice_slots import apprentice_slots, apprentice_slots_stats, apprentice_slots_export, apprentice_slots_sync_actions
    from trainees.attendance_evening_slots import evening_slots, evening_slots_stats, evening_slots_export, evening_slots_sync_actions
    from trainees.attendance_crossing_slots import crossing_slots, crossing_slots_stats, crossing_slots_export, crossing_slots_sync_actions

    urlpatterns = [
      path("healthz/", healthz_view, name="healthz"),
      path("readyz/", readyz_view, name="readyz"),
      path("admin/quick/initial/", admin_quick_initial, name="admin_quick_initial"),
      path("admin/quick/apprentice/", admin_quick_apprentice, name="admin_quick_apprentice"),
      path("admin/quick/evening/", admin_quick_evening, name="admin_quick_evening"),
      path("admin/quick/crossing/", admin_quick_crossing, name="admin_quick_crossing"),
      path("admin/quick/<str:program>/<str:status>/", admin_quick_filtered, name="admin_quick_filtered"),
      path("admin/", admin.site.urls),
      path("", login_view, name="login"),
      path("accounts/login/", login_view, name="accounts_login"),
      path("developer/login/", developer_login_view, name="developer_login"),
      path("dashboard/", dashboard, name="dashboard"),
      path("account/", account_overview, name="account_overview"),
      path("management/overview/", management_overview, name="management_overview"),
      path("attendance/", attendance_home, name="attendance_home"),
      path("attendance/saved-stats/", saved_attendance_stats_archive, name="attendance_saved_stats"),
      path("attendance/saved-stats/export/<str:fmt>/", saved_attendance_stats_export, name="attendance_saved_stats_export"),
      path("attendance/apprentice/user-summary/", user_attendance_summary, name="user_attendance_summary"),
      path("attendance/apprentice/user-summary/print/", user_attendance_summary_print, name="user_attendance_summary_print"),
      path("attendance/apprentice/user-summary/export/<str:fmt>/", user_attendance_summary_export, name="user_attendance_summary_export"),
      path("attendance/apprentice/user-summary/archive/", user_attendance_summary_archive, name="user_attendance_summary_archive"),
      path("attendance/apprentice/user-summary/archive/create/", user_attendance_summary_archive_create, name="user_attendance_summary_archive_create"),
      path("attendance/apprentice/user-summary/archive/<int:pk>/", user_attendance_summary_archive_detail, name="user_attendance_summary_archive_detail"),
      # مقرر الفصل: يجب أن تأتي هذه المسارات قبل attendance/<str:program>/ حتى تظهر في صفحة 404 بوضوح.
      path("management/dismissal/<str:program>/", _office_dismissal_redirect, name="management_dismissal_redirect"),
      path("attendance/<str:program>/dismissal/", dismissal_decisions, name="dismissal_decisions"),
      path("attendance/<str:program>/dismissal/bulk/", dismissal_decisions_bulk, name="dismissal_decisions_bulk"),
      path("attendance/<str:program>/dismissal/bulk-edit/", dismissal_decisions_bulk_edit, name="dismissal_decisions_bulk_edit"),
      path("attendance/<str:program>/dismissal/preview/", dismissal_decisions_preview, name="dismissal_decisions_preview"),
      path("attendance/<str:program>/dismissal/archive/", dismissal_decisions_archive, name="dismissal_decisions_archive"),
      path("attendance/<str:program>/dismissal/archive/bulk/", dismissal_decisions_archive_bulk, name="dismissal_decisions_archive_bulk"),
      path("dismissal/<str:program>/", dismissal_decisions),
      path("moqarrar-fasl/<str:program>/", dismissal_decisions, name="dismissal_decisions_direct"),
      path("dismissal/<str:program>/bulk/", dismissal_decisions_bulk),
      path("dismissal/<str:program>/bulk-edit/", dismissal_decisions_bulk_edit),
      path("dismissal/<str:program>/preview/", dismissal_decisions_preview),
      path("dismissal/<str:program>/archive/", dismissal_decisions_archive),
      path("dismissal/<str:program>/archive/bulk/", dismissal_decisions_archive_bulk),
      path("management/sanctions/<str:program>/", _office_sanctions_redirect, name="management_sanctions_redirect"),
      path("attendance/<str:program>/sanctions/", sanction_records, name="sanction_records"),
      path("attendance/<str:program>/sanctions/bulk/", sanction_records_bulk, name="sanction_records_bulk"),
      path("attendance/<str:program>/sanctions/bulk-edit/", sanction_records_bulk_edit, name="sanction_records_bulk_edit"),
      path("attendance/<str:program>/sanctions/preview/", sanction_records_preview, name="sanction_records_preview"),
      path("sanctions/<str:program>/", sanction_records),
      path("sanctions/<str:program>/bulk/", sanction_records_bulk),
      path("sanctions/<str:program>/bulk-edit/", sanction_records_bulk_edit),
      path("sanctions/<str:program>/preview/", sanction_records_preview),

      path("management/summons/<str:program>/", summons_records, name="management_summons_redirect"),
      path("attendance/<str:program>/summons/", summons_records, name="summons_records"),
      path("attendance/<str:program>/summons/bulk/", summons_records_bulk, name="summons_records_bulk"),
      path("attendance/<str:program>/summons/bulk-edit/", summons_records_bulk_edit, name="summons_records_bulk_edit"),
      path("attendance/<str:program>/summons/preview/", summons_records_preview, name="summons_records_preview"),
      path("summons/<str:program>/", summons_records),
      path("summons/<str:program>/bulk/", summons_records_bulk),
      path("summons/<str:program>/bulk-edit/", summons_records_bulk_edit),
      path("summons/<str:program>/preview/", summons_records_preview),
      # نظام الغيابات الجديد بالحصة: صفحات مستقلة لا تلمس الصفحات القديمة.
      path("attendance/initial-slots/", initial_slots, name="attendance_initial_slots"),
      path("attendance/initial-slots/stats/", initial_slots_stats, name="attendance_initial_slots_stats"),
      path("attendance/initial-slots/export/<str:fmt>/", initial_slots_export, name="attendance_initial_slots_export"),
      path("attendance/initial-slots/sync-actions/", initial_slots_sync_actions, name="attendance_initial_slots_sync_actions"),
      path("attendance/apprentice-slots/", apprentice_slots, name="attendance_apprentice_slots"),
      path("attendance/apprentice-slots/stats/", apprentice_slots_stats, name="attendance_apprentice_slots_stats"),
      path("attendance/apprentice-slots/export/<str:fmt>/", apprentice_slots_export, name="attendance_apprentice_slots_export"),
      path("attendance/apprentice-slots/sync-actions/", apprentice_slots_sync_actions, name="attendance_apprentice_slots_sync_actions"),
      path("attendance/evening-slots/", evening_slots, name="attendance_evening_slots"),
      path("attendance/evening-slots/stats/", evening_slots_stats, name="attendance_evening_slots_stats"),
      path("attendance/evening-slots/export/<str:fmt>/", evening_slots_export, name="attendance_evening_slots_export"),
      path("attendance/evening-slots/sync-actions/", evening_slots_sync_actions, name="attendance_evening_slots_sync_actions"),
      path("attendance/crossing-slots/", crossing_slots, name="attendance_crossing_slots"),
      path("attendance/crossing-slots/stats/", crossing_slots_stats, name="attendance_crossing_slots_stats"),
      path("attendance/crossing-slots/export/<str:fmt>/", crossing_slots_export, name="attendance_crossing_slots_export"),
      path("attendance/crossing-slots/sync-actions/", crossing_slots_sync_actions, name="attendance_crossing_slots_sync_actions"),
      path("attendance-slots/initial/", initial_slots),
      path("attendance-slots/initial/stats/", initial_slots_stats),
      path("attendance-slots/initial/export/<str:fmt>/", initial_slots_export),
      path("attendance-slots/initial/sync-actions/", initial_slots_sync_actions),
      path("attendance-slots/apprentice/", apprentice_slots),
      path("attendance-slots/apprentice/stats/", apprentice_slots_stats),
      path("attendance-slots/apprentice/export/<str:fmt>/", apprentice_slots_export),
      path("attendance-slots/apprentice/sync-actions/", apprentice_slots_sync_actions),
      path("attendance-slots/evening/", evening_slots),
      path("attendance-slots/evening/stats/", evening_slots_stats),
      path("attendance-slots/evening/export/<str:fmt>/", evening_slots_export),
      path("attendance-slots/evening/sync-actions/", evening_slots_sync_actions),
      path("attendance-slots/crossing/", crossing_slots),
      path("attendance-slots/crossing/stats/", crossing_slots_stats),
      path("attendance-slots/crossing/export/<str:fmt>/", crossing_slots_export),
      path("attendance-slots/crossing/sync-actions/", crossing_slots_sync_actions),
      path("attendance/<str:program>/", attendance_program, name="attendance_program"),
      path("attendance/<str:program>/stats/", attendance_stats, name="attendance_stats"),
      path("attendance/<str:program>/actions/", attendance_actions, name="attendance_actions"),
      path("attendance/<str:program>/slot-actions/", attendance_slot_actions, name="attendance_slot_actions"),
      path("attendance/<str:program>/actions/preview/", attendance_actions_preview, name="attendance_actions_preview"),
      path("attendance/actions/<int:pk>/edit/", attendance_action_edit, name="attendance_action_edit"),
      path("attendance/<str:program>/actions/bulk-edit/", attendance_actions_bulk_edit, name="attendance_actions_bulk_edit"),
      path("attendance/actions/<int:pk>/archive/", attendance_action_archive_toggle, name="attendance_action_archive_toggle"),
      path("attendance/actions/<int:pk>/delete/", attendance_action_delete, name="attendance_action_delete"),
      path("attendance/actions/<int:pk>/delete-direct/", attendance_action_delete_direct, name="attendance_action_delete_direct"),
      path("attendance/actions/bulk/", attendance_actions_bulk, name="attendance_actions_bulk"),
      path("attendance/actions/<int:pk>/print/", attendance_action_print, name="attendance_action_print"),
      path("attendance/<str:program>/export/<str:fmt>/", attendance_export, name="attendance_export"),
      path("logout/", logout_view, name="logout"),
      path("program/initial/", initial_list, name="initial_list"),
      path("program/apprentice/", apprentice_list, name="apprentice_list"),
      path("program/evening/", evening_list, name="evening_list"),
      path("program/crossing/", crossing_list, name="crossing_list"),
      path("program/<str:program>/graduates/", program_graduates_list, name="program_graduates_list"),
      path("program/<str:program>/add/", trainee_add, name="trainee_add"),
      path("program/<str:program>/<int:pk>/edit/", trainee_edit, name="trainee_edit"),
      path("program/<str:program>/<int:pk>/media-upload/", trainee_media_upload, name="trainee_media_upload"),
      path("program/<str:program>/<int:pk>/delete/", trainee_delete, name="trainee_delete"),
      path("program/<str:program>/export/<str:fmt>/", export_program_data, name="export_program_data"),
      path("maintenance/recompute-semesters/", recompute_semesters_ui, name="recompute_semesters_ui"),
      path("system/", include(core_urls)),
      path("api/", include("sync_core.urls")),
    ]

if settings.DEBUG or str(getattr(settings, "APP_MODE", "")).strip().lower() in {"desktop", "lan", "lan_server", "central_server"} or os.getenv("TRAINING_CENTER_DESKTOP", "0") == "1":
  urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
  urlpatterns += [
    path("static/<path:path>", static_serve, {"document_root": settings.STATIC_ROOT}, name="served_static"),
    path("media/<path:path>", static_serve, {"document_root": settings.MEDIA_ROOT}, name="served_media"),
  ]

handler404 = "trainees.views.error_404"
handler403 = "trainees.views.error_403"
handler500 = "trainees.views.error_500"

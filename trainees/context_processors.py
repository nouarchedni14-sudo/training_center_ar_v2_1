from .permissions import visible_programs, can_access_admin_panel, can_manage_users, build_access_summary


def ui_permissions(request):
    user = getattr(request, 'user', None)
    # نرسل ملخص الصلاحيات إلى كل القوالب حتى تظهر حالة الحساب في الشريط العلوي والصفحات المختلفة.
    return {
        'visible_programs': visible_programs(user),
        'can_access_admin_panel': can_access_admin_panel(user),
        'can_manage_users': can_manage_users(user),
        'access_summary': build_access_summary(user),
    }

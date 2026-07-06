from pathlib import Path


def test_admin_uses_shared_mixins_and_base_classes():
    admin_py = Path(__file__).resolve().parents[1] / 'admin.py'
    text = admin_py.read_text(encoding='utf-8')

    assert 'from .admin_mixins import AdminPanelPermissionMixin, SuperuserOnlyAdminMixin, BaseProgramAdmin' in text
    assert 'class InitialAdmin(ExcelImportAdminMixin, BaseProgramAdmin)' in text
    assert 'class ApprenticeAdmin(ExcelImportAdminMixin, BaseProgramAdmin)' in text
    assert 'class EveningAdmin(ExcelImportAdminMixin, BaseProgramAdmin)' in text
    assert 'class RestrictedUserAdmin(SuperuserOnlyAdminMixin, DjangoUserAdmin)' in text

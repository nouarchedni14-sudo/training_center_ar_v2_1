from django.contrib import admin
from django.contrib.auth.models import User
from django.test import SimpleTestCase

from trainees.admin_users import AccessAuditLogAdmin, RestrictedUserAdmin
from trainees.models import AccessAuditLog


class AdminUserModuleStructureTests(SimpleTestCase):
    def test_admin_py_uses_extracted_user_module(self):
        content = open("trainees/admin.py", "r", encoding="utf-8").read()
        self.assertIn("from .admin_users import RestrictedUserAdmin, AccessAuditLogAdmin, register_auth_admin", content)
        self.assertIn("register_auth_admin(admin.site)", content)

    def test_expected_admin_classes_registered(self):
        self.assertIsInstance(admin.site._registry[User], RestrictedUserAdmin)
        self.assertIsInstance(admin.site._registry[AccessAuditLog], AccessAuditLogAdmin)

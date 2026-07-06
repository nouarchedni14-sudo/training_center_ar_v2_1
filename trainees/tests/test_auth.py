from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from trainees.models import ActivityLog


class AuthFlowTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="tester",
            password="SafePass123!",
            is_staff=True,
        )

    def test_login_page_loads(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اسم المستخدم")

    def test_successful_login_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "SafePass123!"},
            follow=False,
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("dashboard"))
        self.assertTrue("_auth_user_id" in self.client.session)
        self.assertTrue(ActivityLog.objects.filter(action="login", user=self.user).exists())

    def test_failed_login_returns_error_message(self):
        response = self.client.post(
            reverse("login"),
            {"username": "tester", "password": "wrong-password"},
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اسم المستخدم أو كلمة المرور غير صحيحة")
        self.assertTrue(ActivityLog.objects.filter(action="login_failed").exists())

    def test_logout_redirects_to_login_page(self):
        self.client.login(username="tester", password="SafePass123!")

        response = self.client.get(reverse("logout"), follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], reverse("login"))
        self.assertFalse("_auth_user_id" in self.client.session)
        self.assertTrue(ActivityLog.objects.filter(action="logout").exists())

    def test_protected_page_uses_existing_login_route(self):
        response = self.client.get(reverse("dashboard"), follow=False)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts_login"), response.headers["Location"])

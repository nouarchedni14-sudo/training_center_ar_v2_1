from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse


class DashboardAndAccountViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="dashboard-user", password="pass12345")

    def test_dashboard_requires_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_loads_after_login(self):
        self.client.login(username="dashboard-user", password="pass12345")
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حالة الحساب")

    def test_account_overview_loads_after_login(self):
        self.client.login(username="dashboard-user", password="pass12345")
        response = self.client.get(reverse("account_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "حالة الحساب")


class LoginViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="login-user", password="pass12345")

    def test_invalid_login_shows_error(self):
        response = self.client.post(reverse("login"), {"username": "login-user", "password": "wrong-pass"})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "اسم المستخدم أو كلمة المرور غير صحيحة")

    def test_valid_login_redirects_to_dashboard(self):
        response = self.client.post(reverse("login"), {"username": "login-user", "password": "pass12345"})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse("dashboard"))

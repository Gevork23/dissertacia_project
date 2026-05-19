from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import UserProfile


class AccountsTests(TestCase):
    def test_bootstrap_users_created(self):
        admin_user = User.objects.get(username="admin")
        employee_user = User.objects.get(username="user")

        self.assertTrue(admin_user.is_superuser)
        self.assertEqual(admin_user.profile.role, UserProfile.Role.ADMIN)
        self.assertEqual(employee_user.profile.role, UserProfile.Role.EMPLOYEE)

    def test_registration_creates_employee_profile(self):
        response = self.client.post(
            reverse("accounts-register"),
            {
                "username": "newemployee",
                "first_name": "New",
                "last_name": "Employee",
                "email": "employee@example.com",
                "password1": "ComplexPass123!",
                "password2": "ComplexPass123!",
            },
        )

        self.assertEqual(response.status_code, 302)
        user = User.objects.get(username="newemployee")
        self.assertEqual(user.profile.role, UserProfile.Role.EMPLOYEE)

    def test_login_page_is_available(self):
        response = self.client.get(reverse("accounts-login"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Войти")

    def test_admin_profile_can_update_role(self):
        admin_user = User.objects.get(username="admin")
        employee_user = User.objects.get(username="user")
        self.client.force_login(admin_user)

        response = self.client.post(
            reverse("accounts-profile"),
            {
                "user_id": employee_user.id,
                "role": "admin",
                "is_active": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        employee_user.refresh_from_db()
        self.assertTrue(employee_user.is_superuser)
        self.assertEqual(employee_user.profile.role, UserProfile.Role.ADMIN)

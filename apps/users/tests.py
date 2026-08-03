from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department, StaffUser


class AuthTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP100",
            username="emp100",
            email="emp100@srms.ac.in",
            first_name="Test",
            last_name="User",
            password="pass12345",
            department=self.dept,
            role="staff",
        )

    def test_login_with_employee_id(self):
        resp = self.client.post(reverse('login'), {
            'employee_id': 'EMP100', 'password': 'pass12345'
        })
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(int(self.client.session['_auth_user_id']), self.staff.pk)

    def test_login_wrong_password(self):
        resp = self.client.post(reverse('login'), {
            'employee_id': 'EMP100', 'password': 'wrong'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Invalid")

    def test_dashboard_requires_login(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_profile_requires_login(self):
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 302)

    def test_logged_in_profile(self):
        self.client.login(employee_id='EMP100', password='pass12345')
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)


class LanguageToggleTests(TestCase):
    def setUp(self):
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP101", username="emp101",
            email="a@b.com", password="pass12345", role="staff"
        )
        self.client.login(employee_id='EMP101', password='pass12345')

    def test_toggle_language(self):
        resp = self.client.get(reverse('toggle_language'), {'lang': 'hi'})
        self.assertEqual(resp.status_code, 302)
        self.staff.refresh_from_db()
        self.assertEqual(self.staff.preferred_language, 'hi')

    def test_dashboard_renders_hindi(self):
        self.staff.preferred_language = 'hi'
        self.staff.save()
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "पाठ्यक्रम", status_code=200)

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


class RegistrationApprovalTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.admin = StaffUser.objects.create_user(
            employee_id="ADMIN9", username="admin9",
            email="admin9@srms.ac.in", password="pass12345",
            role="admin", is_superuser=True,
        )

    def test_register_creates_inactive_user(self):
        resp = self.client.post(reverse('register'), {
            'employee_id': 'EMP777', 'first_name': 'New', 'last_name': 'User',
            'email': 'new@srms.ac.in', 'department': self.dept.id,
            'designation': 'Lab Assistant', 'phone_number': '12345',
            'password1': 'secret123', 'password2': 'secret123',
        })
        self.assertEqual(resp.status_code, 302)
        user = StaffUser.objects.get(employee_id='EMP777')
        self.assertFalse(user.is_active)
        self.assertEqual(user.role, 'staff')

    def test_register_rejects_duplicate_employee_id(self):
        StaffUser.objects.create_user(
            employee_id="EMP778", username="emp778",
            email="a@b.com", password="pass12345", role="staff",
        )
        resp = self.client.post(reverse('register'), {
            'employee_id': 'EMP778', 'first_name': 'A', 'last_name': 'B',
            'email': 'x@srms.ac.in', 'password1': 'secret123', 'password2': 'secret123',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "already registered")

    def test_login_pending_shows_approval_message(self):
        user = StaffUser.objects.create_user(
            employee_id="EMP779", username="emp779",
            email="a@b.com", password="pass12345", role="staff", is_active=False,
        )
        resp = self.client.post(reverse('login'), {
            'employee_id': 'EMP779', 'password': 'pass12345'
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "pending admin approval")

    def test_approve_user_enables_login(self):
        user = StaffUser.objects.create_user(
            employee_id="EMP780", username="emp780",
            email="a@b.com", password="pass12345", role="staff", is_active=False,
        )
        self.client.login(employee_id='ADMIN9', password='pass12345')
        resp = self.client.post(reverse('approve_user', args=[user.id]))
        self.assertEqual(resp.status_code, 302)
        user.refresh_from_db()
        self.assertTrue(user.is_active)

    def test_non_admin_cannot_approve(self):
        staff = StaffUser.objects.create_user(
            employee_id="EMP781", username="emp781",
            email="a@b.com", password="pass12345", role="staff",
        )
        pending = StaffUser.objects.create_user(
            employee_id="EMP782", username="emp782",
            email="a@b.com", password="pass12345", role="staff", is_active=False,
        )
        self.client.login(employee_id='EMP781', password='pass12345')
        resp = self.client.post(reverse('approve_user', args=[pending.id]))
        self.assertEqual(resp.status_code, 403)


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

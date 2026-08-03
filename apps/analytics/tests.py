from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course
from apps.quizzes.models import Quiz, Question, Choice, QuizAttempt

StaffUser = get_user_model()


class AnalyticsAccessTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP500", username="emp500", email="a@b.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.trainer = StaffUser.objects.create_user(
            employee_id="EMP501", username="emp501", email="c@d.com",
            password="pass12345", role="trainer", department=self.dept
        )

    def test_staff_denied_hr_dashboard(self):
        self.client.login(employee_id='EMP500', password='pass12345')
        resp = self.client.get(reverse('hr_dashboard'))
        self.assertEqual(resp.status_code, 302)

    def test_trainer_allowed_hr_dashboard(self):
        self.client.login(employee_id='EMP501', password='pass12345')
        resp = self.client.get(reverse('hr_dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('dept_stats', resp.context)

    def test_staff_denied_csv(self):
        self.client.login(employee_id='EMP500', password='pass12345')
        resp = self.client.get(reverse('export_staff_csv'))
        self.assertEqual(resp.status_code, 403)

    def test_trainer_csv_export(self):
        self.client.login(employee_id='EMP501', password='pass12345')
        resp = self.client.get(reverse('export_staff_csv'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('text/csv', resp['Content-Type'])
        self.assertTrue(resp.content.startswith(b'Employee ID'))

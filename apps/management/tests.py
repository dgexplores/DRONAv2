from django.test import TestCase
from django.urls import reverse
from apps.users.models import StaffUser, Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment


class ManagementConsoleTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.admin = StaffUser.objects.create_user(
            employee_id="ADMIN9", username="admin9",
            email="admin9@srms.ac.in", password="pass12345",
            role="admin", is_superuser=True,
        )
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP90", username="emp90",
            email="emp90@srms.ac.in", password="pass12345",
            role="staff", department=self.dept,
        )
        self.category = Category.objects.create(name="Safety")
        self.client.login(employee_id='ADMIN9', password='pass12345')

    def test_console_requires_manager(self):
        self.client.login(employee_id='EMP90', password='pass12345')
        resp = self.client.get(reverse('mgmt_home'))
        self.assertEqual(resp.status_code, 302)

    def test_create_course(self):
        resp = self.client.post(reverse('mgmt_course_create'), {
            'title': 'Fire Safety',
            'description': 'Fire safety procedures',
            'category': self.category.id,
            'is_mandatory': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Course.objects.filter(title='Fire Safety').exists())

    def test_add_module_and_lesson(self):
        course = Course.objects.create(title="C1", description="d", category=self.category)
        resp = self.client.post(reverse('mgmt_course_detail', args=[course.id]), {
            'title': 'Module 1', 'order': '1',
        })
        self.assertEqual(resp.status_code, 302)
        module = Module.objects.get(course=course)
        resp = self.client.post(reverse('mgmt_lesson_create', args=[module.id]), {
            'title': 'Video 1', 'lesson_type': 'video',
            'video_url': 'https://youtube.com/watch?v=x', 'order': '1', 'duration_minutes': '10',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Lesson.objects.filter(module=module, title='Video 1').exists())

    def test_bulk_enroll_all_staff(self):
        course = Course.objects.create(title="C2", description="d", category=self.category)
        resp = self.client.post(reverse('mgmt_bulk_enroll'), {
            'course': course.id, 'department': '',
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Enrollment.objects.filter(staff_user=self.staff, course=course).exists())

    def test_bulk_enroll_by_department(self):
        course = Course.objects.create(title="C3", description="d", category=self.category)
        resp = self.client.post(reverse('mgmt_bulk_enroll'), {
            'course': course.id, 'department': self.dept.id,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertTrue(Enrollment.objects.filter(staff_user=self.staff, course=course).exists())

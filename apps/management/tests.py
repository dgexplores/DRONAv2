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

    def test_assign_single_staff(self):
        course = Course.objects.create(title="C4", description="d", category=self.category)
        staff2 = StaffUser.objects.create_user(
            employee_id="EMP91", username="emp91",
            email="emp91@srms.ac.in", password="pass12345",
            role="staff", department=self.dept,
        )
        resp = self.client.post(reverse('mgmt_assign_staff'), {
            'staff_user': staff2.id, 'course': course.id,
        })
        self.assertEqual(resp.status_code, 302)
        self.assertRedirects(resp, reverse('mgmt_home'))
        self.assertTrue(Enrollment.objects.filter(staff_user=staff2, course=course).exists())
        self.assertFalse(Enrollment.objects.filter(staff_user=self.staff, course=course).exists())

    def test_assign_staff_requires_manager(self):
        course = Course.objects.create(title="C5", description="d", category=self.category)
        self.client.login(employee_id='EMP90', password='pass12345')
        resp = self.client.get(reverse('mgmt_assign_staff'))
        self.assertEqual(resp.status_code, 302)


class CreateAccountTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="HR", code="HR")
        self.admin = StaffUser.objects.create_user(
            employee_id="ADMIN8", username="admin8",
            email="admin8@srms.ac.in", password="pass12345",
            role="admin", is_staff=True, is_superuser=True,
        )
        self.trainer = StaffUser.objects.create_user(
            employee_id="EMP11", username="emp11",
            email="emp11@srms.ac.in", password="pass12345",
            role="trainer",
        )

    def test_admin_can_create_hr_account(self):
        self.client.login(employee_id='ADMIN8', password='pass12345')
        resp = self.client.post(reverse('mgmt_create_user'), {
            'employee_id': 'HR001', 'first_name': 'Ritu',
            'last_name': 'Arora', 'email': 'ritu@srms.ac.in',
            'department': self.dept.pk, 'designation': 'HR Manager',
            'role': 'trainer', 'password': 'Temp@12345',
        })
        self.assertRedirects(resp, reverse('mgmt_home'))
        u = StaffUser.objects.get(employee_id='HR001')
        self.assertTrue(u.is_active)
        self.assertEqual(u.role, 'trainer')
        self.assertTrue(u.check_password('Temp@12345'))

    def test_trainer_cannot_create_account(self):
        self.client.login(employee_id='EMP11', password='pass12345')
        resp = self.client.get(reverse('mgmt_create_user'))
        self.assertRedirects(resp, reverse('mgmt_home'))
        self.assertFalse(StaffUser.objects.filter(employee_id='HR002').exists())

    def test_duplicate_employee_id_rejected(self):
        self.client.login(employee_id='ADMIN8', password='pass12345')
        self.client.post(reverse('mgmt_create_user'), {
            'employee_id': 'ADMIN8', 'first_name': 'Dup',
            'last_name': 'User', 'email': 'dup@srms.ac.in',
            'role': 'staff', 'password': 'Temp@12345',
        })
        self.assertEqual(StaffUser.objects.filter(employee_id='ADMIN8').count(), 1)

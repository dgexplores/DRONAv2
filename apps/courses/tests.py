import json
from django.test import TestCase, Client
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment, LessonProgress

StaffUser = get_user_model()


class CourseFlowTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.cat = Category.objects.create(name="Safety", name_hi="सुरक्षा")
        self.course = Course.objects.create(
            title="Fire Safety", title_hi="अग्नि सुरक्षा",
            description="Desc", category=self.cat, is_mandatory=True
        )
        self.course.target_departments.add(self.dept)
        self.module = Module.objects.create(course=self.course, title="Intro", order=1)
        self.lesson = Lesson.objects.create(
            module=self.module, title="L1", order=1,
            lesson_type='video', duration_minutes=10
        )
        self.user = StaffUser.objects.create_user(
            employee_id="EMP200", username="emp200", email="x@y.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.client.login(employee_id='EMP200', password='pass12345')

    def test_auto_enroll_mandatory_on_dashboard(self):
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Enrollment.objects.filter(staff_user=self.user, course=self.course).exists())

    def test_staff_cannot_view_unassigned_course(self):
        elective = Course.objects.create(title="ERP", category=self.cat, is_mandatory=False)
        resp = self.client.get(reverse('course_detail', args=[elective.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(staff_user=self.user, course=elective).exists())

    def test_staff_cannot_access_unassigned_lesson(self):
        other = Course.objects.create(title="Other", category=self.cat, is_mandatory=False)
        other_module = Module.objects.create(course=other, title="M", order=1)
        other_lesson = Lesson.objects.create(
            module=other_module, title="L", order=1, lesson_type='video', duration_minutes=10
        )
        resp = self.client.get(reverse('lesson_view', args=[other_lesson.id]))
        self.assertEqual(resp.status_code, 302)

    def test_manager_can_preview_any_course(self):
        manager = StaffUser.objects.create_user(
            employee_id="TRAIN200", username="train200", email="t@y.com",
            password="pass12345", role="trainer"
        )
        self.client.login(employee_id='TRAIN200', password='pass12345')
        elective = Course.objects.create(title="ERP", category=self.cat, is_mandatory=False)
        resp = self.client.get(reverse('course_detail', args=[elective.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertIsNone(resp.context['enrollment'])

    def test_course_detail(self):
        enrollment = Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('course_detail', args=[self.course.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context['enrollment'].id, enrollment.id)

    def test_lesson_view(self):
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('lesson_view', args=[self.lesson.id]))
        self.assertEqual(resp.status_code, 200)

    def test_save_progress_updates_enrollment(self):
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.post(
            reverse('save_lesson_progress', args=[self.lesson.id]),
            data=json.dumps({'position': 100, 'completed': True}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        enrollment = Enrollment.objects.get(staff_user=self.user, course=self.course)
        self.assertEqual(enrollment.progress_percent, 100)
        self.assertTrue(enrollment.is_completed)

    def test_progress_requires_json(self):
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('save_lesson_progress', args=[self.lesson.id]))
        self.assertEqual(resp.status_code, 405)

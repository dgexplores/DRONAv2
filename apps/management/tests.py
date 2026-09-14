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


class AuditLogTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="ITA")
        self.admin = StaffUser.objects.create_user(
            employee_id="ADMINA", username="admina",
            email="admina@srms.ac.in", password="pass12345",
            role="admin", is_superuser=True,
        )
        self.category = Category.objects.create(name="Safety")
        self.client.login(employee_id='ADMINA', password='pass12345')

    def test_bulk_enroll_writes_audit(self):
        from apps.management.models import AuditLog
        course = Course.objects.create(title="AC1", description="d", category=self.category)
        self.client.post(reverse('mgmt_bulk_enroll'), {'course': course.id, 'department': ''})
        self.assertTrue(AuditLog.objects.filter(action='bulk_enroll').exists())

    def test_approve_writes_audit(self):
        from apps.management.models import AuditLog
        pending = StaffUser.objects.create_user(
            employee_id="PEND1", username="pend1", email="p@x.com",
            password="pass12345", role="staff", is_active=False,
        )
        self.client.post(reverse('approve_user', args=[pending.id]))
        self.assertTrue(AuditLog.objects.filter(action='approve_user', target_id='PEND1').exists())

    def test_prune_deletes_only_stale(self):
        from django.utils import timezone
        from datetime import timedelta
        from apps.management.models import AuditLog
        old = AuditLog.objects.create(action='bulk_enroll', detail='old')
        AuditLog.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=200))
        fresh = AuditLog.objects.create(action='bulk_enroll', detail='fresh')
        deleted = AuditLog.prune(days=180)
        self.assertEqual(deleted, 1)
        self.assertFalse(AuditLog.objects.filter(pk=old.pk).exists())
        self.assertTrue(AuditLog.objects.filter(pk=fresh.pk).exists())


class ReminderDedupTests(TestCase):
    def test_second_run_skips_recently_reminded(self):
        from django.core import mail
        from django.utils import timezone
        from datetime import timedelta
        from apps.notifications.scheduler import send_reminders_job
        dept = Department.objects.create(name="ITR", code="ITR")
        cat = Category.objects.create(name="SafetyR")
        course = Course.objects.create(title="RMand", description="d", category=cat, is_mandatory=True)
        user = StaffUser.objects.create_user(
            employee_id="REMR1", username="remr1", email="r@x.com",
            password="pass12345", role="staff", department=dept, first_name="R",
        )
        Enrollment.objects.create(staff_user=user, course=course)
        send_reminders_job()
        self.assertEqual(len(mail.outbox), 1)
        enrollment = Enrollment.objects.get(staff_user=user, course=course)
        self.assertIsNotNone(enrollment.last_reminded_at)
        send_reminders_job()
        self.assertEqual(len(mail.outbox), 1, "second run within interval must not resend")
        Enrollment.objects.filter(pk=enrollment.pk).update(
            last_reminded_at=timezone.now() - timedelta(hours=49)
        )
        send_reminders_job()
        self.assertEqual(len(mail.outbox), 2, "stale reminder must resend after interval")

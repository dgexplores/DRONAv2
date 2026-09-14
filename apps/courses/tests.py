import json
import tempfile

from django.test import TestCase, Client, override_settings
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment, LessonProgress

StaffUser = get_user_model()

# Uploaded SOP PDFs must not land in the repo's real media/ directory.
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='srms-test-media-')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
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

    def test_manager_sees_command_center_not_learner_catalog(self):
        manager = StaffUser.objects.create_user(
            employee_id="HOD001", username="hod001", email="h@y.com",
            password="pass12345", role="trainer", department=self.dept
        )
        self.client.force_login(manager)
        resp = self.client.get(reverse('dashboard'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Management Actions")
        self.assertNotContains(resp, "module-card")
        self.assertFalse(
            Enrollment.objects.filter(staff_user=manager, course=self.course).exists(),
            "Manager must not be auto-enrolled into learner courses",
        )

    def test_manager_profile_shows_scoped_overview(self):
        hr_dept = Department.objects.create(name="Corporate", code="CORP")
        manager = StaffUser.objects.create_user(
            employee_id="HOD002", username="hod002", email="h2@y.com",
            password="pass12345", role="trainer", department=hr_dept
        )
        staff = StaffUser.objects.create_user(
            employee_id="EMP300", username="emp300", email="s@y.com",
            password="pass12345", role="staff", department=self.dept
        )
        other_dept = Department.objects.create(name="HR2", code="HR2")
        other_staff = StaffUser.objects.create_user(
            employee_id="EMP301", username="emp301", email="o@y.com",
            password="pass12345", role="staff", department=other_dept
        )
        Enrollment.objects.create(staff_user=staff, course=self.course, is_completed=True)
        self.client.force_login(manager)
        resp = self.client.get(reverse('profile'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Management Overview")
        self.assertNotContains(resp, "My Enrollments")
        self.assertEqual(resp.context['active_staff'], 1)
        self.assertEqual(resp.context['completed_count'], 0)

    def test_staff_cannot_view_unassigned_mandatory_course(self):
        other = Course.objects.create(title="ERP", category=self.cat, is_mandatory=True)
        resp = self.client.get(reverse('course_detail', args=[other.id]))
        self.assertEqual(resp.status_code, 302)
        self.assertFalse(Enrollment.objects.filter(staff_user=self.user, course=other).exists())

    def test_staff_auto_enroll_elective_on_view(self):
        elective = Course.objects.create(title="ERP", category=self.cat, is_mandatory=False)
        resp = self.client.get(reverse('course_detail', args=[elective.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(Enrollment.objects.filter(staff_user=self.user, course=elective).exists())

    def test_staff_cannot_access_unassigned_mandatory_lesson(self):
        other = Course.objects.create(title="Other", category=self.cat, is_mandatory=True)
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
        """Watching a video to the end completes the lesson and the course."""
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        # Simulate the player's ~10s heartbeats across the 10-minute lesson.
        for position in range(10, 601, 10):
            resp = self.client.post(
                reverse('save_lesson_progress', args=[self.lesson.id]),
                data=json.dumps({'position': position, 'completed': False, 'watched': 10}),
                content_type='application/json'
            )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json()['lesson_completed'])
        enrollment = Enrollment.objects.get(staff_user=self.user, course=self.course)
        self.assertEqual(enrollment.progress_percent, 100)
        self.assertTrue(enrollment.is_completed)

    def test_forged_completion_flag_is_ignored_for_video(self):
        """A crafted POST must not complete a video lesson without watch time.

        Regression guard: the endpoint used to trust the client's `completed`
        flag, so anyone could POST their way to a verified certificate.
        """
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.post(
            reverse('save_lesson_progress', args=[self.lesson.id]),
            data=json.dumps({'position': 600, 'completed': True, 'watched': 0}),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.json()['lesson_completed'])
        enrollment = Enrollment.objects.get(staff_user=self.user, course=self.course)
        self.assertEqual(enrollment.progress_percent, 0)
        self.assertFalse(enrollment.is_completed)

    def test_single_heartbeat_cannot_credit_whole_video(self):
        """One oversized heartbeat is clamped to HEARTBEAT_MAX_SECONDS."""
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        self.client.post(
            reverse('save_lesson_progress', args=[self.lesson.id]),
            data=json.dumps({'position': 600, 'completed': False, 'watched': 600}),
            content_type='application/json'
        )
        progress = LessonProgress.objects.get(enrollment__staff_user=self.user, lesson=self.lesson)
        self.assertEqual(progress.watched_seconds, LessonProgress.HEARTBEAT_MAX_SECONDS)
        self.assertFalse(progress.is_completed)

    def test_watch_time_total_is_capped_at_lesson_duration(self):
        """Repeated heartbeats cannot accumulate more than one full viewing."""
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        for _ in range(100):
            self.client.post(
                reverse('save_lesson_progress', args=[self.lesson.id]),
                data=json.dumps({'position': 600, 'completed': False, 'watched': 30}),
                content_type='application/json'
            )
        progress = LessonProgress.objects.get(enrollment__staff_user=self.user, lesson=self.lesson)
        self.assertEqual(progress.watched_seconds, 600)

    def test_pdf_lesson_completes_on_acknowledgement(self):
        """PDF lessons cannot be watch-verified, so an ack is the honest floor."""
        from django.core.files.uploadedfile import SimpleUploadedFile
        pdf = SimpleUploadedFile("sop.pdf", b"%PDF-1.4 x", content_type="application/pdf")
        lesson = Lesson.objects.create(
            module=self.module, title="SOP", order=2, lesson_type='pdf', pdf_file=pdf
        )
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.post(
            reverse('save_lesson_progress', args=[lesson.id]),
            data=json.dumps({'position': 0, 'completed': True, 'watched': 0}),
            content_type='application/json'
        )
        self.assertTrue(resp.json()['lesson_completed'])

    def test_zero_duration_video_does_not_auto_complete(self):
        """A missing duration must not be treated as 'nothing to watch'."""
        lesson = Lesson.objects.create(
            module=self.module, title="NoDuration", order=3,
            lesson_type='video', duration_minutes=0
        )
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.post(
            reverse('save_lesson_progress', args=[lesson.id]),
            data=json.dumps({'position': 0, 'completed': False, 'watched': 30}),
            content_type='application/json'
        )
        self.assertFalse(resp.json()['lesson_completed'])

    def test_progress_requires_json(self):
        Enrollment.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('save_lesson_progress', args=[self.lesson.id]))
        self.assertEqual(resp.status_code, 405)


class TrainingCalendarManagerTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.cat = Category.objects.create(name="Safety")
        self.training_calendar_staff = StaffUser.objects.create_user(
            employee_id="TF1", username="tf1", email="tf1@y.com",
            password="pass12345", role="trainer", department=self.dept
        )
        self.emp = StaffUser.objects.create_user(
            employee_id="EMP300", username="emp300", email="emp300@y.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.manager_flag_route = reverse('training_calendar')

    def test_trainer_sees_manager_controls(self):
        self.assertTrue(self.client.login(employee_id='TF1', password='pass12345'), 'trainer login failed')
        resp = self.client.get(self.manager_flag_route)
        self.assertEqual(resp.status_code, 200, msg=f"got {resp.status_code} -> {getattr(resp,'url',None)}")
        self.assertTrue(resp.context['is_manager'])

    def test_staff_does_not_see_manager_controls(self):
        self.assertTrue(self.client.login(employee_id='EMP300', password='pass12345'), 'staff login failed')
        resp = self.client.get(self.manager_flag_route)
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['is_manager'])


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class SopDocumentGateTests(TestCase):
    def setUp(self):
        from django.core.files.uploadedfile import SimpleUploadedFile
        self.dept = Department.objects.create(name="IT", code="ITG")
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Gated", description="d", category=self.cat, is_mandatory=True)
        self.module = Module.objects.create(course=self.course, title="M", order=1)
        pdf = SimpleUploadedFile("sop.pdf", b"%PDF-1.4 gated", content_type="application/pdf")
        self.lesson = Lesson.objects.create(module=self.module, title="SOP", order=1, lesson_type='pdf', pdf_file=pdf)
        self.staff = StaffUser.objects.create_user(
            employee_id="EMPG1", username="empg1", email="g1@y.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.other = StaffUser.objects.create_user(
            employee_id="EMPG2", username="empg2", email="g2@y.com",
            password="pass12345", role="staff", department=self.dept
        )

    def test_unenrolled_denied(self):
        self.client.login(employee_id='EMPG2', password='pass12345')
        resp = self.client.get(reverse('sop_document', args=[self.lesson.id]))
        self.assertEqual(resp.status_code, 404)

    def test_enrolled_allowed(self):
        Enrollment.objects.create(staff_user=self.staff, course=self.course)
        self.client.login(employee_id='EMPG1', password='pass12345')
        resp = self.client.get(reverse('sop_document', args=[self.lesson.id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')

    def _fetch_media(self, user):
        """Hit the production /media/ fallback route for the SOP file."""
        from django.test import RequestFactory
        from srms_drona.views import protected_media
        path = self.lesson.pdf_file.name
        request = RequestFactory().get('/media/' + path)
        request.user = user
        return protected_media(request, path)

    def test_media_route_blocks_unenrolled_sop(self):
        """The media fallback must not bypass the enrollment check."""
        from django.http import Http404
        with self.assertRaises(Http404):
            self._fetch_media(self.other)

    def test_media_route_allows_enrolled_sop(self):
        Enrollment.objects.create(staff_user=self.staff, course=self.course)
        self.assertEqual(self._fetch_media(self.staff).status_code, 200)

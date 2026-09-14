import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse
from django.http import Http404
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course
from apps.certificates.models import Certificate
from apps.certificates.pdf_builder import generate_certificate_pdf

StaffUser = get_user_model()

# Generated PDFs must not be written into the repo's real media/ directory.
# Without this, tests dirty the working tree and leak state between runs.
TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix='srms-test-media-')


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class CertificateTests(TestCase):
    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="IT")
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.user = StaffUser.objects.create_user(
            employee_id="EMP400", username="emp400", email="a@b.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.client.login(employee_id='EMP400', password='pass12345')

    def test_certificate_id_format(self):
        from django.utils import timezone
        cert = Certificate.objects.create(staff_user=self.user, course=self.course)
        self.assertTrue(cert.certificate_id.startswith(f"SRMS-CERT-{timezone.now().year}-"))

    def test_pdf_generation(self):
        cert = generate_certificate_pdf(self.user, self.course, request_host="example.com")
        self.assertTrue(cert.pdf_file.name.startswith("certificates/"))
        self.assertTrue(cert.pdf_file.name.endswith(".pdf"))

    def test_verify_valid_certificate(self):
        cert = Certificate.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('verify_certificate', args=[cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_valid'])

    def test_verify_invalid_certificate(self):
        resp = self.client.get(reverse('verify_certificate', args=['SRMS-CERT-2026-NOPE123']))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['is_valid'])

    def test_my_certificates(self):
        Certificate.objects.create(staff_user=self.user, course=self.course)
        resp = self.client.get(reverse('my_certificates'))
        self.assertEqual(resp.status_code, 200)

    def test_public_verify_page_masks_personal_details(self):
        """The QR landing page is public, so it must not publish a full roster.

        Anyone holding a certificate ID can open this page; showing the full
        name, Employee ID, and department turns it into a staff directory.
        """
        named = StaffUser.objects.create_user(
            employee_id="EMP410", username="emp410", email="rita@srms.ac.in",
            first_name="Ritu", last_name="Arora", password="pass12345",
            role="staff", department=self.dept,
        )
        cert = Certificate.objects.create(staff_user=named, course=self.course)
        resp = self.client.get(reverse('verify_certificate', args=[cert.certificate_id]))
        self.assertEqual(resp.context['display_name'], 'Ritu A.')
        body = resp.content.decode()
        self.assertIn(cert.certificate_id, body)
        self.assertNotIn('Arora', body)
        self.assertNotIn('EMP410', body)
        self.assertNotIn('rita@srms.ac.in', body)

    def test_download_pdf(self):
        cert = generate_certificate_pdf(self.user, self.course, request_host="example.com")
        resp = self.client.get(reverse('download_certificate', args=[cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        content = b''.join(resp.streaming_content)
        self.assertTrue(content.startswith(b'%PDF'))


class ManagerCertificateDirectoryTests(TestCase):
    def setUp(self):
        self.dept1 = Department.objects.create(name="IT", code="IT")
        self.dept2 = Department.objects.create(name="HR", code="HR")
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.manager = StaffUser.objects.create_user(
            employee_id="TRAIN1", username="train1", email="train@b.com",
            password="pass12345", role="trainer"
        )
        self.staff = StaffUser.objects.create_user(
            employee_id="EMP500", username="emp500", email="s@b.com",
            password="pass12345", role="staff", department=self.dept1
        )
        cert = Certificate.objects.create(staff_user=self.staff, course=self.course)
        self.cert_id = cert.certificate_id
        self.client.login(employee_id='TRAIN1', password='pass12345')

    def test_manager_sees_directory_and_all_certs(self):
        resp = self.client.get(reverse('my_certificates'))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_manager'])
        self.assertEqual(resp.context['all_cert_count'], 1)

    def test_manager_search_by_employee_id(self):
        resp = self.client.get(reverse('my_certificates'), {'q': 'EMP500'})
        self.assertEqual(resp.context['all_cert_count'], 1)
        resp = self.client.get(reverse('my_certificates'), {'q': 'NOMATCH'})
        self.assertEqual(resp.context['all_cert_count'], 0)

    def test_manager_filter_by_department(self):
        resp = self.client.get(reverse('my_certificates'), {'dept': self.dept2.id})
        self.assertEqual(resp.context['all_cert_count'], 0)
        resp = self.client.get(reverse('my_certificates'), {'dept': self.dept1.id})
        self.assertEqual(resp.context['all_cert_count'], 1)

    def test_staff_does_not_see_directory(self):
        self.client.login(employee_id='EMP500', password='pass12345')
        resp = self.client.get(reverse('my_certificates'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(resp.context['is_manager'])

    def test_verify_certificate_is_public(self):
        resp = self.client.get(reverse('verify_certificate', args=[self.cert_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.context['is_valid'])


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class ProtectedMediaTests(TestCase):
    """The production /media/ route must authorise each file, not just the login.

    Regression guard: the route used to be a blanket login_required, so any
    authenticated staff member could pull another staff member's certificate
    PDF straight out of /media/certificates/ by guessing the filename.
    """

    def setUp(self):
        self.dept = Department.objects.create(name="IT", code="ITM")
        self.cat = Category.objects.create(name="Safety")
        self.course = Course.objects.create(title="Safety", category=self.cat)
        self.owner = StaffUser.objects.create_user(
            employee_id="EMP700", username="emp700", email="o@b.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.other = StaffUser.objects.create_user(
            employee_id="EMP701", username="emp701", email="p@b.com",
            password="pass12345", role="staff", department=self.dept
        )
        self.cert = generate_certificate_pdf(self.owner, self.course, request_host="example.com")
        self.media_path = self.cert.pdf_file.name

    def _fetch(self, user, path):
        from django.test import RequestFactory
        from srms_drona.views import protected_media
        request = RequestFactory().get('/media/' + path)
        request.user = user
        return protected_media(request, path)

    def test_owner_can_fetch_own_certificate(self):
        self.assertEqual(self._fetch(self.owner, self.media_path).status_code, 200)

    def test_other_staff_cannot_fetch_someone_elses_certificate(self):
        with self.assertRaises(Http404):
            self._fetch(self.other, self.media_path)

    def test_manager_can_fetch_any_certificate(self):
        manager = StaffUser.objects.create_user(
            employee_id="TRAIN9", username="train9", email="m@b.com",
            password="pass12345", role="trainer"
        )
        self.assertEqual(self._fetch(manager, self.media_path).status_code, 200)

    def test_unknown_certificate_path_is_not_served(self):
        with self.assertRaises(Http404):
            self._fetch(self.owner, 'certificates/SRMS-CERT-2026-DEADBEEF.pdf')

    def test_path_traversal_is_rejected(self):
        with self.assertRaises(Http404):
            self._fetch(self.owner, '../../etc/passwd')

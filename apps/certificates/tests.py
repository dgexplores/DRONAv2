from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from apps.users.models import Department
from apps.courses.models import Category, Course
from apps.certificates.models import Certificate
from apps.certificates.pdf_builder import generate_certificate_pdf

StaffUser = get_user_model()


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
        cert = Certificate.objects.create(staff_user=self.user, course=self.course)
        self.assertTrue(cert.certificate_id.startswith("SRMS-CERT-2026-"))

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

    def test_download_pdf(self):
        cert = generate_certificate_pdf(self.user, self.course, request_host="example.com")
        resp = self.client.get(reverse('download_certificate', args=[cert.certificate_id]))
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp['Content-Type'], 'application/pdf')
        self.assertTrue(resp.content.startswith(b'%PDF'))


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

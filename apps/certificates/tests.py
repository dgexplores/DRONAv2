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

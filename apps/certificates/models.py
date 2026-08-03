import uuid
from django.db import models
from django.conf import settings
from apps.courses.models import Course

def generate_cert_id():
    return f"SRMS-CERT-2026-{uuid.uuid4().hex[:8].upper()}"

class Certificate(models.Model):
    certificate_id = models.CharField(max_length=50, unique=True, default=generate_cert_id)
    staff_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='certificates')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='certificates')
    issued_at = models.DateTimeField(auto_now_add=True)
    pdf_file = models.FileField(upload_to='certificates/', blank=True, null=True)

    class Meta:
        unique_together = ('staff_user', 'course')

    def __str__(self):
        return f"Certificate {self.certificate_id} - {self.staff_user.get_full_name()} ({self.course.title})"

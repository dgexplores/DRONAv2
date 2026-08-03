from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
import os
from django.conf import settings

from apps.certificates.models import Certificate
from apps.certificates.pdf_builder import generate_certificate_pdf

@login_required
def my_certificates_view(request):
    certificates = Certificate.objects.filter(staff_user=request.user).select_related('course')
    return render(request, 'certificates/my_certificates.html', {'certificates': certificates})

def verify_certificate_view(request, cert_id):
    try:
        certificate = Certificate.objects.select_related('staff_user', 'course', 'staff_user__department').get(certificate_id=cert_id)
        is_valid = True
    except Certificate.DoesNotExist:
        certificate = None
        is_valid = False

    context = {
        'cert_id': cert_id,
        'certificate': certificate,
        'is_valid': is_valid,
    }
    return render(request, 'certificates/verify.html', context)

@login_required
def download_certificate_pdf(request, cert_id):
    certificate = get_object_or_404(Certificate, certificate_id=cert_id, staff_user=request.user)
    
    if not certificate.pdf_file or not os.path.exists(certificate.pdf_file.path):
        # Regenerate PDF
        host = request.get_host()
        generate_certificate_pdf(request.user, certificate.course, request_host=host)
        certificate.refresh_from_db()

    if certificate.pdf_file and os.path.exists(certificate.pdf_file.path):
        with open(certificate.pdf_file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{certificate.certificate_id}.pdf"'
            return response
    raise Http404("Certificate PDF not found.")

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, Http404
from django.db.models import Q
import os
from django.conf import settings

from apps.certificates.models import Certificate
from apps.certificates.pdf_builder import generate_certificate_pdf
from apps.users.models import Department
from apps.courses.models import Course

def _is_manager(user):
    return user.role in ('trainer', 'admin') or user.is_superuser or user.is_staff

@login_required
def my_certificates_view(request):
    # Super-admin / HR / HOD: role-aware directory of who earned which certificate,
    # with search + filters. Regular staff only see their own.
    if _is_manager(request.user):
        certs = Certificate.objects.select_related('staff_user', 'course', 'staff_user__department')

        q = request.GET.get('q', '').strip()
        dept_id = request.GET.get('dept', '')
        course_id = request.GET.get('course', '')

        if q:
            certs = certs.filter(
                Q(staff_user__employee_id__icontains=q)
                | Q(staff_user__first_name__icontains=q)
                | Q(staff_user__last_name__icontains=q)
                | Q(staff_user__email__icontains=q)
            )
        if dept_id:
            certs = certs.filter(staff_user__department_id=dept_id)
        if course_id:
            certs = certs.filter(course_id=course_id)

        certs = certs.order_by('-issued_at')

        context = {
            'certificates': certs,
            'is_manager': True,
            'departments': Department.objects.all().order_by('name'),
            'courses_offered': Course.objects.all().order_by('title'),
            'query': q,
            'selected_dept': dept_id,
            'selected_course': course_id,
            'all_cert_count': certs.count(),
        }
        return render(request, 'certificates/my_certificates.html', context)

    certificates = Certificate.objects.filter(staff_user=request.user).select_related('course')
    return render(request, 'certificates/my_certificates.html', {'certificates': certificates, 'is_manager': False})

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
    qs = Certificate.objects.filter(certificate_id=cert_id)
    if not _is_manager(request.user):
        qs = qs.filter(staff_user=request.user)
    certificate = get_object_or_404(qs)
    
    if not certificate.pdf_file or not os.path.exists(certificate.pdf_file.path):
        # Regenerate PDF
        host = request.get_host()
        generate_certificate_pdf(certificate.staff_user, certificate.course, request_host=host)
        certificate.refresh_from_db()

    if certificate.pdf_file and os.path.exists(certificate.pdf_file.path):
        with open(certificate.pdf_file.path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/pdf')
            response['Content-Disposition'] = f'inline; filename="{certificate.certificate_id}.pdf"'
            return response
    raise Http404("Certificate PDF not found.")

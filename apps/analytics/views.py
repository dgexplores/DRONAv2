import csv
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import StreamingHttpResponse
from django.db.models import Count, Avg, Q, Sum
from django.core.paginator import Paginator
from django.contrib import messages
from django.utils.translation import gettext_lazy as _

from apps.users.models import StaffUser, Department
from apps.courses.models import Course, Enrollment, LessonProgress
from apps.quizzes.models import QuizAttempt, Quiz

@login_required
def hr_dashboard_view(request):
    if not bool(getattr(request.user, 'is_manager', False)):
        messages.error(request, _("Access restricted to HODs and HR Administrators."))
        return redirect('dashboard')

    departments = Department.objects.all()
    dept_stats = []

    for dept in departments:
        staff_members = StaffUser.objects.filter(department=dept)
        total_staff = staff_members.count()
        enrollments = Enrollment.objects.filter(staff_user__department=dept)
        total_enrollments = enrollments.count()
        completed_enrollments = enrollments.filter(is_completed=True).count()
        completion_rate = round((completed_enrollments / total_enrollments) * 100, 1) if total_enrollments > 0 else 0

        dept_stats.append({
            'department': dept,
            'total_staff': total_staff,
            'total_enrollments': total_enrollments,
            'completed_enrollments': completed_enrollments,
            'completion_rate': completion_rate,
        })

    total_staff_count = StaffUser.objects.count()
    total_courses_count = Course.objects.count()
    from apps.certificates.models import Certificate as _Cert
    total_cert_count = _Cert.objects.count()
    total_completed_enrollments = Enrollment.objects.filter(is_completed=True).count()
    avg_quiz_score = QuizAttempt.objects.aggregate(Avg('score'))['score__avg'] or 0.0
    total_learning_hours = (Enrollment.objects.aggregate(Sum('watch_seconds'))['watch_seconds__sum'] or 0) / 3600

    recent_attempts = QuizAttempt.objects.select_related('staff_user', 'quiz').order_by('-attempted_at')[:10]

    is_admin = request.user.role in ('admin', 'trainer') or request.user.is_superuser
    pending_qs = StaffUser.objects.filter(is_active=False).select_related('department').order_by('date_joined') if is_admin else StaffUser.objects.none()
    paginator = Paginator(pending_qs, 20)
    pending_page = paginator.get_page(request.GET.get('pending_page'))
    pending_users = pending_page

    context = {
        'dept_stats': dept_stats,
        'total_staff_count': total_staff_count,
        'total_courses_count': total_courses_count,
        'total_cert_count': total_cert_count,
        'total_completed_enrollments': total_completed_enrollments,
        'avg_quiz_score': round(avg_quiz_score, 1),
        'total_learning_hours': round(total_learning_hours, 1),
        'recent_attempts': recent_attempts,
        'pending_users': pending_users,
        'pending_page': pending_page,
        'is_admin': is_admin,
    }
    return render(request, 'analytics/hr_dashboard.html', context)

@login_required
def export_staff_report_csv(request):
    if not bool(getattr(request.user, 'is_manager', False)):
        return render(request, 'errors/403.html', status=403)

    # Streaming + annotated counts: avoids loading all rows and N+1 per-row counts.
    qs = (StaffUser.objects.select_related('department')
          .annotate(
              total_e=Count('enrollments', distinct=True),
              completed_e=Count('enrollments', filter=Q(enrollments__is_completed=True), distinct=True),
              cert_n=Count('certificates', distinct=True),
          )
          .order_by('employee_id')
          .iterator(chunk_size=500))

    def rows():
        yield ['Employee ID', 'Name', 'Department', 'Role', 'Enrolled Courses', 'Completed Courses', 'Certificates Earned']
        for staff in qs:
            yield [
                staff.employee_id,
                staff.get_full_name(),
                staff.department.name if staff.department else 'N/A',
                staff.get_role_display(),
                staff.total_e,
                staff.completed_e,
                staff.cert_n,
            ]

    class Echo:
        def write(self, value):
            return value

    writer = csv.writer(Echo())
    response = StreamingHttpResponse((writer.writerow(r) for r in rows()), content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="srms_dorna_staff_report.csv"'
    return response

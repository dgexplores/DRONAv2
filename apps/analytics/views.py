import csv
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.db.models import Count, Avg, Q
from django.contrib import messages

from apps.users.models import StaffUser, Department
from apps.courses.models import Course, Enrollment, LessonProgress
from apps.quizzes.models import QuizAttempt, Quiz

@login_required
def hr_dashboard_view(request):
    if request.user.role not in ['trainer', 'admin'] and not request.user.is_staff:
        messages.error(request, "Access restricted to HODs and HR Administrators.")
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
    total_cert_count = Enrollment.objects.filter(is_completed=True).count()
    avg_quiz_score = QuizAttempt.objects.aggregate(Avg('score'))['score__avg'] or 0.0

    recent_attempts = QuizAttempt.objects.select_related('staff_user', 'quiz').order_by('-attempted_at')[:10]

    is_admin = request.user.role == 'admin' or request.user.is_superuser
    pending_users = StaffUser.objects.filter(is_active=False).order_by('date_joined') if is_admin else []

    context = {
        'dept_stats': dept_stats,
        'total_staff_count': total_staff_count,
        'total_courses_count': total_courses_count,
        'total_cert_count': total_cert_count,
        'avg_quiz_score': round(avg_quiz_score, 1),
        'recent_attempts': recent_attempts,
        'pending_users': pending_users,
        'is_admin': is_admin,
    }
    return render(request, 'analytics/hr_dashboard.html', context)

@login_required
def export_staff_report_csv(request):
    if request.user.role not in ['trainer', 'admin'] and not request.user.is_staff:
        return HttpResponse("Unauthorized", status=403)

    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="srms_drona_staff_report.csv"'

    writer = csv.writer(response)
    writer.writerow(['Employee ID', 'Name', 'Department', 'Role', 'Enrolled Courses', 'Completed Courses', 'Certificates Earned'])

    staff_list = StaffUser.objects.select_related('department').prefetch_related('enrollments', 'certificates').all()
    for staff in staff_list:
        total_e = staff.enrollments.count()
        completed_e = staff.enrollments.filter(is_completed=True).count()
        certs = staff.certificates.count()
        writer.writerow([
            staff.employee_id,
            staff.get_full_name(),
            staff.department.name if staff.department else 'N/A',
            staff.get_role_display(),
            total_e,
            completed_e,
            certs
        ])

    return response

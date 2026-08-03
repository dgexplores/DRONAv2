from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
import json

from apps.courses.models import Course, Category, Module, Lesson, Enrollment, LessonProgress
from apps.users.models import Department

@login_required
def dashboard_view(request):
    user = request.user
    
    # Auto-enroll in mandatory courses for user's department
    if user.department:
        mandatory_courses = Course.objects.filter(is_mandatory=True, target_departments=user.department)
        for course in mandatory_courses:
            Enrollment.objects.get_or_create(staff_user=user, course=course)

    user_enrollments = Enrollment.objects.filter(staff_user=user).select_related('course')
    enrolled_course_ids = user_enrollments.values_list('course_id', flat=True)

    available_courses = Course.objects.exclude(id__in=enrolled_course_ids)
    categories = Category.objects.all()

    # Metrics
    completed_count = user_enrollments.filter(is_completed=True).count()
    in_progress_count = user_enrollments.filter(is_completed=False).count()
    certificates_count = user.certificates.count()

    context = {
        'user_enrollments': user_enrollments,
        'available_courses': available_courses,
        'categories': categories,
        'completed_count': completed_count,
        'in_progress_count': in_progress_count,
        'certificates_count': certificates_count,
    }
    return render(request, 'courses/dashboard.html', context)

@login_required
def course_detail_view(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    enrollment, created = Enrollment.objects.get_or_create(staff_user=request.user, course=course)
    
    modules = course.modules.prefetch_related('lessons').all()
    
    # Fetch lesson progress for current enrollment
    progress_map = {
        lp.lesson_id: lp 
        for lp in LessonProgress.objects.filter(enrollment=enrollment)
    }

    # Quiz status
    quiz_attempts = request.user.quiz_attempts.filter(quiz__course=course).order_by('-attempted_at')
    latest_attempt = quiz_attempts.first()

    context = {
        'course': course,
        'enrollment': enrollment,
        'modules': modules,
        'progress_map': progress_map,
        'latest_attempt': latest_attempt,
    }
    return render(request, 'courses/course_detail.html', context)

@login_required
def lesson_view(request, lesson_id):
    lesson = get_object_or_404(Lesson, id=lesson_id)
    course = lesson.module.course
    enrollment, _ = Enrollment.objects.get_or_create(staff_user=request.user, course=course)
    
    progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)

    # Next / Prev lesson navigation
    all_lessons = list(Lesson.objects.filter(module__course=course).order_by('module__order', 'order'))
    curr_idx = all_lessons.index(lesson)
    prev_lesson = all_lessons[curr_idx - 1] if curr_idx > 0 else None
    next_lesson = all_lessons[curr_idx + 1] if curr_idx < len(all_lessons) - 1 else None

    context = {
        'lesson': lesson,
        'course': course,
        'enrollment': enrollment,
        'progress': progress,
        'prev_lesson': prev_lesson,
        'next_lesson': next_lesson,
    }
    return render(request, 'courses/lesson.html', context)

@login_required
@csrf_exempt
def save_lesson_progress(request, lesson_id):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            position = data.get('position', 0)
            completed = data.get('completed', False)

            lesson = get_object_or_404(Lesson, id=lesson_id)
            enrollment, _ = Enrollment.objects.get_or_create(staff_user=request.user, course=lesson.module.course)
            
            progress, _ = LessonProgress.objects.get_or_create(enrollment=enrollment, lesson=lesson)
            progress.last_position_seconds = int(position)
            if completed:
                progress.is_completed = True
            progress.save()

            enrollment.update_progress()

            return JsonResponse({'status': 'success', 'progress_percent': enrollment.progress_percent})
        except Exception as e:
            return JsonResponse({'status': 'error', 'message': str(e)}, status=400)
    return JsonResponse({'status': 'invalid method'}, status=405)

@login_required
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    Enrollment.objects.get_or_create(staff_user=request.user, course=course)
    return redirect('course_detail', course_id=course.id)

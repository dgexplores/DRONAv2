from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.db.models import Count

from apps.users.models import StaffUser, Department
from apps.courses.models import Course, Module, Lesson, Enrollment, Category
from apps.quizzes.models import Quiz
from apps.management.forms import CourseForm, ModuleForm, LessonForm, EnrollForm


def _can_manage(user):
    return user.role in ('admin', 'trainer') or user.is_superuser


def _require_manager(request):
    if not _can_manage(request.user):
        messages.error(request, _("Access restricted to administrators and trainers."))
        return redirect('dashboard')
    return None


@login_required
def console_home(request):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    context = {
        'course_count': Course.objects.count(),
        'module_count': Module.objects.count(),
        'lesson_count': Lesson.objects.count(),
        'quiz_count': Quiz.objects.count(),
        'category_count': Category.objects.count(),
        'active_staff_count': StaffUser.objects.filter(is_active=True).count(),
        'enrollment_count': Enrollment.objects.count(),
        'pending_count': StaffUser.objects.filter(is_active=False).count(),
    }
    return render(request, 'management/console_home.html', context)


@login_required
def course_list(request):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    courses = (Course.objects.select_related('category')
               .annotate(module_count=Count('modules'), enrollment_count=Count('enrollments'))
               .order_by('-created_at'))
    return render(request, 'management/course_list.html', {'courses': courses})


@login_required
def course_create(request):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    if request.method == 'POST':
        form = CourseForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, f"Course '{form.instance.title}' created. Add modules and lessons.")
            return redirect('mgmt_course_detail', course_id=form.instance.id)
    else:
        form = CourseForm()
    return render(request, 'management/course_form.html', {'form': form, 'title': _('Create Course'), 'is_new': True})


@login_required
def course_edit(request, course_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        form = CourseForm(request.POST, instance=course)
        if form.is_valid():
            form.save()
            messages.success(request, "Course updated.")
            return redirect('mgmt_course_detail', course_id=course.id)
    else:
        form = CourseForm(instance=course)
    return render(request, 'management/course_form.html', {'form': form, 'title': _('Edit Course'), 'course': course, 'is_new': False})


@login_required
def course_delete(request, course_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    course = get_object_or_404(Course, id=course_id)
    if request.method == 'POST':
        title = course.title
        course.delete()
        messages.warning(request, f"Course '{title}' deleted.")
        return redirect('mgmt_course_list')
    return redirect('mgmt_course_detail', course_id=course_id)


@login_required
def course_detail(request, course_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    course = get_object_or_404(Course, id=course_id)
    modules = course.modules.prefetch_related('lessons').all()

    if request.method == 'POST':
        # Add a module
        module_form = ModuleForm(request.POST)
        if module_form.is_valid():
            module = module_form.save(commit=False)
            module.course = course
            module.save()
            messages.success(request, f"Module '{module.title}' added.")
            return redirect('mgmt_course_detail', course_id=course.id)
    else:
        module_form = ModuleForm()

    context = {
        'course': course,
        'modules': modules,
        'module_form': module_form,
        'enrollment_count': course.enrollments.count(),
    }
    return render(request, 'management/course_detail.html', context)


@login_required
def module_edit(request, module_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    module = get_object_or_404(Module, id=module_id)
    if request.method == 'POST':
        form = ModuleForm(request.POST, instance=module)
        if form.is_valid():
            form.save()
            messages.success(request, "Module updated.")
            return redirect('mgmt_course_detail', course_id=module.course.id)
    else:
        form = ModuleForm(instance=module)
    return render(request, 'management/module_form.html', {'form': form, 'module': module})


@login_required
def module_delete(request, module_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    module = get_object_or_404(Module, id=module_id)
    course_id = module.course.id
    if request.method == 'POST':
        module.delete()
        messages.warning(request, "Module deleted.")
    return redirect('mgmt_course_detail', course_id=course_id)


@login_required
def lesson_create(request, module_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    module = get_object_or_404(Module, id=module_id)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES)
        if form.is_valid():
            lesson = form.save(commit=False)
            lesson.module = module
            lesson.save()
            messages.success(request, f"Lesson '{lesson.title}' added.")
            return redirect('mgmt_course_detail', course_id=module.course.id)
    else:
        form = LessonForm()
    return render(request, 'management/lesson_form.html', {'form': form, 'module': module, 'title': _('Add Lesson')})


@login_required
def lesson_edit(request, lesson_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    lesson = get_object_or_404(Lesson, id=lesson_id)
    if request.method == 'POST':
        form = LessonForm(request.POST, request.FILES, instance=lesson)
        if form.is_valid():
            form.save()
            messages.success(request, "Lesson updated.")
            return redirect('mgmt_course_detail', course_id=lesson.module.course.id)
    else:
        form = LessonForm(instance=lesson)
    return render(request, 'management/lesson_form.html', {'form': form, 'lesson': lesson, 'module': lesson.module, 'title': _('Edit Lesson')})


@login_required
def lesson_delete(request, lesson_id):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    lesson = get_object_or_404(Lesson, id=lesson_id)
    course_id = lesson.module.course.id
    if request.method == 'POST':
        lesson.delete()
        messages.warning(request, "Lesson deleted.")
    return redirect('mgmt_course_detail', course_id=course_id)


@login_required
def bulk_enroll(request):
    redirect_resp = _require_manager(request)
    if redirect_resp:
        return redirect_resp

    preview = None
    if request.method == 'POST':
        form = EnrollForm(request.POST)
        if form.is_valid():
            course = form.cleaned_data['course']
            department = form.cleaned_data['department']

            staff = StaffUser.objects.filter(is_active=True)
            if department:
                staff = staff.filter(department=department)

            created = 0
            already = 0
            for user in staff:
                _, was_created = Enrollment.objects.get_or_create(staff_user=user, course=course)
                if was_created:
                    created += 1
                else:
                    already += 1

            if department:
                scope = f"{department.name} ({staff.count() + already + created} staff)"
            else:
                scope = f"all departments ({staff.count() + already + created} staff)"
            messages.success(
                request,
                f"Enrolled {created} staff into '{course.title}'. {already} were already enrolled ({scope}).",
            )
            return redirect('mgmt_course_detail', course_id=course.id)
    else:
        form = EnrollForm()

    return render(request, 'management/bulk_enroll.html', {'form': form})

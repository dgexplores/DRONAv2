from django.contrib import admin
from django.contrib import messages
from apps.courses.models import Category, Course, Module, Lesson, Enrollment, LessonProgress

class LessonInline(admin.TabularInline):
    model = Lesson
    extra = 0
    fields = ('title', 'lesson_type', 'order', 'duration_minutes')

class ModuleInline(admin.StackedInline):
    model = Module
    extra = 0
    inlines = [LessonInline]

class CourseAdmin(admin.ModelAdmin):
    list_display = ('title', 'category', 'is_mandatory', 'created_at')
    list_filter = ('category', 'is_mandatory')
    search_fields = ('title', 'description')
    filter_horizontal = ('target_departments',)
    inlines = [ModuleInline]

    actions = ['enroll_target_department_staff']

    @admin.action(description="Enroll all active staff in target departments")
    def enroll_target_department_staff(self, request, queryset):
        from apps.users.models import StaffUser
        created = 0
        already = 0
        for course in queryset:
            depts = list(course.target_departments.all())
            staff = StaffUser.objects.filter(is_active=True, department__in=depts)
            for user in staff:
                _, was_created = Enrollment.objects.get_or_create(staff_user=user, course=course)
                if was_created:
                    created += 1
                else:
                    already += 1
        self.message_user(
            request,
            f"Enrolled {created} staff ({already} already enrolled) across {queryset.count()} course(s).",
            level=messages.SUCCESS,
        )

class ModuleAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'order')
    list_filter = ('course',)
    inlines = [LessonInline]

class LessonAdmin(admin.ModelAdmin):
    list_display = ('title', 'module', 'lesson_type', 'order')
    list_filter = ('lesson_type', 'module__course')

class EnrollmentAdmin(admin.ModelAdmin):
    list_display = ('staff_user', 'course', 'progress_percent', 'is_completed', 'enrolled_at')
    list_filter = ('is_completed', 'course')

class LessonProgressAdmin(admin.ModelAdmin):
    list_display = ('enrollment', 'lesson', 'is_completed', 'last_position_seconds')

admin.site.register(Category)
admin.site.register(Course, CourseAdmin)
admin.site.register(Module, ModuleAdmin)
admin.site.register(Lesson, LessonAdmin)
admin.site.register(Enrollment, EnrollmentAdmin)
admin.site.register(LessonProgress, LessonProgressAdmin)

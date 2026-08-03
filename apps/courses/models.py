from django.db import models
from django.conf import settings
from apps.users.models import Department

class Category(models.Model):
    name = models.CharField(max_length=100)
    name_hi = models.CharField(max_length=100, blank=True)
    icon = models.CharField(max_length=50, default='book-open')
    description = models.TextField(blank=True)

    class Meta:
        verbose_name_plural = "Categories"

    def __str__(self):
        return self.name

class Course(models.Model):
    title = models.CharField(max_length=200)
    title_hi = models.CharField(max_length=200, blank=True)
    description = models.TextField()
    description_hi = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.CASCADE, related_name='courses')
    is_mandatory = models.BooleanField(default=False)
    target_departments = models.ManyToManyField(Department, blank=True, related_name='target_courses')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def get_total_lessons(self):
        return Lesson.objects.filter(module__course=self).count()

class Module(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='modules')
    title = models.CharField(max_length=200)
    title_hi = models.CharField(max_length=200, blank=True)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.course.title} - Module {self.order}: {self.title}"

class Lesson(models.Model):
    LESSON_TYPES = (
        ('video', 'Video Lesson'),
        ('pdf', 'SOP PDF Manual'),
    )

    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='lessons')
    title = models.CharField(max_length=200)
    title_hi = models.CharField(max_length=200, blank=True)
    lesson_type = models.CharField(max_length=10, choices=LESSON_TYPES, default='video')
    video_url = models.CharField(max_length=500, blank=True)
    pdf_file = models.FileField(upload_to='sop_documents/', blank=True, null=True)
    sop_text = models.TextField(blank=True, help_text="Extracted text from SOP manual for AI processing")
    duration_minutes = models.PositiveIntegerField(default=10)
    order = models.PositiveIntegerField(default=1)

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.module.title} - Lesson {self.order}: {self.title}"

class Enrollment(models.Model):
    staff_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='enrollments')
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='enrollments')
    enrolled_at = models.DateTimeField(auto_now_add=True)
    is_completed = models.BooleanField(default=False)
    completed_at = models.DateTimeField(null=True, blank=True)
    progress_percent = models.IntegerField(default=0)

    class Meta:
        unique_together = ('staff_user', 'course')

    def update_progress(self):
        total_lessons = self.course.get_total_lessons()
        if total_lessons == 0:
            self.progress_percent = 100
        else:
            completed = LessonProgress.objects.filter(
                enrollment=self,
                is_completed=True
            ).count()
            self.progress_percent = int((completed / total_lessons) * 100)
        
        if self.progress_percent >= 100 and not self.is_completed:
            self.is_completed = True
            from django.utils import timezone
            self.completed_at = timezone.now()
        self.save()

    def __str__(self):
        return f"{self.staff_user.employee_id} enrolled in {self.course.title} ({self.progress_percent}%)"

class LessonProgress(models.Model):
    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progresses')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progresses')
    is_completed = models.BooleanField(default=False)
    last_position_seconds = models.PositiveIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')

    def __str__(self):
        return f"{self.enrollment.staff_user.employee_id} - {self.lesson.title}: {'Completed' if self.is_completed else 'In Progress'}"

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
    watch_seconds = models.PositiveIntegerField(default=0, help_text="Total active learning time watched (seconds)")
    last_reminded_at = models.DateTimeField(null=True, blank=True, help_text="Last reminder email sent (dedup)")

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
            self.progress_percent = max(0, min(100, int((completed / total_lessons) * 100)))
        
        if self.progress_percent >= 100 and not self.is_completed:
            self.is_completed = True
            from django.utils import timezone
            self.completed_at = timezone.now()
        self.save(update_fields=['progress_percent', 'is_completed', 'completed_at'])

    def __str__(self):
        return f"{self.staff_user.employee_id} enrolled in {self.course.title} ({self.progress_percent}%)"

class LessonProgress(models.Model):
    # Fraction of a video's duration that must be watched before the lesson
    # counts as complete. Deliberately not 1.0: the player heartbeats in ~10s
    # steps, so the final partial step would leave a legitimately-watched
    # lesson just under 100% and block the certificate.
    COMPLETION_RATIO = 0.9
    # Upper bound on a single heartbeat, in seconds. Stops a hand-crafted
    # request from crediting an entire video in one call.
    HEARTBEAT_MAX_SECONDS = 30

    enrollment = models.ForeignKey(Enrollment, on_delete=models.CASCADE, related_name='lesson_progresses')
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name='progresses')
    is_completed = models.BooleanField(default=False)
    last_position_seconds = models.PositiveIntegerField(default=0)
    watched_seconds = models.PositiveIntegerField(
        default=0,
        help_text="Server-accumulated watch time for this lesson (seconds)",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('enrollment', 'lesson')

    @property
    def lesson_duration_seconds(self):
        return max(0, (self.lesson.duration_minutes or 0) * 60)

    @property
    def requires_watch_time(self):
        """True when completion can be verified from watch time.

        Video lessons with a known duration can be verified. PDF lessons and
        lessons with a missing/zero duration cannot, so they fall back to an
        explicit acknowledgement rather than auto-completing on zero.
        """
        return self.lesson.lesson_type == 'video' and self.lesson_duration_seconds > 0

    @property
    def required_watch_seconds(self):
        return int(self.lesson_duration_seconds * self.COMPLETION_RATIO)

    def register_watch(self, seconds):
        """Accumulate watch time server-side and derive completion.

        The running total is capped at the lesson duration, so repeated
        heartbeats can never inflate it past one full viewing. Returns the
        number of seconds actually credited (0 once the cap is reached).
        """
        try:
            seconds = int(seconds)
        except (TypeError, ValueError):
            seconds = 0
        seconds = max(0, min(seconds, self.HEARTBEAT_MAX_SECONDS))

        before = self.watched_seconds
        self.watched_seconds = min(before + seconds, self.lesson_duration_seconds)
        credited = self.watched_seconds - before

        if self.watched_seconds >= self.required_watch_seconds:
            self.is_completed = True
        return credited

    def acknowledge(self):
        """Complete a lesson that cannot be watch-verified (e.g. a PDF SOP)."""
        self.is_completed = True

    def __str__(self):
        return f"{self.enrollment.staff_user.employee_id} - {self.lesson.title}: {'Completed' if self.is_completed else 'In Progress'}"


class TrainingSession(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course = models.ForeignKey(Course, on_delete=models.SET_NULL, null=True, blank=True, related_name='training_sessions')
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    location = models.CharField(max_length=200, blank=True)
    is_mandatory = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='training_sessions'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['date', 'start_time']

    def clean(self):
        from django.core.exceptions import ValidationError
        super().clean()
        if self.end_time and self.end_time <= self.start_time:
            raise ValidationError({'end_time': 'End time must be after start time.'})

    def __str__(self):
        return f"{self.title} ({self.date})"

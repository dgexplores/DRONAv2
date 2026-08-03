from django.db import models
from django.conf import settings
from apps.courses.models import Course, Module

class Quiz(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes', null=True, blank=True)
    module = models.OneToOneField(Module, on_delete=models.CASCADE, related_name='quiz', null=True, blank=True)
    title = models.CharField(max_length=200)
    title_hi = models.CharField(max_length=200, blank=True)
    passing_score = models.IntegerField(default=70) # Percentage threshold e.g. 70%

    def __str__(self):
        return f"Quiz: {self.title}"

class Question(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    text = models.TextField()
    text_hi = models.TextField(blank=True)
    explanation = models.TextField(blank=True)
    explanation_hi = models.TextField(blank=True)
    points = models.IntegerField(default=1)

    def __str__(self):
        return f"Question {self.id}: {self.text[:50]}"

class Choice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='choices')
    text = models.CharField(max_length=300)
    text_hi = models.CharField(max_length=300, blank=True)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.text} ({'Correct' if self.is_correct else 'Incorrect'})"

class QuizAttempt(models.Model):
    staff_user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='quiz_attempts')
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    score = models.FloatField() # e.g., 80.0 %
    total_questions = models.IntegerField(default=5)
    passed = models.BooleanField(default=False)
    attempted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.staff_user.employee_id} - {self.quiz.title}: {self.score}% ({'PASS' if self.passed else 'FAIL'})"

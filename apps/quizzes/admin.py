from django.contrib import admin
from apps.quizzes.models import Quiz, Question, Choice, QuizAttempt

class ChoiceInline(admin.TabularInline):
    model = Choice
    extra = 1

class QuestionAdmin(admin.ModelAdmin):
    list_display = ('text', 'quiz', 'points')
    list_filter = ('quiz',)
    inlines = [ChoiceInline]

class QuizAdmin(admin.ModelAdmin):
    list_display = ('title', 'course', 'module', 'passing_score')
    search_fields = ('title',)

class QuizAttemptAdmin(admin.ModelAdmin):
    list_display = ('staff_user', 'quiz', 'score', 'passed', 'attempted_at')
    list_filter = ('passed', 'quiz')

admin.site.register(Quiz, QuizAdmin)
admin.site.register(Question, QuestionAdmin)
admin.site.register(Choice)
admin.site.register(QuizAttempt, QuizAttemptAdmin)

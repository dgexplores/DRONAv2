from django import forms
from django.utils.translation import gettext_lazy as _

from apps.users.models import StaffUser, Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['title', 'title_hi', 'description', 'description_hi', 'category', 'is_mandatory', 'target_departments']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Laboratory Safety & Handling'}),
            'title_hi': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Hindi title (optional)'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'description_hi': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'category': forms.Select(attrs={'class': 'form-input'}),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'form-check'}),
            'target_departments': forms.SelectMultiple(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['category'].empty_label = _("Select category")
        if self.instance and self.instance.pk:
            self.fields['target_departments'].help_text = _("Leave empty to make this course available to all departments.")


class ModuleForm(forms.ModelForm):
    class Meta:
        model = Module
        fields = ['title', 'title_hi', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Module 1: Introduction'}),
            'title_hi': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Hindi title (optional)'}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
        }


class LessonForm(forms.ModelForm):
    class Meta:
        model = Lesson
        fields = ['title', 'title_hi', 'lesson_type', 'video_url', 'pdf_file', 'sop_text', 'duration_minutes', 'order']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Personal Protective Equipment'}),
            'title_hi': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Hindi title (optional)'}),
            'lesson_type': forms.Select(attrs={'class': 'form-input'}),
            'video_url': forms.URLInput(attrs={'class': 'form-input', 'placeholder': 'https://youtube.com/watch?v=...'}),
            'pdf_file': forms.ClearableFileInput(attrs={'class': 'form-input'}),
            'sop_text': forms.Textarea(attrs={'class': 'form-input', 'rows': 4, 'placeholder': 'Pasted text from the SOP manual (used for AI quizzes)'}),
            'duration_minutes': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
            'order': forms.NumberInput(attrs={'class': 'form-input', 'min': 1}),
        }

    def clean(self):
        cleaned = super().clean()
        lesson_type = cleaned.get('lesson_type')
        video_url = cleaned.get('video_url', '')
        pdf_file = cleaned.get('pdf_file')
        if lesson_type == 'video' and not video_url:
            self.add_error('video_url', _("A video URL is required for video lessons."))
        if lesson_type == 'pdf' and not pdf_file:
            self.add_error('pdf_file', _("A PDF file is required for SOP PDF lessons."))
        return cleaned


class EnrollForm(forms.Form):
    course = forms.ModelChoiceField(
        queryset=Course.objects.all().order_by('title'),
        label=_("Course"),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all().order_by('name'),
        label=_("Department"),
        required=False,
        empty_label=_("All departments (all active staff)"),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )

from django import forms
from django.utils.translation import gettext_lazy as _

from apps.users.models import StaffUser, Department
from apps.courses.models import Category, Course, Module, Lesson, Enrollment, TrainingSession


class CreateUserForm(forms.ModelForm):
    """Provisions an HR / HOD / staff account (super admin only)."""

    password = forms.CharField(
        label="Temporary password",
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'autocomplete': 'new-password'}),
        help_text=_("Temporary password. Leave blank to auto-generate a random one."),
    )

    class Meta:
        model = StaffUser
        fields = ['employee_id', 'first_name', 'last_name', 'email', 'department',
                  'designation', 'role']
        widgets = {
            'employee_id': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. HR001'}),
            'first_name': forms.TextInput(attrs={'class': 'form-input'}),
            'last_name': forms.TextInput(attrs={'class': 'form-input'}),
            'email': forms.EmailInput(attrs={'class': 'form-input'}),
            'department': forms.Select(attrs={'class': 'form-input'}),
            'designation': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. HR Manager'}),
            'role': forms.Select(attrs={'class': 'form-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['department'].empty_label = _("No department")
        self.fields['employee_id'].help_text = _("Uppercase letters/numbers only (e.g. HR001).")
        self.fields['employee_id'].widget.attrs['autofocus'] = True

    def clean_employee_id(self):
        employee_id = self.cleaned_data['employee_id'].strip().upper()
        if StaffUser.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(_("An account with this Employee ID already exists."))
        return employee_id

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip()
        if email and StaffUser.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("An account with this email already exists."))
        return email


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


class TrainingSessionForm(forms.ModelForm):
    class Meta:
        model = TrainingSession
        fields = ['title', 'description', 'course', 'date', 'start_time', 'end_time', 'location', 'is_mandatory']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Fire Drill Workshop'}),
            'description': forms.Textarea(attrs={'class': 'form-input', 'rows': 3}),
            'course': forms.Select(attrs={'class': 'form-input'}),
            'date': forms.DateInput(attrs={'class': 'form-input', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-input', 'type': 'time'}),
            'location': forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Training Hall, Block B'}),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'form-check'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['course'].empty_label = _("No linked course (optional)")

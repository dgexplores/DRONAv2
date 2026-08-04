from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _

from apps.users.models import Department, employee_id_validator

User = get_user_model()


class RegistrationForm(forms.Form):
    employee_id = forms.CharField(
        label=_("Employee ID"),
        max_length=50,
        validators=[employee_id_validator],
        widget=forms.TextInput(attrs={
            'class': 'form-input',
            'placeholder': 'e.g. EMP123',
            'autofocus': True,
        }),
    )
    first_name = forms.CharField(
        label=_("First Name"),
        max_length=150,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your first name'}),
    )
    last_name = forms.CharField(
        label=_("Last Name"),
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Your last name'}),
    )
    email = forms.EmailField(
        label=_("Email"),
        widget=forms.EmailInput(attrs={'class': 'form-input', 'placeholder': 'you@srms.edu.in'}),
    )
    department = forms.ModelChoiceField(
        label=_("Department"),
        queryset=Department.objects.all(),
        required=False,
        empty_label=_("Select department (optional)"),
        widget=forms.Select(attrs={'class': 'form-input'}),
    )
    designation = forms.CharField(
        label=_("Designation / Job Title"),
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'e.g. Lab Assistant'}),
    )
    phone_number = forms.CharField(
        label=_("Phone Number"),
        max_length=15,
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-input', 'placeholder': 'Optional'}),
    )
    password1 = forms.CharField(
        label=_("Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'At least 8 characters'}),
    )
    password2 = forms.CharField(
        label=_("Confirm Password"),
        widget=forms.PasswordInput(attrs={'class': 'form-input', 'placeholder': 'Repeat password'}),
    )

    def clean_employee_id(self):
        employee_id = self.cleaned_data['employee_id'].strip().upper()
        if User.objects.filter(employee_id=employee_id).exists():
            raise forms.ValidationError(_("This Employee ID is already registered."))
        return employee_id

    def clean(self):
        cleaned = super().clean()
        password1 = cleaned.get('password1')
        password2 = cleaned.get('password2')

        if password1 and len(password1) < 8:
            self.add_error('password1', _("Password must be at least 8 characters."))
        if password1 and password2 and password1 != password2:
            self.add_error('password2', _("Passwords do not match."))
        return cleaned

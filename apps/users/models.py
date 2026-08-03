from django.db import models
from django.contrib.auth.models import AbstractUser

class Department(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=20, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return f"{self.name} ({self.code})"

class StaffUser(AbstractUser):
    ROLE_CHOICES = (
        ('staff', 'Non-Teaching Staff'),
        ('trainer', 'Departmental Trainer / HOD'),
        ('admin', 'Super Admin'),
    )
    LANGUAGE_CHOICES = (
        ('en', 'English'),
        ('hi', 'Hindi'),
    )

    employee_id = models.CharField(max_length=50, unique=True, verbose_name="Employee ID")
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='staff_members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='staff')
    preferred_language = models.CharField(max_length=10, choices=LANGUAGE_CHOICES, default='en')
    phone_number = models.CharField(max_length=15, blank=True)
    designation = models.CharField(max_length=100, blank=True)

    USERNAME_FIELD = 'employee_id'
    REQUIRED_FIELDS = ['username', 'email', 'first_name', 'last_name']

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.employee_id}) - {self.get_role_display()}"

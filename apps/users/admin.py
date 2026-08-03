from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from apps.users.models import StaffUser, Department

class StaffUserAdmin(UserAdmin):
    model = StaffUser
    list_display = ('employee_id', 'get_full_name', 'department', 'role', 'is_active', 'is_staff')
    list_filter = ('role', 'department', 'is_active')
    search_fields = ('employee_id', 'first_name', 'last_name', 'email')
    ordering = ('employee_id',)

    fieldsets = (
        (None, {'fields': ('employee_id', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'email', 'phone_number', 'designation')}),
        ('Work Info', {'fields': ('department', 'role', 'preferred_language')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Important dates', {'fields': ('last_login', 'date_joined')}),
    )
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('employee_id', 'username', 'first_name', 'last_name', 'email', 'department', 'role', 'password1', 'password2'),
        }),
    )

class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')

admin.site.register(StaffUser, StaffUserAdmin)
admin.site.register(Department, DepartmentAdmin)

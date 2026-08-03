from django.contrib import admin
from apps.certificates.models import Certificate

class CertificateAdmin(admin.ModelAdmin):
    list_display = ('certificate_id', 'staff_user', 'course', 'issued_at')
    search_fields = ('certificate_id', 'staff_user__employee_id', 'course__title')
    list_filter = ('issued_at',)

admin.site.register(Certificate, CertificateAdmin)

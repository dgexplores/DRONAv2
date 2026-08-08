import os

from django.core.management.base import BaseCommand

from apps.users.models import StaffUser


class Command(BaseCommand):
    help = "Set/rotate the super-admin password from the DJANGO_ADMIN_PASSWORD env var."

    def handle(self, *args, **options):
        password = os.environ.get('DJANGO_ADMIN_PASSWORD', '')
        if not password:
            self.stderr.write("DJANGO_ADMIN_PASSWORD not set; nothing done.")
            return
        try:
            admin = StaffUser.objects.get(employee_id='ADMIN001')
        except StaffUser.DoesNotExist:
            self.stderr.write("ADMIN001 not found.")
            return
        admin.set_password(password)
        admin.save()
        self.stdout.write(self.style.SUCCESS("ADMIN001 password rotated."))

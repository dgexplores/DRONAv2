from django.core.management.base import BaseCommand
from apps.users.models import StaffUser


class Command(BaseCommand):
    help = "List user emails for verifying the reset-email/SMTP flow."

    def handle(self, *args, **options):
        for u in StaffUser.objects.all()[:50]:
            self.stdout.write(f"{u.employee_id}\t{u.email}\tactive={u.is_active}\trole={u.role}")
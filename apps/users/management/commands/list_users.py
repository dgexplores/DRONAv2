from django.core.management.base import BaseCommand
from apps.users.models import StaffUser


class Command(BaseCommand):
    help = "List users for verifying the reset-email/SMTP flow."

    def add_arguments(self, parser):
        parser.add_argument(
            '--include-email',
            action='store_true',
            help='Show full email addresses. Default masks them so logs stay PII-free.',
        )

    def handle(self, *args, **options):
        show_email = options['include_email']
        for u in StaffUser.objects.all()[:50]:
            email = u.email if show_email else _mask_email(u.email)
            self.stdout.write(f"{u.employee_id}\t{email}\tactive={u.is_active}\trole={u.role}")


def _mask_email(email):
    """Keep domain for SMTP debugging, mask the local part."""
    if '@' not in email:
        return '***'
    _, domain = email.rsplit('@', 1)
    return f"***@{domain}"
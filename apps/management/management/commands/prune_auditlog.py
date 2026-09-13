from django.core.management.base import BaseCommand

from apps.management.models import AuditLog


class Command(BaseCommand):
    help = "Delete AuditLog rows older than --days (default 180)."

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=180, help='Retention window in days.')

    def handle(self, *args, **options):
        deleted = AuditLog.prune(days=options['days'])
        self.stdout.write(self.style.SUCCESS(f"Pruned {deleted} audit rows older than {options['days']} days."))

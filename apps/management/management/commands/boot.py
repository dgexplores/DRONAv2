from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = (
        "Single-process Render boot: migrate + cache table + admin password. "
        "Replaces three separate manage.py invocations (three Django boots, "
        "~90s) with one process to cut free-plan cold-start time."
    )

    def handle(self, *args, **options):
        verbosity = options['verbosity']
        call_command('migrate', '--noinput', verbosity=verbosity)
        call_command('createcachetable', 'rate_limit_cache', verbosity=verbosity)
        call_command('set_admin_password')

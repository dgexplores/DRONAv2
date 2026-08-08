from django.core.management.base import BaseCommand

from apps.notifications.scheduler import start


class Command(BaseCommand):
    help = "Start the APScheduler email-reminder background scheduler."

    def handle(self, *args, **options):
        start()
        self.stdout.write(self.style.SUCCESS("SRMS Drona APScheduler started."))
        try:
            while True:
                import time
                time.sleep(60)
        except KeyboardInterrupt:
            self.stdout.write("Scheduler stopped.")

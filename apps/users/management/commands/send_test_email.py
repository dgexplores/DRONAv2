import os

from django.conf import settings
from django.core.mail import send_mail
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Send a test email through the configured SMTP to verify mail delivery (SET TEST_EMAIL_TO)."

    def handle(self, *args, **options):
        to = os.getenv('TEST_EMAIL_TO', '')
        if not to:
            self.stderr.write("Set TEST_EMAIL_TO env var to a recipient.")
            return
        try:
            count = send_mail(
                "SRMS Drona - SMTP connectivity test",
                "This confirms SMTP is working on the production server.",
                settings.DEFAULT_FROM_EMAIL,
                [to],
                fail_silently=False,
            )
            self.stdout.write(self.style.SUCCESS("Sent %d email(s)." % count))
        except Exception as e:
            self.stderr.write("SMTP failure: %s" % e)
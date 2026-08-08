from django.apps import AppConfig

class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.notifications'

    def ready(self):
        # Start the APScheduler email-reminder scheduler in-process.
        # Safe because production runs a single gunicorn worker (see railway.toml),
        # so exactly one scheduler instance sends reminder emails. Opt-in via
        # SRMS_RUN_SCHEDULER=1; no-ops otherwise (dev/test).
        from django.conf import settings
        if getattr(settings, 'SRMS_RUN_SCHEDULER', False):
            from apps.notifications.scheduler import start
            start()

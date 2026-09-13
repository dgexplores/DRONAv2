import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

scheduler = None

def start():
    """Start the APScheduler background scheduler. Safe to call multiple times.

    Opt-in via SRMS_RUN_SCHEDULER=1 so multi-worker production deployments
    (gunicorn) do not start a scheduler in every worker and double-send emails.
    """
    global scheduler
    from django.conf import settings
    if not getattr(settings, 'SRMS_RUN_SCHEDULER', False):
        logger.info("Scheduler disabled (set SRMS_RUN_SCHEDULER=1 to enable).")
        return
    if scheduler is not None:
        return
    scheduler = BackgroundScheduler(timezone=settings.TIME_ZONE)
    scheduler.add_job(
        send_reminders_job,
        trigger=IntervalTrigger(hours=settings.SRMS_REMINDER_INTERVAL_HOURS),
        id='send_pending_reminders',
        replace_existing=True,
    )
    scheduler.add_job(
        prune_auditlog_job,
        trigger=IntervalTrigger(days=1),
        id='prune_auditlog',
        replace_existing=True,
    )
    scheduler.start()
    logger.info("SRMS Drona APScheduler started.")

def send_reminders_job():
    """Send reminder emails to staff with incomplete mandatory training."""
    from django.core.mail import send_mail
    from django.conf import settings
    from django.db.models import Q
    from django.utils import timezone
    from datetime import timedelta
    from apps.courses.models import Enrollment

    interval_hours = getattr(settings, 'SRMS_REMINDER_INTERVAL_HOURS', 24)
    cutoff = timezone.now() - timedelta(hours=interval_hours)
    # Dedup: only enrollments never reminded or reminded before cutoff.
    # Only mandatory courses, oldest first, deterministic order. Caps 50/run.
    pending = (Enrollment.objects
               .filter(is_completed=False, course__is_mandatory=True, staff_user__is_active=True)
               .filter(Q(last_reminded_at__isnull=True) | Q(last_reminded_at__lt=cutoff))
               .select_related('staff_user', 'course')
               .filter(staff_user__email__isnull=False)
               .exclude(staff_user__email='')
               .order_by('last_reminded_at', 'enrolled_at', 'id')[:50])

    sent = 0
    for enrollment in pending:
        user = enrollment.staff_user
        course = enrollment.course
        progress = enrollment.progress_percent
        course_url = f"{settings.SRMS_BASE_URL}/courses/{course.id}/"

        subject = f"[SRMS Drona] Reminder: Complete {course.title}"
        message = (
            f"Dear {user.first_name},\n\n"
            f"This is a reminder that you have not yet completed the mandatory training:\n"
            f"  {course.title}\n"
            f"  Current progress: {progress}%\n\n"
            f"Please continue your learning here: {course_url}\n\n"
            f"Completing this course and passing the assessment earns your verified certificate.\n\n"
            f"Regards,\nSRMS Learning & HR Team"
        )
        try:
            send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
            Enrollment.objects.filter(pk=enrollment.pk).update(last_reminded_at=timezone.now())
            sent += 1
        except Exception as e:
            logger.error(f"Reminder email failed for {user.employee_id}: {e}")

    logger.info(f"Sent {sent} reminder emails.")


def prune_auditlog_job(days=180):
    """Daily retention prune for AuditLog. Best-effort, never raises."""
    try:
        from apps.management.models import AuditLog
        deleted = AuditLog.prune(days=days)
        logger.info(f"Pruned {deleted} audit rows older than {days} days.")
    except Exception as e:
        logger.error(f"Audit prune failed: {e}")

"""Shared side effects for the users app.

Two things every provisioning path needs:

* a post-commit hook, so background work never observes an uncommitted row; and
* a password-setup email, so a newly created account chooses its own password
  instead of an administrator handling a plaintext one.
"""
import logging
import threading

from django.conf import settings
from django.contrib.auth.forms import PasswordResetForm
from django.db import close_old_connections, transaction

logger = logging.getLogger(__name__)


def run_after_commit(func):
    """Run ``func`` on a daemon thread once the current transaction commits.

    Falls back to running immediately when there is no open transaction, and
    closes the DB connection at both ends so the worker thread never reuses the
    request's connection.
    """
    def _job():
        close_old_connections()
        try:
            func()
        except Exception:
            logger.exception("Post-commit background job failed")
        finally:
            close_old_connections()

    def _spawn():
        threading.Thread(target=_job, daemon=True).start()

    try:
        transaction.on_commit(_spawn)
    except Exception:
        _spawn()


def _base_url_parts():
    """Return (use_https, domain) derived from SRMS_BASE_URL."""
    base = (getattr(settings, 'SRMS_BASE_URL', '') or '').rstrip('/')
    if not base:
        return False, 'localhost:8000'
    return base.startswith('https://'), base.split('://', 1)[-1]


def send_password_setup_email(user):
    """Email an account a link to choose its own password.

    The account deliberately keeps a *usable* password: Django's
    ``PasswordResetForm.get_users()`` skips accounts without one, so switching
    to an unusable password here would silently stop the email from sending.
    The generated value is never displayed, logged, or returned.
    """
    if not user.email:
        logger.warning("No email on %s; cannot send password setup link.", user.employee_id)
        return

    form = PasswordResetForm({'email': user.email})
    if not form.is_valid():
        logger.warning("Password setup email skipped for %s: %s", user.employee_id, form.errors)
        return

    use_https, domain = _base_url_parts()
    form.save(
        domain_override=domain,
        use_https=use_https,
        from_email=settings.DEFAULT_FROM_EMAIL,
        subject_template_name='users/password_setup_subject.txt',
        email_template_name='users/password_setup_email.html',
    )


def send_password_setup_emails_async(user_ids):
    """Send setup links for ``user_ids`` in one background job.

    Batched into a single thread: provisioning a 500-row CSV must not spawn 500
    threads. Queued after commit so the rows are visible to the worker.
    """
    ids = list(user_ids)
    if not ids:
        return

    def _job():
        from apps.users.models import StaffUser
        for user in StaffUser.objects.filter(id__in=ids):
            try:
                send_password_setup_email(user)
            except Exception:
                logger.exception("Password setup email failed for %s", user.employee_id)

    run_after_commit(_job)

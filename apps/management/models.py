from django.db import models
from django.conf import settings


class AuditLog(models.Model):
    """Immutable ops trail: approvals, deletes, enrolls, imports, cert issuance."""

    ACTION_CHOICES = (
        ('approve_user', 'Approve user'),
        ('reject_user', 'Reject user'),
        ('create_user', 'Create user'),
        ('bulk_enroll', 'Bulk enroll'),
        ('assign_staff', 'Assign staff'),
        ('import_staff', 'Import staff'),
        ('course_create', 'Course create'),
        ('course_edit', 'Course edit'),
        ('course_delete', 'Course delete'),
        ('module_create', 'Module create'),
        ('module_edit', 'Module edit'),
        ('module_delete', 'Module delete'),
        ('lesson_create', 'Lesson create'),
        ('lesson_edit', 'Lesson edit'),
        ('lesson_delete', 'Lesson delete'),
        ('session_create', 'Session create'),
        ('session_edit', 'Session edit'),
        ('session_delete', 'Session delete'),
        ('certificate_issued', 'Certificate issued'),
    )

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_actions'
    )
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=100, blank=True)
    target_id = models.CharField(max_length=100, blank=True)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [models.Index(fields=['-created_at']), models.Index(fields=['action'])]

    @classmethod
    def prune(cls, days=180):
        """Delete rows older than `days`. Returns deleted count."""
        from django.utils import timezone
        from datetime import timedelta
        cutoff = timezone.now() - timedelta(days=max(1, int(days)))
        deleted, _ = cls.objects.filter(created_at__lt=cutoff).delete()
        return deleted

    def __str__(self):
        return f"{self.created_at:%Y-%m-%d %H:%M} {self.actor} {self.action} {self.target_type}:{self.target_id}"


def log_audit(actor, action, target=None, detail=""):
    """Best-effort audit write; never breaks the request on failure."""
    import logging
    logger = logging.getLogger(__name__)
    try:
        target_type = ""
        target_id = ""
        if target is not None:
            target_type = type(target).__name__
            for attr in ('employee_id', 'certificate_id', 'pk', 'id'):
                if hasattr(target, attr):
                    try:
                        target_id = str(getattr(target, attr))
                        break
                    except Exception:
                        continue
        AuditLog.objects.create(
            actor=actor if getattr(actor, 'pk', None) else None,
            action=action,
            target_type=target_type,
            target_id=target_id,
            detail=detail or "",
        )
    except Exception:
        logger.exception("Audit log write failed for %s", action)

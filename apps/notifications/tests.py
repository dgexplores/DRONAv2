from django.test import TestCase


class SchedulerDisabledWarningTests(TestCase):
    def test_disabled_scheduler_warns(self):
        """A disabled scheduler must not fail silently.

        Regression guard for ENGINEERING.md trap 4.12 / HANDOFF.md §3a:
        with SRMS_RUN_SCHEDULER unset, reminder emails are never generated
        and the only trace was an INFO line. The disabled path must log at
        WARNING so a misconfigured deploy is visible in the logs.
        """
        from django.test import override_settings
        from apps.notifications import scheduler
        with override_settings(SRMS_RUN_SCHEDULER=False):
            with self.assertLogs('apps.notifications.scheduler', level='WARNING') as captured:
                scheduler.start()
        self.assertTrue(
            any('SRMS_RUN_SCHEDULER' in line for line in captured.output),
            f"expected a scheduler-disabled warning, got: {captured.output}",
        )

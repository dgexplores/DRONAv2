from django.utils.translation import gettext_lazy as _
from django.db.models import Sum


def get_user_badges(user):
    """Return a list of badge dicts, each with `earned` True/False."""
    enrollments = user.enrollments.all()
    completed_count = enrollments.filter(is_completed=True).count()
    total_watch = user.enrollments.aggregate(total=Sum('watch_seconds'))['total'] or 0

    top_score = 0
    for attempt in user.quiz_attempts.filter(passed=True).order_by('-score')[:1]:
        top_score = attempt.score

    badges = [
        {
            'key': 'first_steps',
            'name': _("First Steps"),
            'icon': '👣',
            'description': _("Enrolled in your first course."),
            'earned': enrollments.exists(),
        },
        {
            'key': 'completer',
            'name': _("Course Completer"),
            'icon': '🏁',
            'description': _("Completed your first course."),
            'earned': completed_count >= 1,
        },
        {
            'key': 'certified',
            'name': _("Certified"),
            'icon': '🎓',
            'description': _("Earned a verified certificate."),
            'earned': user.certificates.exists(),
        },
        {
            'key': 'top_performer',
            'name': _("Top Performer"),
            'icon': '🏅',
            'description': _("Scored 90% or above in an assessment."),
            'earned': top_score >= 90,
        },
        {
            'key': 'course_master',
            'name': _("Course Master"),
            'icon': '🏆',
            'description': _("Completed 3 or more courses."),
            'earned': completed_count >= 3,
        },
        {
            'key': 'dedicated_learner',
            'name': _("Dedicated Learner"),
            'icon': '⏰',
            'description': _("Logged 3+ hours of active learning."),
            'earned': total_watch >= 3 * 3600,
        },
    ]
    return badges

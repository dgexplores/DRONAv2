import os

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import render
from django.views.static import serve as static_serve


def handler404(request, exception=None):
    return render(request, 'errors/404.html', status=404)


def handler500(request):
    return render(request, 'errors/500.html', status=500)


def handler403(request, exception=None):
    return render(request, 'errors/403.html', status=403)


def handler400(request, exception=None):
    return render(request, 'errors/400.html', status=400)


def _is_manager(user):
    return bool(getattr(user, 'is_manager', False))


@login_required
def protected_media(request, path):
    """Serve ``/media/`` in production with per-file authorisation.

    A blanket ``login_required`` is not sufficient here: it still lets any
    authenticated staff member fetch another staff member's certificate PDF,
    or the SOP for a course they are not enrolled in, simply by guessing the
    filename. Certificate IDs are short and are printed on the PDF and encoded
    in the verification QR code, so they are not a secret.

    Unlisted directories keep the previous login-only behaviour.
    """
    normalised = os.path.normpath(path).replace('\\', '/')
    # Reject traversal before any lookup. static_serve also guards this, but a
    # 404 here keeps the failure mode consistent and cheap.
    if normalised.startswith('..') or os.path.isabs(normalised):
        raise Http404("Invalid media path.")

    if normalised.startswith('certificates/'):
        from apps.certificates.models import Certificate
        authorised = _is_manager(request.user) or Certificate.objects.filter(
            pdf_file=normalised, staff_user=request.user
        ).exists()
        if not authorised:
            raise Http404("Not found.")

    elif normalised.startswith('sop_documents/'):
        from apps.courses.models import Enrollment, Lesson
        lesson = Lesson.objects.filter(pdf_file=normalised).first()
        if lesson is None:
            raise Http404("Not found.")
        if not _is_manager(request.user) and not Enrollment.objects.filter(
            staff_user=request.user, course=lesson.module.course
        ).exists():
            raise Http404("Not found.")

    return static_serve(request, normalised, document_root=settings.MEDIA_ROOT)

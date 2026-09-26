from django.contrib import admin
from django.urls import path, include, reverse_lazy
from django.conf import settings
from django.conf.urls.static import static
from django.http import HttpResponse
from django.contrib.auth import views as auth_views

from apps.users import views as user_views
from apps.courses import views as course_views
from apps.quizzes import views as quiz_views
from apps.certificates import views as cert_views
from apps.analytics import views as analytics_views

# Custom error handlers
handler400 = 'srms_dorna.views.handler400'
handler403 = 'srms_dorna.views.handler403'
handler404 = 'srms_dorna.views.handler404'
handler500 = 'srms_dorna.views.handler500'


def favicon_view(request):
    """Serve the app icon at /favicon.ico from the collected static files."""
    from django.contrib.staticfiles.storage import staticfiles_storage
    try:
        with staticfiles_storage.open('img/favicon.ico') as fh:
            return HttpResponse(fh.read(), content_type='image/x-icon')
    except (OSError, ValueError):
        return HttpResponse(status=204)

urlpatterns = [
    # Healthcheck (used by Railway + CI)
    path('health/', lambda request: HttpResponse('ok', content_type='text/plain'), name='health'),

    # Browsers request /favicon.ico at the site root regardless of any <link>
    # tag, and the standalone auth + error templates carry no layout, so serve
    # it from a real route instead of leaving every page with a 404.
    path('favicon.ico', favicon_view, name='favicon'),

    # Admin
    path('admin/', admin.site.urls),

    # Auth & Users
    path('login/', user_views.login_view, name='login'),
    path('register/', user_views.register_view, name='register'),
    path('logout/', user_views.logout_view, name='logout'),
    path('profile/', user_views.profile_view, name='profile'),
    path('users/<int:user_id>/approve/', user_views.approve_user, name='approve_user'),
    path('users/<int:user_id>/reject/', user_views.reject_user, name='reject_user'),
    path('language/toggle/', user_views.toggle_language, name='toggle_language'),

    # Password Reset
    path('password-reset/', user_views.RateLimitedPasswordResetView.as_view(
        template_name='users/password_reset_form.html',
        email_template_name='users/password_reset_email.html',
        subject_template_name='users/password_reset_subject.txt',
        success_url=reverse_lazy('password_reset_done'),
    ), name='password_reset'),
    path('password-reset/done/', auth_views.PasswordResetDoneView.as_view(
        template_name='users/password_reset_done.html',
    ), name='password_reset_done'),
    path('reset/<uidb64>/<token>/', user_views.RateLimitedPasswordResetConfirmView.as_view(
        template_name='users/password_reset_confirm.html',
        success_url=reverse_lazy('password_reset_complete'),
    ), name='password_reset_confirm'),
    path('reset/done/', auth_views.PasswordResetCompleteView.as_view(
        template_name='users/password_reset_complete.html',
    ), name='password_reset_complete'),

    # Courses & PWA Dashboard
    path('', course_views.dashboard_view, name='dashboard'),
    path('courses/<int:course_id>/', course_views.course_detail_view, name='course_detail'),
    path('courses/<int:course_id>/enroll/', course_views.enroll_course, name='enroll_course'),
    path('lessons/<int:lesson_id>/', course_views.lesson_view, name='lesson_view'),
    path('lessons/<int:lesson_id>/progress/', course_views.save_lesson_progress, name='save_lesson_progress'),
    path('sop/<int:lesson_id>/', course_views.sop_document_view, name='sop_document'),
    path('training-calendar/', course_views.training_calendar, name='training_calendar'),

    # Quizzes & AI Generator
    path('quizzes/course/<int:course_id>/', quiz_views.take_quiz_view, name='take_quiz'),
    path('quizzes/<int:quiz_id>/submit/', quiz_views.submit_quiz_view, name='submit_quiz'),
    path('quizzes/ai-generate/', quiz_views.generate_ai_quiz, name='generate_ai_quiz'),

    # Certificates & QR Verification
    path('certificates/', cert_views.my_certificates_view, name='my_certificates'),
    path('certificates/<str:cert_id>/download/', cert_views.download_certificate_pdf, name='download_certificate'),
    path('verify/<str:cert_id>/', cert_views.verify_certificate_view, name='verify_certificate'),

    # Analytics & HR Dashboard
    path('analytics/', analytics_views.hr_dashboard_view, name='hr_dashboard'),
    path('analytics/export/csv/', analytics_views.export_staff_report_csv, name='export_staff_csv'),

    # Management Console (admin/trainer)
    path('manage/', include('apps.management.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Serve uploaded media in production. protected_media authorises each file:
    # certificate PDFs require ownership, SOP documents require enrollment.
    # Long-term: object storage + signed URLs.
    from srms_dorna.views import protected_media
    urlpatterns += [
        path(f'{settings.MEDIA_URL.lstrip("/")}<path:path>', protected_media),
    ]

import secrets
from django.http import HttpResponse


class SecurityHeadersMiddleware:
    """Adds modern security headers not covered by Django's SecurityMiddleware.

    Per-request CSP nonce for inline scripts. Templates must use
    nonce="{{ request.csp_nonce }}" on inline <script> tags.
    External app.js remains nonce-free via 'self'.
    """

    CSP_BASE = (
        "default-src 'self'; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' https://www.gstatic.com; "
        "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
        "media-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'none'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        nonce = secrets.token_urlsafe(16)
        request.csp_nonce = nonce
        response = self.get_response(request)
        if isinstance(response, HttpResponse):
            csp = (
                "default-src 'self'; "
                f"script-src 'self' 'nonce-{nonce}' https://cdn.jsdelivr.net https://www.gstatic.com; "
                "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
                "font-src 'self' https://fonts.gstatic.com; "
                "img-src 'self' data: blob:; "
                "connect-src 'self' https://www.gstatic.com; "
                "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
                "media-src 'self'; "
                "object-src 'none'; "
                "base-uri 'self'; "
                "form-action 'self'; "
                "frame-ancestors 'none'"
            )
            response.headers.setdefault('Content-Security-Policy', csp)
            response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
            response.headers.setdefault(
                'Permissions-Policy',
                'camera=(), microphone=(), geolocation=(), payment=()',
            )
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('X-Frame-Options', 'DENY')
        return response

class UserLanguageMiddleware:
    """Resolve the active language from the session, then the saved preference.

    Two gaps this closes:

    1. Django's `LocaleMiddleware` reads only the `django_language` *cookie* and
       `Accept-Language` -- `get_language_from_request` no longer looks at
       `request.session['django_language']`, which is exactly what
       `toggle_language` writes. So the toggle set the session, the context
       processor reported Hindi via `html lang`, and every `{% trans %}` still
       rendered English.

    2. The pre-`{% trans %}` templates used an `is_hindi` context variable, and
       `language_context` fell back to `StaffUser.preferred_language` when the
       session was empty. That fallback has to live somewhere now, or a user
       whose preference is Hindi gets English chrome on a fresh session.

    Priority: session (an explicit choice) > saved user preference > whatever
    `LocaleMiddleware` already negotiated. Must sit after `AuthenticationMiddleware`
    so `request.user` is populated.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        from django.conf import settings
        from django.utils import translation

        supported = dict(settings.LANGUAGES)
        chosen = request.session.get('django_language')
        if chosen not in supported:
            chosen = getattr(getattr(request, 'user', None), 'preferred_language', None)
        if chosen in supported:
            translation.activate(chosen)
        return self.get_response(request)

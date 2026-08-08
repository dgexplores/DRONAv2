from django.http import HttpResponse


class SecurityHeadersMiddleware:
    """Adds modern security headers not covered by Django's SecurityMiddleware.

    Applied as a thin header layer so no extra dependency (e.g. django-csp)
    is required. Keep CSP permissive enough for inline scripts/styles used by
    the current templates that rely on them.
    """

    # style 'unsafe-inline' + script nonce-free 'unsafe-inline' needed because the
    # app renders inline <script>/<style> blocks directly in Django templates.
    CSP = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://www.gstatic.com; "
        "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
        "font-src 'self' https://fonts.gstatic.com; "
        "img-src 'self' data: blob:; "
        "connect-src 'self' https://www.gstatic.com; "
        "frame-src 'self' https://www.youtube.com https://www.youtube-nocookie.com; "
        "media-src 'self'; "
        "object-src 'none'; "
        "base-uri 'self'; "
        "form-action 'self'; "
        "frame-ancestors 'self'"
    )

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if isinstance(response, HttpResponse):
            response.headers.setdefault('Content-Security-Policy', self.CSP)
            response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
            response.headers.setdefault(
                'Permissions-Policy',
                'camera=(), microphone=(), geolocation=(), payment=()',
            )
            response.headers.setdefault('X-Content-Type-Options', 'nosniff')
            response.headers.setdefault('X-Frame-Options', 'DENY')
        return response
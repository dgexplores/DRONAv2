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
        "frame-ancestors 'self'"
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
                "frame-ancestors 'self'"
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
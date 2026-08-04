"""Clerk SSO authentication backend.

Verifies a Clerk session token (JWT) against Clerk's secret key, maps the
verified Clerk identity to a StaffUser by email, and auto-provisions a
StaffUser account on first sign-in.

Disabled (no-op) when CLERK_SECRET_KEY is not configured, so the app keeps
working with internal employee_id/password auth.
"""
from django.conf import settings
from django.contrib.auth.backends import BaseBackend
from django.core.exceptions import ObjectDoesNotExist

from apps.users.models import StaffUser

try:
    from clerk_backend_api.security.verifytoken import (
        TokenVerificationError,
        verify_token,
        VerifyTokenOptions,
    )
except Exception:  # pragma: no cover - package may be absent on prod build
    verify_token = None
    TokenVerificationError = Exception
    VerifyTokenOptions = None


def clerk_enabled():
    return bool(getattr(settings, 'CLERK_SECRET_KEY', ''))


class ClerkAuthenticationBackend(BaseBackend):
    def authenticate(self, request, clerk_token=None, **kwargs):
        if not clerk_token or not clerk_enabled() or verify_token is None:
            return None

        options = VerifyTokenOptions(
            secret_key=settings.CLERK_SECRET_KEY,
            audience=settings.CLERK_JWT_AUDIENCE or None,
        )
        try:
            payload = verify_token(clerk_token, options)
        except TokenVerificationError:
            return None

        email = (payload.get('email') or '').strip().lower()
        if not email:
            return None

        user = self._get_or_create_user(email, payload)
        return user if user and user.is_active else None

    def _get_or_create_user(self, email, payload):
        user = StaffUser.objects.filter(email__iexact=email).first()
        if user:
            return user

        first = (payload.get('first_name') or '').strip()
        last = (payload.get('last_name') or '').strip()
        username = (payload.get('employee_id') or self._derive_username(email, first, last))

        user = StaffUser(
            username=username,
            employee_id=username,
            email=email,
            first_name=first,
            last_name=last,
            role='staff',
            is_active=True,
        )
        user.set_unusable_password()
        user.save()
        return user

    @staticmethod
    def _derive_username(email, first, last):
        base = (first or last or email.split('@')[0]).upper().replace(' ', '')
        base = ''.join(ch for ch in base if ch.isalnum())[:20] or 'USER'
        candidate = base
        n = 1
        while StaffUser.objects.filter(employee_id__iexact=candidate).exists():
            suffix = str(n)
            candidate = base[:20 - len(suffix)] + suffix
            n += 1
        return candidate

    def get_user(self, user_id):
        try:
            return StaffUser.objects.get(pk=user_id)
        except ObjectDoesNotExist:
            return None

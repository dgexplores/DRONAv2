from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import threading

from django.core.mail import send_mail
from django.contrib.auth.views import PasswordResetView, PasswordResetConfirmView
from django.contrib.auth.mixins import UserPassesTestMixin
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Sum
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from django.utils.translation import gettext_lazy as _

import logging
logger = logging.getLogger(__name__)

from apps.users.models import StaffUser, Department
from apps.users.forms import RegistrationForm
from apps.users.badges import get_user_badges

LOGIN_MAX_RATE = '5/5m'  # max 5 attempts per IP per 5 minutes
REGISTER_MAX_RATE = '3/1h'  # max 3 self-signups per IP per hour (anti-spam)
RESET_MAX_RATE = '3/1h'  # max 3 password-reset requests per IP per hour


def get_client_ip(group, request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _send_approval_email(user, approved):
    """Notify a staff member that their registration was approved or rejected."""
    if not user.email:
        return
    base = settings.SRMS_BASE_URL.rstrip('/')
    if approved:
        subject = "Your SRMS Drona account is active"
        message = (
            f"Dear {user.first_name or user.employee_id},\n\n"
            "Your SRMS Drona account has been approved by an administrator.\n"
            "You can now sign in and start your training.\n\n"
            f"Sign in here: {base}/login/\n"
            "Forgot your password? Use the 'Forgot password?' link on the login page.\n\n"
            "Regards,\nSRMS Learning & HR Team"
        )
    else:
        subject = "Your SRMS Drona registration"
        message = (
            f"Dear {user.first_name or user.employee_id},\n\n"
            "Your SRMS Drona registration request has not been approved.\n"
            "If you believe this is an error, please contact the SRMS HR / admin team.\n\n"
            "Regards,\nSRMS Learning & HR Team"
        )
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [user.email])
    except Exception:
        logger.exception("Approval email failed for %s", user.employee_id)


def _send_approval_email_async(user_id, approved):
    """Fire-and-forget approval email so the admin request never blocks on SMTP."""
    def _job():
        try:
            from apps.users.models import StaffUser
            user = StaffUser.objects.get(id=user_id)
        except StaffUser.DoesNotExist:
            return
        _send_approval_email(user, approved)

    t = threading.Thread(target=_job, daemon=True)
    t.start()


@ratelimit(key=get_client_ip, rate=LOGIN_MAX_RATE, method='POST', block=False)
def login_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if getattr(request, 'limited', False):
        messages.error(
            request,
            _("Too many failed login attempts. Please wait a few minutes and try again."),
        )
        return render(request, 'users/login.html', status=429)

    context = {
        'clerk_publishable_key': settings.CLERK_PUBLISHABLE_KEY,
        'clerk_enabled': bool(settings.CLERK_PUBLISHABLE_KEY),
    }

    if request.method == 'POST':
        employee_id = request.POST.get('employee_id', '').strip()
        password = request.POST.get('password', '').strip()

        user = None
        try:
            candidate = StaffUser.objects.get(employee_id=employee_id)
        except StaffUser.DoesNotExist:
            candidate = None

        if candidate is not None and candidate.check_password(password):
            if candidate.is_active:
                candidate.backend = 'django.contrib.auth.backends.ModelBackend'
                login(request, candidate)
                messages.success(request, f"Welcome back, {candidate.first_name or candidate.employee_id}!")
                next_url = request.POST.get('next') or request.GET.get('next') or ''
                if next_url.startswith('/') and not next_url.startswith('//'):
                    return redirect(next_url)
                return redirect('dashboard')
        messages.error(request, _("Invalid Employee ID or Password. Please try again."))

    return render(request, 'users/login.html', context)

@ratelimit(key=get_client_ip, rate=REGISTER_MAX_RATE, method='POST', block=False)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

    if getattr(request, 'limited', False):
        messages.error(request, _("Too many sign-up attempts. Please try again later."))
        return render(request, 'users/register.html', {'form': RegistrationForm(request.POST)}, status=429)

    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            user = StaffUser.objects.create_user(
                username=data['employee_id'],
                employee_id=data['employee_id'],
                first_name=data['first_name'],
                last_name=data['last_name'] or '',
                email=data['email'],
                department=data.get('department'),
                designation=data.get('designation', ''),
                phone_number=data.get('phone_number', ''),
                role='staff',
                is_active=False,
                password=data['password1'],
            )
            messages.success(
                request,
                _("Account created successfully. An admin must approve your account before you can sign in."),
            )
            return redirect('login')
    else:
        form = RegistrationForm()

    return render(request, 'users/register.html', {'form': form})

@login_required
def approve_user(request, user_id):
    if request.user.role not in ('admin', 'trainer') and not request.user.is_superuser:
        return HttpResponse(_("Unauthorized"), status=403)

    target = get_object_or_404(StaffUser, id=user_id)
    if target.role == 'admin':
        messages.error(request, _("Admin accounts cannot be approved via self-signup."))
        return redirect('hr_dashboard')

    target.is_active = True
    target.save()
    messages.success(request, f"{target.get_full_name() or target.employee_id} approved and can now sign in.")
    _send_approval_email_async(target.pk, approved=True)
    return redirect('hr_dashboard')

@login_required
def reject_user(request, user_id):
    if request.user.role not in ('admin', 'trainer') and not request.user.is_superuser:
        return HttpResponse(_("Unauthorized"), status=403)

    target = get_object_or_404(StaffUser, id=user_id)
    name = target.get_full_name() or target.employee_id
    if target.is_active:
        messages.error(request, _("Only pending (inactive) accounts can be rejected."))
        return redirect('hr_dashboard')

    _send_approval_email_async(target.pk, approved=False)
    target.delete()
    messages.warning(request, f"Registration request for {name} rejected and removed.")
    return redirect('hr_dashboard')

@method_decorator(ratelimit(key=get_client_ip, rate=RESET_MAX_RATE, method='POST', block=False), name='dispatch')
class RateLimitedPasswordResetView(PasswordResetView):
    """Password reset form with per-IP rate limiting (anti email-bombing)."""

    def form_valid(self, form):
        if getattr(self.request, 'limited', False):
            messages.error(
                self.request,
                _("Too many password reset requests. Please wait and try again later."),
            )
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


@method_decorator(ratelimit(key=get_client_ip, rate=RESET_MAX_RATE, method='POST', block=False), name='dispatch')
class RateLimitedPasswordResetConfirmView(PasswordResetConfirmView):
    """Password reset token confirmation with per-IP rate limiting."""

    def form_valid(self, form):
        if getattr(self.request, 'limited', False):
            messages.error(
                self.request,
                _("Too many reset attempts. Please wait and try again later."),
            )
            return self.render_to_response(self.get_context_data(form=form))
        return super().form_valid(form)


def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('login')

@login_required
def profile_view(request):
    staff_user = request.user
    is_manager = staff_user.role in ('admin', 'trainer') or staff_user.is_superuser or staff_user.is_staff

    if is_manager:
        return _manager_profile(request)

    certificates = staff_user.certificates.select_related('course').all()
    enrollments = staff_user.enrollments.select_related('course').all()
    total_watch = staff_user.enrollments.aggregate(total=Sum('watch_seconds'))['total'] or 0
    badges = get_user_badges(staff_user)

    context = {
        'staff_user': staff_user,
        'certificates': certificates,
        'enrollments': enrollments,
        'badges': badges,
        'learning_hours': total_watch / 3600,
    }
    return render(request, 'users/profile.html', context)


def _manager_profile(request):
    """Role-aware profile for super-admin and HOD/trainer accounts.

    Shows account details plus a scoped management overview instead of the
    learner badge/enrollment trackers.
    """
    staff_user = request.user
    is_super = staff_user.is_superuser or staff_user.role == 'admin'
    dept = staff_user.department

    from apps.users.models import StaffUser as SU
    from apps.courses.models import Enrollment, Course
    from apps.certificates.models import Certificate

    def staff_qs():
        qs = SU.objects.filter(is_active=True)
        return qs if is_super or not dept else qs.filter(department=dept)

    def enrollment_qs():
        qs = Enrollment.objects.all()
        return qs if is_super or not dept else qs.filter(staff_user__department=dept)

    scope_label = "all departments" if is_super else (dept.name if dept else "department")
    context = {
        'staff_user': staff_user,
        'is_manager': True,
        'is_super': is_super,
        'scope_label': scope_label,
        'active_staff': staff_qs().count(),
        'completed_count': enrollment_qs().filter(is_completed=True).count(),
        'enrollment_count': Course.objects.filter(enrollments__in=enrollment_qs()).distinct().count(),
        'cert_count': (Certificate.objects.count()
                       if is_super else Certificate.objects.filter(staff_user__department=dept).count()),
    }
    return render(request, 'users/profile.html', context)

def toggle_language(request):
    new_lang = request.GET.get('lang', 'en')
    if new_lang in ['en', 'hi']:
        request.session['django_language'] = new_lang
        if request.user.is_authenticated:
            request.user.preferred_language = new_lang
            request.user.save()
    next_url = request.META.get('HTTP_REFERER', 'dashboard')
    return redirect(next_url)

def clerk_login_view(request):
    """Exchange a verified Clerk session token for a Django session.

    The Clerk frontend signs the user in, obtains a session JWT, and POSTs it
    here. The token is verified against Clerk's secret key and mapped to a
    StaffUser (auto-provisioned on first sign-in).
    """
    from django.contrib.auth import authenticate

    if request.user.is_authenticated:
        return redirect('dashboard')

    if request.method != 'POST':
        return redirect('login')

    token = request.POST.get('token', '').strip()
    if not token:
        messages.error(request, _("Missing Clerk session token."))
        return redirect('login')

    user = authenticate(request, clerk_token=token)
    if user is not None:
        login(request, user)
        messages.success(request, f"Welcome back, {user.first_name or user.employee_id}!")
        return redirect('dashboard')

    messages.error(request, _("Unable to sign in with the provided session. Please try again."))
    return redirect('login')

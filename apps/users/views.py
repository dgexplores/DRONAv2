from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponse
from django.conf import settings
from django.db.models import Sum
from django_ratelimit.decorators import ratelimit
from django.utils.translation import gettext_lazy as _
from apps.users.models import StaffUser, Department
from apps.users.forms import RegistrationForm
from apps.users.badges import get_user_badges

LOGIN_MAX_RATE = '5/5m'  # max 5 attempts per IP per 5 minutes


def get_client_ip(group, request):
    xff = request.META.get('HTTP_X_FORWARDED_FOR', '')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


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
                return redirect('dashboard')
        messages.error(request, _("Invalid Employee ID or Password. Please try again."))

    context = {
        'clerk_publishable_key': settings.CLERK_PUBLISHABLE_KEY,
        'clerk_enabled': bool(settings.CLERK_PUBLISHABLE_KEY),
    }
    return render(request, 'users/login.html', context)

@ratelimit(key=get_client_ip, rate=LOGIN_MAX_RATE, method='POST', block=False)
def register_view(request):
    if request.user.is_authenticated:
        return redirect('dashboard')

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
    if request.user.role != 'admin' and not request.user.is_superuser:
        return HttpResponse(_("Unauthorized"), status=403)

    target = get_object_or_404(StaffUser, id=user_id)
    if target.role == 'admin':
        messages.error(request, _("Admin accounts cannot be approved via self-signup."))
        return redirect('hr_dashboard')

    target.is_active = True
    target.save()
    messages.success(request, f"{target.get_full_name() or target.employee_id} approved and can now sign in.")
    return redirect('hr_dashboard')

@login_required
def reject_user(request, user_id):
    if request.user.role != 'admin' and not request.user.is_superuser:
        return HttpResponse(_("Unauthorized"), status=403)

    target = get_object_or_404(StaffUser, id=user_id)
    name = target.get_full_name() or target.employee_id
    if target.is_active:
        messages.error(request, _("Only pending (inactive) accounts can be rejected."))
        return redirect('hr_dashboard')

    target.delete()
    messages.warning(request, f"Registration request for {name} rejected and removed.")
    return redirect('hr_dashboard')

def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('login')

@login_required
def profile_view(request):
    staff_user = request.user
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

@login_required
def toggle_language(request):
    new_lang = request.GET.get('lang', 'en')
    if new_lang in ['en', 'hi']:
        request.user.preferred_language = new_lang
        request.user.save()
        request.session['django_language'] = new_lang
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

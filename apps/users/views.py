from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django_ratelimit.decorators import ratelimit
from django.utils.translation import gettext_lazy as _
from apps.users.models import StaffUser, Department

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

        user = authenticate(request, username=employee_id, password=password)
        if user is not None:
            login(request, user)
            messages.success(request, f"Welcome back, {user.first_name or user.employee_id}!")
            return redirect('dashboard')
        else:
            messages.error(request, _("Invalid Employee ID or Password. Please try again."))

    return render(request, 'users/login.html')

def logout_view(request):
    logout(request)
    messages.info(request, "Logged out successfully.")
    return redirect('login')

@login_required
def profile_view(request):
    staff_user = request.user
    certificates = staff_user.certificates.select_related('course').all()
    enrollments = staff_user.enrollments.select_related('course').all()
    
    context = {
        'staff_user': staff_user,
        'certificates': certificates,
        'enrollments': enrollments,
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

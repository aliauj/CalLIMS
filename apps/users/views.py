from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect
from django.utils import timezone


def login_view(request):
    if request.user.is_authenticated:
        return redirect('workflows:dashboard')
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '')
        user = authenticate(request, username=email, password=password)
        if user is not None:
            if user.is_account_locked():
                messages.error(request, 'Account is temporarily locked. Please try again later.')
            else:
                user.failed_login_attempts = 0
                user.last_login_ip = request.META.get('REMOTE_ADDR')
                user.save(update_fields=['failed_login_attempts', 'last_login_ip'])
                login(request, user)
                return redirect(request.GET.get('next', 'workflows:dashboard'))
        else:
            from apps.users.models import User
            try:
                u = User.objects.get(email=email)
                u.failed_login_attempts += 1
                if u.failed_login_attempts >= 5:
                    u.locked_until = timezone.now() + timezone.timedelta(minutes=15)
                    messages.error(request, 'Too many failed attempts. Account locked for 15 minutes.')
                else:
                    messages.error(request, 'Invalid email or password.')
                u.save(update_fields=['failed_login_attempts', 'locked_until'])
            except User.DoesNotExist:
                messages.error(request, 'Invalid email or password.')
    return render(request, 'users/login.html')


def logout_view(request):
    logout(request)
    return redirect('users:login')


@login_required
def profile_view(request):
    return render(request, 'users/profile.html', {'user_obj': request.user})

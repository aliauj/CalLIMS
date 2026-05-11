from functools import wraps
from django.shortcuts import redirect
from django.contrib import messages


def admin_required(view_func):
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('users:login')
        if request.user.role not in ('ADMIN', 'MANAGER'):
            messages.error(request, 'Access denied. Admin or Manager role required.')
            return redirect('workflows:dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper

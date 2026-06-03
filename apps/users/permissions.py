"""
Lightweight permission helper.
ADMIN bypasses everything. Others check UserModulePermission first,
then fall back to role-based defaults.
"""
from .models import AppSection

# Default allowed actions per role per section
_DEFAULTS = {
    'ADMIN': {s: ('view','add','modify','delete') for s in AppSection.values},
    'MANAGER': {
        'instruments':  ('view','add','modify'),
        'jobs':         ('view','add','modify'),
        'results':      ('view','add','modify'),
        'certificates': ('view','add','modify'),
        'standards':    ('view','add','modify'),
        'clients':      ('view','add','modify'),
        'users':        ('view',),
        'audit':        ('view',),
        'proficiency':  ('view','add','modify'),
        'nc':           ('view','add','modify'),
        'admin_panel':  ('view',),
    },
    'TECHNICIAN': {
        'instruments':  ('view',),
        'jobs':         ('view','modify'),
        'results':      ('view','add','modify'),
        'certificates': ('view',),
        'standards':    ('view',),
        'clients':      (),
        'users':        (),
        'audit':        (),
        'proficiency':  ('view',),
        'nc':           ('view','add'),
        'admin_panel':  (),
    },
    'REVIEWER': {
        'instruments':  ('view',),
        'jobs':         ('view',),
        'results':      ('view',),
        'certificates': ('view','add','modify'),
        'standards':    ('view',),
        'clients':      ('view',),
        'users':        (),
        'audit':        ('view',),
        'proficiency':  ('view',),
        'nc':           ('view','add','modify'),
        'admin_panel':  (),
    },
    'AUDITOR': {
        'instruments':  ('view',),
        'jobs':         ('view',),
        'results':      ('view',),
        'certificates': ('view',),
        'standards':    ('view',),
        'clients':      (),
        'users':        (),
        'audit':        ('view',),
        'proficiency':  ('view',),
        'nc':           ('view',),
        'admin_panel':  (),
    },
    'CLIENT': {
        'instruments':  ('view',),
        'certificates': ('view',),
        'jobs': (), 'results': (), 'standards': (), 'clients': (),
        'users': (), 'audit': (), 'proficiency': (), 'nc': (), 'admin_panel': (),
    },
}


def check_perm(user, section, action='view'):
    if not user or not user.is_authenticated:
        return False
    if user.role == 'ADMIN':
        return True
    from .models import UserModulePermission
    perm = UserModulePermission.objects.filter(user=user, section=section).first()
    if perm is not None:
        return getattr(perm, f'can_{action}', False)
    return action in _DEFAULTS.get(user.role, {}).get(section, ())


def require_perm(section, action='view'):
    from functools import wraps
    from django.contrib import messages
    from django.shortcuts import redirect
    def decorator(fn):
        @wraps(fn)
        def wrapper(request, *args, **kwargs):
            if not check_perm(request.user, section, action):
                messages.error(request, 'You do not have permission to perform this action.')
                return redirect('workflows:dashboard')
            return fn(request, *args, **kwargs)
        return wrapper
    return decorator


def lab_staff_required(view_func):
    """Block CLIENT users from lab-internal views.

    CLIENT users are redirected to the portal dashboard so they land somewhere
    useful instead of staring at a 403; non-lab custom roles get an explicit
    403 since they have no portal of their own.
    """
    from functools import wraps
    from django.http import HttpResponseForbidden
    from django.shortcuts import redirect

    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user = request.user
        if not user.is_authenticated:
            return redirect('users:login')
        if user.is_client:
            return redirect('portal:dashboard')
        if not user.is_lab_staff:
            return HttpResponseForbidden('Access restricted to lab staff.')
        return view_func(request, *args, **kwargs)

    return wrapper

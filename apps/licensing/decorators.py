from functools import wraps
from django.shortcuts import render


def module_required(module_name):
    """Blocks a view if the named module is not enabled in the current license."""
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(request, *args, **kwargs):
            try:
                from .models import LicenseRecord
                license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
                if license and not license.is_module_enabled(module_name):
                    from .services import MODULE_LABELS
                    return render(request, 'licensing/module_disabled.html', {
                        'module_name': module_name,
                        'module_label': MODULE_LABELS.get(module_name, module_name),
                        'license': license,
                    }, status=403)
            except Exception:
                pass
            return view_func(request, *args, **kwargs)
        return wrapper
    return decorator

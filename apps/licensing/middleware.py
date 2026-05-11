from django.shortcuts import redirect
from django.urls import reverse, NoReverseMatch

# Paths that always pass through, regardless of license state
_EXEMPT = (
    '/auth/',
    '/license/',
    '/static/',
    '/media/',
    '/admin/',
    '/notifications/api/',  # JSON polling — must not be redirected to HTML
)


class LicenseMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        path = request.path_info

        # Always let exempt paths through
        if any(path.startswith(p) for p in _EXEMPT):
            return self.get_response(request)

        # Only enforce for authenticated users
        if not getattr(request, 'user', None) or not request.user.is_authenticated:
            return self.get_response(request)

        try:
            from .models import LicenseRecord
            license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
            if not license or not license.is_valid:
                expired_url = reverse('licensing:expired')
                if path != expired_url:
                    return redirect(expired_url)
        except Exception:
            # If the licensing table doesn't exist yet (first migration), pass through
            pass

        return self.get_response(request)

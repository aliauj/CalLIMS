from django.utils import timezone
from config.version import VERSION, VENDOR_NAME, VENDOR_URL, PRODUCT_NAME


def licensing(request):
    ctx = {
        'callims_version': VERSION,
        'callims_vendor': VENDOR_NAME,
        'callims_vendor_url': VENDOR_URL,
        'callims_product': PRODUCT_NAME,
    }
    if not getattr(request, 'user', None) or not request.user.is_authenticated:
        return ctx
    try:
        from .models import LabSettings, LicenseRecord
        lab = LabSettings.get()
        license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
        days_remaining = license.days_remaining if license else 0
        ctx.update({
            'lab_settings': lab,
            'license': license,
            'license_is_valid': license.is_valid if license else False,
            'enabled_modules': license.enabled_modules if license else [],
            'license_days_remaining': days_remaining,
            'license_expiry_warning': 0 < days_remaining <= 30,
        })
    except Exception:
        pass
    return ctx

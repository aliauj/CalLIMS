import json
from datetime import datetime
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect

from .models import LabSettings, LicenseRecord
from .services import decode_license_key, MODULE_LABELS, ALL_MODULES, CORE_MODULES, TIER_DEFAULTS


def license_expired(request):
    """Shown when the license has expired or is missing. No login required."""
    license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
    lab = LabSettings.get()
    return render(request, 'licensing/expired.html', {
        'license': license,
        'lab_settings': lab,
    })


@login_required
def license_status(request):
    """License dashboard — admins and managers only."""
    if request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Only ADMIN or MANAGER can view license information.')
        return redirect('administration:dashboard')

    from apps.users.models import User
    license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
    lab = LabSettings.get()
    user_count = User.objects.filter(is_active=True).count()

    all_module_status = [
        {
            'key': m,
            'label': MODULE_LABELS.get(m, m),
            'enabled': license.is_module_enabled(m) if license else False,
            'core': m in CORE_MODULES,
        }
        for m in ALL_MODULES
    ]

    return render(request, 'licensing/status.html', {
        'license': license,
        'lab': lab,
        'user_count': user_count,
        'all_module_status': all_module_status,
        'tier_choices': LicenseRecord.Tier.choices,
    })


@login_required
def activate_license(request):
    """Activate or replace the license key."""
    if request.user.role != 'ADMIN':
        messages.error(request, 'Only ADMIN users can activate license keys.')
        return redirect('licensing:status')

    if request.method == 'POST':
        key = request.POST.get('license_key', '').strip()
        if not key:
            messages.error(request, 'Please paste the license key.')
            return redirect('licensing:status')

        payload = decode_license_key(key)
        if not payload:
            messages.error(request, 'Invalid or tampered license key. Please contact support.')
            return redirect('licensing:status')

        try:
            valid_from = datetime.strptime(payload['valid_from'], '%Y-%m-%d').date()
            valid_until = datetime.strptime(payload['valid_until'], '%Y-%m-%d').date()
        except (KeyError, ValueError) as e:
            messages.error(request, f'Malformed license key payload: {e}')
            return redirect('licensing:status')

        # Deactivate all previous licenses
        LicenseRecord.objects.filter(is_active=True).update(is_active=False)

        LicenseRecord.objects.create(
            license_key=key,
            license_id=payload.get('license_id', ''),
            issued_to=payload.get('issued_to', ''),
            issued_to_email=payload.get('issued_to_email', ''),
            tier=payload.get('tier', 'STARTER'),
            max_users=int(payload.get('max_users', 5)),
            valid_from=valid_from,
            valid_until=valid_until,
            modules_json=json.dumps(payload.get('modules', [])),
            activated_by=request.user,
        )
        messages.success(
            request,
            f'License activated for {payload["issued_to"]} — '
            f'{payload.get("tier")} tier, valid until {valid_until}.'
        )
        return redirect('licensing:status')

    return redirect('licensing:status')


@login_required
def lab_settings_edit(request):
    """Edit lab branding and contact information."""
    if request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Only ADMIN or MANAGER can edit lab settings.')
        return redirect('administration:dashboard')

    lab = LabSettings.get()

    if request.method == 'POST':
        lab.lab_name = request.POST.get('lab_name', '').strip() or lab.lab_name
        lab.lab_subtitle = request.POST.get('lab_subtitle', '').strip()
        lab.address = request.POST.get('address', '').strip()
        lab.phone = request.POST.get('phone', '').strip()
        lab.email = request.POST.get('email', '').strip()
        lab.website = request.POST.get('website', '').strip()
        lab.accreditation_body = request.POST.get('accreditation_body', '').strip()
        lab.accreditation_number = request.POST.get('accreditation_number', '').strip()
        lab.footer_text = request.POST.get('footer_text', '').strip()

        if 'logo' in request.FILES:
            if lab.logo:
                try:
                    lab.logo.delete(save=False)
                except Exception:
                    pass
            lab.logo = request.FILES['logo']
        elif request.POST.get('clear_logo'):
            if lab.logo:
                try:
                    lab.logo.delete(save=False)
                except Exception:
                    pass
            lab.logo = None

        lab.save()
        messages.success(request, 'Lab settings updated successfully.')
        return redirect('licensing:status')

    return render(request, 'licensing/lab_settings.html', {'lab': lab})


def module_disabled_view(request, module_name):
    """Standalone page when a module URL is hit but not in the license."""
    from .services import MODULE_LABELS
    license = LicenseRecord.objects.filter(is_active=True).order_by('-activated_at').first()
    return render(request, 'licensing/module_disabled.html', {
        'module_name': module_name,
        'module_label': MODULE_LABELS.get(module_name, module_name),
        'license': license,
    }, status=403)

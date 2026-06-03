from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from apps.licensing.decorators import module_required
from apps.certificates.models import Certificate
from apps.assets.models import Instrument


def _client_guard(request):
    """Return the client profile or None if the user is not a valid client."""
    if not request.user.is_client:
        return None
    try:
        return request.user.client_profile
    except Exception:
        return None


@login_required
@module_required('portal')
def portal_dashboard(request):
    client = _client_guard(request)
    if client is None:
        if not request.user.is_client:
            return HttpResponseForbidden('Access restricted to clients.')
        return render(request, 'portal/dashboard.html', {'error': 'No client profile found.'})

    instruments = Instrument.objects.filter(client=client).order_by('asset_tag')
    certificates = Certificate.objects.filter(
        job__instrument__client=client,
        status__in=['ISSUED', 'SIGNED'],
    ).select_related('job__instrument').order_by('-created_at')[:20]
    today = timezone.now().date()
    due_soon = instruments.filter(next_calibration_date__lte=today + timezone.timedelta(days=30))
    return render(request, 'portal/dashboard.html', {
        'client': client,
        'instruments': instruments,
        'certificates': certificates,
        'due_soon': due_soon,
    })


@login_required
@module_required('portal')
def portal_instrument_detail(request, pk):
    client = _client_guard(request)
    if client is None:
        return HttpResponseForbidden('Access restricted to clients.')

    instrument = get_object_or_404(Instrument, pk=pk, client=client)
    jobs = instrument.calibration_jobs.select_related('method', 'assigned_to').order_by('-created_at')[:15]
    certificates = Certificate.objects.filter(
        job__instrument=instrument,
        status__in=['ISSUED', 'SIGNED'],
    ).select_related('job').order_by('-created_at')

    return render(request, 'portal/instrument_detail.html', {
        'instrument': instrument,
        'jobs': jobs,
        'certificates': certificates,
    })

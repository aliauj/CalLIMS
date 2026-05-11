import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import Nonconformance, CorrectiveAction


def _staff_qs():
    from apps.users.models import User
    return User.objects.filter(is_active=True).order_by('last_name', 'first_name')


def _clients_qs():
    from apps.clients.models import Client
    return Client.objects.filter(is_active=True).order_by('name')


def _certs_by_client_json():
    """Return a JSON-safe dict {client_id: [{pk, cert_number, instrument_tag, instrument_desc}, ...]}"""
    from apps.certificates.models import Certificate
    certs = (
        Certificate.objects
        .filter(status__in=['ISSUED', 'SIGNED'])
        .select_related('job__instrument__client')
        .order_by('certificate_number')
    )
    result = {}
    for cert in certs:
        client = cert.job.instrument.client
        if client is None:
            continue
        key = str(client.pk)
        result.setdefault(key, [])
        result[key].append({
            'pk': cert.pk,
            'cert_number': cert.certificate_number,
            'instrument': f"{cert.job.instrument.asset_tag} — {cert.job.instrument.description}",
        })
    return json.dumps(result)


@login_required
def nc_list(request):
    qs = Nonconformance.objects.select_related(
        'detected_by', 'technician', 'certificate', 'job'
    )
    status_filter = request.GET.get('status', '')
    severity_filter = request.GET.get('severity', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if severity_filter:
        qs = qs.filter(severity=severity_filter)
    return render(request, 'nonconformance/nc_list.html', {
        'ncs': qs,
        'status_filter': status_filter,
        'severity_filter': severity_filter,
        'status_choices': Nonconformance.Status.choices,
        'severity_choices': Nonconformance.Severity.choices,
    })


@login_required
def nc_detail(request, pk):
    nc = get_object_or_404(
        Nonconformance.objects.select_related(
            'detected_by', 'technician', 'closed_by',
            'customer', 'certificate', 'job__instrument', 'job__method',
        ).prefetch_related('actions__assigned_to', 'actions__verified_by'),
        pk=pk,
    )
    today = timezone.now().date()
    return render(request, 'nonconformance/nc_detail.html', {
        'nc': nc,
        'today': today,
    })


@login_required
def nc_create(request):
    """
    Create a new NC. Accepts GET params:
      ?certificate=<pk>  — pre-populate from a certificate + its job + technician
    """
    from apps.certificates.models import Certificate

    # Pre-population from certificate trigger
    cert = None
    initial_title = ''
    initial_source = Nonconformance.Source.CALIBRATION
    initial_cert_id = ''
    initial_job_id = ''
    initial_tech_id = ''

    cert_pk = request.GET.get('certificate') or request.POST.get('_certificate_pk')
    if cert_pk:
        cert = Certificate.objects.select_related(
            'job__assigned_to', 'job__instrument'
        ).filter(pk=cert_pk).first()
        if cert:
            initial_title = f'NC: {cert.certificate_number} — {cert.job.instrument}'
            initial_source = Nonconformance.Source.CALIBRATION
            initial_cert_id = cert.pk
            initial_job_id = cert.job.pk
            initial_tech_id = cert.job.assigned_to_id or ''

    if request.method == 'POST':
        source = request.POST['source']
        is_customer = source == 'CUSTOMER_COMPLAINT'
        nc = Nonconformance(
            title=request.POST['title'].strip(),
            description=request.POST['description'].strip(),
            source=source,
            severity=request.POST['severity'],
            detected_by=request.user,
            detected_date=request.POST.get('detected_date') or timezone.now().date(),
            immediate_action=request.POST.get('immediate_action', '').strip(),
            target_closure_date=request.POST.get('target_closure_date') or None,
            customer_resolution=request.POST.get('customer_resolution', '') if is_customer else '',
            complaint_channel=request.POST.get('complaint_channel', '') if is_customer else '',
            customer_id=request.POST.get('customer_id') or None if is_customer else None,
        )
        cert_id = request.POST.get('certificate_id') or None
        job_id = request.POST.get('job_id') or None
        tech_id = request.POST.get('technician_id') or None
        if cert_id:
            nc.certificate_id = cert_id
        if job_id:
            nc.job_id = job_id
        if tech_id:
            nc.technician_id = tech_id
        nc.save()
        messages.success(request, f'Nonconformance {nc.nc_number} raised.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    return render(request, 'nonconformance/nc_form.html', {
        'cert': cert,
        'initial_title': initial_title,
        'initial_source': initial_source,
        'initial_cert_id': initial_cert_id,
        'initial_job_id': initial_job_id,
        'initial_tech_id': initial_tech_id,
        'today': timezone.now().date(),
        'staff': _staff_qs(),
        'clients': _clients_qs(),
        'certs_by_client_json': _certs_by_client_json(),
        'source_choices': Nonconformance.Source.choices,
        'severity_choices': Nonconformance.Severity.choices,
        'customer_resolution_choices': Nonconformance.CustomerResolution.choices,
        'action': 'Raise',
    })


@login_required
def nc_edit(request, pk):
    nc = get_object_or_404(Nonconformance, pk=pk)
    if nc.status == Nonconformance.Status.CLOSED:
        messages.error(request, 'Closed nonconformances cannot be edited.')
        return redirect('nonconformance:nc_detail', pk=pk)

    if request.method == 'POST':
        nc.title = request.POST['title'].strip()
        nc.description = request.POST['description'].strip()
        nc.source = request.POST['source']
        nc.severity = request.POST['severity']
        nc.status = request.POST['status']
        nc.immediate_action = request.POST.get('immediate_action', '').strip()
        nc.root_cause = request.POST.get('root_cause', '').strip()
        nc.target_closure_date = request.POST.get('target_closure_date') or None
        is_customer = nc.source == 'CUSTOMER_COMPLAINT'
        nc.customer_resolution = request.POST.get('customer_resolution', '') if is_customer else ''
        nc.complaint_channel = request.POST.get('complaint_channel', '') if is_customer else ''
        nc.customer_id = request.POST.get('customer_id') or None if is_customer else None
        cert_id = request.POST.get('certificate_id') or None
        if cert_id:
            nc.certificate_id = cert_id
        tech_id = request.POST.get('technician_id') or None
        nc.technician_id = tech_id
        nc.save()
        messages.success(request, f'{nc.nc_number} updated.')
        return redirect('nonconformance:nc_detail', pk=pk)

    return render(request, 'nonconformance/nc_form.html', {
        'nc': nc,
        'initial_title': '',
        'initial_source': '',
        'initial_cert_id': '',
        'initial_job_id': '',
        'initial_tech_id': '',
        'today': timezone.now().date(),
        'staff': _staff_qs(),
        'clients': _clients_qs(),
        'certs_by_client_json': _certs_by_client_json(),
        'source_choices': Nonconformance.Source.choices,
        'severity_choices': Nonconformance.Severity.choices,
        'status_choices': Nonconformance.Status.choices,
        'customer_resolution_choices': Nonconformance.CustomerResolution.choices,
        'action': 'Edit',
    })


@login_required
def nc_close(request, pk):
    if request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Only ADMIN or MANAGER can close a nonconformance.')
        return redirect('nonconformance:nc_detail', pk=pk)
    nc = get_object_or_404(Nonconformance, pk=pk)
    if not nc.all_capas_verified:
        messages.error(request, 'All corrective/preventive actions must be verified before closing.')
        return redirect('nonconformance:nc_detail', pk=pk)
    nc.status = Nonconformance.Status.CLOSED
    nc.closed_date = timezone.now().date()
    nc.closed_by = request.user
    nc.save(update_fields=['status', 'closed_date', 'closed_by', 'updated_at'])
    messages.success(request, f'{nc.nc_number} closed.')
    return redirect('nonconformance:nc_detail', pk=pk)


# ── CAPA views ────────────────────────────────────────────────────────────────

@login_required
def capa_create(request, nc_pk):
    nc = get_object_or_404(Nonconformance, pk=nc_pk)
    if nc.status == Nonconformance.Status.CLOSED:
        messages.error(request, 'Cannot add actions to a closed nonconformance.')
        return redirect('nonconformance:nc_detail', pk=nc_pk)

    if request.method == 'POST':
        CorrectiveAction.objects.create(
            nonconformance=nc,
            action_type=request.POST['action_type'],
            description=request.POST['description'].strip(),
            assigned_to_id=request.POST['assigned_to'],
            due_date=request.POST['due_date'],
        )
        # Advance NC status to investigating if still open
        if nc.status == Nonconformance.Status.OPEN:
            nc.status = Nonconformance.Status.INVESTIGATING
            nc.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Action added.')
        return redirect('nonconformance:nc_detail', pk=nc_pk)

    return render(request, 'nonconformance/capa_form.html', {
        'nc': nc,
        'staff': _staff_qs(),
        'action_type_choices': CorrectiveAction.ActionType.choices,
        'action': 'Add',
    })


@login_required
def capa_edit(request, pk):
    capa = get_object_or_404(CorrectiveAction.objects.select_related('nonconformance'), pk=pk)
    nc = capa.nonconformance
    if capa.status == CorrectiveAction.Status.VERIFIED:
        messages.error(request, 'Verified actions cannot be edited.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    if request.method == 'POST':
        capa.action_type = request.POST['action_type']
        capa.description = request.POST['description'].strip()
        capa.assigned_to_id = request.POST['assigned_to']
        capa.due_date = request.POST['due_date']
        capa.save()
        messages.success(request, 'Action updated.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    return render(request, 'nonconformance/capa_form.html', {
        'nc': nc,
        'capa': capa,
        'staff': _staff_qs(),
        'action_type_choices': CorrectiveAction.ActionType.choices,
        'action': 'Edit',
    })


@login_required
def capa_complete(request, pk):
    capa = get_object_or_404(CorrectiveAction.objects.select_related('nonconformance'), pk=pk)
    nc = capa.nonconformance
    # Assigned person, manager, or admin can mark complete
    if request.user not in (capa.assigned_to,) and request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Only the assigned person or a manager can mark this complete.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    if request.method == 'POST':
        capa.status = CorrectiveAction.Status.COMPLETED
        capa.completion_notes = request.POST.get('completion_notes', '').strip()
        capa.completed_date = timezone.now().date()
        capa.save(update_fields=['status', 'completion_notes', 'completed_date', 'updated_at'])
        # Advance NC to awaiting verification if all actions are completed or verified
        non_open = all(
            a.status in (CorrectiveAction.Status.COMPLETED, CorrectiveAction.Status.VERIFIED)
            for a in nc.actions.all()
        )
        if non_open and nc.status != Nonconformance.Status.AWAITING_VERIFICATION:
            nc.status = Nonconformance.Status.AWAITING_VERIFICATION
            nc.save(update_fields=['status', 'updated_at'])
        messages.success(request, 'Action marked as completed — awaiting verification.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    return render(request, 'nonconformance/capa_complete.html', {'capa': capa, 'nc': nc})


@login_required
def capa_verify(request, pk):
    if request.user.role not in ('ADMIN', 'MANAGER', 'REVIEWER'):
        messages.error(request, 'Only ADMIN, MANAGER, or REVIEWER can verify actions.')
        return redirect('nonconformance:nc_list')

    capa = get_object_or_404(CorrectiveAction.objects.select_related('nonconformance'), pk=pk)
    nc = capa.nonconformance
    if capa.status != CorrectiveAction.Status.COMPLETED:
        messages.error(request, 'Action must be marked complete before it can be verified.')
        return redirect('nonconformance:nc_detail', pk=nc.pk)

    capa.status = CorrectiveAction.Status.VERIFIED
    capa.verified_by = request.user
    capa.verified_at = timezone.now()
    capa.save(update_fields=['status', 'verified_by', 'verified_at', 'updated_at'])
    messages.success(request, 'Action verified as effective.')
    return redirect('nonconformance:nc_detail', pk=nc.pk)

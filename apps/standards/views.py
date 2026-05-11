import json
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from .models import ReferenceStandard, MeasurementUnit, StandardUncertainty


@login_required
def standard_list(request):
    qs = list(ReferenceStandard.objects.select_related('uncertainty_unit', 'custodian').order_by('name'))
    today = timezone.now().date()
    status_filter = request.GET.get('status', '')
    for std in qs:
        std.days_until_expiry = (std.calibration_due_date - today).days
    if status_filter:
        qs = [s for s in qs if s.status == status_filter]
    return render(request, 'standards/standard_list.html', {
        'standards': qs,
        'status_filter': status_filter,
        'status_choices': ReferenceStandard.Status.choices,
    })


@login_required
def standard_detail(request, pk):
    std = get_object_or_404(
        ReferenceStandard.objects.select_related('uncertainty_unit', 'custodian')
        .prefetch_related('uncertainties__unit'),
        pk=pk,
    )
    return render(request, 'standards/standard_detail.html', {'standard': std})


@login_required
def standard_create(request):
    if request.method == 'POST':
        ReferenceStandard.objects.create(
            serial_number=request.POST['serial_number'],
            name=request.POST['name'],
            description=request.POST.get('description', ''),
            manufacturer=request.POST.get('manufacturer', ''),
            uncertainty_value=request.POST['uncertainty_value'],
            uncertainty_unit_id=request.POST['uncertainty_unit'],
            calibration_date=request.POST['calibration_date'],
            calibration_due_date=request.POST['calibration_due_date'],
            certificate_number=request.POST.get('certificate_number', ''),
            issued_by=request.POST.get('issued_by', ''),
            custodian_id=request.POST.get('custodian') or None,
        )
        messages.success(request, 'Reference standard registered.')
        return redirect('standards:standard_list')
    units = MeasurementUnit.objects.all()
    from apps.users.models import User
    staff = User.objects.filter(role__in=['ADMIN', 'MANAGER', 'TECHNICIAN'])
    return render(request, 'standards/standard_create.html', {'units': units, 'staff': staff})


@login_required
def standard_edit(request, pk):
    """Edit a reference standard — uncertainty, traceability, dates, status."""
    if request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Only ADMIN or MANAGER can edit reference standards.')
        return redirect('standards:standard_detail', pk=pk)

    std = get_object_or_404(ReferenceStandard, pk=pk)

    if request.method == 'POST':
        std.name = request.POST['name'].strip()
        std.description = request.POST.get('description', '')
        std.manufacturer = request.POST.get('manufacturer', '')
        std.model_number = request.POST.get('model_number', '')
        std.status = request.POST['status']
        std.location = request.POST.get('location', '')
        std.notes = request.POST.get('notes', '')
        std.calibration_date = request.POST['calibration_date']
        std.calibration_due_date = request.POST['calibration_due_date']
        std.calibration_interval_days = int(request.POST.get('calibration_interval_days', 365))
        std.certificate_number = request.POST.get('certificate_number', '')
        std.issued_by = request.POST.get('issued_by', '')
        std.custodian_id = request.POST.get('custodian') or None

        # Traceability chain
        try:
            chain = json.loads(request.POST.get('traceability_chain_json', '[]'))
            std.traceability_chain = [l for l in chain if l.get('issuing_body', '').strip()]
        except (json.JSONDecodeError, TypeError):
            std.traceability_chain = []

        # Uncertainties — replace all existing entries with the submitted list
        try:
            u_entries = json.loads(request.POST.get('uncertainties_json', '[]'))
        except (json.JSONDecodeError, TypeError):
            u_entries = []

        std.save()

        # Sync uncertainties: delete all, recreate from submitted data
        std.uncertainties.all().delete()
        for seq, entry in enumerate(u_entries, start=1):
            param = entry.get('parameter', '').strip()
            unit_id = entry.get('unit_id')
            uval = entry.get('uncertainty_value', '')
            if not param or not unit_id or not uval:
                continue
            try:
                StandardUncertainty.objects.create(
                    standard=std,
                    sequence=seq,
                    parameter=param,
                    range_description=entry.get('range_description', ''),
                    uncertainty_value=uval,
                    coverage_factor=entry.get('coverage_factor') or 2,
                    unit_id=unit_id,
                    confidence_level=entry.get('confidence_level') or 95.45,
                    notes=entry.get('notes', ''),
                )
            except Exception:
                pass

        # Keep legacy field in sync with the first entry
        first = std.uncertainties.order_by('sequence').first()
        if first:
            std.uncertainty_value = first.uncertainty_value
            std.uncertainty_unit = first.unit
            std.save(update_fields=['uncertainty_value', 'uncertainty_unit'])

        messages.success(request, f'{std.serial_number} updated successfully.')
        return redirect('standards:standard_detail', pk=pk)

    from apps.users.models import User
    units = MeasurementUnit.objects.order_by('quantity_type', 'symbol')
    staff = User.objects.filter(is_active=True, role__in=['ADMIN', 'MANAGER', 'TECHNICIAN']).order_by('last_name')
    existing_uncertainties = list(
        std.uncertainties.select_related('unit').order_by('sequence').values(
            'sequence', 'parameter', 'range_description',
            'uncertainty_value', 'coverage_factor', 'unit_id',
            'unit__symbol', 'confidence_level', 'notes',
        )
    )
    # Make Decimal values JSON-serialisable
    for e in existing_uncertainties:
        e['uncertainty_value'] = str(e['uncertainty_value'])
        e['coverage_factor'] = str(e['coverage_factor'])
        e['confidence_level'] = str(e['confidence_level'])

    return render(request, 'standards/standard_edit.html', {
        'standard': std,
        'units': units,
        'staff': staff,
        'status_choices': ReferenceStandard.Status.choices,
        'traceability_json': json.dumps(std.traceability_chain),
        'uncertainties_json': json.dumps(existing_uncertainties),
    })

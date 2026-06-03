import random
import string
from decimal import Decimal, InvalidOperation
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from apps.users.permissions import lab_staff_required
from .models import CalibrationJob, CalibrationMethod, CalibrationPoint, MeasurementResult
from apps.assets.models import Instrument
from apps.standards.models import ReferenceStandard


@login_required
@lab_staff_required
def dashboard(request):
    today = timezone.now().date()
    user = request.user
    ctx = {
        'jobs_in_progress': CalibrationJob.objects.filter(
            status__in=['received', 'assigned', 'in_progress']
        ).count(),
        'jobs_review': CalibrationJob.objects.filter(status='review').count(),
        'overdue_instruments': Instrument.objects.filter(
            next_calibration_date__lt=today, status='ACTIVE'
        ).count(),
        'expiring_standards': ReferenceStandard.objects.filter(
            calibration_due_date__lte=today + timezone.timedelta(days=30),
            status='ACTIVE',
        ).count(),
        'recent_jobs': CalibrationJob.objects.select_related(
            'instrument', 'assigned_to'
        ).order_by('-created_at')[:10],
    }

    role = getattr(user, 'role', None)
    if role == 'TECHNICIAN':
        ctx['pending_assigned'] = CalibrationJob.objects.filter(
            assigned_to=user, status='assigned'
        ).select_related('instrument', 'method').order_by('due_date')[:10]
        ctx['pending_corrections'] = CalibrationJob.objects.filter(
            assigned_to=user, status='in_progress'
        ).exclude(rejection_notes='').select_related('instrument').order_by('-created_at')[:10]

    elif role in ('MANAGER', 'ADMIN'):
        ctx['pending_review_jobs'] = CalibrationJob.objects.filter(
            status='review'
        ).select_related('instrument', 'assigned_to').order_by('created_at')[:10]
        ctx['unassigned_jobs'] = CalibrationJob.objects.filter(
            status='received'
        ).select_related('instrument').order_by('priority', 'received_date')[:10]
        ctx['overdue_list'] = Instrument.objects.filter(
            next_calibration_date__lt=today, status='ACTIVE'
        ).select_related('client').order_by('next_calibration_date')[:8]
        ctx['expiring_list'] = ReferenceStandard.objects.filter(
            calibration_due_date__lte=today + timezone.timedelta(days=30),
            status='ACTIVE',
        ).order_by('calibration_due_date')[:8]

    elif role == 'REVIEWER':
        ctx['pending_review_jobs'] = CalibrationJob.objects.filter(
            status='review'
        ).select_related('instrument', 'assigned_to').order_by('created_at')[:10]

    ctx['today'] = today
    return render(request, 'workflows/dashboard.html', ctx)


@login_required
@lab_staff_required
def job_list(request):
    qs = CalibrationJob.objects.select_related(
        'instrument', 'assigned_to', 'method'
    ).order_by('-created_at')
    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)
    if request.user.role == 'TECHNICIAN':
        qs = qs.filter(assigned_to=request.user)
    return render(request, 'workflows/job_list.html', {
        'jobs': qs,
        'status_filter': status_filter,
        'status_choices': CalibrationJob.Status.choices,
    })


@login_required
@lab_staff_required
def job_detail(request, pk):
    from django.db.models import Q
    from apps.users.models import User, TechnicianMethodAuthorization
    job = get_object_or_404(
        CalibrationJob.objects.select_related(
            'instrument', 'method', 'assigned_to', 'reviewed_by'
        ),
        pk=pk,
    )
    results = job.results.select_related('unit', 'reference_standard').order_by('sequence')

    today = timezone.now().date()
    all_techs = list(
        User.objects.filter(is_active=True, role__in=['TECHNICIAN', 'MANAGER', 'ADMIN'])
        .order_by('last_name', 'first_name')
    )
    authorized_ids = set(
        TechnicianMethodAuthorization.objects.filter(
            method=job.method,
            status='AUTHORIZED',
        ).filter(
            Q(expiry_date__isnull=True) | Q(expiry_date__gte=today)
        ).values_list('technician_id', flat=True)
    )
    for tech in all_techs:
        tech.is_authorized = tech.pk in authorized_ids

    authorized_techs = [t for t in all_techs if t.is_authorized]
    unauthorized_techs = [t for t in all_techs if not t.is_authorized]

    return render(request, 'workflows/job_detail.html', {
        'job': job,
        'results': results,
        'authorized_techs': authorized_techs,
        'unauthorized_techs': unauthorized_techs,
        'today': today,
    })


@login_required
@lab_staff_required
def job_create(request):
    if request.method == 'POST':
        instrument_id = request.POST.get('instrument')
        method_id = request.POST.get('method')
        priority = request.POST.get('priority', 2)
        due_date = request.POST.get('due_date') or None
        notes = request.POST.get('notes', '')
        job_num = f"JOB-{timezone.now().strftime('%Y%m')}-{''.join(random.choices(string.digits, k=4))}"
        instrument = get_object_or_404(Instrument, pk=instrument_id)
        method = get_object_or_404(CalibrationMethod, pk=method_id)
        job = CalibrationJob.objects.create(
            job_number=job_num,
            instrument=instrument,
            method=method,
            priority=int(priority),
            due_date=due_date,
            notes=notes,
            received_date=timezone.now().date(),
            created_by=request.user,
        )
        instrument.status = Instrument.Status.IN_CALIBRATION
        instrument.save(update_fields=['status'])
        messages.success(request, f'Job {job.job_number} created successfully.')
        return redirect('workflows:job_detail', pk=job.pk)
    instruments = Instrument.objects.filter(
        status__in=['ACTIVE', 'CALIBRATED']
    ).select_related('client')
    methods = CalibrationMethod.objects.filter(is_active=True)
    return render(request, 'workflows/job_create.html', {
        'instruments': instruments,
        'methods': methods,
        'preselected_instrument': request.GET.get('instrument', ''),
    })


# ── FSM TRANSITIONS ──────────────────────────────────────────────

@login_required
@lab_staff_required
def job_assign(request, pk):
    """Assign a technician and move job to ASSIGNED."""
    from django.db.models import Q
    from apps.users.models import TechnicianMethodAuthorization
    job = get_object_or_404(CalibrationJob.objects.select_related('method'), pk=pk)
    if request.method == 'POST':
        tech_id = request.POST.get('technician') or None
        if tech_id:
            auth = TechnicianMethodAuthorization.objects.filter(
                technician_id=tech_id,
                method=job.method,
                status='AUTHORIZED',
            ).filter(
                Q(expiry_date__isnull=True) | Q(expiry_date__gte=timezone.now().date())
            ).first()
            if not auth:
                messages.error(
                    request,
                    f'This technician is not authorized for method {job.method.code} — {job.method.name}. '
                    f'Update the Authorization Matrix first.'
                )
                return redirect('workflows:job_detail', pk=pk)
        try:
            job.assigned_to_id = tech_id
            job.assign()
            job.save()
            messages.success(request, f'{job.job_number} assigned.')
            job.refresh_from_db(fields=['assigned_to_id'])
            _notify_technician_assigned(job)
        except Exception as e:
            messages.error(request, f'Cannot assign: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_start(request, pk):
    """Move job from ASSIGNED → IN_PROGRESS."""
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        try:
            job.start()
            job.save()
            messages.success(request, f'{job.job_number} is now In Progress.')
        except Exception as e:
            messages.error(request, f'Cannot start: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_submit_review(request, pk):
    """Move job from IN_PROGRESS → UNDER REVIEW and notify managers."""
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        if not job.results.exists():
            messages.error(request, 'Cannot submit for review: no measurement results recorded.')
            return redirect('workflows:job_detail', pk=pk)
        try:
            job.submit_for_review()
            job.save()
            messages.success(request, f'{job.job_number} submitted for review.')
            _notify_managers(job, request.user)
        except Exception as e:
            messages.error(request, f'Cannot submit: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_approve(request, pk):
    """Move job from REVIEW → APPROVED and notify the assigned technician."""
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        if request.user.role not in ('REVIEWER', 'MANAGER', 'ADMIN'):
            messages.error(request, 'You do not have permission to approve jobs.')
            return redirect('workflows:job_detail', pk=pk)
        try:
            job.reviewed_by = request.user
            job.rejection_notes = ''  # clear any previous rejection
            job.approve()
            job.save()
            messages.success(request, f'{job.job_number} approved.')
            _notify_technician_approved(job, request.user)
        except Exception as e:
            messages.error(request, f'Cannot approve: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_reject(request, pk):
    """Move job from REVIEW → back to IN_PROGRESS with a mandatory rejection reason."""
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        if request.user.role not in ('REVIEWER', 'MANAGER', 'ADMIN'):
            messages.error(request, 'You do not have permission to reject jobs.')
            return redirect('workflows:job_detail', pk=pk)
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'A rejection reason is required.')
            return redirect('workflows:job_detail', pk=pk)
        try:
            job.rejection_notes = reason
            job.reject_review()
            job.save()
            messages.warning(request, f'{job.job_number} returned to technician for correction.')
            _notify_technician_rejected(job, request.user, reason)
        except Exception as e:
            messages.error(request, f'Cannot reject: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_complete(request, pk):
    """Move job from APPROVED → COMPLETED and update equipment dates."""
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        try:
            job.complete()
            job.save()
            # Update instrument calibration dates
            instr = job.instrument
            instr.last_calibration_date = job.completed_date
            instr.next_calibration_date = job.completed_date + timezone.timedelta(
                days=instr.calibration_interval_days
            )
            instr.status = Instrument.Status.CALIBRATED
            instr.save(update_fields=['last_calibration_date', 'next_calibration_date', 'status'])
            messages.success(request, f'{job.job_number} completed. Certificate will be generated.')
            _notify_client_job_completed(job)
        except Exception as e:
            messages.error(request, f'Cannot complete: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_hold(request, pk):
    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        try:
            job.hold()
            job.save()
            messages.warning(request, f'{job.job_number} placed on hold.')
        except Exception as e:
            messages.error(request, f'Cannot hold: {e}')
    return redirect('workflows:job_detail', pk=pk)


@login_required
@lab_staff_required
def job_delete(request, pk):
    """Permanently delete a job. Admin/Manager only — for cancelled customer requests."""
    from django.db.models import ProtectedError

    if request.user.role not in ('ADMIN', 'MANAGER'):
        messages.error(request, 'Access denied. Admin or Manager role required to delete jobs.')
        return redirect('workflows:job_detail', pk=pk)

    job = get_object_or_404(CalibrationJob, pk=pk)
    if request.method == 'POST':
        job_number = job.job_number
        try:
            job.delete()
        except ProtectedError:
            messages.error(
                request,
                f'Cannot delete {job_number}: a certificate is linked to it. '
                'Revoke the certificate first.',
            )
            return redirect('workflows:job_detail', pk=pk)
        messages.success(request, f'Job {job_number} deleted.')
        return redirect('workflows:job_list')
    return redirect('workflows:job_detail', pk=pk)


# ── DATA ENTRY ────────────────────────────────────────────────────

@login_required
@lab_staff_required
def job_enter_results(request, pk):
    """Technician enters DUT readings at each calibration point."""
    job = get_object_or_404(
        CalibrationJob.objects.select_related('method', 'instrument'),
        pk=pk,
    )
    points = job.method.calibration_points.select_related('unit').order_by('sequence')
    active_standards = ReferenceStandard.objects.filter(status='ACTIVE').order_by('name')
    existing = {r.sequence: r for r in job.results.select_related('unit', 'reference_standard')}

    if request.method == 'POST':
        ref_std_id = request.POST.get('reference_standard')
        ref_std = get_object_or_404(ReferenceStandard, pk=ref_std_id)
        temp = request.POST.get('temperature_c') or None
        humidity = request.POST.get('humidity_pct') or None

        # Save environmental conditions
        if temp:
            job.temperature_c = Decimal(temp)
        if humidity:
            job.humidity_pct = Decimal(humidity)
        job.save(update_fields=['temperature_c', 'humidity_pct'])

        # Load uncertainty calculator
        from apps.uncertainty.services import UncertaintyCalculator
        calc = UncertaintyCalculator()
        contributors_data = [
            {
                'name': c.name,
                'value': float(c.value or 0),
                'divisor': float(c.divisor),
                'sensitivity_coefficient': float(c.sensitivity_coefficient),
                'distribution': c.distribution,
            }
            for c in job.method.contributors.all()
        ]
        uncertainty_result = calc.calculate(contributors_data, reference_standard=ref_std)
        k = Decimal(str(job.method.coverage_factor))
        combined_u = Decimal(str(uncertainty_result['combined_u']))
        expanded_u = Decimal(str(uncertainty_result['expanded_u']))

        saved = 0
        for point in points:
            field_name = f'measured_{point.pk}'
            raw = request.POST.get(field_name, '').strip()
            if not raw:
                continue
            try:
                measured = Decimal(raw)
            except InvalidOperation:
                messages.error(request, f'Invalid value for point "{point.label}".')
                continue

            error = measured - point.nominal_value

            # Pass/fail against tolerance
            pass_fail = None
            if point.tolerance_positive is not None or point.tolerance_negative is not None:
                tol_pos = point.tolerance_positive or point.tolerance_negative
                tol_neg = point.tolerance_negative or point.tolerance_positive
                pass_fail = (-tol_neg <= error <= tol_pos)

            defaults = dict(
                parameter=point.label,
                nominal_value=point.nominal_value,
                measured_value=measured,
                unit=point.unit,
                error=error,
                standard_uncertainty=combined_u,
                coverage_factor_k=k,
                expanded_uncertainty=expanded_u,
                reference_standard=ref_std,
                uncertainty_snapshot=uncertainty_result,
                pass_fail=pass_fail,
                tolerance=point.tolerance_positive,
            )
            MeasurementResult.objects.update_or_create(
                job=job,
                parameter=point.label,
                sequence=point.sequence,
                defaults=defaults,
            )
            saved += 1

        if saved:
            messages.success(request, f'{saved} measurement result(s) saved.')
        return redirect('workflows:job_detail', pk=pk)

    return render(request, 'workflows/job_enter_results.html', {
        'job': job,
        'points': points,
        'active_standards': active_standards,
        'existing': existing,
    })


# ── NOTIFICATION HELPERS ──────────────────────────────────────────

def _notify_technician_assigned(job):
    """Notify the assigned technician that a job has been assigned to them."""
    if not job.assigned_to:
        return
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=job.assigned_to,
        notification_type=Notification.NotificationType.JOB_ASSIGNED,
        title=f'Job assigned to you: {job.job_number}',
        message=(
            f'You have been assigned job {job.job_number} '
            f'({job.instrument}) — {job.method}. Please start calibration.'
        ),
        link=f'/dashboard/jobs/{job.pk}/',
    )


def _notify_managers(job, submitted_by):
    """Notify all MANAGER, ADMIN, and REVIEWER users that a job is pending review."""
    from apps.notifications.models import Notification
    from apps.users.models import User
    reviewers = User.objects.filter(is_active=True, role__in=['MANAGER', 'ADMIN', 'REVIEWER'])
    notifications = [
        Notification(
            recipient=r,
            notification_type=Notification.NotificationType.JOB_REVIEW_REQUESTED,
            title=f'Review requested: {job.job_number}',
            message=(
                f'{submitted_by.get_full_name()} has submitted job {job.job_number} '
                f'({job.instrument}) for your review.'
            ),
            link=f'/dashboard/jobs/{job.pk}/',
        )
        for r in reviewers
    ]
    Notification.objects.bulk_create(notifications)


def _notify_technician_rejected(job, rejected_by, reason):
    """Notify the assigned technician that their job was rejected."""
    if not job.assigned_to:
        return
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=job.assigned_to,
        notification_type=Notification.NotificationType.JOB_REJECTED,
        title=f'Correction required: {job.job_number}',
        message=(
            f'{rejected_by.get_full_name()} has returned job {job.job_number} '
            f'for correction.\n\nReason: {reason}'
        ),
        link=f'/dashboard/jobs/{job.pk}/',
    )


def _notify_client_job_completed(job):
    """Notify the client's portal user that their instrument calibration is complete."""
    from apps.notifications.models import Notification
    client = getattr(job.instrument, 'client', None)
    if not client:
        return
    portal_user = getattr(client, 'portal_user', None)
    if not portal_user or not portal_user.is_active:
        return
    Notification.objects.create(
        recipient=portal_user,
        notification_type=Notification.NotificationType.JOB_COMPLETED,
        title=f'Calibration complete: {job.instrument.asset_tag}',
        message=(
            f'The calibration of {job.instrument} (job {job.job_number}) '
            f'has been completed. Your certificate is ready.'
        ),
        link=f'/portal/',
    )


def _notify_technician_approved(job, approved_by):
    """Notify the assigned technician that their job was approved."""
    if not job.assigned_to:
        return
    from apps.notifications.models import Notification
    Notification.objects.create(
        recipient=job.assigned_to,
        notification_type=Notification.NotificationType.JOB_APPROVED,
        title=f'Job approved: {job.job_number}',
        message=(
            f'{approved_by.get_full_name()} has approved job {job.job_number}. '
            f'Ready to complete and issue certificate.'
        ),
        link=f'/dashboard/jobs/{job.pk}/',
    )

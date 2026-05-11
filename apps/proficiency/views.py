from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone


@login_required
def scheme_list(request):
    from .models import PTScheme

    status_filter = request.GET.get('status', '')
    schemes = PTScheme.objects.select_related('provider').all()
    if status_filter:
        schemes = schemes.filter(status=status_filter)

    return render(request, 'proficiency/scheme_list.html', {
        'schemes': schemes,
        'status_filter': status_filter,
        'status_choices': PTScheme.Status.choices,
    })


@login_required
def scheme_detail(request, pk):
    from .models import PTScheme

    scheme = get_object_or_404(
        PTScheme.objects.select_related('provider'),
        pk=pk,
    )
    participations = scheme.participations.select_related(
        'technician', 'method'
    ).all()

    return render(request, 'proficiency/scheme_detail.html', {
        'scheme': scheme,
        'participations': participations,
    })


@login_required
def scheme_create(request):
    from .models import PTProvider, PTScheme

    providers = PTProvider.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        p = request.POST
        try:
            scheme = PTScheme.objects.create(
                provider_id=p['provider'],
                name=p['name'],
                code=p['code'],
                measurand=p['measurand'],
                unit_symbol=p.get('unit_symbol', ''),
                year=p['year'],
                round_number=p.get('round_number') or 1,
                status=p.get('status', PTScheme.Status.OPEN),
                sample_dispatch_date=p.get('sample_dispatch_date') or None,
                results_due_date=p.get('results_due_date') or None,
                assigned_value=p.get('assigned_value') or None,
                assigned_std_dev=p.get('assigned_std_dev') or None,
                description=p.get('description', ''),
            )
            messages.success(request, f'Scheme "{scheme}" created successfully.')
            return redirect('proficiency:scheme_list')
        except Exception as exc:
            messages.error(request, f'Could not create scheme: {exc}')

    return render(request, 'proficiency/scheme_form.html', {
        'providers': providers,
        'status_choices': PTScheme.Status.choices,
        'action': 'Create',
    })


@login_required
def scheme_edit(request, pk):
    from .models import PTProvider, PTScheme

    scheme = get_object_or_404(PTScheme, pk=pk)
    providers = PTProvider.objects.filter(is_active=True).order_by('name')

    if request.method == 'POST':
        p = request.POST
        try:
            scheme.provider_id = p['provider']
            scheme.name = p['name']
            scheme.code = p['code']
            scheme.measurand = p['measurand']
            scheme.unit_symbol = p.get('unit_symbol', '')
            scheme.year = p['year']
            scheme.round_number = p.get('round_number') or 1
            scheme.status = p.get('status', scheme.status)
            scheme.sample_dispatch_date = p.get('sample_dispatch_date') or None
            scheme.results_due_date = p.get('results_due_date') or None
            scheme.assigned_value = p.get('assigned_value') or None
            scheme.assigned_std_dev = p.get('assigned_std_dev') or None
            scheme.description = p.get('description', '')
            scheme.save()
            messages.success(request, f'Scheme "{scheme}" updated successfully.')
            return redirect('proficiency:scheme_detail', pk=scheme.pk)
        except Exception as exc:
            messages.error(request, f'Could not update scheme: {exc}')

    return render(request, 'proficiency/scheme_form.html', {
        'scheme': scheme,
        'providers': providers,
        'status_choices': PTScheme.Status.choices,
        'action': 'Edit',
    })


@login_required
def participation_create(request, scheme_pk):
    from django.contrib.auth import get_user_model

    from apps.workflows.models import CalibrationMethod

    from .models import PTParticipation, PTScheme

    scheme = get_object_or_404(PTScheme, pk=scheme_pk)
    User = get_user_model()
    technicians = User.objects.filter(
        is_active=True,
    ).exclude(role=User.Role.CLIENT).order_by('last_name', 'first_name')
    methods = CalibrationMethod.objects.filter(is_active=True).order_by('code')

    if request.method == 'POST':
        p = request.POST
        try:
            participation = PTParticipation.objects.create(
                scheme=scheme,
                technician_id=p.get('technician') or None,
                method_id=p.get('method') or None,
                status=p.get('status', PTParticipation.ParticipationStatus.REGISTERED),
                notes=p.get('notes', ''),
            )
            messages.success(
                request,
                f'Participation registered for scheme "{scheme}".',
            )
            return redirect('proficiency:scheme_detail', pk=scheme.pk)
        except Exception as exc:
            messages.error(request, f'Could not register participation: {exc}')

    return render(request, 'proficiency/participation_form.html', {
        'scheme': scheme,
        'technicians': technicians,
        'methods': methods,
        'status_choices': PTParticipation.ParticipationStatus.choices,
        'action': 'Register',
    })


@login_required
def participation_detail(request, pk):
    from .models import PTParticipation

    participation = get_object_or_404(
        PTParticipation.objects.select_related(
            'scheme',
            'scheme__provider',
            'technician',
            'method',
            'corrective_action_by',
        ),
        pk=pk,
    )

    return render(request, 'proficiency/participation_detail.html', {
        'participation': participation,
    })


@login_required
def submit_results(request, pk):
    from .models import PTParticipation

    participation = get_object_or_404(
        PTParticipation.objects.select_related('scheme'),
        pk=pk,
    )

    if request.method == 'POST':
        p = request.POST
        try:
            participation.submitted_value = p.get('submitted_value') or None
            participation.expanded_uncertainty = p.get('expanded_uncertainty') or None
            participation.coverage_factor = p.get('coverage_factor') or 2
            participation.submission_date = timezone.now().date()
            participation.notes = p.get('notes', participation.notes)
            participation.status = PTParticipation.ParticipationStatus.RESULTS_SUBMITTED
            participation.calculate_scores()
            participation.save()
            messages.success(request, 'Results submitted and scores calculated.')
        except Exception as exc:
            messages.error(request, f'Could not submit results: {exc}')

    return redirect('proficiency:participation_detail', pk=participation.pk)


@login_required
def corrective_action(request, pk):
    from .models import PTParticipation

    participation = get_object_or_404(PTParticipation, pk=pk)

    if request.method == 'POST':
        p = request.POST
        try:
            participation.corrective_action = p.get('corrective_action', '')
            participation.corrective_action_date = timezone.now().date()
            participation.corrective_action_by = request.user
            participation.status = PTParticipation.ParticipationStatus.EVALUATED
            participation.save()
            messages.success(request, 'Corrective action recorded.')
        except Exception as exc:
            messages.error(request, f'Could not save corrective action: {exc}')

    return redirect('proficiency:participation_detail', pk=participation.pk)


@login_required
def provider_list(request):
    from .models import PTProvider

    providers = PTProvider.objects.all()

    return render(request, 'proficiency/provider_list.html', {
        'providers': providers,
    })


@login_required
def provider_create(request):
    from .models import PTProvider

    if request.method == 'POST':
        p = request.POST
        try:
            provider = PTProvider.objects.create(
                name=p['name'],
                code=p['code'],
                website=p.get('website', ''),
                contact_email=p.get('contact_email', ''),
                accreditation_body=p.get('accreditation_body', ''),
                is_active=bool(p.get('is_active')),
            )
            messages.success(request, f'Provider "{provider}" created successfully.')
            return redirect('proficiency:provider_list')
        except Exception as exc:
            messages.error(request, f'Could not create provider: {exc}')

    return render(request, 'proficiency/provider_form.html', {
        'action': 'Create',
    })


@login_required
def provider_edit(request, pk):
    from .models import PTProvider

    provider = get_object_or_404(PTProvider, pk=pk)

    if request.method == 'POST':
        p = request.POST
        try:
            provider.name = p['name']
            provider.code = p['code']
            provider.website = p.get('website', '')
            provider.contact_email = p.get('contact_email', '')
            provider.accreditation_body = p.get('accreditation_body', '')
            provider.is_active = bool(p.get('is_active'))
            provider.save()
            messages.success(request, f'Provider "{provider}" updated successfully.')
            return redirect('proficiency:provider_list')
        except Exception as exc:
            messages.error(request, f'Could not update provider: {exc}')

    return render(request, 'proficiency/provider_form.html', {
        'provider': provider,
        'action': 'Edit',
    })

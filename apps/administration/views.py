import csv
import json
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.http import HttpResponse
from django.utils import timezone
from django.db.models import Count, Q
from .decorators import admin_required


@admin_required
def dashboard(request):
    from apps.users.models import User
    from apps.assets.models import Instrument
    from apps.standards.models import ReferenceStandard
    from apps.workflows.models import CalibrationJob
    from apps.certificates.models import Certificate
    from apps.compliance.models import AuditLog

    today = timezone.now().date()
    ctx = {
        'total_users': User.objects.count(),
        'active_users': User.objects.filter(is_active=True).count(),
        'total_instruments': Instrument.objects.count(),
        'total_standards': ReferenceStandard.objects.count(),
        'total_jobs': CalibrationJob.objects.count(),
        'total_certificates': Certificate.objects.count(),
        'jobs_by_status': dict(
            CalibrationJob.objects.values_list('status').annotate(c=Count('id')).order_by()
        ),
        'overdue_instruments': Instrument.objects.filter(
            next_calibration_date__lt=today, status='ACTIVE'
        ).count(),
        'expiring_standards': ReferenceStandard.objects.filter(
            calibration_due_date__lte=today + timezone.timedelta(days=30),
            status='ACTIVE',
        ).count(),
        'recent_audit': AuditLog.objects.select_related('user').order_by('-timestamp')[:8],
        'users_by_role': dict(
            User.objects.values_list('role').annotate(c=Count('id')).order_by()
        ),
    }
    return render(request, 'administration/dashboard.html', ctx)


# ── USER MANAGEMENT ──────────────────────────────────────────────

@admin_required
def user_list(request):
    from apps.users.models import User
    users = User.objects.order_by('role', 'last_name', 'first_name')
    return render(request, 'administration/user_list.html', {
        'users': users,
        'all_role_choices': _all_role_choices(),
    })


def _all_role_choices():
    from apps.users.models import User, CustomRole
    custom = [(cr.code, cr.name) for cr in CustomRole.objects.filter()]
    return list(User.Role.choices) + custom


@admin_required
def user_create(request):
    from apps.users.models import User
    if request.method == 'POST':
        email = request.POST['email'].strip()
        if User.objects.filter(email=email).exists():
            messages.error(request, f'Email {email} is already registered.')
            return redirect('administration:user_create')
        password = request.POST['password']
        user = User.objects.create_user(
            email=email,
            password=password,
            first_name=request.POST['first_name'].strip(),
            last_name=request.POST['last_name'].strip(),
            role=request.POST['role'],
        )
        messages.success(request, f'User {user.get_full_name()} created successfully.')
        return redirect('administration:user_list')
    return render(request, 'administration/user_form.html', {
        'role_choices': _all_role_choices(),
        'action': 'Create',
    })


@admin_required
def user_edit(request, pk):
    from apps.users.models import User
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.first_name = request.POST['first_name'].strip()
        user.last_name = request.POST['last_name'].strip()
        user.role = request.POST['role']
        user.is_active = 'is_active' in request.POST
        new_password = request.POST.get('password', '').strip()
        if new_password:
            user.set_password(new_password)
        user.save()
        messages.success(request, f'User {user.get_full_name()} updated.')
        return redirect('administration:user_list')
    return render(request, 'administration/user_form.html', {
        'user_obj': user,
        'role_choices': _all_role_choices(),
        'action': 'Edit',
    })


@admin_required
def user_toggle_active(request, pk):
    from apps.users.models import User
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot deactivate your own account.')
        return redirect('administration:user_list')
    user.is_active = not user.is_active
    user.save(update_fields=['is_active'])
    state = 'activated' if user.is_active else 'deactivated'
    messages.success(request, f'User {user.get_full_name()} {state}.')
    return redirect('administration:user_list')


@admin_required
def user_change_role(request, pk):
    """Quick inline role change from the user list."""
    from apps.users.models import User
    if request.method == 'POST':
        user = get_object_or_404(User, pk=pk)
        new_role = request.POST.get('role', '').strip()
        valid_codes = [v for v, _ in _all_role_choices()]
        if new_role not in valid_codes:
            messages.error(request, 'Invalid role selected.')
        elif user == request.user and new_role != user.role:
            messages.error(request, 'You cannot change your own role.')
        else:
            user.role = new_role
            user.save(update_fields=['role'])
            messages.success(request, f'{user.get_full_name()} role changed to {user.get_role_display()}.')
    return redirect('administration:user_list')


# ── ROLE MANAGEMENT ───────────────────────────────────────────────

@admin_required
def role_list(request):
    from apps.users.models import User, CustomRole
    from django.db.models import Count
    built_in = [
        {'code': val, 'name': label, 'count': User.objects.filter(role=val).count(), 'built_in': True}
        for val, label in User.Role.choices
    ]
    custom_roles = CustomRole.objects.all()
    return render(request, 'administration/role_list.html', {
        'built_in_roles': built_in,
        'custom_roles': custom_roles,
    })


@admin_required
def role_create(request):
    from apps.users.models import CustomRole
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper().replace(' ', '_')
        name = request.POST.get('name', '').strip()
        if not code or not name:
            messages.error(request, 'Code and name are required.')
            return redirect('administration:role_create')
        if CustomRole.objects.filter(code=code).exists():
            messages.error(request, f'Role code "{code}" already exists.')
            return redirect('administration:role_create')
        from apps.users.models import User
        if code in [v for v, _ in User.Role.choices]:
            messages.error(request, f'"{code}" is a reserved built-in role code.')
            return redirect('administration:role_create')
        CustomRole.objects.create(
            code=code,
            name=name,
            description=request.POST.get('description', '').strip(),
            is_lab_staff='is_lab_staff' in request.POST,
        )
        messages.success(request, f'Role "{name}" created.')
        return redirect('administration:role_list')
    return render(request, 'administration/role_form.html', {'action': 'Create'})


@admin_required
def role_edit(request, pk):
    from apps.users.models import CustomRole
    role = get_object_or_404(CustomRole, pk=pk)
    if request.method == 'POST':
        role.name = request.POST.get('name', '').strip()
        role.description = request.POST.get('description', '').strip()
        role.is_lab_staff = 'is_lab_staff' in request.POST
        if not role.name:
            messages.error(request, 'Name is required.')
            return redirect('administration:role_edit', pk=pk)
        role.save()
        messages.success(request, f'Role "{role.name}" updated.')
        return redirect('administration:role_list')
    return render(request, 'administration/role_form.html', {
        'action': 'Edit',
        'role': role,
    })


@admin_required
def role_delete(request, pk):
    from apps.users.models import CustomRole, User
    role = get_object_or_404(CustomRole, pk=pk)
    if request.method == 'POST':
        count = User.objects.filter(role=role.code).count()
        if count:
            messages.error(request, f'Cannot delete: {count} user(s) still have this role. Reassign them first.')
            return redirect('administration:role_list')
        name = role.name
        role.delete()
        messages.success(request, f'Role "{name}" deleted.')
    return redirect('administration:role_list')


# ── CALIBRATION METHODS ──────────────────────────────────────────

@admin_required
def method_list(request):
    from apps.workflows.models import CalibrationMethod
    methods = CalibrationMethod.objects.annotate(job_count=Count('jobs')).order_by('code')
    return render(request, 'administration/method_list.html', {'methods': methods})


@admin_required
def method_create(request):
    from apps.workflows.models import CalibrationMethod
    from apps.certificates.models import CertificateTemplate
    if request.method == 'POST':
        tmpl_id = request.POST.get('certificate_template') or None
        CalibrationMethod.objects.create(
            code=request.POST['code'].strip().upper(),
            name=request.POST['name'].strip(),
            version=request.POST['version'].strip(),
            description=request.POST.get('description', ''),
            coverage_factor=request.POST.get('coverage_factor', 2.0),
            confidence_level=request.POST.get('confidence_level', 95.45),
            is_active='is_active' in request.POST,
            certificate_template_id=tmpl_id,
        )
        messages.success(request, 'Calibration method created.')
        return redirect('administration:method_list')
    from apps.certificates.models import CertificateTemplate
    return render(request, 'administration/method_form.html', {
        'action': 'Create',
        'cert_templates': CertificateTemplate.objects.order_by('-is_default', 'name'),
    })


@admin_required
def method_edit(request, pk):
    from apps.workflows.models import CalibrationMethod
    from apps.certificates.models import CertificateTemplate
    method = get_object_or_404(CalibrationMethod, pk=pk)
    if request.method == 'POST':
        method.code = request.POST['code'].strip().upper()
        method.name = request.POST['name'].strip()
        method.version = request.POST['version'].strip()
        method.description = request.POST.get('description', '')
        method.coverage_factor = request.POST.get('coverage_factor', 2.0)
        method.confidence_level = request.POST.get('confidence_level', 95.45)
        method.is_active = 'is_active' in request.POST
        method.certificate_template_id = request.POST.get('certificate_template') or None
        method.save()
        messages.success(request, f'Method {method.code} updated.')
        return redirect('administration:method_list')
    return render(request, 'administration/method_form.html', {
        'method': method,
        'action': 'Edit',
        'cert_templates': CertificateTemplate.objects.order_by('-is_default', 'name'),
    })


# ── CALIBRATION POINTS ───────────────────────────────────────────

@admin_required
def method_points(request, method_pk):
    from apps.workflows.models import CalibrationMethod, CalibrationPoint
    method = get_object_or_404(CalibrationMethod, pk=method_pk)
    points = method.calibration_points.select_related('unit').order_by('sequence')
    return render(request, 'administration/point_list.html', {
        'method': method,
        'points': points,
    })


@admin_required
def point_create(request, method_pk):
    from apps.workflows.models import CalibrationMethod, CalibrationPoint
    from apps.standards.models import MeasurementUnit
    method = get_object_or_404(CalibrationMethod, pk=method_pk)
    if request.method == 'POST':
        CalibrationPoint.objects.create(
            method=method,
            label=request.POST['label'].strip(),
            nominal_value=request.POST['nominal_value'],
            unit_id=request.POST['unit'],
            tolerance_positive=request.POST.get('tolerance_positive') or None,
            tolerance_negative=request.POST.get('tolerance_negative') or None,
            num_readings=int(request.POST.get('num_readings', 3)),
            sequence=int(request.POST['sequence']),
        )
        messages.success(request, 'Calibration point added.')
        return redirect('administration:method_points', method_pk=method_pk)
    units = MeasurementUnit.objects.order_by('quantity_type', 'symbol')
    next_seq = (method.calibration_points.order_by('-sequence').values_list('sequence', flat=True).first() or 0) + 1
    return render(request, 'administration/point_form.html', {
        'method': method,
        'units': units,
        'next_seq': next_seq,
        'action': 'Add',
    })


@admin_required
def point_edit(request, pk):
    from apps.workflows.models import CalibrationPoint
    from apps.standards.models import MeasurementUnit
    point = get_object_or_404(CalibrationPoint.objects.select_related('method'), pk=pk)
    if request.method == 'POST':
        point.label = request.POST['label'].strip()
        point.nominal_value = request.POST['nominal_value']
        point.unit_id = request.POST['unit']
        point.tolerance_positive = request.POST.get('tolerance_positive') or None
        point.tolerance_negative = request.POST.get('tolerance_negative') or None
        point.num_readings = int(request.POST.get('num_readings', 3))
        point.sequence = int(request.POST['sequence'])
        point.save()
        messages.success(request, 'Calibration point updated.')
        return redirect('administration:method_points', method_pk=point.method_id)
    units = MeasurementUnit.objects.order_by('quantity_type', 'symbol')
    return render(request, 'administration/point_form.html', {
        'point': point,
        'method': point.method,
        'units': units,
        'action': 'Edit',
    })


@admin_required
def point_delete(request, pk):
    from apps.workflows.models import CalibrationPoint
    point = get_object_or_404(CalibrationPoint, pk=pk)
    method_pk = point.method_id
    if request.method == 'POST':
        point.delete()
        messages.success(request, 'Calibration point deleted.')
    return redirect('administration:method_points', method_pk=method_pk)


# ── INSTRUMENT CATEGORIES ────────────────────────────────────────

@admin_required
def category_list(request):
    from apps.assets.models import InstrumentCategory
    categories = InstrumentCategory.objects.annotate(
        instrument_count=Count('instrument')
    ).order_by('name')
    return render(request, 'administration/category_list.html', {'categories': categories})


@admin_required
def category_create(request):
    from apps.assets.models import InstrumentCategory
    if request.method == 'POST':
        name = request.POST['name'].strip()
        code = request.POST.get('code', '').strip().upper()
        if InstrumentCategory.objects.filter(name__iexact=name).exists():
            messages.error(request, f'Category "{name}" already exists.')
        elif code and InstrumentCategory.objects.filter(code__iexact=code).exists():
            messages.error(request, f'Code "{code}" is already used by another category.')
        else:
            InstrumentCategory.objects.create(
                name=name,
                code=code,
                description=request.POST.get('description', ''),
            )
            messages.success(request, f'Category "{name}" created.')
        return redirect('administration:category_list')
    return render(request, 'administration/category_form.html', {'action': 'Create'})


@admin_required
def category_edit(request, pk):
    from apps.assets.models import InstrumentCategory
    category = get_object_or_404(InstrumentCategory, pk=pk)
    if request.method == 'POST':
        code = request.POST.get('code', '').strip().upper()
        if code and InstrumentCategory.objects.filter(code__iexact=code).exclude(pk=pk).exists():
            messages.error(request, f'Code "{code}" is already used by another category.')
            return render(request, 'administration/category_form.html', {
                'category': category, 'action': 'Edit',
            })
        category.name = request.POST['name'].strip()
        category.code = code
        category.description = request.POST.get('description', '')
        category.save()
        messages.success(request, 'Category updated.')
        return redirect('administration:category_list')
    return render(request, 'administration/category_form.html', {
        'category': category,
        'action': 'Edit',
    })


# ── MEASUREMENT UNITS ────────────────────────────────────────────

@admin_required
def unit_list(request):
    from apps.standards.models import MeasurementUnit
    units = MeasurementUnit.objects.annotate(
        standards_count=Count('standards')
    ).order_by('quantity_type', 'symbol')
    return render(request, 'administration/unit_list.html', {'units': units})


@admin_required
def unit_create(request):
    from apps.standards.models import MeasurementUnit
    if request.method == 'POST':
        symbol = request.POST['symbol'].strip()
        if MeasurementUnit.objects.filter(symbol=symbol).exists():
            messages.error(request, f'Unit symbol "{symbol}" already exists.')
        else:
            MeasurementUnit.objects.create(
                symbol=symbol,
                name=request.POST['name'].strip(),
                quantity_type=request.POST['quantity_type'].strip(),
            )
            messages.success(request, f'Unit "{symbol}" created.')
        return redirect('administration:unit_list')
    return render(request, 'administration/unit_form.html', {'action': 'Create'})


@admin_required
def unit_edit(request, pk):
    from apps.standards.models import MeasurementUnit
    unit = get_object_or_404(MeasurementUnit, pk=pk)
    if request.method == 'POST':
        unit.symbol = request.POST['symbol'].strip()
        unit.name = request.POST['name'].strip()
        unit.quantity_type = request.POST['quantity_type'].strip()
        unit.save()
        messages.success(request, 'Unit updated.')
        return redirect('administration:unit_list')
    return render(request, 'administration/unit_form.html', {
        'unit': unit,
        'action': 'Edit',
    })


@admin_required
def certificate_template_list(request):
    from apps.certificates.models import CertificateTemplate
    templates = CertificateTemplate.objects.prefetch_related('methods')
    return render(request, 'administration/certificate_template_list.html', {'templates': templates})


@admin_required
def certificate_template_create(request):
    from apps.certificates.models import CertificateTemplate
    from apps.certificates.views import QR_FIELD_CHOICES, _QR_DEFAULTS
    if request.method == 'POST':
        tmpl = CertificateTemplate(
            name=request.POST.get('name', '').strip() or 'Untitled',
            accreditation_scope=request.POST.get('accreditation_scope', '').strip(),
            accreditation_number=request.POST.get('accreditation_number', '').strip(),
            lab_name=request.POST.get('lab_name', '').strip() or 'CalLIMS',
            lab_subtitle=request.POST.get('lab_subtitle', '').strip(),
            accreditation_text=request.POST.get('accreditation_text', '').strip(),
            declaration_statement=request.POST.get('declaration_statement', '').strip(),
            footer_text=request.POST.get('footer_text', '').strip(),
            is_default='is_default' in request.POST,
            include_sticker='include_sticker' in request.POST,
            qr_info_fields=request.POST.getlist('qr_info_fields'),
        )
        if 'logo' in request.FILES:
            tmpl.logo = request.FILES['logo']
        tmpl.save()
        messages.success(request, f'Template "{tmpl.name}" created.')
        return redirect('administration:certificate_template_list')
    return render(request, 'administration/certificate_template_form.html', {
        'action': 'Create',
        'qr_field_choices': QR_FIELD_CHOICES,
        'qr_defaults': _QR_DEFAULTS,
    })


@admin_required
def certificate_template_edit(request, pk):
    from apps.certificates.models import CertificateTemplate
    from apps.certificates.views import QR_FIELD_CHOICES, _QR_DEFAULTS
    tmpl = get_object_or_404(CertificateTemplate, pk=pk)
    if request.method == 'POST':
        tmpl.name = request.POST.get('name', '').strip() or 'Untitled'
        tmpl.accreditation_scope = request.POST.get('accreditation_scope', '').strip()
        tmpl.accreditation_number = request.POST.get('accreditation_number', '').strip()
        tmpl.lab_name = request.POST.get('lab_name', '').strip() or 'CalLIMS'
        tmpl.lab_subtitle = request.POST.get('lab_subtitle', '').strip()
        tmpl.accreditation_text = request.POST.get('accreditation_text', '').strip()
        tmpl.declaration_statement = request.POST.get('declaration_statement', '').strip()
        tmpl.footer_text = request.POST.get('footer_text', '').strip()
        tmpl.is_default = 'is_default' in request.POST
        tmpl.include_sticker = 'include_sticker' in request.POST
        tmpl.qr_info_fields = request.POST.getlist('qr_info_fields')
        if 'logo' in request.FILES:
            tmpl.logo = request.FILES['logo']
        elif 'logo_clear' in request.POST:
            tmpl.logo = None
        tmpl.save()
        messages.success(request, f'Template "{tmpl.name}" saved.')
        return redirect('administration:certificate_template_list')
    return render(request, 'administration/certificate_template_form.html', {
        'tmpl': tmpl,
        'action': 'Edit',
        'qr_field_choices': QR_FIELD_CHOICES,
        'qr_defaults': _QR_DEFAULTS,
    })


@admin_required
def certificate_template_delete(request, pk):
    from apps.certificates.models import CertificateTemplate
    tmpl = get_object_or_404(CertificateTemplate, pk=pk)
    if tmpl.is_default:
        messages.error(request, 'Cannot delete the default template.')
        return redirect('administration:certificate_template_list')
    if tmpl.methods.exists():
        messages.error(request, f'Cannot delete — {tmpl.methods.count()} method(s) use this template.')
        return redirect('administration:certificate_template_list')
    if request.method == 'POST':
        name = tmpl.name
        tmpl.delete()
        messages.success(request, f'Template "{name}" deleted.')
    return redirect('administration:certificate_template_list')


# ── USER DETAIL / PERMISSIONS ────────────────────────────────────

@admin_required
def user_detail(request, pk):
    from apps.users.models import User, AppSection, UserModulePermission
    from apps.workflows.models import CalibrationMethod
    user_obj = get_object_or_404(User, pk=pk)

    # Build sections list: (value, label, perm_or_None)
    perms_qs = {p.section: p for p in user_obj.module_permissions.all()}
    sections = [
        (value, label, perms_qs.get(value))
        for value, label in AppSection.choices
    ]

    auth_records = []
    if user_obj.role == 'TECHNICIAN':
        auth_records = list(
            user_obj.method_authorizations
            .select_related('method', 'authorized_by')
            .order_by('method__code')
        )

    all_methods = CalibrationMethod.objects.filter(is_active=True).order_by('code')

    return render(request, 'administration/user_detail.html', {
        'user_obj': user_obj,
        'sections': sections,
        'auth_records': auth_records,
        'all_methods': all_methods,
        'today': timezone.now().date(),
    })


@admin_required
def user_permissions_save(request, pk):
    from apps.users.models import User, AppSection, UserModulePermission
    if request.method != 'POST':
        return redirect('administration:user_detail', pk=pk)

    user_obj = get_object_or_404(User, pk=pk)

    if request.POST.get('reset') == '1':
        user_obj.module_permissions.all().delete()
        messages.success(request, f'Permissions for {user_obj.get_full_name()} reset to role defaults.')
        return redirect('administration:user_detail', pk=pk)

    for value, _label in AppSection.choices:
        can_view   = bool(request.POST.get(f'section_{value}_view'))
        can_add    = bool(request.POST.get(f'section_{value}_add'))
        can_modify = bool(request.POST.get(f'section_{value}_modify'))
        can_delete = bool(request.POST.get(f'section_{value}_delete'))
        UserModulePermission.objects.update_or_create(
            user=user_obj,
            section=value,
            defaults={
                'can_view': can_view,
                'can_add': can_add,
                'can_modify': can_modify,
                'can_delete': can_delete,
            },
        )

    messages.success(request, f'Permissions for {user_obj.get_full_name()} saved.')
    return redirect('administration:user_detail', pk=pk)


# ── TECHNICIAN AUTHORIZATION MATRIX ─────────────────────────────

@admin_required
def authorization_matrix(request):
    from apps.users.models import User, TechnicianMethodAuthorization
    from apps.workflows.models import CalibrationMethod

    technicians = list(
        User.objects.filter(role='TECHNICIAN', is_active=True)
        .order_by('last_name', 'first_name')
    )
    methods = list(CalibrationMethod.objects.filter(is_active=True).order_by('code'))

    auth_records = TechnicianMethodAuthorization.objects.select_related('technician', 'method')
    # Build a lookup dict: (tech_pk, method_pk) -> auth
    auth_lookup = {(a.technician_id, a.method_id): a for a in auth_records}

    # Build rows: list of (tech, [(auth_or_None, method) per method])
    rows = []
    for tech in technicians:
        cells = [(auth_lookup.get((tech.pk, m.pk)), m) for m in methods]
        rows.append((tech, cells))

    return render(request, 'administration/authorization_matrix.html', {
        'technicians': technicians,
        'methods': methods,
        'rows': rows,
    })


@admin_required
def authorization_edit(request, pk):
    from apps.users.models import User, TechnicianMethodAuthorization
    auth = get_object_or_404(
        TechnicianMethodAuthorization.objects.select_related('technician', 'method', 'authorized_by'),
        pk=pk,
    )
    if request.method == 'POST':
        auth.status          = request.POST['status']
        auth.authorized_by   = request.user
        auth.training_date   = request.POST.get('training_date') or None
        auth.evaluation_date = request.POST.get('evaluation_date') or None
        auth.expiry_date     = request.POST.get('expiry_date') or None
        auth.certificate_ref = request.POST.get('certificate_ref', '').strip()
        auth.notes           = request.POST.get('notes', '').strip()
        auth.save()
        messages.success(request, f'Authorization for {auth.technician.get_full_name()} — {auth.method.code} updated.')
        return redirect('administration:authorization_matrix')
    return render(request, 'administration/authorization_form.html', {
        'auth': auth,
        'action': 'Edit',
        'status_choices': TechnicianMethodAuthorization.Status.choices,
    })


@admin_required
def authorization_create(request):
    from apps.users.models import User, TechnicianMethodAuthorization
    from apps.workflows.models import CalibrationMethod

    technicians = User.objects.filter(role='TECHNICIAN', is_active=True).order_by('last_name', 'first_name')
    methods = CalibrationMethod.objects.filter(is_active=True).order_by('code')

    if request.method == 'POST':
        technician_id = request.POST['technician']
        method_id     = request.POST['method']
        auth, created = TechnicianMethodAuthorization.objects.update_or_create(
            technician_id=technician_id,
            method_id=method_id,
            defaults={
                'status':          request.POST.get('status', TechnicianMethodAuthorization.Status.PENDING),
                'authorized_by':   request.user,
                'training_date':   request.POST.get('training_date') or None,
                'evaluation_date': request.POST.get('evaluation_date') or None,
                'expiry_date':     request.POST.get('expiry_date') or None,
                'certificate_ref': request.POST.get('certificate_ref', '').strip(),
                'notes':           request.POST.get('notes', '').strip(),
            },
        )
        verb = 'created' if created else 'updated'
        messages.success(request, f'Authorization {verb} for {auth.technician.get_full_name()} — {auth.method.code}.')
        return redirect('administration:authorization_matrix')

    return render(request, 'administration/authorization_form.html', {
        'technicians': technicians,
        'methods': methods,
        'action': 'Create',
        'status_choices': TechnicianMethodAuthorization.Status.choices,
        'preselect_technician': request.GET.get('technician', ''),
        'preselect_method': request.GET.get('method', ''),
    })


# ── REPORTING ─────────────────────────────────────────────────────

@admin_required
def report_overview(request):
    from apps.workflows.models import CalibrationJob
    from apps.assets.models import Instrument
    from apps.certificates.models import Certificate
    from apps.standards.models import ReferenceStandard

    today = timezone.now().date()
    # Last 12 months job counts per month
    from django.db.models.functions import TruncMonth
    jobs_by_month = (
        CalibrationJob.objects
        .filter(created_at__gte=today - timezone.timedelta(days=365))
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )
    certs_by_month = (
        Certificate.objects
        .filter(created_at__gte=today - timezone.timedelta(days=365), status__in=['ISSUED', 'SIGNED'])
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(count=Count('id'))
        .order_by('month')
    )

    jobs_by_status = dict(
        CalibrationJob.objects.values_list('status').annotate(c=Count('id')).order_by()
    )

    # Build chart series (last 12 calendar months)
    from datetime import date
    months = []
    m = today.replace(day=1)
    for _ in range(12):
        months.append(m)
        if m.month == 1:
            m = m.replace(year=m.year - 1, month=12)
        else:
            m = m.replace(month=m.month - 1)
    months.reverse()

    month_labels = [m.strftime('%b %Y') for m in months]
    job_series = {m: 0 for m in months}
    for row in jobs_by_month:
        key = row['month'].date().replace(day=1)
        if key in job_series:
            job_series[key] = row['count']
    cert_series = {m: 0 for m in months}
    for row in certs_by_month:
        key = row['month'].date().replace(day=1)
        if key in cert_series:
            cert_series[key] = row['count']

    from apps.nonconformance.models import Nonconformance
    customer_ncs = (
        Nonconformance.objects
        .filter(source='CUSTOMER_COMPLAINT')
        .select_related('detected_by', 'closed_by', 'customer', 'certificate', 'job__instrument')
        .prefetch_related('actions')
        .order_by('-detected_date')
    )
    nc_by_resolution = {}
    for nc in customer_ncs:
        key = nc.customer_resolution or ''
        nc_by_resolution[key] = nc_by_resolution.get(key, 0) + 1

    nc_resolution_counts = {
        'RETURN_RECALIBRATE': nc_by_resolution.get('RETURN_RECALIBRATE', 0),
        'USE_AS_IS': nc_by_resolution.get('USE_AS_IS', 0),
        'CORRECT_REISSUE': nc_by_resolution.get('CORRECT_REISSUE', 0),
        'pending': nc_by_resolution.get('', 0),
    }

    overdue_qs = Instrument.objects.filter(
        next_calibration_date__lt=today, status='ACTIVE'
    )
    overdue_count = overdue_qs.count()
    overdue_instruments = overdue_qs.select_related('client').order_by('next_calibration_date')[:20]

    expiring_qs = ReferenceStandard.objects.filter(
        calibration_due_date__lte=today + timezone.timedelta(days=30),
        status='ACTIVE',
    )
    expiring_count = expiring_qs.count()
    expiring_standards = expiring_qs.order_by('calibration_due_date')[:20]

    return render(request, 'administration/report_overview.html', {
        'month_labels': json.dumps(month_labels),
        'jobs_series': json.dumps(list(job_series.values())),
        'certs_series': json.dumps(list(cert_series.values())),
        'jobs_by_status': jobs_by_status,
        'jobs_by_status_json': json.dumps(jobs_by_status),
        'overdue_instruments': overdue_instruments,
        'expiring_standards': expiring_standards,
        'total_jobs': CalibrationJob.objects.count(),
        'total_certs': Certificate.objects.filter(status__in=['ISSUED', 'SIGNED']).count(),
        'overdue_count': overdue_count,
        'expiring_count': expiring_count,
        'customer_ncs': customer_ncs,
        'nc_resolution_counts': nc_resolution_counts,
        'nc_resolution_choices': Nonconformance.CustomerResolution.choices,
    })


@admin_required
def report_jobs_export(request):
    from apps.workflows.models import CalibrationJob
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="jobs_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Job Number', 'Status', 'Priority', 'Instrument Tag',
        'Instrument Description', 'Client', 'Method', 'Assigned To',
        'Created Date', 'Due Date', 'Completed Date',
    ])
    qs = CalibrationJob.objects.select_related(
        'instrument__client', 'method', 'assigned_to'
    ).order_by('-created_at')

    status_filter = request.GET.get('status', '')
    if status_filter:
        qs = qs.filter(status=status_filter)

    for job in qs:
        writer.writerow([
            job.job_number,
            job.get_status_display(),
            job.get_priority_display(),
            job.instrument.asset_tag,
            job.instrument.description,
            str(job.instrument.client) if job.instrument.client else 'Internal',
            f'{job.method.code} — {job.method.name}',
            job.assigned_to.get_full_name() if job.assigned_to else '',
            job.created_at.strftime('%Y-%m-%d'),
            job.due_date.strftime('%Y-%m-%d') if job.due_date else '',
            job.completed_date.strftime('%Y-%m-%d') if job.completed_date else '',
        ])
    return response


@admin_required
def report_instruments_export(request):
    from apps.assets.models import Instrument
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="instruments_export.csv"'
    writer = csv.writer(response)
    writer.writerow([
        'Instrument Tag', 'Description', 'Serial Number', 'Manufacturer',
        'Model', 'Client', 'Status', 'Last Calibration', 'Next Calibration',
        'Interval (days)', 'Category',
    ])
    for instr in Instrument.objects.select_related('client', 'category').order_by('asset_tag'):
        writer.writerow([
            instr.asset_tag,
            instr.description,
            instr.serial_number,
            instr.manufacturer,
            instr.model_number,
            str(instr.client) if instr.client else 'Internal',
            instr.get_status_display(),
            instr.last_calibration_date.strftime('%Y-%m-%d') if instr.last_calibration_date else '',
            instr.next_calibration_date.strftime('%Y-%m-%d') if instr.next_calibration_date else '',
            instr.calibration_interval_days,
            str(instr.category) if instr.category else '',
        ])
    return response

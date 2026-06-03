from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.http import FileResponse, Http404
from apps.licensing.decorators import module_required
from apps.users.permissions import lab_staff_required
from .models import Certificate, CertificateTemplate


def _scoped_certificate_qs(user, base_qs=None):
    """Restrict certificate access to the requesting user's tenant.

    Lab staff see every certificate; a CLIENT user only ever sees certificates
    whose underlying instrument belongs to their own client profile. Returns an
    empty queryset for a CLIENT without a linked profile so get_object_or_404
    yields a clean 404 instead of leaking another tenant's certificate.
    """
    qs = base_qs if base_qs is not None else Certificate.objects.all()
    if user.is_client:
        try:
            return qs.filter(job__instrument__client=user.client_profile)
        except Exception:
            return qs.none()
    return qs

# Ordered list of all fields that can appear on the QR verification page.
QR_FIELD_CHOICES = [
    ('lab_name',              'Lab Name'),
    ('accreditation_number',  'Accreditation Number'),
    ('accreditation_scope',   'Accreditation Scope'),
    ('accreditation_text',    'Accreditation Text'),
    ('cert_number',           'Certificate Number'),
    ('calibration_date',      'Date of Calibration'),
    ('expiry_date',           'Valid Until'),
    ('instrument_description','Instrument Description'),
    ('instrument_asset_tag',  'Asset Tag'),
    ('serial_number',         'Serial Number'),
    ('manufacturer',          'Manufacturer'),
    ('model_number',          'Model Number'),
    ('client_name',           'Client Name'),
    ('method',                'Calibration Method'),
    ('technician',            'Performed By'),
    ('signed_by',             'Authorized Signatory'),
    ('temperature',           'Lab Temperature'),
    ('humidity',              'Lab Humidity'),
]

_QR_DEFAULTS = [
    'lab_name', 'accreditation_number', 'accreditation_text',
    'cert_number', 'calibration_date', 'expiry_date',
    'instrument_description', 'serial_number',
]


@login_required
@module_required('certificates')
def certificate_list(request):
    qs = Certificate.objects.select_related(
        'job__instrument__client',
        'job__assigned_to',
        'signed_by',
    ).order_by('-created_at')

    if request.user.is_client:
        try:
            qs = qs.filter(job__instrument__client=request.user.client_profile)
        except Exception:
            qs = qs.none()

    # Filters
    status_filter = request.GET.get('status', '')
    client_filter = request.GET.get('client', '')
    tech_filter = request.GET.get('technician', '')
    cert_num_filter = request.GET.get('cert_number', '').strip()
    instrument_filter = request.GET.get('instrument', '').strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if client_filter == 'internal':
        qs = qs.filter(job__instrument__client__isnull=True)
    elif client_filter:
        qs = qs.filter(job__instrument__client_id=client_filter)
    if tech_filter:
        qs = qs.filter(job__assigned_to_id=tech_filter)
    if cert_num_filter:
        qs = qs.filter(certificate_number__icontains=cert_num_filter)
    if instrument_filter:
        qs = qs.filter(job__instrument__asset_tag__icontains=instrument_filter)

    from apps.clients.models import Client
    from apps.users.models import User
    clients = Client.objects.filter(is_active=True).order_by('name') if not request.user.is_client else []
    technicians = User.objects.filter(
        is_active=True, role__in=['TECHNICIAN', 'MANAGER', 'ADMIN']
    ).order_by('last_name', 'first_name') if not request.user.is_client else []

    return render(request, 'certificates/certificate_list.html', {
        'certificates': qs,
        'status_choices': Certificate.Status.choices,
        'clients': clients,
        'technicians': technicians,
        'status_filter': status_filter,
        'client_filter': client_filter,
        'tech_filter': tech_filter,
        'cert_num_filter': cert_num_filter,
        'instrument_filter': instrument_filter,
    })


@login_required
@module_required('certificates')
def certificate_detail(request, pk):
    cert = get_object_or_404(
        _scoped_certificate_qs(
            request.user,
            Certificate.objects.select_related(
                'job__instrument', 'job__method', 'signed_by', 'superseded_by'
            ),
        ),
        pk=pk,
    )
    results = cert.job.results.select_related('unit', 'reference_standard').order_by('sequence')
    return render(request, 'certificates/certificate_detail.html', {
        'cert': cert,
        'results': results,
        'today': timezone.now().date(),
    })


@login_required
@lab_staff_required
@module_required('certificates')
def certificate_edit(request, pk):
    """Edit certificate header information: dates, signatory, notes."""
    cert = get_object_or_404(Certificate, pk=pk)
    if cert.status in ('SIGNED', 'ISSUED', 'REVOKED'):
        messages.error(request, 'A signed or issued certificate cannot be edited.')
        return redirect('certificates:certificate_detail', pk=pk)

    if request.method == 'POST':
        cert.issue_date = request.POST.get('issue_date') or None
        cert.expiry_date = request.POST.get('expiry_date') or None
        cert.notes = request.POST.get('notes', '')
        signatory_id = request.POST.get('signatory') or None
        cert.signed_by_id = signatory_id
        cert.save()
        messages.success(request, 'Certificate information saved.')
        return redirect('certificates:certificate_detail', pk=pk)

    from apps.users.models import User
    signatories = User.objects.filter(
        is_active=True, role__in=['REVIEWER', 'MANAGER', 'ADMIN']
    ).order_by('last_name', 'first_name')
    return render(request, 'certificates/certificate_edit.html', {
        'cert': cert,
        'signatories': signatories,
    })


@login_required
@lab_staff_required
@module_required('certificates')
def certificate_sign(request, pk):
    """Sign the certificate — stamps the current user as signatory."""
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        if cert.status not in ('DRAFT', 'PENDING_SIGN'):
            messages.error(request, 'Only draft or pending certificates can be signed.')
            return redirect('certificates:certificate_detail', pk=pk)
        if request.user.role not in ('REVIEWER', 'MANAGER', 'ADMIN'):
            messages.error(request, 'You do not have permission to sign certificates.')
            return redirect('certificates:certificate_detail', pk=pk)

        cert.signed_by = request.user
        cert.signed_at = timezone.now()
        cert.status = Certificate.Status.SIGNED
        # Set issue_date if not already set
        if not cert.issue_date:
            cert.issue_date = timezone.now().date()
        cert.content_hash = cert.compute_hash()
        cert.save()

        # Regenerate PDF with signature info
        from .tasks import generate_certificate_pdf
        generate_certificate_pdf.delay(cert.pk)

        messages.success(request, f'{cert.certificate_number} signed by {request.user.get_full_name()}.')
    return redirect('certificates:certificate_detail', pk=pk)


@login_required
@lab_staff_required
@module_required('certificates')
def certificate_issue(request, pk):
    """Issue the certificate (SIGNED → ISSUED) — makes it available to the client."""
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        if cert.status != 'SIGNED':
            messages.error(request, 'Certificate must be signed before it can be issued.')
            return redirect('certificates:certificate_detail', pk=pk)
        cert.status = Certificate.Status.ISSUED
        cert.save()
        messages.success(request, f'{cert.certificate_number} has been issued.')
    return redirect('certificates:certificate_detail', pk=pk)


@login_required
@lab_staff_required
@module_required('certificates')
def certificate_revoke(request, pk):
    """Revoke a signed or issued certificate with a mandatory reason."""
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        if cert.status not in ('SIGNED', 'ISSUED'):
            messages.error(request, 'Only signed or issued certificates can be revoked.')
            return redirect('certificates:certificate_detail', pk=pk)
        if request.user.role not in ('MANAGER', 'ADMIN'):
            messages.error(request, 'Only MANAGER or ADMIN can revoke certificates.')
            return redirect('certificates:certificate_detail', pk=pk)
        reason = request.POST.get('reason', '').strip()
        if not reason:
            messages.error(request, 'A revocation reason is required.')
            return redirect('certificates:certificate_detail', pk=pk)
        cert.status = Certificate.Status.REVOKED
        cert.notes = f'REVOKED by {request.user.get_full_name()} on {timezone.now().date()}: {reason}\n\n{cert.notes}'
        cert.save()
        messages.warning(request, f'{cert.certificate_number} has been revoked.')
    return redirect('certificates:certificate_detail', pk=pk)


@login_required
@lab_staff_required
@module_required('certificates')
def certificate_regenerate_pdf(request, pk):
    """Trigger PDF regeneration manually."""
    cert = get_object_or_404(Certificate, pk=pk)
    if request.method == 'POST':
        from .tasks import generate_certificate_pdf
        generate_certificate_pdf.delay(cert.pk)
        messages.success(request, 'PDF regeneration queued.')
    return redirect('certificates:certificate_detail', pk=pk)


@login_required
@module_required('certificates')
def certificate_pdf(request, pk):
    """Serve the pre-generated PDF file."""
    cert = get_object_or_404(_scoped_certificate_qs(request.user), pk=pk)
    if cert.pdf_file:
        return FileResponse(cert.pdf_file.open(), content_type='application/pdf')
    raise Http404('PDF not yet generated')


@login_required
@module_required('certificates')
def certificate_print(request, pk):
    """Generate PDF on-demand and stream it — no Celery required."""
    import io
    import base64
    import qrcode
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    from django.core.files.base import ContentFile

    cert = get_object_or_404(
        _scoped_certificate_qs(
            request.user,
            Certificate.objects.select_related(
                'job__instrument__client',
                'job__method__certificate_template',
                'signed_by',
            ),
        ),
        pk=pk,
    )
    results = cert.job.results.select_related('unit', 'reference_standard').order_by('sequence')

    # Resolve certificate template: method-specific → default → None
    tmpl = (
        cert.job.method.certificate_template
        or CertificateTemplate.get_default()
    )

    # Encode logo as base64 so WeasyPrint doesn't need filesystem access
    logo_b64 = ''
    logo_mime = 'image/png'
    if tmpl and tmpl.logo:
        try:
            import mimetypes
            mime, _ = mimetypes.guess_type(tmpl.logo.name)
            logo_mime = mime or 'image/png'
            with tmpl.logo.open('rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode()
        except Exception:
            logo_b64 = ''

    # Build QR code as base64 so WeasyPrint doesn't need file access
    qr_url = request.build_absolute_uri(f'/certificates/{cert.pk}/verify/')
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    html_string = render_to_string('certificates/certificate_pdf.html', {
        'cert': cert,
        'results': results,
        'generated_at': timezone.now(),
        'qr_b64': qr_b64,
        'lab_settings': tmpl,
        'logo_b64': logo_b64,
        'logo_mime': logo_mime,
    })

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(
            string=html_string,
            base_url=request.build_absolute_uri('/'),
        ).write_pdf()
    except Exception as e:
        return HttpResponse(f'PDF generation failed: {e}', status=500, content_type='text/plain')

    # Optionally save the generated file back to the cert record
    if not cert.pdf_file:
        cert.pdf_file.save(
            f'certificate_{cert.certificate_number}.pdf',
            ContentFile(pdf_bytes),
            save=True,
        )

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    filename = f'certificate_{cert.certificate_number}.pdf'
    # inline → opens in browser for printing; use 'attachment' to force download
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


@module_required('certificates')
def certificate_verify(request, pk):
    """
    Public certificate verification page — no login required.
    Scanned from the QR code on the certificate sticker or PDF.
    """
    cert = get_object_or_404(
        Certificate.objects.select_related(
            'job__instrument__client',
            'job__method__certificate_template',
            'signed_by',
            'job__assigned_to',
        ),
        pk=pk,
    )
    tmpl = (
        cert.job.method.certificate_template
        or CertificateTemplate.get_default()
    )

    # Resolve which fields to show; fall back to sensible defaults
    active_fields = (tmpl.qr_info_fields if tmpl and tmpl.qr_info_fields else _QR_DEFAULTS)
    active_set = set(active_fields)

    instr = cert.job.instrument
    today = timezone.now().date()

    def _v(key, value):
        return (key, value) if key in active_set and value else None

    rows = list(filter(None, [
        _v('lab_name',               tmpl.lab_name if tmpl else 'CalLIMS'),
        _v('accreditation_number',   tmpl.accreditation_number if tmpl else ''),
        _v('accreditation_scope',    tmpl.accreditation_scope if tmpl else ''),
        _v('accreditation_text',     tmpl.accreditation_text if tmpl else ''),
        _v('cert_number',            cert.certificate_number),
        _v('calibration_date',       cert.issue_date.strftime('%d %b %Y') if cert.issue_date else ''),
        _v('expiry_date',            cert.expiry_date.strftime('%d %b %Y') if cert.expiry_date else ''),
        _v('instrument_description', instr.description),
        _v('instrument_asset_tag',   instr.asset_tag),
        _v('serial_number',          instr.serial_number),
        _v('manufacturer',           instr.manufacturer),
        _v('model_number',           instr.model_number),
        _v('client_name',            str(instr.client) if instr.client else ''),
        _v('method',                 str(cert.job.method)),
        _v('technician',             cert.job.assigned_to.get_full_name() if cert.job.assigned_to else ''),
        _v('signed_by',              cert.signed_by.get_full_name() if cert.signed_by else ''),
        _v('temperature',            f'{cert.job.temperature_c} °C' if cert.job.temperature_c else ''),
        _v('humidity',               f'{cert.job.humidity_pct} %RH' if cert.job.humidity_pct else ''),
    ]))

    # Label map: key → human label (preserve display order from template config)
    label_map = dict(QR_FIELD_CHOICES)
    info = [(label_map.get(k, k), v) for k, v in rows]

    is_valid = (
        cert.status in ('SIGNED', 'ISSUED')
        and (not cert.expiry_date or cert.expiry_date >= today)
    )
    is_expired = (
        cert.status in ('SIGNED', 'ISSUED')
        and cert.expiry_date
        and cert.expiry_date < today
    )
    is_revoked = cert.status == 'REVOKED'

    # Logo base64 for WeasyPrint-free public page
    logo_b64 = ''
    logo_mime = 'image/png'
    if tmpl and tmpl.logo:
        try:
            import base64, mimetypes
            mime, _ = mimetypes.guess_type(tmpl.logo.name)
            logo_mime = mime or 'image/png'
            with tmpl.logo.open('rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    return render(request, 'certificates/certificate_verify.html', {
        'cert': cert,
        'tmpl': tmpl,
        'info': info,
        'is_valid': is_valid,
        'is_expired': is_expired,
        'is_revoked': is_revoked,
        'logo_b64': logo_b64,
        'logo_mime': logo_mime,
    })


@login_required
@module_required('certificates')
def certificate_sticker_pdf(request, pk):
    """Generate and stream a standalone 75×50 mm sticker PDF for a certificate."""
    import io, base64, qrcode
    from django.template.loader import render_to_string
    from django.http import HttpResponse

    cert = get_object_or_404(
        _scoped_certificate_qs(
            request.user,
            Certificate.objects.select_related(
                'job__instrument__client',
                'job__method__certificate_template',
                'signed_by',
                'job__assigned_to',
            ),
        ),
        pk=pk,
    )
    tmpl = cert.job.method.certificate_template or CertificateTemplate.get_default()

    # QR code → verify URL
    qr_url = request.build_absolute_uri(f'/certificates/{cert.pk}/verify/')
    qr = qrcode.QRCode(box_size=4, border=2)
    qr.add_data(qr_url)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color='black', back_color='white')
    buf = io.BytesIO()
    qr_img.save(buf, format='PNG')
    qr_b64 = base64.b64encode(buf.getvalue()).decode()

    # Logo base64
    logo_b64, logo_mime = '', 'image/png'
    if tmpl and tmpl.logo:
        try:
            import mimetypes
            mime, _ = mimetypes.guess_type(tmpl.logo.name)
            logo_mime = mime or 'image/png'
            with tmpl.logo.open('rb') as f:
                logo_b64 = base64.b64encode(f.read()).decode()
        except Exception:
            pass

    today = timezone.now().date()
    html_string = render_to_string('certificates/certificate_sticker.html', {
        'cert': cert,
        'tmpl': tmpl,
        'qr_b64': qr_b64,
        'logo_b64': logo_b64,
        'logo_mime': logo_mime,
        'is_overdue': bool(cert.expiry_date and cert.expiry_date < today),
    })

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(
            string=html_string,
            base_url=request.build_absolute_uri('/'),
        ).write_pdf()
    except Exception as e:
        return HttpResponse(f'PDF generation failed: {e}', status=500, content_type='text/plain')

    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="sticker-{cert.certificate_number}.pdf"'
    return response

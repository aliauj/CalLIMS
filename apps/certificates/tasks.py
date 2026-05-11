import os
import io
import qrcode
from celery import shared_task
from django.utils import timezone
from django.template.loader import render_to_string
from django.core.files.base import ContentFile


@shared_task
def generate_certificate_pdf(certificate_id):
    """Generate PDF for a certificate using WeasyPrint."""
    from apps.certificates.models import Certificate

    try:
        cert = Certificate.objects.select_related(
            'job__instrument__client',
            'job__method',
            'signed_by',
        ).get(pk=certificate_id)
    except Certificate.DoesNotExist:
        return

    results = cert.job.results.select_related('unit', 'reference_standard').order_by('sequence')

    # Generate QR code pointing to certificate verification
    qr_data = f'/certificates/{cert.pk}/'
    qr_img = qrcode.make(qr_data)
    qr_buffer = io.BytesIO()
    qr_img.save(qr_buffer, format='PNG')
    qr_buffer.seek(0)
    cert.qr_code.save(
        f'cert_{cert.certificate_number}_qr.png',
        ContentFile(qr_buffer.read()),
        save=False,
    )

    # Render HTML
    html_content = render_to_string('certificates/certificate_pdf.html', {
        'cert': cert,
        'results': results,
        'generated_at': timezone.now(),
    })
    cert.html_snapshot = html_content
    cert.content_hash = cert.compute_hash()

    # Generate PDF with WeasyPrint
    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html_content, base_url='/').write_pdf()
        cert.pdf_file.save(
            f'certificate_{cert.certificate_number}.pdf',
            ContentFile(pdf_bytes),
            save=False,
        )
    except Exception as e:
        # WeasyPrint may need system libs; log and continue without PDF
        print(f'WeasyPrint error for cert {certificate_id}: {e}')

    cert.save()

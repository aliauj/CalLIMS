import hashlib
from django.db import models
from django.conf import settings


class CertificateTemplate(models.Model):
    """
    One row per certificate layout variant.
    Assign a template to a CalibrationMethod; the print view picks the right one
    automatically. Mark one as is_default=True as the fallback.
    """
    name = models.CharField(
        max_length=200,
        help_text='Internal name, e.g. "Mass & Force — UKAS" or "Temperature — Default"',
    )
    accreditation_scope = models.CharField(
        max_length=300,
        blank=True,
        help_text='Accreditation scope description, e.g. "Mass, Force, Torque — OIML R 111"',
    )
    is_default = models.BooleanField(
        default=False,
        help_text='Used when a calibration method has no specific template assigned',
    )

    # Header branding
    lab_name = models.CharField(max_length=150, default='CalLIMS')
    lab_subtitle = models.CharField(max_length=150, default='Calibration Laboratory', blank=True)
    logo = models.ImageField(
        upload_to='cert_logos/',
        null=True,
        blank=True,
        help_text='Accreditation / lab logo shown in the top-left of the certificate PDF',
    )
    accreditation_text = models.CharField(
        max_length=255,
        default='ISO/IEC 17025 Accredited',
        blank=True,
        help_text='Short text in top-right, e.g. "ISO/IEC 17025 — UKAS No. 1234"',
    )

    accreditation_number = models.CharField(
        max_length=100,
        blank=True,
        help_text='Accreditation body reference number, e.g. "UKAS No. 1234" or "ILAC-MRA"',
    )

    # Body content
    declaration_statement = models.TextField(
        blank=True,
        help_text='Formal declaration printed above the signature block.',
    )
    footer_text = models.CharField(
        max_length=500,
        blank=True,
        help_text='Optional extra line in the PDF footer.',
    )

    # Calibration sticker
    include_sticker = models.BooleanField(
        default=True,
        help_text='Append a small calibration sticker page (75×50 mm) to the certificate PDF.',
    )

    # QR verification page configuration
    qr_info_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='Fields to display on the public QR verification page.',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-is_default', 'name']
        verbose_name = 'Certificate Template'
        verbose_name_plural = 'Certificate Templates'

    def __str__(self):
        return f'{self.name}{"  [default]" if self.is_default else ""}'

    def save(self, *args, **kwargs):
        # Ensure only one default at a time
        if self.is_default:
            CertificateTemplate.objects.exclude(pk=self.pk).filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)

    @classmethod
    def get_default(cls):
        return (
            cls.objects.filter(is_default=True).first()
            or cls.objects.first()
        )


class Certificate(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        PENDING_SIGN = 'PENDING_SIGN', 'Pending Signature'
        SIGNED = 'SIGNED', 'Signed'
        ISSUED = 'ISSUED', 'Issued'
        SUPERSEDED = 'SUPERSEDED', 'Superseded'
        REVOKED = 'REVOKED', 'Revoked'

    certificate_number = models.CharField(max_length=50, unique=True)
    job = models.OneToOneField('workflows.CalibrationJob', on_delete=models.PROTECT, related_name='certificate')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    issue_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    pdf_file = models.FileField(upload_to='certificates/', null=True, blank=True)
    html_snapshot = models.TextField(blank=True)
    content_hash = models.CharField(max_length=64, blank=True, help_text='SHA-256 of signed content')
    signed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='signed_certificates',
    )
    signed_at = models.DateTimeField(null=True, blank=True)
    qr_code = models.ImageField(upload_to='qrcodes/', null=True, blank=True)
    superseded_by = models.ForeignKey(
        'self',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='supersedes',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'Certificate {self.certificate_number}'

    def compute_hash(self):
        content = f'{self.certificate_number}{self.job_id}{self.html_snapshot}'
        return hashlib.sha256(content.encode()).hexdigest()

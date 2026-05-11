from django.db import models
from django.conf import settings
from django.utils import timezone


class Nonconformance(models.Model):
    class Source(models.TextChoices):
        CALIBRATION = 'CALIBRATION', 'Calibration Result'
        CUSTOMER_COMPLAINT = 'CUSTOMER_COMPLAINT', 'Customer Complaint'
        INTERNAL_AUDIT = 'INTERNAL_AUDIT', 'Internal Audit'
        PROFICIENCY_TEST = 'PROFICIENCY_TEST', 'Proficiency Test'
        EQUIPMENT_FAILURE = 'EQUIPMENT_FAILURE', 'Equipment Failure'
        OTHER = 'OTHER', 'Other'

    class Severity(models.TextChoices):
        MINOR = 'MINOR', 'Minor'
        MAJOR = 'MAJOR', 'Major'
        CRITICAL = 'CRITICAL', 'Critical'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        INVESTIGATING = 'INVESTIGATING', 'Under Investigation'
        AWAITING_VERIFICATION = 'AWAITING_VERIFICATION', 'Awaiting Verification'
        CLOSED = 'CLOSED', 'Closed'

    class CustomerResolution(models.TextChoices):
        RETURN_RECALIBRATE = 'RETURN_RECALIBRATE', 'Return for Recalibration'
        USE_AS_IS = 'USE_AS_IS', 'Accept / Use As-Is'
        CORRECT_REISSUE = 'CORRECT_REISSUE', 'Correct Certificate & Reissue'

    class ComplaintChannel(models.TextChoices):
        EMAIL = 'EMAIL', 'Email'
        PHONE = 'PHONE', 'Phone'

    nc_number = models.CharField(max_length=20, unique=True, blank=True)
    title = models.CharField(max_length=255)
    description = models.TextField()
    source = models.CharField(max_length=30, choices=Source.choices, default=Source.CALIBRATION)
    severity = models.CharField(max_length=10, choices=Severity.choices, default=Severity.MINOR)
    status = models.CharField(max_length=25, choices=Status.choices, default=Status.OPEN)

    # Customer complaint metadata
    customer = models.ForeignKey(
        'clients.Client',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nonconformances',
        help_text='Customer who raised the complaint',
    )
    complaint_channel = models.CharField(
        max_length=10,
        choices=ComplaintChannel.choices,
        blank=True,
        help_text='How the complaint was received',
    )

    # Links to calibration artifacts
    certificate = models.ForeignKey(
        'certificates.Certificate',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nonconformances',
    )
    job = models.ForeignKey(
        'workflows.CalibrationJob',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='nonconformances',
    )
    # Technician who performed the calibration (denormalized from job.assigned_to)
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='technician_nonconformances',
    )

    detected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='detected_nonconformances',
    )
    detected_date = models.DateField(default=timezone.now)

    customer_resolution = models.CharField(
        max_length=20,
        choices=CustomerResolution.choices,
        blank=True,
        help_text='Resolution action taken — only applicable to Customer Complaint NCs',
    )

    root_cause = models.TextField(blank=True, help_text='Root cause identified during investigation')
    immediate_action = models.TextField(blank=True, help_text='Action taken immediately to contain the issue')

    target_closure_date = models.DateField(null=True, blank=True)
    closed_date = models.DateField(null=True, blank=True)
    closed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='closed_nonconformances',
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f'{self.nc_number} — {self.title}'

    def save(self, *args, **kwargs):
        if not self.nc_number:
            year = timezone.now().year
            count = Nonconformance.objects.filter(
                nc_number__startswith=f'NC-{year}-'
            ).count() + 1
            self.nc_number = f'NC-{year}-{count:04d}'
        super().save(*args, **kwargs)

    @property
    def all_capas_verified(self):
        actions = self.actions.all()
        return actions.exists() and all(a.status == CorrectiveAction.Status.VERIFIED for a in actions)

    @property
    def severity_color(self):
        return {'MINOR': 'yellow', 'MAJOR': 'orange', 'CRITICAL': 'red'}.get(self.severity, 'gray')


class CorrectiveAction(models.Model):
    class ActionType(models.TextChoices):
        CORRECTIVE = 'CORRECTIVE', 'Corrective Action'
        PREVENTIVE = 'PREVENTIVE', 'Preventive Action'

    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed — Pending Verification'
        VERIFIED = 'VERIFIED', 'Verified Effective'

    nonconformance = models.ForeignKey(
        Nonconformance,
        on_delete=models.CASCADE,
        related_name='actions',
    )
    action_type = models.CharField(max_length=15, choices=ActionType.choices, default=ActionType.CORRECTIVE)
    description = models.TextField()
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='assigned_capas',
    )
    due_date = models.DateField()
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.OPEN)

    completion_notes = models.TextField(blank=True)
    completed_date = models.DateField(null=True, blank=True)

    verified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='verified_capas',
    )
    verified_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['due_date']

    def __str__(self):
        return f'{self.get_action_type_display()} for {self.nonconformance.nc_number}'

    @property
    def is_overdue(self):
        return (
            self.status not in (self.Status.COMPLETED, self.Status.VERIFIED)
            and self.due_date < timezone.now().date()
        )

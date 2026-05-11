from django.db import models
from django.conf import settings
from django_fsm import FSMField, transition


class CalibrationMethod(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    version = models.CharField(max_length=20)
    is_active = models.BooleanField(default=True)
    document = models.FileField(upload_to='methods/', null=True, blank=True)
    coverage_factor = models.DecimalField(max_digits=5, decimal_places=2, default=2)
    confidence_level = models.DecimalField(max_digits=5, decimal_places=2, default=95.45)
    certificate_template = models.ForeignKey(
        'certificates.CertificateTemplate',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='methods',
        help_text='Certificate layout used for jobs under this method. Falls back to the default template.',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.code} v{self.version} — {self.name}'


class CalibrationJob(models.Model):
    class Status(models.TextChoices):
        RECEIVED = 'received', 'Received'
        ASSIGNED = 'assigned', 'Assigned'
        IN_PROGRESS = 'in_progress', 'In Progress'
        REVIEW = 'review', 'Under Review'
        APPROVED = 'approved', 'Approved'
        COMPLETED = 'completed', 'Completed'
        ON_HOLD = 'on_hold', 'On Hold'
        CANCELLED = 'cancelled', 'Cancelled'

    job_number = models.CharField(max_length=30, unique=True, db_index=True)
    instrument = models.ForeignKey('assets.Instrument', on_delete=models.PROTECT, related_name='calibration_jobs')
    method = models.ForeignKey(CalibrationMethod, on_delete=models.PROTECT, related_name='jobs')
    status = FSMField(default=Status.RECEIVED, choices=Status.choices, protected=True)
    priority = models.PositiveSmallIntegerField(default=2, help_text='1=High, 2=Normal, 3=Low')
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_jobs',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='reviewed_jobs',
    )
    received_date = models.DateField()
    due_date = models.DateField(null=True, blank=True)
    completed_date = models.DateField(null=True, blank=True)
    temperature_c = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    humidity_pct = models.DecimalField(max_digits=5, decimal_places=1, null=True, blank=True)
    notes = models.TextField(blank=True)
    rejection_notes = models.TextField(blank=True, help_text='Reason for rejection set by reviewer.')
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_jobs',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['status', 'due_date']),
            models.Index(fields=['assigned_to', 'status']),
        ]

    def __str__(self):
        return f'Job #{self.job_number}'

    @transition(field=status, source=Status.RECEIVED, target=Status.ASSIGNED)
    def assign(self):
        pass

    @transition(field=status, source=Status.ASSIGNED, target=Status.IN_PROGRESS)
    def start(self):
        pass

    @transition(field=status, source=Status.IN_PROGRESS, target=Status.REVIEW)
    def submit_for_review(self):
        pass

    @transition(field=status, source=Status.REVIEW, target=Status.APPROVED)
    def approve(self):
        pass

    @transition(field=status, source=Status.APPROVED, target=Status.COMPLETED)
    def complete(self):
        from django.utils import timezone
        self.completed_date = timezone.now().date()

    @transition(field=status, source=[Status.RECEIVED, Status.ASSIGNED, Status.IN_PROGRESS], target=Status.ON_HOLD)
    def hold(self):
        pass

    @transition(field=status, source=[Status.RECEIVED, Status.ON_HOLD], target=Status.CANCELLED)
    def cancel(self):
        pass

    @transition(field=status, source=Status.REVIEW, target=Status.IN_PROGRESS)
    def reject_review(self):
        pass


class CalibrationPoint(models.Model):
    """Predefined test points for a calibration method (e.g. 0 °C, 50 °C, 100 °C)."""
    method = models.ForeignKey(
        CalibrationMethod,
        on_delete=models.CASCADE,
        related_name='calibration_points',
    )
    label = models.CharField(max_length=100, help_text='e.g. Lower Range, Mid Point, Upper Range')
    nominal_value = models.DecimalField(max_digits=20, decimal_places=6)
    unit = models.ForeignKey(
        'standards.MeasurementUnit',
        on_delete=models.PROTECT,
        related_name='calibration_points',
    )
    tolerance_positive = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True,
        help_text='Maximum allowed positive error',
    )
    tolerance_negative = models.DecimalField(
        max_digits=20, decimal_places=6, null=True, blank=True,
        help_text='Maximum allowed negative error (store as positive number)',
    )
    num_readings = models.PositiveSmallIntegerField(default=3, help_text='Repeat readings per point')
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['method', 'sequence']
        unique_together = [('method', 'sequence')]

    def __str__(self):
        return f'{self.label} ({self.nominal_value} {self.unit.symbol})'


class MeasurementResult(models.Model):
    job = models.ForeignKey(CalibrationJob, on_delete=models.CASCADE, related_name='results')
    parameter = models.CharField(max_length=255)
    nominal_value = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    measured_value = models.DecimalField(max_digits=20, decimal_places=10)
    unit = models.ForeignKey('standards.MeasurementUnit', on_delete=models.PROTECT)
    error = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    standard_uncertainty = models.DecimalField(max_digits=20, decimal_places=10)
    coverage_factor_k = models.DecimalField(max_digits=5, decimal_places=2)
    expanded_uncertainty = models.DecimalField(max_digits=20, decimal_places=10)
    reference_standard = models.ForeignKey(
        'standards.ReferenceStandard',
        on_delete=models.PROTECT,
        related_name='used_in_results',
    )
    uncertainty_snapshot = models.JSONField(
        default=dict,
        help_text='Snapshot of calculation inputs for reproducibility',
    )
    pass_fail = models.BooleanField(null=True, blank=True)
    tolerance = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['job', 'sequence']
        unique_together = [['job', 'parameter', 'sequence']]

    def __str__(self):
        return f'{self.job} — {self.parameter}: {self.measured_value}'

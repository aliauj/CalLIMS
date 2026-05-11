from django.db import models
from django.conf import settings


class MeasurementUnit(models.Model):
    symbol = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    quantity_type = models.CharField(max_length=100, help_text='e.g. Length, Mass, Temperature')

    def __str__(self):
        return f'{self.symbol} ({self.name})'


class ReferenceStandard(models.Model):
    class Status(models.TextChoices):
        ACTIVE = 'ACTIVE', 'Active'
        DUE = 'DUE', 'Due for Calibration'
        EXPIRED = 'EXPIRED', 'Expired / Out of Cal'
        RETIRED = 'RETIRED', 'Retired'
        REPAIR = 'REPAIR', 'Under Repair'

    serial_number = models.CharField(max_length=100, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.ACTIVE)
    uncertainty_value = models.DecimalField(
        max_digits=20, decimal_places=10,
        help_text='Standard uncertainty (k=1)',
    )
    uncertainty_unit = models.ForeignKey(MeasurementUnit, on_delete=models.PROTECT, related_name='standards')
    calibration_date = models.DateField()
    calibration_due_date = models.DateField(db_index=True)
    calibration_interval_days = models.PositiveIntegerField(default=365)
    traceability_chain = models.JSONField(
        default=list,
        help_text='List of dicts: [{issuing_body, cert_number, date}] up to SI',
    )
    certificate_number = models.CharField(max_length=100, blank=True)
    issued_by = models.CharField(max_length=255, blank=True, help_text='External calibration lab name')
    location = models.CharField(max_length=255, blank=True)
    custodian = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='custodied_standards',
    )
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.serial_number} — {self.name}'

    @property
    def is_valid(self):
        from django.utils import timezone
        return (
            self.status == self.Status.ACTIVE
            and self.calibration_due_date >= timezone.now().date()
        )

    @property
    def primary_uncertainty(self):
        """Return the first uncertainty entry, falling back to the legacy field."""
        first = self.uncertainties.order_by('sequence').first()
        return first if first else None


class StandardUncertainty(models.Model):
    """One uncertainty entry for a reference standard (a standard may have many)."""
    standard = models.ForeignKey(
        ReferenceStandard,
        on_delete=models.CASCADE,
        related_name='uncertainties',
    )
    parameter = models.CharField(
        max_length=200,
        help_text='e.g. Temperature, DC Voltage 1 V range',
    )
    range_description = models.CharField(
        max_length=200,
        blank=True,
        help_text='e.g. 0 to 100 °C',
    )
    uncertainty_value = models.DecimalField(
        max_digits=20,
        decimal_places=10,
        help_text='Standard uncertainty u (k=1)',
    )
    coverage_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2,
        help_text='Coverage factor k',
    )
    unit = models.ForeignKey(
        MeasurementUnit,
        on_delete=models.PROTECT,
        related_name='standard_uncertainties',
    )
    confidence_level = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=95.45,
        help_text='Confidence level %',
    )
    notes = models.CharField(max_length=255, blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['standard', 'sequence']

    def __str__(self):
        return (
            f'{self.standard.serial_number} — {self.parameter}: '
            f'U=±{self.expanded_uncertainty} {self.unit.symbol} (k={self.coverage_factor})'
        )

    @property
    def expanded_uncertainty(self):
        return round(self.uncertainty_value * self.coverage_factor, 10)

from django.db import models
from django.conf import settings


class InstrumentCategory(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(
        max_length=5,
        unique=True,
        blank=True,
        help_text='2–5 letter uppercase prefix for auto-generated tags (e.g. ELE, TMP, MECH)',
    )
    description = models.TextField(blank=True)

    class Meta:
        verbose_name = 'Instrument Category'
        verbose_name_plural = 'Instrument Categories'
        ordering = ['name']

    def __str__(self):
        return self.name

    def next_tag(self):
        """Return the next available sequential tag for this category, e.g. ELE-0042."""
        prefix = self.code.upper()
        existing_nums = []
        for tag in Instrument.objects.filter(
            asset_tag__startswith=f'{prefix}-'
        ).values_list('asset_tag', flat=True):
            try:
                existing_nums.append(int(tag[len(prefix) + 1:]))
            except (ValueError, IndexError):
                pass
        next_num = (max(existing_nums) + 1) if existing_nums else 1
        return f'{prefix}-{next_num:04d}'


class Instrument(models.Model):
    class Status(models.TextChoices):
        DRAFT = 'DRAFT', 'Draft'
        ACTIVE = 'ACTIVE', 'Active / In Service'
        IN_CALIBRATION = 'IN_CALIBRATION', 'In Calibration'
        CALIBRATED = 'CALIBRATED', 'Calibrated'
        OUT_OF_SERVICE = 'OUT_OF_SERVICE', 'Out of Service'
        UNDER_REPAIR = 'UNDER_REPAIR', 'Under Repair'
        DISPOSED = 'DISPOSED', 'Disposed'

    asset_tag = models.CharField(max_length=50, unique=True, db_index=True)
    serial_number = models.CharField(max_length=100)
    description = models.CharField(max_length=255)
    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    category = models.ForeignKey(InstrumentCategory, on_delete=models.PROTECT, null=True, blank=True)
    client = models.ForeignKey(
        'clients.Client',
        on_delete=models.PROTECT,
        related_name='instruments',
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    location = models.CharField(max_length=255, blank=True)
    purchase_date = models.DateField(null=True, blank=True)
    last_calibration_date = models.DateField(null=True, blank=True)
    next_calibration_date = models.DateField(null=True, blank=True, db_index=True)
    calibration_interval_days = models.PositiveIntegerField(default=365)
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_instruments',
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Instrument / Gauge'
        verbose_name_plural = 'Instruments & Gauges'
        ordering = ['asset_tag']
        indexes = [
            models.Index(fields=['status', 'next_calibration_date']),
            models.Index(fields=['client', 'status']),
        ]

    def __str__(self):
        return f'{self.asset_tag} — {self.description}'

    @property
    def is_overdue(self):
        from django.utils import timezone
        if self.next_calibration_date:
            return self.next_calibration_date < timezone.now().date()
        return False

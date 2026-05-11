import random
import string
from django.db import models
from django.conf import settings
from django.utils import timezone


def _generate_rfq_number():
    year = timezone.now().year
    suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    return f'RFQ-{year}-{suffix}'


class RFQ(models.Model):
    """Request For Quotation submitted by sales for lab manager review."""

    class Status(models.TextChoices):
        PENDING = 'PENDING', 'Pending Review'
        ACCEPTED = 'ACCEPTED', 'Accepted'
        REJECTED = 'REJECTED', 'Rejected'
        READY_FOR_JOBS = 'READY_FOR_JOBS', 'Ready for Job Creation'
        CLOSED = 'CLOSED', 'Closed'

    rfq_number = models.CharField(max_length=30, unique=True, db_index=True, default=_generate_rfq_number)
    client = models.ForeignKey('clients.Client', on_delete=models.PROTECT, related_name='rfqs')
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    priority = models.PositiveSmallIntegerField(default=2, help_text='1=High, 2=Normal, 3=Low')

    received_date = models.DateField(default=timezone.now)
    required_by = models.DateField(null=True, blank=True)

    contact_person = models.CharField(max_length=255, blank=True)
    contact_email = models.EmailField(blank=True)
    contact_phone = models.CharField(max_length=50, blank=True)

    scope_description = models.TextField(help_text='Service scope as requested by the customer')
    notes = models.TextField(blank=True)

    instruments = models.ManyToManyField(
        'assets.Instrument',
        blank=True,
        related_name='rfqs',
        help_text='Instruments registered against this RFQ after acceptance',
    )

    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='created_rfqs',
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='reviewed_rfqs',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(blank=True)
    sent_to_lab_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'RFQ'
        verbose_name_plural = 'RFQs'
        indexes = [
            models.Index(fields=['status', 'received_date']),
        ]

    def __str__(self):
        return f'RFQ {self.rfq_number} — {self.client.name}'

    @property
    def is_pending(self):
        return self.status == self.Status.PENDING

    @property
    def is_accepted(self):
        return self.status == self.Status.ACCEPTED

    @property
    def is_rejected(self):
        return self.status == self.Status.REJECTED

    @property
    def is_ready_for_jobs(self):
        return self.status == self.Status.READY_FOR_JOBS


class RFQItem(models.Model):
    """A draft line on the RFQ — what the customer asked for, before instruments are registered."""

    rfq = models.ForeignKey(RFQ, on_delete=models.CASCADE, related_name='items')
    sequence = models.PositiveSmallIntegerField(default=0)
    description = models.CharField(max_length=255, help_text='e.g. "Digital multimeter Fluke 87V"')
    manufacturer = models.CharField(max_length=150, blank=True)
    model_number = models.CharField(max_length=100, blank=True)
    serial_number = models.CharField(max_length=100, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    notes = models.CharField(max_length=255, blank=True)
    registered_instrument = models.ForeignKey(
        'assets.Instrument',
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='rfq_line_items',
    )

    class Meta:
        ordering = ['sequence', 'pk']

    def __str__(self):
        return f'{self.description} (×{self.quantity})'

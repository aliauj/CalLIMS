import math

from django.conf import settings
from django.db import models


class PTProvider(models.Model):
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50, unique=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    accreditation_body = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.code} — {self.name}'


class PTScheme(models.Model):
    class Status(models.TextChoices):
        OPEN = 'OPEN', 'Open for Registration'
        ACTIVE = 'ACTIVE', 'Sample Dispatched'
        RESULTS_DUE = 'RESULTS_DUE', 'Results Due'
        EVALUATING = 'EVALUATING', 'Under Evaluation'
        CLOSED = 'CLOSED', 'Closed'

    provider = models.ForeignKey(
        PTProvider,
        on_delete=models.PROTECT,
        related_name='schemes',
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=50)
    measurand = models.CharField(max_length=200)
    unit_symbol = models.CharField(max_length=20, blank=True)
    year = models.PositiveSmallIntegerField()
    round_number = models.PositiveSmallIntegerField(default=1)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    sample_dispatch_date = models.DateField(null=True, blank=True)
    results_due_date = models.DateField(null=True, blank=True)
    assigned_value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    assigned_std_dev = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
        help_text='σ_pt for z-score',
    )
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-year', '-round_number']
        unique_together = [('provider', 'code', 'year', 'round_number')]

    def __str__(self):
        return f'{self.code} {self.year}/R{self.round_number} — {self.name}'


class PTParticipation(models.Model):
    class ParticipationStatus(models.TextChoices):
        REGISTERED = 'REGISTERED', 'Registered'
        SAMPLE_RECEIVED = 'SAMPLE_RECEIVED', 'Sample Received'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        RESULTS_SUBMITTED = 'RESULTS_SUBMITTED', 'Results Submitted'
        EVALUATED = 'EVALUATED', 'Evaluated'

    class Performance(models.TextChoices):
        SATISFACTORY = 'SATISFACTORY', 'Satisfactory (|z|≤2)'
        QUESTIONABLE = 'QUESTIONABLE', 'Questionable (2<|z|≤3)'
        UNSATISFACTORY = 'UNSATISFACTORY', 'Unsatisfactory (|z|>3)'
        PENDING = 'PENDING', 'Pending'

    scheme = models.ForeignKey(
        PTScheme,
        on_delete=models.PROTECT,
        related_name='participations',
    )
    technician = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pt_participations',
        null=True,
        blank=True,
    )
    method = models.ForeignKey(
        'workflows.CalibrationMethod',
        on_delete=models.PROTECT,
        related_name='pt_participations',
        null=True,
        blank=True,
    )
    status = models.CharField(
        max_length=20,
        choices=ParticipationStatus.choices,
        default=ParticipationStatus.REGISTERED,
    )
    submitted_value = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    expanded_uncertainty = models.DecimalField(
        max_digits=18,
        decimal_places=6,
        null=True,
        blank=True,
    )
    coverage_factor = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2,
    )
    submission_date = models.DateField(null=True, blank=True)
    z_score = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    en_number = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        null=True,
        blank=True,
    )
    performance = models.CharField(
        max_length=20,
        choices=Performance.choices,
        default=Performance.PENDING,
    )
    notes = models.TextField(blank=True)
    corrective_action = models.TextField(blank=True)
    corrective_action_date = models.DateField(null=True, blank=True)
    corrective_action_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='pt_corrective_actions',
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        unique_together = [('scheme', 'technician')]

    def __str__(self):
        return f'{self.scheme} — {self.technician}'

    def calculate_scores(self):
        if (
            self.submitted_value is not None
            and self.scheme.assigned_value is not None
            and self.scheme.assigned_std_dev is not None
            and float(self.scheme.assigned_std_dev) != 0
        ):
            z = (
                float(self.submitted_value) - float(self.scheme.assigned_value)
            ) / float(self.scheme.assigned_std_dev)
            self.z_score = round(z, 4)
            if abs(z) <= 2:
                self.performance = self.Performance.SATISFACTORY
            elif abs(z) <= 3:
                self.performance = self.Performance.QUESTIONABLE
            else:
                self.performance = self.Performance.UNSATISFACTORY

        # En number
        if (
            self.submitted_value is not None
            and self.scheme.assigned_value is not None
            and self.expanded_uncertainty is not None
        ):
            u_ref = float(self.scheme.assigned_std_dev or 0) * 2
            u_lab = float(self.expanded_uncertainty)
            denom_sq = u_lab ** 2 + u_ref ** 2
            if denom_sq > 0:
                en = (
                    float(self.submitted_value) - float(self.scheme.assigned_value)
                ) / math.sqrt(denom_sq)
                self.en_number = round(en, 4)

from django.db import models


class UncertaintyContributor(models.Model):
    class ContributorType(models.TextChoices):
        REFERENCE_STD = 'REF_STD', 'Reference Standard'
        RESOLUTION = 'RESOLUTION', 'Instrument Resolution'
        REPEATABILITY = 'REPEATABILITY', 'Repeatability / Reproducibility'
        DRIFT = 'DRIFT', 'Instrument Drift'
        ENVIRONMENTAL = 'ENV', 'Environmental'
        CUSTOM = 'CUSTOM', 'Custom'

    class Distribution(models.TextChoices):
        NORMAL = 'NORMAL', 'Normal'
        RECTANGULAR = 'RECTANGULAR', 'Rectangular'
        TRIANGULAR = 'TRIANGULAR', 'Triangular'
        U_SHAPED = 'U_SHAPED', 'U-Shaped'

    method = models.ForeignKey('workflows.CalibrationMethod', on_delete=models.CASCADE, related_name='contributors')
    name = models.CharField(max_length=100)
    contributor_type = models.CharField(max_length=20, choices=ContributorType.choices)
    distribution = models.CharField(max_length=20, choices=Distribution.choices, default=Distribution.NORMAL)
    value = models.DecimalField(max_digits=20, decimal_places=10, null=True, blank=True)
    divisor = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    sensitivity_coefficient = models.DecimalField(max_digits=10, decimal_places=4, default=1)
    description = models.TextField(blank=True)
    sequence = models.PositiveSmallIntegerField(default=1)

    class Meta:
        ordering = ['method', 'sequence']

    def __str__(self):
        return f'{self.method.code} — {self.name}'

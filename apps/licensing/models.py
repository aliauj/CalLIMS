import json
from django.db import models
from django.conf import settings
from django.utils import timezone


class LabSettings(models.Model):
    """Singleton — one row per installation, holds lab branding and contact info."""
    lab_name = models.CharField(max_length=200, default='CalLIMS')
    lab_subtitle = models.CharField(max_length=200, default='Calibration Laboratory', blank=True)
    logo = models.ImageField(upload_to='lab_branding/', null=True, blank=True)
    address = models.TextField(blank=True)
    phone = models.CharField(max_length=50, blank=True)
    email = models.EmailField(blank=True)
    website = models.CharField(max_length=200, blank=True)
    accreditation_body = models.CharField(max_length=200, blank=True)
    accreditation_number = models.CharField(max_length=100, blank=True)
    footer_text = models.TextField(blank=True, help_text='Printed at the bottom of PDFs and certificates.')
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Lab Settings'
        verbose_name_plural = 'Lab Settings'

    def __str__(self):
        return self.lab_name

    def save(self, *args, **kwargs):
        self.pk = 1  # enforce singleton
        super().save(*args, **kwargs)

    @classmethod
    def get(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'lab_name': 'CalLIMS'})
        return obj


class LicenseRecord(models.Model):
    """The activated license for this CalLIMS installation."""

    class Tier(models.TextChoices):
        STARTER = 'STARTER', 'Starter'
        PROFESSIONAL = 'PROFESSIONAL', 'Professional'
        ENTERPRISE = 'ENTERPRISE', 'Enterprise'

    license_key = models.TextField(unique=True)
    license_id = models.CharField(max_length=50, blank=True, db_index=True)
    issued_to = models.CharField(max_length=200)
    issued_to_email = models.EmailField(blank=True)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.STARTER)
    max_users = models.IntegerField(default=5, help_text='-1 = unlimited')
    valid_from = models.DateField()
    valid_until = models.DateField()
    modules_json = models.TextField(default='[]', help_text='JSON list of enabled module names.')
    activated_at = models.DateTimeField(auto_now_add=True)
    activated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='activated_licenses',
    )
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True)

    class Meta:
        ordering = ['-activated_at']

    def __str__(self):
        return f'{self.license_id} — {self.issued_to} ({self.tier})'

    # ── Computed properties ──────────────────────────────────────

    @property
    def enabled_modules(self):
        try:
            return json.loads(self.modules_json)
        except Exception:
            return []

    def is_module_enabled(self, module_name):
        return module_name in self.enabled_modules

    @property
    def is_expired(self):
        return self.valid_until < timezone.now().date()

    @property
    def is_valid(self):
        today = timezone.now().date()
        return self.is_active and self.valid_from <= today <= self.valid_until

    @property
    def days_remaining(self):
        delta = self.valid_until - timezone.now().date()
        return delta.days

    @property
    def current_user_count(self):
        from apps.users.models import User
        return User.objects.filter(is_active=True).count()

    @property
    def users_remaining(self):
        if self.max_users < 0:
            return None  # unlimited
        return max(0, self.max_users - self.current_user_count)

    @property
    def user_limit_reached(self):
        if self.max_users < 0:
            return False
        return self.current_user_count >= self.max_users

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('Email is required')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('role', User.Role.ADMIN)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        MANAGER = 'MANAGER', 'Lab Manager'
        TECHNICIAN = 'TECHNICIAN', 'Technician'
        REVIEWER = 'REVIEWER', 'Technical Reviewer'
        AUDITOR = 'AUDITOR', 'Quality Auditor'
        SALES = 'SALES', 'Sales Representative'
        CLIENT = 'CLIENT', 'Client'

    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.TECHNICIAN)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(default=timezone.now)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    failed_login_attempts = models.PositiveSmallIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    signature_image = models.ImageField(upload_to='signatures/', null=True, blank=True)

    objects = UserManager()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name', 'last_name']

    class Meta:
        verbose_name = 'user'
        verbose_name_plural = 'users'
        ordering = ['last_name', 'first_name']

    def __str__(self):
        return f'{self.get_full_name()} <{self.email}>'

    def get_full_name(self):
        return f'{self.first_name} {self.last_name}'.strip()

    def get_role_display(self):
        for val, label in self.Role.choices:
            if val == self.role:
                return label
        try:
            return CustomRole.objects.get(code=self.role).name
        except CustomRole.DoesNotExist:
            return self.role

    @property
    def is_client(self):
        return self.role == self.Role.CLIENT

    @property
    def is_lab_staff(self):
        if self.role in [self.Role.ADMIN, self.Role.MANAGER, self.Role.TECHNICIAN, self.Role.REVIEWER, self.Role.AUDITOR, self.Role.SALES]:
            return True
        try:
            return CustomRole.objects.get(code=self.role).is_lab_staff
        except CustomRole.DoesNotExist:
            return False

    def is_account_locked(self):
        if self.locked_until and timezone.now() < self.locked_until:
            return True
        return False


class CustomRole(models.Model):
    code = models.CharField(max_length=20, unique=True, help_text='All caps, letters/underscores only. e.g. QUALITY_ENGINEER')
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_lab_staff = models.BooleanField(default=True, help_text='Grants access to lab nav (jobs, instruments, etc.)')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f'{self.name} ({self.code})'

    def save(self, *args, **kwargs):
        self.code = self.code.upper().replace(' ', '_')
        super().save(*args, **kwargs)

    @property
    def user_count(self):
        return User.objects.filter(role=self.code).count()


class AppSection(models.TextChoices):
    INSTRUMENTS    = 'instruments', 'Instruments & Gauges'
    CALIBRATION    = 'jobs',        'Calibration Jobs'
    RESULTS        = 'results',     'Measurement Results'
    CERTIFICATES   = 'certificates','Certificates'
    STANDARDS      = 'standards',   'Reference Standards'
    CLIENTS        = 'clients',     'Clients'
    USERS          = 'users',       'User Management'
    AUDIT_LOG      = 'audit',       'Audit Log'
    PROFICIENCY    = 'proficiency', 'Proficiency Testing'
    NONCONFORMANCE = 'nc',          'Nonconformances'
    ADMINISTRATION = 'admin_panel', 'Administration / Settings'


class UserModulePermission(models.Model):
    user      = models.ForeignKey('User', on_delete=models.CASCADE, related_name='module_permissions')
    section   = models.CharField(max_length=20, choices=AppSection.choices)
    can_view  = models.BooleanField(default=False)
    can_add   = models.BooleanField(default=False)
    can_modify= models.BooleanField(default=False)
    can_delete= models.BooleanField(default=False)

    class Meta:
        unique_together = [('user', 'section')]
        ordering = ['section']

    def __str__(self):
        return f'{self.user} / {self.section}'


class TechnicianMethodAuthorization(models.Model):
    class Status(models.TextChoices):
        AUTHORIZED = 'AUTHORIZED', 'Authorized'
        PENDING    = 'PENDING',    'Pending Evaluation'
        SUSPENDED  = 'SUSPENDED',  'Suspended'
        REVOKED    = 'REVOKED',    'Revoked'

    technician   = models.ForeignKey('User', on_delete=models.CASCADE, related_name='method_authorizations')
    method       = models.ForeignKey('workflows.CalibrationMethod', on_delete=models.CASCADE, related_name='authorized_technicians')
    status       = models.CharField(max_length=15, choices=Status.choices, default=Status.PENDING)
    authorized_by= models.ForeignKey('User', on_delete=models.SET_NULL, null=True, blank=True, related_name='granted_authorizations')
    training_date   = models.DateField(null=True, blank=True)
    evaluation_date = models.DateField(null=True, blank=True)
    expiry_date     = models.DateField(null=True, blank=True, help_text='Leave blank for no expiry.')
    certificate_ref = models.CharField(max_length=100, blank=True)
    notes           = models.TextField(blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('technician', 'method')]
        ordering = ['technician__last_name', 'method__code']

    def __str__(self):
        return f'{self.technician.get_full_name()} — {self.method.code} [{self.status}]'

    @property
    def is_valid(self):
        from django.utils import timezone
        if self.status != 'AUTHORIZED':
            return False
        if self.expiry_date and self.expiry_date < timezone.now().date():
            return False
        return True

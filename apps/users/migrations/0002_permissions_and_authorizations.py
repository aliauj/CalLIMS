from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('users', '0001_initial'),
        ('workflows', '0005_calibrationjob_rejection_notes'),
    ]

    operations = [
        migrations.CreateModel(
            name='UserModulePermission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('section', models.CharField(
                    max_length=20,
                    choices=[
                        ('instruments', 'Instruments & Gauges'),
                        ('jobs', 'Calibration Jobs'),
                        ('results', 'Measurement Results'),
                        ('certificates', 'Certificates'),
                        ('standards', 'Reference Standards'),
                        ('clients', 'Clients'),
                        ('users', 'User Management'),
                        ('audit', 'Audit Log'),
                        ('proficiency', 'Proficiency Testing'),
                        ('nc', 'Nonconformances'),
                        ('admin_panel', 'Administration / Settings'),
                    ],
                )),
                ('can_view', models.BooleanField(default=False)),
                ('can_add', models.BooleanField(default=False)),
                ('can_modify', models.BooleanField(default=False)),
                ('can_delete', models.BooleanField(default=False)),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='module_permissions',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['section'],
                'unique_together': {('user', 'section')},
            },
        ),
        migrations.CreateModel(
            name='TechnicianMethodAuthorization',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(
                    max_length=15,
                    choices=[
                        ('AUTHORIZED', 'Authorized'),
                        ('PENDING', 'Pending Evaluation'),
                        ('SUSPENDED', 'Suspended'),
                        ('REVOKED', 'Revoked'),
                    ],
                    default='PENDING',
                )),
                ('training_date', models.DateField(blank=True, null=True)),
                ('evaluation_date', models.DateField(blank=True, null=True)),
                ('expiry_date', models.DateField(blank=True, null=True, help_text='Leave blank for no expiry.')),
                ('certificate_ref', models.CharField(blank=True, max_length=100)),
                ('notes', models.TextField(blank=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('technician', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='method_authorizations',
                    to=settings.AUTH_USER_MODEL,
                )),
                ('method', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='authorized_technicians',
                    to='workflows.calibrationmethod',
                )),
                ('authorized_by', models.ForeignKey(
                    blank=True,
                    null=True,
                    on_delete=django.db.models.deletion.SET_NULL,
                    related_name='granted_authorizations',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['technician__last_name', 'method__code'],
                'unique_together': {('technician', 'method')},
            },
        ),
    ]

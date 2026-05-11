from django.db import migrations, models
import django.utils.timezone


def set_default_name(apps, schema_editor):
    CertificateTemplate = apps.get_model('certificates', 'CertificateTemplate')
    CertificateTemplate.objects.filter(pk=1).update(name='Default', is_default=True)


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0004_alter_certificatetemplate_declaration_statement'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificatetemplate',
            name='name',
            field=models.CharField(
                default='Default',
                max_length=200,
                help_text='Internal name, e.g. "Mass & Force — UKAS"',
            ),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='certificatetemplate',
            name='accreditation_scope',
            field=models.CharField(
                blank=True,
                max_length=300,
                help_text='Accreditation scope, e.g. "Mass, Force, Torque — OIML R 111"',
            ),
        ),
        migrations.AddField(
            model_name='certificatetemplate',
            name='is_default',
            field=models.BooleanField(
                default=False,
                help_text='Used when a calibration method has no specific template assigned',
            ),
        ),
        migrations.AddField(
            model_name='certificatetemplate',
            name='logo',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to='cert_logos/',
                help_text='Accreditation / lab logo shown in the top-left of the certificate PDF',
            ),
        ),
        migrations.AddField(
            model_name='certificatetemplate',
            name='created_at',
            field=models.DateTimeField(auto_now_add=True, default=django.utils.timezone.now),
            preserve_default=False,
        ),
        migrations.AlterField(
            model_name='certificatetemplate',
            name='lab_subtitle',
            field=models.CharField(blank=True, default='Calibration Laboratory', max_length=150),
        ),
        migrations.AlterModelOptions(
            name='certificatetemplate',
            options={
                'ordering': ['-is_default', 'name'],
                'verbose_name': 'Certificate Template',
                'verbose_name_plural': 'Certificate Templates',
            },
        ),
        migrations.RunPython(set_default_name, migrations.RunPython.noop),
    ]

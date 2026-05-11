from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0002_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='CertificateTemplate',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('lab_name', models.CharField(default='CalLIMS', max_length=150)),
                ('lab_subtitle', models.CharField(default='Calibration Laboratory', max_length=150)),
                ('accreditation_text', models.CharField(blank=True, default='ISO/IEC 17025 Accredited', max_length=255)),
                ('declaration_statement', models.TextField(blank=True, help_text='Formal declaration printed on every certificate above the signature block.')),
                ('footer_text', models.CharField(blank=True, help_text='Optional extra line in the PDF footer.', max_length=500)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Certificate Template Settings',
            },
        ),
    ]

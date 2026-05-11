from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0005_certificate_template_multi_logo'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificatetemplate',
            name='accreditation_number',
            field=models.CharField(
                blank=True,
                max_length=100,
                help_text='Accreditation body reference number, e.g. "UKAS No. 1234" or "ILAC-MRA"',
            ),
        ),
        migrations.AddField(
            model_name='certificatetemplate',
            name='qr_info_fields',
            field=models.JSONField(
                default=list,
                blank=True,
                help_text='Fields to display on the public QR verification page.',
            ),
        ),
    ]

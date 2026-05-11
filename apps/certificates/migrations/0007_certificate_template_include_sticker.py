from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0006_certificate_template_qr_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='certificatetemplate',
            name='include_sticker',
            field=models.BooleanField(
                default=True,
                help_text='Append a small calibration sticker page (75×50 mm) to the certificate PDF.',
            ),
        ),
    ]

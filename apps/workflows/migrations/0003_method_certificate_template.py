import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('certificates', '0005_certificate_template_multi_logo'),
        ('workflows', '0002_calibrationpoint'),
    ]

    operations = [
        migrations.AddField(
            model_name='calibrationmethod',
            name='certificate_template',
            field=models.ForeignKey(
                blank=True,
                help_text='Certificate layout for jobs using this method. Falls back to the default template.',
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='methods',
                to='certificates.certificatetemplate',
            ),
        ),
    ]

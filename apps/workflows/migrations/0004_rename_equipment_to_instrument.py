import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0004_rename_to_instrument'),
        ('workflows', '0003_method_certificate_template'),
    ]

    operations = [
        migrations.RenameField(
            model_name='calibrationjob',
            old_name='equipment',
            new_name='instrument',
        ),
        migrations.AlterField(
            model_name='calibrationjob',
            name='instrument',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='calibration_jobs',
                to='assets.instrument',
            ),
        ),
    ]

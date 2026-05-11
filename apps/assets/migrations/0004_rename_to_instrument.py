import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0003_initial'),
        ('clients', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # Rename the category model first (no FKs to fix — category FK is on Equipment)
        migrations.RenameModel(
            old_name='EquipmentCategory',
            new_name='InstrumentCategory',
        ),
        # Rename the main model
        migrations.RenameModel(
            old_name='Equipment',
            new_name='Instrument',
        ),
        # Update related_name on the client FK (DB-transparent, recorded for state)
        migrations.AlterField(
            model_name='instrument',
            name='client',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='instruments',
                to='clients.client',
            ),
        ),
        # Update related_name on created_by FK
        migrations.AlterField(
            model_name='instrument',
            name='created_by',
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name='created_instruments',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        # Update verbose names
        migrations.AlterModelOptions(
            name='instrumentcategory',
            options={
                'ordering': ['name'],
                'verbose_name': 'Instrument Category',
                'verbose_name_plural': 'Instrument Categories',
            },
        ),
        migrations.AlterModelOptions(
            name='instrument',
            options={
                'ordering': ['asset_tag'],
                'verbose_name': 'Instrument / Gauge',
                'verbose_name_plural': 'Instruments & Gauges',
            },
        ),
    ]

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('workflows', '0004_rename_equipment_to_instrument'),
    ]

    operations = [
        migrations.AddField(
            model_name='calibrationjob',
            name='rejection_notes',
            field=models.TextField(blank=True, help_text='Reason for rejection set by reviewer.'),
        ),
    ]

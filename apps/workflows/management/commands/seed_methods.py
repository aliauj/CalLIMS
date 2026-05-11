from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed initial calibration methods'

    def handle(self, *args, **options):
        from apps.workflows.models import CalibrationMethod
        methods = [
            ('CAL-TEMP-001', 'Temperature Calibration (Contact)', '1.0', 2.0, 95.45),
            ('CAL-PRESS-001', 'Pressure Gauge Calibration', '1.0', 2.0, 95.45),
            ('CAL-MASS-001', 'Mass / Weight Calibration', '1.0', 2.0, 95.45),
            ('CAL-DIM-001', 'Dimensional Calibration', '1.0', 2.0, 95.45),
            ('CAL-ELEC-001', 'Electrical Multimeter Calibration', '1.0', 2.0, 95.45),
            ('CAL-FORCE-001', 'Force / Torque Calibration', '1.0', 2.0, 95.45),
            ('CAL-HUM-001', 'Humidity Calibration', '1.0', 2.0, 95.45),
            ('CAL-FLOW-001', 'Flow Meter Calibration', '1.0', 2.0, 95.45),
        ]
        created = 0
        for code, name, version, k, cl in methods:
            _, c = CalibrationMethod.objects.get_or_create(
                code=code,
                defaults={
                    'name': name,
                    'version': version,
                    'coverage_factor': k,
                    'confidence_level': cl,
                    'is_active': True,
                },
            )
            if c:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} calibration methods.'))

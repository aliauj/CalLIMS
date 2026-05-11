from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Seed initial measurement units'

    def handle(self, *args, **options):
        from apps.standards.models import MeasurementUnit
        units = [
            ('mm', 'Millimetre', 'Length'),
            ('m', 'Metre', 'Length'),
            ('kg', 'Kilogram', 'Mass'),
            ('g', 'Gram', 'Mass'),
            ('°C', 'Degree Celsius', 'Temperature'),
            ('K', 'Kelvin', 'Temperature'),
            ('Pa', 'Pascal', 'Pressure'),
            ('kPa', 'Kilopascal', 'Pressure'),
            ('MPa', 'Megapascal', 'Pressure'),
            ('bar', 'Bar', 'Pressure'),
            ('mbar', 'Millibar', 'Pressure'),
            ('N', 'Newton', 'Force'),
            ('kN', 'Kilonewton', 'Force'),
            ('Ω', 'Ohm', 'Electrical Resistance'),
            ('V', 'Volt', 'Electrical Voltage'),
            ('A', 'Ampere', 'Electrical Current'),
            ('mA', 'Milliampere', 'Electrical Current'),
            ('Hz', 'Hertz', 'Frequency'),
            ('rpm', 'Revolutions per Minute', 'Rotational Speed'),
            ('%RH', 'Percent Relative Humidity', 'Humidity'),
            ('ppm', 'Parts per Million', 'Concentration'),
            ('lux', 'Lux', 'Illuminance'),
            ('dB', 'Decibel', 'Sound Level'),
            ('N·m', 'Newton Metre', 'Torque'),
        ]
        created = 0
        for symbol, name, qty in units:
            _, c = MeasurementUnit.objects.get_or_create(
                symbol=symbol,
                defaults={'name': name, 'quantity_type': qty},
            )
            if c:
                created += 1
        self.stdout.write(self.style.SUCCESS(f'Created {created} measurement units.'))

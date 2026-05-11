import random
import string
from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.licensing.services import generate_license_key, TIER_DEFAULTS, ALL_MODULES


class Command(BaseCommand):
    help = 'Generate a signed CalLIMS license key for a customer.'

    def add_arguments(self, parser):
        parser.add_argument('--issued-to', required=True, help='Customer lab name')
        parser.add_argument('--email', default='', help='Customer contact email')
        parser.add_argument('--tier', default='PROFESSIONAL',
                            choices=['STARTER', 'PROFESSIONAL', 'ENTERPRISE'])
        parser.add_argument('--max-users', type=int, default=None,
                            help='Override tier default user limit (-1 = unlimited)')
        parser.add_argument('--days', type=int, default=365,
                            help='License validity period in days (default: 365)')
        parser.add_argument('--modules', default=None,
                            help='Comma-separated module overrides, e.g. instruments,jobs,certificates')
        parser.add_argument('--license-id', default=None,
                            help='Custom license ID (auto-generated if omitted)')

    def handle(self, *args, **options):
        tier = options['tier']
        defaults = TIER_DEFAULTS[tier]

        valid_from = date.today()
        valid_until = valid_from + timedelta(days=options['days'])

        max_users = options['max_users'] if options['max_users'] is not None else defaults['max_users']

        if options['modules']:
            modules = [m.strip() for m in options['modules'].split(',') if m.strip() in ALL_MODULES]
        else:
            modules = defaults['modules']

        license_id = options['license_id'] or (
            f"LIC-{valid_from.year}-{''.join(random.choices(string.digits, k=6))}"
        )

        payload = {
            'license_id': license_id,
            'issued_to': options['issued_to'],
            'issued_to_email': options['email'],
            'tier': tier,
            'max_users': max_users,
            'valid_from': str(valid_from),
            'valid_until': str(valid_until),
            'modules': modules,
            'issued': str(date.today()),
        }

        key = generate_license_key(payload)

        w = 64
        self.stdout.write('\n' + '=' * w)
        self.stdout.write(self.style.SUCCESS('  CalLIMS LICENSE KEY GENERATED'))
        self.stdout.write('=' * w)
        self.stdout.write(f'  License ID  : {license_id}')
        self.stdout.write(f'  Issued to   : {options["issued_to"]}')
        self.stdout.write(f'  Email       : {options["email"] or "—"}')
        self.stdout.write(f'  Tier        : {tier}')
        self.stdout.write(f'  Max users   : {"Unlimited" if max_users < 0 else max_users}')
        self.stdout.write(f'  Valid from  : {valid_from}')
        self.stdout.write(f'  Valid until : {valid_until}  ({options["days"]} days)')
        self.stdout.write(f'  Modules     : {", ".join(modules)}')
        self.stdout.write('=' * w)
        self.stdout.write(self.style.WARNING('\n  LICENSE KEY (send this to the customer):\n'))
        # Print in 60-char chunks for readability
        for i in range(0, len(key), 60):
            self.stdout.write('  ' + key[i:i+60])
        self.stdout.write('\n' + '=' * w + '\n')

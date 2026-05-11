from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

User = get_user_model()


class Command(BaseCommand):
    help = 'Create initial admin user for CalLIMS'

    def handle(self, *args, **options):
        if User.objects.filter(role='ADMIN').exists():
            self.stdout.write('Admin user already exists.')
            return
        user = User.objects.create_superuser(
            email='admin@callims.local',
            password='Admin@CalLIMS2026',
            first_name='System',
            last_name='Administrator',
        )
        self.stdout.write(self.style.SUCCESS(
            f'Admin user created: {user.email} / Admin@CalLIMS2026'
        ))

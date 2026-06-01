#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    # Prefer DJANGO_SETTINGS_MODULE from the process env, then .env (read via
    # decouple), and fall back to development settings for local work. Without
    # the decouple lookup, production boxes crash on `manage.py shell` etc.
    # because the .env value is never consulted before Django imports settings.
    from decouple import config
    os.environ.setdefault(
        'DJANGO_SETTINGS_MODULE',
        config('DJANGO_SETTINGS_MODULE', default='config.settings.development'),
    )
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == '__main__':
    main()

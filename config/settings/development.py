from .base import *

DEBUG = True
ALLOWED_HOSTS = ['*']

INSTALLED_APPS += ['debug_toolbar']
MIDDLEWARE = ['debug_toolbar.middleware.DebugToolbarMiddleware'] + MIDDLEWARE

INTERNAL_IPS = ['127.0.0.1']

DATABASES['default']['NAME'] = config('DB_NAME', default='lims_dev')

EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

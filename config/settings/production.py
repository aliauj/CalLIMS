from .base import *
import sentry_sdk
from sentry_sdk.integrations.django import DjangoIntegration

DEBUG = False

# Set to True when nginx (or any other reverse proxy) is terminating TLS in
# front of gunicorn. install.sh writes this to .env when --enable-https is
# passed. When False, secure-cookie/redirect/HSTS settings stay off so an
# HTTP-only install does not lock users out with cookie/CSRF failures.
CALLIMS_SECURE = config('CALLIMS_SECURE', default=False, cast=bool)

SENTRY_DSN = config('SENTRY_DSN', default='')
if SENTRY_DSN:
    sentry_sdk.init(dsn=SENTRY_DSN, integrations=[DjangoIntegration()], traces_sample_rate=0.1)

# Hardening that applies regardless of TLS posture.
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'same-origin'

# TLS-dependent hardening — only enabled when nginx is actually fronting TLS,
# otherwise SECURE_SSL_REDIRECT loops forever (Django sees plain HTTP from the
# proxy) and the cookie SECURE flags lock users out on HTTP.
if CALLIMS_SECURE:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# Django 4+/5 require CSRF_TRUSTED_ORIGINS for POSTs whose Origin/Referer comes
# in via the proxy. Build it from ALLOWED_HOSTS so install.sh stays the single
# source of truth for hostnames.
_csrf_scheme = 'https' if CALLIMS_SECURE else 'http'
CSRF_TRUSTED_ORIGINS = [
    f'{_csrf_scheme}://{host}'
    for host in ALLOWED_HOSTS
    if host and host != '*'
]

# Fail fast on default secrets in production rather than silently shipping
# the placeholder values that ship with base.py.
if SECRET_KEY == 'dev-secret-key-change-in-production':
    raise RuntimeError(
        'SECRET_KEY is the default placeholder. Set SECRET_KEY in .env '
        'before booting production.'
    )
if LICENSE_SECRET_KEY == 'callims-vendor-secret-change-per-deployment':
    raise RuntimeError(
        'LICENSE_SECRET_KEY is the default placeholder. Set LICENSE_SECRET_KEY '
        'in .env before booting production.'
    )

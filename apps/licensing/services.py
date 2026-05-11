import hmac
import hashlib
import base64
import json
from django.conf import settings

LICENSE_SECRET = getattr(settings, 'LICENSE_SECRET_KEY', 'callims-default-secret-change-in-production')

# Module names that can be toggled in a license
ALL_MODULES = [
    'instruments', 'jobs', 'certificates',   # core — always available
    'standards', 'clients',
    'portal', 'nonconformance', 'proficiency',
    'compliance', 'reports', 'uncertainty',
    'sales',
]

CORE_MODULES = ['instruments', 'jobs', 'certificates']

TIER_DEFAULTS = {
    'STARTER': {
        'max_users': 5,
        'modules': ['instruments', 'jobs', 'certificates', 'standards', 'clients'],
    },
    'PROFESSIONAL': {
        'max_users': 20,
        'modules': [
            'instruments', 'jobs', 'certificates', 'standards', 'clients',
            'portal', 'nonconformance', 'compliance', 'reports', 'sales',
        ],
    },
    'ENTERPRISE': {
        'max_users': -1,  # unlimited
        'modules': ALL_MODULES,
    },
}

MODULE_LABELS = {
    'instruments':    'Instruments & Gauges',
    'jobs':           'Calibration Jobs',
    'certificates':   'Certificates',
    'standards':      'Reference Standards',
    'clients':        'Clients',
    'portal':         'Client Portal',
    'nonconformance': 'NC / CAPA',
    'proficiency':    'Proficiency Testing',
    'compliance':     'Audit Log',
    'reports':        'Reports & Analytics',
    'uncertainty':    'Uncertainty Engine',
    'sales':          'Sales / RFQ',
}


def _sign(payload: dict) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(',', ':')).encode()
    return hmac.new(LICENSE_SECRET.encode(), data, hashlib.sha256).hexdigest()


def generate_license_key(payload: dict) -> str:
    """Sign and base64-encode a license payload into a portable key string."""
    sig = _sign(payload)
    full = json.dumps({'d': payload, 's': sig}, separators=(',', ':'))
    return base64.b64encode(full.encode()).decode()


def decode_license_key(key: str) -> dict | None:
    """Decode and verify a license key. Returns the payload dict or None if tampered/invalid."""
    try:
        full = json.loads(base64.b64decode(key.strip()).decode())
        payload = full['d']
        sig = full['s']
        expected = _sign(payload)
        if hmac.compare_digest(sig, expected):
            return payload
    except Exception:
        pass
    return None

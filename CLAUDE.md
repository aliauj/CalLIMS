# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Installation

```bash
# Full server install (Ubuntu, Debian, RHEL, Rocky, AlmaLinux, Fedora)
sudo bash install.sh

# With optional flags:
sudo bash install.sh --domain callims.example.com   # set Nginx server_name
sudo bash install.sh --enable-https                 # generate self-signed cert, serve HTTPS on :443
sudo bash install.sh --skip-nginx                   # skip Nginx setup
sudo bash install.sh --skip-firewall                # skip ufw/firewalld
```

The installer: detects the distro, installs Python (3.12 on Ubuntu 24.04+, 3.11 elsewhere via deadsnakes/backports) plus PostgreSQL 16/Redis/Nginx, creates a `callims` system user with home at `/home/callims` (nologin shell), sets up `/home/callims/app`, writes `/home/callims/app/.env` with generated secrets, runs migrations, prompts for a superuser, creates systemd services (`callims-web`, `callims-worker`, `callims-beat`), configures Nginx (with self-signed TLS at `/etc/ssl/callims/` if `--enable-https`), and generates the first license key.

**Re-running the installer is safe.** It preserves `SECRET_KEY` (sessions stay valid) and `LICENSE_SECRET_KEY` (previously-issued license keys keep verifying) from the existing `.env`, generating fresh secrets only on a first install. It also resets the PG user's password to match the new `.env` so DB auth stays consistent. `ALLOWED_HOSTS` is auto-built from `localhost`, `127.0.0.1`, the detected server IP, the system hostname, and `--domain` (if provided); never edit this manually unless adding extra aliases.

## Commands

```bash
# Activate virtualenv (required for all commands)
source venv/bin/activate

# Run dev server
python manage.py runserver

# Migrations
python manage.py makemigrations
python manage.py migrate

# Run a specific app's migrations
python manage.py migrate workflows

# Django system check (run before reporting work as done)
python manage.py check

# Create superuser
python manage.py createsuperuser

# Generate a license key (vendor tool — run on the server, send key to customer)
python manage.py generate_license --issued-to "Lab Name" --tier ENTERPRISE --days 365

# Celery worker (required for PDF generation via tasks)
celery -A config worker -l info

# Celery beat scheduler
celery -A config beat -l info
```

The settings module is `config.settings.development` (set in `manage.py`). No `.env` file is needed for local dev — defaults are wired into `config/settings/development.py`.

**Running `manage.py` on a production server**: `manage.py` hardcodes the dev settings module, and dev settings include `debug_toolbar`, which is **not** in `requirements/production.txt`. Any `manage.py` command on a prod box will crash with `ModuleNotFoundError: No module named 'debug_toolbar'` unless you override the env var. Use:
```bash
sudo -u callims env DJANGO_SETTINGS_MODULE=config.settings.production \
  /home/callims/app/venv/bin/python /home/callims/app/manage.py <command>
```
The systemd units already export `DJANGO_SETTINGS_MODULE=config.settings.production` via `EnvironmentFile=` so gunicorn/celery work fine — this gotcha only bites interactive shell/management commands.

### Production operations

- **Gunicorn logs**: `/home/callims/app/logs/gunicorn_access.log` and `gunicorn_error.log`. Application tracebacks land in `gunicorn_error.log`, **not** in `journalctl -u callims-web` (journal only shows startup banners).
- **Nginx logs**: `/var/log/nginx/callims_access.log` and `callims_error.log`.
- **Debugging 500s**: there's no `LOGGING` config wired into Django settings, so unhandled exceptions in production are swallowed (Django would normally email `ADMINS`, but SMTP isn't configured by default). The fastest path to see a traceback is to flip `DEBUG=True` in `/home/callims/app/.env`, restart `callims-web`, reproduce, then revert. **Don't leave DEBUG=True on** — it leaks settings and source paths on every error page.
- **Manual cert regeneration** (when `--enable-https` was used): delete `/etc/ssl/callims/{cert,key}.pem` and re-run the installer; otherwise existing certs are reused.

## Architecture

### Project layout

```
config/           Django project root (settings/, urls.py, celery.py)
apps/             All Django applications
templates/        All HTML templates (mirrors apps/ structure)
  partials/       Shared partials (navbar.html, etc.)
  administration/ Admin panel templates extending base_admin.html
  licensing/      License status, activation, lab settings, module-disabled pages
venv/             Virtualenv (never modify)
```

### Apps and their responsibilities

| App | Responsibility |
|-----|---------------|
| `licensing` | `LabSettings` singleton, `LicenseRecord`, HMAC-SHA256 key signing, middleware enforcement, module gating |
| `users` | Custom `User` model (email auth, 7 RBAC roles + `CustomRole`), `UserModulePermission`, `TechnicianMethodAuthorization` |
| `assets` | `Instrument` / `InstrumentCategory` models, instrument CRUD, sticker PDF, Excel/PDF export |
| `workflows` | `CalibrationJob` FSM, `CalibrationMethod`, `MeasurementResult`, `CalibrationPoint` |
| `certificates` | `Certificate`, `CertificateTemplate`, PDF generation, QR verification, sticker PDF |
| `standards` | `ReferenceStandard`, `MeasurementUnit` traceability chain |
| `uncertainty` | `UncertaintyCalculator` service (GUM-compliant, in `services.py`) |
| `compliance` | `AuditLog`, `AuditMiddleware`, signals-based audit trail |
| `clients` | `Client` model, client CRUD |
| `portal` | Read-only client-facing views (instruments, certificates) |
| `administration` | Admin panel: user management, custom roles, methods, categories, units, cert templates, reports |
| `notifications` | `Notification` model, in-app notifications, JSON poll API |
| `nonconformance` | NC/CAPA records including customer complaints |
| `proficiency` | Proficiency testing records |
| `sales` | `RFQ` and `RFQItem` — sales submit RFQs for lab manager review; on acceptance, sales register customer instruments and notify the manager to create jobs |

### URL namespaces

`licensing:`, `instruments:`, `workflows:`, `certificates:`, `standards:`, `clients:`, `portal:`, `compliance:`, `administration:`, `proficiency:`, `nonconformance:`, `sales:`, `users:`, `notifications:`

### Key patterns

**Licensing system** — `apps/licensing` is the first app in `INSTALLED_APPS` and its middleware runs last in the chain. `LicenseMiddleware` blocks all authenticated requests when no valid license exists, redirecting to `licensing:expired`. Exempt paths: `/auth/`, `/license/`, `/static/`, `/media/`, `/admin/`, `/notifications/api/`. `LabSettings` is a singleton (enforces `pk=1` in `save()`); use `LabSettings.get()` everywhere. `LicenseRecord` stores the active signed key; only one row has `is_active=True`.

**License key format** — Keys are base64-encoded JSON `{"d": payload, "s": hmac_sig}`. The HMAC uses `LICENSE_SECRET_KEY` from settings (vendor-controlled secret, never ship the same key to all customers). `decode_license_key()` in `apps/licensing/services.py` verifies with `hmac.compare_digest` (timing-safe). Generate keys with `python manage.py generate_license`.

**Module gating** — Two layers: (1) `@module_required('module_name')` decorator on views returns 403 with `licensing/module_disabled.html`; (2) navbar links are wrapped in `{% if 'module_name' in enabled_modules %}` using the `enabled_modules` list injected by the `licensing` context processor. Tier defaults live in `apps/licensing/services.py` (`TIER_DEFAULTS`).

**Licensing context processor** — `apps/licensing/context_processors.licensing` (in `TEMPLATES` context processors) injects into every template: `lab_settings`, `license`, `license_is_valid`, `enabled_modules` (list of strings), `license_days_remaining`, `license_expiry_warning` (True when ≤30 days), plus vendor branding: `callims_version`, `callims_vendor`, `callims_vendor_url`, `callims_product`. Version/vendor constants live in `config/version.py`. Use `{{ lab_settings.lab_name|default:"CalLIMS" }}` in titles/navbars. The navbar uses the lab logo if `lab_settings.logo` is set, otherwise the lab name as text. Both `base.html` and `base_admin.html` render a footer using these context variables.

**FSM on CalibrationJob** — `django-fsm` powers job state transitions. Status values are lowercase strings (`'received'`, `'assigned'`, `'in_progress'`, `'review'`, `'approved'`, `'completed'`, `'on_hold'`, `'cancelled'`). Always call the FSM method (e.g. `job.approve()`) then `job.save()` — never set `job.status` directly. ADMIN and MANAGER can hard-delete a job through `workflows:job_delete` (POST-only); the view catches `ProtectedError` so jobs with a linked Certificate fail gracefully — revoke the certificate first.

**Custom User model** — `apps.users.User` with `AUTH_USER_MODEL = 'users.User'`. Built-in roles: `ADMIN`, `MANAGER`, `TECHNICIAN`, `REVIEWER`, `AUDITOR`, `SALES`, `CLIENT`. Dynamic roles are stored in `CustomRole` (code, name, is_lab_staff flag). `user.get_role_display()` checks built-in choices first, then falls back to a `CustomRole` DB lookup. `user.is_lab_staff` is True for every built-in role except `CLIENT`. The `@admin_required` decorator in `apps/administration/decorators.py` allows ADMIN and MANAGER roles. The sales app exposes its own `sales_required` (SALES/MANAGER/ADMIN) and `review_required` (MANAGER/ADMIN) decorators in `apps/sales/views.py`.

**Custom roles** — `CustomRole` model in `apps/users/models.py`. `_all_role_choices()` helper in `apps/administration/views.py` returns built-in + custom choices for dropdowns. Inline role change in the user list uses Alpine.js `x-data="{ editing: false }"` with a form that posts to `administration:user_change_role`. Role CRUD lives at `administration:role_list/create/edit/delete`; deletion is blocked if any users still hold that role.

**Permission system** — `apps/users/permissions.py` exposes `check_perm(user, section, action)` and `@require_perm(section, action)`. ADMIN always passes. Others check `UserModulePermission` records first, then fall back to role defaults in `_DEFAULTS`. Section keys match `AppSection` values (e.g. `'instruments'`, `'jobs'`, `'certificates'`).

**Audit trail** — `apps/compliance/middleware.py` stores the request on a thread-local. `apps/compliance/signals.py` hooks `post_save`/`post_delete` and writes `AuditLog` records automatically. The middleware must remain in `MIDDLEWARE` for audit logging to work.

**PDF generation** — Two paths exist:
1. *On-demand* (synchronous): `certificate_print` and `certificate_sticker_pdf` views use WeasyPrint directly, base64-encode logos/QR codes, and stream the response.
2. *Background* (Celery): `generate_certificate_pdf` task in `apps/certificates/tasks.py` — triggered after signing.
Always embed images as `data:mime;base64,...` URIs so WeasyPrint doesn't need filesystem access.

**Instrument export** — `instrument_export_excel` and `instrument_export_pdf` views in `apps/assets/views.py`. Both share `_build_export_qs(request)` which handles preset filters (`calibrated`, `active`, `overdue`, `due_30`, `due_60`, `out_of_service`, `in_calibration`) and sort options. The export modal in `instrument_list.html` uses Alpine.js to build the export URL from either the current list filters (preset=`current`) or a named preset. Excel uses openpyxl with colored headers and conditional row fills; PDF uses WeasyPrint with A4 landscape `@page`.

**Certificate lifecycle** — `DRAFT → PENDING_SIGN → SIGNED → ISSUED`. Revoke is allowed from `SIGNED` or `ISSUED`. A `content_hash` (SHA-256) is computed at signing via `cert.compute_hash()`. Certificate number and job number are generated with random suffixes at creation time. The certificate list supports filter parameters: `status`, `client` (client PK), `tech` (assigned-to PK), `cert_number`, and instrument tag search.

**Technician authorization** — `TechnicianMethodAuthorization` links a technician `User` to a `CalibrationMethod` with a status (`AUTHORIZED`, `PENDING`, `SUSPENDED`, `REVOKED`) and expiry date. The `is_valid` property checks both status and expiry. Job assignment (`job_assign` view) enforces authorization server-side and shows authorized/unauthorized optgroups in the UI.

**Instrument auto-tagging** — `InstrumentCategory` has a `code` field (e.g. `ELE`). `category.next_tag()` scans existing tags with that prefix to find the true max number and returns the next sequential tag (e.g. `ELE-0004`). The instrument create form uses this when the selected category has a code; otherwise the user enters the tag manually.

**Notifications** — `apps/notifications/context_processors.notifications` injects `unread_notification_count` and `recent_notifications` (top 5 unread) into every template. The bell badge in `navbar.html` auto-polls `/notifications/api/unread-count/` every 30 seconds. Notification triggers live in `apps/workflows/views.py` and `apps/sales/views.py` as `_notify_*` helpers; call them after the corresponding state transition succeeds. `Notification.NotificationType` includes job (`JOB_*`), certificate (`CERT_ISSUED`), standard (`STD_EXPIRING`), and RFQ (`RFQ_NEW`, `RFQ_ACCEPTED`, `RFQ_REJECTED`, `RFQ_READY_FOR_JOBS`) types.

**Sales / RFQ workflow** — `apps/sales/RFQ` is a status field (not django-fsm): `PENDING → ACCEPTED → READY_FOR_JOBS`, or `PENDING → REJECTED`. Sales users only see and edit RFQs they created; managers/admins see all. Acceptance unlocks the "Registered Instruments" panel where sales link existing client instruments (filtered to `RFQ.client`) or register new ones (status defaults to `Instrument.Status.DRAFT`, client auto-set from the RFQ). `Send to Lab Manager` requires at least one linked instrument and notifies all MANAGER/ADMIN users to create calibration jobs through the existing `workflows:job_create` flow — there's no auto-job-creation. RFQ numbers are generated by `_generate_rfq_number()` (`RFQ-YYYY-XXXXXX` with a random suffix) at create time. Instruments link to RFQs via M2M (`RFQ.instruments`); `RFQItem` is a separate draft list captured by sales pre-acceptance and is not the same as the registered instruments.

**NC customer complaint fields** — `NonConformance` has `source` choices including `CUSTOMER_COMPLAINT`. When source is customer complaint, three additional fields apply: `customer` (FK to `Client`), `complaint_channel` (`EMAIL`/`PHONE`), and `customer_resolution` (`RETURN_RECALIBRATE`/`USE_AS_IS`/`CORRECT_REISSUE`). The NC form uses Alpine.js `x-show="source === 'CUSTOMER_COMPLAINT'"` to reveal these fields, with a certificate autocomplete backed by a `CERTS_BY_CLIENT` JSON object embedded in the page.

**Dashboard pending actions** — The `dashboard` view in `apps/workflows/views.py` passes role-specific querysets to the template. Technicians see assigned-but-not-started jobs and jobs returned for correction. Managers/Admins see jobs awaiting review, unassigned jobs, overdue instruments, and expiring standards. Reviewers see jobs awaiting review. Always include `ctx['today'] = today` so due-date comparisons work in the template.

**Reports** — `administration:report_overview` (`/manage/reports/`) renders 12-month job/cert volume, jobs-by-status doughnut, overdue instruments, expiring standards, and customer NCR resolution breakdown. Chart.js data is passed as pre-serialized JSON (`json.dumps(...)`) in the view context and used via `{{ var|safe }}` in template `<script>` blocks — never pass raw Python dicts to template JS.

### Frontend

- Tailwind CSS via CDN (`cdn.tailwindcss.com`) — no build step required
- Alpine.js via CDN (`unpkg.com/alpinejs@3.x.x`) — used for all interactive UI (dropdowns, modals, selection bars, conditional field visibility, inline role editing)
- `[x-cloak]{display:none!important}` is set in `base.html` to prevent Alpine flash-of-content
- The admin panel uses `templates/administration/base_admin.html` (has its own sidebar nav with a "License & Settings" link); all other pages use `templates/base.html`
- When embedding JSON for Alpine.js use, always serialize server-side with `json.dumps()` and output with `{{ var|safe }}`; Django templates cannot serialize Python dicts to JSON on their own
- The `{% load licensing %}` tag must appear at the top of any template that uses `{% module_enabled %}` or the `days_label` filter

### Database notes

- DB name for dev: `lims_dev` (override via `DB_NAME` env var)
- `django-fsm` version is 2.x (the `>=2.11` pin) — ignore the deprecation warning about `viewflow.fsm`; it is harmless
- `rejection_notes` on `CalibrationJob` stores the manager's rejection reason when a job is returned from REVIEW → IN_PROGRESS; blank string means no rejection
- `LicenseRecord` rows are never deleted — old licenses are deactivated (`is_active=False`) when a new key is activated

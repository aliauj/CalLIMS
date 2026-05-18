#!/usr/bin/env bash
# =============================================================================
#  CalLIMS v1.0 — Automated Server Installer
#  Developed by AUJ Tech  |  www.auj-it.com
#
#  Supported platforms:
#    Debian/Ubuntu  — Ubuntu 20.04/22.04/24.04, Debian 11/12
#    Red Hat family — RHEL 8/9, Rocky Linux 8/9, AlmaLinux 8/9, Fedora 38+
#
#  Usage:
#    sudo bash install.sh [--domain example.com] [--app-dir /home/callims/app]
#                         [--enable-https]
#                         [--db-name callims_db] [--skip-nginx] [--skip-firewall]
# =============================================================================

set -euo pipefail
IFS=$'\n\t'

# ── Defaults (override with CLI flags) ────────────────────────────────────────
CALLIMS_VERSION="1.0"
APP_USER="callims"
APP_HOME="/home/callims"
APP_DIR="${APP_HOME}/app"
DB_NAME="callims_db"
DB_USER="callims_db_user"
DOMAIN="_"          # Nginx server_name; use _ for catch-all or set --domain
ENABLE_HTTPS=false  # Generate a self-signed cert and serve HTTPS on :443
PGVERSION="16"
SKIP_NGINX=false
SKIP_FIREWALL=false
SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ── Parse CLI flags ───────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --domain)       DOMAIN="$2";     shift 2 ;;
    --app-dir)      APP_DIR="$2";    shift 2 ;;
    --db-name)      DB_NAME="$2";    shift 2 ;;
    --skip-nginx)   SKIP_NGINX=true; shift   ;;
    --skip-firewall) SKIP_FIREWALL=true; shift ;;
    --enable-https) ENABLE_HTTPS=true; shift ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

VENV_DIR="$APP_DIR/venv"
ENV_FILE="$APP_DIR/.env"

# ── Colors & helpers ──────────────────────────────────────────────────────────
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
BLUE='\033[0;34m'; BOLD='\033[1m'; NC='\033[0m'

info()    { echo -e "${BLUE}[INFO]${NC}  $*"; }
success() { echo -e "${GREEN}[OK]${NC}    $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
step()    { echo -e "\n${BOLD}${BLUE}══ $* ${NC}"; }
error()   { echo -e "${RED}[ERROR]${NC} $*" >&2; exit 1; }

gen_secret() { python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits+'!@#$%^&*') for _ in range(50)))"; }
gen_pass()   { python3 -c "import secrets,string; print(''.join(secrets.choice(string.ascii_letters+string.digits) for _ in range(24)))"; }

# ── Preflight checks ──────────────────────────────────────────────────────────
preflight() {
  step "Preflight checks"

  [[ $EUID -ne 0 ]] && error "This script must be run as root.  Try: sudo bash install.sh"
  [[ -f "$SOURCE_DIR/manage.py" ]] || error "manage.py not found in $SOURCE_DIR. Run install.sh from the CalLIMS project root."

  # Check available disk space (need at least 2 GB)
  AVAIL_KB=$(df -k "$SOURCE_DIR" | awk 'NR==2{print $4}')
  [[ "$AVAIL_KB" -lt 2097152 ]] && warn "Less than 2 GB free disk space. Installation may fail."

  success "Running as root, source directory looks good."
}

# ── Distro detection ──────────────────────────────────────────────────────────
detect_distro() {
  step "Detecting operating system"

  [[ -f /etc/os-release ]] || error "Cannot detect OS: /etc/os-release not found."
  # shellcheck source=/dev/null
  source /etc/os-release

  DISTRO_ID="${ID,,}"
  DISTRO_NAME="${NAME}"
  DISTRO_VERSION="${VERSION_ID:-0}"
  DISTRO_MAJOR="${VERSION_ID%%.*}"

  # Normalize ID_LIKE for derivative distros
  ID_LIKE_NORM="${ID_LIKE:-}"

  case "$DISTRO_ID" in
    ubuntu|debian)
      PKG_FAMILY="debian"
      ;;
    rhel|centos|rocky|almalinux|fedora)
      PKG_FAMILY="rhel"
      ;;
    *)
      # Check ID_LIKE for derivative distros
      if echo "$ID_LIKE_NORM" | grep -qi "debian\|ubuntu"; then
        PKG_FAMILY="debian"
      elif echo "$ID_LIKE_NORM" | grep -qi "rhel\|fedora"; then
        PKG_FAMILY="rhel"
      else
        error "Unsupported distribution: $DISTRO_ID. Supported: Ubuntu, Debian, RHEL, CentOS, Rocky Linux, AlmaLinux, Fedora."
      fi
      ;;
  esac

  info "Detected: $DISTRO_NAME $DISTRO_VERSION (family: $PKG_FAMILY)"
}

# ── Debian/Ubuntu packages ────────────────────────────────────────────────────
install_debian_packages() {
  step "Installing system packages (Debian/Ubuntu)"

  export DEBIAN_FRONTEND=noninteractive
  apt-get update -qq

  # Python — pick a package set per distro release
  PY_PKGS=()
  case "$DISTRO_ID:$DISTRO_MAJOR" in
    ubuntu:20|ubuntu:22)
      info "Ubuntu ${DISTRO_VERSION} detected — adding deadsnakes PPA for Python 3.11"
      apt-get install -y -qq software-properties-common
      add-apt-repository -y ppa:deadsnakes/ppa
      apt-get update -qq
      PY_PKGS=(python3.11 python3.11-dev python3.11-venv python3.11-distutils)
      ;;
    ubuntu:24|ubuntu:25)
      info "Ubuntu ${DISTRO_VERSION} detected — using system Python 3.12"
      PY_PKGS=(python3.12 python3.12-dev python3.12-venv)
      ;;
    debian:11)
      info "Debian 11 detected — adding backports for Python 3.11"
      echo "deb http://deb.debian.org/debian bullseye-backports main" \
        >> /etc/apt/sources.list.d/backports.list
      apt-get update -qq
      PY_PKGS=(python3.11 python3.11-dev python3.11-venv)
      ;;
    debian:12)
      PY_PKGS=(python3.11 python3.11-dev python3.11-venv)
      ;;
    *)
      info "Unrecognized Debian/Ubuntu release ${DISTRO_VERSION} — falling back to default python3"
      PY_PKGS=(python3 python3-dev python3-venv)
      ;;
  esac

  DEBIAN_PKGS=(
    # Build tools
    build-essential gcc curl wget gnupg2 ca-certificates lsb-release
    # Python (chosen above per distro)
    "${PY_PKGS[@]}"
    # PostgreSQL client libs (for psycopg)
    libpq-dev
    # WeasyPrint system dependencies
    libcairo2 libpango-1.0-0 libpangoft2-1.0-0 libpangocairo-1.0-0
    libgdk-pixbuf2.0-0 libffi-dev libxml2-dev libxslt-dev
    shared-mime-info fonts-noto-core fonts-noto
    # Nginx
    nginx
    # Misc
    git acl
  )

  if [[ "$DISTRO_ID" == "debian" && "$DISTRO_MAJOR" == "11" ]]; then
    apt-get install -y -qq -t bullseye-backports "${PY_PKGS[@]}"
    # Install rest from main
    PKGS_NO_PY=("${DEBIAN_PKGS[@]/python3*/}")
    apt-get install -y -qq "${PKGS_NO_PY[@]}" 2>/dev/null || true
  else
    apt-get install -y -qq "${DEBIAN_PKGS[@]}" 2>/dev/null || \
      apt-get install -y "${DEBIAN_PKGS[@]}"
  fi

  # Install Redis
  apt-get install -y -qq redis-server

  success "System packages installed."
}

# ── RHEL/CentOS/Rocky/Alma/Fedora packages ────────────────────────────────────
install_rhel_packages() {
  step "Installing system packages (Red Hat family)"

  # Pick correct package manager
  if command -v dnf &>/dev/null; then
    PKG_MGR="dnf"
  else
    PKG_MGR="yum"
  fi

  # Enable EPEL (needed for Redis on RHEL 8/9, Rocky, Alma)
  if [[ "$DISTRO_ID" != "fedora" ]]; then
    $PKG_MGR install -y epel-release 2>/dev/null || \
      $PKG_MGR install -y "https://dl.fedoraproject.org/pub/epel/epel-release-latest-${DISTRO_MAJOR}.noarch.rpm" || \
      warn "Could not install EPEL; Redis may not be available."
  fi

  # On RHEL (not Rocky/Alma), enable CodeReady Linux Builder or enable subscription
  if [[ "$DISTRO_ID" == "rhel" ]]; then
    subscription-manager repos --enable "codeready-builder-for-rhel-${DISTRO_MAJOR}-$(uname -m)-rpms" 2>/dev/null || true
  fi

  # Python 3.11
  if [[ "$DISTRO_ID" == "fedora" ]]; then
    PYTHON_PKGS="python3.11 python3.11-devel"
  else
    # RHEL 8/9, Rocky, Alma — Python 3.11 from AppStream
    if [[ "$DISTRO_MAJOR" == "8" ]]; then
      $PKG_MGR module enable -y python311 2>/dev/null || true
    fi
    PYTHON_PKGS="python3.11 python3.11-devel"
  fi

  RHEL_PKGS=(
    # Build tools
    gcc gcc-c++ make curl wget ca-certificates
    $PYTHON_PKGS
    # PostgreSQL client libs
    libpq-devel
    # WeasyPrint system dependencies
    cairo pango libffi-devel libxml2-devel libxslt-devel
    gdk-pixbuf2 shared-mime-info
    # Fonts (best available)
    google-noto-fonts-common google-noto-sans-fonts
    # Nginx
    nginx
    # Redis (from EPEL or AppStream)
    redis
    # Misc
    git acl
  )

  $PKG_MGR install -y "${RHEL_PKGS[@]}" 2>/dev/null || \
    $PKG_MGR install -y "${RHEL_PKGS[@]}"

  success "System packages installed."
}

# ── PostgreSQL (official PGDG repo) ──────────────────────────────────────────
setup_postgresql() {
  step "Installing PostgreSQL $PGVERSION"

  if command -v psql &>/dev/null; then
    INSTALLED_PG=$(psql --version | grep -oP '\d+' | head -1)
    if [[ "$INSTALLED_PG" -ge "$PGVERSION" ]]; then
      info "PostgreSQL $INSTALLED_PG already installed. Skipping."
      PG_SERVICE="postgresql"
      return
    fi
  fi

  if [[ "$PKG_FAMILY" == "debian" ]]; then
    # Official PGDG apt repo
    install -d /usr/share/postgresql-common/pgdg
    curl -fsSL "https://www.postgresql.org/media/keys/ACCC4CF8.asc" \
      | gpg --dearmor -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg
    DISTRO_CODENAME="$(lsb_release -cs 2>/dev/null || echo "$VERSION_CODENAME")"
    echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.gpg] \
https://apt.postgresql.org/pub/repos/apt ${DISTRO_CODENAME}-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list
    apt-get update -qq
    apt-get install -y -qq "postgresql-$PGVERSION" "postgresql-client-$PGVERSION"
    PG_SERVICE="postgresql"

  elif [[ "$PKG_FAMILY" == "rhel" ]]; then
    ARCH="$(uname -m)"
    PGDG_RPM="https://download.postgresql.org/pub/repos/yum/reporpms/EL-${DISTRO_MAJOR}-${ARCH}/pgdg-redhat-repo-latest.noarch.rpm"
    $PKG_MGR install -y "$PGDG_RPM" 2>/dev/null || true
    # Disable built-in postgresql module to avoid conflicts
    $PKG_MGR -qy module disable postgresql 2>/dev/null || true
    $PKG_MGR install -y "postgresql${PGVERSION}-server" "postgresql${PGVERSION}"
    # Initialize the database cluster
    "/usr/pgsql-${PGVERSION}/bin/postgresql-${PGVERSION}-setup" initdb
    PG_SERVICE="postgresql-${PGVERSION}"
  fi

  systemctl enable --now "$PG_SERVICE"
  success "PostgreSQL $PGVERSION installed and started."
}

# ── Redis ─────────────────────────────────────────────────────────────────────
setup_redis() {
  step "Enabling Redis"

  if [[ "$PKG_FAMILY" == "debian" ]]; then
    REDIS_SVC="redis-server"
  else
    REDIS_SVC="redis"
  fi

  systemctl enable --now "$REDIS_SVC"
  success "Redis enabled."
}

# ── App user & directory ───────────────────────────────────────────────────────
setup_app_user() {
  step "Creating system user '$APP_USER'"

  if id "$APP_USER" &>/dev/null; then
    warn "User '$APP_USER' already exists. Skipping creation."
  else
    useradd --system --create-home --home-dir "$APP_HOME" --shell /usr/sbin/nologin "$APP_USER"
    success "User '$APP_USER' created."
  fi

  # Ensure the home dir exists and is owned by the app user — covers the case
  # where the user was created on a previous install with --no-create-home.
  mkdir -p "$APP_HOME"
  chown "$APP_USER":"$APP_USER" "$APP_HOME"
  chmod 750 "$APP_HOME"
}

setup_app_directory() {
  step "Copying application files to $APP_DIR"

  if [[ "$SOURCE_DIR" == "$APP_DIR" ]]; then
    info "Source is already at $APP_DIR. Skipping copy."
  else
    mkdir -p "$APP_DIR"
    # Copy everything except venv, __pycache__, *.pyc, and the .env if it exists
    rsync -a --exclude='venv/' --exclude='__pycache__/' \
              --exclude='*.pyc' --exclude='.env' \
              --exclude='media/' --exclude='staticfiles/' \
              "$SOURCE_DIR/" "$APP_DIR/"
    info "Files copied from $SOURCE_DIR to $APP_DIR"
  fi

  # Ensure media and staticfiles directories exist
  mkdir -p "$APP_DIR/media" "$APP_DIR/staticfiles" "$APP_DIR/logs"

  chown -R "$APP_USER":"$APP_USER" "$APP_DIR"
  chmod 750 "$APP_DIR"
  success "Application directory ready at $APP_DIR"
}

# ── Python virtualenv ─────────────────────────────────────────────────────────
setup_venv() {
  step "Creating Python virtual environment"

  PYTHON_BIN=""
  for py in python3.12 python3.11 python3.10; do
    if command -v "$py" &>/dev/null; then
      PYTHON_BIN="$(command -v "$py")"
      break
    fi
  done
  [[ -z "$PYTHON_BIN" ]] && error "Python 3.10+ not found. Install python3.11 manually and re-run."

  PY_VERSION=$("$PYTHON_BIN" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
  info "Using $PYTHON_BIN (Python $PY_VERSION)"

  if [[ -d "$VENV_DIR" ]]; then
    warn "Virtual environment already exists at $VENV_DIR. Re-using."
  else
    sudo -u "$APP_USER" "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --quiet --upgrade pip wheel setuptools

  info "Installing Python dependencies (this may take a few minutes)..."
  sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --quiet -r "$APP_DIR/requirements/production.txt"

  success "Virtual environment ready."
}

# ── Database ──────────────────────────────────────────────────────────────────
setup_database() {
  step "Setting up PostgreSQL database"

  DB_PASSWORD="$(gen_pass)"

  # Create role if it doesn't exist; either way, reset the password to the freshly
  # generated value so it matches what we'll write to .env. Without the ALTER on
  # re-runs, .env drifts out of sync with PG and Django can't connect.
  if sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname='$DB_USER'" | grep -q 1; then
    sudo -u postgres psql -c "ALTER USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
  else
    sudo -u postgres psql -c "CREATE USER $DB_USER WITH PASSWORD '$DB_PASSWORD';"
  fi

  # Create database if it doesn't exist
  sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname='$DB_NAME'" | grep -q 1 || \
    sudo -u postgres psql -c "CREATE DATABASE $DB_NAME OWNER $DB_USER;"

  sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE $DB_NAME TO $DB_USER;" &>/dev/null

  # Persist password for env file
  GENERATED_DB_PASSWORD="$DB_PASSWORD"
  success "Database '$DB_NAME' ready."
}

# ── Environment file ──────────────────────────────────────────────────────────
create_env_file() {
  step "Writing .env configuration file"

  # Preserve secrets across re-installs. Regenerating SECRET_KEY logs every
  # user out; regenerating LICENSE_SECRET_KEY invalidates every license key
  # ever issued by this install. If an existing .env has these values, reuse
  # them and only generate fresh ones on a true first install.
  EXISTING_SECRET_KEY=""
  EXISTING_LICENSE_SECRET=""
  if [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists at $ENV_FILE — preserving secrets, backing up to .env.bak"
    cp "$ENV_FILE" "${ENV_FILE}.bak"
    EXISTING_SECRET_KEY=$(awk -F= '/^SECRET_KEY=/{sub(/^SECRET_KEY=/,""); print; exit}' "$ENV_FILE")
    EXISTING_LICENSE_SECRET=$(awk -F= '/^LICENSE_SECRET_KEY=/{sub(/^LICENSE_SECRET_KEY=/,""); print; exit}' "$ENV_FILE")
  fi

  if [[ -n "$EXISTING_SECRET_KEY" ]]; then
    SECRET_KEY="$EXISTING_SECRET_KEY"
    info "Reusing existing SECRET_KEY from .env"
  else
    SECRET_KEY="$(gen_secret)"
  fi

  if [[ -n "$EXISTING_LICENSE_SECRET" ]]; then
    LICENSE_SECRET="$EXISTING_LICENSE_SECRET"
    info "Reusing existing LICENSE_SECRET_KEY — previously issued license keys remain valid"
  else
    LICENSE_SECRET="$(gen_secret)"
  fi

  # Build ALLOWED_HOSTS — Django rejects "_" so we always include real
  # hostnames/IPs. When --domain wasn't provided, DOMAIN is "_" (Nginx
  # catch-all marker) and must NOT leak into ALLOWED_HOSTS.
  SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  SERVER_HOST="$(hostname -f 2>/dev/null || hostname)"
  ALLOWED_HOSTS_LIST="localhost,127.0.0.1"
  [[ -n "$SERVER_IP" ]]   && ALLOWED_HOSTS_LIST="${ALLOWED_HOSTS_LIST},${SERVER_IP}"
  [[ -n "$SERVER_HOST" ]] && ALLOWED_HOSTS_LIST="${ALLOWED_HOSTS_LIST},${SERVER_HOST}"
  [[ "$DOMAIN" != "_" && -n "$DOMAIN" ]] && ALLOWED_HOSTS_LIST="${ALLOWED_HOSTS_LIST},${DOMAIN}"

  # DEFAULT_FROM_EMAIL domain — fall back to the server hostname when no
  # --domain was passed so we don't end up with "noreply@_".
  FROM_EMAIL_DOMAIN="$DOMAIN"
  [[ "$FROM_EMAIL_DOMAIN" == "_" || -z "$FROM_EMAIL_DOMAIN" ]] && FROM_EMAIL_DOMAIN="${SERVER_HOST:-localhost}"

  cat > "$ENV_FILE" <<EOF
# CalLIMS v${CALLIMS_VERSION} — Generated by installer on $(date -u '+%Y-%m-%d %H:%M UTC')
# Developed by AUJ Tech — www.auj-it.com
# ---------------------------------------------------------------
# KEEP THIS FILE SECRET. Do not commit it to version control.
# ---------------------------------------------------------------

DJANGO_SETTINGS_MODULE=config.settings.production
DEBUG=False
SECRET_KEY=${SECRET_KEY}
ALLOWED_HOSTS=${ALLOWED_HOSTS_LIST}

# Database
DB_NAME=${DB_NAME}
DB_USER=${DB_USER}
DB_PASSWORD=${GENERATED_DB_PASSWORD}
DB_HOST=127.0.0.1
DB_PORT=5432

# Redis / Celery
REDIS_URL=redis://127.0.0.1:6379/0

# Email (configure your SMTP server here)
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=localhost
EMAIL_PORT=25
DEFAULT_FROM_EMAIL=noreply@${FROM_EMAIL_DOMAIN}

# License signing key — NEVER share this with customers
LICENSE_SECRET_KEY=${LICENSE_SECRET}
EOF

  chown "$APP_USER":"$APP_USER" "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  success ".env written to $ENV_FILE"
}

# ── Django setup ──────────────────────────────────────────────────────────────
setup_django() {
  step "Running Django migrations and static files"

  cd "$APP_DIR"

  sudo -u "$APP_USER" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    "$VENV_DIR/bin/python" manage.py migrate --noinput

  sudo -u "$APP_USER" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    "$VENV_DIR/bin/python" manage.py collectstatic --noinput --clear

  success "Database migrations and static files done."
}

# ── Admin superuser ───────────────────────────────────────────────────────────
create_superuser() {
  step "Creating Django superuser (administrator account)"

  echo ""
  echo "  Enter the details for the CalLIMS administrator account."
  echo "  This account will have full access to the system."
  echo ""

  read -rp "  Admin email address : " ADMIN_EMAIL
  read -rp "  Admin first name    : " ADMIN_FIRST
  read -rp "  Admin last name     : " ADMIN_LAST
  read -rsp "  Admin password      : " ADMIN_PASS
  echo ""
  read -rsp "  Confirm password    : " ADMIN_PASS2
  echo ""

  if [[ "$ADMIN_PASS" != "$ADMIN_PASS2" ]]; then
    warn "Passwords do not match. Skipping superuser creation. Run manually:"
    warn "  sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py createsuperuser"
    return
  fi

  cd "$APP_DIR"
  sudo -u "$APP_USER" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    "$VENV_DIR/bin/python" - <<PYEOF
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.production')
django.setup()
from apps.users.models import User
if not User.objects.filter(email='${ADMIN_EMAIL}').exists():
    u = User.objects.create_superuser(
        email='${ADMIN_EMAIL}',
        password='${ADMIN_PASS}',
        first_name='${ADMIN_FIRST}',
        last_name='${ADMIN_LAST}',
    )
    u.role = 'ADMIN'
    u.save()
    print('Superuser created.')
else:
    print('User already exists — skipped.')
PYEOF

  success "Administrator account ready."
}

# ── Systemd services ──────────────────────────────────────────────────────────
create_systemd_services() {
  step "Creating systemd service units"

  # ── Gunicorn (web) ───────────────────────────────────────────────────────
  cat > /etc/systemd/system/callims-web.service <<EOF
[Unit]
Description=CalLIMS Web (Gunicorn)
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=notify
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/gunicorn \\
    --bind 127.0.0.1:8000 \\
    --workers 3 \\
    --worker-class sync \\
    --timeout 120 \\
    --access-logfile ${APP_DIR}/logs/gunicorn_access.log \\
    --error-logfile  ${APP_DIR}/logs/gunicorn_error.log \\
    config.wsgi:application
ExecReload=/bin/kill -s HUP \$MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

  # ── Celery worker ────────────────────────────────────────────────────────
  cat > /etc/systemd/system/callims-worker.service <<EOF
[Unit]
Description=CalLIMS Celery Worker
After=network.target redis.service
Requires=redis.service

[Service]
Type=forking
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/celery \\
    -A config worker \\
    --loglevel=info \\
    --logfile=${APP_DIR}/logs/celery_worker.log \\
    --pidfile=${APP_DIR}/logs/celery_worker.pid \\
    --detach
ExecStop=/bin/kill -TERM \$MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  # ── Celery beat (scheduler) ──────────────────────────────────────────────
  cat > /etc/systemd/system/callims-beat.service <<EOF
[Unit]
Description=CalLIMS Celery Beat Scheduler
After=network.target redis.service
Requires=redis.service

[Service]
Type=forking
User=${APP_USER}
Group=${APP_USER}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${VENV_DIR}/bin/celery \\
    -A config beat \\
    --loglevel=info \\
    --logfile=${APP_DIR}/logs/celery_beat.log \\
    --pidfile=${APP_DIR}/logs/celery_beat.pid \\
    --scheduler django_celery_beat.schedulers:DatabaseScheduler \\
    --detach
ExecStop=/bin/kill -TERM \$MAINPID
Restart=on-failure
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

  systemctl daemon-reload
  systemctl enable --now callims-web callims-worker callims-beat

  success "Systemd services created and started."
}

# ── Self-signed TLS cert (optional, for --enable-https) ───────────────────────
setup_ssl_cert() {
  [[ "$ENABLE_HTTPS" == true ]] || return 0
  [[ "$SKIP_NGINX" == true ]]   && { warn "--enable-https set but --skip-nginx active; not generating cert."; return 0; }

  step "Generating self-signed TLS certificate"

  SSL_DIR="/etc/ssl/callims"
  SSL_CERT="$SSL_DIR/cert.pem"
  SSL_KEY="$SSL_DIR/key.pem"

  mkdir -p "$SSL_DIR"

  if [[ -f "$SSL_CERT" && -f "$SSL_KEY" ]]; then
    info "Existing cert found at $SSL_CERT — reusing. Delete the files and rerun to regenerate."
    return 0
  fi

  CERT_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
  CERT_HOST="$(hostname -f 2>/dev/null || hostname)"

  # Build subjectAltName list: localhost + IPs + hostname + --domain (if real)
  SAN="DNS:localhost,IP:127.0.0.1"
  [[ -n "$CERT_IP" ]]   && SAN="${SAN},IP:${CERT_IP}"
  [[ -n "$CERT_HOST" ]] && SAN="${SAN},DNS:${CERT_HOST}"
  [[ "$DOMAIN" != "_" && -n "$DOMAIN" ]] && SAN="${SAN},DNS:${DOMAIN}"

  # CN: prefer real domain, then hostname, then IP
  CERT_CN="$DOMAIN"
  [[ "$CERT_CN" == "_" || -z "$CERT_CN" ]] && CERT_CN="${CERT_HOST:-${CERT_IP:-localhost}}"

  openssl req -x509 -nodes -newkey rsa:4096 -days 3650 \
    -keyout "$SSL_KEY" -out "$SSL_CERT" \
    -subj "/CN=${CERT_CN}/O=CalLIMS" \
    -addext "subjectAltName=${SAN}" >/dev/null 2>&1

  chmod 644 "$SSL_CERT"
  chmod 600 "$SSL_KEY"

  success "Self-signed cert written to $SSL_CERT (SAN: $SAN)"
}

# ── Nginx ─────────────────────────────────────────────────────────────────────
setup_nginx() {
  if [[ "$SKIP_NGINX" == true ]]; then
    warn "Skipping Nginx configuration (--skip-nginx flag set)."
    return
  fi

  step "Configuring Nginx"

  # Shared location blocks reused by both the HTTP-only and the HTTPS vhost
  read -r -d '' NGINX_APP_BLOCK <<EOF || true
    client_max_body_size 20M;

    location /static/ {
        alias ${APP_DIR}/staticfiles/;
        expires 30d;
        access_log off;
        add_header Cache-Control "public, immutable";
    }

    location /media/ {
        alias ${APP_DIR}/media/;
        expires 7d;
        access_log off;
    }

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_connect_timeout 60s;
        proxy_read_timeout 120s;
        proxy_send_timeout 60s;
    }

    access_log /var/log/nginx/callims_access.log;
    error_log  /var/log/nginx/callims_error.log;
EOF

  if [[ "$ENABLE_HTTPS" == true ]]; then
    NGINX_CONF_CONTENT="# HTTP → HTTPS redirect
server {
    listen 80;
    server_name ${DOMAIN};
    return 301 https://\$host\$request_uri;
}

# HTTPS app server (self-signed cert; browser warns on first visit)
server {
    listen 443 ssl;
    http2 on;
    server_name ${DOMAIN};

    ssl_certificate     /etc/ssl/callims/cert.pem;
    ssl_certificate_key /etc/ssl/callims/key.pem;
    ssl_protocols       TLSv1.2 TLSv1.3;
    ssl_ciphers         HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_cache   shared:SSL:10m;
    ssl_session_timeout 1d;

${NGINX_APP_BLOCK}
}"
  else
    NGINX_CONF_CONTENT="server {
    listen 80;
    server_name ${DOMAIN};

${NGINX_APP_BLOCK}
}"
  fi

  if [[ "$PKG_FAMILY" == "debian" ]]; then
    NGINX_CONF_PATH="/etc/nginx/sites-available/callims"
    echo "$NGINX_CONF_CONTENT" > "$NGINX_CONF_PATH"
    ln -sf "$NGINX_CONF_PATH" /etc/nginx/sites-enabled/callims
    # Remove default site if it exists to avoid port conflict
    rm -f /etc/nginx/sites-enabled/default
  else
    # RHEL-family uses conf.d
    NGINX_CONF_PATH="/etc/nginx/conf.d/callims.conf"
    echo "$NGINX_CONF_CONTENT" > "$NGINX_CONF_PATH"
    # Remove default conf
    rm -f /etc/nginx/conf.d/default.conf
  fi

  # Fall back to the legacy "listen 443 ssl http2" form if the split syntax
  # isn't supported (nginx < 1.25, e.g. Ubuntu 22.04 stock).
  if ! nginx -t >/dev/null 2>&1; then
    info "nginx -t failed with split http2 directive; retrying with legacy syntax"
    sed -i 's|listen 443 ssl;\n *http2 on;|listen 443 ssl http2;|' "$NGINX_CONF_PATH" 2>/dev/null
    # sed -i with \n is GNU-only; do a 2-line collapse the portable way
    perl -i -0pe 's/listen 443 ssl;\s*\n\s*http2 on;/listen 443 ssl http2;/' "$NGINX_CONF_PATH" 2>/dev/null || true
  fi

  nginx -t && systemctl enable --now nginx && systemctl reload nginx
  success "Nginx configured at $NGINX_CONF_PATH"
}

# ── Firewall ──────────────────────────────────────────────────────────────────
setup_firewall() {
  if [[ "$SKIP_FIREWALL" == true ]]; then
    warn "Skipping firewall configuration (--skip-firewall flag set)."
    return
  fi

  step "Configuring firewall"

  if command -v ufw &>/dev/null; then
    ufw allow OpenSSH
    ufw allow 'Nginx Full'
    ufw --force enable
    success "ufw: SSH + HTTP/HTTPS allowed."

  elif command -v firewall-cmd &>/dev/null; then
    firewall-cmd --permanent --add-service=http
    firewall-cmd --permanent --add-service=https
    firewall-cmd --permanent --add-service=ssh
    firewall-cmd --reload
    success "firewalld: SSH + HTTP/HTTPS allowed."

  else
    warn "No firewall manager found (ufw/firewalld). Configure manually if needed."
  fi
}

# ── Generate initial license key ──────────────────────────────────────────────
generate_license() {
  step "Generating initial license key"

  echo ""
  read -rp "  Customer / Lab name (for the license): " LIC_LAB_NAME
  read -rp "  Tier [STARTER / PROFESSIONAL / ENTERPRISE] (default: ENTERPRISE): " LIC_TIER
  LIC_TIER="${LIC_TIER:-ENTERPRISE}"
  read -rp "  Validity in days (default: 365): " LIC_DAYS
  LIC_DAYS="${LIC_DAYS:-365}"

  cd "$APP_DIR"
  echo ""
  echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
  sudo -u "$APP_USER" \
    DJANGO_SETTINGS_MODULE=config.settings.production \
    "$VENV_DIR/bin/python" manage.py generate_license \
      --issued-to "$LIC_LAB_NAME" \
      --tier "$LIC_TIER" \
      --days "$LIC_DAYS"
  echo -e "${BOLD}═══════════════════════════════════════════════════════${NC}"
  echo ""
  warn "Copy the license key above. The customer must paste it at: http://<server>/license/status/"
}

# ── Print summary ─────────────────────────────────────────────────────────────
print_summary() {
  SERVER_IP="$(hostname -I 2>/dev/null | awk '{print $1}' || echo '<server-ip>')"

  echo ""
  echo -e "${BOLD}${GREEN}"
  echo "╔══════════════════════════════════════════════════════════════╗"
  echo "║         CalLIMS v${CALLIMS_VERSION} — Installation Complete              ║"
  echo "║         Developed by AUJ Tech  |  www.auj-it.com            ║"
  echo "╚══════════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
  URL_SCHEME="http"
  [[ "$ENABLE_HTTPS" == true ]] && URL_SCHEME="https"
  echo -e "  ${BOLD}Application URL${NC}  : ${URL_SCHEME}://${DOMAIN//_/$SERVER_IP}"
  echo -e "  ${BOLD}App directory${NC}    : $APP_DIR"
  echo -e "  ${BOLD}Config file${NC}      : $ENV_FILE"
  echo -e "  ${BOLD}Log directory${NC}    : $APP_DIR/logs/"
  echo ""
  echo -e "  ${BOLD}Services${NC}:"
  systemctl is-active callims-web    &>/dev/null && echo -e "    ${GREEN}●${NC} callims-web     (Gunicorn)"   || echo -e "    ${RED}●${NC} callims-web     (FAILED)"
  systemctl is-active callims-worker &>/dev/null && echo -e "    ${GREEN}●${NC} callims-worker  (Celery)"     || echo -e "    ${RED}●${NC} callims-worker  (FAILED)"
  systemctl is-active callims-beat   &>/dev/null && echo -e "    ${GREEN}●${NC} callims-beat    (Scheduler)"  || echo -e "    ${RED}●${NC} callims-beat    (FAILED)"
  echo ""
  echo -e "  ${BOLD}Useful commands${NC}:"
  echo "    Restart web      : systemctl restart callims-web"
  echo "    View web logs    : journalctl -u callims-web -f"
  echo "    View Celery logs : tail -f $APP_DIR/logs/celery_worker.log"
  echo "    Generate license : sudo -u $APP_USER $VENV_DIR/bin/python $APP_DIR/manage.py generate_license --issued-to \"Lab\" --tier PROFESSIONAL --days 365"
  echo ""
  echo -e "  ${YELLOW}Next steps:${NC}"
  echo "    1. Open ${URL_SCHEME}://${DOMAIN//_/$SERVER_IP}/auth/login/ and log in with the admin account."
  echo "    2. Activate the license at /license/status/ using the key printed above."
  if [[ "$ENABLE_HTTPS" == true ]]; then
    echo "    3. The TLS cert is self-signed — browsers will warn once; trust it and continue."
    echo "       For a real cert with a public domain, run: certbot --nginx -d yourdomain.com"
  else
    echo "    3. To enable HTTPS later, rerun with --enable-https (or use certbot for a real cert)."
  fi
  echo "    4. Edit $ENV_FILE to configure SMTP email settings."
  echo ""
}

# ── Main ──────────────────────────────────────────────────────────────────────
main() {
  echo ""
  echo -e "${BOLD}${BLUE}"
  echo "  ╔════════════════════════════════════════════════════╗"
  echo "  ║   CalLIMS v${CALLIMS_VERSION} — Automated Installer               ║"
  echo "  ║   Developed by AUJ Tech  |  www.auj-it.com        ║"
  echo "  ╚════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  preflight
  detect_distro

  if [[ "$PKG_FAMILY" == "debian" ]]; then
    install_debian_packages
  else
    install_rhel_packages
  fi

  setup_postgresql
  setup_redis
  setup_app_user
  setup_app_directory
  setup_venv
  setup_database
  create_env_file
  setup_django
  create_superuser
  create_systemd_services
  setup_ssl_cert
  setup_nginx
  setup_firewall
  generate_license
  print_summary
}

main "$@"

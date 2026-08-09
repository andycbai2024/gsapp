#!/usr/bin/env bash
set -euo pipefail

IFS=$'\n\t'

log() {
  echo "[INFO] $*"
}

warn() {
  echo "[WARN] $*" >&2
}

die() {
  echo "[ERROR] $*" >&2
  exit 1
}

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    die "Please run as root (use sudo)."
  fi
}

usage() {
  cat <<'EOF'
Usage:
  install_gsapp.sh [options]

Options:
  --project-dir <path>      管理平台 project path (default: script parent directory)
  --root-dir <path>         Software root directory (default: /opt/hongmsoft)
  --install-dir <path>      Application install path (default: <root>/softapp)
  --zlm-server <url>        ZLMediaKit HTTP API URL for management platform backend (default: http://127.0.0.1:8080)
  --zlm-mode <mode>         auto | build | existing | skip (default: auto)
  --http-port <port>        management platform frontend nginx listen port (default: 80)
  --api-port <port>         management platform backend listen port in code (default: 10801)
  --zlm-secret <secret>     ZLMediaKit API secret to write into the configuration directory if missing (default: streamui)
  --gb28181-enabled         Enable GB28181 UDP SIP registration service (enabled by default)
  --gb28181-sip-port <port> GB28181 UDP SIP listen port (default: 5060)
  --gb28181-server-id <id>  GB28181 platform ID (default: 34020000002000000001)
  --gb28181-password <pwd>  GB28181 SIP Digest password (default: empty)
  --offline-dir <path>      Install dependencies from an offline bundle payload directory
  --expected-python-version <version>  Require this Python major.minor version before installing dependencies
  --install-system-deps     Allow offline mode to install bundled .deb system packages
  --quick                   Sync application files and restart services without reinstalling dependencies
  -h, --help                Show this help

Examples:
  ./scripts/install_gsapp.sh
  ./scripts/install_gsapp.sh --root-dir /opt/hongmsoft
  ./scripts/install_gsapp.sh --quick
  ./scripts/install_gsapp.sh --offline-dir /tmp/gsapp-offline/payload --zlm-mode existing
  ./scripts/install_gsapp.sh --offline-dir /tmp/gsapp-offline/payload --install-system-deps
  ./scripts/install_gsapp.sh --zlm-mode existing --zlm-server http://127.0.0.1:8080
  ./scripts/install_gsapp.sh --zlm-mode build --http-port 80 --api-port 10801
EOF
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SOFTWARE_ROOT="/opt/hongmsoft"
INSTALL_DIR=""
DATA_DIR=""
CONFIG_DIR=""
LOG_DIR=""
UPGRADE_DIR=""
RUNTIME_DIR=""
MEDIA_ROOT=""
RECORD_ROOT=""
ZLM_CONF_DIR=""
ZLM_CONF_FILE=""
ZLM_SERVER="http://127.0.0.1:8080"
ZLM_MODE="auto"
HTTP_PORT="80"
API_PORT="10801"
ZLM_SECRET="streamui"
GB28181_ENABLED="true"
GB28181_SIP_PORT="5060"
GB28181_SERVER_ID="34020000002000000001"
GB28181_PASSWORD="NSlb-3ggeg1JVXp4oFFeOJeGRyOc1pCO"
SYSTEM_PYTHON="/usr/bin/python3"
QUICK_DEPLOY=0
OFFLINE_DIR=""
EXPECTED_PYTHON_VERSION=""
INSTALL_SYSTEM_DEPS=0
PYTHON_RUNTIME_LD_LIBRARY_PATH=""
NGINX_BIN=""
NGINX_PRIVATE=0
FFMPEG_BIN=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --root-dir)
      SOFTWARE_ROOT="$2"
      shift 2
      ;;
    --project-dir)
      PROJECT_DIR="$2"
      shift 2
      ;;
    --install-dir)
      INSTALL_DIR="$2"
      shift 2
      ;;
    --zlm-server)
      ZLM_SERVER="$2"
      shift 2
      ;;
    --zlm-mode)
      ZLM_MODE="$2"
      shift 2
      ;;
    --http-port)
      HTTP_PORT="$2"
      shift 2
      ;;
    --api-port)
      API_PORT="$2"
      shift 2
      ;;
    --zlm-secret)
      ZLM_SECRET="$2"
      shift 2
      ;;
    --gb28181-enabled)
      GB28181_ENABLED="true"
      shift
      ;;
    --gb28181-sip-port)
      GB28181_SIP_PORT="$2"
      shift 2
      ;;
    --gb28181-server-id)
      GB28181_SERVER_ID="$2"
      shift 2
      ;;
    --gb28181-password)
      GB28181_PASSWORD="$2"
      shift 2
      ;;
    --offline-dir)
      OFFLINE_DIR="$2"
      shift 2
      ;;
    --expected-python-version)
      EXPECTED_PYTHON_VERSION="$2"
      shift 2
      ;;
    --install-system-deps)
      INSTALL_SYSTEM_DEPS=1
      shift
      ;;
    --quick)
      QUICK_DEPLOY=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unknown argument: $1"
      ;;
  esac
done

INSTALL_DIR="${INSTALL_DIR:-${SOFTWARE_ROOT}/softapp}"
DATA_DIR="${SOFTWARE_ROOT}/appdata"
CONFIG_DIR="${SOFTWARE_ROOT}/softcfg"
LOG_DIR="${SOFTWARE_ROOT}/softlog"
UPGRADE_DIR="${SOFTWARE_ROOT}/upgrade"
RUNTIME_DIR="${SOFTWARE_ROOT}/runtime"
MEDIA_ROOT="${INSTALL_DIR}"
RECORD_ROOT="${DATA_DIR}/record"
ZLM_CONF_DIR="${CONFIG_DIR}/zlm"
ZLM_CONF_FILE="${ZLM_CONF_DIR}/config.ini"

validate_inputs() {
  [[ -d "$PROJECT_DIR" ]] || die "Project directory not found: $PROJECT_DIR"
  [[ -f "$PROJECT_DIR/backend/main.py" ]] || die "backend/main.py not found under project directory"
  [[ -f "$PROJECT_DIR/frontend/index.html" ]] || die "frontend/index.html not found under project directory"
  [[ "$ZLM_MODE" =~ ^(auto|build|existing|skip)$ ]] || die "Invalid --zlm-mode: $ZLM_MODE"
  [[ -z "$EXPECTED_PYTHON_VERSION" || "$EXPECTED_PYTHON_VERSION" =~ ^[0-9]+\.[0-9]+$ ]] || die "--expected-python-version must use major.minor format"
  if [[ -n "$OFFLINE_DIR" ]]; then
    [[ -d "$OFFLINE_DIR/debs" ]] || die "Offline package directory not found: $OFFLINE_DIR/debs"
    [[ -d "$OFFLINE_DIR/wheels" ]] || die "Offline Python wheel directory not found: $OFFLINE_DIR/wheels"
  fi
  [[ "$HTTP_PORT" =~ ^[0-9]+$ ]] || die "--http-port must be numeric"
  [[ "$API_PORT" =~ ^[0-9]+$ ]] || die "--api-port must be numeric"
  [[ "$GB28181_SIP_PORT" =~ ^[0-9]+$ && "$GB28181_SIP_PORT" -ge 1 && "$GB28181_SIP_PORT" -le 65535 ]] || die "--gb28181-sip-port must be 1-65535"
  [[ "$GB28181_SERVER_ID" =~ ^[0-9A-Za-z_.-]{3,64}$ ]] || die "--gb28181-server-id is invalid"
}

prepare_application_paths() {
  log "Preparing application directories under $SOFTWARE_ROOT"
  mkdir -p "$INSTALL_DIR" "$DATA_DIR/db" "$DATA_DIR/device_archives" "$CONFIG_DIR" "$LOG_DIR" "$UPGRADE_DIR" "$RUNTIME_DIR"
}

prepare_private_runtime() {
  [[ -n "$OFFLINE_DIR" ]] || return 1
  local runtime_payload="$OFFLINE_DIR/python-runtime/debs"
  local runtime_root="${RUNTIME_DIR}/debian-root"
  local runtime_bin="${RUNTIME_DIR}/bin"
  [[ -d "$runtime_payload" ]] || return 1

  log "Preparing private Python runtime under $RUNTIME_DIR without modifying system packages"
  rm -rf "$runtime_root"
  mkdir -p "$runtime_root" "$runtime_bin"
  local debs=("$runtime_payload"/*.deb)
  [[ -e "${debs[0]}" ]] || die "No private runtime .deb packages found in $runtime_payload"
  for deb in "${debs[@]}"; do
    dpkg-deb -x "$deb" "$runtime_root"
  done

  local python_binary
  python_binary="$(find "$runtime_root/usr/bin" -maxdepth 1 -type f -name 'python3.[0-9]*' | sort | head -n 1 || true)"
  [[ -n "$python_binary" ]] || die "Offline runtime does not contain a Python interpreter"
  local library_paths
  library_paths="$(find "$runtime_root/usr/lib" -mindepth 0 -maxdepth 2 -type d | paste -sd: -)"
  [[ -n "$library_paths" ]] || die "Offline runtime does not contain Python libraries"
  cat > "$runtime_bin/python3" <<EOF
#!/usr/bin/env bash
export LD_LIBRARY_PATH="${library_paths}:\${LD_LIBRARY_PATH:-}"
exec "${python_binary}" "\$@"
EOF
  chmod 0755 "$runtime_bin/python3"
  SYSTEM_PYTHON="$runtime_bin/python3"
  PYTHON_RUNTIME_LD_LIBRARY_PATH="$library_paths"
  NGINX_BIN="$(find "$runtime_root/usr/sbin" -maxdepth 1 -type f -name nginx | head -n 1 || true)"
  FFMPEG_BIN="$(find "$runtime_root/usr/bin" -maxdepth 1 -type f -name ffmpeg | head -n 1 || true)"
  [[ -n "$NGINX_BIN" ]] && NGINX_PRIVATE=1
  "$SYSTEM_PYTHON" -c 'import sqlite3, venv' || die "Private Python runtime is incomplete; regenerate the offline bundle on a matching Linux platform"
}

migrate_legacy_data() {
  local legacy_install_dir="/opt/streamui"
  local legacy_db="${legacy_install_dir}/backend/db/streamui.db"
  local legacy_archives="${legacy_install_dir}/backend/data/device_archives"
  local legacy_media_root="/opt/media"
  local legacy_record_root="${legacy_media_root}/bin/www/record"
  local legacy_zlm_conf="${legacy_media_root}/conf/config.ini"
  local prior_layout_db="${DATA_DIR}/db/streamui.db"
  local target_db="${DATA_DIR}/db/gsapp.db"

  if [[ ! -f "$target_db" ]]; then
    if [[ -f "$prior_layout_db" ]]; then
      log "Migrating prior application database to $target_db"
      mv "$prior_layout_db" "$target_db"
    elif [[ -f "$legacy_db" ]]; then
      log "Migrating legacy SQLite database to $target_db"
      install -m 0600 "$legacy_db" "$target_db"
    fi
  fi
  if [[ -d "$legacy_archives" ]]; then
    log "Migrating legacy device archives to ${DATA_DIR}/device_archives"
    cp -a -n "${legacy_archives}/." "${DATA_DIR}/device_archives/"
  fi
  if [[ ! -f "$ZLM_CONF_FILE" && -f "$legacy_zlm_conf" ]]; then
    log "Migrating legacy ZLMediaKit configuration to $ZLM_CONF_FILE"
    install -m 0644 "$legacy_zlm_conf" "$ZLM_CONF_FILE"
  fi
  if [[ ! -e "$RECORD_ROOT" && -d "$legacy_record_root" ]]; then
    if systemctl is-active --quiet zlmediakit.service; then
      log "Stopping ZLMediaKit before migrating its media directory"
      systemctl stop zlmediakit.service
    fi
    log "Migrating legacy recordings to $RECORD_ROOT"
    mv "$legacy_record_root" "$RECORD_ROOT"
  fi
  if [[ ! -x "$MEDIA_ROOT/bin/MediaServer" && -x "$legacy_media_root/bin/MediaServer" ]]; then
    log "Migrating legacy MediaServer application to $MEDIA_ROOT/bin"
    mv "$legacy_media_root/bin" "$MEDIA_ROOT/bin"
  fi
}

install_system_packages() {
  if [[ "$QUICK_DEPLOY" -eq 1 ]]; then
    log "Quick deployment: skipping system package installation"
    return
  fi
  if [[ -n "$OFFLINE_DIR" ]]; then
    if [[ "$INSTALL_SYSTEM_DEPS" -eq 0 ]]; then
      log "Offline deployment: preserving existing system packages"
      local need_private_runtime=0
      local system_nginx="$(command -v nginx || true)"
      local system_ffmpeg="$(command -v ffmpeg || true)"
      [[ -n "$system_nginx" ]] || need_private_runtime=1
      [[ -n "$system_ffmpeg" ]] || need_private_runtime=1
      if [[ ! -x "$SYSTEM_PYTHON" ]] || ! "$SYSTEM_PYTHON" -c 'import sqlite3, venv' >/dev/null 2>&1; then
        need_private_runtime=1
      fi
      if [[ "$need_private_runtime" -eq 1 ]]; then
        prepare_private_runtime || die "No usable system runtime and no private runtime in the offline bundle"
      fi
      if [[ -n "$system_nginx" ]]; then NGINX_BIN="$system_nginx"; NGINX_PRIVATE=0; fi
      if [[ -n "$system_ffmpeg" ]]; then FFMPEG_BIN="$system_ffmpeg"; fi
      [[ -n "$NGINX_BIN" ]] || die "No usable Nginx in system or private runtime"
      [[ -n "$FFMPEG_BIN" ]] || die "No usable FFmpeg in system or private runtime"
      if [[ -x "$SYSTEM_PYTHON" ]] && "$SYSTEM_PYTHON" -c 'import sqlite3, venv' >/dev/null 2>&1; then
        log "Using existing system Python: $SYSTEM_PYTHON"
      else
        die "No usable system or private Python runtime"
      fi
      return
    fi
    log "Installing system packages from offline bundle"
    local debs=("$OFFLINE_DIR"/debs/*.deb)
    [[ -e "${debs[0]}" ]] || die "No .deb packages found in $OFFLINE_DIR/debs"
    export DEBIAN_FRONTEND=noninteractive
    dpkg -i "${debs[@]}" || apt-get -y --no-download -f install
    dpkg --configure -a
    return
  fi
  local runtime_packages=(
    ca-certificates
    curl
    ffmpeg
    nginx
    python3
    python3-venv
    python3-pip
  )
  local missing_packages=()
  local package
  for package in "${runtime_packages[@]}"; do
    if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx 'installed'; then
      missing_packages+=("$package")
    fi
  done

  local media_server_bin="${MEDIA_ROOT}/bin/MediaServer"
  if [[ ! -x "$media_server_bin" && ( "$ZLM_MODE" == "build" || "$ZLM_MODE" == "auto" ) ]]; then
    local build_packages=(build-essential cmake git pkg-config libssl-dev zlib1g-dev)
    for package in "${build_packages[@]}"; do
      if ! dpkg-query -W -f='${db:Status-Status}' "$package" 2>/dev/null | grep -qx 'installed'; then
        missing_packages+=("$package")
      fi
    done
  fi

  if [[ "${#missing_packages[@]}" -eq 0 ]]; then
    log "System runtime and build dependencies are already installed; skipping apt"
    return
  fi

  log "Installing missing system packages via apt: ${missing_packages[*]}"
  rm -f /etc/apt/sources.list.d/onlyoffice.list /usr/share/keyrings/onlyoffice.gpg
  export DEBIAN_FRONTEND=noninteractive
  apt-get update
  apt-get install -y "${missing_packages[@]}"
}

deploy_project() {
  log "Deploying project files to $INSTALL_DIR"
  mkdir -p "$INSTALL_DIR"

  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete --exclude '.git' --exclude 'bin' --exclude 'backend/.venv' "$PROJECT_DIR/" "$INSTALL_DIR/"
  else
    local venv_backup=""
    if [[ -d "$INSTALL_DIR/backend/.venv" ]]; then
      venv_backup="$(mktemp -d)/.venv"
      mv "$INSTALL_DIR/backend/.venv" "$venv_backup"
    fi
    find "$INSTALL_DIR" -mindepth 1 -maxdepth 1 ! -name bin -exec rm -rf {} +
    tar --exclude='.git' -C "$PROJECT_DIR" -cf - . | tar -C "$INSTALL_DIR" -xf -
    if [[ -n "$venv_backup" ]]; then
      mv "$venv_backup" "$INSTALL_DIR/backend/.venv"
    fi
  fi
}

prepare_media_paths() {
  log "Preparing media directories"
  mkdir -p "$MEDIA_ROOT/bin/www" "$RECORD_ROOT"
  mkdir -p "$ZLM_CONF_DIR"

  if [[ ! -f "$ZLM_CONF_FILE" ]]; then
    cat > "$ZLM_CONF_FILE" <<EOF
[api]
secret=${ZLM_SECRET}
EOF
    log "Created default ZLMediaKit config at $ZLM_CONF_FILE"
  elif ! grep -q '^secret=' "$ZLM_CONF_FILE"; then
    echo "secret=${ZLM_SECRET}" >> "$ZLM_CONF_FILE"
    log "Appended secret to existing $ZLM_CONF_FILE"
  fi

  ln -sfn "$ZLM_CONF_FILE" "$MEDIA_ROOT/bin/config.ini"
  if [[ -d "$MEDIA_ROOT/bin/www/record" && ! -L "$MEDIA_ROOT/bin/www/record" ]]; then
    if find "$MEDIA_ROOT/bin/www/record" -mindepth 1 -print -quit | grep -q .; then
      log "Migrating MediaServer recordings to $RECORD_ROOT"
      cp -a "$MEDIA_ROOT/bin/www/record/." "$RECORD_ROOT/"
    fi
    rm -rf "$MEDIA_ROOT/bin/www/record"
  fi
  ln -sfn "$RECORD_ROOT" "$MEDIA_ROOT/bin/www/record"
}

install_python_deps() {
  if [[ "$QUICK_DEPLOY" -eq 1 ]]; then
    [[ -x "$INSTALL_DIR/backend/.venv/bin/python" ]] || die "Quick deployment requires an existing backend virtual environment; run without --quick first"
    "$INSTALL_DIR/backend/.venv/bin/python" -c 'import fastapi, uvicorn, apscheduler, httpx, psutil, docker, docx, multipart, sqlite3' || die "Quick deployment found an incomplete backend virtual environment; run without --quick"
    log "Quick deployment: reusing existing Python virtual environment"
    return
  fi
  [[ -x "$SYSTEM_PYTHON" ]] || die "System Python not found: $SYSTEM_PYTHON"
  "$SYSTEM_PYTHON" -c 'import sqlite3' || die "System Python has no sqlite3 support: $SYSTEM_PYTHON"
  local python_version
  python_version="$("$SYSTEM_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  [[ -z "$EXPECTED_PYTHON_VERSION" || "$python_version" == "$EXPECTED_PYTHON_VERSION" ]] || die "Expected Python $EXPECTED_PYTHON_VERSION, but found Python $python_version"
  log "Recreating Python virtual environment with $SYSTEM_PYTHON"
  rm -rf "$INSTALL_DIR/backend/.venv"
  "$SYSTEM_PYTHON" -m venv "$INSTALL_DIR/backend/.venv"
  local pip_options=()
  if [[ -n "$OFFLINE_DIR" ]]; then
    pip_options=(--no-index --find-links "$OFFLINE_DIR/wheels")
  else
    "$INSTALL_DIR/backend/.venv/bin/pip" install --upgrade pip
  fi
  if [[ -n "$PYTHON_RUNTIME_LD_LIBRARY_PATH" ]]; then
    env LD_LIBRARY_PATH="$PYTHON_RUNTIME_LD_LIBRARY_PATH" "$INSTALL_DIR/backend/.venv/bin/pip" install "${pip_options[@]}" \
      fastapi uvicorn apscheduler httpx psutil docker python-multipart python-docx
  else
    "$INSTALL_DIR/backend/.venv/bin/pip" install "${pip_options[@]}" \
      fastapi uvicorn apscheduler httpx psutil docker python-multipart python-docx
  fi
}

write_backend_service() {
  log "Writing systemd service: gsapp.service"
  local runtime_library_environment=""
  local runtime_path_environment=""
  if [[ -n "$PYTHON_RUNTIME_LD_LIBRARY_PATH" ]]; then
    runtime_library_environment="Environment=LD_LIBRARY_PATH=${PYTHON_RUNTIME_LD_LIBRARY_PATH}"
    runtime_path_environment="Environment=PATH=${RUNTIME_DIR}/debian-root/usr/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin"
  fi
  cat > /etc/systemd/system/gsapp.service <<EOF
[Unit]
Description=Management Platform FastAPI Backend
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}/backend
Environment=ZLM_SERVER=${ZLM_SERVER}
Environment=STREAMUI_DB_PATH=${DATA_DIR}/db/gsapp.db
Environment=STREAMUI_ARCHIVE_ROOT=${DATA_DIR}/device_archives
Environment=STREAMUI_RECORD_ROOT=${RECORD_ROOT}
Environment=STREAMUI_ZLM_CONF=${ZLM_CONF_FILE}
Environment=STREAMUI_GB28181_ENABLED=${GB28181_ENABLED}
Environment=STREAMUI_GB28181_SIP_PORT=${GB28181_SIP_PORT}
Environment=STREAMUI_GB28181_SERVER_ID=${GB28181_SERVER_ID}
Environment=STREAMUI_GB28181_REALM=${GB28181_SERVER_ID}
Environment="STREAMUI_GB28181_PASSWORD=${GB28181_PASSWORD}"
${runtime_library_environment}
${runtime_path_environment}
StandardOutput=append:${LOG_DIR}/gsapp.log
StandardError=append:${LOG_DIR}/gsapp.log
ExecStart=${INSTALL_DIR}/backend/.venv/bin/python ${INSTALL_DIR}/backend/main.py
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF
}

write_nginx_conf() {
  if [[ -z "$NGINX_BIN" ]]; then
    NGINX_BIN="$(command -v nginx || true)"
  fi
  [[ -n "$NGINX_BIN" ]] || die "Nginx executable was not found. Install nginx or use an offline bundle with a private runtime."
  if [[ "$NGINX_PRIVATE" -eq 1 ]]; then
    log "Writing private nginx config under $CONFIG_DIR/nginx"
    mkdir -p "$CONFIG_DIR/nginx" "$RUNTIME_DIR/nginx"
    cat > "$CONFIG_DIR/nginx/nginx.conf" <<EOF
worker_processes auto;
error_log ${LOG_DIR}/nginx-error.log;
pid ${RUNTIME_DIR}/nginx/nginx.pid;
events { worker_connections 1024; }
http {
  include ${RUNTIME_DIR}/debian-root/etc/nginx/mime.types;
  default_type application/octet-stream;
  access_log ${LOG_DIR}/nginx-access.log;
  server {
    listen ${HTTP_PORT};
    server_name _;
    root ${INSTALL_DIR}/frontend;
    index index.html;
    location = /login.html { add_header Cache-Control "no-store, no-cache, must-revalidate" always; try_files \$uri =404; }
    location / { try_files \$uri \$uri/ /index.html; }
    location /record/ { alias ${RECORD_ROOT}/; internal; sendfile on; tcp_nopush on; }
    location /api/ { proxy_pass http://127.0.0.1:${API_PORT}; proxy_set_header Host \$host; proxy_set_header X-Real-IP \$remote_addr; proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for; proxy_set_header X-Forwarded-Proto \$scheme; }
    location /openapi.json { proxy_pass http://127.0.0.1:${API_PORT}; }
    location ~ /\.(git|env|ht|svn) { deny all; }
  }
}
EOF
    env LD_LIBRARY_PATH="$PYTHON_RUNTIME_LD_LIBRARY_PATH" "$NGINX_BIN" -t -p "$RUNTIME_DIR/nginx" -c "$CONFIG_DIR/nginx/nginx.conf"
    cat > /etc/systemd/system/gsapp-nginx.service <<EOF
[Unit]
Description=Management Platform Private Nginx
After=network.target
[Service]
Type=forking
PIDFile=${RUNTIME_DIR}/nginx/nginx.pid
ExecStart=${NGINX_BIN} -p ${RUNTIME_DIR}/nginx -c ${CONFIG_DIR}/nginx/nginx.conf
ExecReload=${NGINX_BIN} -s reload
ExecStop=${NGINX_BIN} -s quit
Restart=on-failure
Environment=LD_LIBRARY_PATH=${PYTHON_RUNTIME_LD_LIBRARY_PATH}
[Install]
WantedBy=multi-user.target
EOF
    return
  fi
  log "Writing nginx site config: /etc/nginx/conf.d/gsapp.conf"
  rm -f /etc/nginx/conf.d/streamui.conf
  cat > /etc/nginx/conf.d/gsapp.conf <<EOF
server {
    listen ${HTTP_PORT};
    server_name _;

    root ${INSTALL_DIR}/frontend;
    index index.html;

    location = /login.html {
      add_header Cache-Control "no-store, no-cache, must-revalidate" always;
      try_files \$uri =404;
    }

    location / {
        try_files \$uri \$uri/ /index.html;
    }

    location /record/ {
        alias ${RECORD_ROOT}/;
      internal;
        sendfile on;
        tcp_nopush on;
    }

    location /api/ {
        proxy_pass http://127.0.0.1:${API_PORT};
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }

    location /openapi.json {
        proxy_pass http://127.0.0.1:${API_PORT};
    }

    location ~ /\.(git|env|ht|svn) {
        deny all;
    }
}
EOF
    rm -f /etc/nginx/sites-enabled/default

  "$NGINX_BIN" -t
}

write_zlm_service() {
  log "Writing systemd service: zlmediakit.service"
  cat > /etc/systemd/system/zlmediakit.service <<EOF
[Unit]
Description=ZLMediaKit MediaServer
After=network.target

[Service]
Type=simple
WorkingDirectory=${MEDIA_ROOT}/bin
StandardOutput=append:${LOG_DIR}/zlmediakit.log
StandardError=append:${LOG_DIR}/zlmediakit.log
ExecStart=${MEDIA_ROOT}/bin/MediaServer
Restart=always
RestartSec=3
User=root

[Install]
WantedBy=multi-user.target
EOF
}

build_zlm_if_needed() {
  local media_server_bin="${MEDIA_ROOT}/bin/MediaServer"

  if [[ -x "$media_server_bin" ]]; then
    log "MediaServer already exists: $media_server_bin"
    write_zlm_service
    return
  fi

  if [[ "$ZLM_MODE" == "skip" ]]; then
    warn "Skipping ZLMediaKit install by request (--zlm-mode skip)."
    warn "Ensure an external ZLMediaKit is running and ZLM_SERVER is reachable."
    return
  fi

  if [[ -n "$OFFLINE_DIR" && -x "$OFFLINE_DIR/zlm/MediaServer" ]]; then
    log "Installing prebuilt ZLMediaKit from offline bundle"
    mkdir -p "${MEDIA_ROOT}/bin"
    install -m 0755 "$OFFLINE_DIR/zlm/MediaServer" "$media_server_bin"
    if [[ -d "$OFFLINE_DIR/zlm/www" ]]; then
      mkdir -p "${MEDIA_ROOT}/bin/www"
      cp -a "$OFFLINE_DIR/zlm/www/." "${MEDIA_ROOT}/bin/www/"
    fi
    write_zlm_service
    return
  fi

  if [[ "$ZLM_MODE" == "existing" ]]; then
    die "--zlm-mode existing requested, but ${MEDIA_ROOT}/bin/MediaServer was not found"
  fi

  if [[ "$QUICK_DEPLOY" -eq 1 ]]; then
    die "Quick deployment requires an existing MediaServer binary: ${MEDIA_ROOT}/bin/MediaServer"
  fi

  log "Building ZLMediaKit from source (this may take several minutes)"
  local build_dir
  build_dir="/tmp/ZLMediaKit-build-$$"

  rm -rf "$build_dir"
  git clone --depth=1 https://github.com/ZLMediaKit/ZLMediaKit.git "$build_dir"

  cmake -S "$build_dir" -B "$build_dir/build" -DCMAKE_BUILD_TYPE=Release
  cmake --build "$build_dir/build" -j"$(nproc)"

  local found_bin
  found_bin="$(find "$build_dir" -type f -name MediaServer | head -n 1 || true)"
  [[ -n "$found_bin" ]] || die "Failed to locate MediaServer binary after build"

  mkdir -p "${MEDIA_ROOT}/bin"
  install -m 0755 "$found_bin" "${MEDIA_ROOT}/bin/MediaServer"

  local found_cfg
  found_cfg="$(find "$build_dir" -type f -name config.ini | head -n 1 || true)"
  if [[ -n "$found_cfg" && ! -f "$ZLM_CONF_FILE" ]]; then
    install -m 0644 "$found_cfg" "$ZLM_CONF_FILE"
  fi

  local found_www
  found_www="$(find "$build_dir" -type d -name www | head -n 1 || true)"
  if [[ -n "$found_www" ]]; then
    mkdir -p "${MEDIA_ROOT}/bin/www"
    cp -a "$found_www/." "${MEDIA_ROOT}/bin/www/"
  fi

  if ! grep -q '^secret=' "$ZLM_CONF_FILE"; then
    echo "secret=${ZLM_SECRET}" >> "$ZLM_CONF_FILE"
  fi

  write_zlm_service
  rm -rf "$build_dir"
}

start_services() {
  log "Reloading systemd and starting services"
  if systemctl list-unit-files --no-legend | grep -q '^streamui-backend.service'; then
    log "Removing legacy streamui-backend service"
    systemctl disable --now streamui-backend.service || true
    rm -f /etc/systemd/system/streamui-backend.service
  fi
  if systemctl list-unit-files --no-legend | grep -q '^gsapp-backend.service'; then
    log "Migrating gsapp-backend service to gsapp"
    systemctl disable --now gsapp-backend.service || true
    rm -f /etc/systemd/system/gsapp-backend.service
  fi
  systemctl daemon-reload

  if systemctl list-unit-files --no-legend | grep -q '^gsapp-onlyoffice.service'; then
    log "Removing legacy Docker OnlyOffice service"
    systemctl disable --now gsapp-onlyoffice.service || true
    rm -f /etc/systemd/system/gsapp-onlyoffice.service
  fi
  systemctl disable --now ds-converter ds-docservice ds-metrics 2>/dev/null || true
  if [[ -x "${MEDIA_ROOT}/bin/MediaServer" ]]; then
    systemctl enable zlmediakit.service
    if [[ "$QUICK_DEPLOY" -eq 1 ]]; then
      systemctl start zlmediakit.service
    else
      systemctl restart zlmediakit.service
    fi
  fi

  systemctl enable gsapp.service
  systemctl restart gsapp.service

  if [[ "$NGINX_PRIVATE" -eq 1 ]]; then
    systemctl enable gsapp-nginx.service
    systemctl restart gsapp-nginx.service
  else
    systemctl enable nginx
    systemctl restart nginx
  fi

  log "Service status summary"
  systemctl --no-pager --full status gsapp.service | sed -n '1,12p' || true
  if systemctl list-unit-files | grep -q '^zlmediakit.service'; then
    systemctl --no-pager --full status zlmediakit.service | sed -n '1,12p' || true
  fi
  systemctl --no-pager --full status "$([[ "$NGINX_PRIVATE" -eq 1 ]] && echo gsapp-nginx || echo nginx)" | sed -n '1,12p' || true
}

print_finish_notes() {
  cat <<EOF

Installation finished.

Frontend URL:
  http://<server-ip>:${HTTP_PORT}

Backend API docs:
  http://<server-ip>:${API_PORT}/docs

Important paths:
  Application: ${INSTALL_DIR}
  Data:        ${DATA_DIR}
  Config:      ${CONFIG_DIR}
  Logs:        ${LOG_DIR}
  Upgrade:     ${UPGRADE_DIR}
  Nginx conf:  /etc/nginx/conf.d/gsapp.conf
  Backend svc: /etc/systemd/system/gsapp.service
  Media conf:  ${ZLM_CONF_FILE}
  Record dir:  ${RECORD_ROOT}

Common commands:
  systemctl restart gsapp
  systemctl restart nginx
  systemctl restart zlmediakit
  journalctl -u gsapp -f
  journalctl -u nginx -f
EOF
}

main() {
  require_root
  validate_inputs

  log "Project directory: $PROJECT_DIR"
  log "Software root: $SOFTWARE_ROOT"
  log "Application directory: $INSTALL_DIR"
  log "ZLM mode: $ZLM_MODE"
  log "ZLM server URL for backend: $ZLM_SERVER"

  install_system_packages
  prepare_application_paths
  migrate_legacy_data
  deploy_project
  prepare_media_paths
  install_python_deps
  build_zlm_if_needed
  write_backend_service
  write_nginx_conf
  start_services
  print_finish_notes
}

main "$@"

#!/usr/bin/env bash
set -euo pipefail

IFS=$'\n\t'

log() { echo "[INFO] $*"; }
warn() { echo "[WARN] $*" >&2; }
die() { echo "[ERROR] $*" >&2; exit 1; }

usage() {
  cat <<'EOF'
Usage:
  sudo bash scripts/create_offline_bundle.sh [options]

Options:
  --output <path>    Output directory for the generated .tar.gz bundle (default: /tmp)
  --zlm-bin <path>   Existing ZLMediaKit bin directory (default: /opt/hongmsoft/softapp/bin)
  --platform <name>  Platform name in the bundle filename (default: gsapp)
  -h, --help         Show this help

The source and target machines must use the same Debian/Ubuntu release, CPU architecture,
and Python major/minor version. Run this on a deployed online machine so its ZLMediaKit binary
is bundled for the offline target.
EOF
}

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUTPUT_DIR="/tmp"
ZLM_BIN_DIR="/opt/hongmsoft/softapp/bin"
SYSTEM_PYTHON="/usr/bin/python3"
PLATFORM_NAME="gsapp"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output) OUTPUT_DIR="$2"; shift 2 ;;
    --zlm-bin) ZLM_BIN_DIR="$2"; shift 2 ;;
    --platform) PLATFORM_NAME="$2"; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Unknown argument: $1" ;;
  esac
done

[[ "${EUID}" -eq 0 ]] || die "Please run as root (use sudo)."
[[ "$PLATFORM_NAME" =~ ^[A-Za-z0-9][A-Za-z0-9._-]*$ ]] || die "--platform may only contain letters, numbers, dot, underscore, and hyphen"
[[ -x "$SYSTEM_PYTHON" ]] || die "System Python not found: $SYSTEM_PYTHON"
[[ -x "$ZLM_BIN_DIR/MediaServer" ]] || die "MediaServer not found: $ZLM_BIN_DIR/MediaServer"
[[ -d "$ZLM_BIN_DIR/www" ]] || die "ZLMediaKit www directory not found: $ZLM_BIN_DIR/www"
dpkg-query -W -f='${Status}' onlyoffice-documentserver 2>/dev/null | grep -q 'install ok installed' || die "OnlyOffice Document Server must be installed on the online bundle source"

ARCH="$(dpkg --print-architecture)"
CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-unknown}")"
STAMP="$(date +%Y%m%d-%H%M%S)"
BUNDLE_NAME="${PLATFORM_NAME}-offline-${CODENAME}-${ARCH}-${STAMP}"
STAGE_DIR="$(mktemp -d)"
ROOT_DIR="$STAGE_DIR/$BUNDLE_NAME"
PAYLOAD_DIR="$ROOT_DIR/payload"

cleanup() { rm -rf "$STAGE_DIR"; }
trap cleanup EXIT

mkdir -p "$PAYLOAD_DIR/debs" "$PAYLOAD_DIR/onlyoffice/debs" "$PAYLOAD_DIR/onlyoffice/corefonts" "$PAYLOAD_DIR/wheels" "$PAYLOAD_DIR/python-runtime/debs" "$PAYLOAD_DIR/zlm/www" "$OUTPUT_DIR"

log "Refreshing package metadata and installing package dependency resolver"
export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y apt-rdepends

SYSTEM_PACKAGES=(
  ca-certificates
  curl
  ffmpeg
  nginx
  python3
  python3-venv
  python3-pip
)

mapfile -t ZLM_LIBRARIES < <(
  ldd "$ZLM_BIN_DIR/MediaServer" \
    | awk '/=> \/[^ ]+/ { print $3 } /^\// { print $1 }' \
    | sort -u
)
for library in "${ZLM_LIBRARIES[@]}"; do
  package="$(dpkg-query -S "$library" 2>/dev/null | sed -n '1s/: .*$//p')"
  [[ -n "$package" ]] && SYSTEM_PACKAGES+=("$package")
done
mapfile -t SYSTEM_PACKAGES < <(printf '%s\n' "${SYSTEM_PACKAGES[@]}" | sort -u)

log "Collecting Debian packages and transitive dependencies"
mapfile -t DEB_PACKAGES < <(
  apt-rdepends --follow=DEPENDS,PREDEPENDS "${SYSTEM_PACKAGES[@]}" 2>/dev/null \
    | awk '/^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$/ { print }' \
    | sort -u
)

pushd "$PAYLOAD_DIR/debs" >/dev/null
for package in "${DEB_PACKAGES[@]}"; do
  if ! apt-get download "$package"; then
    warn "Unable to download optional or virtual package: $package"
  fi
done
popd >/dev/null

cp -a "$PAYLOAD_DIR/debs/." "$PAYLOAD_DIR/python-runtime/debs/"

for package in "${SYSTEM_PACKAGES[@]}"; do
  package_base="${package%%:*}"
  compgen -G "$PAYLOAD_DIR/debs/${package_base}_*.deb" >/dev/null || die "Required package was not downloaded: $package"
done

log "Collecting OnlyOffice Document Server packages and transitive dependencies"
mapfile -t ONLYOFFICE_DEB_PACKAGES < <(
  apt-rdepends --follow=DEPENDS,PREDEPENDS onlyoffice-documentserver 2>/dev/null \
    | awk '/^[a-z0-9][a-z0-9+.-]*(:[a-z0-9-]+)?$/ { print }' \
    | sort -u
)
[[ " ${ONLYOFFICE_DEB_PACKAGES[*]} " == *" onlyoffice-documentserver "* ]] || die "Unable to resolve OnlyOffice Document Server dependencies"
pushd "$PAYLOAD_DIR/onlyoffice/debs" >/dev/null
for package in "${ONLYOFFICE_DEB_PACKAGES[@]}"; do
  if ! apt-get download "$package"; then
    die "Unable to download required OnlyOffice package: $package"
  fi
done
popd >/dev/null
compgen -G "$PAYLOAD_DIR/onlyoffice/debs/onlyoffice-documentserver_*.deb" >/dev/null || die "OnlyOffice Document Server package was not downloaded"

log "Copying cached Microsoft core-font installers"
font_cache_dir="/usr/share/package-data-downloads"
compgen -G "$font_cache_dir/*.exe" >/dev/null || die "Core-font installer cache is missing in $font_cache_dir"
install -m 0644 "$font_cache_dir"/*.exe "$PAYLOAD_DIR/onlyoffice/corefonts/"

log "Downloading Python wheels"
"$SYSTEM_PYTHON" -m pip download --only-binary=:all: --dest "$PAYLOAD_DIR/wheels" \
  fastapi \
  uvicorn \
  apscheduler \
  httpx \
  psutil \
  docker \
  python-multipart

log "Copying ZLMediaKit runtime"
install -m 0755 "$ZLM_BIN_DIR/MediaServer" "$PAYLOAD_DIR/zlm/MediaServer"
tar --exclude='./record' -C "$ZLM_BIN_DIR/www" -cf - . | tar -C "$PAYLOAD_DIR/zlm/www" -xf -

log "Packaging application source"
tar \
  --exclude='.git' \
  --exclude='backend/.venv' \
  -C "$PROJECT_DIR" \
  -czf "$PAYLOAD_DIR/app.tar.gz" .

install -m 0755 "$PROJECT_DIR/scripts/install_offline_gsapp.sh" "$ROOT_DIR/install_offline_gsapp.sh"
cat > "$PAYLOAD_DIR/platform.env" <<EOF
PLATFORM_NAME=${PLATFORM_NAME}
ARCH=${ARCH}
CODENAME=${CODENAME}
PYTHON_VERSION=$($SYSTEM_PYTHON -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
EOF
cat > "$ROOT_DIR/MANIFEST.txt" <<EOF
Bundle: ${BUNDLE_NAME}
Platform: ${PLATFORM_NAME}
Generated: $(date -Is)
Source OS: $(. /etc/os-release && echo "${PRETTY_NAME}")
Architecture: ${ARCH}
Python: $($SYSTEM_PYTHON --version)
ZLMediaKit: ${ZLM_BIN_DIR}/MediaServer
OnlyOffice: bundled native packages and core-font installers
EOF

(cd "$ROOT_DIR" && find payload -type f -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS)

OUTPUT_FILE="$OUTPUT_DIR/${BUNDLE_NAME}.tar.gz"
tar -C "$STAGE_DIR" -czf "$OUTPUT_FILE" "$BUNDLE_NAME"
log "Offline bundle created: $OUTPUT_FILE"
log "Copy this file to the offline machine and follow README.md."
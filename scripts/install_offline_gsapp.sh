#!/usr/bin/env bash
set -euo pipefail

IFS=$'\n\t'

log() { echo "[INFO] $*"; }
die() { echo "[ERROR] $*" >&2; exit 1; }

[[ "${EUID}" -eq 0 ]] || die "Please run as root (use sudo)."

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PAYLOAD_DIR="$SCRIPT_DIR/payload"
APP_DIR="$(mktemp -d)"

cleanup() { rm -rf "$APP_DIR"; }
trap cleanup EXIT

[[ -f "$PAYLOAD_DIR/app.tar.gz" ]] || die "Application archive not found: $PAYLOAD_DIR/app.tar.gz"
[[ -f "$PAYLOAD_DIR/platform.env" ]] || die "Bundle platform metadata not found: $PAYLOAD_DIR/platform.env"
[[ -d "$PAYLOAD_DIR/debs" ]] || die "Debian package directory not found: $PAYLOAD_DIR/debs"
[[ -d "$PAYLOAD_DIR/onlyoffice/debs" ]] || die "OnlyOffice package directory not found: $PAYLOAD_DIR/onlyoffice/debs"
[[ -d "$PAYLOAD_DIR/onlyoffice/corefonts" ]] || die "OnlyOffice core-font cache directory not found: $PAYLOAD_DIR/onlyoffice/corefonts"
[[ -d "$PAYLOAD_DIR/wheels" ]] || die "Python wheel directory not found: $PAYLOAD_DIR/wheels"
[[ -x "$PAYLOAD_DIR/zlm/MediaServer" ]] || die "ZLMediaKit binary not found: $PAYLOAD_DIR/zlm/MediaServer"
[[ -f "$SCRIPT_DIR/SHA256SUMS" ]] || die "Bundle checksum file not found: $SCRIPT_DIR/SHA256SUMS"

# The bundle is architecture and distribution specific because it contains .deb packages and MediaServer.
source "$PAYLOAD_DIR/platform.env"
TARGET_ARCH="$(dpkg --print-architecture)"
TARGET_CODENAME="$(. /etc/os-release && echo "${VERSION_CODENAME:-unknown}")"
[[ "$TARGET_ARCH" == "$ARCH" ]] || die "Bundle architecture is $ARCH, but target architecture is $TARGET_ARCH"
[[ "$TARGET_CODENAME" == "$CODENAME" ]] || die "Bundle distribution is $CODENAME, but target distribution is $TARGET_CODENAME"

log "Verifying bundle checksums for ${PLATFORM_NAME}"
(cd "$SCRIPT_DIR" && sha256sum -c SHA256SUMS)

log "Extracting application source"
tar -C "$APP_DIR" -xzf "$PAYLOAD_DIR/app.tar.gz"

log "Installing from offline payload"
# By default this preserves the target's system Python, Nginx, and FFmpeg. Append
# --install-system-deps only when package installation or upgrades are approved.
bash "$APP_DIR/scripts/install_gsapp.sh" \
  --project-dir "$APP_DIR" \
  --offline-dir "$PAYLOAD_DIR" \
  --expected-python-version "$PYTHON_VERSION" \
  "$@"
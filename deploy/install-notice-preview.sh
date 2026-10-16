#!/usr/bin/env bash
# Run as root from a trusted checkout on Ubuntu 22.04/systemd 249 or later.
set -euo pipefail

if [[ "$(id -u)" != 0 ]]; then
    echo "Run this installer as root." >&2
    exit 1
fi
project_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
test -f "$project_dir/scripts/render_notice_preview.py"
test -d /run/systemd/system

export DEBIAN_FRONTEND=noninteractive NEEDRESTART_MODE=l
apt-get update -qq
apt-get install -y --no-install-recommends libreoffice-impress poppler-utils fonts-nanum
if ! getent passwd vicpreview >/dev/null; then
    useradd --system --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin vicpreview
fi
test "$(id -u vicpreview)" != 0
install -d -o root -g root -m 0711 /var/lib/vicabc-preview /var/lib/vicabc-preview/work
install -d -o root -g root -m 0755 /opt/vicabc-preview
install -o root -g root -m 0644 "$project_dir/scripts/render_notice_preview.py" /opt/vicabc-preview/render_notice_preview.py
echo "Worker installed. Apply app files and Nginx notices snippet, then reload workers."

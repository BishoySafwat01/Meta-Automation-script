#!/usr/bin/env bash
# ==============================================================================
# Meta Automation Hub (Apple Prismatic Glass Edition V6.3.4)
# Linux Desktop Launcher
# ==============================================================================

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=============================================================================="
echo "  ⚡ Meta Business Suite Automation - Desktop Control Center V6.3.4"
echo "  Apple Prismatic Glass Edition (Linux Launcher)"
echo "=============================================================================="

# 1. Check Python 3
if ! command -v python3 &>/dev/null; then
  echo "❌ Error: python3 is not installed on this system."
  exit 1
fi

# 2. Check pywebview dependency
if ! python3 -c "import webview" &>/dev/null; then
  echo "📦 Installing pywebview dependency..."
  pip install --break-system-packages pywebview || pip install pywebview
fi

# 3. Launch Desktop App
echo "🚀 Launching Desktop Control Center..."
exec python3 desktop_app.py "$@"

#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "✦ Installing Antigravity Quota Widget for KDE Plasma / Linux Desktop..."

# 1. Install application icon
mkdir -p ~/.local/share/icons/hicolor/scalable/apps
cp "$SCRIPT_DIR/resources/icon.svg" ~/.local/share/icons/hicolor/scalable/apps/gemini-quota-widget.svg

# 2. Generate and install .desktop file
mkdir -p ~/.local/share/applications
cat << DESKTOP_EOF > ~/.local/share/applications/gemini-quota-widget.desktop
[Desktop Entry]
Type=Application
Version=1.0
Name=Antigravity Quota Widget
GenericName=AI Quota Monitor
Comment=Real-time Google Antigravity & Gemini quota monitor widget
Exec=$SCRIPT_DIR/main.py
Path=$SCRIPT_DIR
Icon=gemini-quota-widget
Terminal=false
Categories=Utility;Monitor;
Keywords=antigravity;gemini;quota;token;ai;google;
StartupNotify=true
StartupWMClass=gemini-quota-widget
DESKTOP_EOF

chmod +x ~/.local/share/applications/gemini-quota-widget.desktop

# 3. Update desktop and icon databases
update-desktop-database ~/.local/share/applications/ 2>/dev/null || true
gtk-update-icon-cache ~/.local/share/icons/hicolor/ 2>/dev/null || true

# 4. Rebuild KDE Plasma sycoca cache if available
if command -v kbuildsycoca6 >/dev/null 2>&1; then
    kbuildsycoca6 --noincremental 2>/dev/null || true
elif command -v kbuildsycoca5 >/dev/null 2>&1; then
    kbuildsycoca5 --noincremental 2>/dev/null || true
fi

echo "✔ Successfully registered! You can now find 'Antigravity Quota Widget' in Kickoff (Application Launcher) and KRunner (Alt+Space)."

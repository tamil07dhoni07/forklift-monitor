#!/bin/bash
if [ "$(id -u)" != "0" ]; then
    echo "Please run with sudo: sudo ./install.sh"
    exit 1
fi
ORIGINAL_USER=${SUDO_USER:-$USER}
HOME_DIR=$(eval echo ~$ORIGINAL_USER)
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Installing Forklift Monitor for: $ORIGINAL_USER"
mkdir -p /usr/local/share/forklift-monitor/web/templates
mkdir -p /usr/local/share/forklift-monitor/web/static
mkdir -p /usr/local/share/forklift-monitor/lib
mkdir -p /usr/local/share/forklift-monitor/icons
mkdir -p /usr/local/share/forklift-monitor/logs
mkdir -p /usr/local/bin
mkdir -p /usr/local/share/applications

[ -d "$SCRIPT_DIR/web/templates" ] && cp -r "$SCRIPT_DIR/web/templates/"* /usr/local/share/forklift-monitor/web/templates/
[ -d "$SCRIPT_DIR/web/static" ] && cp -r "$SCRIPT_DIR/web/static/"* /usr/local/share/forklift-monitor/web/static/
[ -d "$SCRIPT_DIR/lib" ] && cp "$SCRIPT_DIR/lib/"*.py /usr/local/share/forklift-monitor/lib/
[ -d "$SCRIPT_DIR/icons" ] && cp -r "$SCRIPT_DIR/icons/"* /usr/local/share/forklift-monitor/icons/
[ -f "$SCRIPT_DIR/bin/forklift-monitor" ] && cp "$SCRIPT_DIR/bin/forklift-monitor" /usr/local/bin/ && chmod +x /usr/local/bin/forklift-monitor
[ -f "$SCRIPT_DIR/forklift-monitor.desktop" ] && cp "$SCRIPT_DIR/forklift-monitor.desktop" /usr/local/share/applications/ && cp "$SCRIPT_DIR/forklift-monitor.desktop" "$HOME_DIR/Desktop/" && chmod +x "$HOME_DIR/Desktop/forklift-monitor.desktop"

chown -R $ORIGINAL_USER:$ORIGINAL_USER /usr/local/share/forklift-monitor 2>/dev/null || true
pip3 install flask flask-cors psycopg2-binary minimalmodbus --user 2>/dev/null
echo "Installation complete! Double-click desktop icon to launch."

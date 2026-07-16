#!/bin/bash

set -uo pipefail

#=========================================================
# Restore Desktop View - reverses the Forklift kiosk setup
#=========================================================

TARGET_USER="linaro"
TARGET_HOME="/home/linaro"
PROJECT_DIR="/home/linaro/forklift-monitor"
LOG_FILE="/var/log/forklift-restore-desktop.log"

COLOR_GREEN="\033[1;32m"
COLOR_YELLOW="\033[1;33m"
COLOR_RED="\033[1;31m"
COLOR_RESET="\033[0m"

log_success() { echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} $1" | tee -a "$LOG_FILE"; }
log_warning() { echo -e "${COLOR_YELLOW}[WARNING]${COLOR_RESET} $1" | tee -a "$LOG_FILE"; }
log_error()   { echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1" | tee -a "$LOG_FILE"; }
log_info()    { echo -e "${COLOR_GREEN}[INFO]${COLOR_RESET} $1" | tee -a "$LOG_FILE"; }

if [[ $EUID -ne 0 ]]; then
    echo -e "${COLOR_RED}This script must be run as root. Use: sudo ./restore-desktop.sh${COLOR_RESET}"
    exit 1
fi

touch "$LOG_FILE"
log_info "===== Restoring normal desktop view ====="

#=========================================================
# 1. Stop and disable the kiosk dashboard service
#=========================================================
log_info "Stopping forklift.service (dashboard app)..."

if systemctl list-unit-files | grep -q "forklift.service"; then
    systemctl stop forklift.service >>"$LOG_FILE" 2>&1
    systemctl disable forklift.service >>"$LOG_FILE" 2>&1
    log_success "forklift.service stopped and disabled. It will not auto-launch on boot."
else
    log_warning "forklift.service not found, skipping."
fi

#=========================================================
# 2. Keep autologin enabled (no login screen) - just remove kiosk restrictions
#=========================================================
log_info "Keeping autologin enabled (no login screen will be shown)..."

AUTOLOGIN_CONF="/etc/lightdm/lightdm.conf.d/50-autologin.conf"

if [[ -f "$AUTOLOGIN_CONF" ]]; then
    log_success "Autologin config left in place. Board will boot straight to desktop, no login screen."
else
    log_warning "No autologin config found. Login screen may still appear until install.sh is re-run."
fi

#=========================================================
# 3. Restore Openbox autostart to a plain, non-kiosk default
#=========================================================
log_info "Restoring default Openbox autostart..."

OPENBOX_DIR="$TARGET_HOME/.config/openbox"
AUTOSTART_FILE="$OPENBOX_DIR/autostart"

if [[ -f "$AUTOSTART_FILE" ]]; then
    mv "$AUTOSTART_FILE" "${AUTOSTART_FILE}.kiosk.bak"
    log_success "Kiosk autostart backed up to ${AUTOSTART_FILE}.kiosk.bak"
fi

cat > "$AUTOSTART_FILE" <<'EOF'
# Default Openbox autostart (kiosk mode disabled)
xsetroot -solid "#303030" &
EOF

if [[ -f "$OPENBOX_DIR/rc.xml" ]]; then
    mv "$OPENBOX_DIR/rc.xml" "$OPENBOX_DIR/rc.xml.kiosk.bak"
    log_success "Kiosk rc.xml backed up to $OPENBOX_DIR/rc.xml.kiosk.bak (Openbox will use its default config)."
fi

chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config"
log_success "Openbox restored to default (no forced fullscreen, no forced decor removal)."

#=========================================================
# 4. Optionally stop the camera streamer too
#=========================================================
read -rp "Also stop the camera streaming service (mjpg-streamer)? [y/N]: " STOP_CAMERA
if [[ "$STOP_CAMERA" =~ ^[Yy]$ ]]; then
    systemctl stop mjpg-streamer.service >>"$LOG_FILE" 2>&1
    systemctl disable mjpg-streamer.service >>"$LOG_FILE" 2>&1
    log_success "mjpg-streamer service stopped and disabled."
else
    log_info "Leaving mjpg-streamer service running."
fi

#=========================================================
# Finish
#=========================================================
log_success "===== Desktop view restored ====="
echo ""
echo -e "${COLOR_GREEN}Desktop view restored.${COLOR_RESET}"
echo "On next reboot you will boot straight to the desktop (no login screen) with the kiosk app disabled."
echo ""
echo "To re-enable kiosk mode later, simply re-run install.sh, or manually restore the backups:"
echo "  sudo mv ${AUTOSTART_FILE}.kiosk.bak ${AUTOSTART_FILE}"
echo "  sudo mv $OPENBOX_DIR/rc.xml.kiosk.bak $OPENBOX_DIR/rc.xml"
echo "  sudo systemctl enable forklift.service"
echo ""
read -rp "Reboot now to apply changes? [y/N]: " DO_REBOOT
if [[ "$DO_REBOOT" =~ ^[Yy]$ ]]; then
    log_info "Rebooting..."
    reboot
else
    log_info "Reboot skipped. Changes will apply on your next manual reboot."
fi
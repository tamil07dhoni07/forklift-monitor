#!/bin/bash

set -uo pipefail

#=========================================================
# Forklift Monitoring System - Installer
# Target: Rockchip RK3568 EVB1 DDR4 V10 (Linaro Ubuntu)
#=========================================================

PROJECT_NAME="Forklift Monitoring System"
TARGET_USER="linaro"
TARGET_HOME="/home/linaro"
PROJECT_DIR="/home/linaro/forklift-monitor"
REPO_URL="https://github.com/tamil07dhoni07/forklift-monitor.git"
MJPG_DIR="/home/linaro/mjpg-streamer"
MJPG_REPO="https://github.com/jacksonliam/mjpg-streamer.git"
LOG_FILE="/var/log/forklift-install.log"

#=========================================================
# Colors / Logging
#=========================================================
COLOR_GREEN="\033[1;32m"
COLOR_YELLOW="\033[1;33m"
COLOR_RED="\033[1;31m"
COLOR_RESET="\033[0m"

log_success() {
    echo -e "${COLOR_GREEN}[SUCCESS]${COLOR_RESET} $1" | tee -a "$LOG_FILE"
}

log_warning() {
    echo -e "${COLOR_YELLOW}[WARNING]${COLOR_RESET} $1" | tee -a "$LOG_FILE"
}

log_error() {
    echo -e "${COLOR_RED}[ERROR]${COLOR_RESET} $1" | tee -a "$LOG_FILE"
}

log_info() {
    echo -e "${COLOR_GREEN}[INFO]${COLOR_RESET} $1" | tee -a "$LOG_FILE"
}

run_step() {
    local description="$1"
    shift
    log_info "Starting: $description"
    if "$@"; then
        log_success "$description completed."
    else
        log_error "$description FAILED."
    fi
}

#=========================================================
# 1. Root check
#=========================================================
if [[ $EUID -ne 0 ]]; then
    echo -e "${COLOR_RED}This installer must be run as root. Use: sudo ./install.sh${COLOR_RESET}"
    exit 1
fi

touch "$LOG_FILE"
log_info "===== $PROJECT_NAME Installation Started ====="

#=========================================================
# 2. Network check / WiFi setup
#=========================================================
check_internet() {
    if ping -c 1 -W 3 8.8.8.8 &>/dev/null; then
        return 0
    else
        return 1
    fi
}

setup_wifi() {
    log_warning "No internet connection detected."

    if ! command -v nmcli &>/dev/null; then
        log_info "Installing NetworkManager..."
        apt update -y >>"$LOG_FILE" 2>&1
        apt install -y network-manager >>"$LOG_FILE" 2>&1
        systemctl enable NetworkManager >>"$LOG_FILE" 2>&1
        systemctl start NetworkManager >>"$LOG_FILE" 2>&1
        sleep 3
    fi

    read -rp "Enter WiFi SSID: " WIFI_SSID
    read -rsp "Enter WiFi Password: " WIFI_PASSWORD
    echo ""

    log_info "Connecting to WiFi network: $WIFI_SSID ..."
    nmcli radio wifi on >>"$LOG_FILE" 2>&1
    sleep 2
    nmcli device wifi rescan >>"$LOG_FILE" 2>&1
    sleep 2
    nmcli device wifi connect "$WIFI_SSID" password "$WIFI_PASSWORD" >>"$LOG_FILE" 2>&1

    sleep 5

    if check_internet; then
        log_success "WiFi connected successfully."
    else
        log_error "Failed to connect to WiFi. Please check credentials and try again."
        exit 1
    fi
}

if check_internet; then
    log_success "Internet connection detected."
else
    setup_wifi
fi

#=========================================================
# 3. System update / upgrade
#=========================================================
run_step "apt update" apt update -y
run_step "apt upgrade" apt upgrade -y

#=========================================================
# 4. Install required packages
#=========================================================
log_info "Installing required system packages..."

PACKAGE_LIST=(
    git
    curl
    wget
    build-essential
    cmake
    make
    gcc
    g++
    pkg-config
    ffmpeg
    gstreamer1.0-tools
    gstreamer1.0-plugins-base
    gstreamer1.0-plugins-good
    gstreamer1.0-plugins-bad
    gstreamer1.0-plugins-ugly
    v4l-utils
    i2c-tools
    python3
    python3-pip
    python3-dev
    python3-setuptools
    python3-wheel
    python3-venv
    python3-gi
    python3-gi-cairo
    gir1.2-gtk-3.0
    gir1.2-webkit2-4.0
    libgtk-3-dev
    libwebkit2gtk-4.0-dev
    libjpeg-dev
    libv4l-dev
    libevent-dev
    network-manager
    lightdm
    openbox
    unclutter
    xinit
    xserver-xorg
    x11-xserver-utils
    postgresql
    postgresql-contrib
)

apt install -y "${PACKAGE_LIST[@]}" >>"$LOG_FILE" 2>&1

FAILED_PACKAGES=()
for pkg in "${PACKAGE_LIST[@]}"; do
    if ! dpkg -s "$pkg" &>/dev/null; then
        log_warning "Package $pkg not yet installed, retrying individually..."
        if apt install -y "$pkg" >>"$LOG_FILE" 2>&1; then
            log_success "$pkg installed."
        else
            log_error "$pkg FAILED to install (package name may not exist on this OS release)."
            FAILED_PACKAGES+=("$pkg")
        fi
    fi
done

if [[ ${#FAILED_PACKAGES[@]} -eq 0 ]]; then
    log_success "All required packages installed."
else
    log_warning "The following packages could not be installed: ${FAILED_PACKAGES[*]}"
    log_warning "Check package names against your OS release (run: lsb_release -a) and install manually if needed."
fi

#=========================================================
# 5. PostgreSQL setup
#=========================================================
log_info "Configuring PostgreSQL..."

systemctl enable postgresql >>"$LOG_FILE" 2>&1
systemctl restart postgresql >>"$LOG_FILE" 2>&1

log_info "Waiting for PostgreSQL to become ready..."
PG_READY=0
for i in $(seq 1 15); do
    if pg_isready -q; then
        PG_READY=1
        break
    fi
    sleep 2
done

if [[ "$PG_READY" -eq 1 ]]; then
    sudo -u postgres psql -c "ALTER USER postgres PASSWORD 'root';" >>"$LOG_FILE" 2>&1
    if [[ $? -eq 0 ]]; then
        log_success "PostgreSQL configured and password set."
    else
        log_error "Failed to configure PostgreSQL password."
    fi
else
    log_error "PostgreSQL did not become ready in time. Password not set."
fi

#=========================================================
# 6. Python packages
#=========================================================
log_info "Upgrading pip and installing Python packages..."

python3 -m pip install --upgrade pip >>"$LOG_FILE" 2>&1

PYTHON_PACKAGES=(
    Flask
    Flask-Cors
    requests
    schedule
    numpy
    Pillow
    psutil
    pyserial
    minimalmodbus
    psycopg2-binary
    smbus
	PyQt5
)

PIP_OK=0
for attempt in 1 2 3; do
    if python3 -m pip install --break-system-packages "${PYTHON_PACKAGES[@]}" >>"$LOG_FILE" 2>&1; then
        PIP_OK=1
        break
    fi
    if python3 -m pip install "${PYTHON_PACKAGES[@]}" >>"$LOG_FILE" 2>&1; then
        PIP_OK=1
        break
    fi
    log_warning "pip install attempt $attempt failed, retrying in 5s..."
    sleep 5
done

if [[ "$PIP_OK" -eq 1 ]]; then
    log_success "Python packages installed."
else
    log_error "Failed to install one or more Python packages after 3 attempts."
fi

#=========================================================
# 7. Clone / update repository
#=========================================================
log_info "Setting up project repository..."
export GIT_TERMINAL_PROMPT=0

if [[ -d "$PROJECT_DIR/.git" ]]; then
    log_info "Repository already exists. Resetting and pulling latest changes."
    cd "$PROJECT_DIR" || exit 1
    sudo -u "$TARGET_USER" GIT_TERMINAL_PROMPT=0 git reset --hard >>"$LOG_FILE" 2>&1
    sudo -u "$TARGET_USER" GIT_TERMINAL_PROMPT=0 git pull >>"$LOG_FILE" 2>&1
else
    log_info "Cloning repository..."
    sudo -u "$TARGET_USER" GIT_TERMINAL_PROMPT=0 git clone "$REPO_URL" "$PROJECT_DIR" >>"$LOG_FILE" 2>&1
fi

if [[ -d "$PROJECT_DIR" ]]; then
    log_success "Repository ready at $PROJECT_DIR"
else
    log_error "Failed to clone repository."
    exit 1
fi

#=========================================================
# 8. Ownership / Permissions
#=========================================================
log_info "Setting ownership and permissions..."

chown -R "$TARGET_USER:$TARGET_USER" "$PROJECT_DIR"
chmod -R 755 "$PROJECT_DIR"

log_success "Ownership and permissions set."

#=========================================================
# MJPG-Streamer
#=========================================================
log_info "Installing MJPG-Streamer..."

if [[ ! -d "$MJPG_DIR" ]]; then
    sudo -u "$TARGET_USER" git clone "$MJPG_REPO" "$MJPG_DIR" >>"$LOG_FILE" 2>&1
else
    cd "$MJPG_DIR" || exit 1
    sudo -u "$TARGET_USER" git pull >>"$LOG_FILE" 2>&1
fi

cd "$MJPG_DIR/mjpg-streamer-experimental" || {
    log_error "mjpg-streamer source directory not found."
}

if [[ -d "$MJPG_DIR/mjpg-streamer-experimental" ]]; then
    make clean >>"$LOG_FILE" 2>&1
    make >>"$LOG_FILE" 2>&1
    make install >>"$LOG_FILE" 2>&1

    if [[ $? -eq 0 ]]; then
        log_success "MJPG-Streamer compiled and installed."
    else
        log_error "MJPG-Streamer compilation failed."
    fi
fi

# systemd service for mjpg-streamer
cat > /etc/systemd/system/mjpg-streamer.service <<EOF
[Unit]
Description=MJPG Streamer Camera Service
After=network.target

[Service]
Type=simple
Restart=always
RestartSec=2
WorkingDirectory=$MJPG_DIR/mjpg-streamer-experimental
ExecStart=$MJPG_DIR/mjpg-streamer-experimental/mjpg_streamer -i "input_uvc.so -d /dev/video10 -r 1280x720 -f 30" -o "output_http.so -p 8080 -w $MJPG_DIR/mjpg-streamer-experimental/www"
User=root

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable mjpg-streamer.service >>"$LOG_FILE" 2>&1
systemctl restart mjpg-streamer.service >>"$LOG_FILE" 2>&1

log_success "MJPG-Streamer service enabled and started on port 8080."

#=========================================================
# LightDM Autologin Configuration
#=========================================================
log_info "Configuring LightDM autologin..."

mkdir -p /etc/lightdm/lightdm.conf.d

cat > /etc/lightdm/lightdm.conf.d/50-autologin.conf <<EOF
[Seat:*]
autologin-user=$TARGET_USER
autologin-user-timeout=0
autologin-session=openbox
greeter-hide-users=true
greeter-show-manual-login=false
allow-guest=false
EOF

if [[ -f /etc/lightdm/lightdm.conf ]]; then
    sed -i '/^\[Seat:\*\]/,/^\[/{/autologin-user=/d}' /etc/lightdm/lightdm.conf 2>/dev/null
fi

systemctl enable lightdm >>"$LOG_FILE" 2>&1
systemctl set-default graphical.target >>"$LOG_FILE" 2>&1

log_success "LightDM autologin configured for user $TARGET_USER."

#=========================================================
# Openbox Autostart / Kiosk Mode
#=========================================================
log_info "Configuring Openbox kiosk environment..."

OPENBOX_DIR="$TARGET_HOME/.config/openbox"
mkdir -p "$OPENBOX_DIR"

cat > "$OPENBOX_DIR/autostart" <<EOF
xset s off &
xset -dpms &
xset s noblank &
unclutter -idle 5 -jitter 5 &

while true; do
    python3 /home/linaro/forklift-monitor/lib/webview_app.py >> /home/linaro/forklift-monitor/webview.log 2>&1
    echo "\$(date): webview_app.py exited, restarting in 2s..." >> /home/linaro/forklift-monitor/webview.log
    sleep 2
done &
EOF

cat > "$OPENBOX_DIR/rc.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<openbox_config xmlns="http://openbox.org/3.4/rc">
  <desktops>
    <number>1</number>
  </desktops>
  <applications>
    <application class="*">
      <decor>no</decor>
      <maximized>yes</maximized>
      <fullscreen>yes</fullscreen>
    </application>
  </applications>
</openbox_config>
EOF

chown -R "$TARGET_USER:$TARGET_USER" "$TARGET_HOME/.config"
chmod +x "$OPENBOX_DIR/autostart"

log_success "Openbox kiosk mode configured (no panels, no wallpaper, no screensaver, cursor hidden, fullscreen only)."

#=========================================================
# Boot-time auto-update script (runs before forklift.service starts)
#=========================================================
log_info "Creating boot-time auto-update script..."

cat > "$PROJECT_DIR/boot-update.sh" <<EOF
#!/bin/bash
# Runs on every boot before the dashboard starts.
# Pulls latest code if internet is available; otherwise skips silently.

cd $PROJECT_DIR || exit 0

if timeout 3 ping -c 1 -W 2 8.8.8.8 &>/dev/null; then
    echo "\$(date): Internet available, pulling latest code..." >> "$PROJECT_DIR/boot-update.log"
    git fetch --all >> "$PROJECT_DIR/boot-update.log" 2>&1
    git reset --hard origin/main >> "$PROJECT_DIR/boot-update.log" 2>&1 \\
        || git reset --hard origin/master >> "$PROJECT_DIR/boot-update.log" 2>&1
    echo "\$(date): Update check complete." >> "$PROJECT_DIR/boot-update.log"
else
    echo "\$(date): No internet, skipping update." >> "$PROJECT_DIR/boot-update.log"
fi

exit 0
EOF

chmod +x "$PROJECT_DIR/boot-update.sh"
chown "$TARGET_USER:$TARGET_USER" "$PROJECT_DIR/boot-update.sh"

log_success "boot-update.sh created at $PROJECT_DIR/boot-update.sh"

#=========================================================
# systemd service for the dashboard application
#=========================================================
log_info "Creating forklift.service..."

cat > /etc/systemd/system/forklift.service <<EOF
[Unit]
Description=Forklift Monitoring
After=network-online.target postgresql.service mjpg-streamer.service
Wants=network-online.target

[Service]
Type=simple
Restart=always
RestartSec=2
WorkingDirectory=$PROJECT_DIR
User=$TARGET_USER
ExecStartPre=-/bin/bash $PROJECT_DIR/boot-update.sh
ExecStart=/usr/bin/python3 $PROJECT_DIR/lib/webview_app.py

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable forklift.service >>"$LOG_FILE" 2>&1

log_success "forklift.service created and enabled."

#=========================================================
# Camera verification
#=========================================================
log_info "Verifying camera device..."

if [[ -e /dev/video10 ]]; then
    log_success "Camera device /dev/video10 detected."
else
    log_warning "Camera device /dev/video10 not found. Please check hardware connection."
fi

if systemctl is-active --quiet mjpg-streamer.service; then
    log_success "MJPG-Streamer service is running."
else
    log_warning "MJPG-Streamer service is not active."
fi

#=========================================================
# update.sh script
#=========================================================
log_info "Creating update.sh script..."

cat > "$PROJECT_DIR/update.sh" <<EOF
#!/bin/bash
set -e
cd $PROJECT_DIR
git pull
sudo systemctl restart forklift.service
echo "Update complete. forklift.service restarted."
EOF

chmod +x "$PROJECT_DIR/update.sh"
chown "$TARGET_USER:$TARGET_USER" "$PROJECT_DIR/update.sh"

log_success "update.sh created at $PROJECT_DIR/update.sh"

#=========================================================
# Post Install Verification
#=========================================================
log_info "Running post-install verification..."

if command -v python3 &>/dev/null; then
    log_success "Python3 is installed: $(python3 --version)"
else
    log_error "Python3 is not installed."
fi

if systemctl is-active --quiet postgresql; then
    log_success "PostgreSQL service is running."
else
    log_error "PostgreSQL service is not running."
fi

if [[ -e /dev/video10 ]]; then
    log_success "Camera device present."
else
    log_warning "Camera device not detected."
fi

if curl -s --max-time 3 http://localhost:8080 &>/dev/null; then
    log_success "Camera streaming API responding on port 8080."
else
    log_warning "Camera streaming API not responding yet."
fi

if [[ -f "$PROJECT_DIR/lib/webview_app.py" ]]; then
    log_success "Dashboard application found."
else
    log_error "Dashboard application (webview_app.py) not found in $PROJECT_DIR/lib/"
fi

if systemctl is-enabled --quiet forklift.service; then
    log_success "forklift.service is enabled."
else
    log_error "forklift.service is not enabled."
fi

#=========================================================
# Finish
#=========================================================
log_success "===== Installation Completed Successfully ====="
echo -e "${COLOR_GREEN}Installation Completed Successfully${COLOR_RESET}"
echo -e "${COLOR_GREEN}System will reboot automatically in 5 seconds...${COLOR_RESET}"

sleep 5

reboot
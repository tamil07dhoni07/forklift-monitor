#!/bin/bash
if [ "$(id -u)" != "0" ]; then
    echo "Please run with sudo: sudo ./uninstall.sh"
    exit 1
fi
echo "Uninstalling Forklift Monitor..."
sudo rm -rf /usr/local/share/forklift-monitor
sudo rm -f /usr/local/bin/forklift-monitor
rm -f ~/Desktop/forklift-monitor.desktop
sudo rm -f /usr/local/share/applications/forklift-monitor.desktop
echo "Uninstall complete."

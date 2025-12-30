#!/bin/bash
# Setup office WiFi on ARTIFACT Pi
# This script adds the office_64 network with auto-connect

# Add the office_64 connection with proper priority
sudo nmcli connection add \
    type wifi \
    con-name "office_64" \
    ssid "office_64" \
    wifi-sec.key-mgmt wpa-psk \
    wifi-sec.psk "v6321093v" \
    connection.autoconnect yes \
    connection.autoconnect-priority 10

# Set home network (Renaissance) to lower priority so office takes precedence when both available
sudo nmcli connection modify "Renaissance" connection.autoconnect-priority 5 2>/dev/null || true

echo "WiFi configured!"
echo "- office_64: priority 10 (will connect when at office)"
echo "- Renaissance: priority 5 (will connect when at home)"
echo ""
echo "To connect now: sudo nmcli device wifi connect 'office_64'"

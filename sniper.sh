#!/bin/bash
# SNIPER.SH - Aggressively try to connect to Pi and fix networking
#
# TWO POSSIBLE NETWORKS:
#   1. office_64 (venue WiFi) - 192.168.2.x subnet
#   2. VNVNC (backup WiFi, pw: vnvnc2018) - unknown subnet
#
# Run this script, then switch YOUR MAC between networks to find the Pi

PASSWORD="qaz123"

# Commands to run once connected - fix all the networking bullshit
FIX_COMMANDS='
echo "=== SNIPER CONNECTED at $(date) ==="
echo "Connected from: $(hostname -I 2>/dev/null || echo unknown)"

# Kill sing-box
sudo systemctl stop sing-box 2>/dev/null
sudo systemctl disable sing-box 2>/dev/null

# Kill the broken persist-venue-route service
sudo systemctl stop persist-venue-route.service 2>/dev/null
sudo systemctl disable persist-venue-route.service 2>/dev/null
sudo rm -f /etc/systemd/system/persist-venue-route.service
sudo systemctl daemon-reload

# Remove any manual IP hacks
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null

# Fix DNS - this was broken!
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf > /dev/null

# Make sure BOTH WiFi networks are configured
sudo nmcli connection delete "VNVNC" 2>/dev/null
sudo nmcli connection delete "office_64" 2>/dev/null
sudo nmcli device wifi connect "VNVNC" password "vnvnc2018" 2>/dev/null || true
sudo nmcli device wifi connect "office_64" password "" 2>/dev/null || true

# Reset NetworkManager
sudo systemctl restart NetworkManager
sleep 3

# Restart Tailscale
sudo systemctl restart tailscaled
sleep 3

# Show status
echo ""
echo "=== CURRENT WIFI ==="
iwgetid -r 2>/dev/null || echo "unknown"
echo ""
echo "=== NETWORK STATUS ==="
ip addr show wlan0 | grep -E "inet |state"
echo ""
echo "=== ROUTES ==="
ip route | head -5
echo ""
echo "=== DNS ==="
cat /etc/resolv.conf | grep nameserver
echo ""
echo "=== TAILSCALE ==="
tailscale status 2>&1 | head -5
echo ""
echo "=== SNIPER SUCCESS! ==="
'

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  SNIPER - Hunting for Pi                                      ║"
echo "║                                                               ║"
echo "║  The Pi might be on:                                          ║"
echo "║    - office_64 (192.168.2.x)                                  ║"
echo "║    - VNVNC (unknown subnet, pw: vnvnc2018)                    ║"
echo "║                                                               ║"
echo "║  TRY BOTH:                                                    ║"
echo "║    1. Connect Mac to office_64, run this script               ║"
echo "║    2. If no luck, connect Mac to VNVNC, run again             ║"
echo "║                                                               ║"
echo "║  Press Ctrl+C once you see SUCCESS                            ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo "ERROR: sshpass not installed. Run: brew install hudochenkov/sshpass/sshpass"
    exit 1
fi

# Get current subnet
CURRENT_IP=$(ipconfig getifaddr en0 2>/dev/null)
if [ -z "$CURRENT_IP" ]; then
    echo "WARNING: Can't detect Mac's IP. Make sure you're on WiFi."
    SUBNET="192.168"
else
    SUBNET=$(echo "$CURRENT_IP" | cut -d. -f1-3)
    echo "Mac IP: $CURRENT_IP (scanning $SUBNET.x)"
fi
echo ""

# Build IP list based on current subnet
IPS=(
    "artifact.local"           # mDNS (works across subnets sometimes)
    "$SUBNET.1"                # Often router, but try anyway
)

# Add common IPs in current subnet
for i in {2..30} {100..110} {150..160} {200..210}; do
    IPS+=("$SUBNET.$i")
done

# Also try the known office_64 IPs regardless of current network
IPS+=(
    "192.168.2.12"
    "192.168.2.14"
    "192.168.2.16"
    "192.168.2.21"
    "192.168.2.150"
)

attempt=0
while true; do
    attempt=$((attempt + 1))
    echo "[Attempt $attempt] Scanning..."

    for ip in "${IPS[@]}"; do
        # Quick port check first (faster than full SSH timeout)
        if nc -z -w1 "$ip" 22 2>/dev/null; then
            echo "  Found SSH on $ip - trying to connect..."

            result=$(sshpass -p "$PASSWORD" ssh \
                -o ConnectTimeout=5 \
                -o StrictHostKeyChecking=no \
                -o UserKnownHostsFile=/dev/null \
                -o LogLevel=ERROR \
                "kirniy@$ip" "$FIX_COMMANDS" 2>&1)

            if echo "$result" | grep -q "SNIPER SUCCESS"; then
                echo ""
                echo "$result"
                echo ""
                echo "╔═══════════════════════════════════════════════════════════╗"
                echo "║  SUCCESS! Connected via $ip"
                echo "║  Pi should be stable now. Try:"
                echo "║    ssh kirniy@$ip"
                echo "╚═══════════════════════════════════════════════════════════╝"
                exit 0
            else
                echo "  Connected but command failed. Output:"
                echo "$result" | head -10
            fi
        fi
    done

    sleep 2
done

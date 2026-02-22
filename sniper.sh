#!/bin/bash
# SNIPER.SH - Aggressively try to connect to Pi and fix networking
#
# SITUATION: office_64 is DOWN, need to switch Pi to VNVNC
#
# STRATEGY:
#   1. Try VNVNC first (Pi might already be there or auto-switched)
#   2. If not found, try office_64 (local access might still work even if no internet)
#   3. Once connected, force Pi to VNVNC

PASSWORD="qaz123"

# Commands to run once connected - fix all networking and switch to VNVNC
FIX_COMMANDS='
echo "=== SNIPER CONNECTED at $(date) ==="
echo "Current WiFi: $(iwgetid -r 2>/dev/null || echo unknown)"
echo "IP: $(hostname -I 2>/dev/null || echo unknown)"

# Kill all VPN stuff
sudo systemctl stop sing-box 2>/dev/null
sudo systemctl disable sing-box 2>/dev/null
sudo systemctl stop xray-proxy 2>/dev/null
sudo systemctl disable xray-proxy 2>/dev/null
sudo systemctl stop tun2socks 2>/dev/null
sudo systemctl disable tun2socks 2>/dev/null
sudo systemctl stop amneziawg 2>/dev/null

# Kill the broken persist-venue-route service
sudo systemctl stop persist-venue-route.service 2>/dev/null
sudo systemctl disable persist-venue-route.service 2>/dev/null
sudo rm -f /etc/systemd/system/persist-venue-route.service
sudo systemctl daemon-reload

# Remove any manual IP hacks
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null

# Fix DNS
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf > /dev/null
echo "nameserver 1.1.1.1" | sudo tee -a /etc/resolv.conf > /dev/null

# SWITCH TO VNVNC WIFI
echo ""
echo "=== SWITCHING TO VNVNC WIFI ==="

# Delete office_64 to prevent reconnection
sudo nmcli connection delete "office_64" 2>/dev/null || true

# Check if already on VNVNC
CURRENT_WIFI=$(iwgetid -r 2>/dev/null)
if [ "$CURRENT_WIFI" = "VNVNC" ]; then
    echo "Already on VNVNC!"
else
    echo "Connecting to VNVNC..."
    sudo nmcli device wifi rescan 2>/dev/null
    sleep 2
    sudo nmcli device wifi connect "VNVNC" password "vnvnc2018" || {
        echo "First attempt failed, retrying..."
        sleep 3
        sudo nmcli device wifi connect "VNVNC" password "vnvnc2018"
    }
fi

# Wait for connection
sleep 5

# Restart networking
sudo systemctl restart NetworkManager
sleep 3

# Show status
echo ""
echo "=== FINAL STATUS ==="
echo "WiFi: $(iwgetid -r 2>/dev/null || echo DISCONNECTED)"
ip addr show wlan0 2>/dev/null | grep -E "inet " || echo "No IP on wlan0"
echo ""
echo "Routes:"
ip route | head -3
echo ""
echo "Internet test:"
ping -c 2 8.8.8.8 2>&1 | tail -2
echo ""

# Restart Tailscale
sudo systemctl restart tailscaled
sleep 3
echo "Tailscale:"
tailscale status 2>&1 | head -3

echo ""
echo "=== SNIPER SUCCESS! ==="
'

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  SNIPER - Hunting for Pi                                      ║"
echo "║                                                               ║"
echo "║  SITUATION: office_64 is DOWN                                 ║"
echo "║                                                               ║"
echo "║  STRATEGY:                                                    ║"
echo "║    Round 1: Connect Mac to VNVNC, run sniper                  ║"
echo "║    Round 2: If not found, connect Mac to office_64, run again ║"
echo "║             (local SSH might work even if no internet)        ║"
echo "║                                                               ║"
echo "║  Once found, Pi will be switched to VNVNC automatically       ║"
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
    SUBNET="192.168.1"
else
    SUBNET=$(echo "$CURRENT_IP" | cut -d. -f1-3)
    echo "Mac IP: $CURRENT_IP"
    echo "Scanning: $SUBNET.x + known office_64 IPs"
fi
echo ""

# Build IP list
IPS=(
    "artifact.local"           # mDNS
)

# Add IPs in current subnet
for i in {2..50} {100..120} {150..160} {200..220}; do
    IPS+=("$SUBNET.$i")
done

# Also try known office_64 IPs (in case Pi is there)
IPS+=(
    "192.168.2.12"
    "192.168.2.14"
    "192.168.2.16"
    "192.168.2.21"
    "192.168.2.100"
    "192.168.2.150"
)

attempt=0
while true; do
    attempt=$((attempt + 1))
    echo "[Attempt $attempt] Scanning ${#IPS[@]} addresses..."

    for ip in "${IPS[@]}"; do
        # Quick port check (1 second timeout)
        if nc -z -w1 "$ip" 22 2>/dev/null; then
            echo "  → Found SSH on $ip - connecting..."

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
                # Extract new IP from output
                NEW_IP=$(echo "$result" | grep "inet " | grep -oE "192\.[0-9]+\.[0-9]+\.[0-9]+" | head -1)
                echo "╔═══════════════════════════════════════════════════════════════╗"
                echo "║  SUCCESS!                                                     ║"
                echo "║                                                               ║"
                echo "║  Pi is now on VNVNC WiFi                                      ║"
                echo "║  New IP: ${NEW_IP:-check output above}                        ║"
                echo "║                                                               ║"
                echo "║  Next steps:                                                  ║"
                echo "║    1. Connect YOUR Mac to VNVNC (if not already)              ║"
                echo "║    2. ssh kirniy@${NEW_IP:-artifact.local}                    ║"
                echo "║    3. Run: ./scripts/setup-amneziawg.sh                       ║"
                echo "╚═══════════════════════════════════════════════════════════════╝"
                exit 0
            else
                echo "  Connected but something failed:"
                echo "$result" | head -15
                echo ""
            fi
        fi
    done

    echo "  No Pi found this round. Retrying in 3s..."
    sleep 3
done

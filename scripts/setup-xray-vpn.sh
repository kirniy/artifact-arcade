#!/bin/bash
# SETUP-XRAY-VPN.SH
# Installs xray + tun2socks (same architecture as Amnezia on Mac)
# Completely removes sing-box and cleans up all network hacks

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Setting up xray + tun2socks VPN                              ║"
echo "║  (Same architecture as Amnezia on Mac)                        ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# PHASE 1: CLEAN UP ALL THE SHIT
# =============================================================================
echo "=== PHASE 1: Cleaning up old configs ==="

# Stop and remove sing-box completely
echo "Removing sing-box..."
sudo systemctl stop sing-box 2>/dev/null || true
sudo systemctl disable sing-box 2>/dev/null || true
sudo rm -f /etc/systemd/system/sing-box.service
sudo rm -rf /etc/sing-box
sudo apt remove -y sing-box 2>/dev/null || true

# Remove the broken persist-venue-route service
echo "Removing persist-venue-route service..."
sudo systemctl stop persist-venue-route.service 2>/dev/null || true
sudo systemctl disable persist-venue-route.service 2>/dev/null || true
sudo rm -f /etc/systemd/system/persist-venue-route.service

# Remove any IP hacks
echo "Cleaning up IP hacks..."
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null || true

# Fix DNS
echo "Fixing DNS..."
sudo tee /etc/resolv.conf > /dev/null << 'EOF'
nameserver 8.8.8.8
nameserver 1.1.1.1
EOF

# Reload systemd
sudo systemctl daemon-reload

echo "Cleanup complete!"
echo ""

# =============================================================================
# PHASE 2: INSTALL XRAY
# =============================================================================
echo "=== PHASE 2: Installing xray ==="

# Check if xray already installed
if command -v xray &> /dev/null; then
    echo "xray already installed: $(xray version | head -1)"
else
    echo "Installing xray..."

    # Download latest xray for arm64
    cd /tmp
    XRAY_VERSION="1.8.24"
    wget -q "https://github.com/XTLS/Xray-core/releases/download/v${XRAY_VERSION}/Xray-linux-arm64-v8a.zip" -O xray.zip
    unzip -o xray.zip xray
    sudo mv xray /usr/local/bin/xray
    sudo chmod +x /usr/local/bin/xray
    rm -f xray.zip

    echo "xray installed: $(xray version | head -1)"
fi

# =============================================================================
# PHASE 3: INSTALL TUN2SOCKS
# =============================================================================
echo ""
echo "=== PHASE 3: Installing tun2socks ==="

if command -v tun2socks &> /dev/null || [ -f /usr/local/bin/tun2socks ]; then
    echo "tun2socks already installed"
else
    echo "Installing tun2socks..."

    cd /tmp
    TUN2SOCKS_VERSION="2.5.2"
    wget -q "https://github.com/xjasonlyu/tun2socks/releases/download/v${TUN2SOCKS_VERSION}/tun2socks-linux-arm64.zip" -O tun2socks.zip
    unzip -o tun2socks.zip
    sudo mv tun2socks-linux-arm64 /usr/local/bin/tun2socks
    sudo chmod +x /usr/local/bin/tun2socks
    rm -f tun2socks.zip

    echo "tun2socks installed"
fi

# =============================================================================
# PHASE 4: CONFIGURE XRAY
# =============================================================================
echo ""
echo "=== PHASE 4: Configuring xray ==="

sudo mkdir -p /etc/xray
sudo cp "$PROJECT_DIR/configs/vpn/xray-config.json" /etc/xray/config.json
echo "Config installed to /etc/xray/config.json"

# =============================================================================
# PHASE 5: INSTALL SYSTEMD SERVICES
# =============================================================================
echo ""
echo "=== PHASE 5: Installing systemd services ==="

# xray-proxy service
sudo cp "$PROJECT_DIR/configs/vpn/xray-proxy.service" /etc/systemd/system/
echo "Installed xray-proxy.service"

# tun2socks service (optional - for full TUN mode)
sudo cp "$PROJECT_DIR/configs/vpn/tun2socks.service" /etc/systemd/system/
echo "Installed tun2socks.service"

sudo systemctl daemon-reload

# =============================================================================
# PHASE 6: START SERVICES
# =============================================================================
echo ""
echo "=== PHASE 6: Starting services ==="

# Always start xray (SOCKS proxy)
sudo systemctl enable xray-proxy
sudo systemctl start xray-proxy
sleep 2

if systemctl is-active --quiet xray-proxy; then
    echo "✓ xray-proxy is running"
else
    echo "✗ xray-proxy failed to start!"
    sudo journalctl -u xray-proxy -n 10
    exit 1
fi

# =============================================================================
# PHASE 7: TEST
# =============================================================================
echo ""
echo "=== PHASE 7: Testing proxy ==="

# Test SOCKS proxy
if curl -s --connect-timeout 5 --proxy socks5://127.0.0.1:10808 https://www.google.com > /dev/null 2>&1; then
    echo "✓ SOCKS proxy works (google.com reachable)"
else
    echo "✗ SOCKS proxy test failed"
fi

# Test Gemini API
if curl -s --connect-timeout 10 --proxy socks5://127.0.0.1:10808 https://generativelanguage.googleapis.com/ > /dev/null 2>&1; then
    echo "✓ Gemini API reachable through proxy!"
else
    echo "⚠ Gemini API not reachable (might be blocked or slow)"
fi

# =============================================================================
# DONE
# =============================================================================
echo ""
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Setup complete!                                              ║"
echo "║                                                               ║"
echo "║  xray-proxy: SOCKS5 on 127.0.0.1:10808 (RUNNING)             ║"
echo "║  tun2socks:  Available but NOT started                        ║"
echo "║                                                               ║"
echo "║  The artifact app will use the SOCKS proxy for Gemini.        ║"
echo "║  Tailscale and everything else stays on normal network.       ║"
echo "║                                                               ║"
echo "║  To enable FULL tunnel mode (all traffic through VPN):        ║"
echo "║    sudo systemctl enable --now tun2socks                      ║"
echo "║                                                               ║"
echo "║  WARNING: Full tunnel mode will route ALL traffic through     ║"
echo "║  VPN. If VPN fails, you lose SSH access!                      ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

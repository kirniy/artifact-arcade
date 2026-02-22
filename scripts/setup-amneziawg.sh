#!/bin/bash
# SETUP-AMNEZIAWG.SH
# Installs AmneziaWG kernel module and tools on Raspberry Pi (Debian Trixie)
# This replaces xray/sing-box with native WireGuard-speed VPN with DPI obfuscation

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  Setting up AmneziaWG (WireGuard + DPI obfuscation)           ║"
echo "║  Native kernel module = WireGuard speeds!                     ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo ""

# =============================================================================
# PHASE 1: CLEAN UP OLD VPN STUFF
# =============================================================================
echo "=== PHASE 1: Cleaning up old VPN configs ==="

# Stop and remove xray
echo "Removing xray..."
sudo systemctl stop xray-proxy 2>/dev/null || true
sudo systemctl disable xray-proxy 2>/dev/null || true
sudo rm -f /etc/systemd/system/xray-proxy.service

# Stop and remove tun2socks
echo "Removing tun2socks..."
sudo systemctl stop tun2socks 2>/dev/null || true
sudo systemctl disable tun2socks 2>/dev/null || true
sudo rm -f /etc/systemd/system/tun2socks.service

# Stop and remove sing-box (just in case)
echo "Removing sing-box..."
sudo systemctl stop sing-box 2>/dev/null || true
sudo systemctl disable sing-box 2>/dev/null || true
sudo rm -f /etc/systemd/system/sing-box.service
sudo rm -rf /etc/sing-box

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
# PHASE 2: INSTALL DEPENDENCIES
# =============================================================================
echo "=== PHASE 2: Installing dependencies ==="

sudo apt-get update
sudo apt-get install -y ca-certificates curl gpg linux-headers-$(uname -r) dkms

echo "Dependencies installed!"
echo ""

# =============================================================================
# PHASE 3: ADD AMNEZIA PPA
# =============================================================================
echo "=== PHASE 3: Adding Amnezia PPA ==="

# Set up the Amnezia PPA key
sudo install -d -m 0755 /usr/share/keyrings
sudo rm -f /usr/share/keyrings/amnezia-ppa.gpg
curl -fsSL "https://keyserver.ubuntu.com/pks/lookup?op=get&search=0x75C9DD72C799870E310542E24166F2C257290828" \
  | gpg --dearmor | sudo tee /usr/share/keyrings/amnezia-ppa.gpg > /dev/null

echo "PPA key installed"

# Add the PPA repository (deb822 format for Trixie)
sudo tee /etc/apt/sources.list.d/amnezia-ppa.sources > /dev/null <<'EOF'
Types: deb
URIs: https://ppa.launchpadcontent.net/amnezia/ppa/ubuntu
Suites: focal
Components: main
Signed-By: /usr/share/keyrings/amnezia-ppa.gpg
EOF

echo "PPA repository added"

# Enable Debian source repositories for DKMS (required for Trixie)
if ! grep -q "deb-src.*trixie main" /etc/apt/sources.list 2>/dev/null; then
    echo "Adding Debian source repositories for DKMS..."
    sudo tee -a /etc/apt/sources.list > /dev/null <<'EOF'

# Source repos for DKMS (required for AmneziaWG kernel module build)
deb-src http://deb.debian.org/debian trixie main
deb-src http://deb.debian.org/debian trixie-updates main
EOF
fi

echo "Source repositories configured"
echo ""

# =============================================================================
# PHASE 4: INSTALL AMNEZIAWG
# =============================================================================
echo "=== PHASE 4: Installing AmneziaWG ==="

sudo apt-get update
sudo apt-get install -y amneziawg amneziawg-tools || {
    echo ""
    echo "⚠ Package installation failed. Trying manual build..."
    echo ""

    # Fallback: manual build
    cd /tmp
    rm -rf amneziawg-linux-kernel-module amnezia-wg-tools

    # Build kernel module
    git clone https://github.com/amnezia-vpn/amneziawg-linux-kernel-module.git
    cd amneziawg-linux-kernel-module/src
    make
    sudo make install

    # Build tools
    cd /tmp
    git clone https://github.com/amnezia-vpn/amnezia-wg-tools.git
    cd amnezia-wg-tools/src
    make
    sudo make install

    cd /tmp
    rm -rf amneziawg-linux-kernel-module amnezia-wg-tools
}

echo ""

# =============================================================================
# PHASE 5: VERIFY INSTALLATION
# =============================================================================
echo "=== PHASE 5: Verifying installation ==="

# Load kernel module
sudo modprobe amneziawg 2>/dev/null || true

# Check module
if lsmod | grep -q amneziawg; then
    echo "✓ AmneziaWG kernel module loaded"
else
    echo "⚠ Kernel module not loaded (might need reboot)"
fi

# Check tools
if command -v awg &> /dev/null; then
    echo "✓ awg command available"
else
    echo "✗ awg command not found!"
    exit 1
fi

if command -v awg-quick &> /dev/null; then
    echo "✓ awg-quick command available"
else
    echo "✗ awg-quick command not found!"
    exit 1
fi

echo ""

# =============================================================================
# PHASE 5.5: BUILD AWG TOOLS FROM SOURCE (for AWG 2.0 support)
# =============================================================================
echo "=== PHASE 5.5: Building AWG tools from source for AWG 2.0 support ==="

cd /tmp
rm -rf amneziawg-tools 2>/dev/null || true
git clone https://github.com/amnezia-vpn/amneziawg-tools.git
cd amneziawg-tools/src
make clean
make
sudo make install
cd /tmp
rm -rf amneziawg-tools

echo "AWG tools built from source"
echo ""

# =============================================================================
# PHASE 6: INSTALL CONFIG
# =============================================================================
echo "=== PHASE 6: Installing VPN config ==="

# awg-quick looks for configs in /etc/amnezia/amneziawg/
sudo mkdir -p /etc/amnezia/amneziawg
sudo cp "$PROJECT_DIR/configs/vpn/awg0.conf" /etc/amnezia/amneziawg/awg0.conf
sudo chmod 600 /etc/amnezia/amneziawg/awg0.conf

echo "Config installed to /etc/amnezia/amneziawg/awg0.conf"
echo ""

# =============================================================================
# PHASE 7: CREATE SYSTEMD SERVICE
# =============================================================================
echo "=== PHASE 7: Creating systemd service ==="

# Use awg-quick@ template service
sudo tee /etc/systemd/system/awg-quick@.service > /dev/null <<'EOF'
[Unit]
Description=AmneziaWG Quick VPN (%i)
After=network-online.target
Wants=network-online.target
Before=artifact.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/bin/awg-quick up %i
ExecStop=/usr/bin/awg-quick down %i
Environment=WG_QUICK_USERSPACE_IMPLEMENTATION=amneziawg-go

[Install]
WantedBy=multi-user.target
EOF

# Disable and mask old sing-box if exists
if systemctl is-enabled sing-box &>/dev/null; then
    echo "Disabling old sing-box..."
    sudo systemctl stop sing-box 2>/dev/null || true
    sudo systemctl disable sing-box
    sudo systemctl mask sing-box
fi

sudo systemctl daemon-reload
echo "Systemd service created"
echo ""

# =============================================================================
# PHASE 7.5: CONFIGURE TAILSCALE DNS
# =============================================================================
echo "=== PHASE 7.5: Configuring Tailscale ==="

if command -v tailscale &>/dev/null; then
    echo "Disabling Tailscale DNS management (using 8.8.8.8 instead)..."
    sudo tailscale set --accept-dns=false
fi
echo ""

# =============================================================================
# PHASE 8: START VPN (but don't enable auto-start yet)
# =============================================================================
echo "=== PHASE 8: Starting VPN ==="

# Don't auto-enable - we need to test first
sudo systemctl start awg-quick@awg0 || {
    echo ""
    echo "⚠ VPN failed to start. Checking logs..."
    sudo journalctl -u awg-quick@awg0 -n 20
    echo ""
    echo "Try rebooting to load the kernel module, then run:"
    echo "  sudo systemctl start awg-quick@awg0"
    exit 1
}

sleep 3

if systemctl is-active --quiet awg-quick@awg0; then
    echo "✓ AmneziaWG VPN is running"
else
    echo "✗ VPN failed to start"
    exit 1
fi

echo ""

# =============================================================================
# PHASE 9: TEST CONNECTIVITY
# =============================================================================
echo "=== PHASE 9: Testing connectivity ==="

# Check interface exists
if ip link show awg0 &>/dev/null; then
    echo "✓ awg0 interface exists"
    ip addr show awg0 | grep inet
else
    echo "✗ awg0 interface not found"
    exit 1
fi

# Test internet through VPN
echo ""
echo "Testing internet through VPN..."
if ping -c 2 -W 5 8.8.8.8 &>/dev/null; then
    echo "✓ Internet works through VPN"
else
    echo "✗ No internet through VPN"
    echo "  Check your VPN server or config"
fi

# Test DNS
if ping -c 2 -W 5 google.com &>/dev/null; then
    echo "✓ DNS resolution works"
else
    echo "⚠ DNS might have issues"
fi

# Test Gemini API
echo ""
echo "Testing Gemini API access..."
if curl -s --connect-timeout 10 https://generativelanguage.googleapis.com/ > /dev/null 2>&1; then
    echo "✓ Gemini API is reachable!"
else
    echo "⚠ Gemini API not reachable (might be slow or blocked)"
fi

echo ""

# =============================================================================
# PHASE 10: ENABLE AUTO-START
# =============================================================================
echo "=== PHASE 10: Enabling auto-start ==="

sudo systemctl enable awg-quick@awg0
echo "✓ VPN will start on boot"

echo ""

# =============================================================================
# DONE
# =============================================================================
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║  AmneziaWG 2.0 setup complete!                                ║"
echo "║                                                               ║"
echo "║  VPN Status: RUNNING                                          ║"
echo "║  Interface:  awg0                                             ║"
echo "║  Auto-start: ENABLED                                          ║"
echo "║                                                               ║"
echo "║  Commands:                                                    ║"
echo "║    sudo awg show awg0               - Show VPN status         ║"
echo "║    sudo systemctl restart awg-quick@awg0 - Restart VPN        ║"
echo "║    sudo systemctl stop awg-quick@awg0    - Stop VPN           ║"
echo "║                                                               ║"
echo "║  Config: /etc/amnezia/amneziawg/awg0.conf                     ║"
echo "║  Tailscale: Active (DNS disabled, using 8.8.8.8)              ║"
echo "║                                                               ║"
echo "║  Features:                                                    ║"
echo "║  - AWG 2.0 with full DPI obfuscation (H1-H4, S3-S4, I1)       ║"
echo "║  - Split-tunnel routing (Tailscale bypasses VPN)              ║"
echo "║  - VPN endpoint exception (prevents routing loops)           ║"
echo "╚═══════════════════════════════════════════════════════════════╝"

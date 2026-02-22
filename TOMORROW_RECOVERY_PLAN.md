# ARTIFACT Pi Recovery Plan - February 23, 2026

**CRITICAL: Do NOT spend more than 15 minutes on any single step. If stuck, move to fallback.**

---

## BEFORE YOU START

### Today's Changes:
1. **office_64 WiFi is DOWN** - Use VNVNC instead (pw: vnvnc2018)
2. **AmneziaWG 2.0** - Replacing xray/sing-box with native kernel module VPN
3. **No more SOCKS proxy** - AmneziaWG routes ALL traffic through VPN

### WiFi Network:
| Network | Password | Notes |
|---------|----------|-------|
| VNVNC | vnvnc2018 | PRIMARY - use this! |
| office_64 | - | DOWN, don't use |

---

## PHASE 0: QUICK SANITY CHECK (2 minutes max)

Before doing anything complex, try the obvious:

```bash
# From your Mac (connected to VNVNC!), try:
ping artifact.local
ssh kirniy@artifact.local
tailscale ping artifact
```

If any of these work, skip to PHASE 2.

---

## PHASE 1: FIND THE PI (15 minutes max)

### Step 1A: Connect Mac to VNVNC first!
```bash
# On Mac, connect to VNVNC WiFi (password: vnvnc2018)
# Then run sniper:
cd ~/dev/artifact-arcade
./sniper.sh
```
Wait up to 3 minutes for "SNIPER SUCCESS!"

### Step 1B: Manual network scan
If sniper doesn't find it:
```bash
# Get your Mac's current IP
ipconfig getifaddr en0

# Scan the subnet (replace with your subnet)
nmap -sn 192.168.1.0/24 2>/dev/null | grep -B2 "Raspberry\|DC:A6:32\|artifact"

# Or use arp
arp -a | grep -i "dc:a6:32\|raspberry"
```

### Step 1C: If nothing works
The Pi might be:
- Crashed/frozen → Need physical power cycle (can't do remotely)
- Still on office_64 → It won't respond if that network is down
- WiFi chip dead → Need physical access

**DECISION POINT:** If you can't connect after 15 minutes, the Pi needs physical intervention. Call someone who can power cycle it.

---

## PHASE 2: GET LOGS FIRST (5 minutes)

**IMMEDIATELY after connecting, before fixing anything, grab logs:**

```bash
# Save this entire output to understand what happened
ssh kirniy@<IP> 'bash -s' << 'GETLOGS'
echo "=== TIMESTAMP ==="
date

echo ""
echo "=== CURRENT WIFI ==="
iwgetid -r 2>/dev/null || echo "not connected"

echo ""
echo "=== IP ADDRESSES ==="
ip addr show wlan0 | grep -E "inet |state"

echo ""
echo "=== ROUTING TABLE ==="
ip route

echo ""
echo "=== DNS CONFIG ==="
cat /etc/resolv.conf

echo ""
echo "=== ACTIVE SERVICES ==="
systemctl list-units --state=running | grep -E "sing-box|xray|tun2socks|amneziawg|persist|artifact|tailscale|network"

echo ""
echo "=== RECENT NETWORK ERRORS ==="
journalctl -u NetworkManager --since "1 hour ago" --no-pager | tail -30

echo ""
echo "=== RECENT TAILSCALE ERRORS ==="
journalctl -u tailscaled --since "1 hour ago" --no-pager | tail -30

echo ""
echo "=== RECENT ARTIFACT ERRORS ==="
journalctl -u artifact --since "1 hour ago" --no-pager | tail -50

echo ""
echo "=== CAMERA STATUS ==="
rpicam-hello --list-cameras 2>&1 | head -10

echo ""
echo "=== INTERNET CONNECTIVITY ==="
ping -c 2 8.8.8.8 2>&1
ping -c 2 google.com 2>&1
GETLOGS
```

**SAVE THIS OUTPUT.** It tells you exactly what's broken.

---

## PHASE 3: SWITCH TO VNVNC WIFI (5 minutes)

### Step 3A: Force switch to VNVNC
```bash
# Remove office_64 and connect to VNVNC
sudo nmcli connection delete "office_64" 2>/dev/null || true
sudo nmcli device wifi connect "VNVNC" password "vnvnc2018"

# Wait for connection
sleep 5

# Verify
iwgetid -r  # Should show "VNVNC"
ip addr show wlan0 | grep inet
```

### Step 3B: Fix DNS
```bash
# This was the main problem last night!
echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf

# Verify
cat /etc/resolv.conf
```

### Step 3C: Verify basic connectivity
```bash
ping -c 3 8.8.8.8 && echo "INTERNET OK" || echo "NO INTERNET"
ping -c 3 google.com && echo "DNS OK" || echo "DNS BROKEN"
```

---

## PHASE 4: CLEAN UP OLD VPN STUFF (5 minutes)

### Step 4A: Kill everything bad
```bash
# Stop all old VPN/routing stuff
sudo systemctl stop sing-box 2>/dev/null
sudo systemctl disable sing-box 2>/dev/null
sudo systemctl stop xray-proxy 2>/dev/null
sudo systemctl disable xray-proxy 2>/dev/null
sudo systemctl stop tun2socks 2>/dev/null
sudo systemctl disable tun2socks 2>/dev/null
sudo systemctl stop persist-venue-route.service 2>/dev/null
sudo systemctl disable persist-venue-route.service 2>/dev/null
sudo rm -f /etc/systemd/system/persist-venue-route.service

# Remove IP hacks
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null

# Reload systemd
sudo systemctl daemon-reload
```

### Step 4B: Restart Tailscale
```bash
sudo systemctl restart tailscaled
sleep 5
tailscale status
```

---

## PHASE 5: SETUP AMNEZIAWG (15 minutes)

Only do this if internet works!

```bash
cd ~/modular-arcade
git pull

# Run the setup script
./scripts/setup-amneziawg.sh
```

The script will:
1. Remove old VPN stuff (xray, sing-box)
2. Install AmneziaWG kernel module
3. Install awg-quick tools
4. Configure the VPN
5. Start the VPN
6. Test connectivity

### Verify it works:
```bash
# Check interface is up
ip link show awg0

# Check VPN status
sudo awg show

# Test Gemini API (the whole point!)
curl -s --connect-timeout 10 https://generativelanguage.googleapis.com/ && echo "GEMINI REACHABLE!"
```

### If setup script fails (kernel module issues):
```bash
# Try reboot first
sudo reboot

# After reboot, try again
./scripts/setup-amneziawg.sh
```

---

## PHASE 6: UPDATE AND RESTART APP (5 minutes)

```bash
cd ~/modular-arcade

# Copy the NEW service file (no proxy needed with AmneziaWG!)
sudo cp configs/vpn/artifact-amneziawg.service /etc/systemd/system/artifact.service
sudo systemctl daemon-reload

# Restart
sudo systemctl restart artifact

# Watch logs for 1 minute
timeout 60 journalctl -u artifact -f || true
```

---

## PHASE 7: FINAL VERIFICATION

```bash
echo "=== FINAL STATUS ==="
echo ""
echo "Services:"
systemctl is-active amneziawg && echo "  amneziawg: RUNNING" || echo "  amneziawg: STOPPED"
systemctl is-active artifact && echo "  artifact: RUNNING" || echo "  artifact: STOPPED"
systemctl is-active tailscaled && echo "  tailscaled: RUNNING" || echo "  tailscaled: STOPPED"

echo ""
echo "Network:"
ping -c 1 8.8.8.8 >/dev/null && echo "  Internet: OK" || echo "  Internet: FAIL"
ip link show awg0 >/dev/null 2>&1 && echo "  VPN Interface: UP" || echo "  VPN Interface: DOWN"

echo ""
echo "S3 Upload (CRITICAL - photos must upload):"
curl -s --connect-timeout 5 https://s3.ru-7.storage.selcloud.ru >/dev/null && echo "  S3 Endpoint: OK" || echo "  S3 Endpoint: FAIL"

echo ""
echo "Gemini API (for AI features):"
curl -s --connect-timeout 5 https://generativelanguage.googleapis.com/ >/dev/null && echo "  Gemini API: OK" || echo "  Gemini API: BLOCKED"

echo ""
echo "Camera:"
rpicam-hello --list-cameras 2>&1 | grep -q "imx708" && echo "  Camera: DETECTED" || echo "  Camera: NOT FOUND"
```

**CRITICAL:** S3 must work for photos to upload. If S3 fails, photos won't have QR codes.

---

## FALLBACK: LOCAL MODE (No AI, but S3 still works)

If AmneziaWG won't work but internet is fine, disable AI:

```bash
# Use old service file (proxy mode disabled)
sudo sed -i 's/GEMINI_USE_PROXY=true/GEMINI_USE_PROXY=false/' /etc/systemd/system/artifact.service

# Stop AmneziaWG if it's causing issues
sudo systemctl stop amneziawg
sudo systemctl disable amneziawg

# Restart app
sudo systemctl daemon-reload
sudo systemctl restart artifact
```

**Important:** Local mode still needs internet for S3 uploads. Photos must still upload and QR codes must work.

---

## QUICK REFERENCE

| Action | Command |
|--------|---------|
| SSH via Tailscale | `ssh kirniy@artifact` or `ssh kirniy@100.x.x.x` |
| SSH via local IP | `ssh kirniy@<IP>` |
| Pi password | `qaz123` |
| Find Pi on network | `./sniper.sh` |
| Setup AmneziaWG | `./scripts/setup-amneziawg.sh` |
| Check VPN status | `sudo awg show` |
| Check logs | `journalctl -u artifact -f` |
| Restart app | `sudo systemctl restart artifact` |
| Restart VPN | `sudo systemctl restart amneziawg` |
| Check camera | `rpicam-hello --list-cameras` |
| List WiFi | `nmcli device wifi list` |
| Connect WiFi | `sudo nmcli device wifi connect "VNVNC" password "vnvnc2018"` |

---

## TIME BUDGET

| Phase | Max Time | If Exceeded |
|-------|----------|-------------|
| Phase 0: Sanity check | 2 min | Move to Phase 1 |
| Phase 1: Find Pi | 15 min | Need physical access |
| Phase 2: Get logs | 5 min | Just proceed |
| Phase 3: Switch WiFi | 5 min | Check cabling |
| Phase 4: Clean up | 5 min | Just proceed |
| Phase 5: AmneziaWG setup | 15 min | Use fallback mode |
| Phase 6: Update app | 5 min | Check logs |
| Phase 7: Final check | 2 min | Done |
| **TOTAL** | **~55 min** | |

**If total exceeds 1 hour, use fallback mode and call it done.**

---

## WHAT'S NEW TODAY

### AmneziaWG vs xray/sing-box

| Feature | sing-box (old) | xray (yesterday) | AmneziaWG (today) |
|---------|---------------|-----------------|-------------------|
| Type | TUN mode | SOCKS proxy | WireGuard fork |
| Speed | Slow | Medium | Native WireGuard |
| Routing | Hijacks ALL traffic | Only proxied apps | Routes ALL traffic |
| Risk | SSH dies if VPN dies | Safer | SSH works via Tailscale |
| DPI bypass | Reality | Reality | Custom obfuscation |
| Protocol | VLESS | VLESS | WireGuard + junk packets |

### Why AmneziaWG is better:
1. **Kernel module** = native WireGuard speeds
2. **Different obfuscation** = better DPI bypass (works well in Russia)
3. **Simpler** = no SOCKS proxy configuration needed
4. **All traffic encrypted** = S3 and Gemini both go through VPN

### New files:
- `configs/vpn/amneziawg.conf` - VPN config
- `configs/vpn/artifact-amneziawg.service` - Updated service file
- `scripts/setup-amneziawg.sh` - One-command setup

# ARTIFACT Pi Recovery Plan - February 23, 2026

**CRITICAL: Do NOT spend more than 15 minutes on any single step. If stuck, move to fallback.**

---

## BEFORE YOU START

### Known Issues From Last Night:
1. **Camera fell** - now physically fixed, but caused black screen (wasted debugging time)
2. **DNS was broken** - Tailscale couldn't resolve anything
3. **sing-box destroyed routing** - auto_route hijacked everything
4. **persist-venue-route.service** - rogue service kept messing with routes
5. **Another agent tried switching WiFi** - Pi might be on wrong network

### WiFi Networks Available:
| Network | Password | Subnet | Notes |
|---------|----------|--------|-------|
| office_64 | (open?) | 192.168.2.x | Main venue WiFi |
| VNVNC | vnvnc2018 | unknown | Backup option |
| Renaissance | (home) | - | Not available at venue |

---

## PHASE 0: QUICK SANITY CHECK (2 minutes max)

Before doing anything complex, try the obvious:

```bash
# From your Mac, try all these:
ping artifact.local
ssh kirniy@artifact.local
tailscale ping artifact
```

If any of these work, skip to PHASE 2.

---

## PHASE 1: FIND THE PI (15 minutes max)

### Step 1A: Try office_64 first
Connect your Mac to `office_64`, then:
```bash
cd ~/dev/artifact-arcade
./sniper.sh
```
Wait up to 3 minutes for "SNIPER SUCCESS!"

### Step 1B: Try VNVNC
If office_64 didn't work, connect Mac to `VNVNC` (password: `vnvnc2018`):
```bash
./sniper.sh
```

### Step 1C: Manual network scan
If sniper doesn't find it:
```bash
# Get your Mac's current IP
ipconfig getifaddr en0

# Scan the subnet (replace with your subnet)
nmap -sn 192.168.1.0/24 2>/dev/null | grep -B2 "Raspberry\|DC:A6:32\|artifact"

# Or use arp
arp -a | grep -i "dc:a6:32\|raspberry"
```

### Step 1D: If nothing works
The Pi might be:
- Crashed/frozen → Need physical power cycle (can't do remotely)
- On a different network → Try other available WiFi networks
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
systemctl list-units --state=running | grep -E "sing-box|xray|tun2socks|persist|artifact|tailscale|network"

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

echo ""
echo "=== PROXY TEST (if xray running) ==="
curl -s --connect-timeout 5 --proxy socks5://127.0.0.1:10808 https://google.com >/dev/null 2>&1 && echo "PROXY WORKS" || echo "PROXY FAILED OR NOT RUNNING"
GETLOGS
```

**SAVE THIS OUTPUT.** It tells you exactly what's broken.

---

## PHASE 3: STABILIZE NETWORK (10 minutes max)

### Step 3A: Kill everything bad
```bash
# Stop all VPN/routing stuff
sudo systemctl stop sing-box 2>/dev/null
sudo systemctl disable sing-box 2>/dev/null
sudo systemctl stop xray-proxy 2>/dev/null
sudo systemctl stop tun2socks 2>/dev/null
sudo systemctl stop persist-venue-route.service 2>/dev/null
sudo systemctl disable persist-venue-route.service 2>/dev/null
sudo rm -f /etc/systemd/system/persist-venue-route.service

# Remove IP hacks
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null
sudo ip route del default via 192.168.2.1 src 192.168.2.150 2>/dev/null

# Reload systemd
sudo systemctl daemon-reload
```

### Step 3B: Fix DNS (CRITICAL)
```bash
# This was the main problem last night!
echo -e "nameserver 8.8.8.8\nnameserver 1.1.1.1" | sudo tee /etc/resolv.conf

# Verify
cat /etc/resolv.conf
```

### Step 3C: Restart networking
```bash
sudo systemctl restart NetworkManager
sleep 5

# Check we have internet
ping -c 3 8.8.8.8 && echo "INTERNET OK" || echo "NO INTERNET"
ping -c 3 google.com && echo "DNS OK" || echo "DNS BROKEN"
```

### Step 3D: Restart Tailscale
```bash
sudo systemctl restart tailscaled
sleep 5
tailscale status
```

**DECISION POINT:** If internet doesn't work here, try switching to a different WiFi network:
```bash
# List available networks
nmcli device wifi list

# Connect to a different one
sudo nmcli device wifi connect "VNVNC" password "vnvnc2018"
```

---

## PHASE 4: VERIFY STABILITY (5 minutes)

**Don't proceed until this passes:**

```bash
# Run this and wait 2 minutes - it should stay connected
for i in {1..24}; do
    echo "=== Check $i/24 ($(date +%H:%M:%S)) ==="
    ping -c 1 8.8.8.8 >/dev/null && echo "Internet: OK" || echo "Internet: FAIL"
    ping -c 1 google.com >/dev/null && echo "DNS: OK" || echo "DNS: FAIL"
    tailscale status >/dev/null 2>&1 && echo "Tailscale: OK" || echo "Tailscale: FAIL"
    echo ""
    sleep 5
done
```

If it keeps failing, **STOP** and use fallback mode (no AI).

---

## PHASE 5: SETUP VPN (10 minutes)

Only do this if Phase 4 passed.

```bash
cd ~/modular-arcade
git pull

# Run the setup script
./scripts/setup-xray-vpn.sh
```

The script will:
1. Remove sing-box completely
2. Install xray
3. Configure SOCKS proxy on localhost:10808
4. Test the connection

### Verify it works:
```bash
# Check service is running
systemctl status xray-proxy

# Test proxy
curl --proxy socks5://127.0.0.1:10808 https://www.google.com -I 2>&1 | head -5

# Test Gemini API specifically
curl --proxy socks5://127.0.0.1:10808 https://generativelanguage.googleapis.com/ -I 2>&1 | head -5
```

---

## PHASE 6: UPDATE AND RESTART APP (5 minutes)

```bash
cd ~/modular-arcade

# Install dependencies
.venv/bin/pip install aiohttp-socks

# Copy updated service file
sudo cp scripts/artifact.service /etc/systemd/system/
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
systemctl is-active xray-proxy && echo "  xray-proxy: RUNNING" || echo "  xray-proxy: STOPPED"
systemctl is-active artifact && echo "  artifact: RUNNING" || echo "  artifact: STOPPED"
systemctl is-active tailscaled && echo "  tailscaled: RUNNING" || echo "  tailscaled: STOPPED"

echo ""
echo "Network:"
ping -c 1 8.8.8.8 >/dev/null && echo "  Internet: OK" || echo "  Internet: FAIL"
curl -s --proxy socks5://127.0.0.1:10808 https://google.com >/dev/null && echo "  VPN Proxy: OK" || echo "  VPN Proxy: FAIL"

echo ""
echo "S3 Upload (CRITICAL - photos must upload):"
curl -s --connect-timeout 5 https://s3.ru-7.storage.selcloud.ru >/dev/null && echo "  S3 Endpoint: OK" || echo "  S3 Endpoint: FAIL"

echo ""
echo "Camera:"
rpicam-hello --list-cameras 2>&1 | grep -q "imx708" && echo "  Camera: DETECTED" || echo "  Camera: NOT FOUND"
```

**CRITICAL:** S3 must work for photos to upload. If S3 fails, photos won't have QR codes.

---

## FALLBACK: LOCAL MODE (No AI, but S3 still works)

If VPN won't work but internet is fine, disable AI only:

```bash
# Disable proxy (Gemini won't work, but S3 uploads will)
sudo sed -i 's/GEMINI_USE_PROXY=true/GEMINI_USE_PROXY=false/' /etc/systemd/system/artifact.service
sudo systemctl daemon-reload
sudo systemctl restart artifact
```

**Important:** Local mode still needs internet for S3 uploads. Photos must still upload and QR codes must work. This is just to avoid AI-related failures - the photobooth still functions for clients.

---

## FALLBACK: DIFFERENT WIFI

If current WiFi is garbage, try another:

```bash
# See what's available
nmcli device wifi list

# Connect to VNVNC
sudo nmcli device wifi connect "VNVNC" password "vnvnc2018"

# Or forget bad network and let it auto-connect to another
sudo nmcli connection delete "office_64"
```

---

## EMERGENCY: NOTHING WORKS

If you absolutely cannot connect remotely:

1. **Power cycle** - Ask someone at venue to unplug and replug the Pi (wait 30 sec between)
2. **Ethernet** - If there's an ethernet port near the machine, ask someone to plug it in
3. **Different outlet** - Sometimes power issues; try a different outlet
4. **Wait and retry** - Venue WiFi might be temporarily down; try again in 30 minutes

**Note:** Physical access to internals (HDMI, keyboard, SD card) is NOT possible without opening the machine.

---

## QUICK REFERENCE

| Action | Command |
|--------|---------|
| SSH via Tailscale | `ssh kirniy@artifact` or `ssh kirniy@100.x.x.x` |
| SSH via local IP | `ssh kirniy@192.168.2.x` |
| Pi password | `qaz123` |
| Find Pi on network | `./sniper.sh` |
| Setup VPN | `./scripts/setup-xray-vpn.sh` |
| Check logs | `journalctl -u artifact -f` |
| Restart app | `sudo systemctl restart artifact` |
| Test proxy | `curl --proxy socks5://127.0.0.1:10808 https://google.com` |
| Check camera | `rpicam-hello --list-cameras` |
| List WiFi | `nmcli device wifi list` |
| Switch WiFi | `sudo nmcli device wifi connect "SSID" password "PASS"` |

---

## WHAT WENT WRONG (Post-Mortem)

### Issue 1: Camera fell (physical)
- Caused black screen, wasted time debugging software
- **Fix**: Check physical connections first next time

### Issue 2: DNS corrupted
- sing-box hijacked DNS, never recovered
- Tailscale couldn't resolve controlplane.tailscale.com
- **Fix**: Always set DNS to 8.8.8.8 explicitly

### Issue 3: sing-box auto_route
- `auto_route: true` hijacked entire routing table
- When VPN failed, ALL traffic blackholed
- **Fix**: Use SOCKS proxy mode, not TUN

### Issue 4: Rogue services
- Another agent created `persist-venue-route.service`
- Kept overwriting routing fixes
- **Fix**: Check for and remove unexpected services

### Issue 5: IP hacks
- Manually adding .150 IP confused NetworkManager
- DHCP and manual IPs conflicting
- **Fix**: Let DHCP do its job, don't add manual IPs

---

## TIME BUDGET

| Phase | Max Time | If Exceeded |
|-------|----------|-------------|
| Phase 0: Sanity check | 2 min | Move to Phase 1 |
| Phase 1: Find Pi | 15 min | Need physical access |
| Phase 2: Get logs | 5 min | Just proceed |
| Phase 3: Stabilize | 10 min | Try different WiFi |
| Phase 4: Verify | 5 min | Use fallback mode |
| Phase 5: VPN setup | 10 min | Use fallback mode |
| Phase 6: Update app | 5 min | Check logs |
| Phase 7: Final check | 2 min | Done |
| **TOTAL** | **~55 min** | |

**If total exceeds 1 hour, use fallback mode and call it done.**

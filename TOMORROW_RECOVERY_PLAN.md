# ARTIFACT Pi Recovery Plan - February 23, 2026

## The Situation

- Pi is at the venue, cannot physically access it
- Network is fucked - another agent created `persist-venue-route.service` that keeps messing with routing
- **DNS was broken** - this caused Tailscale to fail even with sing-box off
- sing-box TUN mode was destroying routing tables
- Another agent may have tried to switch Pi to "VNVNC" WiFi - Pi could be on either network
- Need to connect remotely and fix everything

## Two Possible WiFi Networks

| Network | Password | Subnet |
|---------|----------|--------|
| office_64 | (none?) | 192.168.2.x |
| VNVNC | vnvnc2018 | unknown |

**The Pi might be on either one.** Try both.

---

## PHASE 1: Get Connected (Do This First)

### Option A: Sniper Script (BEST OPTION)

The Pi might be on `office_64` OR `VNVNC`. Try both:

**Step 1: Connect Mac to office_64**
```bash
cd ~/dev/artifact-arcade
./sniper.sh
```

Wait 1-2 minutes. If no success...

**Step 2: Connect Mac to VNVNC (password: vnvnc2018)**
```bash
./sniper.sh
```

The sniper script:
1. Scans the current subnet for SSH
2. Disables broken `persist-venue-route.service`
3. **Fixes DNS** (was broken - set to 8.8.8.8)
4. Configures BOTH WiFi networks on the Pi
5. Restarts NetworkManager and Tailscale

**Watch for "SNIPER SUCCESS!" then Ctrl+C to stop.**

### Option B: Tailscale (if Pi briefly connects)

Tailscale might connect for a few seconds. Be ready:

```bash
# Keep trying in a loop
while true; do
    ssh kirniy@100.102.241.21 "echo CONNECTED" && break
    sleep 1
done
```

Replace `100.102.241.21` with Pi's Tailscale IP (check `tailscale status` on your Mac).

### Option C: mDNS (if network is stable)

```bash
ssh kirniy@artifact.local
```

### Option D: Network Scan

```bash
# Find Pi on local network
arp -a | grep -i "dc:a6:32\|raspberry\|e4:5f:01"

# Or use nmap
nmap -sn 192.168.2.0/24 | grep -B2 "Raspberry\|DC:A6:32"
```

---

## PHASE 2: Emergency Stabilization (Once Connected)

**Run these commands IMMEDIATELY after connecting:**

```bash
# 1. KILL everything that's breaking networking
sudo systemctl stop sing-box
sudo systemctl disable sing-box
sudo systemctl stop persist-venue-route.service 2>/dev/null
sudo systemctl disable persist-venue-route.service 2>/dev/null
sudo rm -f /etc/systemd/system/persist-venue-route.service

# 2. Remove any fucked routing hacks
sudo ip addr del 192.168.2.150/24 dev wlan0 2>/dev/null

# 3. Reset NetworkManager to sane state
sudo systemctl restart NetworkManager

# 4. Wait for DHCP
sleep 5

# 5. Check we have internet
ping -c 3 8.8.8.8

# 6. Restart Tailscale
sudo systemctl restart tailscaled
sleep 5
tailscale status
```

**If internet works but Tailscale doesn't connect:**
```bash
# Check if DNS is broken
cat /etc/resolv.conf

# Force DNS to work
echo "nameserver 8.8.8.8" | sudo tee /etc/resolv.conf

# Try Tailscale again
sudo systemctl restart tailscaled
```

---

## PHASE 3: Verify Stability

Before doing anything else, make sure networking is stable:

```bash
# Watch for 2 minutes - should stay connected
watch -n 5 'echo "=== $(date) ==="; ip addr show wlan0 | grep inet; ip route | head -3; tailscale status | head -3'
```

If it keeps disconnecting, the venue WiFi itself might be unstable. In that case:
- Just use local polaroid mode (no AI)
- Skip VPN setup entirely

---

## PHASE 4: Set Up Robust VPN (xray + tun2socks)

This mirrors exactly what works on your Mac with Amnezia. **Everything is in the git repo - just run the script.**

### ONE COMMAND SETUP:

```bash
cd ~/modular-arcade
./scripts/setup-xray-vpn.sh
```

This script:
1. **Completely removes sing-box** (stops, disables, purges)
2. Removes `persist-venue-route.service` and IP hacks
3. Fixes DNS (8.8.8.8, 1.1.1.1)
4. Installs xray and tun2socks
5. Configures xray with your Netherlands server
6. Creates and starts `xray-proxy.service`
7. Tests the proxy

### After running the script:

```bash
# Verify xray is running
systemctl status xray-proxy

# Test proxy works
curl --proxy socks5://127.0.0.1:10808 https://www.google.com

# Test Gemini API
curl --proxy socks5://127.0.0.1:10808 https://generativelanguage.googleapis.com/
```

### Optional: Full TUN mode (routes ALL traffic through VPN)

Only do this if SOCKS-only mode doesn't work:

```bash
sudo systemctl enable --now tun2socks
```

⚠️ **WARNING**: TUN mode routes ALL traffic through VPN. If VPN fails, you lose SSH access!

---

## PHASE 5: Update Artifact App

Pull latest code and restart:

```bash
cd ~/modular-arcade
git pull

# Install new dependency
.venv/bin/pip install aiohttp-socks

# Restart artifact
sudo systemctl restart artifact

# Check logs
journalctl -u artifact -f
```

---

## PHASE 6: Test Everything

```bash
# 1. Check xray proxy is running
systemctl status xray-proxy

# 2. Check Gemini API is reachable
curl --proxy socks5://127.0.0.1:10808 \
  "https://generativelanguage.googleapis.com/" -I

# 3. Check Tailscale is stable
tailscale status

# 4. Check artifact is running
systemctl status artifact

# 5. Test photobooth manually (if possible)
```

---

## FALLBACK: Local Mode Only

If NOTHING works with VPN, just disable AI and use local polaroid:

```bash
# Edit the service to disable proxy
sudo sed -i 's/GEMINI_USE_PROXY=true/GEMINI_USE_PROXY=false/' /etc/systemd/system/artifact.service
sudo systemctl daemon-reload
sudo systemctl restart artifact
```

The photobooth will work perfectly with local polaroid generation - no AI needed.

---

## Quick Reference

| What | Command |
|------|---------|
| SSH via Tailscale | `ssh kirniy@100.x.x.x` |
| SSH via local IP | `ssh kirniy@192.168.2.x` |
| Pi password | `qaz123` |
| Setup VPN | `./scripts/setup-xray-vpn.sh` |
| Check xray | `systemctl status xray-proxy` |
| Check logs | `journalctl -u artifact -f` |
| Restart artifact | `sudo systemctl restart artifact` |
| Test proxy | `curl --proxy socks5://127.0.0.1:10808 https://google.com` |

---

## What Went Wrong (For Future Reference)

1. **sing-box TUN mode with `auto_route: true`** - hijacked entire routing table, broke everything when VPN hiccuped

2. **Another agent created `persist-venue-route.service`** - kept fucking with routes, causing instability

3. **DNS got corrupted** - Tailscale couldn't resolve controlplane.tailscale.com, causing disconnects even with sing-box OFF

4. **IP address hacks (.150)** - manually adding secondary IPs confused NetworkManager

5. **Another agent tried switching to VNVNC WiFi** - may have left Pi in limbo between networks

6. **All eggs in one basket** - when VPN broke, EVERYTHING broke including Tailscale

**The fix**:
- Fix DNS first (8.8.8.8, 1.1.1.1)
- Remove all rogue services
- Use SOCKS proxy mode (not TUN), only route Gemini traffic through VPN
- Configure both WiFi networks so Pi can fall back

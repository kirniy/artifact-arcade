#!/bin/bash
# =============================================================================
# ARTIFACT Audio Setup - Maximum Nightclub Volume
# =============================================================================
# This script configures the Raspberry Pi 4 audio for maximum volume output
# through the 3.5mm headphone jack (bcm2835 card 2).
#
# Run this:
# - At boot via systemd (artifact-audio.service)
# - Manually when audio isn't working
#
# The script:
# 1. Loads the snd-bcm2835 audio driver
# 2. Sets volume to absolute maximum (+4dB)
# 3. Unmutes all channels
# 4. Verifies audio is working
# =============================================================================

set -e

echo "=== ARTIFACT Audio Setup ==="
echo "Configuring maximum nightclub volume..."

# -----------------------------------------------------------------------------
# 1. Load audio driver if not already loaded
# -----------------------------------------------------------------------------
echo "Loading snd-bcm2835 audio driver..."
if ! lsmod | grep -q snd_bcm2835; then
    modprobe snd-bcm2835
    sleep 1
    echo "  -> Driver loaded"
else
    echo "  -> Driver already loaded"
fi

# Verify card 2 exists (bcm2835 Headphones)
if ! aplay -l | grep -q "card 2"; then
    echo "ERROR: Card 2 (bcm2835 Headphones) not found!"
    echo "Available cards:"
    aplay -l
    exit 1
fi
echo "  -> Card 2 (bcm2835 Headphones) detected"

# -----------------------------------------------------------------------------
# 2. Set volume to absolute maximum (+4dB)
# -----------------------------------------------------------------------------
echo "Setting volume to maximum (+4dB)..."

# Card 2 (bcm2835 Headphones) controls:
# - numid=1: PCM Playback Volume (range: -10239 to 400, 400 = +4dB)
# - numid=2: PCM Playback Switch (on/off)

# Set PCM volume to 400 (+4dB) - the absolute maximum
amixer -c 2 cset numid=1 400 2>/dev/null && echo "  -> numid=1 (volume) = 400 (+4dB)" || true

# Unmute PCM
amixer -c 2 cset numid=2 on 2>/dev/null && echo "  -> numid=2 (switch) = on" || true

# Fallback: try named controls
amixer -c 2 sset PCM 100% unmute 2>/dev/null && echo "  -> PCM = 100% unmute" || true
amixer sset PCM 100% unmute 2>/dev/null || true
amixer sset Master 100% unmute 2>/dev/null || true

# -----------------------------------------------------------------------------
# 3. Set ALSA defaults to card 2
# -----------------------------------------------------------------------------
echo "Setting ALSA defaults..."

# Create /etc/asound.conf if it doesn't exist or update it
cat > /etc/asound.conf << 'EOF'
# ARTIFACT Audio Configuration
# Default to bcm2835 Headphones (card 2) for maximum volume nightclub audio

pcm.!default {
    type hw
    card 2
    device 0
}

ctl.!default {
    type hw
    card 2
}

# Alias for hw:2,0
pcm.headphones {
    type hw
    card 2
    device 0
}

# Software volume control (if needed for finer control)
pcm.softvol {
    type softvol
    slave.pcm "headphones"
    control {
        name "SoftMaster"
        card 2
    }
    min_dB -51.0
    max_dB 0.0
}
EOF
echo "  -> /etc/asound.conf configured"

# -----------------------------------------------------------------------------
# 4. Ensure module loads at boot
# -----------------------------------------------------------------------------
echo "Configuring module autoload..."

# Create modules-load.d config
echo "snd-bcm2835" > /etc/modules-load.d/audio.conf
echo "  -> /etc/modules-load.d/audio.conf created"

# -----------------------------------------------------------------------------
# 5. Verify configuration
# -----------------------------------------------------------------------------
echo ""
echo "=== Audio Configuration Complete ==="
echo ""
echo "Current volume levels:"
amixer -c 2 sget PCM 2>/dev/null || amixer -c 2 contents | head -20

echo ""
echo "Available audio devices:"
aplay -l | grep -E "^card"

echo ""
echo "Testing audio output (brief beep)..."
# Generate a short 440Hz sine wave beep to verify audio works
if command -v speaker-test &> /dev/null; then
    timeout 0.5 speaker-test -D hw:2,0 -t sine -f 440 -l 1 2>/dev/null || true
    echo "  -> Audio test complete (if you heard a beep, audio is working!)"
else
    echo "  -> speaker-test not available, skipping audio test"
fi

echo ""
echo "=== ARTIFACT ready for maximum volume! ==="
echo "Audio device: hw:2,0 (bcm2835 Headphones)"
echo "Volume: +4dB (maximum)"

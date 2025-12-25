# LED Panel Test Commands (with auto-kill)

Run each command, wait 10 seconds, observe display, Ctrl+C to stop.

---

## Kill command (run if display stuck)
```bash
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo"
```

---

## Phase 2: Multiplexing 5-17 (remaining)

```bash
# mux=5
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=5"
```

```bash
# mux=6
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=6"
```

```bash
# mux=7
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=7"
```

```bash
# mux=8
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=8"
```

```bash
# mux=9
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=9"
```

```bash
# mux=10
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=10"
```

```bash
# mux=11
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=11"
```

```bash
# mux=12
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=12"
```

```bash
# mux=13
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=13"
```

```bash
# mux=14
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=14"
```

```bash
# mux=15
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=15"
```

```bash
# mux=16
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=16"
```

```bash
# mux=17
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=17"
```

---

## Phase 3: Multiplexing + row-addr-type=3

```bash
# mux=1 + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=1 --led-row-addr-type=3"
```

```bash
# mux=2 + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=2 --led-row-addr-type=3"
```

```bash
# mux=3 + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=3 --led-row-addr-type=3"
```

```bash
# mux=4 + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=4 --led-row-addr-type=3"
```

```bash
# mux=5 + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=5 --led-row-addr-type=3"
```

---

## Phase 4: Without FM6126A Panel Type

```bash
# No panel type (default)
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100"
```

```bash
# No panel type + row-addr-type=3
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=4 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-row-addr-type=3"
```

---

## Phase 6: Single Panel Isolation Tests (COMPLETE)

Disconnect panels 2, 3, 4. Only panel 1 connected.

```bash
# rows=64, single panel
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=64 --led-cols=64 --led-chain=1 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A"
```

```bash
# rows=32, single panel (shows more content!)
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=32 --led-cols=64 --led-chain=1 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A"
```

```bash
# rows=32, mux=2, single panel
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=32 --led-cols=64 --led-chain=1 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100 --led-panel-type=FM6126A --led-multiplexing=2"
```

```bash
# rows=32, no FM6126A, single panel
sshpass -p "qaz123" ssh kirniy@artifact.local "sudo pkill -9 demo 2>/dev/null; cd ~/rpi-rgb-led-matrix/examples-api-use && sudo ./demo -D0 --led-gpio-mapping=regular --led-rows=32 --led-cols=64 --led-chain=1 --led-parallel=1 --led-slowdown-gpio=4 --led-brightness=100"
```

**Results:**
- rows=64: Content only in bottom-right quadrant
- rows=32: Content spread more, still garbled
- rows=32 + mux=2: Blue rect in bottom-right
- rows=32 + no FM6126A: Blue rect + green diagonal (demo animation visible!)

---

## Phase 8: Pixel Diagnostic Script

First, copy the script to Pi:
```bash
scp scripts/panel_diagnostic.py kirniy@artifact.local:~/
```

Then run interactive diagnostic (SSH into Pi terminal):
```bash
ssh kirniy@artifact.local
cd ~
sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py --rows=32 --cols=64 --chain=1 --brightness=50
```

Try different configurations:
```bash
# With FM6126A
sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py --rows=32 --cols=64 --chain=1 --brightness=50 --panel-type=FM6126A

# With different multiplexing
sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py --rows=32 --cols=64 --chain=1 --brightness=50 --mux=2

# Full 64-row mode
sudo PYTHONPATH=/home/kirniy/rpi-rgb-led-matrix/bindings/python python3 panel_diagnostic.py --rows=64 --cols=64 --chain=1 --brightness=50
```

The diagnostic script will:
1. Test solid color fills
2. Show colored quadrants (red/green/blue/yellow)
3. Draw diagonals
4. Light up individual corner pixels
5. Test rows and columns
6. Show numbered grid pattern
7. Test address lines

Take photos at each step to analyze pixel mapping!

---

## Results so far

Phase 2:
- mux=0: GARBLED (baseline)
- mux=1: BLACK
- mux=2: GARBLED (lots of colors)
- mux=3: BLACK
- mux=4: GARBLED (similar to mux=2)
- mux=5:
- mux=6:
- mux=7:
- mux=8:
- mux=9:
- mux=10:
- mux=11:
- mux=12:
- mux=13:
- mux=14:
- mux=15:
- mux=16:
- mux=17:

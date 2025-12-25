# NovaStar T50 & DH418 Configuration

## Hardware Specifications
- **Sender:** NovaStar T50 (Taurus Series)
- **Receiver:** NovaStar DH418
- **Panels:** 4x P3-64x64-32S-v3
  - **Resolution:** 64 x 64 pixels each
  - **Driver IC:** Chipone ICN2153 (Select `ICND2153` in NovaLCT)
  - **Scan Rate:** 1/32 Scan
  - **Data Groups:** 2 groups per module (Standard for 64px height with 32s scan, usually)
  - **Total Resolution:** 128 x 128 (2x2 grid)

## VM & Network Access
The T50 is located on the local network (`192.168.0.10`). Configuration is done via an Azure Windows VM using NovaLCT. 
**Connection Method:** Tailscale VPN.
1.  **Local Machine:** Tailscale must advertise local routes: `sudo tailscale up --advertise-routes=192.168.0.0/24`
2.  **Azure VM:** Tailscale connected. Can ping `192.168.0.10`.
3.  **NovaLCT:** Login (admin/admin or admin/123456). If device not found, try "Advanced Synchronous System User Login" or manually specify IP in Communication Settings.

## Wiring Plan
**Goal:** 128x128 Screen (2x2 Panels).
**Method:** Drive each panel from a separate HUB75 port on the DH418 (Star Topology). This is preferred over daisy-chaining one long string for configuration simplicity on this specific receiver.

**Connections:**
- **DH418 Port JH1** -> Panel 1 (Bottom-Left)
- **DH418 Port JH2** -> Panel 2 (Top-Left)
- **DH418 Port JH3** -> Panel 3 (Top-Right)
- **DH418 Port JH4** -> Panel 4 (Bottom-Right)
*(Note: Physical arrangement depends on how you physically mount them, logical mapping is done in software)*

## Troubleshooting History & Findings
1.  **Garbage/Flicker:** Originally caused by incorrect scan rate (1/8 vs 1/32) and unknown driver IC. Resolved by identifying ICN2153.
2.  **legacy Config:** "Readback" from the card revealed a `64x192` Irregular Cabinet config (3 vertical panels). This was for a previous "Countdown Clock" project.
3.  **Correcting Config:**
    - The `.rcfgx` file contains critical driver timings (ShiftUnitNum, etc.) which are correct.
    - The "Cabinet" definition inside the file (Irregular 3-panel) is WRONG for the new 2x2 setup.
    - **Fix:** We must load the existing driver settings but redefine the Cabinet Layout to be **Regular 128x128** (composed of 4x 64x64 modules).

## Configuration Steps (Next Session)
1.  **Wire up the panels** to Ports 1-4 on the DH418.
2.  **Connect to NovaLCT** via VM.
3.  **Receiving Card Tab:**
    - Load `current.rcfgx` (or Readback) to get the ICN2153 settings.
    - **CRITICAL:** Change "Cabinet Information" to **Regular**.
    - Set Width: **128**, Height: **128**. (Use "Construct Cabinet" if needed to specify 2x2 module layout).
    - Ensure "Data Groups" maps correctly to the 4 ports.
4.  **Screen Connection Tab:**
    - Configure **1 Receiving Card** (Size 128x128).
    - Position it at (0,0).
5.  **Send to Hardware** & **Save**.

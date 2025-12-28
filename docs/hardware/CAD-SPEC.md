# ARTIFACT Cabinet — CAD Specification v4

**Base Model:** `docs/hardware/arcade_cabinet.step` (Autodesk 2020, copied to project)
**Units:** Millimeters (mm)
**Material:** 18mm plywood

---

## APPROACH: Modify Existing Model

Instead of building from scratch, we use a proven arcade cabinet STEP file and modify it.

### Step 1: Import the Base Model

```
1. Open FreeCAD
2. File → Import → select "arcade_cabinet.step"
3. Wait for import (may take 30-60 seconds)
4. View → Fit All (or press V, F)
```

### Step 2: Examine the Imported Parts

The model contains these components:
- **Left panel / Right panel** - Side walls
- **Back panel** - Rear wall
- **Bottom panel** - Floor
- **Button panel** - Control panel (angled)
- **Front panel below button panel** - Lower front
- **Front panel hatch + door** - Access panel
- **Screen panel** - Display frame
- **Left/Right hold screen panel** - Screen supports
- **Top panel lightbox** - Marquee
- **Bottom/Top left/right holder lightbox** - Marquee supports
- **4× feet** - Cabinet feet

### Step 3: Measure & Scale

Original model dimensions (approximate):
- Width: ~630mm
- Height: ~1760mm (including feet)
- Depth: ~550mm

Our target dimensions:
- Width: 540mm (for 480mm ticker)
- Height: 1750mm
- Depth: 500mm

**Scale factors:**
- X (width): 540/630 = 0.857
- Y (height): 1750/1760 = 0.994
- Z (depth): 500/550 = 0.909

### Step 4: Modify in FreeCAD

```python
# FreeCAD Python console - scale the entire assembly
import FreeCAD

# Select all objects
for obj in FreeCAD.ActiveDocument.Objects:
    if hasattr(obj, 'Shape'):
        # Scale: X=0.857, Y=0.994, Z=0.909
        mat = FreeCAD.Matrix()
        mat.scale(0.857, 0.994, 0.909)
        obj.Shape = obj.Shape.transformGeometry(mat)

FreeCAD.ActiveDocument.recompute()
```

### Step 5: Run the Modification Script

Use the provided Python script to automatically scale the model:

```
1. Import arcade_cabinet.step into FreeCAD
2. View → Panels → Python Console
3. Copy contents of freecad_modify_cabinet.py into console
4. Press Enter to run
```

The script will scale the cabinet to 540×500×1750mm automatically.

---

## CONTROL PANEL LAYOUT

```
┌─────────────────────────────────────────────────────────────────┐
│                      CONTROL PANEL (angled 15°)                 │
│                           504 × 200 mm                          │
│                                                                 │
│     ┌───┐                                         ┌─────────┐   │
│     │ ◀ │         ┌─────────────┐                │ NUMPAD  │   │
│     │30 │         │             │                │         │   │
│     └───┘         │   BIG RED   │                │ 137×85  │   │
│                   │    BUTTON   │                │   mm    │   │
│  -80mm            │    Ø60mm    │     +150mm     │         │   │
│                   │             │                │  (USB)  │   │
│     ┌───┐         └─────────────┘                └─────────┘   │
│     │ ▶ │                                                       │
│     │30 │                                                       │
│     └───┘                                                       │
│    +80mm            CENTER                                      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

All positions relative to panel center (X=252mm from left edge)
```

### Control Panel Cutouts

| Component | Type | Size | Position (from center) |
|-----------|------|------|------------------------|
| Big Red Button | Circle | Ø60mm | Center (0, 0) |
| Left Button | Circle | Ø30mm | -80mm X |
| Right Button | Circle | Ø30mm | +80mm X |
| Numpad Recess | Rectangle | 137×85mm | +150mm X |

### Numpad Specs
- **Model**: USB Numeric Keypad
- **Dimensions**: 137 × 85 × 10 mm
- **Mounting**: Recessed 8mm into panel, secured with adhesive or screws

---

## DISPLAY CUTOUTS

### Front Upper Panel (Screen Section)

```
┌─────────────────────────────────────────────────────────────────┐
│                    FRONT UPPER PANEL                            │
│                       504 × 550 mm                              │
│                                                                 │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │                      TICKER WINDOW                        │  │
│  │                       490 × 90 mm                         │  │ 20mm from top
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
│           ┌─────────────────────────────────┐                   │
│           │                                 │                   │
│           │         MAIN DISPLAY            │                   │
│           │           WINDOW                │                   │
│           │         395 × 395 mm            │                   │
│           │                                 │                   │
│           │     (for 384×384 LED panel)     │                   │
│           │                                 │                   │
│           └─────────────────────────────────┘                   │
│                                                                 │ 100mm from bottom
└─────────────────────────────────────────────────────────────────┘
```

### Front Lower Panel Cutouts

| Component | Type | Size | Position |
|-----------|------|------|----------|
| Printer Slot | Rectangle | 80×30mm | Centered, 200mm from bottom |
| Vent Holes | Circles | 6× Ø30mm | Bottom corners, spaced 50mm |

---

## ALTERNATIVE: Simple Build from Scratch

```
SIDE VIEW (what you'd see looking at the LEFT side from outside):

        _______________
       /               |   ← Angled marquee top
      /                |
     |                 |   ← Vertical screen section
     |                 |
     |                 |
     |_                |   ← Control panel (angled surface, NOT a notch)
     | \               |
     |  \______________|   ← Angled control panel
     |                 |
     |                 |   ← Base section
     |_________________|

     FRONT            BACK
```

---

## MASTER DIMENSIONS

```
WIDTH  = 540 mm   (X axis - set by ticker width 480 + margins)
DEPTH  = 500 mm   (Y axis - comfortable reach depth)
HEIGHT = 1750 mm  (Z axis - marquee at eye level)
T      = 18 mm    (plywood thickness)
```

---

## THE 8 PANELS

This cabinet uses only **8 rectangular panels** (some angled during assembly):

| # | Panel | Dimensions (mm) | Notes |
|---|-------|-----------------|-------|
| 1 | Left Side | 500 × 1750 | Full rectangle |
| 2 | Right Side | 500 × 1750 | Full rectangle |
| 3 | Bottom | 504 × 464 | Sits between sides |
| 4 | Back | 504 × 1714 | Full height back |
| 5 | Front Lower | 504 × 900 | Below control panel |
| 6 | Control Panel | 504 × 200 | Angled 15° |
| 7 | Front Upper | 504 × 550 | Screen area with cutout |
| 8 | Top/Marquee | 504 × 300 | Angled 20° back |

---

## COMPLETE FREECAD PYTHON SCRIPT

Copy this ENTIRE script into FreeCAD Python console:

```python
import FreeCAD
import Part

# Create new document
doc = FreeCAD.newDocument("ARTIFACT_Cabinet")

# ============================================
# DIMENSIONS
# ============================================
WIDTH = 540      # Total external width
DEPTH = 500      # Total external depth
HEIGHT = 1750    # Total external height
T = 18           # Material thickness

# Internal dimensions (between side panels)
INNER_W = WIDTH - 2*T   # 504
INNER_D = DEPTH - 2*T   # 464

# Heights for horizontal divisions
CONTROL_PANEL_Z = 900   # Height where control panel starts
UPPER_FRONT_Z = 1100    # Height where upper front panel starts
MARQUEE_Z = 1650        # Height where marquee starts

# ============================================
# PANEL 1: LEFT SIDE (simple rectangle)
# ============================================
left_side = doc.addObject("Part::Box", "Left_Side")
left_side.Length = T           # 18 (thickness in X)
left_side.Width = DEPTH        # 500 (full depth in Y)
left_side.Height = HEIGHT      # 1750 (full height in Z)
left_side.Placement.Base = FreeCAD.Vector(0, 0, 0)

# ============================================
# PANEL 2: RIGHT SIDE (simple rectangle)
# ============================================
right_side = doc.addObject("Part::Box", "Right_Side")
right_side.Length = T
right_side.Width = DEPTH
right_side.Height = HEIGHT
right_side.Placement.Base = FreeCAD.Vector(WIDTH - T, 0, 0)  # X = 522

# ============================================
# PANEL 3: BOTTOM (horizontal, between sides)
# ============================================
bottom = doc.addObject("Part::Box", "Bottom")
bottom.Length = INNER_W        # 504
bottom.Width = INNER_D         # 464
bottom.Height = T              # 18
bottom.Placement.Base = FreeCAD.Vector(T, T, 0)  # (18, 18, 0)

# ============================================
# PANEL 4: BACK (vertical, full height)
# ============================================
back = doc.addObject("Part::Box", "Back")
back.Length = INNER_W          # 504
back.Width = T                 # 18
back.Height = HEIGHT - T       # 1732 (floor to just below top)
back.Placement.Base = FreeCAD.Vector(T, DEPTH - T, T)  # (18, 482, 18)

# ============================================
# PANEL 5: FRONT LOWER (vertical, floor to control panel)
# ============================================
front_lower = doc.addObject("Part::Box", "Front_Lower")
front_lower.Length = INNER_W   # 504
front_lower.Width = T          # 18
front_lower.Height = CONTROL_PANEL_Z  # 900
front_lower.Placement.Base = FreeCAD.Vector(T, 0, 0)  # (18, 0, 0)

# ============================================
# PANEL 6: CONTROL PANEL (angled 15° down toward player)
# ============================================
control = doc.addObject("Part::Box", "Control_Panel")
control.Length = INNER_W       # 504
control.Width = 200            # 200mm deep
control.Height = T             # 18

# Position: front edge at Y=18 (behind front panel), Z=900
control.Placement.Base = FreeCAD.Vector(T, T, CONTROL_PANEL_Z)

# Rotate 15° around X axis (front edge tilts down)
import math
control.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), -15)

# ============================================
# PANEL 7: FRONT UPPER (vertical, with display cutout)
# ============================================
front_upper = doc.addObject("Part::Box", "Front_Upper")
front_upper.Length = INNER_W   # 504
front_upper.Width = T          # 18
front_upper.Height = MARQUEE_Z - UPPER_FRONT_Z  # 550
front_upper.Placement.Base = FreeCAD.Vector(T, 0, UPPER_FRONT_Z)  # (18, 0, 1100)

# ============================================
# PANEL 8: TOP/MARQUEE (angled 20° backward)
# ============================================
marquee = doc.addObject("Part::Box", "Marquee")
marquee.Length = INNER_W       # 504
marquee.Width = 300            # 300mm deep
marquee.Height = T             # 18

# Position at top
marquee.Placement.Base = FreeCAD.Vector(T, 50, MARQUEE_Z)

# Rotate 20° around X axis (front edge tilts up, back tilts down)
marquee.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 20)

# ============================================
# INTERNAL SHELF (for electronics)
# ============================================
shelf = doc.addObject("Part::Box", "Internal_Shelf")
shelf.Length = INNER_W         # 504
shelf.Width = INNER_D - 50     # 414 (some clearance from back)
shelf.Height = T               # 18
shelf.Placement.Base = FreeCAD.Vector(T, T + 25, 200)  # (18, 43, 200)

# ============================================
# FINISH
# ============================================
doc.recompute()

# Set view
if FreeCAD.GuiUp:
    FreeCAD.Gui.activeDocument().activeView().viewIsometric()
    FreeCAD.Gui.SendMsgToActiveView("ViewFit")

print("ARTIFACT Cabinet created successfully!")
print(f"External: {WIDTH} x {DEPTH} x {HEIGHT} mm")
print(f"Internal: {INNER_W} x {INNER_D} mm")
```

---

## VISUAL LAYOUT

### Front View (looking at the cabinet face)
```
         540mm
    ←───────────────→
    ┌───────────────┐ ─┬─
    │   [MARQUEE]   │  │ 100mm (angled back)
    ├───────────────┤ ─┼─ Z=1650
    │               │  │
    │  ┌─────────┐  │  │
    │  │ TICKER  │  │  │ 550mm
    │  │ 480×80  │  │  │
    │  └─────────┘  │  │
    │               │  │
    │  ┌─────────┐  │  │
    │  │  MAIN   │  │  │
    │  │ DISPLAY │  │  │
    │  │ 384×384 │  │  │
    │  └─────────┘  │  │
    ├───────────────┤ ─┼─ Z=1100
    │ CONTROL PANEL │  │ 200mm (angled 15°)
    │  [●] [●] [●]  │  │
    ├───────────────┤ ─┼─ Z=900
    │               │  │
    │               │  │
    │     BASE      │  │ 900mm
    │    SECTION    │  │
    │               │  │
    │   [PRINTER]   │  │
    │               │  │
    └───────────────┘ ─┴─ Z=0
```

### Side View (looking at left side from outside)
```
              500mm
    ←─────────────────────→
    FRONT                BACK

    ┌──╲___________________┐ ─┬─ Z=1750
    │   ╲                  │  │  Marquee (20° angle)
    │    ╲_________________│ ─┼─ Z=1650
    │                      │  │
    │                      │  │
    │    SCREEN SECTION    │  │  550mm
    │                      │  │
    │                      │  │
    │______                │ ─┼─ Z=1100
    │      ╲               │  │  Control (15° angle)
    │       ╲______________│ ─┼─ Z=900
    │                      │  │
    │                      │  │
    │    BASE SECTION      │  │  900mm
    │                      │  │
    │    [shelf at 200]    │  │
    │                      │  │
    └──────────────────────┘ ─┴─ Z=0

    Y=0                  Y=500
```

---

## CUT LIST (for 18mm plywood)

| Panel | Cut Size | Qty | Notes |
|-------|----------|-----|-------|
| Side Panels | 500 × 1750 mm | 2 | Full rectangles |
| Bottom | 504 × 464 mm | 1 | |
| Back | 504 × 1732 mm | 1 | |
| Front Lower | 504 × 900 mm | 1 | |
| Control Panel | 504 × 200 mm | 1 | Mount at 15° angle |
| Front Upper | 504 × 550 mm | 1 | Cut display window |
| Marquee | 504 × 300 mm | 1 | Mount at 20° angle |
| Internal Shelf | 504 × 414 mm | 1 | Optional |

**Total plywood needed:** ~2.5 m² (one 2440×1220mm sheet is plenty)

---

## CUTOUTS TO ADD

### Front Upper Panel Cutouts:
1. **Main Display Window**: 395 × 395 mm, centered horizontally, 100mm from bottom
2. **Ticker Window**: 490 × 90 mm, centered horizontally, 20mm from top

### Front Lower Panel Cutouts:
1. **Printer Slot**: 80 × 30 mm, centered, 200mm from bottom
2. **Ventilation**: Several 30mm holes near bottom

### Control Panel Cutouts:
1. **Big Red Button**: Ø62mm hole, centered
2. **Arcade Buttons**: 4× Ø30mm holes, arranged around center

---

## ASSEMBLY ORDER

1. Attach Bottom to Left Side (screws from outside of side into bottom edge)
2. Attach Right Side to Bottom
3. Attach Back panel (screws through sides into back edges)
4. Attach Front Lower panel
5. Install Control Panel at 15° angle (use triangular support blocks)
6. Attach Front Upper panel
7. Install Marquee at 20° angle (use angled brackets)
8. Add Internal Shelf

---

## CHECKLIST

- [ ] All side panels are SIMPLE RECTANGLES (500 × 1750)
- [ ] All front/back panels are BETWEEN side panels (504mm wide)
- [ ] Control panel angled 15° (front edge lower)
- [ ] Marquee angled 20° (front edge higher)
- [ ] No gaps between panels
- [ ] Display cutouts centered and correctly sized

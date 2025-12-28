# -*- coding: utf-8 -*-
"""
ARTIFACT Cabinet — CAD Specification v2 (FreeCAD generator)
Units: mm
Origin: front-bottom-left of assembled cabinet
Axes: X left→right, Y front→back, Z bottom→top
Material thickness: 18 mm plywood

This script is designed to avoid the typical "random boxes floating" failure mode:
- Side panels are a single closed profile extruded along X.
- All other panels are created in global coordinates and (when angled) rotated around explicit hinge lines.
- Front screen cutouts are true boolean cuts through the panel thickness.
- Includes geometry sanity checks and bounding-box checks.

Run (headless):
  FreeCADCmd artifact_cabinet_v2_freecad.py

Run (GUI):
  Macro → Macros… → Execute (or open in Python console)

Outputs:
  - Saves FCStd if SAVE_FCSTD is True
  - Exports STEP if EXPORT_STEP is True
"""

import os
import sys
import math

import FreeCAD as App
import Part

# -----------------------------
# PARAMETERS (EDIT THESE FIRST)
# -----------------------------
TOTAL_WIDTH  = 540.0
TOTAL_DEPTH  = 500.0
TOTAL_HEIGHT = 1750.0
T            = 18.0

INTERNAL_WIDTH = TOTAL_WIDTH - 2*T           # 504
INTERNAL_DEPTH = TOTAL_DEPTH - 2*T           # 464

# Side panel profile (Y, Z) in order, closed implicitly
PROFILE_YZ = [
    (0,    0),     # V0
    (0,    400),   # V1
    (150,  400),   # V2
    (150,  500),   # V3
    (0,    500),   # V4
    (0,    1400),  # V5
    (100,  1500),  # V6
    (100,  1650),  # V7
    (350,  1750),  # V8
    (500,  1750),  # V9
    (500,  0),     # V10
]

# Control panel
CONTROL_DEPTH_Y = 150.0
CONTROL_Z       = 400.0
CONTROL_ANGLE_DEG = -12.0
# Note on sign: your spec says -12°. If your panel tilts the wrong way, flip to +12°.

# Front panels
FRONT_BASE_Z_TOP   = 400.0
FRONT_SCREEN_Z0    = 500.0
FRONT_SCREEN_H     = 900.0   # 500..1400
FRONT_THICK_Y      = T

# Screen cutouts (in Front_Screen local coordinates: X from left of internal width, Z from panel bottom)
MAIN_WIN_W = 395.0
MAIN_WIN_H = 395.0
MAIN_WIN_X = (INTERNAL_WIDTH - MAIN_WIN_W) / 2.0      # 54.5
MAIN_WIN_Z = 200.0

TICK_WIN_W = 490.0
TICK_WIN_H = 90.0
TICK_WIN_X = (INTERNAL_WIDTH - TICK_WIN_W) / 2.0      # 7
TICK_WIN_Z = 750.0

# Back panel
BACK_Z0     = T
BACK_Y0     = TOTAL_DEPTH - T
BACK_HEIGHT = 1632.0  # per spec
# That ends at Z=1650, which matches profile V7 Z=1650.

# Internal shelf
SHELF_Z0 = 150.0
SHELF_Y0 = 50.0
SHELF_WY = 400.0

# Optional closure pieces derived from your side profile (makes the cabinet look "real" and reduces gaps)
CLOSE_UPPER_FRONT = True   # fills the 1400→1650 front transition that exists in your profile
CLOSE_TOP         = True   # adds sloped roof + back cap to match V7→V8→V9

# Export options
OUT_DIR     = os.path.abspath(os.path.dirname(__file__)) if "__file__" in globals() else os.getcwd()
DOC_NAME    = "ARTIFACT_Cabinet_v2"
SAVE_FCSTD  = True
EXPORT_STEP = True

FCSTD_PATH  = os.path.join(OUT_DIR, f"{DOC_NAME}.FCStd")
STEP_PATH   = os.path.join(OUT_DIR, f"{DOC_NAME}.step")


# -----------------------------
# UTILS
# -----------------------------
EPS = 1e-6

def v(x, y, z):
    return App.Vector(float(x), float(y), float(z))

def die(msg):
    raise RuntimeError(msg)

def assert_in_range(name, val, lo, hi):
    if not (lo - EPS <= val <= hi + EPS):
        die(f"{name}={val} out of range [{lo}, {hi}]")

def assert_le(name, a, b):
    if a > b + EPS:
        die(f"{name} failed: {a} > {b}")

def bbox_str(bb):
    return f"X[{bb.XMin:.2f},{bb.XMax:.2f}] Y[{bb.YMin:.2f},{bb.YMax:.2f}] Z[{bb.ZMin:.2f},{bb.ZMax:.2f}]"

def rotate_shape_about_x(shape, hinge_y, hinge_z, angle_deg, hinge_x=None):
    """
    Rotate a shape about an X-axis hinge line located at (any X, Y=hinge_y, Z=hinge_z).
    We use hinge_x at the mid internal width by default, but any X is equivalent for an X-axis rotation.
    """
    if hinge_x is None:
        hinge_x = T + INTERNAL_WIDTH / 2.0
    shp = shape.copy()
    shp.rotate(v(hinge_x, hinge_y, hinge_z), v(1, 0, 0), float(angle_deg))
    return shp

def make_feature(doc, name, shape):
    obj = doc.addObject("Part::Feature", name)
    obj.Shape = shape
    return obj

def make_box(lx, ly, lz, base):
    return Part.makeBox(float(lx), float(ly), float(lz), base)

def make_extruded_side(doc, name, x0):
    pts = [v(x0, y, z) for (y, z) in PROFILE_YZ]
    pts.append(pts[0])
    wire = Part.makePolygon(pts)

    if not wire.isClosed():
        die("Side profile wire is not closed. Check PROFILE_YZ order.")
    if not wire.isValid():
        die("Side profile wire is invalid (self-intersection / bad order). Check PROFILE_YZ.")

    try:
        face = Part.Face(wire)
    except Exception as e:
        die(f"Failed to create side face: {e}")

    solid = face.extrude(v(T, 0, 0))
    return make_feature(doc, name, solid)

def cut_rect_through_front_panel(panel_shape, panel_base, local_x, local_z, w, h, extra_y=4.0):
    """
    Cut a rectangular window through a front panel that is thickness FRONT_THICK_Y in Y.
    panel_base = (x,y,z) where panel was placed.
    local_x/local_z relative to panel_base.
    We make cutter slightly thicker in Y (extra_y) so the cut always fully goes through.
    """
    if w <= 0 or h <= 0:
        die("Cutout size must be positive")

    cutter = make_box(
        w,
        FRONT_THICK_Y + extra_y,
        h,
        v(panel_base.x + local_x, panel_base.y - extra_y/2.0, panel_base.z + local_z),
    )
    return panel_shape.cut(cutter)

def within_global_bounds(name, shape, xmin, xmax, ymin, ymax, zmin, zmax, slack=2.0):
    bb = shape.BoundBox
    if bb.XMin < xmin - slack or bb.XMax > xmax + slack or bb.YMin < ymin - slack or bb.YMax > ymax + slack or bb.ZMin < zmin - slack or bb.ZMax > zmax + slack:
        die(f"{name} out of global bounds.\n  {bbox_str(bb)}\n  expected within X[{xmin},{xmax}] Y[{ymin},{ymax}] Z[{zmin},{zmax}] (±{slack}mm)")

def validate_profile():
    ys = [p[0] for p in PROFILE_YZ]
    zs = [p[1] for p in PROFILE_YZ]
    if abs(min(ys) - 0.0) > EPS: die("PROFILE_YZ must start at Y>=0 and include Y=0.")
    if abs(min(zs) - 0.0) > EPS: die("PROFILE_YZ must include Z=0.")
    if abs(max(ys) - TOTAL_DEPTH) > 1e-3:
        die(f"PROFILE_YZ max Y should be TOTAL_DEPTH ({TOTAL_DEPTH}), got {max(ys)}")
    if abs(max(zs) - TOTAL_HEIGHT) > 1e-3:
        die(f"PROFILE_YZ max Z should be TOTAL_HEIGHT ({TOTAL_HEIGHT}), got {max(zs)}")

def validate_cutouts():
    # Must fit inside the Front_Screen panel (INTERNAL_WIDTH x FRONT_SCREEN_H)
    for (nm, x0, z0, w, h) in [
        ("MAIN_WINDOW", MAIN_WIN_X, MAIN_WIN_Z, MAIN_WIN_W, MAIN_WIN_H),
        ("TICKER_WINDOW", TICK_WIN_X, TICK_WIN_Z, TICK_WIN_W, TICK_WIN_H),
    ]:
        assert_in_range(f"{nm}.x0", x0, 0, INTERNAL_WIDTH)
        assert_in_range(f"{nm}.z0", z0, 0, FRONT_SCREEN_H)
        assert_le(f"{nm}.x0+w", x0 + w, INTERNAL_WIDTH)
        assert_le(f"{nm}.z0+h", z0 + h, FRONT_SCREEN_H)

def validate_params():
    if abs(INTERNAL_WIDTH - 504.0) > 1e-3:
        die(f"INTERNAL_WIDTH mismatch: {INTERNAL_WIDTH} (expected 504)")
    if abs(INTERNAL_DEPTH - 464.0) > 1e-3:
        die(f"INTERNAL_DEPTH mismatch: {INTERNAL_DEPTH} (expected 464)")
    validate_profile()
    validate_cutouts()


# -----------------------------
# BUILD
# -----------------------------
def build(doc):
    validate_params()

    # Side panels: left at X=0..18, right at X=522..540
    side_left  = make_extruded_side(doc, "Side_Left", 0.0)
    side_right = make_extruded_side(doc, "Side_Right", TOTAL_WIDTH - T)

    # Base platform (between side panels, behind front panel, in front of back panel)
    base = make_box(INTERNAL_WIDTH, INTERNAL_DEPTH, T, v(T, T, 0.0))
    base_obj = make_feature(doc, "Base_Platform", base)

    # Front base panel (Y=0..18, Z=0..400)
    front_base = make_box(INTERNAL_WIDTH, FRONT_THICK_Y, FRONT_BASE_Z_TOP, v(T, 0.0, 0.0))
    front_base_obj = make_feature(doc, "Front_Panel_Base", front_base)

    # Control panel (plate rotated about hinge line at Y=0, Z=400)
    control = make_box(INTERNAL_WIDTH, CONTROL_DEPTH_Y, T, v(T, 0.0, CONTROL_Z))
    control = rotate_shape_about_x(control, hinge_y=0.0, hinge_z=CONTROL_Z, angle_deg=CONTROL_ANGLE_DEG)
    control_obj = make_feature(doc, "Control_Panel", control)

    # Front screen panel (Y=0..18, Z=500..1400)
    front_screen_base = v(T, 0.0, FRONT_SCREEN_Z0)
    front_screen = make_box(INTERNAL_WIDTH, FRONT_THICK_Y, FRONT_SCREEN_H, front_screen_base)

    # Cutouts
    front_screen = cut_rect_through_front_panel(front_screen, front_screen_base, MAIN_WIN_X, MAIN_WIN_Z, MAIN_WIN_W, MAIN_WIN_H)
    front_screen = cut_rect_through_front_panel(front_screen, front_screen_base, TICK_WIN_X, TICK_WIN_Z, TICK_WIN_W, TICK_WIN_H)

    front_screen_obj = make_feature(doc, "Front_Panel_Screen", front_screen)

    # Back panel (Y=482..500, Z=18..1650)
    back = make_box(INTERNAL_WIDTH, T, BACK_HEIGHT, v(T, BACK_Y0, BACK_Z0))
    back_obj = make_feature(doc, "Back_Panel", back)

    # Internal electronics shelf
    shelf = make_box(INTERNAL_WIDTH, SHELF_WY, T, v(T, SHELF_Y0, SHELF_Z0))
    shelf_obj = make_feature(doc, "Shelf_Electronics", shelf)

    # Optional: fill the upper front transition (derived from your profile V5→V6→V7)
    # V5: (Y=0, Z=1400) to V6: (Y=100, Z=1500) is a 45° slope
    # Then V6→V7 is vertical at Y=100 from Z=1500 to Z=1650
    if CLOSE_UPPER_FRONT:
        # Sloped panel: hinge at Y=0, Z=1400. We want it to land at Y=100, Z=1500.
        run_y = 100.0
        rise_z = 100.0
        angle = math.degrees(math.atan2(rise_z, run_y))  # 45
        # IMPORTANT: a board of width "run_y" rotated doesn't project to run_y.
        # If you want the rotated edge to be at +100mm in Y, you need pre-rotation length = run_y / cos(angle).
        pre_len = run_y / math.cos(math.radians(angle))

        upper_slope = make_box(INTERNAL_WIDTH, pre_len, T, v(T, 0.0, 1400.0))
        upper_slope = rotate_shape_about_x(upper_slope, hinge_y=0.0, hinge_z=1400.0, angle_deg=angle)
        upper_slope_obj = make_feature(doc, "Front_Upper_Slope", upper_slope)

        upper_vert_h = 1650.0 - 1500.0
        upper_vert = make_box(INTERNAL_WIDTH, T, upper_vert_h, v(T, 100.0, 1500.0))
        upper_vert_obj = make_feature(doc, "Front_Upper_Vert", upper_vert)

    # Optional: top closure derived from V7→V8→V9:
    # V7: (100,1650) to V8: (350,1750) is slope; V8→V9 is horizontal top back
    if CLOSE_TOP:
        # Sloped roof
        run_y = 350.0 - 100.0
        rise_z = 1750.0 - 1650.0
        angle = math.degrees(math.atan2(rise_z, run_y))   # ~21.8
        pre_len = run_y / math.cos(math.radians(angle))   # ensure projected Y span matches profile

        roof_slope = make_box(INTERNAL_WIDTH, pre_len, T, v(T, 100.0, 1650.0))
        roof_slope = rotate_shape_about_x(roof_slope, hinge_y=100.0, hinge_z=1650.0, angle_deg=angle)
        roof_slope_obj = make_feature(doc, "Top_Roof_Slope", roof_slope)

        # Flat back cap from Y=350..500 at top. Place it so its top surface is at Z=1750.
        roof_back = make_box(INTERNAL_WIDTH, 150.0, T, v(T, 350.0, 1750.0 - T))
        roof_back_obj = make_feature(doc, "Top_Roof_Back", roof_back)

    # -----------------------------
    # Sanity checks
    # -----------------------------
    solids = [
        ("Side_Left", side_left.Shape),
        ("Side_Right", side_right.Shape),
        ("Base_Platform", base_obj.Shape),
        ("Front_Panel_Base", front_base_obj.Shape),
        ("Control_Panel", control_obj.Shape),
        ("Front_Panel_Screen", front_screen_obj.Shape),
        ("Back_Panel", back_obj.Shape),
        ("Shelf_Electronics", shelf_obj.Shape),
    ]

    # Add optional pieces to checks if created
    for obj_name in ["Front_Upper_Slope", "Front_Upper_Vert", "Top_Roof_Slope", "Top_Roof_Back"]:
        o = doc.getObject(obj_name)
        if o:
            solids.append((obj_name, o.Shape))

    # Boundaries check (allow small slack because angled panels can project a bit)
    for nm, shp in solids:
        within_global_bounds(nm, shp, 0.0, TOTAL_WIDTH, 0.0, TOTAL_DEPTH, 0.0, TOTAL_HEIGHT, slack=5.0)

    # Basic fit checks for rectangular inner panels
    # Base must be inside X[T..TOTAL_WIDTH-T] and Y[T..TOTAL_DEPTH-T]
    bb_base = base_obj.Shape.BoundBox
    if bb_base.XMin < T - EPS or bb_base.XMax > (TOTAL_WIDTH - T) + EPS:
        die("Base_Platform not between side panels in X.")
    if bb_base.YMin < T - EPS or bb_base.YMax > (TOTAL_DEPTH - T) + EPS:
        die("Base_Platform not between front/back in Y.")

    # Cutout checks already done; we also check that cutouts didn't destroy the face completely
    if front_screen_obj.Shape.Volume <= EPS:
        die("Front_Panel_Screen volume is zero after cutouts. Something is very wrong.")

    return True


def export_outputs(doc):
    if SAVE_FCSTD:
        doc.saveAs(FCSTD_PATH)
        print(f"Saved: {FCSTD_PATH}")

    if EXPORT_STEP:
        try:
            import Import
            objs = [o for o in doc.Objects if hasattr(o, "Shape")]
            Import.export(objs, STEP_PATH)
            print(f"Exported STEP: {STEP_PATH}")
        except Exception as e:
            print("STEP export failed (this can happen in some FreeCAD setups).")
            print(str(e))


def main():
    doc = App.newDocument(DOC_NAME)
    ok = build(doc)
    doc.recompute()

    # Try to fit view if GUI is available (safe in headless)
    try:
        import FreeCADGui as Gui
        Gui.activeDocument().activeView().viewIsometric()
        Gui.SendMsgToActiveView("ViewFit")
    except Exception:
        pass

    export_outputs(doc)
    print("Done.")


if __name__ == "__main__":
    main()

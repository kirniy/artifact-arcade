"""
ARTIFACT Cabinet - FreeCAD Build Script
Run this in FreeCAD Python console or as a macro.
Based on CAD-SPEC.md v2
"""

import FreeCAD
import Part

# Create new document
doc = FreeCAD.newDocument("ARTIFACT_Cabinet")

# === CONSTANTS ===
W = 540   # Total width
D = 500   # Total depth
H = 1750  # Total height
T = 18    # Material thickness

# === SIDE PANELS (shaped profile with control panel notch) ===

# Profile points (Y=depth, Z=height) - NEW v2 profile
profile = [
    (0, 0),       # V0: Front-bottom
    (0, 400),     # V1: Top of base section
    (150, 400),   # V2: Control panel front support
    (150, 500),   # V3: Control panel back support
    (0, 500),     # V4: Bottom of screen section
    (0, 1400),    # V5: Top of screen section
    (100, 1500),  # V6: Screen angle transition
    (100, 1650),  # V7: Below marquee
    (350, 1750),  # V8: Back edge of marquee
    (500, 1750),  # V9: Back-top corner
    (500, 0),     # V10: Back-bottom corner
]

# Left side panel (X=0 to X=18)
left_vecs = [FreeCAD.Vector(0, y, z) for y, z in profile]
left_vecs.append(left_vecs[0])  # Close polygon
left_wire = Part.makePolygon(left_vecs)
left_face = Part.Face(left_wire)
left_solid = left_face.extrude(FreeCAD.Vector(T, 0, 0))
left_part = doc.addObject("Part::Feature", "Side_Left")
left_part.Shape = left_solid

# Right side panel (X=522 to X=540)
right_vecs = [FreeCAD.Vector(W - T, y, z) for y, z in profile]
right_vecs.append(right_vecs[0])
right_wire = Part.makePolygon(right_vecs)
right_face = Part.Face(right_wire)
right_solid = right_face.extrude(FreeCAD.Vector(T, 0, 0))
right_part = doc.addObject("Part::Feature", "Side_Right")
right_part.Shape = right_solid

# === SIMPLE BOX PANELS ===

# Base platform (floor level)
base = doc.addObject("Part::Box", "Base_Platform")
base.Length, base.Width, base.Height = 504, 464, T
base.Placement.Base = FreeCAD.Vector(T, T, 0)

# Front panel - base section (Z=0 to 400)
front_base = doc.addObject("Part::Box", "Front_Base")
front_base.Length, front_base.Width, front_base.Height = 504, T, 400
front_base.Placement.Base = FreeCAD.Vector(T, 0, 0)

# Front panel - screen section (Z=500 to 1400)
front_screen = doc.addObject("Part::Box", "Front_Screen")
front_screen.Length, front_screen.Width, front_screen.Height = 504, T, 900
front_screen.Placement.Base = FreeCAD.Vector(T, 0, 500)

# Control panel (angled, sits in notch)
control = doc.addObject("Part::Box", "Control_Panel")
control.Length, control.Width, control.Height = 504, 150, T
control.Placement.Base = FreeCAD.Vector(T, 0, 400)
control.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), -12)

# Back panel
back = doc.addObject("Part::Box", "Back_Panel")
back.Length, back.Width, back.Height = 504, T, 1632
back.Placement.Base = FreeCAD.Vector(T, D - T, T)

# Marquee (angled top)
marquee = doc.addObject("Part::Box", "Marquee")
marquee.Length, marquee.Width, marquee.Height = 504, 250, T
marquee.Placement.Base = FreeCAD.Vector(T, 100, 1650)
marquee.Placement.Rotation = FreeCAD.Rotation(FreeCAD.Vector(1, 0, 0), 20)

# Internal shelf (for electronics)
shelf = doc.addObject("Part::Box", "Shelf")
shelf.Length, shelf.Width, shelf.Height = 504, 400, T
shelf.Placement.Base = FreeCAD.Vector(T, 50, 150)

# === RECOMPUTE AND VIEW ===
doc.recompute()

# Set view (only works with GUI)
try:
    FreeCAD.Gui.activeDocument().activeView().viewIsometric()
    FreeCAD.Gui.SendMsgToActiveView("ViewFit")
except:
    pass

print("ARTIFACT Cabinet built successfully!")
print(f"Parts created: {len(doc.Objects)}")

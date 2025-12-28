#!/usr/bin/env python3
"""
ARTIFACT Cabinet Modification Script for FreeCAD - v2 FIXED

HOW TO USE:
1. Open FreeCAD
2. File → Import → select "arcade_cabinet.step"
3. View → Panels → Python Console
4. Copy this entire script into the Python console and press Enter
"""

import FreeCAD
import Part

# =============================================================================
# CONFIGURATION
# =============================================================================

TARGET_WIDTH = 540    # mm
TARGET_DEPTH = 500    # mm
TARGET_HEIGHT = 1750  # mm

# =============================================================================
# FIXED: Filter out reference geometry (planes, axes)
# =============================================================================

def is_real_part(obj):
    """Check if object is a real solid part, not reference geometry."""
    skip_names = ['axis', 'plane', 'origin', 'solid']
    name_lower = obj.Label.lower()

    # Skip reference geometry
    for skip in skip_names:
        if skip in name_lower and 'panel' not in name_lower:
            return False

    # Must have a valid Shape with finite bounds
    if not hasattr(obj, 'Shape'):
        return False

    try:
        bb = obj.Shape.BoundBox
        # Check for infinite or zero bounds
        if bb.XLength > 1e10 or bb.YLength > 1e10 or bb.ZLength > 1e10:
            return False
        if bb.XLength <= 0 and bb.YLength <= 0 and bb.ZLength <= 0:
            return False
        if obj.Shape.Volume <= 0:
            return False
        return True
    except:
        return False

def get_real_parts():
    """Get list of real solid parts only."""
    parts = []
    for obj in FreeCAD.ActiveDocument.Objects:
        if is_real_part(obj):
            parts.append(obj)
    return parts

def get_assembly_bounds(parts):
    """Get bounding box of real parts only."""
    min_x = min_y = min_z = float('inf')
    max_x = max_y = max_z = float('-inf')

    for obj in parts:
        bb = obj.Shape.BoundBox
        min_x = min(min_x, bb.XMin)
        min_y = min(min_y, bb.YMin)
        min_z = min(min_z, bb.ZMin)
        max_x = max(max_x, bb.XMax)
        max_y = max(max_y, bb.YMax)
        max_z = max(max_z, bb.ZMax)

    return {
        'min_x': min_x, 'max_x': max_x,
        'min_y': min_y, 'max_y': max_y,
        'min_z': min_z, 'max_z': max_z,
        'width': max_x - min_x,
        'depth': max_y - min_y,
        'height': max_z - min_z,
    }

# =============================================================================
# MAIN
# =============================================================================

def main():
    doc = FreeCAD.ActiveDocument
    if not doc:
        print("ERROR: No document open! Import the STEP file first.")
        return

    print("=" * 60)
    print("ARTIFACT Cabinet Modification Script v2")
    print("=" * 60)

    # Get real parts only
    print("\n[1/5] Finding real parts (filtering reference geometry)...")
    parts = get_real_parts()
    print(f"  Found {len(parts)} real parts:")
    for p in parts:
        bb = p.Shape.BoundBox
        print(f"    - {p.Label}: {bb.XLength:.0f} × {bb.YLength:.0f} × {bb.ZLength:.0f} mm")

    if not parts:
        print("ERROR: No valid parts found!")
        return

    # Get current bounds
    print("\n[2/5] Measuring current dimensions...")
    bounds = get_assembly_bounds(parts)
    print(f"  Current assembly:")
    print(f"    Width:  {bounds['width']:.1f} mm")
    print(f"    Depth:  {bounds['depth']:.1f} mm")
    print(f"    Height: {bounds['height']:.1f} mm")

    # Calculate scale
    print("\n[3/5] Calculating scale factors...")
    scale_x = TARGET_WIDTH / bounds['width']
    scale_y = TARGET_DEPTH / bounds['depth']
    scale_z = TARGET_HEIGHT / bounds['height']
    print(f"  Scale: X={scale_x:.4f}, Y={scale_y:.4f}, Z={scale_z:.4f}")

    # Ask for confirmation
    print(f"\n  Will scale to: {TARGET_WIDTH} × {TARGET_DEPTH} × {TARGET_HEIGHT} mm")

    # Scale parts
    print("\n[4/5] Scaling parts...")
    for obj in parts:
        try:
            mat = FreeCAD.Matrix()
            mat.scale(scale_x, scale_y, scale_z)
            obj.Shape = obj.Shape.transformGeometry(mat)
            print(f"  ✓ {obj.Label}")
        except Exception as e:
            print(f"  ✗ {obj.Label}: {e}")

    doc.recompute()

    # Verify
    print("\n[5/5] Verifying new dimensions...")
    new_bounds = get_assembly_bounds(parts)
    print(f"  New assembly:")
    print(f"    Width:  {new_bounds['width']:.1f} mm (target: {TARGET_WIDTH})")
    print(f"    Depth:  {new_bounds['depth']:.1f} mm (target: {TARGET_DEPTH})")
    print(f"    Height: {new_bounds['height']:.1f} mm (target: {TARGET_HEIGHT})")

    print("\n" + "=" * 60)
    print("✅ DONE! Save as: File → Save As → ARTIFACT_Cabinet.FCStd")
    print("=" * 60)

# Run
main()

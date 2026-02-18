# shear_wall/building_dataframe_simple.py
"""
Simple/Predefined Shear Wall Building Generator

This module is triggered when building_type='simple' (keyword: simple+basic/predefined).
It creates a fixed reference building with predetermined dimensions and wall layout.
All user-supplied dimensional parameters are IGNORED when this module is active.

Imported by autocad_2024_mcp_server.py:
    from shear_wall.building_dataframe_simple import recreate_in_autocad as create_simple_building
    from shear_wall.building_dataframe_simple import recreate_with_mcp_connection

Reference building specifications:
    - Footprint: 36m x 12m
    - Floors: 10
    - Floor height: 4.0m
    - Slab thickness: 0.20m
    - Wall thickness: 0.30m
    - Shear walls at fixed positions on perimeter and core
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Reference building fixed parameters
# ---------------------------------------------------------------------------
SIMPLE_BUILDING = {
    "floors": 10,
    "length": 36.0,
    "width": 12.0,
    "floor_height": 4.0,
    "slab_thickness": 0.20,
    "wall_thickness": 0.30,
    "wall_length": 2.0,
    # Fixed shear wall positions (x, y, orientation) relative to building origin
    # orientation: 'x' = wall runs along x-axis, 'y' = wall runs along y-axis
    "shear_walls": [
        # Front face walls
        {"x": 0.0, "y": 0.0, "orient": "x"},
        {"x": 8.0, "y": 0.0, "orient": "x"},
        {"x": 17.0, "y": 0.0, "orient": "x"},
        {"x": 26.0, "y": 0.0, "orient": "x"},
        {"x": 34.0, "y": 0.0, "orient": "x"},
        # Back face walls
        {"x": 0.0, "y": 11.70, "orient": "x"},
        {"x": 8.0, "y": 11.70, "orient": "x"},
        {"x": 17.0, "y": 11.70, "orient": "x"},
        {"x": 26.0, "y": 11.70, "orient": "x"},
        {"x": 34.0, "y": 11.70, "orient": "x"},
        # Left face walls
        {"x": 0.0, "y": 0.0, "orient": "y"},
        {"x": 0.0, "y": 5.0, "orient": "y"},
        {"x": 0.0, "y": 10.0, "orient": "y"},
        # Right face walls
        {"x": 35.70, "y": 0.0, "orient": "y"},
        {"x": 35.70, "y": 5.0, "orient": "y"},
        {"x": 35.70, "y": 10.0, "orient": "y"},
        # Core walls (elevator/stair core at center)
        {"x": 16.0, "y": 4.0, "orient": "x"},
        {"x": 16.0, "y": 7.70, "orient": "x"},
        {"x": 16.0, "y": 4.0, "orient": "y"},
        {"x": 19.70, "y": 4.0, "orient": "y"},
    ],
}


def _make_point(x, y, z):
    """Create a COM-compatible 3D point."""
    import win32com.client
    import pythoncom
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [x, y, z]
    )


def _add_3dface(ms, p1, p2, p3, p4):
    """Add a 3DFace from 4 coordinate tuples."""
    try:
        pt1 = _make_point(*p1)
        pt2 = _make_point(*p2)
        pt3 = _make_point(*p3)
        pt4 = _make_point(*p4)
        return ms.Add3DFace(pt1, pt2, pt3, pt4)
    except Exception as exc:
        logger.debug("3DFace failed: %s", exc)
        return None


def _add_wall_box(ms, x, y, z, wl, wt, wh, orient, layer=None):
    """
    Draw a shear wall as a thin 3D box (6 faces).
    orient='x': wall runs along x-axis (length=wl in x, thickness=wt in y)
    orient='y': wall runs along y-axis (thickness=wt in x, length=wl in y)
    """
    if orient == "x":
        lx, ly = wl, wt
    else:
        lx, ly = wt, wl

    count = 0
    faces_pts = [
        ((x, y, z), (x+lx, y, z), (x+lx, y+ly, z), (x, y+ly, z)),
        ((x, y, z+wh), (x+lx, y, z+wh), (x+lx, y+ly, z+wh), (x, y+ly, z+wh)),
        ((x, y, z), (x+lx, y, z), (x+lx, y, z+wh), (x, y, z+wh)),
        ((x, y+ly, z), (x+lx, y+ly, z), (x+lx, y+ly, z+wh), (x, y+ly, z+wh)),
        ((x, y, z), (x, y+ly, z), (x, y+ly, z+wh), (x, y, z+wh)),
        ((x+lx, y, z), (x+lx, y+ly, z), (x+lx, y+ly, z+wh), (x+lx, y, z+wh)),
    ]
    for pts in faces_pts:
        face = _add_3dface(ms, *pts)
        if face:
            count += 1
            if layer:
                try:
                    face.Layer = layer
                except Exception:
                    pass
    return count


def _add_slab(ms, x, y, z, lx, ly, thickness, layer=None):
    """Draw a floor slab as a thin box."""
    return _add_wall_box(ms, x, y, z, lx, thickness, ly, orient="x", layer=layer)


def _ensure_layer(doc, name, color=None):
    """Create layer if needed."""
    try:
        layers = doc.Layers
        try:
            lyr = layers.Item(name)
        except Exception:
            lyr = layers.Add(name)
        if color is not None:
            lyr.Color = color
    except Exception:
        pass


def recreate_in_autocad(autocad_controller):
    """
    Recreate the simple reference building in AutoCAD.
    Uses autocad_controller.model_space and autocad_controller.doc.

    Returns:
        str: Summary of building created
    """
    b = SIMPLE_BUILDING
    ms = autocad_controller.model_space
    doc = autocad_controller.doc
    total = 0

    _ensure_layer(doc, "S-SLAB", 4)
    _ensure_layer(doc, "S-WALL", 1)

    for floor_idx in range(b["floors"]):
        z_base = floor_idx * b["floor_height"]

        # Floor slab
        slab_pts = [
            (0, 0, z_base),
            (b["length"], 0, z_base),
            (b["length"], b["width"], z_base),
            (0, b["width"], z_base),
        ]
        face = _add_3dface(ms, *slab_pts)
        if face:
            try:
                face.Layer = "S-SLAB"
            except Exception:
                pass
            total += 1

        # Bottom slab (thin)
        slab_top_z = z_base + b["slab_thickness"]

        slab_top_pts = [
            (0, 0, slab_top_z),
            (b["length"], 0, slab_top_z),
            (b["length"], b["width"], slab_top_z),
            (0, b["width"], slab_top_z),
        ]
        face = _add_3dface(ms, *slab_top_pts)
        if face:
            try:
                face.Layer = "S-SLAB"
            except Exception:
                pass
            total += 1

        # Shear walls for this floor
        wall_z = z_base + b["slab_thickness"]
        wall_h = b["floor_height"] - b["slab_thickness"]

        for wall_def in b["shear_walls"]:
            n = _add_wall_box(
                ms,
                wall_def["x"], wall_def["y"], wall_z,
                b["wall_length"], b["wall_thickness"], wall_h,
                wall_def["orient"],
                layer="S-WALL"
            )
            total += n

    # Top roof slab
    z_top = b["floors"] * b["floor_height"]
    face = _add_3dface(ms,
                       (0, 0, z_top),
                       (b["length"], 0, z_top),
                       (b["length"], b["width"], z_top),
                       (0, b["width"], z_top))
    if face:
        try:
            face.Layer = "S-SLAB"
        except Exception:
            pass
        total += 1

    # Set 3D view
    try:
        doc.SendCommand("-VIEW _swiso\n")
    except Exception:
        pass

    return (
        "[OK] Simple Reference Building Created\n"
        "  Type: Predefined shear wall building\n"
        "  Footprint: %.0fm x %.0fm\n"
        "  Floors: %d | Floor height: %.1fm\n"
        "  Total height: %.0fm\n"
        "  Shear walls: %d per floor | Wall thickness: %.2fm\n"
        "  Slab thickness: %.2fm\n"
        "  Total entities: %d\n"
        "  Layers: S-SLAB, S-WALL" % (
            b["length"], b["width"],
            b["floors"], b["floor_height"],
            b["floors"] * b["floor_height"],
            len(b["shear_walls"]), b["wall_thickness"],
            b["slab_thickness"],
            total
        )
    )


def recreate_with_mcp_connection(autocad_controller):
    """
    Wrapper for MCP tool handler - calls recreate_in_autocad.
    This is the function called when building_type='simple' in the server.
    """
    return recreate_in_autocad(autocad_controller)

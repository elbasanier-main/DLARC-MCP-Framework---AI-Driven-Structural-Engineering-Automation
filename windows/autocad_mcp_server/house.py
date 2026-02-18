# house.py
"""
Complete House Generator Module for AutoCAD MCP Server
Creates parametric residential buildings with walls, slabs, roof, rooms,
garage, pool, landscaping, furniture, MEP systems via COM automation.

Imported by autocad_2024_mcp_server.py:
    from house import create_complete_house

Parameters handled (all 14 from create_house tool):
    floors, length, width, style, bedrooms, bathrooms,
    include_garage, include_pool, include_landscaping,
    include_furniture, include_mep, include_basement,
    has_office, open_plan
"""

import math
import logging
import json
from datetime import datetime
from typing import Dict, Any, List, Tuple, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Style configurations - dimensions in meters
# ---------------------------------------------------------------------------
STYLE_CONFIG = {
    "modern": {
        "wall_height": 3.2,
        "parapet_height": 0.9,
        "roof_type": "flat",
        "roof_overhang": 0.6,
        "window_ratio": 0.35,
        "wall_thickness": 0.25,
        "slab_thickness": 0.20,
        "partition_thickness": 0.12,
        "garage_height": 3.0,
    },
    "traditional": {
        "wall_height": 3.0,
        "parapet_height": 0.0,
        "roof_type": "gable",
        "roof_overhang": 0.8,
        "window_ratio": 0.25,
        "wall_thickness": 0.30,
        "slab_thickness": 0.20,
        "partition_thickness": 0.15,
        "garage_height": 2.8,
    },
    "minimalist": {
        "wall_height": 3.0,
        "parapet_height": 0.6,
        "roof_type": "flat",
        "roof_overhang": 0.3,
        "window_ratio": 0.40,
        "wall_thickness": 0.20,
        "slab_thickness": 0.18,
        "partition_thickness": 0.10,
        "garage_height": 2.8,
    },
    "luxury": {
        "wall_height": 3.5,
        "parapet_height": 1.0,
        "roof_type": "hip",
        "roof_overhang": 1.0,
        "window_ratio": 0.40,
        "wall_thickness": 0.30,
        "slab_thickness": 0.25,
        "partition_thickness": 0.15,
        "garage_height": 3.2,
    },
    "compact": {
        "wall_height": 2.8,
        "parapet_height": 0.0,
        "roof_type": "gable",
        "roof_overhang": 0.5,
        "window_ratio": 0.20,
        "wall_thickness": 0.20,
        "slab_thickness": 0.15,
        "partition_thickness": 0.10,
        "garage_height": 2.6,
    },
}


# ---------------------------------------------------------------------------
# Low-level AutoCAD COM geometry helpers
# ---------------------------------------------------------------------------
def _make_point(x, y, z):
    """Create a COM-compatible 3D point array."""
    import win32com.client
    import pythoncom
    return win32com.client.VARIANT(
        pythoncom.VT_ARRAY | pythoncom.VT_R8,
        [x, y, z]
    )


def _add_3dface(model_space, p1, p2, p3, p4):
    """Add a 3DFace to AutoCAD model space from 4 coordinate tuples."""
    try:
        pt1 = _make_point(*p1)
        pt2 = _make_point(*p2)
        pt3 = _make_point(*p3)
        pt4 = _make_point(*p4)
        return model_space.Add3DFace(pt1, pt2, pt3, pt4)
    except Exception as exc:
        logger.debug("_add_3dface failed: %s", exc)
        return None


def _add_line(model_space, start, end):
    """Add a Line entity between two 3D points."""
    try:
        sp = _make_point(*start)
        ep = _make_point(*end)
        return model_space.AddLine(sp, ep)
    except Exception as exc:
        logger.debug("_add_line failed: %s", exc)
        return None


def _add_box_faces(ms, corner, lx, ly, lz, layer=None):
    """
    Draw a rectangular box as 6 x 3DFace entities.
    corner = (x, y, z), lx/ly/lz = dimensions along each axis.
    Returns count of entities created.
    """
    x, y, z = corner
    count = 0

    faces_pts = [
        # bottom
        ((x, y, z), (x+lx, y, z), (x+lx, y+ly, z), (x, y+ly, z)),
        # top
        ((x, y, z+lz), (x+lx, y, z+lz), (x+lx, y+ly, z+lz), (x, y+ly, z+lz)),
        # front (y=y)
        ((x, y, z), (x+lx, y, z), (x+lx, y, z+lz), (x, y, z+lz)),
        # back (y=y+ly)
        ((x, y+ly, z), (x+lx, y+ly, z), (x+lx, y+ly, z+lz), (x, y+ly, z+lz)),
        # left (x=x)
        ((x, y, z), (x, y+ly, z), (x, y+ly, z+lz), (x, y, z+lz)),
        # right (x=x+lx)
        ((x+lx, y, z), (x+lx, y+ly, z), (x+lx, y+ly, z+lz), (x+lx, y, z+lz)),
    ]

    for pts in faces_pts:
        face = _add_3dface(ms, *pts)
        if face is not None:
            count += 1
            if layer:
                try:
                    face.Layer = layer
                except Exception:
                    pass
    return count


def _add_slab(ms, x, y, z, lx, ly, thickness, layer=None):
    """Draw a horizontal slab (thin box)."""
    return _add_box_faces(ms, (x, y, z), lx, ly, thickness, layer=layer)


def _ensure_layer(doc, layer_name, color_index=None):
    """Create layer if it does not exist; optionally set color."""
    try:
        layers = doc.Layers
        try:
            lyr = layers.Item(layer_name)
        except Exception:
            lyr = layers.Add(layer_name)
        if color_index is not None:
            lyr.Color = color_index
        return lyr
    except Exception as exc:
        logger.warning("Could not create layer %s: %s", layer_name, exc)
        return None


# ---------------------------------------------------------------------------
# Room layout generator
# ---------------------------------------------------------------------------
def _generate_room_layout(length, width, bedrooms, bathrooms, has_office,
                          open_plan, style_cfg):
    """
    Return a list of room dicts for one floor:
        {"name": str, "x": float, "y": float, "w": float, "h": float}
    Coordinates relative to (0, 0) ground-floor interior origin.
    """
    rooms = []
    wt = style_cfg["wall_thickness"]

    # usable interior
    ix = wt
    iy = wt
    iw = length - 2 * wt
    ih = width - 2 * wt

    if open_plan:
        # single open living/kitchen/dining zone at the front
        rooms.append({
            "name": "Living / Kitchen / Dining",
            "x": ix, "y": iy, "w": iw, "h": ih * 0.55,
        })
    else:
        half = iw / 2.0
        rooms.append({
            "name": "Living Room",
            "x": ix, "y": iy, "w": half, "h": ih * 0.55,
        })
        rooms.append({
            "name": "Kitchen / Dining",
            "x": ix + half, "y": iy, "w": half, "h": ih * 0.55,
        })

    # back zone -- bedrooms, bathrooms, office
    back_y = iy + ih * 0.55
    back_h = ih * 0.45
    n_back = bedrooms + bathrooms + (1 if has_office else 0)
    if n_back == 0:
        n_back = 1
    slot_w = iw / n_back
    cx = ix

    for i in range(bedrooms):
        rooms.append({
            "name": "Bedroom %d" % (i + 1),
            "x": cx, "y": back_y, "w": slot_w, "h": back_h,
        })
        cx += slot_w

    for i in range(bathrooms):
        rooms.append({
            "name": "Bathroom %d" % (i + 1),
            "x": cx, "y": back_y, "w": slot_w, "h": back_h,
        })
        cx += slot_w

    if has_office:
        rooms.append({
            "name": "Home Office",
            "x": cx, "y": back_y, "w": slot_w, "h": back_h,
        })

    return rooms


# ---------------------------------------------------------------------------
# Drawing sub-systems
# ---------------------------------------------------------------------------
def _draw_foundation_and_basement(ms, doc, length, width, style_cfg):
    """Draw basement level below grade if requested."""
    _ensure_layer(doc, "H-BASEMENT", 8)
    wt = style_cfg["wall_thickness"]
    wh = style_cfg["wall_height"]
    st = style_cfg["slab_thickness"]
    count = 0

    z_base = -wh  # basement is one floor below grade

    # basement floor slab
    count += _add_slab(ms, 0, 0, z_base, length, width, st, layer="H-BASEMENT")

    # basement walls (4 sides)
    z_wall = z_base + st
    h_wall = wh - st
    # front
    count += _add_box_faces(ms, (0, 0, z_wall), length, wt, h_wall, layer="H-BASEMENT")
    # back
    count += _add_box_faces(ms, (0, width - wt, z_wall), length, wt, h_wall, layer="H-BASEMENT")
    # left
    count += _add_box_faces(ms, (0, wt, z_wall), wt, width - 2*wt, h_wall, layer="H-BASEMENT")
    # right
    count += _add_box_faces(ms, (length - wt, wt, z_wall), wt, width - 2*wt, h_wall, layer="H-BASEMENT")

    return count


def _draw_walls_and_slabs(ms, doc, length, width, floors, style_cfg):
    """Draw exterior walls and floor slabs for every storey."""
    _ensure_layer(doc, "H-SLAB", 4)
    _ensure_layer(doc, "H-WALL", 1)
    wt = style_cfg["wall_thickness"]
    wh = style_cfg["wall_height"]
    st = style_cfg["slab_thickness"]
    count = 0

    for f in range(floors):
        z = f * wh

        # floor slab
        count += _add_slab(ms, 0, 0, z, length, width, st, layer="H-SLAB")

        # exterior walls (4 sides, each a thin box)
        z_wall = z + st
        h_wall = wh - st
        # front
        count += _add_box_faces(ms, (0, 0, z_wall), length, wt, h_wall, layer="H-WALL")
        # back
        count += _add_box_faces(ms, (0, width - wt, z_wall), length, wt, h_wall, layer="H-WALL")
        # left
        count += _add_box_faces(ms, (0, wt, z_wall), wt, width - 2*wt, h_wall, layer="H-WALL")
        # right
        count += _add_box_faces(ms, (length - wt, wt, z_wall), wt, width - 2*wt, h_wall, layer="H-WALL")

    # top slab / roof slab
    z_top = floors * wh
    count += _add_slab(ms, 0, 0, z_top, length, width, st, layer="H-SLAB")

    return count


def _draw_roof(ms, doc, length, width, floors, style_cfg):
    """Draw roof geometry based on style (flat/gable/hip)."""
    _ensure_layer(doc, "H-ROOF", 3)
    wh = style_cfg["wall_height"]
    overhang = style_cfg["roof_overhang"]
    st = style_cfg["slab_thickness"]
    z_top = floors * wh + st
    count = 0

    roof_type = style_cfg["roof_type"]

    if roof_type == "flat":
        ph = style_cfg["parapet_height"]
        if ph > 0:
            pw = 0.15  # parapet wall thickness
            # front parapet
            count += _add_box_faces(ms, (-overhang, -overhang, z_top),
                                    length + 2*overhang, pw, ph, layer="H-ROOF")
            # back parapet
            count += _add_box_faces(ms, (-overhang, width + overhang - pw, z_top),
                                    length + 2*overhang, pw, ph, layer="H-ROOF")
            # left parapet
            count += _add_box_faces(ms, (-overhang, -overhang + pw, z_top),
                                    pw, width + 2*overhang - 2*pw, ph, layer="H-ROOF")
            # right parapet
            count += _add_box_faces(ms, (length + overhang - pw, -overhang + pw, z_top),
                                    pw, width + 2*overhang - 2*pw, ph, layer="H-ROOF")

    elif roof_type in ("gable", "hip"):
        ridge_h = min(length, width) * 0.25
        mid_y = width / 2.0

        # two sloping faces
        face = _add_3dface(ms,
                           (-overhang, -overhang, z_top),
                           (length + overhang, -overhang, z_top),
                           (length + overhang, mid_y, z_top + ridge_h),
                           (-overhang, mid_y, z_top + ridge_h))
        if face:
            try:
                face.Layer = "H-ROOF"
            except Exception:
                pass
            count += 1

        face = _add_3dface(ms,
                           (-overhang, width + overhang, z_top),
                           (length + overhang, width + overhang, z_top),
                           (length + overhang, mid_y, z_top + ridge_h),
                           (-overhang, mid_y, z_top + ridge_h))
        if face:
            try:
                face.Layer = "H-ROOF"
            except Exception:
                pass
            count += 1

        if roof_type == "gable":
            # triangular end walls
            face = _add_3dface(ms,
                               (-overhang, -overhang, z_top),
                               (-overhang, width + overhang, z_top),
                               (-overhang, mid_y, z_top + ridge_h),
                               (-overhang, mid_y, z_top + ridge_h))
            if face:
                try:
                    face.Layer = "H-ROOF"
                except Exception:
                    pass
                count += 1

            face = _add_3dface(ms,
                               (length + overhang, -overhang, z_top),
                               (length + overhang, width + overhang, z_top),
                               (length + overhang, mid_y, z_top + ridge_h),
                               (length + overhang, mid_y, z_top + ridge_h))
            if face:
                try:
                    face.Layer = "H-ROOF"
                except Exception:
                    pass
                count += 1

        elif roof_type == "hip":
            # hip triangles at each end
            mid_x_start = 0.0
            mid_x_end = length
            face = _add_3dface(ms,
                               (-overhang, -overhang, z_top),
                               (-overhang, width + overhang, z_top),
                               (mid_x_start, mid_y, z_top + ridge_h),
                               (mid_x_start, mid_y, z_top + ridge_h))
            if face:
                try:
                    face.Layer = "H-ROOF"
                except Exception:
                    pass
                count += 1

            face = _add_3dface(ms,
                               (length + overhang, -overhang, z_top),
                               (length + overhang, width + overhang, z_top),
                               (mid_x_end, mid_y, z_top + ridge_h),
                               (mid_x_end, mid_y, z_top + ridge_h))
            if face:
                try:
                    face.Layer = "H-ROOF"
                except Exception:
                    pass
                count += 1

    return count


def _draw_room_partitions(ms, doc, rooms, z_base, style_cfg):
    """Draw interior partition walls on layer H-PARTITION."""
    _ensure_layer(doc, "H-PARTITION", 5)
    pt = style_cfg["partition_thickness"]
    wh = style_cfg["wall_height"]
    st = style_cfg["slab_thickness"]
    h = wh - st
    z = z_base + st
    count = 0

    for room in rooms:
        rx, ry, rw, rh = room["x"], room["y"], room["w"], room["h"]
        # bottom edge
        count += _add_box_faces(ms, (rx, ry, z), rw, pt, h, layer="H-PARTITION")
        # top edge
        count += _add_box_faces(ms, (rx, ry + rh - pt, z), rw, pt, h, layer="H-PARTITION")
        # left edge
        count += _add_box_faces(ms, (rx, ry, z), pt, rh, h, layer="H-PARTITION")
        # right edge
        count += _add_box_faces(ms, (rx + rw - pt, ry, z), pt, rh, h, layer="H-PARTITION")

    return count


def _draw_garage(ms, doc, length, width, style_cfg):
    """Draw attached garage structure on right side of house."""
    _ensure_layer(doc, "H-GARAGE", 30)
    wt = style_cfg["wall_thickness"]
    gh = style_cfg["garage_height"]
    st = style_cfg["slab_thickness"]
    garage_l = 6.0
    garage_w = 3.5
    count = 0

    # position: attached to the right side
    gx = length
    gy = 0
    gz = 0

    # garage floor slab
    count += _add_slab(ms, gx, gy, gz, garage_l, garage_w, st, layer="H-GARAGE")
    # garage walls (3 sides, front open for door)
    z_wall = gz + st
    h_wall = gh - st
    # back wall
    count += _add_box_faces(ms, (gx, gy + garage_w - wt, z_wall),
                            garage_l, wt, h_wall, layer="H-GARAGE")
    # left wall (shared with house)
    count += _add_box_faces(ms, (gx, gy, z_wall),
                            wt, garage_w, h_wall, layer="H-GARAGE")
    # right wall
    count += _add_box_faces(ms, (gx + garage_l - wt, gy, z_wall),
                            wt, garage_w, h_wall, layer="H-GARAGE")
    # roof slab
    count += _add_slab(ms, gx, gy, gh, garage_l, garage_w, st, layer="H-GARAGE")

    return count


def _draw_pool(ms, doc, length, width, style_cfg):
    """Draw a rectangular swimming pool behind the house."""
    _ensure_layer(doc, "H-POOL", 150)
    pool_l = min(8.0, length * 0.6)
    pool_w = 4.0
    pool_d = 1.5
    count = 0

    # position: centered behind the house, 2m gap
    px = (length - pool_l) / 2.0
    py = width + 2.0

    # pool basin (sunken box)
    count += _add_box_faces(ms, (px, py, -pool_d), pool_l, pool_w, pool_d, layer="H-POOL")
    # pool deck (thin slab around pool)
    deck_w = 1.0
    count += _add_slab(ms, px - deck_w, py - deck_w, 0,
                       pool_l + 2*deck_w, pool_w + 2*deck_w, 0.10, layer="H-POOL")

    return count


def _draw_landscaping(ms, doc, length, width, style_cfg):
    """Draw basic landscaping elements (perimeter path, garden markers)."""
    _ensure_layer(doc, "H-LANDSCAPE", 80)
    count = 0
    path_w = 1.2

    # perimeter walkway (thin slab)
    count += _add_slab(ms, -path_w, -path_w, -0.05,
                       length + 2*path_w, width + 2*path_w, 0.05,
                       layer="H-LANDSCAPE")

    # front garden bed markers (lines)
    for i in range(4):
        cx = length * (i + 1) / 5.0
        line = _add_line(ms, (cx - 0.5, -path_w - 1.5, 0),
                         (cx + 0.5, -path_w - 1.5, 0))
        if line:
            try:
                line.Layer = "H-LANDSCAPE"
            except Exception:
                pass
            count += 1

    # side garden beds
    for i in range(3):
        cy = width * (i + 1) / 4.0
        line = _add_line(ms, (-path_w - 1.5, cy - 0.5, 0),
                         (-path_w - 1.5, cy + 0.5, 0))
        if line:
            try:
                line.Layer = "H-LANDSCAPE"
            except Exception:
                pass
            count += 1

    return count


def _draw_furniture(ms, doc, rooms, z_base, style_cfg):
    """Place simplified furniture blocks in each room."""
    _ensure_layer(doc, "H-FURNITURE", 40)
    st = style_cfg["slab_thickness"]
    z = z_base + st
    count = 0

    for room in rooms:
        rx, ry, rw, rh = room["x"], room["y"], room["w"], room["h"]
        name = room["name"].lower()
        cx = rx + rw * 0.5
        cy = ry + rh * 0.5

        if "bedroom" in name:
            # bed block (1.4 x 2.0 x 0.5)
            bw, bl, bh = 1.4, 2.0, 0.5
            count += _add_box_faces(ms, (cx - bw/2, cy - bl/2, z),
                                    bw, bl, bh, layer="H-FURNITURE")
            # nightstand (0.4 x 0.4 x 0.5)
            count += _add_box_faces(ms, (cx - bw/2 - 0.5, cy - 0.2, z),
                                    0.4, 0.4, 0.5, layer="H-FURNITURE")

        elif "bathroom" in name:
            # bathtub/shower (0.8 x 1.6 x 0.5)
            count += _add_box_faces(ms, (rx + 0.3, ry + 0.3, z),
                                    0.8, 1.6, 0.5, layer="H-FURNITURE")
            # sink (0.5 x 0.4 x 0.8)
            count += _add_box_faces(ms, (rx + rw - 1.0, ry + 0.3, z),
                                    0.5, 0.4, 0.8, layer="H-FURNITURE")

        elif "kitchen" in name or "dining" in name:
            # kitchen counter (2.0 x 0.6 x 0.9)
            count += _add_box_faces(ms, (rx + 0.3, ry + 0.3, z),
                                    2.0, 0.6, 0.9, layer="H-FURNITURE")
            # dining table (1.4 x 0.9 x 0.75)
            count += _add_box_faces(ms, (cx - 0.7, cy, z),
                                    1.4, 0.9, 0.75, layer="H-FURNITURE")

        elif "living" in name:
            # sofa (2.0 x 0.9 x 0.8)
            count += _add_box_faces(ms, (cx - 1.0, cy - 0.45, z),
                                    2.0, 0.9, 0.8, layer="H-FURNITURE")
            # coffee table (1.0 x 0.6 x 0.4)
            count += _add_box_faces(ms, (cx - 0.5, cy + 0.6, z),
                                    1.0, 0.6, 0.4, layer="H-FURNITURE")

        elif "office" in name:
            # desk (1.4 x 0.7 x 0.75)
            count += _add_box_faces(ms, (cx - 0.7, cy - 0.35, z),
                                    1.4, 0.7, 0.75, layer="H-FURNITURE")
            # bookshelf (0.8 x 0.35 x 1.8)
            count += _add_box_faces(ms, (rx + 0.3, ry + rh - 0.65, z),
                                    0.8, 0.35, 1.8, layer="H-FURNITURE")

    return count


def _draw_mep_systems(ms, doc, length, width, floors, style_cfg):
    """Draw simplified MEP system indicators (HVAC ducts, plumbing risers, electrical panels)."""
    _ensure_layer(doc, "H-HVAC", 140)
    _ensure_layer(doc, "H-PLUMBING", 130)
    _ensure_layer(doc, "H-ELECTRICAL", 10)
    wh = style_cfg["wall_height"]
    st = style_cfg["slab_thickness"]
    count = 0

    for f in range(floors):
        z = f * wh + st

        # HVAC main duct running along center (line representation)
        duct_z = z + wh * 0.85
        line = _add_line(ms, (0.5, width / 2.0, duct_z),
                         (length - 0.5, width / 2.0, duct_z))
        if line:
            try:
                line.Layer = "H-HVAC"
            except Exception:
                pass
            count += 1

        # HVAC branch ducts
        for i in range(3):
            bx = length * (i + 1) / 4.0
            line = _add_line(ms, (bx, width * 0.25, duct_z),
                             (bx, width * 0.75, duct_z))
            if line:
                try:
                    line.Layer = "H-HVAC"
                except Exception:
                    pass
                count += 1

        # Plumbing risers (vertical lines at bathroom locations)
        # Place at back-right quadrant typical bathroom location
        riser_x = length * 0.75
        riser_y = width * 0.80
        line = _add_line(ms, (riser_x, riser_y, z),
                         (riser_x, riser_y, z + wh - st))
        if line:
            try:
                line.Layer = "H-PLUMBING"
            except Exception:
                pass
            count += 1

        # Hot water riser
        line = _add_line(ms, (riser_x + 0.15, riser_y, z),
                         (riser_x + 0.15, riser_y, z + wh - st))
        if line:
            try:
                line.Layer = "H-PLUMBING"
            except Exception:
                pass
            count += 1

        # Electrical panel (small box on ground floor only)
        if f == 0:
            count += _add_box_faces(ms, (0.3, 0.3, z + 1.2),
                                    0.4, 0.15, 0.6, layer="H-ELECTRICAL")

        # Electrical conduit runs (lines along walls)
        conduit_z = z + wh * 0.90
        line = _add_line(ms, (0.3, 0.3, conduit_z),
                         (length - 0.3, 0.3, conduit_z))
        if line:
            try:
                line.Layer = "H-ELECTRICAL"
            except Exception:
                pass
            count += 1

    return count


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
def create_complete_house(autocad_controller, arguments: Dict[str, Any]) -> str:
    """
    Create a complete house in AutoCAD.

    Parameters (from arguments dict - all 14 from create_house tool):
        floors            - Number of floors (1-3), default 2
        length            - House length in meters, default 12
        width             - House width in meters, default 10
        style             - House style (modern/traditional/minimalist/luxury/compact)
        bedrooms          - Number of bedrooms, default 3
        bathrooms         - Number of bathrooms, default 2
        include_garage    - Include attached garage, default True
        include_pool      - Include swimming pool, default False
        include_landscaping - Include landscaping, default True
        include_furniture - Include furniture, default True
        include_mep       - Include HVAC/electrical/plumbing, default True
        include_basement  - Include basement, default False
        has_office        - Include home office, default False
        open_plan         - Open plan living area, default True

    Returns:
        str: Summary of created house
    """
    # Extract all 14 parameters
    floors = arguments.get("floors", 2)
    length = float(arguments.get("length", 12.0))
    width = float(arguments.get("width", 10.0))
    style = arguments.get("style", "modern")
    bedrooms = arguments.get("bedrooms", 3)
    bathrooms = arguments.get("bathrooms", 2)
    include_garage = arguments.get("include_garage", True)
    include_pool = arguments.get("include_pool", False)
    include_landscaping = arguments.get("include_landscaping", True)
    include_furniture = arguments.get("include_furniture", True)
    include_mep = arguments.get("include_mep", True)
    include_basement = arguments.get("include_basement", False)
    has_office = arguments.get("has_office", False)
    open_plan = arguments.get("open_plan", True)

    # Clamp floors
    floors = max(1, min(3, floors))

    # Get style config
    style_cfg = STYLE_CONFIG.get(style, STYLE_CONFIG["modern"])

    # Access AutoCAD COM objects
    ms = autocad_controller.model_space
    doc = autocad_controller.doc

    total_entities = 0
    layers_created = []
    components_built = []

    # --- 1. Basement ---
    if include_basement:
        n = _draw_foundation_and_basement(ms, doc, length, width, style_cfg)
        total_entities += n
        layers_created.append("H-BASEMENT")
        components_built.append("Basement (1 level below grade)")

    # --- 2. Walls and Slabs ---
    n = _draw_walls_and_slabs(ms, doc, length, width, floors, style_cfg)
    total_entities += n
    layers_created.extend(["H-WALL", "H-SLAB"])
    components_built.append("Exterior walls + floor slabs (%d floors)" % floors)

    # --- 3. Roof ---
    n = _draw_roof(ms, doc, length, width, floors, style_cfg)
    total_entities += n
    layers_created.append("H-ROOF")
    components_built.append("Roof (%s)" % style_cfg["roof_type"])

    # --- 4. Room partitions ---
    for f in range(floors):
        z_base = f * style_cfg["wall_height"]
        rooms = _generate_room_layout(length, width, bedrooms, bathrooms,
                                      has_office, open_plan, style_cfg)
        n = _draw_room_partitions(ms, doc, rooms, z_base, style_cfg)
        total_entities += n

        # --- 5. Furniture ---
        if include_furniture:
            n = _draw_furniture(ms, doc, rooms, z_base, style_cfg)
            total_entities += n

    layers_created.append("H-PARTITION")
    room_names = [r["name"] for r in rooms]
    components_built.append("Interior rooms: %s" % ", ".join(room_names))

    if include_furniture:
        layers_created.append("H-FURNITURE")
        components_built.append("Furniture (all rooms)")

    # --- 6. Garage ---
    if include_garage:
        n = _draw_garage(ms, doc, length, width, style_cfg)
        total_entities += n
        layers_created.append("H-GARAGE")
        components_built.append("Attached garage (6.0m x 3.5m)")

    # --- 7. Pool ---
    if include_pool:
        n = _draw_pool(ms, doc, length, width, style_cfg)
        total_entities += n
        layers_created.append("H-POOL")
        components_built.append("Swimming pool (%.1fm x 4.0m)" % min(8.0, length * 0.6))

    # --- 8. Landscaping ---
    if include_landscaping:
        n = _draw_landscaping(ms, doc, length, width, style_cfg)
        total_entities += n
        layers_created.append("H-LANDSCAPE")
        components_built.append("Landscaping (walkway + garden beds)")

    # --- 9. MEP Systems ---
    if include_mep:
        n = _draw_mep_systems(ms, doc, length, width, floors, style_cfg)
        total_entities += n
        layers_created.extend(["H-HVAC", "H-PLUMBING", "H-ELECTRICAL"])
        components_built.append("MEP systems (HVAC ducts, plumbing risers, electrical)")

    # --- Set 3D view ---
    try:
        doc.SendCommand("-VIEW _swiso\n")
    except Exception:
        pass

    # --- Build summary ---
    total_height = floors * style_cfg["wall_height"]
    unique_layers = sorted(set(layers_created))

    summary_lines = [
        "[OK] House Created Successfully",
        "  Style: %s" % style,
        "  Size: %.1fm x %.1fm x %.1fm (L x W x H)" % (length, width, total_height),
        "  Floors: %d" % floors,
        "  Wall height: %.1fm | Wall thickness: %.2fm" % (
            style_cfg["wall_height"], style_cfg["wall_thickness"]),
        "  Slab thickness: %.2fm" % style_cfg["slab_thickness"],
        "  Roof type: %s (overhang: %.1fm)" % (
            style_cfg["roof_type"], style_cfg["roof_overhang"]),
        "  Bedrooms: %d | Bathrooms: %d" % (bedrooms, bathrooms),
        "  Open plan: %s | Home office: %s" % (
            "Yes" if open_plan else "No",
            "Yes" if has_office else "No"),
        "  Basement: %s" % ("Yes" if include_basement else "No"),
        "  Garage: %s | Pool: %s" % (
            "Yes" if include_garage else "No",
            "Yes" if include_pool else "No"),
        "  Landscaping: %s | Furniture: %s | MEP: %s" % (
            "Yes" if include_landscaping else "No",
            "Yes" if include_furniture else "No",
            "Yes" if include_mep else "No"),
        "  Total entities: %d" % total_entities,
        "  Layers: %s" % ", ".join(unique_layers),
        "  Components built:",
    ]
    for comp in components_built:
        summary_lines.append("    - %s" % comp)

    return "\n".join(summary_lines)

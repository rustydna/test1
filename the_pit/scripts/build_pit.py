"""Builds the complete Pit: Blender, one DAE per level, audit and land impact estimate.

Usage (from any folder):
    python the_pit/scripts/build_pit.py            # with the bpy module from PyPI
    blender -b --factory-startup --python the_pit/scripts/build_pit.py

Output in the_pit/output/.
"""

import json
import math
import os
import re
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402  (before bmesh with the PyPI module)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import pieces_v3 as P  # noqa: E402
from collada_static import write_dae  # noqa: E402
from geo import FACE_MATS, MATS, SMOOTH_ANGLE, UV_TILE, Geo  # noqa: E402
from mathutils import Matrix  # noqa: E402,F401

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "output")
LEVELS = ["HIGH", "MEDIUM", "LOW", "LOWEST"]
SUFFIX = {"HIGH": "", "MEDIUM": "_LOD2", "LOW": "_LOD1", "LOWEST": "_LOD0", "PHYS": "_PHYS"}
# "MESH | HIGH" is also looked up by render.py and qa_physics.py
COLL = {"HIGH": "MESH | HIGH", "MEDIUM": "LOD | MEDIUM", "LOW": "LOD | LOW", "LOWEST": "LOD | LOWEST",
        "PHYS": "PHYSICS"}
COLORS = {"Flame": (1.0, 0.45, 0.1), "Stone": (0.42, 0.40, 0.37), "Floor": (0.25, 0.22, 0.19),
          "Cloth": (0.38, 0.34, 0.28), "Bone": (0.72, 0.66, 0.55), "Water": (0.05, 0.09, 0.1),
          "Wood": (0.36, 0.24, 0.14), "Iron": (0.12, 0.12, 0.13), "Straw": (0.66, 0.55, 0.3),
          "Physics": (0.2, 0.6, 1.0)}
MARK = 0.004


# ------------------------------------------------------------------ helper geometry
def ensure_bounds(g, mn, mx, mat):
    """Adds two tiny triangles at the corners of the HIGH box if the level does not reach it.
    SL stretches every LOD and the physics to the HIGH box; this way they are not distorted."""
    if g.verts:
        # a level that sticks out of the HIGH box is clamped to it
        for v in g.verts:
            v.x = min(max(v.x, mn.x), mx.x)
            v.y = min(max(v.y, mn.y), mx.y)
            v.z = min(max(v.z, mn.z), mx.z)
        a, b = g.bounds()
        if (a - mn).length < 1e-5 and (b - mx).length < 1e-5:
            return False
    e = MARK
    g.face([mn, mn + Vector((e, 0, 0)), mn + Vector((0, e, 0))], mat, (0, 0, -1))
    g.face([mx, mx - Vector((e, 0, 0)), mx - Vector((0, e, 0))], mat, (0, 0, 1))
    return True


def _copy(g):
    c = Geo()
    c.verts = [v.copy() for v in g.verts]
    c.faces = list(g.faces)
    c.mats = list(g.mats)
    return c


def hull_geo(g, pts):
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    for f in bm.faces:
        if f.is_valid:
            g.face([v.co.copy() for v in f.verts], "Physics", f.normal.copy())
    bm.free()


def decimate(g, target):
    """Reduces a geometry to ~target triangles with Blender's Decimate (for automatic MEDIUM/LOW)."""
    if g.tri_count() <= target or not g.faces:
        return _copy(g)
    mats = sorted(set(g.mats), key=MATS.index)
    me = bpy.data.meshes.new("_dec")
    me.from_pydata([tuple(v) for v in g.verts], [], g.faces)
    for p, m in zip(me.polygons, g.mats):
        p.material_index = mats.index(m)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1.5e-4)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("_dec", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("d", "DECIMATE")
    mod.ratio = max(0.005, target / max(len(me.polygons), 1))
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    m2 = ev.to_mesh()
    out = Geo()
    out.verts = [v.co.copy() for v in m2.vertices]
    out.faces = [tuple(p.vertices) for p in m2.polygons]
    out.mats = [mats[min(p.material_index, len(mats) - 1)] for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return out


def phys_geo(boxes):
    g = Geo()
    for b in boxes:
        # "HULL" (convex hull) and "RAMP" (ramp) are the tags emitted by the phys() functions in
        # pieces / pieces_v3
        if b[0] == "HULL":
            hull_geo(g, b[1])
            continue
        if b[0] == "RAMP":
            _, mn, mx = b
            x0, y0, z0 = mn
            x1, y1, z1 = mx
            pts = [Vector(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1))]
            g.face(pts, "Physics", (0, -1, 1))
            g.face([Vector((x0, y1, z0)), Vector((x1, y1, z0)), Vector((x1, y1, z1)), Vector((x0, y1, z1))],
                   "Physics", (0, 1, 0))
            g.face([Vector((x0, y0, z0)), Vector((x0, y1, z0)), Vector((x0, y1, z1))], "Physics", (-1, 0, 0))
            g.face([Vector((x1, y0, z0)), Vector((x1, y1, z0)), Vector((x1, y1, z1))], "Physics", (1, 0, 0))
            g.face([Vector((x0, y0, z0)), Vector((x1, y0, z0)), Vector((x1, y1, z0)), Vector((x0, y1, z0))],
                   "Physics", (0, 0, -1))
        else:
            g.box(b[0], b[1], "Physics")
    return g


# ------------------------------------------------------------------ Blender
def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        c = COLORS.get(name, (0.5, 0.5, 0.5))
        m.diffuse_color = (*c, 1.0)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*c, 1.0)
            bsdf.inputs["Roughness"].default_value = {"Iron": 0.45, "Flame": 0.6}.get(name, 0.92)
            bsdf.inputs["Metallic"].default_value = 0.85 if name == "Iron" else 0.0
            if name == "Flame":
                bsdf.inputs["Emission Color"].default_value = (1.0, 0.42, 0.08, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 7.0
            if name == "Physics":
                bsdf.inputs["Alpha"].default_value = 0.35
    return m


def uv_for(co, n, mat):
    s = UV_TILE.get(mat, 1.0)
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 0:
        u, v = (co.y if n.x > 0 else -co.y), co.z
    elif ax == 1:
        u, v = (-co.x if n.y > 0 else co.x), co.z
    else:
        u, v = co.x, (co.y if n.z > 0 else -co.y)
    return u / s, v / s


def uv_flames(me, present, uvl):
    """0-1 UVs for the fire flipbook (face 7): cylindrical mapping per island.

    Each connected island of "Flame" polygons (one flame) gets
    u = angle around its vertical axis / 2π and v = relative height within the
    island, so that the whole flipbook frame covers the flame.
    """
    if "Flame" not in present:
        return
    im = present.index("Flame")
    polys = [p for p in me.polygons if p.material_index == im]
    parent = {}

    def find_root(a):
        while parent.setdefault(a, a) != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    for p in polys:
        vs = list(p.vertices)
        for v in vs[1:]:
            parent[find_root(v)] = find_root(vs[0])
    islands = {}
    for p in polys:
        islands.setdefault(find_root(p.vertices[0]), []).append(p)
    for ps in islands.values():
        vids = {v for p in ps for v in p.vertices}
        cos = [me.vertices[v].co for v in vids]
        cx = (min(c.x for c in cos) + max(c.x for c in cos)) / 2
        cy = (min(c.y for c in cos) + max(c.y for c in cos)) / 2
        z0 = min(c.z for c in cos)
        dz = max(max(c.z for c in cos) - z0, 1e-6)
        rmax = max(max(math.hypot(c.x - cx, c.y - cy) for c in cos), 1e-6)
        for p in ps:
            pc = p.center
            if abs(p.normal.z) > 0.7:      # base cap: planar, inside 0-1
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uvl.data[li].uv = (0.5 + 0.45 * (co.x - cx) / rmax, (co.z - z0) / dz)
                continue
            uvs = []
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                dx, dy = co.x - cx, co.y - cy
                if dx * dx + dy * dy < 1e-10:          # vertex on the axis: use the polygon's angle
                    dx, dy = pc.x - cx, pc.y - cy
                uvs.append([(math.atan2(dy, dx) / (2 * math.pi)) % 1.0, (co.z - z0) / dz])
            # seam: the polygon that crosses u=0/1 must not run across the whole
            # texture; it is pushed to the edge (transparent margin of the frame)
            # so it does not spill into the neighbouring flipbook frame
            us = [uv[0] for uv in uvs]
            if max(us) - min(us) > 0.5:
                for uv in uvs:
                    uv[0] = 1.0 if uv[0] < 0.5 else uv[0]
            for li, uv in zip(p.loop_indices, uvs):
                uvl.data[li].uv = uv


def mesh_object(name, g, origin, coll, level, sl_name, kind):
    me = bpy.data.meshes.new(name)
    verts = [v - origin for v in g.verts]
    me.from_pydata([tuple(v) for v in verts], [], g.faces)
    present = [m for m in MATS + ["Physics"] if m in set(g.mats)]
    for m in present:
        me.materials.append(material(m))
    idx = {m: i for i, m in enumerate(present)}
    for poly, m in zip(me.polygons, g.mats):
        poly.material_index = idx[m]
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1.5e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bm.to_mesh(me)
    bm.free()
    # sharp edges by angle depending on the material, and at material changes
    sharp = [False] * len(me.edges)
    edge_faces = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            edge_faces.setdefault(ek, []).append(p.index)
    ek_index = {e.key: e.index for e in me.edges}
    for ek, fl in edge_faces.items():
        i = ek_index[ek]
        if len(fl) != 2:
            sharp[i] = True
            continue
        a, b = me.polygons[fl[0]], me.polygons[fl[1]]
        ma, mb = present[a.material_index], present[b.material_index]
        if ma != mb:
            sharp[i] = True
            continue
        ang = math.degrees(a.normal.angle(b.normal, 0.0))
        sharp[i] = ang > SMOOTH_ANGLE.get(ma, 30)
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    attr.data.foreach_set("value", sharp)
    for p in me.polygons:
        p.use_smooth = True
    # box UVs in world coordinates (tileable textures, continuous across pieces)
    uvl = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        m = present[p.material_index]
        if m == "Flame":
            continue
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co + origin
            uvl.data[li].uv = uv_for(co, p.normal, m)
    uv_flames(me, present, uvl)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    ob["sl_name"] = sl_name
    ob["sl_level"] = level
    ob["sl_kind"] = kind
    coll.objects.link(ob)
    return ob


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


# ------------------------------------------------------------------ land impact (estimate)
def submesh_stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    cn = me.corner_normals
    uv = me.uv_layers[0].data if me.uv_layers else None
    verts = set()
    tris = 0
    for t in me.loop_triangles:
        tris += 1
        for li in t.loops:
            key = (t.material_index, me.loops[li].vertex_index, tuple(round(c, 3) for c in cn[li].vector),
                   tuple(round(c, 4) for c in uv[li].uv) if uv else ())
            verts.add(key)
    return tris, len(verts), len(me.materials)


def est_bytes(tris, verts, subm):
    # SL mesh: quantised position/normal/UV (16 B per vertex) + indices (6 B per triangle), zlib ~0.6
    return (verts * 16 + tris * 6) * 0.6 + 40 * subm


def streaming_cost(radius, lod_bytes):
    """Replica of LLMeshCostData::getRadiusWeightedTris from the SL viewer."""
    max_dist, max_area, min_area = 512.0, 102944.0, 1.0
    dlowest = min(radius / 0.03, max_dist)
    dlow = min(radius / 0.06, max_dist)
    dmid = min(radius / 0.24, max_dist)
    high_area = min(math.pi * dmid * dmid, max_area)
    mid_area = min(math.pi * dlow * dlow, max_area)
    low_area = min(math.pi * dlowest * dlowest, max_area)
    lowest_area = max_area
    lowest_area -= low_area
    low_area -= mid_area
    mid_area -= high_area
    high_area = min(max(high_area, min_area), max_area)
    mid_area = min(max(mid_area, min_area), max_area)
    low_area = min(max(low_area, min_area), max_area)
    lowest_area = min(max(lowest_area, min_area), max_area)
    total = high_area + mid_area + low_area + lowest_area
    w = [high_area / total, mid_area / total, low_area / total, lowest_area / total]
    tris = [max(b - 384.0, 16.0) / 16.0 for b in lod_bytes]
    weighted = sum(a * b for a, b in zip(w, tris))
    return weighted / 250000.0 * 15000.0, w


# ------------------------------------------------------------------ table for the LSL scripts
KIND_CODE = {"structure": 0, "door": 1, "deco": 2, "light": 3, "furniture": 4, "water": 5}
LSL_DIR = os.path.join(ROOT, "lsl")


def _v(v):
    return "<" + ",".join(f"{c:.3f}" for c in v) + ">"


def write_lsl_table(report):
    """Inserts the piece table (name, kind, size, position relative to the throne) into the LSL scripts.
    With it the script recognises every prim even if SL has lost the names on upload."""
    ref = next(p for p in report["pieces"] if p["name"] == "N_Throne")
    rc = Vector(ref["center"])
    rows = []
    for p in report["pieces"]:
        off = Vector(p["center"]) - rc
        rows.append(f'"{p["name"]}", {KIND_CODE[p["kind"]]}, {_v(p["size_m"])}, {_v(off)}')
    table = "list TABLE = [\n    " + ",\n    ".join(rows) + "];"
    chair = next(p for p in report["pieces"] if p["name"] == "C04_Chair")
    seats = []
    for p in report["pieces"]:
        if "seat" in p:
            a = p["seat"]
            seats.append(f'"{p["name"]}", {_v(a["offset"])}, {a["yaw"]}, "{a["anim"]}", "{a["fallback"]}"')
    # moving pieces (doors, gate, portcullis) with size and position relative to the throne, so
    # they can be recognised even if SL does not keep the names
    mov = [f'"{p["name"]}", {_v(p["size_m"])}, {_v(Vector(p["center"]) - rc)}'
           for p in report["pieces"] if p["kind"] == "door"]
    constants = {
        "CHAIR_PIVOT": f"vector CHAIR_PIVOT = {_v(chair['pivot_rel'])};",
        "SEATS": "list SEATS = [\n    " + ",\n    ".join(seats) + "];",
        "THRONE_SIZE": "vector THRONE_SIZE = " + _v(ref["size_m"]) + ";",
        "MOVERS": "list MOVERS = [\n    " + ",\n    ".join(mov) + "];",
    }
    for fn in os.listdir(os.path.join(LSL_DIR, "templates")):
        src = open(os.path.join(LSL_DIR, "templates", fn), encoding="utf-8").read()
        # each script only gets the constants it uses (script memory is tight in SL)
        consts = "\n".join(line for name, line in constants.items() if re.search(r"\b" + name + r"\b", src))
        src = src.replace("//@@TABLE@@", table).replace("//@@CONSTANTS@@", consts)
        with open(os.path.join(LSL_DIR, fn), "w", encoding="utf-8") as f:
            f.write("// GENERATED by scripts/build_pit.py from lsl/templates/" + fn + " (do not edit by hand)\n" + src)


# ------------------------------------------------------------------ main
def build(save=True, export=True):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "The Pit"
    scene.unit_settings.system = "METRIC"
    colls = {lv: get_coll(COLL[lv]) for lv in LEVELS + ["PHYS"]}
    for lv in ("MEDIUM", "LOW", "LOWEST", "PHYS"):
        colls[lv].hide_render = True
        colls[lv].hide_viewport = True

    pieces = P.build_all()
    report = {"pieces": [], "levels": {}, "warnings": []}
    objs = {lv: [] for lv in LEVELS + ["PHYS"]}
    li_total = 0.0
    for pc in pieces:
        cache = {}
        if pc.kind in ("deco", "furniture", "light"):
            # LOD by radius: in SL, at a small radius the LOWEST weighs most; at a medium radius, LOW and MEDIUM
            g0 = pc.build(0)
            a0, b0 = g0.bounds()
            rad = (b0 - a0).length / 2
            pc.lod_map = (0, 0, 1, 3) if rad < 1.2 else ((0, 1, 2, 3) if rad < 2.2 else (0, 1, 3, 3))
            cache[0] = g0
        for m in pc.lod_map:
            if m not in cache:
                cache[m] = pc.build(m)
        geos = [cache[pc.lod_map[0]]] + [_copy(cache[m]) for m in pc.lod_map[1:]]
        if pc.kind in ("deco", "furniture", "light", "door") and pc.lod_map == (0, 0, 1, 3):
            geos[1] = decimate(geos[1], 300)
            geos[2] = decimate(geos[2], 40)
        if pc.kind in ("deco", "furniture", "light") and pc.lod_map != (0, 0, 1, 3):
            # triangle budget by radius (the levels that weigh most in the SL cost)
            hi = cache[0]
            if pc.lod_map == (0, 1, 2, 3):
                geos[1] = decimate(geos[1], min(800, max(60, hi.tri_count() // 4)))
                geos[2] = decimate(geos[2], min(120, max(16, hi.tri_count() // 20)))
            else:
                geos[1] = decimate(geos[1], 160)
        if not geos[0].verts:
            report["warnings"].append(f"{pc.name}: empty HIGH")
            continue
        mn, mx = geos[0].bounds()
        if getattr(pc, "fire", False):
            # the piece centre sits at the base of the flame: SL emits light and particles from there
            lz = [geos[0].verts[i] for f, m in zip(geos[0].faces, geos[0].mats) if m == "Flame" for i in f]
            c = sum(lz, Vector()) / len(lz)
            c.z = min(v.z for v in lz) + 0.04
            h = Vector([max(mx[i] - c[i], c[i] - mn[i]) for i in range(3)])
            mn, mx = c - h, c + h
            ensure_bounds(geos[0], mn, mx, geos[0].mats[0])
        if "Water" not in geos[0].mats:
            # fixed faces: every piece carries the 8 faces in the same order (tiny filler in the corner)
            for k, m in enumerate(FACE_MATS):
                if m not in geos[0].mats:
                    e = MARK
                    o = mn + Vector((e * (1 + 3 * k), e, 0))   # each filler in its own spot: welding does not merge them
                    geos[0].face([o, o + Vector((e, 0, 0)), o + Vector((0, e, 0))], m, (0, 0, -1))
        origin = (mn + mx) / 2
        hmats = [m for m in MATS if m in set(geos[0].mats)]
        markers = {}
        for i in range(1, 4):
            markers[LEVELS[i]] = ensure_bounds(geos[i], mn, mx, hmats[0])
            extra = set(geos[i].mats) - set(hmats)
            if extra:
                report["warnings"].append(f"{pc.name} {LEVELS[i]}: materials not in the HIGH {extra}")
        pg = phys_geo(pc.phys())
        markers["PHYS"] = ensure_bounds(pg, mn, mx, "Physics")
        entry = {"name": pc.name, "kind": pc.kind, "role": getattr(pc, "role", ""), "fire": getattr(pc, "fire", False),
                 "size_m": [round(c, 3) for c in (mx - mn)],
                 "center": [round(c, 3) for c in origin], "triangles": {}, "bbox_markers": markers}
        lod_bytes = []
        for i, lv in enumerate(LEVELS):
            ob = mesh_object(pc.name + SUFFIX[lv], geos[i], origin, colls[lv], lv, pc.name, pc.kind)
            objs[lv].append(ob)
            tris, nv, sm = submesh_stats(ob)
            entry["triangles"][lv] = tris
            lod_bytes.append(est_bytes(tris, nv, sm))
        ob = mesh_object(pc.name + SUFFIX["PHYS"], pg, origin, colls["PHYS"], "PHYS", pc.name, pc.kind)
        objs["PHYS"].append(ob)
        entry["triangles"]["PHYS"] = len(pg.faces) and sum(len(f) - 2 for f in pg.faces)
        radius = (mx - mn).length / 2
        cost, w = streaming_cost(radius, lod_bytes)
        entry["radius_m"] = round(radius, 2)
        entry["lod_weight"] = [round(x, 4) for x in w]
        entry["li_download_est"] = round(cost, 3)
        entry["sl_faces"] = hmats
        li_total += cost
        dims_ok = min(mx - mn) >= 0.5
        if pc.name in P.SITS:
            pt, yaw, anim, fb = P.SITS[pc.name]
            entry["seat"] = {"offset": [round(c, 3) for c in (pt - origin)], "yaw": yaw, "anim": anim, "fallback": fb}
        if hasattr(pc, "pivot"):
            entry["pivot_rel"] = [round(c, 3) for c in (pc.pivot - origin)]
        if pc.kind == "structure" and not dims_ok:
            report["warnings"].append(f"{pc.name}: some dimension < 0.5 m; SL will use a convex hull")
        report["pieces"].append(entry)

    for lv in LEVELS + ["PHYS"]:
        report["levels"][lv] = {"objects": len(objs[lv]),
                                "triangles": sum(p["triangles"][lv] for p in report["pieces"])}

    n = len(report["pieces"])
    report["li_estimate"] = {
        "download_total": round(li_total, 1),
        "server_total": n * 0.5,
        "estimate": round(max(li_total, n * 0.5), 1),
        "note": "Estimate using the viewer's streaming cost formula and an approximate compressed size. "
                "Physics is not estimated: with Prim/None assigned correctly it should not dominate. "
                "The real value is the one the viewer shows on upload (Calculate weights & fee button).",
    }
    # footprint
    allmn = Vector((1e9, 1e9, 1e9))
    allmx = Vector((-1e9, -1e9, -1e9))
    for p in report["pieces"]:
        c, t = Vector(p["center"]), Vector(p["size_m"])
        allmn = Vector(map(min, allmn, c - t / 2))
        allmx = Vector(map(max, allmx, c + t / 2))
    size = allmx - allmn
    report["footprint"] = {"x_m": round(size.x, 2), "y_m": round(size.y, 2), "height_m": round(size.z, 2),
                           "area_m2": round(size.x * size.y, 1), "limit_m2": 1011.5,
                           "parcel_percent": round(100 * size.x * size.y / 2023, 1)}

    if export:
        bpy.context.view_layer.update()
        # SL naming: picking ThePit.dae in Upload > Model loads the LODs and the physics by themselves
        names = {"HIGH": "ThePit.dae", "MEDIUM": "ThePit_LOD2.dae", "LOW": "ThePit_LOD1.dae",
                 "LOWEST": "ThePit_LOD0.dae", "PHYS": "ThePit_PHYS.dae"}
        for lv, fn in names.items():
            write_dae(os.path.join(OUT, fn), objs[lv])
        report["files"] = list(names.values())

    write_lsl_table(report)
    report["seconds"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "Report.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if save:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "ThePit.blend"), compress=True)
    return report, objs


if __name__ == "__main__":
    rep, _ = build(save="--no-save" not in sys.argv, export="--no-export" not in sys.argv)
    print(json.dumps({k: rep[k] for k in ("levels", "li_estimate", "footprint")}, ensure_ascii=False, indent=1))
    for a in rep["warnings"]:
        print("WARNING:", a)
    top = sorted(rep["pieces"], key=lambda p: -p["li_download_est"])[:15]
    for p in top:
        print(f"{p['name']:<28} r={p['radius_m']:<6} LI~{p['li_download_est']:<6} {p['triangles']}")

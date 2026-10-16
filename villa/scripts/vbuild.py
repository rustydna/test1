"""Villa build engine: pieces -> Blender objects -> one DAE set per linkset, LODs, physics,
land impact estimate and a JSON report.

A piece is registered with @piece(linkset, name, kind=..., phys=...) on a function
`fn(lod) -> Shape` (lod 0 = HIGH; 1, 2, 3 = MEDIUM, LOW, LOWEST may return None to let the
engine decimate the HIGH). Every piece is uploaded with the 8 material slots in fixed order
(tiny filler triangles add the missing ones) so scripts can address face N = slot N everywhere.
The pool water is the only piece with a single "water" material.

Second Life naming: <Linkset>.dae with <Linkset>_LOD2/_LOD1/_LOD0/_PHYS.dae next to it, so
picking the first file in Upload > Model loads the others by themselves.
"""

import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(HERE)), "the_pit", "scripts"))

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import vmesh as M  # noqa: E402
from collada_static import write_dae  # noqa: E402  (shared with The Pit)

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "output")
LEVELS = ["HIGH", "MEDIUM", "LOW", "LOWEST"]
SUFFIX = {"HIGH": "", "MEDIUM": "_LOD2", "LOW": "_LOD1", "LOWEST": "_LOD0", "PHYS": "_PHYS"}
KINDS = ("structure", "glass", "door", "furniture", "light", "deco", "water", "plant", "core")
MARK = 0.004
PREVIEW = {   # viewport / DAE colours (the real look comes from the PBR materials in SL)
    "a_plaster": (0.86, 0.84, 0.80), "b_floor": (0.62, 0.58, 0.52), "c_wood": (0.45, 0.30, 0.18),
    "d_stone": (0.78, 0.74, 0.66), "e_fabric": (0.70, 0.64, 0.56), "f_metal": (0.72, 0.60, 0.40),
    "g_glass": (0.55, 0.65, 0.70), "h_glow": (1.0, 0.86, 0.62), "water": (0.10, 0.45, 0.55),
    "Physics": (0.2, 0.6, 1.0)}

REGISTRY = []          # Piece objects in registration order
LINKSETS = {}          # linkset name -> {"root": piece name, "label": text}


class Piece:
    def __init__(self, linkset, name, fn, kind, phys, lods, meta):
        self.linkset, self.name, self.fn, self.kind = linkset, name, fn, kind
        self.phys_spec, self.lods, self.meta = phys, lods, meta


def linkset(name, root, label="", role="house", **meta):
    """Declares a linkset. role: "site" (always rezzed, e.g. the Villa Core and its plot) or
    "house" (one switchable variant). The land impact test adds the site to every house."""
    LINKSETS[name] = {"root": root, "label": label, "role": role, "meta": meta}


def piece(ls, name, kind="structure", phys="hull", lods=None, **meta):
    """Registers a piece builder. phys: 'hull' (convex hull of the LOWEST), 'none' (a tiny
    triangle: walk-through, e.g. plants, curtains, water), 'box' (bounding box), 'floor'
    (a slab the size of the footprint, top at the bounding box top) or a function(lod_shape)
    -> list of ('box', mn, mx) / ('hull', [points]) / ('slab', poly, z0, z1).
    lods: optional (medium, low, lowest) triangle targets for automatic decimation."""
    assert kind in KINDS, kind

    def deco(fn):
        REGISTRY.append(Piece(ls, name, fn, kind, phys, lods, meta))
        return fn
    return deco


# ------------------------------------------------------------------ helpers
def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
    c = PREVIEW.get(name, (0.5, 0.5, 0.5))
    m.diffuse_color = (*c, 1.0)
    return m


def get_coll(name):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(c)
    return c


def shape_bounds(s):
    return s.bounds()


def ensure_bounds(s, mn, mx, slot):
    """Clamps a level to the HIGH box and marks the two corners, so SL does not stretch it."""
    for v in s.bm.verts:
        v.co.x = min(max(v.co.x, mn.x), mx.x)
        v.co.y = min(max(v.co.y, mn.y), mx.y)
        v.co.z = min(max(v.co.z, mn.z), mx.z)
    a, b = s.bounds()
    if s.bm.verts and (a - mn).length < 1e-5 and (b - mx).length < 1e-5:
        return False
    e = MARK
    for c, sx in ((mn, 1), (mx, -1)):
        v0 = s.vert(c)
        v1 = s.vert(c + Vector((sx * e, 0, 0)))
        v2 = s.vert(c + Vector((0, sx * e, 0)))
        s.face([v0, v1, v2], slot)
    return True


def fill_slots(s, mn):
    """Adds a tiny triangle for every slot the piece lacks (fixed face numbers in SL)."""
    present = {f.material_index for f in s.bm.faces}
    for k, slot in enumerate(M.SLOTS):
        if k in present:
            continue
        o = mn + Vector((MARK * (1 + 3 * k), MARK, 0))
        s.face([s.vert(o), s.vert(o + Vector((MARK, 0, 0))), s.vert(o + Vector((0, MARK, 0)))], slot)


def phys_shape(pc, high, lowest, mn, mx):
    """Physics mesh for the piece (Second Life: set 'physics shape: prim' by script)."""
    g = M.Shape()
    spec = pc.phys_spec
    if spec == "none":
        return g
    if spec == "box":
        spec = lambda _s: [("box", mn, mx)]                   # noqa: E731
    if spec == "floor":
        spec = lambda _s: [("box", Vector((mn.x, mn.y, mx.z - 0.1)), mx)]   # noqa: E731
    if spec == "hull":
        src = lowest if lowest.bm.verts else high
        spec = lambda _s: [("hull", [v.co.copy() for v in src.bm.verts])]   # noqa: E731
    for item in spec(high):
        if item[0] == "box":
            b = M.box_cage(item[1], item[2], "a_plaster")
            g.join(b)
        elif item[0] == "hull":
            bm = bmesh.new()
            for p in item[1]:
                bm.verts.new(p)
            if len(bm.verts) >= 4:
                bmesh.ops.convex_hull(bm, input=bm.verts)
                for f in [f for f in bm.faces if not f.is_valid]:
                    bm.faces.remove(f)
                h = M.Shape(bm)
                h.set_slot("a_plaster")
                g.join(h)
            else:
                bm.free()
        elif item[0] == "slab":
            g.join(M.extrude(item[1], item[2], item[3], "a_plaster"))
    g.set_slot("a_plaster")
    return g


def to_object(name, s, origin, coll, sl_name, kind, level):
    me = bpy.data.meshes.new(name)
    s.bm.normal_update()
    s.bm.to_mesh(me)
    for v in me.vertices:
        v.co -= origin
    used = sorted({p.material_index for p in me.polygons})
    names = [M.ALL[i] for i in used] if level != "PHYS" else ["Physics"]
    remap = {old: new for new, old in enumerate(used)}
    for n in names:
        me.materials.append(material(n))
    for p in me.polygons:
        p.material_index = 0 if level == "PHYS" else remap[p.material_index]
    me.update()
    if level != "PHYS":
        M.sharp_by_angle(me)
        M.uv_box(me, origin)
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    ob["sl_name"] = sl_name
    ob["sl_kind"] = kind
    ob["sl_level"] = level
    coll.objects.link(ob)
    return ob


# ------------------------------------------------------------------ land impact estimate
def mesh_bytes(ob):
    me = ob.data
    me.calc_loop_triangles()
    cn = me.corner_normals
    uv = me.uv_layers[0].data if me.uv_layers else None
    verts = set()
    tris = 0
    for t in me.loop_triangles:
        tris += 1
        for li in t.loops:
            verts.add((t.material_index, me.loops[li].vertex_index, tuple(round(c, 3) for c in cn[li].vector),
                       tuple(round(c, 4) for c in uv[li].uv) if uv else ()))
    return tris, (len(verts) * 16 + tris * 6) * 0.6 + 40 * len(me.materials)


def streaming_cost(radius, lod_bytes):
    """LLMeshCostData::getRadiusWeightedTris from the SL viewer (see The Pit's build)."""
    max_area, min_area = 102944.0, 1.0
    dlowest = min(radius / 0.03, 512.0)
    dlow = min(radius / 0.06, 512.0)
    dmid = min(radius / 0.24, 512.0)
    high = min(math.pi * dmid * dmid, max_area)
    mid = min(math.pi * dlow * dlow, max_area)
    low = min(math.pi * dlowest * dlowest, max_area)
    lowest = max_area - low
    low -= mid
    mid -= high
    areas = [min(max(a, min_area), max_area) for a in (high, mid, low, lowest)]
    tot = sum(areas)
    w = [a / tot for a in areas]
    tris = [max(b - 384.0, 16.0) / 16.0 for b in lod_bytes]
    return sum(a * b for a, b in zip(w, tris)) / 250000.0 * 15000.0, w


LI_PER_TRI = 0.04          # ~ land impact of one triangle at full LOD weight (16-byte verts, zlib)
LI_TARGET = {"structure": 5.0, "glass": 2.0, "door": 1.0, "furniture": 1.6, "light": 0.8, "deco": 0.8,
             "water": 1.5, "plant": 1.2, "core": 1.5}


def lod_weights(radius):
    return streaming_cost(radius, [400.0] * 4)[1]


def auto_lods(pc, high, radius):
    """Triangle targets for MEDIUM/LOW/LOWEST. Second Life charges each level by how much of the
    view it is shown in: a small piece is paid almost only by its LOWEST, a big one by MEDIUM.
    So: start from quality ratios of the HIGH, then scale the lower levels down until the
    piece fits its land impact target (meta li=..., else by kind). Floors keep silhouettes."""
    if pc.lods:
        return pc.lods
    t = high.tri_count()
    w = lod_weights(radius)
    target = pc.meta.get("li", LI_TARGET.get(pc.kind, 1.0))
    floors = (min(t, 60), min(t, 24), min(t, 8))
    want = [max(f, int(t * r)) for f, r in zip(floors, (0.4, 0.1, 0.025))]
    left = max(target - w[0] * t * LI_PER_TRI, target * 0.25)
    cost = sum(wi * n * LI_PER_TRI for wi, n in zip(w[1:], want))
    if cost > left:
        k = left / cost
        want = [max(f, int(n * k)) for f, n in zip(floors, want)]
    # each level no richer than the one above it
    want[1] = min(want[1], want[0])
    want[2] = min(want[2], want[1])
    return tuple(want)


def impostor(s, dirs=None):
    """A tiny convex stand-in for the LOWEST level: the hull of the extreme points of the piece in
    14 directions, painted with the slot that covers most of the piece."""
    dirs = dirs or [Vector(d).normalized() for d in
                    ((1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1),
                     (1, 1, 1), (1, 1, -1), (1, -1, 1), (1, -1, -1), (-1, 1, 1), (-1, 1, -1), (-1, -1, 1),
                     (-1, -1, -1))]
    pts = []
    for d in dirs:
        v = max(s.bm.verts, key=lambda v: v.co.dot(d))
        if all((v.co - p).length > 1e-4 for p in pts):
            pts.append(v.co.copy())
    area = {}
    for f in s.bm.faces:
        area[f.material_index] = area.get(f.material_index, 0.0) + f.calc_area()
    slot = M.ALL[max(area, key=area.get)]
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    if len(pts) >= 4:
        bmesh.ops.convex_hull(bm, input=bm.verts)
        for f in [f for f in bm.faces if not f.is_valid]:
            bm.faces.remove(f)
    out = M.Shape(bm)
    out.set_slot(slot)
    return out


def build_piece(pc, report):
    high = pc.fn(0)
    if high is None or not high.bm.faces:
        report["warnings"].append(f"{pc.name}: empty HIGH")
        return None
    high.recalc()
    mn, mx = high.bounds()
    size = mx - mn
    radius = size.length / 2
    targets = auto_lods(pc, high, radius)
    levels = [high]
    for i in (1, 2, 3):
        custom = pc.fn(i)
        if custom is None:
            src = levels[-1] if i > 1 else high
            custom = src.copy().decimate(targets[i - 1])
        if i == 3 and custom.tri_count() > max(2 * targets[2], targets[2] + 12):
            custom.bm.free()
            custom = impostor(high)
        levels.append(custom)
    lowest = levels[3]
    phys = phys_shape(pc, high, lowest, mn, mx)
    if pc.kind != "water":
        fill_slots(high, mn)
    hslots = sorted({f.material_index for f in high.bm.faces})
    first = M.ALL[hslots[0]]
    markers = {}
    for i in (1, 2, 3):
        markers[LEVELS[i]] = ensure_bounds(levels[i], mn, mx, first)
        extra = {f.material_index for f in levels[i].bm.faces} - set(hslots)
        if extra:
            report["warnings"].append(f"{pc.name} {LEVELS[i]}: slots not in HIGH {extra}")
    markers["PHYS"] = ensure_bounds(phys, mn, mx, "a_plaster")
    return levels, phys, mn, mx, markers


def build(only=None, export=True, save=False, verbose=True):
    """Builds every linkset (or only the ones listed) and returns the report."""
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {"linksets": {}, "pieces": [], "warnings": []}
    objs = {}
    for pc in REGISTRY:
        if only and pc.linkset not in only:
            continue
        res = build_piece(pc, report)
        if res is None:
            continue
        levels, phys, mn, mx, markers = res
        origin = (mn + mx) / 2
        ls = objs.setdefault(pc.linkset, {lv: [] for lv in LEVELS + ["PHYS"]})
        lod_bytes, tris = [], {}
        for i, lv in enumerate(LEVELS):
            coll = get_coll(f"{pc.linkset} | {lv}")
            ob = to_object(pc.name + SUFFIX[lv], levels[i], origin, coll, pc.name, pc.kind, lv)
            ls[lv].append(ob)
            t, b = mesh_bytes(ob)
            tris[lv] = t
            lod_bytes.append(b)
        coll = get_coll(f"{pc.linkset} | PHYS")
        ob = to_object(pc.name + SUFFIX["PHYS"], phys, origin, coll, pc.name, pc.kind, "PHYS")
        ls["PHYS"].append(ob)
        tris["PHYS"] = sum(len(p.vertices) - 2 for p in ob.data.polygons)
        radius = (mx - mn).length / 2
        cost, w = streaming_cost(radius, lod_bytes)
        entry = {"name": pc.name, "linkset": pc.linkset, "kind": pc.kind,
                 "size_m": [round(c, 3) for c in (mx - mn)], "center": [round(c, 3) for c in origin],
                 "radius_m": round(radius, 2), "triangles": tris, "lod_weight": [round(x, 3) for x in w],
                 "li_est": round(cost, 3), "markers": markers}
        entry.update({k: v for k, v in pc.meta.items() if isinstance(v, (int, float, str, list, dict, bool))})
        report["pieces"].append(entry)
        for lv in LEVELS:
            levels[LEVELS.index(lv)].bm.free()
        phys.bm.free()
        if verbose:
            print(f"  {pc.linkset:<14} {pc.name:<28} r={radius:5.2f}  tris={tris['HIGH']:6d}"
                  f"/{tris['MEDIUM']}/{tris['LOW']}/{tris['LOWEST']}  LI~{cost:.2f}", flush=True)

    for name, levels in objs.items():
        ps = [p for p in report["pieces"] if p["linkset"] == name]
        li = sum(p["li_est"] for p in ps)
        mn = Vector([min(p["center"][i] - p["size_m"][i] / 2 for p in ps) for i in range(3)])
        mx = Vector([max(p["center"][i] + p["size_m"][i] / 2 for p in ps) for i in range(3)])
        root = LINKSETS.get(name, {}).get("root")
        # the root prim must be the FIRST object of the DAE: SL makes the first node the root
        for lv in levels:
            levels[lv].sort(key=lambda o: 0 if o["sl_name"] == root else 1)
        files = []
        if export:
            os.makedirs(os.path.join(OUT, "models"), exist_ok=True)
            for lv in LEVELS + ["PHYS"]:
                fn = name + SUFFIX[lv] + ".dae"
                write_dae(os.path.join(OUT, "models", fn), levels[lv])
                files.append(fn)
        report["linksets"][name] = {
            "pieces": len(ps), "root": root, "label": LINKSETS.get(name, {}).get("label", ""),
            "li_download_est": round(li, 1), "li_server": len(ps) * 0.5,
            "li_estimate": round(max(li, len(ps) * 0.5), 1),
            "size_m": [round(c, 2) for c in (mx - mn)], "min": [round(c, 2) for c in mn],
            "triangles_high": sum(p["triangles"]["HIGH"] for p in ps), "files": files}
    report["roles"] = {n: LINKSETS.get(n, {}).get("role", "house") for n in report["linksets"]}
    report["seconds"] = round(time.time() - t0, 1)
    if save:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Villa.blend"), compress=True)
    return report


def write_report(report, path=None):
    path = path or os.path.join(OUT, "Report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=1)
    return path

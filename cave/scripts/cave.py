"""THE CAVE - a large natural cave for Second Life roleplay, all mesh.

Plan (metres, origin at the centre of the Great Hall floor, +Y north, the mouth to the east):
    Entrance tunnel   from the mouth at x = +23 west to the hall; a hide curtain at x = 19
    Great Hall        (4, 0)    24 x 20 m, 9 m dome: the hearth, log benches, furs, supplies
    Lake Grotto       (-12, 8)  18 x 16 m: a still lake with a waterfall, a sky chimney,
                                glow-worms on the ceiling, stepping stones and a raft
    Hot Spring        (-10, -10) a steaming stone basin
    Crystal Grotto    (14, -12) crystal clusters, an old altar and a treasure chest
    The Den           (14, 11)  three fur beds on rock ledges
The rock is one continuous shell (merged volumes, voxel remeshed, sculpted with noise, 1.4 m
thick so it is a rock mound from outside), cut into 12 pieces so each stays cheap in land
impact. Props are dropped onto the real floor and walls by ray casts.

Slots (fixed face numbers, same pipeline as the Villa): 0 rock, 1 ground, 2 wood, 3 moss/wet
stone, 4 fur/leather, 5 metal, 6 crystal, 7 glow; the water pieces have only "water".
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "villa", "scripts"))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401  (before bmesh with the PyPI module)
import bmesh  # noqa: E402
from mathutils import Vector, noise  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import vbuild as B  # noqa: E402
import vmesh as M  # noqa: E402
from furniture import catalogue as C  # noqa: E402

B.OUT = os.path.join(os.path.dirname(HERE), "output")
M.UV_TILE.update({"a_plaster": 4.0, "b_floor": 3.0, "c_wood": 1.2, "d_stone": 3.0, "e_fabric": 0.8,
                  "f_metal": 1.0, "g_glass": 1.0, "h_glow": 1.0, "water": 4.0})
ROCK, GROUND, WOOD, MOSS, FUR, METAL, CRYSTAL, GLOW = M.SLOTS
LS = "Cave"
B.linkset(LS, "Cave_Hearth", label="The Cave", role="house")

CHAMBERS = {   # name: (centre, rx, ry, dome height, floor bowl depth)
    "hall": ((4.0, 0.0, 0.3), 12.0, 10.0, 9.0, 0.3),
    "lake": ((-12.0, 8.0, 0.2), 9.0, 8.0, 7.0, 1.8),
    "spring": ((-10.0, -10.0, 0.2), 6.0, 5.5, 5.0, 0.25),
    "crystal": ((14.0, -12.0, 0.2), 6.0, 6.0, 7.0, 0.2),
    "den": ((14.0, 11.0, 0.2), 6.0, 5.0, 4.5, 0.2),
}
TUNNELS = [((4, 0), (27, 0)), ((4, 0), (-12, 8)), ((4, 0), (-10, -10)), ((4, 0), (14, -12)), ((4, 0), (14, 11))]
MOUTH_X = 23.0
CHIMNEY = (-12.0, 8.0, 1.8)
WATER_Z = -0.3
CUT_X = [-11.0, 0.0, 11.0]
CUT_Y = [-6.5, 6.5]


def chamber(c, rx, ry, rup, rdown, nu=40, nv=20):
    """Air volume of a chamber: an ellipsoid with a tall dome and a shallow floor bowl."""
    s = M.Shape()
    rows = []
    for j in range(nv + 1):
        t = -math.pi / 2 + math.pi * j / nv
        r, z = math.cos(t), math.sin(t)
        rz = rup if z > 0 else rdown
        if r < 1e-6:
            rows.append([s.vert((c[0], c[1], c[2] + z * rz))])
            continue
        rows.append([s.vert((c[0] + rx * r * math.cos(2 * math.pi * i / nu), c[1] + ry * r * math.sin(2 * math.pi * i / nu),
                             c[2] + z * rz)) for i in range(nu)])
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(nu):
            k = (i + 1) % nu
            if len(a) == 1:
                s.face([a[0], b[k], b[i]], ROCK)
            elif len(b) == 1:
                s.face([a[i], a[k], b[0]], ROCK)
            else:
                s.face([a[i], a[k], b[k], b[i]], ROCK)
    s.recalc()
    return s


def build_shell():
    parts = [chamber(*v) for v in CHAMBERS.values()]
    prof = [(2.4 * math.cos(a * math.pi / 8), 2.1 * math.sin(a * math.pi / 8)) for a in range(16)]
    for p0, p1 in TUNNELS:
        path = [(p0[0] + (p1[0] - p0[0]) * k / 6, p0[1] + (p1[1] - p0[1]) * k / 6, 1.9) for k in range(7)]
        parts.append(M.sweep(path, 1.0, ROCK, profile=prof))
    s = M.join(*parts)
    ob = s._object()
    r = ob.modifiers.new("r", "REMESH")
    r.mode = "VOXEL"
    r.voxel_size = 0.55
    sm = ob.modifiers.new("s", "SMOOTH")
    sm.iterations = 6
    sm.factor = 0.8
    s._take(ob)
    s.bm.normal_update()
    # sculpt: big lumps and fine fractures; the floor (normals pointing down) stays walkable
    for v in s.bm.verts:
        n = v.normal
        d = noise.fractal(v.co * 0.22, 0.55, 2.1, 4) * 0.55 + noise.noise(v.co * 0.07) * 0.8
        if n.z < -0.6:
            d *= 0.12
        elif v.co.z < 0.8:
            d *= 0.5
        v.co += n * d
    # open the mouth and the sky chimney over the lake
    dele = []
    for f in s.bm.faces:
        c = f.calc_center_median()
        if c.x > MOUTH_X or (math.hypot(c.x - CHIMNEY[0], c.y - CHIMNEY[1]) < CHIMNEY[2] and f.normal.z > 0.4):
            dele.append(f)
    bmesh.ops.delete(s.bm, geom=dele, context="FACES")
    bvh = BVHTree.FromBMesh(s.bm)
    # thickness outwards: the original surface becomes the inside (slot 0), the new one the outside (slot 3)
    ob = s._object()
    for sl in M.ALL:
        ob.data.materials.append(M._slot_material(sl))
    mod = ob.modifiers.new("sol", "SOLIDIFY")
    mod.thickness = 1.4
    mod.offset = 1.0
    mod.use_rim = True
    mod.use_even_offset = True
    mod.material_offset = 3
    mod.material_offset_rim = 0
    s._take(ob)
    # paint: ground on floors, wet stone near the lake and spring, moss on top outside
    lake_c, lrx, lry = CHAMBERS["lake"][0], CHAMBERS["lake"][1], CHAMBERS["lake"][2]
    outer = set()
    for f in s.bm.faces:
        c = f.calc_center_median()
        n = f.normal
        if f.material_index != 0:
            outer.update(f.verts)
        if f.material_index == 0:
            near_lake = ((c.x - lake_c[0]) / lrx) ** 2 + ((c.y - lake_c[1]) / lry) ** 2 < 1.1
            if n.z > 0.55:
                f.material_index = M.slot_index(MOSS if (near_lake and c.z < 0.1) else GROUND)
            elif near_lake and c.z < 1.2:
                f.material_index = M.slot_index(MOSS)
        else:
            f.material_index = M.slot_index(MOSS if n.z > 0.65 else ROCK)
    # the outside is rougher: crags and ledges on the mound
    s.bm.normal_update()
    for v in outer:
        if v.co.z > -0.5:
            v.co += v.normal * (noise.fractal(v.co * 0.15, 0.6, 2.2, 4) * 1.1)
    s.decimate(20000)
    return s, bvh


SHELL, BVH = build_shell()


def drop(x, y, z=3.0):
    """Floor height under (x, y) (ray cast down onto the cave surface)."""
    hit = BVH.ray_cast(Vector((x, y, z)), Vector((0, 0, -1)), 20.0)
    return hit[0].z if hit[0] else 0.0


def ceiling(x, y, z=1.0):
    hit = BVH.ray_cast(Vector((x, y, z)), Vector((0, 0, 1)), 20.0)
    return hit[0].z if hit[0] else None


def wall(c, ang, z):
    """Point and inward normal of the wall seen from c at angle ang (degrees), height z."""
    d = Vector((math.cos(math.radians(ang)), math.sin(math.radians(ang)), 0))
    hit = BVH.ray_cast(Vector((c[0], c[1], z)), d, 30.0)
    if not hit[0]:
        return None, None
    n = hit[1].copy()
    if n.dot(d) > 0:
        n = -n
    return hit[0], n


# ------------------------------------------------------------------ the rock in 12 pieces
def cell(i, j):
    xs = [-1e9] + CUT_X + [1e9]
    ys = [-1e9] + CUT_Y + [1e9]
    x0, x1, y0, y1 = xs[i], xs[i + 1], ys[j], ys[j + 1]
    s = SHELL.copy()
    s.join(EXTRA.copy())
    for co, no, keep_above in (((x0, 0, 0), (1, 0, 0), True), ((x1, 0, 0), (1, 0, 0), False),
                               ((0, y0, 0), (0, 1, 0), True), ((0, y1, 0), (0, 1, 0), False)):
        if abs(co[0]) > 1e8 or abs(co[1]) > 1e8:
            continue
        geom = list(s.bm.verts) + list(s.bm.edges) + list(s.bm.faces)
        bmesh.ops.bisect_plane(s.bm, geom=geom, plane_co=co, plane_no=no, clear_inner=keep_above,
                               clear_outer=not keep_above)
    return s


def _cell_phys(high):
    return [("mesh", high.copy().decimate(max(60, high.tri_count() // 8)))]


for _i in range(len(CUT_X) + 1):
    for _j in range(len(CUT_Y) + 1):
        @B.piece(LS, f"Cave_Rock_{_i}{_j}", kind="structure", phys=_cell_phys, li=7)
        def _rock(lod, i=_i, j=_j):
            if lod:
                return None
            s = cell(i, j)
            return s if s.bm.faces else None


# ------------------------------------------------------------------ water
def _lake_outline():
    c, rx, ry = CHAMBERS["lake"][0], CHAMBERS["lake"][1] * 0.95, CHAMBERS["lake"][2] * 0.95
    return M.superellipse(c[0], c[1], rx, ry, 56, 2.0)


@B.piece(LS, "Cave_Lake", kind="water", phys="none", li=1.5)
def lake(lod):
    if lod:
        return None
    return M.panel(_lake_outline(), WATER_Z, "water")


@B.piece(LS, "Cave_Waterfall", kind="water", phys="none", li=1.0)
def waterfall(lod):
    """A curved sheet of water spilling from a crack in the north wall into the lake."""
    if lod:
        return None
    top = 5.2
    p, n = wall(CHAMBERS["lake"][0], 100, top)
    x, y = (p.x + n.x * 0.35, p.y + n.y * 0.35) if p else (-12.5, 14.6)
    rows = []
    for k in range(9):
        t = k / 8
        z = top + (WATER_Z - top) * t
        out = 0.35 + 0.9 * t ** 1.6
        w = 0.9 + 0.5 * t
        rows.append([M.V(x + (u - 0.5) * 2 * w, y - out + 0.08 * math.sin(u * 7 + k), z) for u in [i / 6 for i in range(7)]])
    s = M.Shape()
    vs = [[s.vert(p) for p in r] for r in rows]
    for a, b in zip(vs[:-1], vs[1:]):
        for i in range(6):
            s.face([a[i], a[i + 1], b[i + 1], b[i]], "water")
            s.face([a[i + 1], a[i], b[i], b[i + 1]], "water")
    return s


# ------------------------------------------------------------------ props
def placed(name, fn, x, y, yaw=0.0, kind="deco", seat=None, phys="hull", li=None, dz=0.0):
    z = drop(x, y) + dz
    meta = {}
    if seat:
        lx, ly, lz, *poses = seat
        sx, sy = C.rot2(lx, ly, yaw)
        meta["seat"] = (x + sx, y + sy, z + lz, (yaw - 90.0) % 360.0, *poses)
    if li:
        meta["li"] = li

    @B.piece(LS, name, kind=kind, phys=phys, **meta)
    def _b(lod, fn=fn, x=x, y=y, z=z, yaw=yaw):
        if lod:
            return None
        return C.place(fn(), x, y, z, yaw)


def rock(cx, cy, cz, rx, ry, rz, slot=ROCK, seed=0.0, e=2.2):
    b = M.blob((cx, cy, cz), rx, ry, rz, slot, nu=14, nv=8, e=e)
    for v in b.bm.verts:
        v.co += (v.co - Vector((cx, cy, cz))).normalized() * noise.noise(v.co * 2.3 + Vector((seed, 0, 0))) * min(rx, rz) * 0.18
    return b


def hearth():
    """Ring of fire-blackened stones, crossed logs, the ember bed, an iron tripod and pot."""
    parts = []
    for k in range(10):
        a = 2 * math.pi * k / 10
        parts.append(rock(0.75 * math.cos(a), 0.75 * math.sin(a), 0.1, 0.2, 0.16, 0.14, ROCK, seed=k))
    parts.append(M.lathe([(0, 0.0), (0.62, 0.0), (0.6, 0.05), (0.3, 0.09), (0, 0.1)], GLOW, n=24))
    for k in range(4):
        a = math.radians(45 * k + 10)
        parts.append(M.sweep([(-0.45 * math.cos(a), -0.45 * math.sin(a), 0.1), (0.05 * math.cos(a), 0.05 * math.sin(a), 0.42)],
                             0.06, WOOD, n=8))
    for k in range(3):
        a = 2 * math.pi * k / 3
        parts.append(M.sweep([(0.85 * math.cos(a), 0.85 * math.sin(a), 0.0), (0, 0, 1.5)], 0.018, METAL, n=6))
    parts.append(M.lathe([(0, 0.82), (0.22, 0.85), (0.26, 0.98), (0.24, 1.1), (0.2, 1.13), (0, 1.12)], METAL, n=24))
    parts.append(M.sweep([(0, 0, 1.13), (0, 0, 1.5)], 0.008, METAL, n=4))
    return M.join(*parts)


def log_bench(l=2.0):
    log = M.sweep([(-l / 2, 0, 0.27), (0, 0.02, 0.29), (l / 2, 0, 0.27)], 0.2, WOOD, n=12)
    for v in log.bm.verts:
        v.co.z += noise.noise(v.co * 3.0) * 0.015
    for sx in (-0.6, 0.6):
        log.join(rock(sx * l / 2, 0, 0.08, 0.2, 0.22, 0.12, ROCK, seed=sx))
    # flatten the seat a little where people sit
    for v in log.bm.verts:
        if v.co.z > 0.44:
            v.co.z = 0.44 + (v.co.z - 0.44) * 0.3
    return log


def fur_rug(a=1.1, b=0.75, seed=1):
    poly = M.superellipse(0, 0, a, b, 28, 2.0)
    poly = [(x * (1 + 0.12 * noise.noise(Vector((x * 2, y * 2, seed)))), y * (1 + 0.12 * noise.noise(Vector((y * 2, x, seed)))))
            for x, y in poly]
    return M.pillow(poly, 0.0, 0.06, FUR, r=0.025, crown=0.02, levels=1)


def fur_bed():
    """Rock ledge with a fur nest and a rolled fur bolster at the head (+Y)."""
    ledge = rock(0, 0, 0.18, 1.25, 0.75, 0.24, ROCK, seed=3.3, e=3.0)
    nest = M.pillow(M.superellipse(0, -0.05, 1.05, 0.62, 28, 2.6), 0.36, 0.52, FUR, r=0.07, crown=0.03)
    bol = M.sweep([(-0.9, 0.5, 0.62), (0, 0.55, 0.66), (0.9, 0.5, 0.62)], 0.13, FUR, n=12)
    return M.join(ledge, nest, bol)


def torch():
    """Wall torch in an iron sconce (origin at the wall, the torch leans out along -Y)."""
    parts = [M.rounded_box((-0.06, -0.03, -0.1), (0.06, 0.0, 0.1), METAL, r=0.01, seg=1),
             M.sweep([(0, 0.0, 0.0), (0, -0.18, 0.05)], 0.012, METAL, n=6),
             M.sweep([(0, -0.18, -0.25), (0, -0.24, 0.28)], 0.025, WOOD, n=8),
             M.sweep([(0, -0.18, 0.05), (0, -0.18, 0.05)], 0.05, METAL, n=8)]
    head = M.blob((0, -0.24, 0.32), 0.05, 0.05, 0.07, GLOW, nu=10, nv=6)
    parts.append(head)
    return M.join(*parts)


def crystal_cluster(seed=1, scale=1.0):
    parts = []
    for k in range(7):
        a = 2 * math.pi * (k / 7) + seed
        tilt = 0.35 + 0.25 * ((k * 3 + seed) % 3) / 2
        h = scale * (0.6 + 0.9 * ((k * 5 + int(seed * 7)) % 5) / 4)
        r = scale * (0.07 + 0.05 * (k % 3))
        base = Vector((0.12 * scale * math.cos(a), 0.12 * scale * math.sin(a), 0))
        axis = Vector((math.sin(tilt) * math.cos(a), math.sin(tilt) * math.sin(a), math.cos(tilt)))
        prism = M.lathe([(0, 0), (r, 0), (r, h * 0.78), (0, h)], CRYSTAL, n=6)
        core = M.lathe([(0, 0.02), (r * 0.45, 0.02), (r * 0.45, h * 0.7), (0, h * 0.85)], GLOW, n=6)
        prism.join(core)
        rot = axis.to_track_quat("Z", "Y").to_matrix().to_4x4()
        prism.transform(rot)
        prism.move(base.x, base.y, base.z)
        parts.append(prism)
    parts.append(rock(0, 0, 0.0, 0.35 * scale, 0.3 * scale, 0.15 * scale, ROCK, seed=seed))
    return M.join(*parts)


def altar():
    slab = M.rounded_box((-0.9, -0.45, 0.0), (0.9, 0.45, 0.85), ROCK, r=0.06, seg=2)
    for v in slab.bm.verts:
        v.co += Vector((noise.noise(v.co * 4), noise.noise(v.co * 4 + Vector((5, 0, 0))), 0)) * 0.03
    top = M.slab(M.rounded_rect(0, 0, 1.95, 1.0, 0.08, 3), 0.85, 0.97, MOSS, r=0.02, seg=1)
    bowl = M.lathe([(0, 0.97), (0.2, 0.97), (0.24, 1.08), (0.22, 1.1), (0.18, 1.04), (0, 1.02)], METAL, n=24)
    flame = M.lathe([(0, 1.03), (0.15, 1.03), (0.0, 1.12)], GLOW, n=12)
    return M.join(slab, top, bowl, flame)


def chest():
    body = M.rounded_box((-0.45, -0.28, 0.0), (0.45, 0.28, 0.42), WOOD, r=0.02, seg=1)
    lid = M.sweep([(-0.45, 0, 0.42), (0.45, 0, 0.42)], 0.28, WOOD, n=12,
                  profile=[(math.cos(a), max(0.0, math.sin(a))) for a in [k * math.pi / 6 for k in range(7)]] + [(-1, 0)])
    bands = [M.rounded_box((x - 0.03, -0.29, 0.0), (x + 0.03, 0.29, 0.44), METAL, r=0.005, seg=1) for x in (-0.3, 0.3)]
    coins = rock(0.0, -0.55, 0.0, 0.45, 0.3, 0.12, METAL, seed=9, e=2.0)
    return M.join(body, lid, *bands, coins)


def barrel():
    s = M.lathe([(0, 0), (0.24, 0), (0.29, 0.35), (0.24, 0.7), (0, 0.7)], WOOD, n=20)
    for z in (0.08, 0.62):
        s.join(M.sweep([(0.265 * math.cos(a * math.pi / 10), 0.265 * math.sin(a * math.pi / 10), z) for a in range(20)],
                       0.012, METAL, n=4, closed=True))
    return s


def crate():
    return M.join(M.rounded_box((-0.35, -0.3, 0.0), (0.35, 0.3, 0.55), WOOD, r=0.01, seg=1),
                  *[M.rounded_box((-0.36, -0.31, z), (0.36, 0.31, z + 0.05), WOOD, r=0.005, seg=1) for z in (0.05, 0.45)])


def raft():
    planks = [M.rounded_box((-1.0, y - 0.11, 0.0), (1.0, y + 0.11, 0.14), WOOD, r=0.03, seg=1) for y in (-0.45, -0.22, 0, 0.22, 0.45)]
    lash = [M.sweep([(x, -0.6, 0.15), (x, 0.6, 0.15)], 0.02, FUR, n=6) for x in (-0.7, 0.7)]
    return M.join(*planks, *lash)


def curtain_hide(w=4.6, h=3.6):
    line = [(0, -w / 2), (0, w / 2)]
    s = M.curtain([(0.0, -w / 2), (0.0, w / 2)], 0.05, h, FUR, folds=10, depth=0.07)
    s.join(M.sweep([(0, -w / 2 - 0.2, h + 0.05), (0, w / 2 + 0.2, h + 0.05)], 0.05, WOOD, n=8))
    del line
    return s


# --- the Great Hall (root: the hearth)
HX, HY = 4.0, 0.0
placed("Cave_Hearth", hearth, HX, HY, kind="core", phys="box", li=1.0)
for k, a in enumerate((25, 145, 265)):
    r = 2.7
    x, y = HX + r * math.cos(math.radians(a)), HY + r * math.sin(math.radians(a))
    placed(f"Cave_Log_{k + 1}", log_bench, x, y, yaw=a - 90, kind="furniture",
           seat=(0, 0.0, 0.46, "cave_sit_relaxed", "cave_sit_upright", "cave_sit_crossed"))
for k, (a, r) in enumerate(((85, 2.4), (205, 2.3), (325, 2.4))):
    x, y = HX + r * math.cos(math.radians(a)), HY + r * math.sin(math.radians(a))
    placed(f"Cave_Fur_{k + 1}", lambda k=k: fur_rug(1.0, 0.7, k), x, y, yaw=a, kind="furniture", phys="none",
           seat=(0, 0.0, 0.06, "cave_sit_curl", "cave_sit_crossed"))
placed("Cave_Crates", lambda: M.join(crate().move(0, 0, 0), crate().rotate(14).move(0.8, 0.1, 0),
                                     crate().rotate(-8).move(0.35, 0.05, 0.55)), 12.5, -4.2, yaw=20)
placed("Cave_Barrels", lambda: M.join(barrel(), barrel().move(0.62, 0.05, 0), barrel().move(0.3, 0.55, 0)), 12.8, 4.0)
placed("Cave_Table", lambda: M.join(rock(0, 0, 0.35, 0.95, 0.6, 0.12, ROCK, seed=7, e=3.0),
                                    rock(-0.5, 0, 0.15, 0.25, 0.3, 0.22, ROCK, 2), rock(0.5, 0, 0.15, 0.25, 0.3, 0.22, ROCK, 4)),
       -1.5, -4.5, yaw=10)

# --- the Den
for k, (dx, dy, yaw) in enumerate(((-3.0, 2.0, 200), (0.0, 3.0, 180), (3.0, 1.5, 160))):
    cx, cy = CHAMBERS["den"][0][0], CHAMBERS["den"][0][1]
    placed(f"Cave_Bed_{k + 1}", fur_bed, cx + dx, cy + dy, yaw=yaw, kind="furniture",
           seat=(0, 0.3, 0.52, "cave_lounge", "cave_sit_curl", "cave_sit_relaxed"))

# --- the Hot Spring
SPX, SPY = CHAMBERS["spring"][0][0], CHAMBERS["spring"][0][1]


def spring():
    ring = M.lathe([(1.7, 0.0), (2.1, 0.0), (2.15, 0.35), (2.0, 0.5), (1.8, 0.48), (1.7, 0.3), (1.65, 0.02)], MOSS, n=36)
    for v in ring.bm.verts:
        v.co += Vector((0, 0, noise.noise(v.co * 1.7) * 0.06))
    floor = M.panel(M.superellipse(0, 0, 1.72, 1.72, 36, 2.0), 0.02, MOSS)
    return ring.join(floor)


placed("Cave_Spring", spring, SPX, SPY, kind="structure", phys="none", li=1.2)


@B.piece(LS, "Cave_Spring_Water", kind="water", phys="none", li=0.6)
def spring_water(lod):
    if lod:
        return None
    return M.panel(M.superellipse(SPX, SPY, 1.75, 1.75, 36, 2.0), drop(SPX, SPY) + 0.38, "water")


for k, a in enumerate((90, 270)):
    x, y = SPX + 1.25 * math.cos(math.radians(a)), SPY + 1.25 * math.sin(math.radians(a))
    placed(f"Cave_Spring_Seat_{k + 1}", lambda: rock(0, 0, 0.12, 0.3, 0.3, 0.14, MOSS, seed=1.5), x, y, yaw=a + 90,
           kind="seat", phys="none", seat=(0, 0.25, 0.22, "cave_sit_relaxed", "cave_lounge"))

# --- the Lake Grotto
LX, LY = CHAMBERS["lake"][0][0], CHAMBERS["lake"][0][1]
placed("Cave_Stepping_Stones", lambda: M.join(*[rock(1.0 * k, 0.35 * math.sin(k), 0.0, 0.42, 0.36, 0.42, MOSS, seed=k)
                                               for k in range(5)]), LX + 3.0, LY - 4.2, yaw=-30, phys="hull")


@B.piece(LS, "Cave_Raft", kind="furniture", phys="box", li=0.8, seat=(LX - 2.0, LY + 0.5, WATER_Z + 0.16, 270.0,
                                                                     "cave_sit_crossed", "cave_lounge"))
def raft_piece(lod):
    if lod:
        return None
    return raft().rotate(10).move(LX - 2.0, LY + 0.5, WATER_Z + 0.02)


def glowworms():
    """Hundreds of tiny glow points hanging under the lake grotto ceiling."""
    s = M.Shape()
    k = 0
    for i in range(-8, 9):
        for j in range(-7, 8):
            x = LX + i * 0.9 + 0.4 * noise.noise(Vector((i, j, 0.3)))
            y = LY + j * 0.9 + 0.4 * noise.noise(Vector((j, i, 0.7)))
            if math.hypot(x - CHIMNEY[0], y - CHIMNEY[1]) < CHIMNEY[2] + 0.4:
                continue
            z = ceiling(x, y)
            if z is None or z < 2.5:
                continue
            for d in range(2):
                zz = z - 0.15 - 0.35 * ((i * 7 + j * 3 + d) % 5) / 4
                xx, yy = x + 0.17 * d, y - 0.11 * d
                a = s.vert((xx - 0.02, yy, zz))
                b = s.vert((xx + 0.02, yy, zz))
                c = s.vert((xx, yy, zz + 0.04))
                s.face([a, b, c], GLOW)
                s.face([b, a, c], GLOW)
                k += 1
    return s




# --- the Crystal Grotto
CX_, CY_ = CHAMBERS["crystal"][0][0], CHAMBERS["crystal"][0][1]
placed("Cave_Altar", altar, CX_ + 1.5, CY_ - 2.6, yaw=0, kind="furniture",
       seat=(0, -0.95, 0.0, "cave_kneel"))
placed("Cave_Chest", chest, CX_ - 3.0, CY_ - 1.5, yaw=40)
for k, (dx, dy, sc) in enumerate(((3.2, 1.0, 1.4), (-2.6, 2.6, 1.0), (0.2, 3.6, 1.2), (-3.8, -0.8, 0.8), (3.6, -1.8, 1.0))):
    placed(f"Cave_Crystals_{k + 1}", lambda k=k, sc=sc: crystal_cluster(k * 1.3, sc), CX_ + dx, CY_ + dy, yaw=k * 47,
           kind="light", phys="hull")

# --- the entrance
placed("Cave_Curtain", curtain_hide, 19.0, 0.0, kind="door", phys="box", li=1.0)

# --- torches on the walls (ray cast from each chamber)
TORCHES = [("hall", 50), ("hall", 130), ("hall", 230), ("hall", 310), ("lake", 210), ("lake", 330),
           ("spring", 200), ("den", 60), ("den", 120), ("crystal", 300), ("entrance", 90), ("entrance", 270)]
for k, (ch, ang) in enumerate(TORCHES):
    c = (17.0, 0.0) if ch == "entrance" else CHAMBERS[ch][0][:2]
    p, n = wall(c, ang, 2.2)
    if p is None:
        continue
    yaw = math.degrees(math.atan2(n.x, -n.y))      # local -Y (the lean of the torch) along the inward normal

    @B.piece(LS, f"Cave_Torch_{k + 1}", kind="light", phys="none", li=0.4)
    def _torch(lod, p=p.copy(), n=n.copy(), yaw=yaw):
        if lod:
            return None
        return torch().rotate(yaw).move(p.x - n.x * 0.02, p.y - n.y * 0.02, p.z)


# --- stalactites and stalagmites, one piece per chamber
def formations(name, seed):
    (cx, cy, _), rx, ry, _, _ = CHAMBERS[name]
    s = M.Shape()
    for k in range(26):
        a = 2 * math.pi * ((k * 0.381966 + seed) % 1.0)
        f = 0.35 + 0.6 * ((k * 0.618 + seed * 0.3) % 1.0)
        x, y = cx + rx * f * math.cos(a), cy + ry * f * math.sin(a)
        if name == "hall" and math.hypot(x - HX, y - HY) < 4.0:
            continue
        top = ceiling(x, y)
        if top is not None and top > 2.8:
            L = 0.4 + 1.3 * ((k * 7) % 5) / 4
            s.join(M.lathe([(0.0, top + 0.1), (0.16 + 0.08 * (k % 3), top + 0.1), (0.08, top - L * 0.6), (0.0, top - L)],
                           MOSS if k % 3 == 0 else ROCK, n=8, center=(x, y, 0)))
        if f > 0.78 and name != "lake":
            fl = drop(x, y)
            H = 0.3 + 0.9 * ((k * 3) % 4) / 3
            s.join(M.lathe([(0.0, fl - 0.05), (0.22, fl - 0.05), (0.1, fl + H * 0.6), (0.0, fl + H)], ROCK, n=8,
                           center=(x, y, 0)))
    return s


# stalactites, stalagmites and glow-worms become part of the rock pieces they hang from
EXTRA = M.join(*[formations(_name, _k * 0.37) for _k, _name in enumerate(("hall", "lake", "spring", "crystal", "den"))],
               glowworms())

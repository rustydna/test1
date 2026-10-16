"""Organic mesh toolkit for the Villa (Blender bmesh + modifiers).

Everything the villa uploads is generated here as real mesh: no Second Life prims, no Blender
primitive operators. A `Shape` is a bmesh whose faces carry a material slot; the constructors
below build cages (lofts, lathes, sweeps, slabs, curved wall bands, rounded boxes, shells) and
`smooth()` turns a cage into a Catmull-Clark surface (with creases where an edge must stay crisp).

Material slots (Second Life sorts faces by material name, so the face number is fixed):
    0 a_plaster  1 b_floor  2 c_wood  3 d_stone  4 e_fabric  5 f_metal  6 g_glass  7 h_glow
and "water" for the pool water piece.

Units: metres, Z up. 2D outlines are lists of (x, y) tuples, counter-clockwise seen from above.
"""

import math

import bmesh
import bpy
from mathutils import Matrix, Vector

SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow"]
ALL = SLOTS + ["water"]
# metres per texture repeat (world-space box UVs): the textures are made at this physical scale
UV_TILE = {"a_plaster": 2.0, "b_floor": 1.6, "c_wood": 1.2, "d_stone": 1.6, "e_fabric": 0.5,
           "f_metal": 1.0, "g_glass": 2.0, "h_glow": 1.0, "water": 3.0}
# normals: edges sharper than this angle (degrees) stay hard; smooth below it
SMOOTH_ANGLE = {"a_plaster": 40, "b_floor": 30, "c_wood": 35, "d_stone": 35, "e_fabric": 60,
                "f_metal": 40, "g_glass": 30, "h_glow": 50, "water": 80}


def V(x, y=0.0, z=0.0):
    if isinstance(x, (tuple, list, Vector)):
        return Vector((x[0], x[1], x[2] if len(x) > 2 else 0.0))
    return Vector((x, y, z))


def slot_index(slot):
    return ALL.index(slot)


# ======================================================================== 2D curves
def catmull(points, n=8, closed=True):
    """Smooth curve through control points (centripetal Catmull-Rom), n samples per span."""
    p = [Vector((q[0], q[1], q[2] if len(q) > 2 else 0.0)) for q in points]
    m = len(p)
    spans = m if closed else m - 1
    out = []
    for i in range(spans):
        p0 = p[(i - 1) % m] if closed or i > 0 else p[0] * 2 - p[1]
        p1 = p[i % m]
        p2 = p[(i + 1) % m]
        p3 = p[(i + 2) % m] if closed or i + 2 < m else p2 * 2 - p1
        t0 = 0.0
        t1 = t0 + max((p1 - p0).length ** 0.5, 1e-6)
        t2 = t1 + max((p2 - p1).length ** 0.5, 1e-6)
        t3 = t2 + max((p3 - p2).length ** 0.5, 1e-6)
        last = (i == spans - 1) and not closed
        for k in range(n + (1 if last else 0)):
            t = t1 + (t2 - t1) * k / n
            a1 = p0 * ((t1 - t) / (t1 - t0)) + p1 * ((t - t0) / (t1 - t0))
            a2 = p1 * ((t2 - t) / (t2 - t1)) + p2 * ((t - t1) / (t2 - t1))
            a3 = p2 * ((t3 - t) / (t3 - t2)) + p3 * ((t - t2) / (t3 - t2))
            b1 = a1 * ((t2 - t) / (t2 - t0)) + a2 * ((t - t0) / (t2 - t0))
            b2 = a2 * ((t3 - t) / (t3 - t1)) + a3 * ((t - t1) / (t3 - t1))
            out.append(b1 * ((t2 - t) / (t2 - t1)) + b2 * ((t - t1) / (t2 - t1)))
    if len(points[0]) == 2:
        return [(v.x, v.y) for v in out]
    return [tuple(v) for v in out]


def resample(points, n, closed=True):
    """n points evenly spaced by arc length along a polyline."""
    pts = [Vector((q[0], q[1], q[2] if len(q) > 2 else 0.0)) for q in points]
    if closed:
        pts = pts + [pts[0]]
    seg = [(pts[i + 1] - pts[i]).length for i in range(len(pts) - 1)]
    total = sum(seg)
    count = n if closed else n - 1
    out, i, acc = [], 0, 0.0
    for k in range(n):
        d = total * k / count
        while i < len(seg) - 1 and acc + seg[i] < d:
            acc += seg[i]
            i += 1
        t = 0.0 if seg[i] == 0 else min(max((d - acc) / seg[i], 0.0), 1.0)
        out.append(pts[i].lerp(pts[i + 1], t))
    if len(points[0]) == 2:
        return [(v.x, v.y) for v in out]
    return [tuple(v) for v in out]


def superellipse(cx, cy, a, b, n=48, e=2.6, rot=0.0, phase=0.0):
    """|x/a|^e + |y/b|^e = 1: e=2 ellipse, e~2.5-4 the soft 'squircle' of modern architecture."""
    out = []
    c, s = math.cos(rot), math.sin(rot)
    for i in range(n):
        t = phase + 2 * math.pi * i / n
        ct, st = math.cos(t), math.sin(t)
        x = a * math.copysign(abs(ct) ** (2 / e), ct)
        y = b * math.copysign(abs(st) ** (2 / e), st)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def rounded_rect(cx, cy, w, d, r, seg=6, rot=0.0):
    """Rectangle w x d with corner radius r (r is clamped to half the short side)."""
    r = max(0.0, min(r, w / 2 - 1e-4, d / 2 - 1e-4))
    hw, hd = w / 2 - r, d / 2 - r
    out = []
    for k, (ox, oy) in enumerate(((hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd))):
        a0 = -math.pi / 2 + k * math.pi / 2
        for j in range(seg + 1):
            a = a0 + (math.pi / 2) * j / seg
            out.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    if r < 1e-4:
        out = [(hw, -hd), (hw, hd), (-hw, hd), (-hw, -hd)]
    c, s = math.cos(rot), math.sin(rot)
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in out]


def arc(cx, cy, r, a0, a1, n):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / (n - 1)), cy + r * math.sin(a0 + (a1 - a0) * i / (n - 1)))
            for i in range(n)]


def area2d(poly):
    return 0.5 * sum(poly[i][0] * poly[(i + 1) % len(poly)][1] - poly[(i + 1) % len(poly)][0] * poly[i][1]
                     for i in range(len(poly)))


def ccw(poly):
    return list(poly) if area2d(poly) > 0 else list(reversed(poly))


def offset2d(poly, d, closed=True):
    """Offsets a polyline by d (positive = to the left of the direction of travel; for a CCW
    closed outline that is outwards... no: left of travel is INSIDE a CCW loop, so use -d to grow).
    Miter joins, limited to 3x the distance."""
    n = len(poly)
    out = []
    for i in range(n):
        p = Vector((poly[i][0], poly[i][1]))
        if closed:
            a = Vector((poly[i - 1][0], poly[i - 1][1]))
            b = Vector((poly[(i + 1) % n][0], poly[(i + 1) % n][1]))
        else:
            a = Vector((poly[max(i - 1, 0)][0], poly[max(i - 1, 0)][1]))
            b = Vector((poly[min(i + 1, n - 1)][0], poly[min(i + 1, n - 1)][1]))
        t1 = (p - a) if (p - a).length > 1e-9 else (b - p)
        t2 = (b - p) if (b - p).length > 1e-9 else (p - a)
        t1.normalize()
        t2.normalize()
        n1 = Vector((-t1.y, t1.x))
        n2 = Vector((-t2.y, t2.x))
        m = n1 + n2
        if m.length < 1e-6:
            m = n1
        m.normalize()
        k = m.dot(n1)
        scale = d / max(k, 0.34)
        q = p + m * scale
        out.append((q.x, q.y))
    return out


def grow(poly, d):
    """Outline grown outwards by d (shrunk if d < 0); poly is made CCW first."""
    return offset2d(ccw(poly), -d, True)


def pts3(poly, z):
    return [Vector((p[0], p[1], z)) for p in poly]


# ======================================================================== Shape
class Shape:
    """A bmesh whose faces carry a material slot. Constructors return Shapes; join them freely."""

    def __init__(self, bm=None):
        self.bm = bm or bmesh.new()
        self._crease = None

    # -- low level
    def vert(self, co):
        return self.bm.verts.new(V(co))

    def face(self, verts, slot):
        try:
            f = self.bm.faces.new(verts)
        except ValueError:
            return None
        f.material_index = slot_index(slot)
        f.smooth = True
        return f

    def crease_layer(self):
        lay = self.bm.edges.layers.float.get("crease_edge")
        if lay is None:
            lay = self.bm.edges.layers.float.new("crease_edge")
        return lay

    def crease(self, edges, value=1.0):
        lay = self.crease_layer()
        for e in edges:
            e[lay] = value
        return self

    def crease_sharp(self, angle=60.0, value=1.0):
        """Creases every edge whose faces meet at more than `angle` degrees (keeps cage corners crisp)."""
        lay = self.crease_layer()
        lim = math.radians(angle)
        for e in self.bm.edges:
            if len(e.link_faces) == 2 and e.link_faces[0].normal.angle(e.link_faces[1].normal, 0) > lim:
                e[lay] = value
            elif len(e.link_faces) != 2:
                e[lay] = value
        return self

    def copy(self):
        return Shape(self.bm.copy())

    def join(self, *others):
        """Adds other shapes into this one (they are consumed)."""
        for o in others:
            if o is None:
                continue
            me = bpy.data.meshes.new("_j")
            o.bm.to_mesh(me)
            self.bm.from_mesh(me)
            bpy.data.meshes.remove(me)
            o.bm.free()
        return self

    def set_slot(self, slot):
        for f in self.bm.faces:
            f.material_index = slot_index(slot)
        return self

    def slot_where(self, slot, test):
        """Re-assigns the faces whose centre passes test(center, normal)."""
        for f in self.bm.faces:
            if test(f.calc_center_median(), f.normal):
                f.material_index = slot_index(slot)
        return self

    # -- transforms
    def transform(self, m):
        bmesh.ops.transform(self.bm, matrix=m, verts=self.bm.verts)
        return self

    def move(self, x, y=0.0, z=0.0):
        return self.transform(Matrix.Translation(V(x, y, z)))

    def rotate(self, deg, axis="Z", center=(0, 0, 0)):
        c = V(center)
        return self.transform(Matrix.Translation(c) @ Matrix.Rotation(math.radians(deg), 4, axis)
                              @ Matrix.Translation(-c))

    def scale(self, sx, sy=None, sz=None, center=(0, 0, 0)):
        sy = sx if sy is None else sy
        sz = sx if sz is None else sz
        c = V(center)
        m = Matrix.Diagonal((sx, sy, sz, 1.0))
        return self.transform(Matrix.Translation(c) @ m @ Matrix.Translation(-c))

    def mirror(self, axis="X", at=0.0):
        """Adds a mirrored copy across the plane axis=at."""
        c = self.copy()
        i = "XYZ".index(axis)
        s = [1.0, 1.0, 1.0]
        s[i] = -1.0
        c.transform(Matrix.Translation(V(*[at if k == i else 0 for k in range(3)]))
                    @ Matrix.Diagonal((*s, 1.0)) @ Matrix.Translation(V(*[-at if k == i else 0 for k in range(3)])))
        bmesh.ops.reverse_faces(c.bm, faces=c.bm.faces)
        return self.join(c)

    def deform(self, fn):
        """fn(Vector) -> Vector applied to every vertex (bends, twists, sags...)."""
        for v in self.bm.verts:
            v.co = fn(v.co.copy())
        return self

    def bounds(self):
        if not self.bm.verts:
            return V(0, 0, 0), V(0, 0, 0)
        xs = [v.co for v in self.bm.verts]
        return (Vector((min(c.x for c in xs), min(c.y for c in xs), min(c.z for c in xs))),
                Vector((max(c.x for c in xs), max(c.y for c in xs), max(c.z for c in xs))))

    def tri_count(self):
        return sum(len(f.verts) - 2 for f in self.bm.faces)

    # -- modifiers through a temporary object
    def _object(self):
        me = bpy.data.meshes.new("_s")
        self.bm.to_mesh(me)
        ob = bpy.data.objects.new("_s", me)
        bpy.context.scene.collection.objects.link(ob)
        return ob

    def _take(self, ob):
        dg = bpy.context.evaluated_depsgraph_get()
        ev = ob.evaluated_get(dg)
        m2 = ev.to_mesh()
        bm = bmesh.new()
        bm.from_mesh(m2)
        ev.to_mesh_clear()
        me = ob.data
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        self.bm.free()
        self.bm = bm
        return self

    def smooth(self, levels=2, boundary_smooth="ALL"):
        """Catmull-Clark subdivision (creased edges stay crisp). Turns a cage into an organic surface."""
        if levels <= 0:
            return self
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        ob = self._object()
        mod = ob.modifiers.new("sub", "SUBSURF")
        mod.levels = levels
        mod.render_levels = levels
        mod.quality = 3
        mod.uv_smooth = "NONE"
        mod.boundary_smooth = boundary_smooth
        mod.use_creases = True
        return self._take(ob)

    def solidify(self, thickness, offset=-1.0, rim=True):
        ob = self._object()
        mod = ob.modifiers.new("sol", "SOLIDIFY")
        mod.thickness = thickness
        mod.offset = offset
        mod.use_rim = rim
        mod.use_even_offset = True
        mod.use_quality_normals = True
        return self._take(ob)

    def boolean(self, cutter, op="DIFFERENCE", solver="EXACT"):
        """Boolean with another Shape (consumed). The cutter's faces keep their slots on a UNION;
        on a DIFFERENCE the cut faces take the cutter's slots (useful: the reveal of a window)."""
        ob = self._object()
        co = cutter._object()
        co.hide_viewport = True
        mod = ob.modifiers.new("bool", "BOOLEAN")
        mod.object = co
        mod.operation = op
        mod.solver = solver
        if solver == "EXACT":
            mod.use_self = False
            mod.use_hole_tolerant = True
        # material indices: the meshes must share the same slot list
        for o in (ob, co):
            for s in ALL:
                o.data.materials.append(_slot_material(s))
        mod.material_mode = "TRANSFER"
        self._take(ob)
        me = co.data
        bpy.data.objects.remove(co)
        bpy.data.meshes.remove(me)
        cutter.bm.free()
        return self

    def weld(self, dist=1e-4):
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=dist)
        return self

    def triangulate(self):
        bmesh.ops.triangulate(self.bm, faces=self.bm.faces, quad_method="BEAUTY", ngon_method="BEAUTY")
        return self

    def decimate(self, target):
        """Collapse decimation to about `target` triangles (for LODs)."""
        tris = self.tri_count()
        if tris <= target:
            return self
        ob = self._object()
        mod = ob.modifiers.new("dec", "DECIMATE")
        mod.ratio = max(0.004, target / max(tris, 1))
        mod.use_collapse_triangulate = True
        return self._take(ob)

    def flip(self):
        bmesh.ops.reverse_faces(self.bm, faces=self.bm.faces)
        return self

    def recalc(self):
        bmesh.ops.recalc_face_normals(self.bm, faces=self.bm.faces)
        return self


def _slot_material(slot):
    m = bpy.data.materials.get(slot)
    if m is None:
        m = bpy.data.materials.new(slot)
    return m


def join(*shapes):
    shapes = [s for s in shapes if s is not None]
    if not shapes:
        return Shape()
    return shapes[0].join(*shapes[1:])


# ======================================================================== constructors
def loft(rings, slot, cap0=True, cap1=True, closed=True, cap_slot=None, fan=False):
    """Connects rings of points (all with the same count). closed=False lofts open strips.
    Caps are n-gons (fan=True caps with a centre vertex: better for subdivision)."""
    s = Shape()
    vs = [[s.vert(p) for p in r] for r in rings]
    n = len(rings[0])
    span = n if closed else n - 1
    for a, b in zip(vs[:-1], vs[1:]):
        for i in range(span):
            j = (i + 1) % n
            s.face([a[i], a[j], b[j], b[i]], slot)
    cs = cap_slot or slot
    for ring, rev, on in ((vs[0], True, cap0), (vs[-1], False, cap1)):
        if not on or not closed:
            continue
        r = list(reversed(ring)) if rev else ring
        if fan:
            c = s.vert(sum((v.co for v in ring), Vector()) / len(ring))
            for i in range(n):
                s.face([c, r[i], r[(i + 1) % n]], cs)
        else:
            s.face(r, cs)
    s.recalc()
    return s


def extrude(poly, z0, z1, slot, top_slot=None, bottom_slot=None, cap0=True, cap1=True, closed=True):
    """Straight extrusion of a 2D outline (CCW) between two heights."""
    poly = ccw(poly) if closed else poly
    s = loft([pts3(poly, z0), pts3(poly, z1)], slot, cap0=False, cap1=False, closed=closed)
    if closed:
        if cap0:
            s.face([v for v in s.bm.verts][:len(poly)][::-1], bottom_slot or slot)
        if cap1:
            s.face([v for v in s.bm.verts][len(poly):], top_slot or slot)
    s.recalc()
    return s


def slab(poly, z0, z1, slot, r=0.0, seg=3, top_slot=None, side_slot=None):
    """Plate from a 2D outline with rounded top and bottom edges of radius r (organic floor plates,
    roof canopies, counter tops)."""
    poly = ccw(poly)
    if r <= 1e-5:
        return extrude(poly, z0, z1, side_slot or slot, top_slot=top_slot or slot, bottom_slot=slot)
    r = min(r, (z1 - z0) / 2)
    rings = []
    for k in range(seg + 1):                       # bottom fillet
        a = math.pi / 2 * k / seg
        rings.append(pts3(grow(poly, -r + r * math.sin(a)), z0 + r - r * math.cos(a)))
    for k in range(seg + 1):                       # top fillet
        a = math.pi / 2 * k / seg
        rings.append(pts3(grow(poly, -r + r * math.cos(a)), z1 - r + r * math.sin(a)))
    inner_b = pts3(grow(poly, -r), z0)
    s = loft(rings, side_slot or slot, cap0=False, cap1=False)
    n = len(poly)
    allv = list(s.bm.verts)
    s.face(allv[:n][::-1], slot)
    s.face(allv[-n:], top_slot or slot)
    del inner_b
    s.recalc()
    return s


def lathe(profile, slot, n=32, a0=0.0, a1=2 * math.pi, center=(0, 0, 0), slots=None):
    """Revolves a profile [(r, z), ...] around Z. r == 0 points become poles.
    slots: optional list with a slot per profile span (len(profile) - 1)."""
    full = abs((a1 - a0) - 2 * math.pi) < 1e-6
    steps = n if full else n + 1
    c = V(center)
    s = Shape()
    rows = []
    for r, z in profile:
        if r < 1e-6:
            rows.append([s.vert(c + V(0, 0, z))])
        else:
            rows.append([s.vert(c + V(r * math.cos(a0 + (a1 - a0) * i / n), r * math.sin(a0 + (a1 - a0) * i / n), z))
                         for i in range(steps)])
    span = n if full else n
    for k, (a, b) in enumerate(zip(rows[:-1], rows[1:])):
        sl = slots[k] if slots else slot
        for i in range(span):
            j = (i + 1) % steps if full else i + 1
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                s.face([a[0], b[j], b[i]], sl)
            elif len(b) == 1:
                s.face([a[i], a[j], b[0]], sl)
            else:
                s.face([a[i], a[j], b[j], b[i]], sl)
    s.recalc()
    return s


def _frames(path, closed):
    """Parallel-transport frames along a 3D path: (tangent, normal, binormal) per point."""
    n = len(path)
    tans = []
    for i in range(n):
        if closed:
            t = path[(i + 1) % n] - path[i - 1]
        else:
            t = path[min(i + 1, n - 1)] - path[max(i - 1, 0)]
        tans.append(t.normalized() if t.length > 1e-9 else Vector((0, 0, 1)))
    up = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(up).normalized()
    out = []
    for i in range(n):
        if i > 0:
            axis = tans[i - 1].cross(tans[i])
            if axis.length > 1e-9:
                ang = tans[i - 1].angle(tans[i], 0.0)
                nrm = Matrix.Rotation(ang, 3, axis.normalized()) @ nrm
        nrm = (nrm - tans[i] * nrm.dot(tans[i])).normalized()
        out.append((tans[i], nrm, tans[i].cross(nrm)))
    return out


def sweep(path, radius, slot, n=12, closed=False, caps=True, profile=None, twist=0.0, fan=True):
    """Tube (or any closed profile [(x, y)...]) swept along a 3D path. radius: number, list per
    point, or function of t in [0, 1]."""
    path = [V(p) for p in path]
    fr = _frames(path, closed)
    m = len(path)
    if profile is None:
        profile = [(math.cos(2 * math.pi * i / n), math.sin(2 * math.pi * i / n)) for i in range(n)]
    rings = []
    for i, (p, (t, nn, b)) in enumerate(zip(path, fr)):
        u = i / max(m - 1, 1)
        r = radius(u) if callable(radius) else (radius[i] if isinstance(radius, (list, tuple)) else radius)
        a = twist * u
        ca, sa = math.cos(a), math.sin(a)
        rings.append([p + (nn * (x * ca - y * sa) + b * (x * sa + y * ca)) * r for x, y in profile])
    if closed:
        rings.append(rings[0])
        s = loft(rings, slot, cap0=False, cap1=False)
        s.weld(1e-5)
        return s
    return loft(rings, slot, cap0=caps, cap1=caps, fan=fan)


def box_cage(mn, mx, slot):
    """8-vertex box (as a cage for bevel/smooth); never uploaded as a 'box'."""
    mn, mx = V(mn), V(mx)
    poly = [(mn.x, mn.y), (mx.x, mn.y), (mx.x, mx.y), (mn.x, mx.y)]
    return extrude(poly, mn.z, mx.z, slot)


def rounded_box(mn, mx, slot, r=0.05, seg=3, profile=0.5):
    """Box with all edges rounded to radius r (furniture bodies, plinths, cushions with seg>=4)."""
    s = box_cage(mn, mx, slot)
    size = V(mx) - V(mn)
    r = min(r, min(size) / 2 - 1e-4)
    if r > 1e-5:
        bmesh.ops.bevel(s.bm, geom=list(s.bm.edges), offset=r, offset_type="OFFSET", segments=seg,
                        profile=profile, affect="EDGES", clamp_overlap=True)
    s.recalc()
    return s


def cushion(mn, mx, slot, r=0.06, crown=0.012, seg=4, pinch=0.35):
    """Upholstered cushion: rounded box with a crowned top and bottom and a pinched welt line
    around the middle (subdivided cage, so it reads soft and tailored)."""
    mn, mx = V(mn), V(mx)
    size = mx - mn
    c = (mn + mx) / 2
    s = rounded_box(mn, mx, slot, r=min(r, size.z * 0.48), seg=seg)
    hz = size.z / 2
    for v in s.bm.verts:
        dz = (v.co.z - c.z) / max(hz, 1e-6)
        fx = 1 - min(abs(v.co.x - c.x) / (size.x / 2), 1) ** 2
        fy = 1 - min(abs(v.co.y - c.y) / (size.y / 2), 1) ** 2
        v.co.z += crown * fx * fy * (1 if dz > 0 else -1) * abs(dz)
        if abs(dz) < 0.25:                      # the welt: sides pulled in a hair at mid height
            k = (1 - abs(dz) / 0.25) * pinch * 0.01
            v.co.x -= (v.co.x - c.x) * k / max(size.x, 0.1)
            v.co.y -= (v.co.y - c.y) * k / max(size.y, 0.1)
    return s


def wall_band(line, thickness, z0, z1, slot, closed=False, end_slot=None, top_slot=None):
    """Curved wall of constant thickness along a 2D centre line (open or closed)."""
    a = offset2d(line, thickness / 2, closed)
    b = offset2d(line, -thickness / 2, closed)
    s = Shape()
    n = len(line)
    A0 = [s.vert((p[0], p[1], z0)) for p in a]
    A1 = [s.vert((p[0], p[1], z1)) for p in a]
    B0 = [s.vert((p[0], p[1], z0)) for p in b]
    B1 = [s.vert((p[0], p[1], z1)) for p in b]
    span = n if closed else n - 1
    for i in range(span):
        j = (i + 1) % n
        s.face([B0[i], B0[j], B1[j], B1[i]], slot)        # right side
        s.face([A0[j], A0[i], A1[i], A1[j]], slot)        # left side
        s.face([A1[i], B1[i], B1[j], A1[j]], top_slot or slot)
        s.face([A0[j], B0[j], B0[i], A0[i]], slot)
    if not closed:
        s.face([A0[0], B0[0], B1[0], A1[0]], end_slot or slot)
        s.face([B0[-1], A0[-1], A1[-1], B1[-1]], end_slot or slot)
    s.recalc()
    return s


def shell(outline, z0, height, slot, rings=8, power=2.0, thickness=0.18, inner_slot=None, open_top=0.0):
    """Organic dome/canopy: the outline (any CCW shape) rises and closes along a superellipse
    quarter (power 2 = round, higher = flatter top and steeper sides). open_top: 0-1 fraction of
    the rise left open as an oculus. thickness > 0 makes a solid shell; inner_slot paints the
    inside (the faces that look back towards the centre of the base)."""
    poly = ccw(outline)
    cx = sum(p[0] for p in poly) / len(poly)
    cy = sum(p[1] for p in poly) / len(poly)
    last = 1.0 - open_top
    rings_pts = []
    for k in range(rings + 1):
        u = (k / rings) * last * (math.pi / 2)
        z = z0 + height * math.sin(u) ** (2 / power)
        sc = max(math.cos(u) ** (2 / power), 1e-3)
        rings_pts.append([Vector((cx + (p[0] - cx) * sc, cy + (p[1] - cy) * sc, z)) for p in poly])
    s = loft(rings_pts, slot, cap0=False, cap1=open_top <= 0, fan=True)
    if thickness > 0:
        s.solidify(thickness, offset=-1.0, rim=True)
        if inner_slot:
            c = Vector((cx, cy, z0))
            s.slot_where(inner_slot, lambda f, n: n.dot(f - c) < 0)
    return s


def bezier3(p0, p1, p2, p3, n):
    p0, p1, p2, p3 = V(p0), V(p1), V(p2), V(p3)
    out = []
    for i in range(n):
        t = i / (n - 1)
        out.append(p0 * (1 - t) ** 3 + p1 * 3 * (1 - t) ** 2 * t + p2 * 3 * (1 - t) * t ** 2 + p3 * t ** 3)
    return out


def blob(center, rx, ry, rz, slot, nu=16, nv=10, e=2.0, flat=None):
    """Superellipsoid (pebbles, poufs, sculptural boulders). flat: z below which it is flattened."""
    c = V(center)
    prof = []
    for j in range(nv + 1):
        t = -math.pi / 2 + math.pi * j / nv
        ct, st = math.cos(t), math.sin(t)
        r = abs(ct) ** (2 / e)
        z = math.copysign(abs(st) ** (2 / e), st)
        prof.append((r, z))
    s = Shape()
    rows = []
    for r, z in prof:
        if r < 1e-6:
            rows.append([s.vert(c + V(0, 0, z * rz))])
            continue
        row = []
        for i in range(nu):
            a = 2 * math.pi * i / nu
            ca, sa = math.cos(a), math.sin(a)
            x = math.copysign(abs(ca) ** (2 / e), ca) * r * rx
            y = math.copysign(abs(sa) ** (2 / e), sa) * r * ry
            zz = z * rz
            if flat is not None:
                zz = max(zz, flat - c.z)
            row.append(s.vert(c + V(x, y, zz)))
        rows.append(row)
    for a, b in zip(rows[:-1], rows[1:]):
        for i in range(nu):
            j = (i + 1) % nu
            if len(a) == 1:
                s.face([a[0], b[j], b[i]], slot)
            elif len(b) == 1:
                s.face([a[i], a[j], b[0]], slot)
            else:
                s.face([a[i], a[j], b[j], b[i]], slot)
    s.recalc()
    s.weld(1e-5)
    return s


def panel(poly, z, slot, up=True):
    """Single-sided flat face from a 2D outline at height z (glass sheets, light diffusers)."""
    s = Shape()
    vs = [s.vert((p[0], p[1], z)) for p in (ccw(poly) if up else list(reversed(ccw(poly))))]
    s.face(vs, slot)
    return s


def vpanel(line, z0, z1, slot, two_sided=True, closed=False):
    """Vertical sheet following a 2D line (glass walls, curtains): optionally both sides."""
    s = Shape()
    a = [s.vert((p[0], p[1], z0)) for p in line]
    b = [s.vert((p[0], p[1], z1)) for p in line]
    n = len(line)
    for i in range(n if closed else n - 1):
        j = (i + 1) % n
        s.face([a[i], a[j], b[j], b[i]], slot)
        if two_sided:
            s.face([a[j], a[i], b[i], b[j]], slot)
    return s


def curtain(line, z0, z1, slot, folds=None, depth=0.06, rows=6, two_sided=True):
    """Pleated curtain hanging along a 2D line: sinusoidal folds that relax towards the floor."""
    pts = resample(line, max(8, len(line)), closed=False)
    tot = sum(math.dist(pts[i], pts[i + 1]) for i in range(len(pts) - 1))
    folds = folds or max(2, int(tot / 0.14))
    n = folds * 4 + 1
    pts = resample(line, n, closed=False)
    s = Shape()
    grid = []
    for r in range(rows + 1):
        z = z1 - (z1 - z0) * r / rows
        row = []
        for i, p in enumerate(pts):
            a = Vector((pts[min(i + 1, n - 1)][0] - pts[max(i - 1, 0)][0],
                        pts[min(i + 1, n - 1)][1] - pts[max(i - 1, 0)][1])).normalized()
            nrm = Vector((-a.y, a.x))
            amp = depth * (0.55 + 0.45 * r / rows)
            off = math.sin(i / 4 * 2 * math.pi) * amp
            row.append(s.vert((p[0] + nrm.x * off, p[1] + nrm.y * off, z)))
        grid.append(row)
    for a, b in zip(grid[:-1], grid[1:]):
        for i in range(n - 1):
            s.face([b[i], b[i + 1], a[i + 1], a[i]], slot)
            if two_sided:
                s.face([a[i], a[i + 1], b[i + 1], b[i]], slot)
    return s


# ======================================================================== UVs and objects
def uv_box(me, origin=Vector(), tiles=None, rotate_wood=True):
    """World-space box mapping per face (tileable textures match across pieces), metres per repeat
    from UV_TILE. Wood grain runs along the longest direction of each face."""
    tiles = tiles or UV_TILE
    mats = [m.name if m else "a_plaster" for m in me.materials]
    uvl = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        slot = mats[p.material_index] if p.material_index < len(mats) else "a_plaster"
        s = tiles.get(slot, 1.0)
        n = p.normal
        ax = max(range(3), key=lambda i: abs(n[i]))
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co + origin
            if ax == 0:
                u, v = (co.y if n.x > 0 else -co.y), co.z
            elif ax == 1:
                u, v = (-co.x if n.y > 0 else co.x), co.z
            else:
                u, v = co.x, (co.y if n.z > 0 else -co.y)
            uvl.data[li].uv = (u / s, v / s)
    return uvl


def sharp_by_angle(me):
    mats = [m.name if m else "a_plaster" for m in me.materials]
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
        ma, mb = mats[a.material_index], mats[b.material_index]
        if ma != mb:
            sharp[i] = True
            continue
        sharp[i] = math.degrees(a.normal.angle(b.normal, 0.0)) > SMOOTH_ANGLE.get(ma, 35)
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    attr.data.foreach_set("value", sharp)
    for p in me.polygons:
        p.use_smooth = True

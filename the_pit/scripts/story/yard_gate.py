"""Story details: yard_gate (see story/__init__.py for the rules).

The yard (P*, T*, M* pieces), the gate (G_*) and the guardroom (V_*): the first things a prisoner
sees. Everything here is HIGH-LOD detail (a couple of silhouettes in MEDIUM) and stays inside each
piece's bounding box (every decorator clamps its new vertices to the box the piece already had).

Writing is drawn with a small stroke font (FONT): dark (Iron) strokes read as cuts, tar or ink,
light (Bone) strokes as chalk or salt. Walls with no slack get a real recess (cut_recess).
"""

import math

from mathutils import Matrix, Vector

from geo import Frame, newell, rng, rot_z
from pieces import FL, NX, PT, YP, wall_anchor

from . import decorates

V = Vector
UP = V((0, 0, 1))
CW = 0.22            # half-width of the yard channel
LIP = CW + 0.007     # side face of the flagstones along the channel
GUTTER = FL - 0.03   # bottom of the channel as built (top of the paving base)
YCELL = [(YP[k] + YP[k + 1]) / 2 for k in range(4)]


# ================================================================== helpers
def kept(*names):
    """Like @decorates, but every vertex the decorator adds is clamped to the piece's existing box."""
    def wrap(fn):
        def run(g, lod):
            if not g.verts:
                return fn(g, lod)
            mn, mx = g.bounds()
            n0 = len(g.verts)
            fn(g, lod)
            for v in g.verts[n0:]:
                v.x = min(max(v.x, mn.x), mx.x)
                v.y = min(max(v.y, mn.y), mx.y)
                v.z = min(max(v.z, mn.z), mx.z)
        run.__name__ = fn.__name__
        decorates(*names)(run)
        return fn
    return wrap


def wall_frame(o, n):
    """Frame on a wall: u reads left to right for a viewer facing the wall, v is up, n points out."""
    n = V(n).normalized()
    return Frame(V(o), UP.cross(n).normalized(), UP, n)


def floor_frame(x, y, ang=0.0):
    """Frame on the floor at z = 0 (depth = absolute height)."""
    u = V((math.cos(ang), math.sin(ang), 0))
    return Frame(V((x, y, 0)), u, V((-u.y, u.x, 0)), UP)


def poly(g, fr, pts, d, mat):
    g.face([fr.p(a, b, d) for a, b in pts], mat, fr.n)


def seg(g, fr, a, b, w, d, mat):
    """A stroke (thin quad) from a to b (frame coordinates) at depth d."""
    a, b = V(a), V(b)
    t = b - a
    if t.length < 1e-6:
        t = V((1, 0))
        b = a + t * (w * 0.2)
    t.normalize()
    nn = V((-t.y, t.x)) * (w / 2)
    a2, b2 = a - t * (w * 0.35), b + t * (w * 0.35)
    poly(g, fr, [a2 - nn, b2 - nn, b2 + nn, a2 + nn], d, mat)


FONT = {
    "A": [[(0, 0), (0, 3), (1, 4), (2, 3), (2, 0)], [(0, 2), (2, 2)]],
    "B": [[(0, 0), (0, 4), (1.5, 4), (2, 3.5), (2, 2.5), (1.5, 2), (0, 2)],
          [(1.5, 2), (2, 1.5), (2, 0.5), (1.5, 0), (0, 0)]],
    "C": [[(2, 4), (0.5, 4), (0, 3.5), (0, 0.5), (0.5, 0), (2, 0)]],
    "D": [[(0, 0), (0, 4), (1.2, 4), (2, 3), (2, 1), (1.2, 0), (0, 0)]],
    "E": [[(2, 4), (0, 4), (0, 0), (2, 0)], [(0, 2), (1.5, 2)]],
    "F": [[(2, 4), (0, 4), (0, 0)], [(0, 2), (1.5, 2)]],
    "G": [[(2, 3.5), (1.5, 4), (0.5, 4), (0, 3.5), (0, 0.5), (0.5, 0), (1.5, 0), (2, 0.5), (2, 2), (1, 2)]],
    "H": [[(0, 0), (0, 4)], [(2, 0), (2, 4)], [(0, 2), (2, 2)]],
    "I": [[(1, 0), (1, 4)], [(0.4, 4), (1.6, 4)], [(0.4, 0), (1.6, 0)]],
    "J": [[(2, 4), (2, 0.5), (1.5, 0), (0.5, 0), (0, 0.5)]],
    "K": [[(0, 0), (0, 4)], [(2, 4), (0, 1.5)], [(0.7, 2.3), (2, 0)]],
    "L": [[(0, 4), (0, 0), (2, 0)]],
    "M": [[(0, 0), (0, 4), (1, 2), (2, 4), (2, 0)]],
    "N": [[(0, 0), (0, 4), (2, 0), (2, 4)]],
    "O": [[(0.5, 0), (0, 0.5), (0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 0.5), (1.5, 0), (0.5, 0)]],
    "P": [[(0, 0), (0, 4), (1.5, 4), (2, 3.5), (2, 2.5), (1.5, 2), (0, 2)]],
    "R": [[(0, 0), (0, 4), (1.5, 4), (2, 3.5), (2, 2.5), (1.5, 2), (0, 2)], [(1, 2), (2, 0)]],
    "S": [[(2, 3.5), (1.5, 4), (0.5, 4), (0, 3.5), (0, 2.5), (0.5, 2), (1.5, 2), (2, 1.5), (2, 0.5), (1.5, 0),
           (0.5, 0), (0, 0.5)]],
    "T": [[(0, 4), (2, 4)], [(1, 4), (1, 0)]],
    "U": [[(0, 4), (0, 0.5), (0.5, 0), (1.5, 0), (2, 0.5), (2, 4)]],
    "V": [[(0, 4), (1, 0), (2, 4)]],
    "W": [[(0, 4), (0.5, 0), (1, 2), (1.5, 0), (2, 4)]],
    "X": [[(0, 0), (2, 4)], [(0, 4), (2, 0)]],
    "Y": [[(0, 4), (1, 2), (2, 4)], [(1, 2), (1, 0)]],
    "Z": [[(0, 4), (2, 4), (0, 0), (2, 0)]],
    "0": [[(0.5, 0), (0, 0.5), (0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 0.5), (1.5, 0), (0.5, 0)]],
    "1": [[(0.5, 3), (1, 4), (1, 0)], [(0.4, 0), (1.6, 0)]],
    "2": [[(0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 2.5), (0, 0), (2, 0)]],
    "3": [[(0, 4), (2, 4), (1, 2.3), (1.5, 2.3), (2, 1.7), (2, 0.5), (1.5, 0), (0.5, 0), (0, 0.5)]],
    "4": [[(1.5, 0), (1.5, 4), (0, 1.2), (2, 1.2)]],
    "5": [[(2, 4), (0, 4), (0, 2.2), (1.5, 2.2), (2, 1.7), (2, 0.5), (1.5, 0), (0, 0)]],
    "6": [[(1.8, 4), (0.8, 4), (0, 3), (0, 0.5), (0.5, 0), (1.5, 0), (2, 0.5), (2, 1.7), (1.5, 2.2), (0, 2.2)]],
    "7": [[(0, 4), (2, 4), (0.6, 0)]],
    "8": [[(0.5, 2), (0, 2.5), (0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 2.5), (1.5, 2), (0.5, 2), (0, 1.5),
           (0, 0.5), (0.5, 0), (1.5, 0), (2, 0.5), (2, 1.5), (1.5, 2)]],
    "9": [[(2, 1.8), (0.5, 1.8), (0, 2.3), (0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 1), (1.2, 0), (0.2, 0)]],
    ".": [[(0.85, 0), (1.15, 0)]],
    ",": [[(1.1, 0.2), (0.8, -0.6)]],
    "-": [[(0.4, 2), (1.6, 2)]],
    ":": [[(0.85, 0.6), (1.15, 0.6)], [(0.85, 2.6), (1.15, 2.6)]],
    "?": [[(0, 3.5), (0.5, 4), (1.5, 4), (2, 3.5), (2, 2.7), (1, 2), (1, 1.2)], [(0.85, 0.1), (1.15, 0.1)]],
    "'": [[(1, 4), (1, 3.1)]],
    "/": [[(0, 0), (2, 4)]],
    "+": [[(1, 1), (1, 3)], [(0, 2), (2, 2)]],
    "|": [[(1, -0.2), (1, 4.2)]],
}
FONT["Q"] = FONT["O"] + [[(1.2, 0.8), (2.1, -0.3)]]


def text_width(s, h, adv=0.75):
    return max(len(s) * adv * h - 0.25 * h, 0.0)


def write(g, fr, s, u0, v0, h, d, mat, w=None, adv=0.75, rnd=None, jit=0.0, align="l", dfun=None):
    """Suggests writing (the bible: 'the mesh only has to suggest writing'): one short dash per
    character, drawn at a slight random tilt so a line of text reads as a line of ink or chalk."""
    k = h / 4.0
    w = h * 0.14 if w is None else w
    if align == "c":
        u0 -= text_width(s, h, adv) / 2
    for i, ch in enumerate(s.upper()):
        if ch == " ":
            continue
        x0 = u0 + i * adv * h
        dd = d if dfun is None else dfun(x0 + h * 0.25, v0 + h * 0.5)
        # one dash per character; jitter its length and height so the row looks hand-written
        tilt = 0.0 if rnd is None else rnd.uniform(-jit * 0.4, jit * 0.4)
        y0 = v0 + h * 0.4 + (0 if rnd is None else rnd.uniform(-jit, jit) * k)
        xa, xb = x0 + 0.1 * h, x0 + (adv - 0.15) * h
        seg(g, fr, (xa, y0 - tilt * h), (xb, y0 + tilt * h), w, dd, mat)


def lines(g, fr, rows, u0, v0, h, d, mat, gap=1.5, **kw):
    """Several lines of text, top line at v0, going down."""
    for i, s in enumerate(rows):
        write(g, fr, s, u0, v0 - i * h * gap, h, d, mat, **kw)


def ribbon(g, pts, side, w, mat, sides=2):
    """Strip of cloth/leather along `pts` (world), `side` gives its width direction. Two-sided."""
    pts = [V(p) for p in pts]
    side = V(side).normalized() * (w / 2)
    for a, b in zip(pts, pts[1:]):
        q = [a - side, b - side, b + side, a + side]
        nrm = (b - a).cross(side)
        g.face(q, mat, nrm)
        if sides == 2:
            g.face(q, mat, -nrm)


def cut_recess(g, axis, val, sgn, a0, a1, b0, b1, depth, wall_mat=None, bot_mat=None):
    """Cuts a rectangular recess into the axis-aligned rectangular face lying in the plane
    coordinate[axis] = val whose normal points to `sgn` along that axis. (a0, a1) and (b0, b1) are
    ranges along the other two axes, in increasing axis order. Returns False if no face fits."""
    ia, ib = [i for i in range(3) if i != axis]
    for idx, (f, m) in enumerate(zip(g.faces, g.mats)):
        if len(f) != 4:
            continue
        pts = [g.verts[i] for i in f]
        if any(abs(p[axis] - val) > 1e-4 for p in pts):
            continue
        nrm = newell(pts)
        if nrm[axis] * sgn <= 0:
            continue
        A0, A1 = min(p[ia] for p in pts), max(p[ia] for p in pts)
        B0, B1 = min(p[ib] for p in pts), max(p[ib] for p in pts)
        if abs(nrm.length / 2 - (A1 - A0) * (B1 - B0)) > 1e-5:
            continue
        if not (A0 < a0 and a1 < A1 and B0 < b0 and b1 < B1):
            continue
        g.faces.pop(idx)
        g.mats.pop(idx)

        def P(a, b, c):
            v = [0.0, 0.0, 0.0]
            v[ia], v[ib], v[axis] = a, b, c
            return V(v)

        out = [0.0, 0.0, 0.0]
        out[axis] = sgn
        for (x0, x1, y0, y1) in ((A0, a0, B0, B1), (a1, A1, B0, B1), (a0, a1, B0, b0), (a0, a1, b1, B1)):
            g.face([P(x0, y0, val), P(x1, y0, val), P(x1, y1, val), P(x0, y1, val)], m, out)
        vb = val - sgn * depth
        g.face([P(a0, b0, vb), P(a1, b0, vb), P(a1, b1, vb), P(a0, b1, vb)], bot_mat or m, out)
        wm = wall_mat or m
        for (p, q, o) in (((a0, b0), (a0, b1), (1, 0)), ((a1, b0), (a1, b1), (-1, 0)),
                          ((a0, b0), (a1, b0), (0, 1)), ((a0, b1), (a1, b1), (0, -1))):
            oo = [0.0, 0.0, 0.0]
            oo[ia], oo[ib] = o
            g.face([P(p[0], p[1], val), P(q[0], q[1], val), P(q[0], q[1], vb), P(p[0], p[1], vb)], wm, oo)
        return True
    return False


class Tops:
    """Heights of the upward horizontal faces of a floor (to lay flat details on uneven flagstones)."""

    def __init__(self, g, mats=("Floor", "Stone")):
        self.r = []
        for f, m in zip(g.faces, g.mats):
            if m not in mats or len(f) < 3:
                continue
            pts = [g.verts[i] for i in f]
            z = pts[0].z
            if any(abs(p.z - z) > 1e-5 for p in pts) or newell(pts).z <= 0:
                continue
            self.r.append((min(p.x for p in pts), max(p.x for p in pts), min(p.y for p in pts),
                           max(p.y for p in pts), z))

    def at(self, x, y):
        best = None
        for x0, x1, y0, y1, z in self.r:
            if x0 <= x <= x1 and y0 <= y <= y1 and (best is None or z > best):
                best = z
        return best

    def over(self, pts, default=FL):
        zs = [self.at(p[0], p[1]) for p in pts]
        zs = [z for z in zs if z is not None]
        return max(zs) if zs else default


def fdecal(g, tops, pts, mat, lift=0.0007, cap=0.43):
    """Flat stain/groove on the floor: polygon (world x, y) laid just over the local flagstones."""
    cx = sum(p[0] for p in pts) / len(pts)
    cy = sum(p[1] for p in pts) / len(pts)
    z = min(cap, tops.over(list(pts) + [(cx, cy)]) + lift)
    g.face([V((x, y, z)) for x, y in pts], mat, UP)


def fseg(g, tops, a, b, w, mat, lift=0.0007, cap=0.43, step=0.25):
    """Floor stroke from a to b, cut in short pieces that each follow the flagstone under them."""
    a, b = V((a[0], a[1])), V((b[0], b[1]))
    n = max(1, int((b - a).length / step + 0.999))
    t = (b - a).normalized()
    nn = V((-t.y, t.x)) * (w / 2)
    for i in range(n):
        p, q = a.lerp(b, i / n), a.lerp(b, (i + 1) / n)
        fdecal(g, tops, [p - nn, q - nn, q + nn, p + nn], mat, lift, cap)


def blotch(cx, cy, r, rnd, n=8, squash=1.0, ang=0.0):
    """Convex-ish irregular polygon (stain), world xy."""
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n
        rr = r * rnd.uniform(0.75, 1.0)
        x, y = math.cos(a) * rr, math.sin(a) * rr * squash
        out.append((cx + x * math.cos(ang) - y * math.sin(ang), cy + x * math.sin(ang) + y * math.cos(ang)))
    return out


def ftext(g, tops, s, x, y, h, mat, ang=0.0, align="l", cap=0.43, **kw):
    fr = floor_frame(x, y, ang)
    write(g, fr, s, 0.0, 0.0, h, 0.0, mat, align=align,
          dfun=lambda a, b: min(cap, tops.over([tuple(fr.p(a + da, b + db, 0))[:2]
                                                  for da in (-h * 0.4, h * 0.4) for db in (-h * 0.5, h * 0.5)])
                                + 0.0007), **kw)


# ------------------------------------------------------------------ small props
def crab(g, p, ang, rnd, mat="Wood", empty=False):
    """Dead shore crab (or an empty, bleached half-shell) lying on the stone."""
    p = V(p)
    R = rot_z(ang)
    if empty:
        g.blob(p + V((0, 0, 0.014)), 0.034, 0.027, -0.013, 6, 1, mat, rnd, 0.08, flat_bottom=False, rot=R)
        return
    g.blob(p, 0.034, 0.027, 0.013, 6, 2, mat, rnd, 0.08, rot=R)
    for sd in (-1, 1):
        for k, yo in enumerate((-0.012, 0.012)):
            a0 = p + R @ V((sd * 0.026, yo, 0.006))
            a1 = p + R @ V((sd * 0.06, yo * 2.0, 0.002))
            g.sweep([a0, a1], 0.0035, 3, mat)
        c0 = p + R @ V((sd * 0.015, 0.024, 0.007))
        c1 = p + R @ V((sd * 0.03, 0.05, 0.008))
        g.sweep([c0, c1], 0.005, 3, mat)


def gull_bones(g, p, ang, rnd):
    """What the rats left of a gull: skull and beak, two wing bones, one feather."""
    p = V(p)
    R = rot_z(ang)
    L = lambda x, y, z: p + R @ V((x, y, z))
    g.blob(L(0, 0, 0.0), 0.016, 0.022, 0.014, 5, 1, "Bone", rnd, 0.06, rot=R)
    g.cyl(L(0, 0.018, 0.006), L(0.004, 0.075, 0.004), 0.006, 3, "Bone", caps=(False, True), r1=0.001)
    for (x0, y0, x1, y1) in ((0.05, -0.02, 0.2, -0.03), (0.06, 0.03, 0.19, 0.05)):
        g.cyl(L(x0, y0, 0.004), L(x1, y1, 0.004), 0.004, 3, "Bone")
    c = p + R @ V((0.15, 0.1, 0.002))
    t = V((math.cos(ang + 0.3), math.sin(ang + 0.3), 0))
    s = V((-t.y, t.x, 0))
    g.face([c - t * 0.06, c + s * 0.012, c + t * 0.06, c - s * 0.012], "Bone", UP)


def nail(g, p, n, r=0.006):
    p, n = V(p), V(n)
    g.cyl(p, p + n * 0.008, r, 5, "Iron", caps=(False, True), r1=r * 0.8)


def sheet(g, fr, u0, v0, u1, v1, d, mat="Cloth", ang=0.0, torn=None, rnd=None):
    """Paper/parchment rectangle on a wall frame (optionally rotated and with a torn corner)."""
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    ca, sa = math.cos(ang), math.sin(ang)
    pts = [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]
    if torn is not None:  # replace one corner by a ragged edge
        i = torn
        a, b = pts[i], pts[(i - 1) % 4]
        c = pts[(i + 1) % 4]
        k1, k2 = rnd.uniform(0.25, 0.45), rnd.uniform(0.25, 0.45)
        pa = (a[0] + (b[0] - a[0]) * k1, a[1] + (b[1] - a[1]) * k1)
        pc = (a[0] + (c[0] - a[0]) * k2, a[1] + (c[1] - a[1]) * k2)
        mid = ((pa[0] + pc[0]) / 2 + (a[0] - (pa[0] + pc[0]) / 2) * 0.25,
               (pa[1] + pc[1]) / 2 + (a[1] - (pa[1] + pc[1]) / 2) * 0.25)
        pts = pts[:i] + [pa, mid, pc] + pts[i + 1:]
        # keep a convex outline order: rebuild as a fan from the centre
    rot = [(cu + (a - cu) * ca - (b - cv) * sa, cv + (a - cu) * sa + (b - cv) * ca) for a, b in pts]
    for k in range(len(rot)):  # fan (handles the torn notch)
        poly(g, fr, [(cu, cv), rot[k], rot[(k + 1) % len(rot)]], d, mat)
    return rot


def rot2(cu, cv, ang):
    ca, sa = math.cos(ang), math.sin(ang)
    return lambda a, b: (cu + (a - cu) * ca - (b - cv) * sa, cv + (a - cu) * sa + (b - cv) * ca)


# ================================================================== the yard floor
def gutter_ring(g, y, sd):
    """Mooring ring: a staple in the side of the channel, the ring lying in the channel bed."""
    x = sd * LIP
    g.link(V((x - sd * 0.004, y, GUTTER + 0.009)), V((1, 0, 0)), V((0, 1, 0)), 0.016, 0.011, 0.004, 8, 3, "Iron")
    g.link(V((x - sd * 0.072, y, GUTTER + 0.0075)), V((1, 0, 0)), V((0, 1, 0)), 0.056, 0.056, 0.0072, 16, 4,
           "Iron")


def floor_common(g, k, rnd):
    tops = Tops(g)
    y0, y1 = YP[k], YP[k + 1]
    # salt rime: a long white crust on each lip, as one strip
    for sd in (-1, 1):
        xa = sd * (LIP + 0.016)
        fdecal(g, tops, [(xa, y0 + 0.1), (xa + sd * 0.022, y0 + 0.4), (xa + sd * 0.015, y1 - 0.4),
                         (xa, y1 - 0.1)][::sd], "Bone")
    # one tuft of weed on the grate
    gy = YCELL[k]
    p0 = V((rnd.uniform(-0.1, 0.1), gy - 0.3, FL + 0.002))
    g.sweep([p0, p0 + V((0, 0.15, 0.003)), p0 + V((rnd.uniform(-0.05, 0.05), 0.3, 0.001))], 0.004, 3, "Straw")
    return tops


@kept("P1_Floor")
def p1_floor(g, lod):
    if lod:
        return
    r = rng("yard-p1")
    tops = floor_common(g, 0, r)
    # the roll-call line: a groove across the yard near the gate, numbered stations beside it
    for sd in (-1, 1):
        fseg(g, tops, (sd * 0.27, -9.6), (sd * 2.92, -9.6), 0.045, "Iron")
        for i in range(6):
            x = sd * (0.5 + i * 0.45)
            ftext(g, tops, str(i + 1 if sd < 0 else i + 7), x, -9.75, 0.07, "Iron", align="c", rnd=r, jit=0.12)
    # the fallen ledger page, against the base of the first west pier
    ang = 0.35
    fr = floor_frame(-2.73, -11.25, ang)
    base = tops.over([(-2.8, -11.35), (-2.66, -11.15), (-2.73, -11.25)]) + 0.0008
    vs = [-0.105, -0.04, 0.03, 0.075, 0.105]
    zs = [0.0, 0.0, 0.001, 0.008, 0.02]
    for i in range(4):
        q = [fr.p(-0.075, vs[i], base + zs[i]), fr.p(0.075, vs[i], base + zs[i]),
             fr.p(0.075, vs[i + 1], base + zs[i + 1]), fr.p(-0.075, vs[i + 1], base + zs[i + 1])]
        g.face(q, "Cloth", UP)
        if i == 3:
            g.face(q, "Cloth", -UP)
    for i in range(9):  # ruled entries in the Wren's hand: number column and a line of writing
        v = -0.09 + i * 0.016
        if v > 0.03:
            break
        z = base + 0.0006
        seg(g, fr, (-0.065, v), (-0.045, v), 0.003, z, "Iron")
        seg(g, fr, (-0.035, v), (r.uniform(0.01, 0.065), v), 0.0022, z, "Iron")
    seg(g, fr, (-0.04, -0.1), (-0.04, 0.03), 0.0015, base + 0.0006, "Iron")
    # one dead crab and one half-shell at the pier bases, one patch of gull droppings under the nests
    crab(g, V((2.76, -11.25, tops.over([(2.76, -11.25)]))), 2.1, r)
    crab(g, V((-2.78, -10.85, tops.over([(-2.78, -10.85)]))), 0.4, r, mat="Bone", empty=True)
    fdecal(g, tops, blotch(2.05, -11.38, 0.14, r, 6, 0.6), "Bone")
    # under the Governor: the dark drip stain and two toe bones that fell from above
    fdecal(g, tops, blotch(0.8, -6.0, 0.2, r, 8, 0.8, 0.4), "Iron")
    for (x, y, a) in ((0.72, -5.95, 0.3), (0.86, -6.08, 1.9)):
        z = tops.over([(x, y)]) + 0.004
        g.cyl(V((x, y, z)), V((x + 0.03 * math.cos(a), y + 0.03 * math.sin(a), z)), 0.0045, 3, "Bone")
    gutter_ring(g, -7.1, -1)


@kept("P2_Floor")
def p2_floor(g, lod):
    if lod:
        return
    r = rng("yard-p2")
    tops = floor_common(g, 1, r)
    gutter_ring(g, -3.9, 1)
    # side drain grate at the foot of the second west pier
    cx, cy, h = -2.74, -5.3, 0.11
    fdecal(g, tops, [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)], "Iron")
    z = tops.over([(cx - h, cy - h), (cx + h, cy + h), (cx, cy)])
    for i in range(6):
        xx = cx - h + 0.012 + i * (2 * h - 0.024) / 5
        g.box(V((xx - 0.008, cy - h, z)), V((xx + 0.008, cy + h, z + 0.006)), "Iron")
    for sy in (-1, 1):
        g.box(V((cx - h - 0.012, cy + sy * h - 0.012, z)), V((cx + h + 0.012, cy + sy * h + 0.012, z + 0.007)), "Iron")
    fdecal(g, tops, blotch(cx + 0.16, cy + 0.02, 0.07, r, 7, 1.6), "Bone")
    # one tuft of weed from the drain
    p0 = V((cx + 0.03, cy, z + 0.004))
    g.sweep([p0, p0 + V((0.07, 0.0, 0.006)), p0 + V((0.14, 0.0, 0.002))], 0.004, 3, "Straw")
    crab(g, V((2.75, -4.3, tops.over([(2.75, -4.3)]))), 4.0, r, mat="Bone", empty=True)


@kept("P3_Floor")
def p3_floor(g, lod):
    if lod:
        return
    r = rng("yard-p3")
    tops = floor_common(g, 2, r)
    # the thick white rime along the east lip, left by the tide twice a day
    y = 0.15
    while y < 5.6:
        ln = r.uniform(0.3, 0.7)
        ye = min(y + ln, 5.65)
        xa = LIP + 0.019
        w0, w1 = r.uniform(0.03, 0.06), r.uniform(0.03, 0.06)
        fdecal(g, tops, [(xa, y), (xa + w0, y + 0.05), (xa + w1, ye - 0.05), (xa, ye)], "Bone", lift=0.0012)
        y = ye + r.uniform(0.02, 0.12)
    gutter_ring(g, 1.6, -1)
    gull_bones(g, V((-2.68, 4.75, tops.over([(-2.68, 4.75), (-2.5, 4.75)]))), -0.6, r)


@kept("P4_Floor")
def p4_floor(g, lod):
    if lod:
        return
    r = rng("yard-p4")
    tops = floor_common(g, 3, r)
    # two knee hollows before the dais, worn pale and smooth, and the toe scuffs behind them
    for sx in (-0.28, 0.28):
        fdecal(g, tops, blotch(sx, 11.0, 0.11, r, 8, 0.65), "Stone", lift=0.0008)
    gutter_ring(g, 7.4, 1)
    crab(g, V((2.72, 11.25, tops.over([(2.72, 11.25)]))), 0.9, r, mat="Bone", empty=True)


# ================================================================== piers
def pier_face(s, y, z):
    """Frame on the yard face of a pier (x = s * NX), facing the yard."""
    return wall_frame(V((s * NX, y, z)), V((-s, 0, 0)))


def soot(g, fr, rnd, z0, z1, w, d=0.0008):
    """Soot plume above a fire: stacked jittered trapezoids."""
    n = 6
    prev = None
    for i in range(n + 1):
        t = i / n
        hw = w * (0.25 + 0.75 * math.sin(min(1.0, t * 1.3) * math.pi / 2)) * (1 - 0.35 * t * t)
        c = rnd.uniform(-0.03, 0.03) * t
        row = (c - hw, c + hw, z0 + (z1 - z0) * t)
        if prev:
            poly(g, fr, [(prev[0], prev[2]), (prev[1], prev[2]), (row[1], row[2]), (row[0], row[2])], d, "Iron")
        prev = row


def pier_common(g, j, s, rnd):
    ua = YP[j] - 0.975 if j > 0 else YP[0] - PT
    ub = YP[j] + 0.975 if j < 4 else YP[4] + PT
    # soot over the torch
    fr = pier_face(s, YP[j], 0.0)
    soot(g, fr, rnd, 3.05, 4.7, 0.2)
    # high-water line of the Great Flood (Year VII), with salt below it
    ys = sorted((ua + 0.01, ub - 0.01))
    fr0 = pier_face(s, 0.0, 0.0)
    a, b = sorted((fr0.o + fr0.u * 0).y for _ in (0,)), None  # noqa: F841 (frame u is +-y)
    sgn = fr0.u.y
    u0, u1 = ys[0] * sgn, ys[1] * sgn
    u0, u1 = min(u0, u1), max(u0, u1)
    k = 0
    u = u0
    while u < u1 - 0.05:
        un = min(u + rnd.uniform(0.25, 0.5), u1)
        z = 1.02 + rnd.uniform(-0.01, 0.01)
        poly(g, fr0, [(u, z - 0.012), (un, z - 0.012 + rnd.uniform(-0.004, 0.004)), (un, z + 0.006), (u, z + 0.006)],
             0.0008, "Floor")
        poly(g, fr0, [(u, z - 0.05 - rnd.uniform(0, 0.02)), (un, z - 0.05 - rnd.uniform(0, 0.02)), (un, z - 0.014),
                      (u, z - 0.014)], 0.0006, "Bone")
        u = un
        k += 1
    return fr0, sgn


def pier(j, S):
    s = -1 if S == "W" else 1
    name = f"M{j}{S}_Pier"

    @kept(name)
    def fn(g, lod):
        if lod:
            return
        r = rng(f"pier-{name}")
        fr0, sgn = pier_common(g, j, s, r)
        n = V((-s, 0, 0))
        U = lambda y: y * sgn  # world y -> frame u
        if name == "M0W_Pier":
            # the press-gang's red rag tied to an iron staple: fresh meat lines up here
            p = V((-NX, -11.3, 2.0))
            g.link(p + n * 0.018, n, UP, 0.022, 0.014, 0.005, 8, 3, "Iron")
            for k, (dy, ln) in enumerate(((-0.015, 0.26), (0.02, 0.2))):
                ribbon(g, [p + n * (0.02 + 0.003 * k) + V((0, dy, 0)), p + n * (0.03 + 0.004 * k) + V((0, dy * 2, -ln * 0.5)),
                           p + n * (0.025 + 0.005 * k) + V((0, dy * 3, -ln))], V((0, 1, 0)), 0.04, "Cloth")
            write(g, fr0, "VII", U(-11.55) - 0.05, 1.035, 0.035, 0.0012, "Iron", rnd=r, jit=0.1)
        elif name == "M1W_Pier":
            # PRISONERS ANSWER WITH THEIR NUMBER, NOT THEIR NAME, nailed over three older orders
            cu, cv = U(-5.75), 1.7
            for k, (du, dv, ang) in enumerate(((-0.04, 0.03, 0.08), (0.05, -0.02, -0.06), (0.0, 0.06, 0.03))):
                pts = sheet(g, fr0, cu + du - 0.17, cv + dv - 0.22, cu + du + 0.17, cv + dv + 0.22, 0.001 + 0.0012 * k,
                            ang=ang, torn=k % 4, rnd=r)
                for q in pts[:2] + pts[-1:]:
                    pass
                for i in range(6):  # faded lines of the old orders
                    v = cv + dv + 0.12 - i * 0.045
                    seg(g, fr0, (cu + du - 0.12, v), (cu + du + r.uniform(-0.05, 0.12), v), 0.004, 0.0012 * (k + 1) + 0.0004,
                        "Floor")
            sheet(g, fr0, cu - 0.19, cv - 0.25, cu + 0.19, cv + 0.25, 0.0052)
            lines(g, fr0, ["PRISONERS", "ANSWER WITH", "THEIR NUMBER", "NOT THEIR", "NAME"], cu, cv + 0.17, 0.04,
                  0.0062, "Iron", gap=1.55, align="c")
            write(g, fr0, "BY ORDER", cu, cv - 0.2, 0.02, 0.0062, "Iron", align="c")
            for du, dv in ((-0.17, 0.23), (0.17, 0.23), (-0.17, -0.23), (0.17, -0.23), (0.0, 0.24)):
                nail(g, fr0.p(cu + du, cv + dv, 0.005), n)
        elif name == "M2W_Pier":
            # the Purse's notice by the mess line
            cu, cv = U(0.0), 1.65
            sheet(g, fr0, cu - 0.17, cv - 0.2, cu + 0.17, cv + 0.2, 0.001, ang=-0.04, torn=1, rnd=r)
            lines(g, fr0, ["RATIONS", "A DOG EATS", "FROM THE BOWL", "A MAN FROM", "THE SPOON"], cu, cv + 0.12, 0.034,
                  0.0018, "Iron", gap=1.6, align="c")
            write(g, fr0, "THE PURSE", cu + 0.04, cv - 0.18, 0.018, 0.0018, "Iron", align="c")
            for du in (-0.15, 0.15):
                nail(g, fr0.p(cu + du, cv + 0.18, 0.003), n)
        elif name == "M3W_Pier":
            # a Crown proclamation from before the Ebb: the red gull seal, the Lord's hook tarred across
            cu, cv = U(5.75), 1.75
            sheet(g, fr0, cu - 0.2, cv - 0.26, cu + 0.2, cv + 0.26, 0.001, ang=0.05, torn=2, rnd=r)
            lines(g, fr0, ["BY THE KING", "FORT CLEMENCY"], cu, cv + 0.17, 0.03, 0.0018, "Iron", gap=1.6, align="c")
            for i in range(6):
                v = cv + 0.05 - i * 0.04
                seg(g, fr0, (cu - 0.15, v), (cu + r.uniform(0.0, 0.15), v), 0.005, 0.0018, "Floor")
            poly(g, fr0, [(cu + 0.12 + math.cos(a) * 0.04, cv - 0.19 + math.sin(a) * 0.04)
                          for a in [2 * math.pi * i / 8 for i in range(8)]], 0.002, "Wood")
            hook = [(cu + 0.05, cv + 0.25), (cu + 0.05, cv - 0.1), (cu, cv - 0.18), (cu - 0.08, cv - 0.16),
                    (cu - 0.11, cv - 0.07), (cu - 0.07, cv - 0.04)]
            for p_, q_ in zip(hook, hook[1:]):
                seg(g, fr0, p_, q_, 0.035, 0.0026, "Iron")
            for du in (0.02, 0.07):
                seg(g, fr0, (cu + du, cv - 0.12), (cu + du, cv - 0.24 - r.uniform(0, 0.08)), 0.008, 0.0026, "Iron")
            for du in (-0.18, 0.18):
                nail(g, fr0.p(cu + du, cv + 0.24, 0.003), n)
        elif name == "M4W_Pier":
            write(g, fr0, "FLOOD VII", U(11.45) - 0.12, 1.04, 0.04, 0.0012, "Iron", rnd=r, jit=0.1)
            seg(g, fr0, (U(11.45) - 0.14, 1.02), (U(11.45) + 0.24, 1.02), 0.006, 0.0014, "Iron")
        elif name == "M0E_Pier":
            # pegs with the sacking hoods taken off the new men at the gate
            for k, y in enumerate((-11.68, -11.43, -11.18)):
                p = V((NX, y, 1.82 - 0.03 * k))
                g.cyl(p, p + n * 0.06, 0.012, 5, "Wood", caps=(False, True))
                hc = p + n * 0.035 + V((0, 0, -0.17))
                for sz in (1, -1):
                    g.blob(hc, 0.03, 0.09 + 0.01 * k, 0.17 * sz, 7, 2, "Cloth", r, 0.12, flat_bottom=False)
                g.link(p + n * 0.045 + V((0, 0, -0.01)), V((0, 1, 0)), UP, 0.04, 0.02, 0.005, 6, 3, "Straw")
            write(g, fr0, "VII", U(-11.5) - 0.06, 1.035, 0.035, 0.0012, "Iron", rnd=r, jit=0.1)
        elif name == "M1E_Pier":
            # DO NOT LOOK AT THE THRONE, cut low by a man on his knees (Old Fetch, first night)
            cu = U(-5.75)
            write(g, fr0, "DO NOT LOOK", cu - 0.02, 1.13, 0.045, 0.0009, "Iron", rnd=r, jit=0.18, align="c", w=0.007)
            write(g, fr0, "AT THE THRONE", cu + 0.01, 1.06, 0.045, 0.0009, "Iron", rnd=r, jit=0.18, align="c", w=0.007)
        elif name == "M2E_Pier":
            # chalked headcounts, morning and evening: they seldom match
            cu, cv = U(0.0), 1.72
            write(g, fr0, "AM", cu - 0.17, cv, 0.04, 0.0008, "Bone", rnd=r, jit=0.1)
            write(g, fr0, "PM", cu + 0.07, cv, 0.04, 0.0008, "Bone", rnd=r, jit=0.1)
            seg(g, fr0, (cu - 0.22, cv - 0.02), (cu + 0.22, cv - 0.02), 0.006, 0.0008, "Bone")
            seg(g, fr0, (cu, cv + 0.05), (cu, cv - 0.47), 0.006, 0.0008, "Bone")
            am = [41, 40, 40, 39, 41, 38, 37, 39]
            for i, a in enumerate(am):
                b = a + r.choice((-2, -1, 0, 1, 1, 2))
                v = cv - 0.075 - i * 0.05
                write(g, fr0, str(a), cu - 0.16, v, 0.032, 0.0008, "Bone", rnd=r, jit=0.12)
                write(g, fr0, str(b), cu + 0.08, v, 0.032, 0.0008, "Bone", rnd=r, jit=0.12)
                if a != b:
                    seg(g, fr0, (cu + 0.06, v + 0.016), (cu + 0.15, v + 0.016), 0.004, 0.0009, "Bone")
        elif name == "M4E_Pier":
            # the waiting ring: men are tied here to wait their turn to kneel
            wall_anchor(g, V((NX, 11.4, 1.05)), n, UP, 0, plate=0.07, ring_r=0.06, wire=0.012)
            for i in range(9):  # rope burns and wear around the ring
                a = -1.2 + i * 0.3
                seg(g, fr0, (U(11.4) + math.cos(a) * 0.1, 1.0 + math.sin(a) * 0.1),
                    (U(11.4) + math.cos(a) * 0.13, 1.0 + math.sin(a) * 0.13), 0.006, 0.0008, "Bone")
    return fn


for _j in range(5):
    for _S in ("W", "E"):
        pier(_j, _S)


# ================================================================== beams
@kept("T0_Beam")
def t0_beam(g, lod):
    if lod:
        return
    r = rng("t0-nests")
    for x in (1.97, 2.13):
        c = V((x, -11.62, 6.30))
        g.blob(c, 0.065, 0.06, -0.085, 8, 2, "Floor", r, 0.12, flat_bottom=False)
        g.cyl(c + V((0, -0.05, -0.015)), c + V((0, -0.062, -0.012)), 0.018, 6, "Iron", caps=(False, True))
        for i in range(3):
            p0 = c + V((r.uniform(-0.04, 0.04), r.uniform(-0.04, 0.0), -0.06))
            g.sweep([p0, p0 + V((r.uniform(-0.03, 0.03), -0.03, -0.03)), p0 + V((r.uniform(-0.05, 0.05), -0.04, -0.07))],
                    0.003, 3, "Straw")
    fr = wall_frame(V((0, -11.67, 0)), V((0, -1, 0)))
    for i in range(5):  # droppings streaking the south face
        x = 1.95 + r.uniform(-0.1, 0.25)
        seg(g, fr, (x, 6.68), (x + r.uniform(-0.01, 0.01), 6.68 - r.uniform(0.08, 0.25)), 0.012, 0.0008, "Bone")


@kept("T1_Beam")
def t1_beam(g, lod):
    if lod:
        return
    r = rng("t1-notches")
    fr = Frame(V((0, YP[1], 6.30)), V((1, 0, 0)), V((0, -1, 0)), V((0, 0, -1)))
    for i in range(23):  # one notch for every man hanged from this beam since the Ebb
        x = -0.3 + i * 0.045 + (0.02 if i >= 1 else 0)
        ln = r.uniform(0.09, 0.12)
        if i == 0:  # the Governor's: a crossed notch
            seg(g, fr, (x - 0.02, -ln), (x + 0.02, ln), 0.012, 0.0009, "Iron")
            seg(g, fr, (x + 0.02, -ln), (x - 0.02, ln), 0.012, 0.0009, "Iron")
        else:
            seg(g, fr, (x, -ln), (x + r.uniform(-0.008, 0.008), ln), 0.011 if i % 5 else 0.016, 0.0009, "Iron")


@kept("T2_Beam")
def t2_beam(g, lod):
    if lod:
        return
    x0, y0 = -1.0, 0.0
    g.link(V((x0, y0, 6.285)), V((0, 0, 1)), V((0, 1, 0)), 0.03, 0.02, 0.006, 8, 3, "Iron")
    # standing part from the staple down to the hangman's knot
    g.sweep([V((x0, y0, 6.27)), V((x0 + 0.01, y0, 6.18)), V((x0, y0, 6.1))], 0.012, 4, "Straw")
    # the knot: four tight turns
    pts = []
    n_t, per = 4, 5
    for i in range(n_t * per + 1):
        a = 2 * math.pi * i / per
        pts.append(V((x0 + math.cos(a) * 0.026, y0 + math.sin(a) * 0.026, 6.1 - i * (0.16 / (n_t * per)))))
    g.sweep(pts, 0.011, 3, "Straw")
    # the noose itself, lifted short and hung beside the knot
    g.link(V((x0, y0, 5.835)), V((0, 0, 1)), V((1, 0, 0)), 0.1, 0.075, 0.012, 10, 3, "Straw")
    # the spare rope, coiled on the same staple
    g.link(V((x0 + 0.12, y0, 6.18)), V((0, 0, 1)), V((1, 0, 0)), 0.1, 0.09, 0.011, 10, 3, "Straw")
    g.sweep([V((x0, y0, 6.27)), V((x0 + 0.06, y0, 6.285)), V((x0 + 0.12, y0, 6.275))], 0.011, 3, "Straw")


@kept("T3_Beam")
def t3_beam(g, lod):
    if lod:
        return
    r = rng("t3-initials")
    fr = wall_frame(V((0, YP[3] - 0.17, 0)), V((0, -1, 0)))
    sets = ["H.O.", "T.W.", "S.C.", "A.K.", "J.M.", "R.B.", "W.T.", "E.L.", "N.F.", "P.G.", "C.D.", "M.H.", "B.R.",
            "D.S."]
    for i, s in enumerate(sets):
        u = -1.48 + i * 0.215 + r.uniform(-0.02, 0.02)
        write(g, fr, s, u, 6.47 + r.uniform(-0.03, 0.03), 0.06 + r.uniform(-0.008, 0.01), 0.0009, "Iron", rnd=r,
              jit=0.15, w=0.007, adv=0.7)


@kept("T4_Beam")
def t4_beam(g, lod):
    if lod > 1:
        return
    y = YP[4]
    hw = 0.55
    top, low, notch = 6.235, 5.74, 5.98
    if lod == 1:  # MEDIUM: the pennant's silhouette only
        for sd in (-1, 1):
            g.face([V((-hw, y, top)), V((0, y, top)), V((0, y, notch)), V((-hw, y, low))], "Cloth", (0, sd, 0))
            g.face([V((0, y, top)), V((hw, y, top)), V((hw, y, low)), V((0, y, notch))], "Cloth", (0, sd, 0))
        return
    r = rng("t4-pennant")
    for x in (-0.5, 0.5):
        g.cyl(V((x, y, 6.30)), V((x, y, 6.245)), 0.008, 4, "Iron")
    g.cyl(V((-0.6, y, 6.245)), V((0.6, y, 6.245)), 0.01, 5, "Iron")
    for x in (-0.6, 0.6):
        g.cyl(V((x, y, 6.245)), V((x + (0.02 if x > 0 else -0.02), y, 6.245)), 0.014, 5, "Iron", r1=0.0)
    # swallow-tailed cloth, the east tail singed short on the Night of the Ebb
    burnt = [(hw, 5.86), (0.5, 5.81), (0.44, 5.83), (0.39, 5.78)]
    left = [(-hw, top), (0, top), (0, notch), (-hw, low)]
    right = [(0, top), (hw, top)] + burnt + [(0.3, 5.76), (0, notch)]
    for sd in (-1, 1):
        fr = wall_frame(V((0, y + sd * 0.002, 0)), V((0, sd, 0)))
        U = lambda x: x * fr.u.x
        for pts in (left, [(0, top), (hw, top), (hw, 5.86), (0, notch)], [(0, notch), (hw, 5.86)] + burnt[1:] +
                    [(0.3, 5.76)]):
            poly(g, fr, [(U(a), b) for a, b in pts], 0.0, "Cloth")
        for a, b in zip(burnt, burnt[1:] + [(0.3, 5.76)]):
            seg(g, fr, (U(a[0]), a[1] + 0.012), (U(b[0]), b[1] + 0.012), 0.03, 0.0006, "Iron")
        # the Lord's sign: a white hook through a broken crown
        cx, cz = 0.0, 6.1
        d = 0.0008
        poly(g, fr, [(U(cx - 0.09), cz - 0.05), (U(cx + 0.09), cz - 0.05), (U(cx + 0.09), cz - 0.02),
                     (U(cx - 0.09), cz - 0.02)], d, "Bone")
        for k, (px, ph) in enumerate(((-0.075, 0.06), (0.0, 0.08), (0.075, 0.025))):
            poly(g, fr, [(U(cx + px - 0.025), cz - 0.02), (U(cx + px + 0.025), cz - 0.02), (U(cx + px), cz - 0.02 + ph)],
                 d, "Bone")
        seg(g, fr, (U(cx + 0.06), cz - 0.055), (U(cx + 0.045), cz - 0.012), 0.006, d + 0.0004, "Cloth")
        hook = [(cx + 0.03, cz + 0.12), (cx + 0.03, cz - 0.07), (cx + 0.0, cz - 0.11), (cx - 0.045, cz - 0.1),
                (cx - 0.06, cz - 0.06), (cx - 0.03, cz - 0.045)]
        for a, b in zip(hook, hook[1:]):
            seg(g, fr, (U(a[0]), a[1]), (U(b[0]), b[1]), 0.022, d + 0.0002, "Bone")
        seg(g, fr, (U(cx + 0.015), cz + 0.13), (U(cx + 0.045), cz + 0.13), 0.03, d + 0.0002, "Bone")
    del r


# ================================================================== the hanged Governor
@kept("P_Gibbet")
def p_gibbet(g, lod):
    if lod > 1:
        return
    c, s = math.cos(0.4), math.sin(0.4)
    yj = YP[1]

    def GW(x, y, z):
        return V((0.9 + x * c - y * s, yj + x * s + y * c, 3.4 + z))

    if lod == 1:  # MEDIUM: the placard and the coat's outline
        g.box(V((0.66, -5.536, 4.51)), V((0.94, -5.524, 4.72)), "Wood")
        for sd in (-1, 1):
            g.face([GW(-0.2, 0.03, 1.5), GW(0.2, 0.03, 1.5), GW(0.2, 0.03, 1.05), GW(-0.2, 0.03, 1.08)], "Cloth",
                   V((-s, c, 0)) * sd)
        return
    r = rng("governor")
    # placard on a cord round the neck: THE CROWN KEEPS THE YARD
    g.bbox(V((0.655, -5.537, 4.51)), V((0.945, -5.524, 4.725)), "Wood", 0.004)
    fr = wall_frame(V((0.8, -5.524, 0)), V((0, 1, 0)))
    U = lambda x: (x - 0.8) * fr.u.x
    write(g, fr, "THE CROWN", U(0.8), 4.645, 0.028, 0.0007, "Iron", align="c", adv=0.72)
    write(g, fr, "KEEPS THE YARD", U(0.8), 4.585, 0.028, 0.0007, "Iron", align="c", adv=0.68)
    seg(g, fr, (U(0.8) - 0.12, 4.565), (U(0.8) + 0.12, 4.565), 0.003, 0.0007, "Iron")
    for x0, path in ((0.68, [GW(-0.07, -0.01, 1.57), GW(-0.12, 0.08, 1.45)]),
                     (0.92, [GW(0.07, -0.01, 1.57), GW(0.13, 0.1, 1.45)])):
        g.sweep([V((x0, -5.53, 4.72))] + path[::-1], 0.004, 3, "Straw")
    g.sweep([GW(-0.07, -0.01, 1.57), GW(0, -0.035, 1.6), GW(0.07, -0.01, 1.57)], 0.004, 3, "Straw")
    # rags of the coat, hanging from the shoulders and the ribs
    g.link(GW(0, 0.02, 1.53), V((c, s, 0)), V((-s, c, 0)), 0.1, 0.075, 0.014, 12, 3, "Cloth")
    strips = [(-0.2, 0.04, 1.08, 0.09), (-0.16, 0.12, 1.15, 0.07), (0.2, 0.0, 1.02, 0.1), (0.18, 0.13, 1.1, 0.07),
              (0.06, -0.05, 1.05, 0.11), (-0.08, -0.03, 1.12, 0.09)]
    for k, (lx, ly, zb, w) in enumerate(strips):
        tang = V((-ly, lx, 0)).normalized()
        out = V((lx, ly, 0)).normalized()
        pts = [V((lx, ly, 1.52)), V((lx + out.x * 0.02, ly + out.y * 0.02, 1.35)),
               V((lx + out.x * 0.03 + r.uniform(-0.02, 0.02), ly + out.y * 0.03, 1.2)),
               V((lx + out.x * 0.035 + r.uniform(-0.03, 0.03), ly + out.y * 0.03, zb))]
        wp = [GW(*p) for p in pts]
        side = V((tang.x * c - tang.y * s, tang.x * s + tang.y * c, 0))
        ribbon(g, wp, side, w, "Cloth")
        if k in (1, 3):  # torn buttonholes down the front edge
            for i in range(3):
                p = GW(lx + out.x * 0.024, ly + out.y * 0.024, 1.42 - i * 0.07) + V((-s, c, 0)) * 0.003
                g.face([p - side * 0.012 - UP * 0.003, p + side * 0.012 - UP * 0.003, p + side * 0.012 + UP * 0.003,
                        p - side * 0.012 + UP * 0.003], "Iron", V((-s, c, 0)))
    # the one tarnished button the looters missed
    bp = GW(0.183, 0.155, 1.3)
    g.cyl(bp, bp + V((-s, c, 0)) * 0.006, 0.01, 6, "Iron", caps=(False, True))
    # salt fish drying on the east butcher's hook
    hk = V((2.04, yj, 5.12))
    g.sweep([hk + V((0.02, 0, 0.0)), hk + V((0.0, 0, -0.02)), hk + V((-0.012, 0, -0.04))], 0.003, 3, "Straw")
    fr2 = Frame(hk + V((-0.012, 0, -0.045)), V((1, 0, 0)), V((0, 0, 1)), V((0, 1, 0)))
    tail = [(0.0, 0.0), (0.035, 0.01), (0.012, -0.05), (-0.012, -0.05), (-0.035, 0.01)]
    body = [(-0.012, -0.05), (0.012, -0.05), (0.04, -0.15), (0.042, -0.25), (0.02, -0.33), (0.0, -0.36),
            (-0.02, -0.33), (-0.042, -0.25), (-0.04, -0.15)]
    g.prism(tail, fr2, -0.004, 0.004, "Bone")
    g.prism(body, fr2, -0.011, 0.011, "Bone")
    for i in range(5):
        v = -0.1 - i * 0.045
        for sd in (-1, 1):
            seg(g, Frame(fr2.o, fr2.u, fr2.v, fr2.n * sd), (-0.03, v), (0.03, v - 0.01), 0.003, 0.0115, "Floor")


# ================================================================== gate
@kept("G_Arch")
def g_arch(g, lod):
    if lod:
        return
    r = rng("arch")
    # a Crown coin in each Ashby jaw
    for sx in (-0.75, 0.75):
        p = V((sx, -18.235, 6.665))
        g.cyl(p - V((0.004, 0, 0.0)), p + V((0.004, 0, 0.0)), 0.019, 8, "Iron")
        g.cyl(p + V((0.0045, 0, 0)), p + V((0.005, 0, 0)), 0.012, 6, "Bone")
    # the Crown's gull chiselled off the shield, the Lord's hook cut in its place
    fr = wall_frame(V((0, -18.09, 0)), V((0, -1, 0)))
    for i in range(14):
        cu, cv = r.uniform(-0.2, 0.2), 7.45 + r.uniform(-0.2, 0.22)
        ra = r.uniform(0.03, 0.06)
        g.face([fr.p(cu + ra * math.cos(a), cv + ra * math.sin(a), r.uniform(0.002, 0.009))
                for a in [2 * math.pi * k / 4 + i for k in range(4)]], "Stone", fr.n)
    hook = [(0.06, 7.85), (0.06, 7.32), (0.0, 7.18), (-0.12, 7.2), (-0.17, 7.3), (-0.12, 7.38)]
    for a, b in zip(hook, hook[1:]):
        seg(g, fr, a, b, 0.045, 0.011, "Iron")
    seg(g, fr, (-0.12, 7.38), (-0.07, 7.3), 0.03, 0.011, "Iron")
    seg(g, fr, (0.0, 7.85), (0.12, 7.85), 0.05, 0.011, "Iron")
    # motto: WHAT THE SEA GIVES, THE PIT KEEPS
    frm = wall_frame(V((0, -18.0, 0)), V((0, -1, 0)))
    write(g, frm, "WHAT THE SEA GIVES, THE PIT KEEPS", 0.0, 6.3, 0.095, 0.0012, "Iron", align="c", adv=0.7, w=0.016)


@kept("G_Tower_W")
def g_tower_w(g, lod):
    if lod:
        return
    r = rng("ashby")
    fr = wall_frame(V((-2.0, 0, 0)), V((1, 0, 0)))
    write(g, fr, "W.A. KEPT THIS GATE", -16.3, 1.53, 0.05, 0.0008, "Iron", align="c", rnd=r, jit=0.12, w=0.006)
    write(g, fr, "NINE YEARS", -16.32, 1.45, 0.05, 0.0008, "Iron", align="c", rnd=r, jit=0.12, w=0.006)


@kept("G_Tower_E")
def g_tower_e(g, lod):
    if lod:
        return
    r = rng("tides")
    fr = wall_frame(V((2.0, 0, 0)), V((-1, 0, 0)))
    U = lambda y: y * fr.u.y
    for z, label in ((0.46, "Y1 THE EBB"), (0.66, "Y4"), (0.78, "Y9"), (0.92, "FLOOD Y7")):
        seg(g, fr, (U(-16.45), z), (U(-16.75), z), 0.007, 0.0008, "Iron")
        write(g, fr, label, U(-16.45) + 0.02, z + 0.01, 0.03, 0.0008, "Iron", rnd=r, jit=0.1, w=0.005)
        seg(g, fr, (U(-16.42), z - 0.03), (U(-16.78), z - 0.03 - r.uniform(0.0, 0.01)), 0.03, 0.0005, "Bone")
    # mooring ring in a recess of the east jamb at the stair head (does not project into the passage)
    if cut_recess(g, 0, 1.7, -1, -17.96, -17.76, 0.52, 0.80, 0.11):
        p = V((1.81, -17.86, 0.74))
        g.link(p - V((0.012, 0, 0)), V((1, 0, 0)), UP, 0.018, 0.012, 0.005, 8, 3, "Iron")
        g.link(V((1.785, -17.86, 0.66)), UP, V((0, 1, 0)), 0.065, 0.065, 0.009, 14, 4, "Iron")
        g.face([V((1.809, -17.95, 0.53)), V((1.809, -17.77, 0.53)), V((1.809, -17.77, 0.62)),
                V((1.809, -17.95, 0.62))], "Wood", (-1, 0, 0))


@kept("G_Stairs")
def g_stairs(g, lod):
    if lod:
        return
    r = rng("stair")
    x0, x1 = -0.44, -0.36
    # the chain groove, bright where the iron bites
    cut_recess(g, 2, 0.4, 1, x0, x1, -18.56, -18.04, 0.006, bot_mat="Bone")
    cut_recess(g, 1, -19.2, -1, x0, x1, 0.0, 0.17, 0.006, bot_mat="Bone")
    g.face([V((x0, -18.6006, 0.22)), V((x1, -18.6006, 0.22)), V((x1, -18.6006, 0.38)), V((x0, -18.6006, 0.38))],
           "Bone", (0, -1, 0))
    g.face([V((x0, -19.17, 0.2006)), V((x1, -19.17, 0.2006)), V((x1, -18.61, 0.2006)), V((x0, -18.61, 0.2006))],
           "Bone", UP)
    # salt and bladder-wrack on the lowest step, beside the walking line
    for i in range(6):
        cx, cy = 2.4 + r.uniform(-0.45, 0.45), -19.05 + r.uniform(-0.08, 0.08)
        pts = blotch(cx, cy, r.uniform(0.04, 0.1), r, 7, 0.6)
        g.face([V((x, max(-19.17, min(-18.62, y)), 0.2006)) for x, y in pts], "Bone", UP)
    for i in range(7):
        p0 = V((2.4 + r.uniform(-0.45, 0.45), -19.12 + r.uniform(0, 0.05), 0.205))
        a = r.uniform(0, 6.28)
        d = V((math.cos(a), abs(math.sin(a)) * 0.6 + 0.2, 0)).normalized()
        g.sweep([p0, p0 + d * 0.08 + V((0, 0, 0.003)), p0 + d * 0.16 + V((r.uniform(-0.03, 0.03), 0, 0))],
                0.006, 3, "Straw")
        g.blob(p0 + d * 0.1, 0.008, 0.008, 0.006, 5, 1, "Straw", r, 0.1)


@kept("G_Winch")
def g_winch(g, lod):
    if lod:
        return
    r = rng("bell")
    bc = V((-5.05, -13.85, 2.9))
    prof = [(0.0, 0.05), (-0.06, 0.12), (-0.22, 0.15), (-0.38, 0.22), (-0.42, 0.25)]

    def rad(h):
        for (h0, r0), (h1, r1) in zip(prof, prof[1:]):
            if h1 <= h <= h0:
                return r0 + (r1 - r0) * (h - h0) / (h1 - h0)
        return prof[-1][1]

    for h in (-0.24, -0.325):
        g.link(bc + V((0, 0, h)), V((1, 0, 0)), V((0, 1, 0)), rad(h) + 0.002, rad(h) + 0.002, 0.005, 12, 3, "Iron")
    txt = "SAINT CLEMENT KEEP THE SAILORS + FORT CLEMENCY + "
    n = len(txt)
    hz = -0.298
    # SAINT filed away as one bright scraped patch
    a0 = 2 * math.pi * 0 / n
    for sweep in range(5):
        a = 2 * math.pi * sweep / n
        d = V((math.cos(a), math.sin(a), 0))
        o = bc + V((0, 0, hz)) + d * (rad(hz) + 0.0015)
        fr = wall_frame(o, d)
        poly(g, fr, [(-0.013, -0.013), (0.013, -0.013), (0.013, 0.016), (-0.013, 0.016)], 0.0, "Bone")
    # the rest of the cast letters: suggest as short radial dashes
    for i in range(5, n):
        a = 2 * math.pi * i / n
        d = V((math.cos(a), math.sin(a), 0))
        o = bc + V((0, 0, hz)) + d * (rad(hz) + 0.0015)
        fr = wall_frame(o, d)
        seg(g, fr, (-0.006, -0.002), (0.006, 0.002), 0.014, 0.0, "Iron")
    del a0
    # chalk strokes on the bell post: one for every man rung in this year
    fp = wall_frame(V((-5.6, -13.77, 0)), V((0, 1, 0)))
    v = 2.3
    while v > 0.5:
        for col in (-0.055, 0.01):
            for k in range(4):
                u = col + k * 0.011
                seg(fp, None, None, None, None, None, None) if False else seg(g, fp, (u, v), (u + r.uniform(-0.003, 0.003), v - 0.05), 0.004, 0.0008, "Bone")
            seg(g, fp, (col - 0.005, v - 0.045), (col + 0.04, v - 0.005), 0.004, 0.0009, "Bone")
        v -= 0.075
    # 37 TURNS UP, chalked on the east winch post
    fw = wall_frame(V((-3.65, -13.65, 0)), V((0, 1, 0)))
    write(g, fw, "37", 0.0, 1.44, 0.06, 0.0008, "Bone", align="c", rnd=r, jit=0.08)
    write(g, fw, "TURNS", 0.0, 1.405, 0.022, 0.0008, "Bone", align="c", adv=0.72, w=0.0035)
    write(g, fw, "UP", 0.0, 1.375, 0.022, 0.0008, "Bone", align="c", adv=0.72, w=0.0035)


# ================================================================== guardroom walls
@kept("G_Wall_W")
def g_wall_w(g, lod):
    if lod:
        return
    r = rng("crown-arms")
    fr = wall_frame(V((-9.0, -15.2, 0)), V((0, 1, 0)))
    cv = 4.05
    d = 0.0008
    shield = [(-0.38, 0.42), (0.38, 0.42), (0.38, 0.0), (0.26, -0.28), (0.0, -0.46), (-0.26, -0.28), (-0.38, 0.0)]
    poly(g, fr, [(a, cv + b) for a, b in shield], d, "Bone")
    for (a, b, w_) in (((-0.3, 0.1), (-0.15, 0.2), 0.04), ((-0.15, 0.2), (0.0, 0.08), 0.05),
                       ((0.0, 0.08), (0.15, 0.2), 0.05), ((0.15, 0.2), (0.3, 0.1), 0.04), ((-0.05, 0.08), (0.05, 0.02), 0.06),
                       ((0.0, 0.04), (0.0, -0.12), 0.07)):
        seg(g, fr, (a[0], cv + a[1]), (b[0], cv + b[1]), w_, d + 0.0003, "Wood")   # the red gull, faded
    crown = [(-0.2, 0.47), (0.2, 0.47), (0.22, 0.6), (0.11, 0.53), (0.0, 0.64), (-0.11, 0.53), (-0.22, 0.6)]
    for k in range(len(crown) - 2):
        poly(g, fr, [(crown[0][0], cv + crown[0][1]), (crown[k + 1][0], cv + crown[k + 1][1]),
                     (crown[k + 2][0], cv + crown[k + 2][1])], d, "Wood")
    poly(g, fr, [(-0.55, -0.56), (0.55, -0.56), (0.6, -0.47), (-0.6, -0.47)], d, "Bone")
    write(g, fr, "FORT CLEMENCY", 0.0, cv - 0.545, 0.06, d + 0.0003, "Wood", align="c")
    for i in range(9):  # the lime flaking off
        cu, cc = r.uniform(-0.5, 0.5), cv + r.uniform(-0.5, 0.45)
        poly(g, fr, [(cu + math.cos(a) * r.uniform(0.02, 0.06), cc + math.sin(a) * r.uniform(0.02, 0.05))
                     for a in [2 * math.pi * k / 6 for k in range(6)]], d + 0.0006, "Stone")
    hook = [(0.12, cv + 0.62), (0.1, cv - 0.15), (-0.02, cv - 0.38), (-0.22, cv - 0.36), (-0.3, cv - 0.18),
            (-0.2, cv - 0.06)]
    for a, b in zip(hook, hook[1:]):
        seg(g, fr, a, b, 0.09, d + 0.0009, "Iron")
    for u in (0.08, 0.14, -0.25):
        seg(g, fr, (u, cv - 0.2 if u < 0 else cv + 0.2), (u, cv - 0.5 - r.uniform(0.0, 0.25)), 0.015, d + 0.0009, "Iron")


@kept("G_Wall_E")
def g_wall_e(g, lod):
    if lod:
        return
    r = rng("wanted")
    fr = wall_frame(V((8.7, -15.2, 0)), V((0, 1, 0)))
    n = V((0, 1, 0))
    # three wanted posters pinned up as one overlapping pile (200, 500, 1,000 crowns)
    for k, (price, du, dv, ang) in enumerate((("200", -0.1, -0.03, 0.06), ("500", 0.05, 0.02, -0.04),
                                              ("1000", 0.0, 0.0, 0.0))):
        d = 0.001 + 0.0012 * k
        sheet(g, fr, du - 0.21, dv - 0.32, du + 0.21, dv + 0.32, d, ang=ang, torn=(k * 2) % 4 if k < 2 else None,
              rnd=r)
    dd = 0.0046
    cu, cv = 0.0, 0.0
    R = lambda a, b: (a, b)
    write(g, fr, "WANTED", cu, cv + 0.22, 0.05, dd, "Iron", align="c")
    # the face of Lucan Drave with the Watch's moustache
    face = [(math.cos(a) * 0.08, math.sin(a) * 0.1 + 0.06) for a in [2 * math.pi * i / 10 for i in range(11)]]
    for a, b in zip(face, face[1:]):
        seg(g, fr, (cu + a[0], cv + a[1]), (cu + b[0], cv + b[1]), 0.005, dd, "Iron")
    for ex in (-0.03, 0.03):
        seg(g, fr, (cu + ex - 0.012, cv + 0.09), (cu + ex + 0.012, cv + 0.09), 0.006, dd, "Iron")
    seg(g, fr, (cu - 0.05, cv + 0.02), (cu + 0.05, cv + 0.02), 0.008, dd + 0.0003, "Iron")
    write(g, fr, "LUCAN DRAVE", cu, cv - 0.1, 0.03, dd, "Iron", align="c", adv=0.7)
    write(g, fr, "1,000 CROWNS", cu, cv - 0.19, 0.045, dd, "Iron", align="c")
    for du, dv in ((-0.18, 0.29), (0.18, 0.29)):
        nail(g, fr.p(cu + du, cv + dv, dd), n)
    del R


@kept("V_Partition_W")
def v_partition_w(g, lod):
    if lod:
        return
    r = rng("rook-belt")
    # soot plume above the branding brazier (north face: inside the Press-Gang)
    fn = wall_frame(V((-9.6, YP[0] + PT, 0)), V((0, 1, 0)))
    soot(g, fn, r, 1.5, 3.7, 0.5)
    soot(g, fn, r, 1.8, 3.3, 0.3, d=0.0014)
    # south face (the guardroom): pegs, Sergeant Rook's belt with its empty sword-frog, manacles, rope
    fs = wall_frame(V((0, YP[0] - PT, 0)), V((0, -1, 0)))
    n = V((0, -1, 0))
    yw = YP[0] - PT
    for x in (-10.4, -9.75, -9.1):
        p = V((x, yw, 1.78))
        g.cyl(p, p + n * 0.045, 0.011, 5, "Wood", caps=(False, True), r1=0.009)
    # the belt: a loop of leather hanging from the middle peg
    lp = V((-9.75, yw - 0.03, 1.765))
    for sx in (-1, 1):
        ribbon(g, [lp + V((sx * 0.01, 0, 0)), lp + V((sx * 0.07, 0.012, -0.2)), lp + V((sx * 0.06, 0.015, -0.36)),
                   lp + V((0.0, 0.016, -0.42))], V((0, 0, 1)).cross(n).normalized() if False else
               V((1, 0, 0)).cross(V((0, 0, 0))) + V((0, 1, 0)), 0.006, "Cloth", sides=1) if False else None
        pts = [lp + V((sx * 0.01, 0, 0)), lp + V((sx * 0.07, 0.008, -0.2)), lp + V((sx * 0.06, 0.012, -0.36)),
               lp + V((0.0, 0.014, -0.42))]
        for a, b in zip(pts, pts[1:]):
            t = (b - a).normalized()
            side = t.cross(n).normalized() * 0.022
            g.face([a - side, b - side, b + side, a + side], "Cloth", n)
    bk = lp + V((0.0, 0.016, -0.42))
    g.link(bk + V((0, -0.002, 0)), V((1, 0, 0)), UP, 0.03, 0.025, 0.004, 8, 3, "Iron")
    fr_ = lp + V((0.065, 0.014, -0.3))
    g.link(fr_ + V((0, 0, -0.06)), UP, V((1, 0, 0)), 0.06, 0.025, 0.006, 10, 3, "Cloth")
    # manacles on the west peg
    mp = V((-10.4, yw - 0.035, 1.765))
    for sx in (-1, 1):
        g.link(mp + V((sx * 0.04, 0.0, -0.13)), V((1, 0, 0)), UP, 0.045, 0.045, 0.007, 8, 3, "Iron")
    # a coil of rope on the east peg
    g.link(V((-9.1, yw - 0.035, 1.66)), UP, V((1, 0, 0)), 0.12, 0.1, 0.014, 10, 3, "Straw")
    del fs


@kept("V_Partition_E")
def v_partition_e(g, lod):
    if lod:
        return
    r = rng("compass")
    # compass rose on the Kennel side (north face): Hugh Ormond's bearings, north struck through
    fr = wall_frame(V((8.0, YP[0] + PT, 1.6)), V((0, 1, 0)))
    for i in range(4):
        a = math.pi / 2 + i * math.pi / 2
        tip = (math.cos(a) * 0.21, math.sin(a) * 0.21)
        side = (math.cos(a + 0.4) * 0.04, math.sin(a + 0.4) * 0.04)
        g.face([fr.p(0, 0, 0.022), fr.p(tip[0], tip[1], 0.022), fr.p(side[0], side[1], 0.022)], "Stone", fr.n)
        a2 = a + math.pi / 4
        tip2 = (math.cos(a2) * 0.12, math.sin(a2) * 0.12)
        g.face([fr.p(0, 0, 0.012), fr.p(tip2[0], tip2[1], 0.012),
                fr.p(math.cos(a2 + 0.4) * 0.04, math.sin(a2 + 0.4) * 0.04, 0.012)], "Stone", fr.n)
    g.link(fr.p(0, 0, 0.008), fr.u, fr.v, 0.15, 0.15, 0.007, 12, 3, "Stone")
    write(g, fr, "N", 0.0, 0.23, 0.05, 0.0008, "Iron", align="c", rnd=r, jit=0.1)
    seg(g, fr, (-0.07, 0.15), (0.07, 0.27), 0.01, 0.0232, "Iron")
    # the wager slate on the guardroom side (south face): HOW LONG UNDER?
    fs = wall_frame(V((8.5, YP[0] - PT, 0)), V((0, -1, 0)))
    cu, cv = 0.0, 1.8
    hw, hh = 0.3, 0.225
    # the slate as one raised rectangle in a wooden frame rectangle (one quad each)
    poly(g, fs, [(cu - hw, cv - hh), (cu + hw, cv - hh), (cu + hw, cv + hh), (cu - hw, cv + hh)], 0.025, "Wood")
    poly(g, fs, [(cu - hw + 0.03, cv - hh + 0.03), (cu + hw - 0.03, cv - hh + 0.03),
                 (cu + hw - 0.03, cv + hh - 0.03), (cu - hw + 0.03, cv + hh - 0.03)], 0.027, "Stone")
    d = 0.0276
    write(g, fs, "HOW LONG UNDER?", cu, cv + 0.14, 0.03, d, "Bone", align="c", adv=0.72)
    rows = [("DACE", "90"), ("MULL", "120"), ("HOLLIS", "200"), ("ORRIN", "61"), ("KETCH", "150")]
    for i, (nm, val) in enumerate(rows):
        v = cv + 0.08 - i * 0.042
        write(g, fs, nm, cu - 0.22, v, 0.024, d, "Bone", rnd=r, jit=0.08, adv=0.72)
        write(g, fs, val, cu + 0.1, v, 0.024, d, "Bone", rnd=r, jit=0.08, adv=0.72)
    seg(g, fs, (cu - 0.23, cv + 0.08 - 3 * 0.042 + 0.012), (cu + 0.2, cv + 0.08 - 3 * 0.042 + 0.012), 0.004, d + 0.0003,
        "Bone")
    # chalk stub on a string
    top = fs.p(cu + hw - 0.05, cv - hh, 0.02)
    g.sweep([top, top + V((0, 0, -0.08)), top + V((0.005, 0, -0.14))], 0.002, 3, "Straw")
    g.cyl(top + V((0.005, 0, -0.14)), top + V((0.005, 0, -0.18)), 0.007, 5, "Bone")


@kept("V_Wall_E")
def v_wall_e(g, lod):
    if lod:
        return
    # the names of the Watch, cut in a dressed panel at head height (FENNICK the newest, the cleanest)
    if not cut_recess(g, 0, 11.6, -1, -13.62, -12.38, 1.52, 2.08, 0.012):
        return
    r = rng("watch-names")
    fr = wall_frame(V((11.612, 0, 0)), V((-1, 0, 0)))
    U = lambda y: y * fr.u.y
    write(g, fr, "THE WATCH", U(-13.0), 1.99, 0.05, 0.0008, "Iron", align="c", w=0.007)
    names = ["DACE", "MULL", "ROOK", "HOLLIS", "TOLLEY", "ORRIN", "KETCH", "FENNICK"]
    for i, nm in enumerate(names):
        col, row = i // 4, i % 4
        u = U(-13.0) - 0.53 + col * 0.58
        v = 1.89 - row * 0.09
        clean = nm == "FENNICK"
        write(g, fr, nm, u, v, 0.045, 0.0008, "Iron", rnd=None if clean else r, jit=0.1, w=0.006)


@kept("V_Floor_1")
def v_floor_1(g, lod):
    if lod:
        return
    r = rng("rust")
    tops = Tops(g)
    fdecal(g, tops, blotch(-6.9, -14.95, 0.28, r, 10, 0.5), "Wood", lift=0.0004, cap=0.4)
    for i in range(4):
        fdecal(g, tops, blotch(-6.9 + r.uniform(-0.4, 0.4), -14.95 + r.uniform(-0.1, 0.2), r.uniform(0.03, 0.07), r, 6),
               "Wood", lift=0.0006, cap=0.4)


@kept("V_Floor_2")
def v_floor_2(g, lod):
    if lod:
        return
    r = rng("strip")
    tops = Tops(g)
    x0, x1, y0, y1 = -3.65, -2.75, -13.05, -12.15
    for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
        fseg(g, tops, a, b, 0.03, "Iron", lift=0.0004, cap=0.4, step=0.15)
    ftext(g, tops, "STRIP HERE", (x0 + x1) / 2, y0 + 0.07, 0.07, "Iron", align="c", cap=0.4, rnd=r, jit=0.06)
    for i in range(5):  # scuffs of bare feet worn pale inside the square
        fdecal(g, tops, blotch(r.uniform(x0 + 0.15, x1 - 0.15), r.uniform(y0 + 0.25, y1 - 0.15), 0.06, r, 7, 0.45,
                               r.uniform(0, 3)), "Stone", lift=0.0004, cap=0.4)


@kept("V_Floor_3")
def v_floor_3(g, lod):
    if lod:
        return
    r = rng("rum")
    tops = Tops(g)
    fdecal(g, tops, blotch(6.85, -13.95, 0.22, r, 10, 0.6, 0.3), "Iron", lift=0.0004, cap=0.4)
    for i in range(4):
        fdecal(g, tops, blotch(6.85 + r.uniform(-0.35, 0.35), -13.95 + r.uniform(-0.2, 0.2), r.uniform(0.02, 0.05), r, 6),
               "Iron", lift=0.0006, cap=0.4)


# ================================================================== guardroom furniture
def tankard(g, p, axis=None):
    """Pewter tankard: tapered body with a handle."""
    p = V(p)
    ax = UP if axis is None else V(axis).normalized()
    if axis is None:
        side = V((1, 0, 0))
    else:
        side = V((0, 0, 1)).cross(ax).normalized()
        side = ax.cross(side).normalized()
    top = p + ax * 0.13
    g.cyl(p, top, 0.046, 7, "Iron", caps=(True, True), r1=0.04)
    h = [p + ax * 0.11 + side * 0.04, p + ax * 0.115 + side * 0.075, p + ax * 0.06 + side * 0.08,
         p + ax * 0.025 + side * 0.045]
    g.sweep(h, 0.007, 3, "Iron")


@kept("V_Table")
def v_table(g, lod):
    if lod:
        return
    r = rng("table-story")
    top = FL + 0.82
    ft = floor_frame(0, 0)
    # pips: the two dice on the table both show six (a double six) — one dark panel per die
    for x0 in (6.8, 6.88):
        poly(g, ft, [(x0 + 0.004, -13.3 + 0.004), (x0 + 0.026, -13.3 + 0.004),
                     (x0 + 0.026, -13.3 + 0.026), (x0 + 0.004, -13.3 + 0.026)], top + 0.0306, "Iron")
    # the third die, Kit Fennick's loaded one, split to show the lead
    x0, y0 = 6.725, -13.38
    g.bbox(V((x0, y0, top)), V((x0 + 0.03, y0 + 0.013, top + 0.03)), "Bone", 0.003)
    g.bbox(V((x0 + 0.002, y0 + 0.019, top)), V((x0 + 0.032, y0 + 0.032, top + 0.028)), "Bone", 0.003)
    g.box(V((x0 + 0.006, y0 + 0.0125, top)), V((x0 + 0.024, y0 + 0.0195, top + 0.02)), "Iron")
    poly(g, ft, [(x0 + 0.012, y0 + 0.004), (x0 + 0.018, y0 + 0.004), (x0 + 0.018, y0 + 0.009), (x0 + 0.012, y0 + 0.009)],
         top + 0.0306, "Iron")
    # debts knifed into the west half of the top
    for i, s in enumerate(("DACE OWES MULL 4", "MULL OWES ROOK 9", "ROOK OWES THE LORD EVERYTHING")):
        write(g, ft, s, 5.72, -13.555 - i * 0.075, 0.028, top + 0.0006, "Iron", rnd=r, jit=0.15, w=0.0035,
              adv=0.72)
    # pewter plate: a fish spine and a crust (the Watch eats first)
    pc = V((6.2, -13.08, top))
    g.cyl(pc, pc + V((0, 0, 0.006)), 0.11, 8, "Iron")
    sp = [pc + V((-0.06, -0.01, 0.009)), pc + V((0.055, 0.012, 0.009))]
    g.sweep(sp, 0.0025, 3, "Bone")
    for k in range(3):
        b = sp[0].lerp(sp[1], 0.25 + k * 0.25)
        g.cyl(b + V((0, -0.025, 0)), b + V((0, 0.025, 0)), 0.001, 3, "Bone", caps=(False, False))
    g.blob(pc + V((-0.03, 0.05, 0.006)), 0.035, 0.022, 0.018, 6, 1, "Wood", r, 0.18)
    # the Lord's Due: a stack of coins at the foot of the stuck dagger
    for k in range(3):
        c = V((7.245 + r.uniform(-0.003, 0.003), -13.45 + r.uniform(-0.003, 0.003), top + k * 0.006))
        g.cyl(c, c + V((0, 0, 0.0055)), 0.015, 6, "Iron")
    # the Two of Bones, half under a tankard
    fc = floor_frame(7.37, -13.13, 0.4)
    poly(g, fc, [(-0.032, -0.045), (0.032, -0.045), (0.032, 0.045), (-0.032, 0.045)], top + 0.0008, "Bone")
    for v in (-0.025, 0.025):
        seg(g, fc, (-0.006, v), (0.006, v), 0.01, top + 0.0014, "Iron")
    tankard(g, V((7.42, -13.08, top + 0.0012)))
    # a second tankard knocked over, its rum spilt across the boards
    tankard(g, V((6.72, -13.72, top + 0.046)), axis=V((1, 0.15, 0)))
    ft2 = floor_frame(6.93, -13.7, 0.2)
    poly(g, ft2, [(0.0, -0.05), (0.09, -0.07), (0.16, -0.02), (0.13, 0.05), (0.03, 0.05)], top + 0.0007, "Floor")


@kept("V_Props_W")
def v_props_w(g, lod):
    if lod:
        return
    r = rng("hall-board")
    wy = -15.2
    n = V((0, 1, 0))
    fr = wall_frame(V((-9.2, wy, 0)), V((0, 1, 0)))
    # the Sentence Board, right above the key board: slate in a wooden frame, chalked in Hask's hand
    u0, u1, z0, z1 = -0.7, 0.7, 2.74, 3.18
    poly(g, fr, [(u0, z0), (u1, z0), (u1, z1), (u0, z1)], 0.025, "Wood")
    poly(g, fr, [(u0 + 0.03, z0 + 0.03), (u1 - 0.03, z0 + 0.03), (u1 - 0.03, z1 - 0.03), (u0 + 0.03, z1 - 0.03)],
         0.027, "Stone")
    d = 0.0276
    write(g, fr, "SENTENCES", 0.0, 3.1, 0.035, d, "Bone", align="c")
    rows = [("PRESS", "4", "9"), ("RACK", "11", "6"), ("STOCKS", "7", "3"), ("CISTERN", "5", "2"),
            ("KENNEL", "2", "40"), ("KENNEL", "8", "61"), ("CAGES", "6", "12"), ("MAST", "9", "5")]
    for i, (room, num, days) in enumerate(rows):
        col, row = i // 4, i % 4
        u = -0.64 + col * 0.66
        v = 3.03 - row * 0.068
        write(g, fr, room, u, v, 0.026, d, "Bone", adv=0.72, rnd=r, jit=0.05)
        write(g, fr, "NO " + num, u + 0.2, v, 0.026, d, "Bone", adv=0.72, rnd=r, jit=0.05)
        write(g, fr, days, u + 0.36, v, 0.026, d, "Bone", adv=0.72, rnd=r, jit=0.05)
        for k in range(int(days) % 5 + 1):  # struck-off days
            uu = u + 0.45 + k * 0.012
            seg(g, fr, (uu, v), (uu, v + 0.026), 0.003, d, "Bone")
        if i in (1, 6):  # finished: struck through, never wiped
            seg(g, fr, (u - 0.01, v + 0.012), (u + 0.52, v + 0.016), 0.004, d + 0.0003, "Bone")
    # Standing Orders of the Watch, in the Wren's round hand
    fo = wall_frame(V((-8.0, wy, 0)), V((0, 1, 0)))
    sheet(g, fo, -0.24, 1.56, 0.24, 2.24, 0.0012, ang=0.02)
    write(g, fo, "STANDING ORDERS", 0.0, 2.16, 0.026, 0.0018, "Iron", align="c", adv=0.7)
    for i, num in enumerate(("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX")):
        v = 2.1 - i * 0.056
        write(g, fo, num, -0.2, v, 0.018, 0.0018, "Iron", adv=0.6)
        for k in range(2):
            seg(g, fo, (-0.12, v + 0.012 - k * 0.022), (r.uniform(0.0, 0.2), v + 0.012 - k * 0.022), 0.0035, 0.0018,
                "Iron")
    for du, dv in ((-0.22, 2.22), (0.22, 2.22), (-0.22, 1.58), (0.22, 1.58)):
        nail(g, fo.p(du, dv, 0.0015), n)
    # the anchor's shank worn bright at hand height (every guard touches it before his watch)
    band = __import__("geo").Geo()
    band.cyl(V((0, 0, 0.95)), V((0, 0, 1.17)), 0.0635, 6, "Bone", caps=(False, False))
    m = Matrix.Translation(V((-6.9, wy + 0.25, FL))) @ Matrix.Rotation(0.22, 4, "X")
    g.extend(band.transform(m))
    # eight bone key tags (the Cistern's stained green with weed) — flat quads on each key
    for i in range(8):
        x = -9.75 + i * 0.16 + 0.02
        t0 = V((x, wy + 0.092, FL + 2.08))
        mat = "Straw" if i == 3 else "Bone"
        g.face([V((t0.x - 0.015, t0.y, t0.z - 0.055)), V((t0.x + 0.015, t0.y, t0.z - 0.055)),
                V((t0.x + 0.015, t0.y, t0.z)), V((t0.x - 0.015, t0.y, t0.z))], mat, (0, 1, 0))


@kept("V_Basket")
def v_basket(g, lod):
    if lod:
        return
    r = rng("basket-story")
    c = V((9.6, -13.0, FL))
    # knife tally on the woven rim: forty-seven baskets down the Kennel hatch this year (groups of five)
    for i in range(24):
        a = 2 * math.pi * i / 24 + 0.1
        d = V((math.cos(a), math.sin(a), 0))
        p = c + V((0, 0, 0.6)) + d * 0.4256
        t = V((-d.y, d.x, 0))
        hz = 0.024 if i % 5 == 4 else 0.016
        g.face([p - t * 0.002 - UP * hz / 2, p + t * 0.002 - UP * hz / 2, p + t * 0.002 + UP * hz / 2,
                p - t * 0.002 + UP * hz / 2], "Iron", d)
    # the forked stick for lifting rags: nobody touches the Watch's breeches by hand
    foot = V((9.38, -12.33, FL))
    fork = V((9.47, -12.6, FL + 0.66))
    g.cyl(foot, fork, 0.012, 5, "Wood", caps=(True, False), r1=0.011)
    for sd in (-1, 1):
        g.cyl(fork, fork + V((sd * 0.045, -0.02, 0.075)), 0.009, 4, "Wood", caps=(False, True), r1=0.006)
    # a loincloth and a shirt sleeve hanging over the rim
    for (a, w, ln) in ((2.6, 0.11, 0.3), (4.2, 0.08, 0.22)):
        d = V((math.cos(a), math.sin(a), 0))
        t = V((-d.y, d.x, 0))
        pts = [c + d * 0.3 + V((0, 0, 0.58)), c + d * 0.41 + V((0, 0, 0.635)), c + d * 0.445 + V((0, 0, 0.58)),
               c + d * 0.43 + V((0, 0, 0.6 - ln * 0.6)), c + d * 0.415 + V((0, 0, 0.6 - ln))]
        ribbon(g, pts, t, w, "Cloth")

"""Story details: throne_hall (see story/__init__.py for the rules).

The Lord's hall (N_* pieces): the only place in the Pit where anything is clean, and even here it is not.
Gilt is Bone (warm ivory reads as old gold by the braziers), soot / black paint / ink / rust is Iron,
paper / leather / cloth is Cloth, wax is Bone, cord and wicker are Straw. Candle flames use Flame.

Everything here is HIGH-LOD (lod 0) unless noted; a couple of silhouettes exist in MEDIUM (lod 1).
Every item stays inside its piece's bounding box (see Report.json / tests/baseline_bounds.json).
"""

import math

from mathutils import Matrix, Vector

from geo import Frame, rng
from pieces import FL, bx

from . import decorates

V = Vector
DAIS = FL + 0.9          # top of the dais (1.30)
YB0 = 15.2               # front face of the back walls
EPS = 0.0004             # "incised" marks: a hair proud of a surface that has no slack

# ------------------------------------------------------------------ a tiny stroke font (u 0..0.7, v 0..1)
_O = [(0.2, 0), (0.5, 0), (0.7, 0.2), (0.7, 0.8), (0.5, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0)]
FONT = {
    "S": [[(0.7, 0.85), (0.55, 1), (0.15, 1), (0, 0.85), (0, 0.62), (0.15, 0.5), (0.55, 0.5), (0.7, 0.38),
           (0.7, 0.12), (0.55, 0), (0.15, 0), (0, 0.15)]],
    "T": [[(0, 1), (0.7, 1)], [(0.35, 1), (0.35, 0)]],
    "E": [[(0.65, 1), (0, 1), (0, 0), (0.65, 0)], [(0, 0.5), (0.5, 0.5)]],
    "A": [[(0, 0), (0.35, 1), (0.7, 0)], [(0.15, 0.4), (0.55, 0.4)]],
    "D": [[(0, 0), (0, 1), (0.4, 1), (0.65, 0.8), (0.7, 0.5), (0.65, 0.2), (0.4, 0), (0, 0)]],
    "F": [[(0.65, 1), (0, 1), (0, 0)], [(0, 0.52), (0.5, 0.52)]],
    "K": [[(0, 0), (0, 1)], [(0.65, 1), (0, 0.42)], [(0.22, 0.6), (0.7, 0)]],
    "N": [[(0, 0), (0, 1), (0.7, 0), (0.7, 1)]],
    "L": [[(0, 1), (0, 0), (0.65, 0)]],
    "O": [_O],
    "Y": [[(0, 1), (0.35, 0.5), (0.7, 1)], [(0.35, 0.5), (0.35, 0)]],
    "7": [[(0, 1), (0.7, 1), (0.25, 0)]],
    "1": [[(0.15, 0.82), (0.35, 1), (0.35, 0)]],
    "R": [[(0, 0), (0, 1), (0.5, 1), (0.7, 0.85), (0.7, 0.62), (0.5, 0.5), (0, 0.5)], [(0.3, 0.5), (0.7, 0)]],
    "J": [[(0.7, 1), (0.7, 0.2), (0.5, 0), (0.15, 0), (0, 0.2)]],
    "P": [[(0, 0), (0, 1), (0.5, 1), (0.7, 0.85), (0.7, 0.62), (0.5, 0.5), (0, 0.5)]],
    "W": [[(0, 1), (0.15, 0), (0.35, 0.6), (0.55, 0), (0.7, 1)]],
    "H": [[(0, 0), (0, 1)], [(0.7, 0), (0.7, 1)], [(0, 0.5), (0.7, 0.5)]],
    "M": [[(0, 0), (0, 1), (0.35, 0.45), (0.7, 1), (0.7, 0)]],
    "C": [[(0.7, 0.85), (0.5, 1), (0.2, 1), (0, 0.8), (0, 0.2), (0.2, 0), (0.5, 0), (0.7, 0.15)]],
    "B": [[(0, 0), (0, 1), (0.5, 1), (0.68, 0.85), (0.68, 0.62), (0.5, 0.5), (0, 0.5)],
          [(0.5, 0.5), (0.7, 0.36), (0.7, 0.14), (0.5, 0), (0, 0)]],
}


def wall_frame(x, z, y=YB0):
    """Frame on the front face of the back walls: u = +x, v = up, n = into the hall (-y)."""
    return Frame((x, y, z), (1, 0, 0), (0, 0, 1), (0, -1, 0))


def seg(g, fr, a, b, w, d0, d1, mat, back=False):
    """A stroke (raised bar) from a to b (frame u, v), width w, between depths d0 and d1."""
    a, b = V((a[0], a[1])), V((b[0], b[1]))
    t = b - a
    if t.length < 1e-6:
        return
    t.normalize()
    s = V((-t.y, t.x)) * (w / 2)
    e = t * (w / 2)
    a, b = a - e, b + e
    poly = [tuple(a - s), tuple(b - s), tuple(b + s), tuple(a + s)]
    g.prism(poly, fr, d0, d1, mat, caps=(back, True))


def polyline(g, fr, pts, w, d0, d1, mat):
    for a, b in zip(pts, pts[1:]):
        seg(g, fr, a, b, w, d0, d1, mat)


def text(g, fr, s, h, w, d0, d1, mat, u0=None, v0=0.0, pitch=0.95, flip=False, skip=(), tilt=None):
    """Writes `s` centred on u = 0 (or from u0). flip: the whole row rotated 180 degrees (upside down)."""
    adv = h * pitch
    total = adv * len(s) - h * (pitch - 0.7)
    start = -total / 2 if u0 is None else u0
    for k, ch in enumerate(s):
        if ch == " " or ch not in FONT or k in skip:
            continue
        ox = start + adv * k
        ang = tilt.get(k, 0.0) if tilt else 0.0
        ca, sa = math.cos(ang), math.sin(ang)
        for line in FONT[ch]:
            pts = []
            for (u, v) in line:
                lu, lv = (u - 0.35) * h, (v - 0.5) * h
                lu, lv = lu * ca - lv * sa, lu * sa + lv * ca
                pu, pv = ox + 0.35 * h + lu, v0 + 0.5 * h + lv
                if flip:
                    pu, pv = -pu, 2 * v0 - pv
                pts.append((pu, pv))
            polyline(g, fr, pts, w, d0, d1, mat)


def strap(g, pts, up, width, thick, mat, caps=True):
    """Rectangular-section band along a polyline; `up` is the normal of the band's flat face."""
    pts = [V(p) for p in pts]
    up = V(up).normalized()
    rings = []
    for i, p in enumerate(pts):
        t = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        s = t.cross(up).normalized() * (width / 2)
        n = s.cross(t).normalized() * (thick / 2)
        rings.append([p - s - n, p + s - n, p + s + n, p - s + n])
    for i in range(len(pts) - 1):
        mid = (pts[i] + pts[i + 1]) / 2
        for k in range(4):
            k2 = (k + 1) % 4
            g.face_c([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], mat, mid)
    if caps:
        g.face(rings[0], mat, pts[0] - pts[1])
        g.face(rings[-1], mat, pts[-1] - pts[-2])


def patch(g, c, r, n, mat, rnd, normal=(0, 0, 1), u=None, jitter=0.3, sx=1.0, sy=1.0):
    """Flat irregular polygon (stain, wax pool, scorch) facing `normal`."""
    c, nrm = V(c), V(normal).normalized()
    u = V(u).normalized() if u is not None else nrm.orthogonal().normalized()
    v = nrm.cross(u)
    pts = []
    for k in range(n):
        a = 2 * math.pi * k / n
        rr = r * (1 + rnd.uniform(-jitter, jitter))
        pts.append(c + u * (math.cos(a) * rr * sx) + v * (math.sin(a) * rr * sy))
    g.face(pts, mat, nrm)


def ering(g, c, rx, ry, h, n, mat, shrink=1.0):
    """Open elliptical band (circlet, hoop) from c.z to c.z + h."""
    c = V(c)
    lo = [c + V((math.cos(2 * math.pi * k / n) * rx, math.sin(2 * math.pi * k / n) * ry, 0)) for k in range(n)]
    hi = [c + V((math.cos(2 * math.pi * k / n) * rx * shrink, math.sin(2 * math.pi * k / n) * ry * shrink, h))
          for k in range(n)]
    for k in range(n):
        k2 = (k + 1) % n
        g.face_c([lo[k], lo[k2], hi[k2], hi[k]], mat, c + V((0, 0, h / 2)))
    return lo, hi


def candle(g, base, h, r, rnd, flame=True, drips=2, n=6, lit=True):
    """Tallow candle (Bone) with wax runs and a small Flame tongue."""
    base = V(base)
    top = base + V((0, 0, h))
    g.cyl(base, top, r, n, "Bone", caps=(False, True), r1=r * 0.93)
    for k in range(drips):
        a = rnd.uniform(0, 6.28)
        d = V((math.cos(a), math.sin(a), 0))
        L = rnd.uniform(0.3, 0.8) * h
        g.sweep([top + d * (r * 0.9) - V((0, 0, 0.003)), top + d * (r * 1.05) - V((0, 0, L * 0.5)),
                 top + d * (r * 1.0) - V((0, 0, L))], r * 0.22, 3, "Bone")
    if flame and lit:
        g.cyl(top, top + V((0, 0, 0.012)), 0.0025, 3, "Iron", caps=(False, False))
        g.flame(top + V((0, 0, 0.008)), rnd.uniform(0.045, 0.06), r * 0.45, 4, "Flame", rnd,
                lean=V((rnd.uniform(-0.006, 0.006), rnd.uniform(-0.006, 0.006), 0)))


def long_bone(g, a, b, r, mat="Bone", gnawed=False):
    """A long bone (femur, shin): shaft and knobbed ends; `gnawed` leaves one end splintered."""
    a, b = V(a), V(b)
    t = (b - a).normalized()
    g.cyl(a + t * r, b - t * r, r, 5, mat, caps=(False, False))
    g.cyl(a - t * r * 0.4, a + t * r * 1.6, r * 1.7, 5, mat, r1=r * 1.1)
    if gnawed:
        g.cyl(b - t * r, b + t * r * 1.5, r, 4, mat, caps=(False, True), r1=r * 0.3)
    else:
        g.cyl(b - t * r * 1.6, b + t * r * 0.4, r * 1.1, 5, mat, r1=r * 1.7)


def hook_and_crown(g, fr, s, d0, d1, w, mat_hook="Bone", mat_crown="Bone"):
    """The Lord's sign in a frame: a hook through a broken crown, scale `s` (about 1 = 1 m tall)."""
    # the crown, broken in two
    for half, (du, dv, ang) in ((-1, (0.0, 0.0, 0.0)), (1, (0.03, -0.05, -0.22))):
        ca, sa = math.cos(ang), math.sin(ang)

        def P(u, v):
            u, v = u * s, v * s
            return (u * ca - v * sa + du * s, u * sa + v * ca + dv * s)
        band = [(-0.36, -0.05), (-0.03, -0.05)] if half < 0 else [(0.03, -0.05), (0.36, -0.05)]
        seg(g, fr, P(*band[0]), P(*band[1]), w * 1.6, d0, d1, mat_crown)
        tips = (-0.34, -0.17) if half < 0 else (0.17, 0.34)
        for tu in tips:
            polyline(g, fr, [P(tu - 0.06, -0.03), P(tu, 0.16), P(tu + 0.06, -0.03)], w * 0.8, d0, d1, mat_crown)
    # the hook: a bent shank with a barb, the eye reduced to a loop at the top
    hk = [(0.0, 0.56), (0.0, 0.1), (-0.03, -0.3), (-0.2, -0.38), (-0.3, -0.22)]
    polyline(g, fr, [(u * s, v * s) for u, v in hk], w * 1.4, d0 + (d1 - d0) * 0.2, d1 + (d1 - d0) * 0.6, mat_hook)
    polyline(g, fr, [(-0.3 * s, -0.22 * s), (-0.22 * s, -0.26 * s)], w, d0, d1 + (d1 - d0) * 0.6, mat_hook)


# ------------------------------------------------------------------ banners (shared by N_Back_W / N_Back_E)
def banner_surface(x0, top=6.6, w=1.3, h=3.4, nx=6, nz=10):
    """Point on the front face of the Lord's banner (pieces_v3.banner) at local (u, z), bilinear."""
    def y_at(i, j):
        return YB0 - 0.15 - 0.04 * math.sin(i * 1.3 + j * 0.9)

    def f(u, z):
        fi = (u + w / 2) / w * nx
        fj = (top - 0.05 - z) / h * nz
        i0, j0 = max(0, min(nx - 1, int(fi))), max(0, min(nz - 1, int(fj)))
        a, b = fi - i0, fj - j0
        y = (y_at(i0, j0) * (1 - a) * (1 - b) + y_at(i0 + 1, j0) * a * (1 - b) + y_at(i0, j0 + 1) * (1 - a) * b
             + y_at(i0 + 1, j0 + 1) * a * b)
        return V((x0 + u, y, z))
    return f


def banner_strokes(g, surf, lines, w, off, mat):
    """Flat strokes laid on the banner cloth (subdivided so they follow its folds).
    The strokes are nudged slightly BACK (+y) onto the surface rather than into the hall, so they stay
    inside the piece's bounding box; `off` here is interpreted as a push back toward the wall."""
    for line in lines:
        for (u0, z0), (u1, z1) in zip(line, line[1:]):
            n = max(1, int(math.hypot(u1 - u0, z1 - z0) / 0.14) + 1)
            du, dz = u1 - u0, z1 - z0
            L = math.hypot(du, dz)
            su, sz = -dz / L * w / 2, du / L * w / 2
            eu, ez = du / L * w / 2, dz / L * w / 2
            pts = [(u0 - eu + (du + 2 * eu) * k / n, z0 - ez + (dz + 2 * ez) * k / n) for k in range(n + 1)]
            for (a, b), (c, d) in zip(pts, pts[1:]):
                q = [surf(a - su, b - sz), surf(c - su, d - sz), surf(c + su, d + sz), surf(a + su, b + sz)]
                q = [V((p.x, max(p.y - off, 15.012), p.z)) for p in q]
                g.face(q, mat, (0, -1, 0))


def lord_banner_device(g, x0, rnd):
    """Hook through a broken crown, in white and gilt, on the Lord's banner; gilt tassels on the bar."""
    surf = banner_surface(x0)
    zc, s = 5.05, 0.9
    crownL = [[(-0.36 * s, zc - 0.05 * s), (-0.03 * s, zc - 0.05 * s)],
              [(-0.4 * s, zc - 0.03 * s), (-0.34 * s, zc + 0.16 * s), (-0.28 * s, zc - 0.03 * s)],
              [(-0.23 * s, zc - 0.03 * s), (-0.17 * s, zc + 0.16 * s), (-0.11 * s, zc - 0.03 * s)],
              [(-0.03 * s, zc - 0.05 * s), (-0.05 * s, zc + 0.05 * s)]]
    crownR = [[(0.05 * s, zc - 0.11 * s), (0.36 * s, zc - 0.2 * s)],
              [(0.11 * s, zc - 0.1 * s), (0.2 * s, zc + 0.07 * s), (0.24 * s, zc - 0.14 * s)],
              [(0.27 * s, zc - 0.15 * s), (0.36 * s, zc + 0.02 * s), (0.4 * s, zc - 0.19 * s)]]
    banner_strokes(g, surf, crownL + crownR, 0.035, 0.007, "Bone")
    hk = [(0.0, 0.5), (0.0, 0.1), (0.0, -0.2), (-0.03, -0.32), (-0.12, -0.39), (-0.24, -0.36), (-0.3, -0.26),
          (-0.29, -0.15), (-0.21, -0.21)]
    banner_strokes(g, surf, [[(u * s, zc + v * s) for u, v in hk]], 0.05, 0.010, "Bone")
    eye = [(0.0, 0.5), (0.06, 0.54), (0.06, 0.62), (0.0, 0.66), (-0.06, 0.62), (-0.06, 0.54), (0.0, 0.5)]
    banner_strokes(g, surf, [[(u * s, zc + v * s) for u, v in eye]], 0.028, 0.010, "Bone")
    # a burnt hole and a sword slash, dark at the edges (soot)
    banner_strokes(g, surf, [[(0.38, 4.05), (0.18, 3.62)], [(0.36, 4.1), (0.15, 3.6)]], 0.012, 0.007, "Iron")
    banner_strokes(g, surf, [[(-0.45, 6.15), (-0.38, 6.22), (-0.3, 6.16), (-0.33, 6.07), (-0.43, 6.06),
                              (-0.45, 6.15)]], 0.03, 0.007, "Iron")
    # gilt border along the top hem
    banner_strokes(g, surf, [[(-0.6, 6.42), (0.6, 6.42)]], 0.04, 0.007, "Bone")
    # gilt cords with tassels from the ends of the bar
    for sx in (-1, 1):
        a = V((x0 + sx * 0.73, YB0 - 0.12, 6.57))
        b = V((x0 + sx * 0.76, YB0 - 0.13, 6.05))
        g.sweep([a, a.lerp(b, 0.5) + V((sx * 0.012, 0, 0)), b], 0.006, 3, "Bone")
        g.cyl(b, b - V((0, 0, 0.03)), 0.012, 5, "Bone", caps=(True, False), r1=0.016)
        g.cyl(b - V((0, 0, 0.03)), b - V((0, 0, 0.13)), 0.016, 5, "Bone", caps=(False, True), r1=0.022)


def half_candle_crown(g, x, z, rnd):
    """Iron candle shelf bracketed to the wall: three candles, wax hanging in beards."""
    y0 = YB0 - 0.02
    bx(g, x - 0.26, x + 0.26, y0 - 0.14, YB0, z - 0.02, z + 0.012, "Iron")
    bx(g, x - 0.04, x + 0.04, y0 - 0.012, YB0, z - 0.28, z - 0.14, "Iron")
    for u in (-0.18, 0.0, 0.18):
        p = V((x + u, y0 - 0.07, z + 0.014))
        g.cyl(p, p + V((0, 0, 0.012)), 0.022, 6, "Iron", caps=(True, True))
        candle(g, p + V((0, 0, 0.012)), rnd.uniform(0.1, 0.22), 0.016, rnd, drips=2)
        g.cyl(p + V((0, 0, -0.002)), p + V((0, 0, -rnd.uniform(0.04, 0.08))), 0.012, 3, "Bone",
              caps=(False, False), r1=0.002)


# ================================================================== N_Back_C
@decorates("N_Back_C")
def n_back_c(g, lod):
    if lod != 0:
        return
    spr = DAIS + 2.2
    r = rng("throne-back-c")

    # -- ghost of the Crown's arms on the back face of the niche (y = YB0 + 0.5), behind the wheel
    fr = Frame((0, YB0 + 0.5, 4.1), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    shield = [(-0.42, 0.45), (0.42, 0.45), (0.42, 0.0), (0.3, -0.3), (0.0, -0.5), (-0.3, -0.3), (-0.42, 0.0)]
    g.face([fr.p(u, v, 0.0015) for u, v in shield], "Floor", fr.n)        # chiselled, rougher, darker
    for a, b in zip(shield, shield[1:] + shield[:1]):
        seg(g, fr, a, b, 0.02, 0.0, 0.004, "Stone")
    # what the chisel missed: a wing tip of the gull and a corner of the crown
    polyline(g, fr, [(0.28, 0.12), (0.37, 0.24), (0.4, 0.38)], 0.03, 0.0, 0.012, "Stone")
    polyline(g, fr, [(-0.38, 0.47), (-0.3, 0.58), (-0.26, 0.5)], 0.025, 0.0, 0.01, "Stone")

    # -- STEADFAST in gilt letters, nailed upside down across the wall above the hood mould
    fw = wall_frame(0.0, 0.0)
    text(g, fw, "STEADFAST", 0.22, 0.03, 0.0, 0.035, "Bone", v0=6.5, pitch=1.55, flip=True, tilt={8: 0.25})
    # a couple of visible nails on the last tilted letter
    for dv in (0.03, 0.21):
        p = V((-1.5, YB0 - 0.04, 6.5 + dv))
        g.cyl(p, p - V((0, 0.012, 0)), 0.012, 4, "Iron", caps=(False, True), r1=0.008)

    # -- the Lord's arms, carved and painted, on both sides of the niche
    for sx in (-1, 1):
        x = sx * 3.2
        f = wall_frame(x, 4.85)
        bx(g, x - 0.52, x + 0.52, YB0 - 0.05, YB0, 4.1, 5.62, "Stone", 0.015)
        # the shield: black field, stone rim, hook and broken crown
        sh = [(-0.34, 0.5), (0.34, 0.5), (0.34, -0.05), (0.24, -0.35), (0.0, -0.55), (-0.24, -0.35), (-0.34, -0.05)]
        g.prism([(u, v + 0.05) for u, v in sh], f, 0.05, 0.085, "Stone", caps=(False, True))
        g.prism([(u * 0.88, v * 0.88 + 0.05) for u, v in sh], f, 0.085, 0.09, "Iron", caps=(False, True))
        fs = Frame(f.p(0, 0.08, 0), f.u, f.v, f.n)
        hook_and_crown(g, fs, 0.6, 0.09, 0.1, 0.03)
        # motto scroll under the shield (the words come from the notecard)
        scroll = [(-0.42, -0.58), (-0.2, -0.53), (0.2, -0.53), (0.42, -0.58)]
        polyline(g, f, scroll, 0.09, 0.05, 0.07, "Stone")
        # soot from the braziers below, licking up the panel
        patch(g, (x - sx * 0.25, YB0 - 0.0005, 3.75), 0.3, 6, "Iron", r, normal=(0, -1, 0), u=(1, 0, 0),
              sx=0.8, sy=1.0)

    # -- iron pricket candlesticks on the niche sill behind the throne, wax pooled on the stone
    for sx in (-1, 1):
        x, y = sx * 1.32, YB0 + 0.3
        b = V((x, y, DAIS))
        patch(g, b + V((0, 0, 0.002)), 0.16, 6, "Bone", r, sx=1.0, sy=0.7)          # pooled wax
        g.cyl(b, b + V((0, 0, 0.04)), 0.12, 5, "Iron", caps=(False, True), r1=0.09)
        g.cyl(b + V((0, 0, 0.04)), b + V((0, 0, 1.12)), 0.022, 4, "Iron", caps=(False, False))
        top = b + V((0, 0, 1.12))
        g.cyl(top, top + V((0, 0, 0.03)), 0.09, 6, "Iron", caps=(True, True), r1=0.1)
        candle(g, top + V((0, 0, 0.03)), 0.32, 0.04, r, drips=2, n=5)
        g.cyl(top, top - V((0, 0, 0.14)), 0.024, 4, "Bone", caps=(False, False), r1=0.004)


# ================================================================== N_Back_W
@decorates("N_Back_W")
def n_back_w(g, lod):
    if lod != 0:
        return
    cx, cz = -9.0, 2.9
    W, H = 2.4, 1.5
    r = rng("throne-back-w")
    lord_banner_device(g, -6.4, r)
    half_candle_crown(g, -5.1, 2.75, r)

    # -- the Lord's chart of the Narrows in a gilt frame
    f = wall_frame(cx, cz)
    # gilt frame with corner bosses
    for a, b in (((-W / 2, -H / 2), (W / 2, -H / 2)), ((W / 2, -H / 2), (W / 2, H / 2)),
                 ((W / 2, H / 2), (-W / 2, H / 2)), ((-W / 2, H / 2), (-W / 2, -H / 2))):
        seg(g, f, (a[0] * 0.97, a[1] * 0.96), (b[0] * 0.97, b[1] * 0.96), 0.07, 0.0, 0.05, "Bone")
    for su in (-1, 1):
        for sv in (-1, 1):
            g.prism([(su * W * 0.485 + du, sv * H * 0.48 + dv) for du, dv in
                     ((-0.06, 0), (0, -0.06), (0.06, 0), (0, 0.06))], f, 0.05, 0.06, "Bone", caps=(False, True))
    # crest on the top rail: the hook
    polyline(g, f, [(0, H / 2 + 0.02), (0, H / 2 + 0.13), (0.05, H / 2 + 0.17)], 0.025, 0.0, 0.055, "Bone")
    # the chart itself (parchment), a little proud, slightly cockled
    pw, ph = W * 0.97 - 0.07, H * 0.96 - 0.07
    nx, nz = 3, 2
    grid = [[f.p(-pw / 2 + pw * i / nx, -ph / 2 + ph * j / nz, 0.012 + 0.006 * ((i + j) % 2)) for j in range(nz + 1)]
            for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nz):
            g.face([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "Cloth", f.n)
    D0, D1 = 0.019, 0.021
    # black rock: the coast of the Narrows and the Widow's Tooth
    coast_n = [(-1.05, 0.55), (-0.8, 0.42), (-0.55, 0.47), (-0.3, 0.3), (0.0, 0.35), (0.25, 0.22), (0.55, 0.3),
               (0.8, 0.18), (1.05, 0.25)]
    coast_s = [(-1.05, -0.45), (-0.7, -0.35), (-0.4, -0.5), (-0.1, -0.38), (0.2, -0.48), (0.5, -0.32),
               (0.75, -0.42), (1.05, -0.35)]
    polyline(g, f, coast_n, 0.012, D0, D1, "Iron")
    polyline(g, f, coast_s, 0.012, D0, D1, "Iron")
    tooth = (0.12, -0.02)
    g.prism([(tooth[0] + 0.05 * math.cos(a), tooth[1] + 0.035 * math.sin(a)) for a in
             [2 * math.pi * k / 5 for k in range(5)]], f, D0 - 0.002, D1, "Iron", caps=(False, True))
    # the circle round the Tooth, drawn many times over
    for k in range(3):
        rr = 0.12 + 0.012 * k
        ring = [(tooth[0] + rr * math.cos(a + k), tooth[1] + rr * 0.8 * math.sin(a + k))
                for a in [2 * math.pi * i / 10 for i in range(11)]]
        polyline(g, f, ring, 0.006, D0, D1 + 0.001, "Iron")
    # Crown patrol lines (red: rust) as dashes, wrecks as crosses, the Lord's ships as little gilt hooks
    for line in ([(-1.0, 0.1), (-0.1, 0.12)], [(0.4, -0.2), (1.0, -0.2)]):
        for (a, b) in zip(line, line[1:]):
            for t in (0.0, 0.4):
                p = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
                q = (a[0] + (b[0] - a[0]) * (t + 0.25), a[1] + (b[1] - a[1]) * (t + 0.25))
                seg(g, f, p, q, 0.01, D0, D1, "Iron")
    for (u, v) in ((0.3, 0.12), (0.65, -0.05)):
        seg(g, f, (u - 0.03, v - 0.03), (u + 0.03, v + 0.03), 0.008, D0, D1, "Iron")
        seg(g, f, (u - 0.03, v + 0.03), (u + 0.03, v - 0.03), 0.008, D0, D1, "Iron")
    for (u, v) in ((-0.85, -0.05), (0.5, 0.05)):
        polyline(g, f, [(u, v + 0.05), (u, v - 0.02), (u - 0.025, v - 0.035), (u - 0.04, v - 0.01)], 0.008,
                 D0, D1 + 0.002, "Bone")
    # compass rose
    cr = (-0.8, -0.18)
    for a in range(8):
        L = 0.11 if a % 2 == 0 else 0.06
        ang = math.pi / 4 * a
        seg(g, f, cr, (cr[0] + L * math.cos(ang), cr[1] + L * math.sin(ang)), 0.006, D0, D1, "Iron")
    # hung from a spike by a cord
    nail = V((cx, YB0 - 0.03, cz + H / 2 + 0.38))
    g.cyl(V((cx, YB0, nail.z)), nail, 0.012, 4, "Iron", caps=(False, True))
    for su in (-1, 1):
        g.sweep([nail, V((cx + su * W * 0.42, YB0 - 0.035, cz + H / 2 - 0.02))], 0.006, 3, "Straw", caps=False)
    # damp: the chart's lower corner has gone brown
    patch(g, f.p(-0.95, -0.55, D0 - 0.003), 0.12, 7, "Floor", r, normal=f.n, u=f.u)


# ================================================================== N_Back_E
def sabre(g, fr, c, ang, L, rnd):
    """Crown officer's sabre on a wall frame: blade (blackening Iron), gilt hilt; hilt at c, blade along ang."""
    d = V((math.cos(ang), math.sin(ang)))
    s = V((-d.y, d.x))
    c = V(c)
    pts = []
    for k in range(4):
        t = k / 3
        p = c + d * (0.16 + L * t) + s * (0.04 * t * t)
        pts.append(fr.p(p.x, p.y, 0.035))
    g.sweep(pts, 0.012, 3, "Iron", caps=False)
    # gilt hilt: guard, grip (leather), pommel
    gp = [fr.p(*(c + d * 0.16 + s * 0.06), 0.035), fr.p(*(c + d * 0.16 - s * 0.06), 0.035)]
    g.cyl(gp[0], gp[1], 0.012, 4, "Bone")
    g.cyl(fr.p(*(c + d * 0.15), 0.035), fr.p(*(c + d * 0.03), 0.035), 0.016, 4, "Cloth", caps=(False, False))
    g.cyl(fr.p(*(c + d * 0.03), 0.035), fr.p(*(c - d * 0.02), 0.035), 0.022, 5, "Bone", r1=0.012)


@decorates("N_Back_E")
def n_back_e(g, lod):
    if lod != 0:
        return
    bx0, bz_top = 9.6, 5.9          # Crown banner: centre x, iron bar height
    W, H = 1.1, 2.55
    r = rng("throne-back-e")
    lord_banner_device(g, 6.4, r)
    half_candle_crown(g, 5.1, 2.75, r)

    # -- the Crown banner, hung upside down from an iron bar; its hoist sleeve now at the bottom
    g.cyl(V((bx0 - 0.62, YB0 - 0.11, bz_top)), V((bx0 + 0.62, YB0 - 0.11, bz_top)), 0.018, 6, "Iron")
    for sx in (-0.57, 0.57):
        g.cyl(V((bx0 + sx, YB0, bz_top)), V((bx0 + sx, YB0 - 0.13, bz_top)), 0.014, 4, "Iron")
    nx, nz = 5, 8
    grid = []
    for i in range(nx + 1):
        row = []
        for j in range(nz + 1):
            u = -W / 2 + W * i / nx
            z = bz_top - 0.03 - H * j / nz
            if j == 0:      # the old fly end, ragged, now at the top: it hangs from rings
                z -= 0.02 * (i % 2)
            y = YB0 - 0.1 - 0.025 * math.sin(i * 1.7 + j * 1.1)
            row.append(V((bx0 + u, y, z)))
        grid.append(row)
    cut = {(4, j) for j in range(0, 5)} | {(3, 0), (3, 1)}       # the strip cut away for the Kennel
    for i in range(nx):
        for j in range(nz):
            if (i, j) in cut:
                continue
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
            g.face(q, "Cloth", (0, -1, 0))
            g.face([p + V((0, 0.005, 0)) for p in q], "Cloth", (0, 1, 0))
    for i in (0, 1, 2, 3):              # rings on the bar
        p = grid[i][0] + V((W / nx * 0.5 * (i % 2), 0, 0))
        g.link(V((p.x, YB0 - 0.11, bz_top - 0.01)), V((0, 0, 1)), V((0, 1, 0)), 0.025, 0.025, 0.004, 6, 3, "Iron")
    # the hoist sleeve, now at the bottom, frayed
    a = grid[0][nz] + V((0, -0.01, 0.0))
    b = grid[nx][nz] + V((0, -0.01, 0.0))
    g.cyl(a, b, 0.025, 5, "Cloth")
    for i in range(6):
        p = a.lerp(b, (i + 0.5) / 6)
        g.sweep([p, p + V((r.uniform(-0.02, 0.02), -0.005, -r.uniform(0.06, 0.15)))], 0.004, 3, "Cloth", caps=False)

    def surf(u, z):
        fi = (u + W / 2) / W * nx
        fj = (bz_top - 0.03 - z) / H * nz
        i0, j0 = max(0, min(nx - 1, int(fi))), max(0, min(nz - 1, int(fj)))
        a_, b_ = fi - i0, fj - j0
        p = (grid[i0][j0] * (1 - a_) * (1 - b_) + grid[i0 + 1][j0] * a_ * (1 - b_)
             + grid[i0][j0 + 1] * (1 - a_) * b_ + grid[i0 + 1][j0 + 1] * a_ * b_)
        return p - V((bx0, 0, 0)) + V((bx0, 0, 0))
    # the red gull (rust), diving: upside down its wings open downward, its beak pointing at the sky
    gz = 4.4
    gull = [[(-0.36, gz - 0.12), (-0.2, gz - 0.02), (-0.06, gz - 0.08), (0.0, gz + 0.02)],
            [(0.0, gz + 0.02), (0.06, gz - 0.08), (0.2, gz - 0.02), (0.36, gz - 0.12)],
            [(0.0, gz + 0.02), (0.0, gz + 0.16), (0.03, gz + 0.22)],
            [(-0.04, gz - 0.02), (0.0, gz - 0.12), (0.04, gz - 0.02)]]
    lines = [[(x - bx0 if False else x, z) for x, z in L] for L in gull]
    for line in lines:
        for (u0, z0), (u1, z1) in zip(line, line[1:]):
            n = max(1, int(math.hypot(u1 - u0, z1 - z0) / 0.1) + 1)
            du, dz = u1 - u0, z1 - z0
            L_ = math.hypot(du, dz)
            su, sz = -dz / L_ * 0.03, du / L_ * 0.03
            pts = [(u0 + du * k / n, z0 + dz * k / n) for k in range(n + 1)]
            for (p0, q0), (p1, q1) in zip(pts, pts[1:]):
                quad = [surf(p0 - su, q0 - sz), surf(p1 - su, q1 - sz), surf(p1 + su, q1 + sz), surf(p0 + su, q0 + sz)]
                g.face([p - V((0, 0.006, 0)) for p in quad], "Iron", (0, -1, 0))
    # a gilt fringe remnant along the old fly end (now the top)
    for i in range(nx - 2):
        p = grid[i][0]
        q = grid[i + 1][0]
        for k in range(3):
            s0 = p.lerp(q, (k + 0.5) / 3) - V((0, 0.007, 0.01))
            g.face([s0, s0 + V((0.012, 0, 0)), s0 + V((0.006, 0, -0.07))], "Bone", (0, -1, 0))

    # -- Crown officers' swords, in a fan, gilt hilts out, blades blackening
    fc = wall_frame(7.95, 3.85)
    g.prism([(0.1 * math.cos(a), 0.1 * math.sin(a)) for a in [2 * math.pi * k / 6 for k in range(6)]],
            fc, 0.0, 0.025, "Wood", caps=(False, True))
    for k in range(4):
        ang = math.pi + (k - 1.5) * 0.5
        hilt = (0.75 * math.cos(ang), 0.75 * math.sin(ang))
        sabre(g, fc, hilt, ang + math.pi, 0.48, r)
        p = fc.p(0.62 * math.cos(ang), 0.62 * math.sin(ang), 0.0)
        g.cyl(p, p + fc.n * 0.05, 0.01, 3, "Wood", caps=(False, True))


# ================================================================== N_Wall_W
@decorates("N_Wall_W")
def n_wall_w(g, lod):
    if lod != 0:
        return
    r = rng("throne-flood")
    x = -11.6 + EPS
    # the flood line of Year VII: an incised level line and a crust of salt under it
    g.face([V((x, 11.9, 0.84)), V((x, 15.15, 0.84)), V((x, 15.15, 0.852)), V((x, 11.9, 0.852))], "Iron", (1, 0, 0))
    pts_top = [V((x, 11.9 + 3.25 * k / 16, 0.835)) for k in range(17)]
    pts_bot = [V((x, p.y, 0.835 - r.uniform(0.02, 0.09))) for p in pts_top]
    for k in range(16):
        g.face([pts_bot[k], pts_bot[k + 1], pts_top[k + 1], pts_top[k]], "Bone", (1, 0, 0))
    # a couple of tide streaks running down to the floor
    for y, z1 in ((12.3, 0.72), (13.6, 0.6), (14.7, 0.68)):
        g.face([V((x, y, 0.41)), V((x, y + 0.015, 0.41)), V((x, y + 0.01, z1)), V((x, y, z1))], "Bone", (1, 0, 0))
    # FLOOD Y7 cut above the line at its north end
    fr = Frame((x, 0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0))
    text(g, fr, "FLOOD Y7", 0.07, 0.009, 0.0, EPS, "Iron", u0=-14.95, v0=0.87, pitch=1.15)


# ================================================================== N_Dais
@decorates("N_Dais")
def n_dais(g, lod):
    if lod != 0:
        return
    # gilt nail heads set along the chamfered front edge of the top step (y 12.6, z 1.3)
    nrm = V((0, -1, 1)).normalized()
    for k in range(25):
        x = -2.95 + 5.9 * k / 24
        p = V((x, 12.6125 - 0.001, DAIS - 0.0125 - 0.001))
        g.cyl(p, p + nrm * 0.004, 0.008, 4, "Bone", caps=(False, True), r1=0.005, phase=k * 0.4)
    # KNEEL cut into the centre of the lowest riser (y = 11.31), worn in the middle
    yr = 13.255 - 3.89 / 2
    fr = Frame((0, yr, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    text(g, fr, "KNEEL", 0.13, 0.018, 0.0, EPS, "Iron", v0=0.44, pitch=1.3)
    # the knees have worn the middle of the word pale and smooth
    r = rng("throne-kneel")
    for u in (-0.14, 0.14):
        patch(g, fr.p(u, 0.5, EPS * 1.5), 0.07, 8, "Stone", r, normal=fr.n, u=fr.u, sx=1.2, sy=0.6)


# ================================================================== N_Throne
@decorates("N_Throne")
def n_throne(g, lod):
    if lod != 0:
        return
    r = rng("throne-story")
    cy = 14.55
    # gilt circlets on the post skulls (the Governor's buttons)
    for sx in (-1, 1):
        c = V((sx * 0.75, cy + 0.39, DAIS + 3.22 + 0.077))
        lo, hi = ering(g, c, 0.06, 0.071, 0.018, 9, "Bone", shrink=0.9)
        for k in range(0, 9, 2):
            p = (lo[k] + hi[k]) / 2
            g.cyl(p, p + V((0, 0, 0.035)) + (p - c).normalized() * 0.004 * 0, 0.009, 3, "Bone", caps=(False, False),
                  r1=0.0)
    # thirty-one gilt studs along the arms: sixteen on the west arm, fifteen on the east and room for more
    for sx, n in ((-1, 16), (1, 15)):
        for k in range(n):
            y = cy - 0.51 + 0.86 * k / 15
            p = V((sx * 0.62, y, DAIS + 1.02))
            g.cyl(p, p + V((0, 0, 0.004)), 0.011, 5, "Bone", caps=(False, True), r1=0.007)
    # carved scroll terminals on the arm fronts
    for sx in (-1, 1):
        x = sx * 0.62
        g.sweep([V((x, cy - 0.555, DAIS + 1.0)), V((x, cy - 0.6, DAIS + 0.95)), V((x, cy - 0.585, DAIS + 0.88)),
                 V((x, cy - 0.55, DAIS + 0.9))], 0.03, 5, "Wood")
    # the Lord's spyglass, hooked on the outside of the east arm
    hook_p = V((0.74, cy + 0.1, DAIS + 0.9))
    g.sweep([hook_p, hook_p + V((0.06, 0, -0.02)), hook_p + V((0.07, 0, 0.02))], 0.006, 4, "Iron")
    a, b = V((0.8, cy - 0.1, DAIS + 0.85)), V((0.8, cy + 0.3, DAIS + 0.85))
    g.cyl(a, a.lerp(b, 0.45), 0.024, 7, "Bone", r1=0.024)                      # brass draw tube
    g.cyl(a.lerp(b, 0.45), b, 0.03, 7, "Cloth", r1=0.032)                       # leather barrel
    for t, rr in ((0.45, 0.034), (0.98, 0.036)):
        p = a.lerp(b, t)
        g.cyl(p, p + V((0, 0.02, 0)), rr, 7, "Bone", caps=(False, False))
    # the hook and broken crown, gilt on a carved wooden cartouche, on the high back
    f = Frame((0, cy + 0.3, DAIS + 2.5), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    oval = [(0.25 * math.cos(a_), 0.29 * math.sin(a_)) for a_ in [2 * math.pi * k / 12 for k in range(12)]]
    g.prism(oval, f, 0.0, 0.006, "Wood", caps=(False, True))
    polyline(g, f, oval + oval[:1], 0.02, 0.004, 0.009, "Wood")
    hook_and_crown(g, Frame(f.p(0, -0.02, 0), f.u, f.v, f.n), 0.42, 0.006, 0.009, 0.022)
    # carved rope bands on the back posts (Reed's knots)
    for sx in (-1, 1):
        for z in (DAIS + 1.4, DAIS + 2.6):
            for k in range(3):
                zz = z + k * 0.04
                g.cyl(V((sx * 0.75, cy + 0.27, zz)), V((sx * 0.75, cy + 0.27, zz + 0.03)), 0.0, 3, "Wood")
                bx(g, sx * 0.75 - 0.085, sx * 0.75 + 0.085, cy + 0.27, cy + 0.29, zz, zz + 0.025, "Wood")
    # 77 scratched small into the plinth's front
    fp = Frame((0, cy - 0.6, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    text(g, fp, "77", 0.07, 0.008, 0.0, 0.0015, "Iron", v0=DAIS + 0.065)
    # the Lord's cup on the plinth under his right hand, and the rings it leaves
    cup = V((0.8, cy - 0.5, DAIS + 0.2))
    g.cyl(cup, cup + V((0, 0, 0.012)), 0.04, 7, "Bone", caps=(False, True), r1=0.03)
    g.cyl(cup + V((0, 0, 0.012)), cup + V((0, 0, 0.09)), 0.009, 5, "Bone", caps=(False, False))
    g.cyl(cup + V((0, 0, 0.09)), cup + V((0, 0, 0.165)), 0.012, 8, "Bone", caps=(True, False), r1=0.042)
    patch(g, cup + V((0, 0, 0.163)), 0.036, 8, "Iron", r, jitter=0.0)        # wine
    for d, rr in ((V((-0.05, 0.08, 0)), 0.04), (V((0.03, 0.16, 0)), 0.042), (V((-0.02, 0.24, 0)), 0.04)):
        p = cup + d + V((0, 0, 0.001))
        ring = [p + V((math.cos(a_) * rr, math.sin(a_) * rr, 0)) for a_ in [2 * math.pi * k / 10 for k in range(11)]]
        for q0, q1 in zip(ring, ring[1:]):
            g.face([q0, q1, q1 + (q1 - p).normalized() * 0.006, q0 + (q0 - p).normalized() * 0.006], "Iron",
                   (0, 0, 1))
    # a fat candle stub on the other front corner, its wax run over the plinth's edge
    cs = V((-0.8, cy - 0.5, DAIS + 0.2))
    patch(g, cs + V((0, -0.01, 0.002)), 0.07, 9, "Bone", r)
    g.face([V((-0.84, cy - 0.6 - 0.0015, DAIS + 0.2)), V((-0.77, cy - 0.6 - 0.0015, DAIS + 0.2)),
            V((-0.79, cy - 0.6 - 0.0015, DAIS + 0.09)), V((-0.82, cy - 0.6 - 0.0015, DAIS + 0.05))], "Bone", (0, -1, 0))
    candle(g, cs + V((0, 0, 0.003)), 0.07, 0.035, r, drips=3, n=7)
    # gnawed bones at the foot of the throne, kicked under the plinth's lip
    long_bone(g, (-0.78, cy - 0.7, DAIS + 0.02), (-0.42, cy - 0.76, DAIS + 0.02), 0.016, gnawed=True)
    long_bone(g, (0.42, cy - 0.66, DAIS + 0.014), (0.6, cy - 0.78, DAIS + 0.014), 0.011, gnawed=True)
    g.sweep([V((-0.3, cy - 0.69, DAIS + 0.008)), V((-0.22, cy - 0.74, DAIS + 0.012)),
             V((-0.12, cy - 0.73, DAIS + 0.008))], 0.007, 3, "Bone")               # a rib
    for k in range(4):                                                            # knuckles
        p = V((r.uniform(-0.9, -0.3), cy - r.uniform(0.66, 0.8), DAIS + 0.008))
        g.blob(p, 0.012, 0.009, 0.01, 5, 1, "Bone", r, 0.2)
    long_bone(g, (-0.94, cy - 0.3, DAIS + 0.016), (-0.94, cy + 0.15, DAIS + 0.016), 0.016, gnawed=True)


# ================================================================== N_Kneeling_Stone
@decorates("N_Kneeling_Stone")
def n_kneeling_stone(g, lod):
    if lod != 0:
        return
    r = rng("throne-kneel-stone")
    c = V((0, 13.15, DAIS))
    top = DAIS + 0.28 + 0.0008
    # two knee hollows, polished and darkened by every presentation
    for sx in (-1, 1):
        patch(g, (sx * 0.15, 13.1, top), 0.1, 10, "Floor", r, jitter=0.08, sx=0.8, sy=1.2)
    # initials crowding the upper edges
    fr = Frame((0, 0, top), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    inits = ["JP", "MK", "TW", "AR", "BC", "HO", "OT", "KF", "WA", "RB", "SM", "J", "77"]
    k = 0
    for row_v in (12.93, 13.37):
        u = -0.36
        while u < 0.3 and k < len(inits):
            s = inits[k]
            text(g, fr, s, 0.035, 0.005, 0.0, 0.0008, "Iron", u0=u, v0=row_v - 0.0175, pitch=1.0)
            u += 0.035 * len(s) + 0.05 + r.uniform(0, 0.03)
            k += 1
    # tally strokes in fives along the west end
    for j in range(3):
        for i in range(5):
            u = -0.37 + 0.012 * i
            v = 13.0 + j * 0.1
            if i < 4:
                seg(g, fr, (u, v), (u, v + 0.05), 0.004, 0.0, 0.0008, "Iron")
        seg(g, fr, (-0.38, 13.0 + j * 0.1), (-0.325, 13.05 + j * 0.1), 0.004, 0.0, 0.0008, "Iron")
    # a leather slave collar left on the stone, its strap hanging over the east edge, iron ring and buckle
    cc = V((0.24, 13.2, top))
    pts = [cc + V((0.06 * math.cos(a), 0.05 * math.sin(a), 0.002)) for a in [2 * math.pi * k / 10 for k in range(10)]]
    pts = pts[1:] + [cc + V((0.12, -0.03, 0.002)), V((0.39, 13.16, top + 0.002)), V((0.448, 13.15, top - 0.02)),
                     V((0.455, 13.14, top - 0.12)), V((0.455, 13.15, top - 0.17))]
    strap(g, pts, (0, 0, 1), 0.03, 0.004, "Cloth")
    g.link(cc + V((-0.062, 0, 0.004)), V((0, 1, 0)), V((1, 0, 0)), 0.018, 0.018, 0.0035, 8, 3, "Iron")
    g.link(V((0.459, 13.15, top - 0.09)), V((0, 0, 1)), V((0, 1, 0)), 0.02, 0.016, 0.003, 8, 3, "Iron")
    # straw strewn before the stone, never cleared
    for k in range(14):
        p = V((r.uniform(-0.4, 0.5), r.uniform(12.62, 12.84), DAIS + 0.004))
        a = r.uniform(0, 6.28)
        d = V((math.cos(a), math.sin(a), 0)) * r.uniform(0.05, 0.12)
        g.face([p, p + d, p + d + V((0.006, 0.006, 0)), p + V((0.006, 0.006, 0))], "Straw", (0, 0, 1))


# ================================================================== N_Brazier_W / N_Brazier_E
def scorch(g, cx, cy, rnd):
    """A black sun burnt into the dais round the brazier, and the freckles of fallen embers."""
    z = DAIS + 0.0012
    c = V((cx, cy, z))
    patch(g, c, 0.5, 14, "Iron", rnd, jitter=0.12)
    for k in range(10):
        a = 2 * math.pi * k / 10 + rnd.uniform(-0.15, 0.15)
        d = V((math.cos(a), math.sin(a), 0))
        s = V((-d.y, d.x, 0))
        L = rnd.uniform(0.58, 0.7)
        g.face([c + d * 0.45 - s * 0.04 + V((0, 0, 0.0004)), c + d * 0.45 + s * 0.04 + V((0, 0, 0.0004)),
                c + d * L + V((0, 0, 0.0004))], "Iron", (0, 0, 1))
    for k in range(8):
        a = rnd.uniform(0, 6.28)
        p = c + V((math.cos(a), math.sin(a), 0)) * rnd.uniform(0.55, 0.72) + V((0, 0, 0.0004))
        patch(g, p, rnd.uniform(0.008, 0.02), 5, "Iron", rnd)


@decorates("N_Brazier_W")
def n_brazier_w(g, lod):
    if lod != 0:
        return
    r = rng("throne-coronet")
    c = V((-2.3, 14.0, DAIS + 0.95))     # bowl rim centre
    R = 0.62
    # the Governor's coronet beaten into a band of gilt spikes nailed round the rim
    ering(g, c + V((0, 0, -0.035)), R + 0.02, R + 0.02, 0.05, 20, "Bone")
    for k in range(16):
        a = 2 * math.pi * k / 16
        d = V((math.cos(a), math.sin(a), 0))
        p = c + d * (R + 0.012) + V((0, 0, 0.01))
        h = 0.11 if k % 2 == 0 else 0.06
        lean = d * (0.03 if k % 5 == 3 else 0.008)
        g.cyl(p, p + V((0, 0, h)) + lean, 0.016, 3, "Bone", caps=(False, False), r1=0.0, phase=a)
        if k % 4 == 0:
            g.blob(p + d * 0.012 + V((0, 0, -0.012)), 0.012, 0.012, 0.012, 5, 1, "Bone", r, 0.0)
    scorch(g, -2.3, 14.0, r)


@decorates("N_Brazier_E")
def n_brazier_e(g, lod):
    if lod != 0:
        return
    r = rng("throne-chain-of-office")
    c = V((2.3, 14.0, DAIS + 0.95))
    R = 0.66
    # the Governor's chain of office in four swags round the bowl; blackened on the fire side
    nsw, nl = 4, 9
    for s in range(nsw):
        a0 = 2 * math.pi * s / nsw + 0.4
        a1 = 2 * math.pi * (s + 1) / nsw + 0.4
        pts = []
        for k in range(nl + 1):
            t = k / nl
            a = a0 + (a1 - a0) * t
            z = c.z - 0.03 - 0.17 * 4 * t * (1 - t)
            rr = R + 0.02 * 4 * t * (1 - t)
            pts.append(V((c.x + math.cos(a) * rr, c.y + math.sin(a) * rr, z)))
        for k in range(nl):
            p, q = pts[k], pts[k + 1]
            m = (p + q) / 2
            tdir = (q - p).normalized()
            radial = V((m.x - c.x, m.y - c.y, 0)).normalized()
            mat = "Iron" if m.y > c.y + 0.25 else "Bone"
            side = tdir.cross(radial).normalized()
            hl = (q - p).length * 0.42
            corners = [m - tdir * hl - side * 0.012, m + tdir * hl - side * 0.012, m + tdir * hl + side * 0.012,
                       m - tdir * hl + side * 0.012]
            g.face(corners, mat, radial)
            g.face([v - radial * 0.006 for v in corners], mat, -radial)
            for i in range(4):
                j = (i + 1) % 4
                g.face_c([corners[i], corners[j], corners[j] - radial * 0.006, corners[i] - radial * 0.006], mat, m)
        # hook on the rim holding the swag
        g.sweep([pts[0] + V((0, 0, 0.06)), pts[0] + V((0, 0, 0.0))], 0.006, 3, "Bone", caps=False)
    # the badge of office hanging in front, toward the hall: a gilt plaque with the red gull hammered off
    a = 2 * math.pi * 3 / nsw + 0.4 + math.pi / nsw
    d = V((math.cos(a), math.sin(a), 0))
    p = V((c.x, c.y, 0)) + d * (R + 0.03) + V((0, 0, c.z - 0.25))
    g.cyl(p - d * 0.008, p + d * 0.008, 0.06, 8, "Bone")
    g.cyl(p + d * 0.008, p + d * 0.011, 0.035, 6, "Iron", caps=(False, True))
    scorch(g, 2.3, 14.0, r)


# ================================================================== N_Props_W
def chart_roll(g, a, b, r, rnd):
    a, b = V(a), V(b)
    g.cyl(a, b, r, 6, "Cloth")
    t = (b - a).normalized()
    for f_ in (0.3, 0.7):
        p = a.lerp(b, f_)
        g.cyl(p - t * 0.006, p + t * 0.006, r * 1.12, 6, "Straw", caps=(False, False))


@decorates("N_Props_W")
def n_props_w(g, lod):
    if lod != 0:
        return
    r = rng("throne-props-w")
    # -- a worn, rich rug under the lectern
    x0, x1, y0, y1 = -10.62, -9.22, 13.82, 14.62
    z = FL + 0.006
    g.face([V((x0, y0, z)), V((x1, y0, z)), V((x1, y1, z)), V((x0, y1, z))], "Cloth", (0, 0, 1))
    for (a, b, c_, d) in ((x0 + 0.06, y0 + 0.06, x1 - 0.06, y0 + 0.1), (x0 + 0.06, y1 - 0.1, x1 - 0.06, y1 - 0.06),
                          (x0 + 0.06, y0 + 0.06, x0 + 0.1, y1 - 0.06), (x1 - 0.1, y0 + 0.06, x1 - 0.06, y1 - 0.06)):
        g.face([V((a, b, z + 0.001)), V((c_, b, z + 0.001)), V((c_, d, z + 0.001)), V((a, d, z + 0.001))], "Bone",
               (0, 0, 1))
    g.face([V((-10.1, 14.05, z + 0.001)), V((-9.9, 14.22, z + 0.001)), V((-9.7, 14.05, z + 0.001)),
            V((-9.9, 13.9, z + 0.001))], "Bone", (0, 0, 1))
    patch(g, (-9.5, 13.95, z + 0.0015), 0.12, 8, "Floor", r)                    # mud from boots
    for k in range(10):                                                         # fringe
        for xx in (x0, x1):
            y = y0 + 0.04 + (y1 - y0 - 0.08) * k / 9
            sgn = -1 if xx == x0 else 1
            g.face([V((xx, y, z)), V((xx, y + 0.02, z)), V((xx + sgn * 0.05, y + 0.012, FL + 0.002))], "Cloth",
                   (0, 0, 1))

    # -- the lectern: ledger, letters, inkpot, quill and a candle
    lc = V((-9.92, 14.25, FL))
    for a in (0.0, math.pi / 2):                                   # crossed feet
        d = V((math.cos(a), math.sin(a), 0)) * 0.26
        bx(g, *(sorted((lc.x - d.x - 0.03 * (a > 0), lc.x + d.x + 0.03 * (a > 0)))),
           *(sorted((lc.y - d.y - 0.03 * (a == 0), lc.y + d.y + 0.03 * (a == 0)))), z, z + 0.06, "Wood", 0.008)
    bx(g, lc.x - 0.05, lc.x + 0.05, lc.y - 0.05, lc.y + 0.05, z + 0.06, FL + 1.0, "Wood", 0.01)
    for z_ in (FL + 0.3, FL + 0.95):
        bx(g, lc.x - 0.065, lc.x + 0.065, lc.y - 0.065, lc.y + 0.065, z_, z_ + 0.04, "Wood", 0.008)
    tilt = 0.42
    desk = Frame(lc + V((0, 0, 1.1)), (1, 0, 0), (0, math.cos(tilt), math.sin(tilt)),
                 (0, -math.sin(tilt), math.cos(tilt)))
    g.prism([(-0.32, -0.22), (0.32, -0.22), (0.32, 0.22), (-0.32, 0.22)], desk, -0.03, 0.0, "Wood")
    g.prism([(-0.32, -0.25), (0.32, -0.25), (0.32, -0.22), (-0.32, -0.22)], desk, -0.03, 0.03, "Wood")   # lip
    # open ledger: cover, two fanned page blocks, a ribbon
    g.prism([(-0.28, -0.2), (0.28, -0.2), (0.28, 0.19), (-0.28, 0.19)], desk, 0.0, 0.008, "Cloth",
            caps=(False, True))
    for su in (-1, 1):
        pg = [desk.p(su * 0.01, -0.19, 0.008), desk.p(su * 0.26, -0.19, 0.008), desk.p(su * 0.26, 0.18, 0.008),
              desk.p(su * 0.01, 0.18, 0.008)]
        hi = [p + desk.n * 0.022 for p in pg]
        hi[0] -= desk.n * 0.012
        hi[3] -= desk.n * 0.012
        g.face(hi, "Cloth", desk.n)
        for i in range(4):
            j = (i + 1) % 4
            g.face_c([pg[i], pg[j], hi[j], hi[i]], "Cloth", (pg[0] + pg[2]) / 2 + desk.n * 0.01)
        for k in range(9):                                         # lines of the Lord's tally
            v = 0.14 - k * 0.035
            L = 0.2 if k % 4 else 0.12
            a_ = desk.p(su * 0.03 if su > 0 else -0.03 - L, v, 0.0302)
            b_ = desk.p(su * 0.03 + L if su > 0 else -0.03, v, 0.0302)
            g.face([a_, b_, b_ - desk.v * 0.006, a_ - desk.v * 0.006], "Iron", desk.n)
    g.sweep([desk.p(0.0, 0.18, 0.02), desk.p(0.01, -0.1, 0.031), desk.p(0.03, -0.24, 0.02),
             desk.p(0.04, -0.33, -0.02)], 0.004, 3, "Bone", caps=False)        # gilt silk ribbon
    # sealed letter tucked in the ledger, sticking out
    lt = [desk.p(0.12, 0.17, 0.031), desk.p(0.26, 0.22, 0.031), desk.p(0.22, 0.32, 0.031), desk.p(0.08, 0.27, 0.031)]
    g.face(lt, "Cloth", desk.n)
    g.face(lt[::-1], "Cloth", -desk.n)
    g.cyl(desk.p(0.17, 0.26, 0.031), desk.p(0.17, 0.26, 0.036), 0.012, 6, "Iron", caps=(False, True))
    # side shelf: inkpot and quill, candle in a pricket
    sh = lc + V((0.22, 0.0, 0.92))
    bx(g, sh.x - 0.1, sh.x + 0.1, sh.y - 0.08, sh.y + 0.08, sh.z - 0.025, sh.z, "Wood", 0.006)
    bx(g, lc.x + 0.05, sh.x - 0.08, sh.y - 0.02, sh.y + 0.02, sh.z - 0.07, sh.z - 0.025, "Wood")
    ip = sh + V((-0.04, -0.02, 0))
    g.cyl(ip, ip + V((0, 0, 0.05)), 0.03, 7, "Iron", caps=(False, True), r1=0.022)
    g.sweep([ip + V((0, 0, 0.03)), ip + V((0.04, 0.02, 0.15)), ip + V((0.07, 0.04, 0.24))], 0.003, 3, "Bone",
            caps=False)
    g.face([ip + V((0.035, 0.01, 0.13)), ip + V((0.075, 0.03, 0.24)), ip + V((0.055, 0.06, 0.2))], "Bone",
           (-1, 1, 0))
    cp = sh + V((0.05, 0.03, 0))
    patch(g, cp + V((0, 0, 0.001)), 0.045, 7, "Bone", r)
    candle(g, cp, 0.11, 0.022, r, drips=3)

    # -- the chart rolls, tied with Reed's knots, in a wicker basket by the lectern
    bc = V((-10.45, 14.05, FL))
    g.cyl(bc, bc + V((0, 0, 0.42)), 0.15, 9, "Straw", caps=(True, False), r1=0.19)
    for k in range(6):
        a = 2 * math.pi * k / 6 + 0.3
        base_ = bc + V((math.cos(a) * 0.08, math.sin(a) * 0.08, 0.05))
        tip = base_ + V((math.cos(a) * 0.14, math.sin(a) * 0.14, r.uniform(0.62, 0.8)))
        chart_roll(g, base_, tip, r.uniform(0.028, 0.04), r)

    # -- the working chart over the top bale, weighted with dividers and a candle stub
    bz = FL + 0.9 + 0.003
    ang = 0.08
    ca, sa = math.cos(ang), math.sin(ang)
    o = V((-8.0, 14.45, bz))
    u, v = V((ca, sa, 0)), V((-sa, ca, 0))
    cw, chh = 0.45, 0.24
    corners = [o - u * cw - v * chh, o + u * cw - v * chh, o + u * cw + v * chh, o - u * cw + v * chh]
    g.face(corners, "Cloth", (0, 0, 1))
    # the front edge droops over the bale
    fd = [corners[0], corners[1], corners[1] - v * 0.03 - V((0, 0, 0.12)), corners[0] - v * 0.03 - V((0, 0, 0.1))]
    g.face(fd, "Cloth", -v + V((0, 0, 0.3)))
    for (a_, b_) in (((-0.35, 0.1), (0.05, 0.15)), ((0.05, 0.15), (0.38, 0.05)), ((-0.3, -0.12), (0.4, -0.16))):
        p0 = o + u * a_[0] + v * a_[1] + V((0, 0, 0.001))
        p1 = o + u * b_[0] + v * b_[1] + V((0, 0, 0.001))
        g.face([p0, p1, p1 + v * 0.008, p0 + v * 0.008], "Iron", (0, 0, 1))
    xm = o + u * 0.1 + v * 0.0 + V((0, 0, 0.001))                       # the Dead Ebb, crossed in red (rust)
    for d in (u + v, u - v):
        d = d.normalized() * 0.03
        g.face([xm - d, xm + d, xm + d + V((0, 0, 0)) + d.cross(V((0, 0, 1))) * 0.25,
                xm - d + d.cross(V((0, 0, 1))) * 0.25], "Iron", (0, 0, 1))
    # dividers, open across the Narrows
    hinge = o + u * (-0.15) + v * 0.05 + V((0, 0, 0.03))
    for d in (u * 0.13 + v * 0.05, u * 0.1 - v * 0.09):
        g.cyl(hinge, o + u * (-0.15) + v * 0.05 + d + V((0, 0, 0.003)), 0.004, 4, "Bone", caps=(False, False),
              r1=0.0015)
    g.cyl(hinge - V((0, 0, 0.006)), hinge + V((0, 0, 0.006)), 0.01, 6, "Bone")
    # the candle stub weighting the far corner
    cs = o + u * 0.36 + v * 0.17
    patch(g, cs + V((0, 0, 0.001)), 0.05, 8, "Bone", r)
    candle(g, cs, 0.06, 0.024, r, drips=2)
    # lead weights on the near corners
    for p in (corners[0] + u * 0.05 + v * 0.05, corners[3] + u * 0.05 - v * 0.05):
        g.cyl(p, p + V((0, 0, 0.02)), 0.025, 6, "Iron")


# ================================================================== N_Props_E
def figurehead(g, base, lean, rnd):
    """A prize's figurehead, a crowned woman, leant against the back wall on her scroll."""
    base = V(base)
    up = V((0, math.sin(lean), math.cos(lean)))
    fwd = V((0, -math.cos(lean), math.sin(lean)))
    side = V((1, 0, 0))

    def P(x, h, f):
        return base + side * x + up * h + fwd * f
    # body: lofted ellipses (scroll base -> waist -> breast -> shoulders -> neck)
    prof = [(0.08, 0.2, 0.18, 0.0), (0.22, 0.22, 0.22, 0.03), (0.45, 0.17, 0.18, 0.05), (0.75, 0.15, 0.16, 0.06),
            (1.0, 0.17, 0.17, 0.08), (1.18, 0.2, 0.15, 0.06), (1.3, 0.2, 0.12, 0.04), (1.36, 0.06, 0.05, 0.04)]
    n = 10
    rings = []
    for h, rx, rf, off in prof:
        rings.append([P(math.cos(2 * math.pi * k / n) * rx, h, off + math.sin(2 * math.pi * k / n) * rf)
                      for k in range(n)])
    axis = P(0, 0.7, 0.03)
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            g.face_c([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], "Wood", axis)
    g.face(rings[0], "Wood", -up)
    # scroll curl at the foot (raised so it stays above the floor)
    g.sweep([P(-0.18, 0.12, 0.1), P(0, 0.08, 0.22), P(0.18, 0.12, 0.1)], 0.05, 5, "Wood")
    # head, face painted white long ago, crown (gilt) and hair down her back
    hc = P(0, 1.5, 0.06)
    g.blob(hc - up * 0.1, 0.1, 0.11, 0.2, 8, 3, "Wood", rnd, 0.04, flat_bottom=False,
           rot=Matrix.Rotation(-lean, 3, "X"))
    fc = hc + fwd * 0.07 + up * 0.0
    g.blob(fc - up * 0.06, 0.065, 0.05, 0.12, 6, 2, "Bone", rnd, 0.05, flat_bottom=True,
           rot=Matrix.Rotation(-lean, 3, "X"))
    for sx in (-1, 1):
        e = fc + side * (sx * 0.03) + up * 0.02 + fwd * 0.045
        g.cyl(e, e + fwd * 0.006, 0.01, 5, "Iron", caps=(False, True))
    cb = hc + up * 0.06
    for k in range(7):
        a = 2 * math.pi * k / 7
        p = cb + side * (math.cos(a) * 0.085) + fwd * (math.sin(a) * 0.09)
        g.cyl(p, p + up * 0.07, 0.016, 3, "Bone", caps=(False, False), r1=0.0)
    g.sweep([cb + side * 0.088 + fwd * 0.0, cb + fwd * 0.092, cb - side * 0.088], 0.012, 4, "Bone", caps=False)
    for sx in (-1, 1):
        g.sweep([hc + side * (sx * 0.08) - fwd * 0.02, P(sx * 0.14, 1.25, -0.08), P(sx * 0.12, 1.0, -0.1)], 0.035, 5,
                "Wood")
    # arms crossed over the breast
    for sx in (-1, 1):
        g.sweep([P(sx * 0.2, 1.22, 0.06), P(sx * 0.23, 1.02, 0.12), P(-sx * 0.08, 1.0, 0.24),
                 P(-sx * 0.15, 1.08, 0.22)], 0.04, 5, "Wood")
    # salt crust on the shoulders and a split down the scroll
    g.blob(P(0.12, 1.28, 0.08), 0.06, 0.05, 0.02, 5, 1, "Bone", rnd, 0.3, rot=Matrix.Rotation(-lean, 3, "X"))
    g.sweep([P(-0.05, 0.12, 0.27), P(0.0, 0.35, 0.27), P(0.04, 0.55, 0.22)], 0.006, 3, "Iron", caps=False)


@decorates("N_Props_E")
def n_props_e(g, lod):
    if lod != 0:
        return
    r = rng("throne-props-e")
    cc = V((8.0, 14.6, FL))
    # -- a rich rug in front of the chest, coins spilled on it
    x0, x1, y0, y1 = 7.55, 9.3, 13.58, 14.32
    z = FL + 0.006
    g.face([V((x0, y0, z)), V((x1, y0, z)), V((x1, y1, z)), V((x0, y1, z))], "Cloth", (0, 0, 1))
    for (a, b, c_, d) in ((x0 + 0.05, y0 + 0.05, x1 - 0.05, y0 + 0.09), (x0 + 0.05, y1 - 0.09, x1 - 0.05, y1 - 0.05),
                          (x0 + 0.05, y0 + 0.05, x0 + 0.09, y1 - 0.05), (x1 - 0.09, y0 + 0.05, x1 - 0.05, y1 - 0.05)):
        g.face([V((a, b, z + 0.001)), V((c_, b, z + 0.001)), V((c_, d, z + 0.001)), V((a, d, z + 0.001))], "Bone",
               (0, 0, 1))
    for k in range(3):
        m = V((7.95 + 0.55 * k, 13.95, z + 0.001))
        g.face([m + V((-0.14, 0, 0)), m + V((0, -0.17, 0)), m + V((0.14, 0, 0)), m + V((0, 0.17, 0))], "Iron",
               (0, 0, 1))
    patch(g, (9.05, 13.75, z + 0.0015), 0.16, 9, "Floor", r)                       # a rum stain
    g.face([V((9.3, 13.62, z)), V((9.35, 13.75, FL + 0.002)), V((9.32, 13.95, FL + 0.002)), V((9.3, 14.1, z))],
           "Cloth", (0, 0, 1))                                                     # the torn corner

    # -- coins: in the chest, on its rim and spilled on the rug
    def coin(p, tilt=0.0, a=0.0):
        p = V(p)
        nrm = V((math.sin(tilt) * math.cos(a), math.sin(tilt) * math.sin(a), math.cos(tilt)))
        g.cyl(p, p + nrm * 0.004, 0.017, 6, "Bone", caps=(False, True))
    for k in range(18):
        a = r.uniform(0, 6.28)
        p = V((cc.x - 0.05 + r.uniform(-0.4, 0.55), cc.y - 0.42 + r.uniform(-0.2, 0.12), z + 0.0015))
        coin(p, 0.0, a)
    for k in range(10):
        coin(V((cc.x + r.uniform(-0.38, 0.38), cc.y + r.uniform(-0.18, 0.18), FL + 0.47 + r.uniform(0, 0.04))),
             r.uniform(0, 0.5), r.uniform(0, 6.28))
    stack = V((8.62, 14.45, FL))
    for k in range(7):                                                      # a counted stack
        off_x = r.uniform(-0.002, 0.002)
        g.cyl(stack + V((off_x, 0, 0.0045 * k)), stack + V((off_x, 0, 0.0045 * k + 0.0045)), 0.017, 6,
              "Bone", caps=(False, True))
    # -- grey pearls spilling over the front edge of the chest
    pts = []
    for k in range(12):
        t = k / 11
        x = 8.15 + 0.2 * t
        if t < 0.4:
            p = V((x, 14.36 - t * 0.18, FL + 0.47))
        else:
            p = V((x, 14.29, FL + 0.47 - (t - 0.4) * 0.09))
        pts.append(p)
    for p in pts:
        g.blob(p, 0.008, 0.008, 0.011, 4, 1, "Bone", r, 0.0, flat_bottom=True)
    # -- the gilt reliquary of Saint Clement, standing on the coins
    rc = V((7.75, 14.6, 0.86))
    bx(g, rc.x - 0.09, rc.x + 0.09, rc.y - 0.06, rc.y + 0.06, rc.z, rc.z + 0.08, "Bone", 0.006)
    g.prism([(-0.095, 0.0), (0.095, 0.0), (0.0, 0.06)], Frame(rc + V((0, 0, 0.08)), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
            -0.065, 0.065, "Bone")
    g.cyl(rc + V((0, 0, 0.14)), rc + V((0, 0, 0.17)), 0.006, 4, "Bone")
    g.cyl(rc + V((-0.012, 0, 0.158)), rc + V((0.012, 0, 0.158)), 0.006, 4, "Bone")
    for sx in (-1, 1):
        g.blob(rc + V((sx * 0.09, sx * 0.06, -0.005)), 0.012, 0.012, 0.012, 5, 1, "Bone", r, 0.0)
    # a gilt candlestick and a cup, thrown in with the coins
    g.cyl(V((8.2, 14.7, 0.87)), V((8.45, 14.55, 0.9)), 0.012, 6, "Bone")
    g.cyl(V((8.45, 14.55, 0.9)), V((8.5, 14.52, 0.905)), 0.035, 7, "Bone", r1=0.02)
    g.cyl(V((7.95, 14.48, 0.86)), V((7.95, 14.48, 0.94)), 0.015, 6, "Bone", r1=0.04)

    # -- rum barrels: iron hoops, a spigot that drips, a tankard, the ransom letters on a spike
    for (x, y) in ((9.7, 14.5), (10.4, 14.65), (10.0, 13.85)):
        for h in (0.07, 0.25, 0.65, 0.83):
            rr = 0.27 + (0.33 - 0.27) * (1 - abs(h - 0.45) / 0.45)
            rr2 = 0.27 + (0.33 - 0.27) * (1 - abs(h + 0.035 - 0.45) / 0.45)
            g.cyl(V((x, y, FL + h)), V((x, y, FL + h + 0.035)), rr + 0.006, 14, "Iron", caps=(False, False),
                  r1=rr2 + 0.006)
        top = V((x, y, FL + 0.9 + 0.001))
        patch(g, top + V((0.08, -0.06, 0)), 0.03, 6, "Wood", r, jitter=0.0)    # the bung
        for k in range(3):                                                     # XXX burnt into the head
            p = top + V((-0.12 + 0.05 * k, 0.05, 0))
            for d in (V((0.018, 0.018, 0)), V((0.018, -0.018, 0))):
                g.face([p - d, p + d, p + d + V((0.005, 0, 0)), p - d + V((0.005, 0, 0))], "Iron", (0, 0, 1))
    sp = V((9.7, 14.5 - 0.3, FL + 0.2))                                        # spigot of the front barrel
    g.cyl(sp + V((0, 0.02, 0)), sp - V((0, 0.08, 0)), 0.018, 6, "Wood")
    g.cyl(sp - V((0, 0.05, 0)), sp - V((0, 0.05, -0.05)), 0.008, 4, "Wood")
    g.cyl(sp - V((0, 0.08, 0)), sp - V((0, 0.08, 0.04)), 0.006, 4, "Bone", caps=(False, True), r1=0.002)
    patch(g, V((9.7, 14.12, FL + 0.002)), 0.13, 9, "Iron", r)                 # the drip's dark pool
    tk = V((10.05, 13.82, FL + 0.9))                                           # a tankard on the near barrel
    g.cyl(tk, tk + V((0, 0, 0.13)), 0.045, 8, "Iron", caps=(True, False), r1=0.04)
    g.sweep([tk + V((0.04, 0, 0.11)), tk + V((0.08, 0, 0.09)), tk + V((0.08, 0, 0.04)), tk + V((0.04, 0, 0.025))],
            0.007, 3, "Iron", caps=False)
    patch(g, tk + V((0, 0, 0.11)), 0.035, 7, "Floor", r, jitter=0.0)
    lp = V((10.4, 14.65, FL + 0.9))                                            # letter spike
    bx(g, lp.x - 0.06, lp.x + 0.06, lp.y - 0.06, lp.y + 0.06, lp.z, lp.z + 0.03, "Wood", 0.005)
    g.cyl(lp + V((0, 0, 0.03)), lp + V((0, 0, 0.2)), 0.004, 4, "Iron", caps=(False, False), r1=0.0005)
    for k in range(4):
        zz = lp.z + 0.04 + k * 0.018
        a = r.uniform(0, 6.28)
        u, v = V((math.cos(a), math.sin(a), 0)), V((-math.sin(a), math.cos(a), 0))
        c = lp + V((0, 0, zz - lp.z)) + u * 0.02
        sheet = [c - u * 0.09 - v * 0.065, c + u * 0.07 - v * 0.065, c + u * 0.07 + v * 0.065 + V((0, 0, 0.01)),
                 c - u * 0.09 + v * 0.065 + V((0, 0, 0.01 * (k % 2)))]
        g.face(sheet, "Cloth", (0, 0, 1))
        g.face(sheet[::-1], "Cloth", (0, 0, -1))

    # -- a prize's figurehead, leant against the back wall between the chest and the barrels
    figurehead(g, (8.96, 14.62, FL + 0.1), 0.22, r)

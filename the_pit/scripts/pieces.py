"""The Pit V2 pieces (new concept, from scratch).

Plan (X transverse, Y longitudinal, Z up; origin on the axis of the yard):

    y = -19.2 .. -18   outer stairs
    y = -18   .. -14.4 fortified gate: two towers + vaulted passage + portcullis
    y = -15.2 .. -11.8 transverse hall
    y = -11.5 ..  11.5 the Pit: 6 m yard between two wings of 4 vaulted cells
    y =  11.8 ..  16   kennel master's hall: dais, niche and great brazier

Each piece is built for a level of detail `lod` (0 HIGH, 1 MEDIUM,
2 LOW, 3 LOWEST) and declares physics boxes and its kind ("structure", "door",
"deco").
"""

import math

from mathutils import Vector

from geo import Frame, Geo, arch_height, pointed_arch, rng

V = Vector

# ------------------------------------------------------------------ dimensions
FL = 0.40            # finished floor level
ZB = -0.40           # foundation base (hides the uneven terrain)
WT = 7.60            # top of the walls
NX = 3.0             # half-width of the yard
FT = 0.8             # thickness of the cell front (x 3.0..3.8)
XI, XO, XB = 11.6, 12.4, 13.0   # inner / outer face of the perimeter wall, buttresses
YP = [-11.5 + 5.75 * k for k in range(5)]   # axes of the partition walls
PT = 0.30            # half-thickness of the partitions
VS = 4.60            # springing line of the cell vaults
R_VAULT = 2.575      # inner vault radius (clear span 5.15 m)
T_VAULT = 0.30
ARCH_SPAN, ARCH_RATIO, ARCH_SPRING = 3.8, 0.62, FL + 2.9
DOOR_HW, DOOR_H = 0.70, 2.60
GRILLE_D = -0.45     # grille plane inside the thickness of the front

LODS = ("HIGH", "MEDIUM", "LOW", "LOWEST")


def bx(g, x0, x1, y0, y1, z0, z1, mat, c=0.0, skip=()):
    mn = V((min(x0, x1), min(y0, y1), min(z0, z1)))
    mx = V((max(x0, x1), max(y0, y1), max(z0, z1)))
    if c > 0:
        g.bbox(mn, mx, mat, c, skip)
    else:
        g.box(mn, mx, mat, skip)


def flipx(skip, s):
    """Swap the '+x'/'-x' face keys for the west wing (s = -1)."""
    if s > 0:
        return skip
    out = []
    for k in skip:
        out.append({"+x": "-x", "-x": "+x"}.get(k, k))
    return tuple(out)


def pbox(x0, x1, y0, y1, z0, z1):
    return (V((min(x0, x1), min(y0, y1), min(z0, z1))), V((max(x0, x1), max(y0, y1), max(z0, z1))))


# ================================================================== walls with an arch
def arch_wall(g, fr, u0, u1, uc, span, ratio, v_spring, v_bot, v_top, depth, n_side, mat,
              skip_u0=False, skip_u1=False, thr_top=None, front_only=False, top=True, back=True):
    """Wall with a pointed-arch opening. Wall body in d ∈ [-depth, 0]."""
    hw = span / 2
    P = fr.p
    out_f, out_b = fr.n, -fr.n
    la, lb = u0, uc - hw
    ra, rb = uc + hw, u1
    for (a, b, side) in ((la, lb, -1), (ra, rb, 1)):
        if b - a < 1e-4:
            continue
        # full front and back faces
        g.face([P(a, v_bot, 0), P(b, v_bot, 0), P(b, v_top, 0), P(a, v_top, 0)], mat, out_f)
        if front_only:
            continue
        if back:
            g.face([P(a, v_bot, -depth), P(b, v_bot, -depth), P(b, v_top, -depth), P(a, v_top, -depth)], mat, out_b)
        if top:
            g.face([P(a, v_top, 0), P(b, v_top, 0), P(b, v_top, -depth), P(a, v_top, -depth)], mat, V((0, 0, 1)))
        # outer end face
        if side < 0 and not skip_u0:
            g.face([P(a, v_bot, 0), P(a, v_top, 0), P(a, v_top, -depth), P(a, v_bot, -depth)], mat, -fr.u)
        if side > 0 and not skip_u1:
            g.face([P(b, v_bot, 0), P(b, v_top, 0), P(b, v_top, -depth), P(b, v_bot, -depth)], mat, fr.u)
        # jamb (only up to the springing line)
        j = b if side < 0 else a
        g.face([P(j, v_bot, 0), P(j, v_spring, 0), P(j, v_spring, -depth), P(j, v_bot, -depth)], mat,
               fr.u * (1 if side < 0 else -1))
    # threshold
    if thr_top is not None and not front_only:
        g.face([P(uc - hw, thr_top, 0), P(uc + hw, thr_top, 0), P(uc + hw, thr_top, -depth),
                P(uc - hw, thr_top, -depth)], mat, V((0, 0, 1)))
        g.face([P(uc - hw, v_bot, 0), P(uc + hw, v_bot, 0), P(uc + hw, thr_top, 0), P(uc - hw, thr_top, 0)],
               mat, out_f)
    # spandrels above the arch
    pts = pointed_arch(span, ratio, n_side)
    ctr = P(uc, v_spring, 0)
    for i in range(len(pts) - 1):
        (pu0, pv0), (pu1, pv1) = pts[i], pts[i + 1]
        A0, A1 = (uc + pu0, v_spring + pv0), (uc + pu1, v_spring + pv1)
        g.face([P(A0[0], A0[1], 0), P(A1[0], A1[1], 0), P(A1[0], v_top, 0), P(A0[0], v_top, 0)], mat, out_f)
        if front_only:
            continue
        if back:
            g.face([P(A0[0], A0[1], -depth), P(A1[0], A1[1], -depth), P(A1[0], v_top, -depth),
                    P(A0[0], v_top, -depth)], mat, out_b)
        sof = [P(A0[0], A0[1], 0), P(A1[0], A1[1], 0), P(A1[0], A1[1], -depth), P(A0[0], A0[1], -depth)]
        mid = sum(sof, V()) / 4
        g.face(sof, mat, V((ctr.x, ctr.y, ctr.z)) + fr.n * (-depth / 2) - mid)
    if top and not front_only:
        g.face([P(uc - hw, v_top, 0), P(uc + hw, v_top, 0), P(uc + hw, v_top, -depth), P(uc - hw, v_top, -depth)],
               mat, V((0, 0, 1)))


def voussoirs(g, fr, uc, v_spring, span, ratio, n_side, depth_r, proud, mat, gap=0.012, key=0.10):
    """Voussoirs carved on the wall face, alternating in length, with a projecting keystone."""
    hw = span / 2
    R = ratio * span
    cx = -hw + R
    th_end = math.acos(max(-1.0, min(1.0, -cx / R)))
    th_k = th_end + (math.pi - th_end) * 0.10
    d_g = gap / (2 * R)

    def pt(th, rad, sgn):
        u = cx + rad * math.cos(th)
        return fr.p(uc + sgn * u, v_spring + rad * math.sin(th), 0)

    for sgn in (-1, 1):
        for i in range(n_side):
            a = math.pi + (th_k - math.pi) * i / n_side
            b = math.pi + (th_k - math.pi) * (i + 1) / n_side
            a2, b2 = a - d_g, b + d_g
            r_out = R + depth_r * (1.0 if i % 2 == 0 else 0.82)
            poly = [pt(a2, R, sgn), pt(b2, R, sgn), pt(b2, r_out, sgn), pt(a2, r_out, sgn)]
            _stone(g, poly, fr.n, proud, mat)
    # keystone
    apex_in = fr.p(uc, v_spring + math.sqrt(max(R * R - cx * cx, 0)), 0)
    Rk = R + depth_r + key
    apex_out = fr.p(uc, v_spring + math.sqrt(max(Rk * Rk - cx * cx, 0)), 0)
    poly = [pt(th_k - d_g, R, -1), apex_in, pt(th_k - d_g, R, 1), pt(th_k - d_g, R + depth_r + key * 0.6, 1),
            apex_out, pt(th_k - d_g, R + depth_r + key * 0.6, -1)]
    _stone(g, poly, fr.n, proud + 0.03, mat)


def _stone(g, poly_front, n, proud, mat):
    """Prism from the wall face (d=0) out to `proud`; no back face."""
    a = list(poly_front)
    b = [p + n * proud for p in a]
    ctr = sum(a, V()) / len(a) + n * (proud / 2)
    g.face(b, mat, n)
    for i in range(len(a)):
        j = (i + 1) % len(a)
        g.face_c([a[i], a[j], b[j], b[i]], mat, ctr)


def hood(g, fr, uc, v_spring, span, ratio, n_side, r_in_extra, width, proud, mat, stops=True, sides=True):
    """Continuous hood mould over the arch, with horizontal stops."""
    inner = pointed_arch(span, ratio, n_side, r_in_extra)
    outer = pointed_arch(span, ratio, n_side, r_in_extra + width)
    P = lambda u, v, d: fr.p(uc + u, v_spring + v, d)
    for i in range(len(inner) - 1):
        a0, a1 = inner[i], inner[i + 1]
        b0, b1 = outer[i], outer[i + 1]
        q = [P(*a0, 0), P(*a1, 0), P(*b1, 0), P(*b0, 0)]
        mid = sum(q, V()) / 4
        g.face([P(*a0, proud), P(*a1, proud), P(*b1, proud), P(*b0, proud)], mat, fr.n)
        if sides:
            g.face([P(*a0, 0), P(*a1, 0), P(*a1, proud), P(*a0, proud)], mat, P(0, 0, 0) - mid)
            g.face([P(*b0, 0), P(*b1, 0), P(*b1, proud), P(*b0, proud)], mat, mid - P(0, 0, 0))
    if stops:
        for sgn, (a, b) in ((-1, (inner[0], outer[0])), (1, (inner[-1], outer[-1]))):
            u_in, u_out = a[0], b[0]
            lo, hi = sorted((u_in, u_out + sgn * 0.15))
            p0 = fr.p(uc + lo, v_spring - 0.16, 0)
            p1 = fr.p(uc + hi, v_spring, proud)
            bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, mat, 0.015 if proud > 0.05 else 0)


def cross_slit_skin(g, to3d, u0, u1, z0, z1, um, zs0, zs1, mat, hw_v=0.08, hw_h=0.36, hh=0.075, skip=()):
    """Wall skin (range u, z) pierced by a cross-shaped arrow slit centred on um.
    `to3d(u0, u1, z0, z1)` returns (x0, x1, y0, y1, z0, z1) for each box of the skin."""
    zm = (zs0 + zs1) / 2
    rects = [(u0, um - hw_h, z0, z1), (um + hw_h, u1, z0, z1),
             (um - hw_h, um - hw_v, z0, zm - hh), (um - hw_h, um - hw_v, zm + hh, z1),
             (um + hw_v, um + hw_h, z0, zm - hh), (um + hw_v, um + hw_h, zm + hh, z1),
             (um - hw_v, um + hw_v, z0, zs0), (um - hw_v, um + hw_v, zs1, z1)]
    for (a, b, c, d) in rects:
        if b - a > 1e-4 and d - c > 1e-4:
            bx(g, *to3d(a, b, c, d), mat, skip=skip)


# ================================================================== ironwork
def bar(g, p0, p1, r, n, mat):
    g.cyl(p0, p1, r, n, mat, caps=(False, False), phase=math.pi / n)


def chain_path(start, down_to, heading, floor_len, wiggle, rnd, samples=80):
    """Polyline: vertical drop from `start` down to height `down_to`, a bend and a stretch on the floor."""
    start = V(start)
    heading = V((heading.x, heading.y, 0)).normalized()
    side = V((-heading.y, heading.x, 0))
    pts = []
    drop = start.z - down_to
    bend = min(0.18, drop * 0.5)
    n1 = max(int((drop - bend) / 0.02), 2)
    for i in range(n1):
        pts.append(start + V((0, 0, -(drop - bend) * i / n1)))
    c = V((start.x, start.y, down_to + bend)) + heading * bend
    for i in range(10):
        a = math.pi / 2 * i / 9
        pts.append(c + heading * (-bend * math.cos(a)) + V((0, 0, -bend * math.sin(a))))
    base = pts[-1].copy()
    ph = rnd.uniform(0, math.pi)
    for i in range(1, samples):
        t = floor_len * i / (samples - 1)
        pts.append(base + heading * t + side * (math.sin(ph + t * 3.1) * wiggle * min(1, t)))
    return pts


def resample(pts, step):
    out = [(pts[0], (pts[1] - pts[0]).normalized())]
    acc = 0.0
    target = step
    for i in range(1, len(pts)):
        a, b = pts[i - 1], pts[i]
        seg = (b - a).length
        while acc + seg >= target and seg > 0:
            t = (target - acc) / seg
            p = a.lerp(b, t)
            out.append((p, (b - a).normalized()))
            target += step
        acc += seg
    return out


def chain(g, path, a_c, b_c, r, lod, rnd, z_floor):
    """Chain of interlocking links that follows `path` (list of centres)."""
    pitch = 2 * (a_c - r)
    if lod >= 1:
        # MEDIUM/LOW: twisted tube instead of links
        n = 4 if lod == 1 else 3
        step = pitch * (1 if lod == 1 else 3)
        pts = [p for p, _ in resample(path, step)]
        if len(pts) >= 2:
            g.sweep(pts, b_c * 0.85, n, "Iron", caps=True)
        return pts
    centers = resample(path, pitch)
    for i, (c, t) in enumerate(centers):
        vertical = abs(t.z) > 0.7
        ref = V((0, 0, 1)) if abs(t.z) < 0.9 else V((1, 0, 0))
        w0 = t.cross(ref).normalized()
        on_floor = c.z < z_floor + 0.2 and not vertical
        roll = (math.pi / 2) * (i % 2)
        if on_floor:
            roll = math.pi / 4 if i % 2 == 0 else -math.pi / 4
            w0 = t.cross(V((0, 0, 1))).normalized()
            n0 = t.cross(w0)
            if n0.z < 0:
                n0 = -n0
            w = w0 * math.cos(roll) + n0 * math.sin(roll)
            c = V((c.x, c.y, z_floor + b_c * math.cos(math.pi / 4) + r - 0.003))
        else:
            n0 = t.cross(w0)
            w = w0 * math.cos(roll) + n0 * math.sin(roll)
        g.link(c, t, w, a_c, b_c, r, 8, 4, "Iron")
    return [c for c, _ in centers]


def wall_anchor(g, P0, n, up, lod, plate=0.11, ring_r=0.075, wire=0.016):
    """Riveted plate, staple and hanging ring. Returns the lowest point of the ring.

    P0: point on the wall face; n: outward normal; up: vertical.
    """
    P0, n, up = V(P0), V(n).normalized(), V(up).normalized()
    u = up.cross(n).normalized()
    th = 0.03
    corners = [P0 + u * a + up * b for a, b in ((-plate, -plate), (plate, -plate), (plate, plate), (-plate, plate))]
    if lod == 0:
        # chamfered plate as a prism with a bevel on the visible face
        inner = [P0 + u * a * 0.85 + up * b * 0.85 + n * th for a, b in
                 ((-plate, -plate), (plate, -plate), (plate, plate), (-plate, plate))]
        mid = [p + n * (th * 0.55) for p in corners]
        ctr = P0 + n * (th / 2)
        g.face(inner, "Iron", n)
        for i in range(4):
            j = (i + 1) % 4
            g.face_c([mid[i], mid[j], inner[j], inner[i]], "Iron", ctr)
            g.face_c([corners[i], corners[j], mid[j], mid[i]], "Iron", ctr)
        for a, b in ((-0.75, -0.75), (0.75, -0.75), (0.75, 0.75), (-0.75, 0.75)):
            base = P0 + u * (a * plate) + up * (b * plate) + n * (th - 0.002)
            g.cyl(base, base + n * 0.014, 0.013, 6, "Iron", caps=(False, True), r1=0.004)
    else:
        g.prism([(-plate, -plate), (plate, -plate), (plate, plate), (-plate, plate)],
                Frame(P0, u, up, n), 0.0, th, "Iron", caps=(False, True))
    # staple (a link with its axis perpendicular to the wall)
    s_half, s_w, s_r = 0.05, 0.035, 0.014
    sc = P0 + n * (th + 0.02)
    hole_hi = s_w - s_r
    ring_c = sc + n * 0.012 + up * (-hole_hi + wire - ring_r)
    if lod <= 1:
        nm = (10, 5) if lod == 0 else (6, 3)
        g.link(sc, n, up, s_half, s_w, s_r, nm[0], nm[1], "Iron")
        g.link(ring_c, u, up, ring_r, ring_r, wire, 16 if lod == 0 else 8, 6 if lod == 0 else 3, "Iron")
    elif lod == 2:
        g.link(ring_c, u, up, ring_r, ring_r, wire, 6, 3, "Iron")
    return ring_c - up * ring_r, ring_c, u


def collar(g, c, R, r, lod):
    nm = {0: (20, 6), 1: (10, 4), 2: (6, 3)}.get(lod)
    if nm:
        g.link(c, V((1, 0, 0)), V((0, 1, 0)), R, R, r, nm[0], nm[1], "Iron")
        if lod == 0:  # collar rivets
            for k in range(6):
                a = 2 * math.pi * k / 6
                p = c + V((math.cos(a), math.sin(a), 0)) * (R + r * 0.6) + V((0, 0, r * 0.4))
                g.cyl(p, p + V((math.cos(a), math.sin(a), 0.5)).normalized() * 0.015, 0.01, 4, "Iron",
                      caps=(False, True), r1=0.002)


# ================================================================== registry
class Piece:
    def __init__(self, name, kind, build, phys, lod_map):
        self.name, self.kind, self.build, self.phys = name, kind, build, phys
        self.lod_map = lod_map


PIECES = []

# Which builder variant each SL level uses (HIGH, MEDIUM, LOW, LOWEST).
# On big pieces LOW carries ~60 % of the cost: keep LOW and LOWEST minimal.
# On small pieces LOWEST carries the weight: MEDIUM can be almost the HIGH.
BIG = (0, 1, 3, 3)
SMALL = (0, 0, 1, 3)
STD = (0, 1, 2, 3)


def register(name, kind, build, phys, lod_map=STD):
    PIECES.append(Piece(name, kind, build, phys, lod_map))


def bbox_phys(build):
    """Bounding-box physics for decorative pieces (they are set to None in SL)."""
    def ph():
        mn, mx = build(0).bounds()
        return [(mn, mx)]
    return ph


# ================================================================== CELLS
def cell_name(k, s):
    return f"C{(k + 1) if s < 0 else (k + 5):02d}"


def make_cell(k, s):
    y0, y1 = YP[k], YP[k + 1]
    yc = (y0 + y1) / 2
    cy0, cy1 = y0 + PT, y1 - PT
    tag = cell_name(k, s)
    X = lambda x: s * x
    rnd_layout = rng(f"layout-{tag}")
    # ---- per-cell variations (the same in every LOD)
    anchor_x = X(rnd_layout.uniform(6.6, 8.2))
    anchor_z = FL + rnd_layout.uniform(0.95, 1.15)
    head_ang = rnd_layout.uniform(-0.6, 0.5)
    floor_len = rnd_layout.uniform(0.7, 1.3)
    trough_x = X(rnd_layout.uniform(4.5, 5.6))
    hay_y = rnd_layout.uniform(-0.6, 0.6)

    # ------------------------------------------------------------ walls
    def walls(lod):
        g = Geo()
        top_part = WT if k == 3 else VS
        inner, outer = flipx(("-x",), s)[0], flipx(("+x",), s)[0]
        ends = (("-y",) if k > 0 else ()) + (("+y",) if k < 3 else ())
        ox0, ox1 = XI, XO
        yb0, yb1 = y1 - 0.45, y1 + 0.45
        if lod == 3:  # LOW/LOWEST: only what is seen from afar (outside and wall top)
            bx(g, X(ox0), X(ox1), y0, y1, FL, WT, "Stone", skip=("-z", "-y", "+y", inner))
            bx(g, X(XO), X(XB), yb0, yb1, FL, FL + 5.6, "Stone", skip=("-z", inner, "-y"))
            return g
        # north partition
        bx(g, X(3.8), X(XI), y1 - PT, y1 + PT, ZB, top_part, "Stone", 0.0,
           skip=("-z", "-x", "+x") + (() if k == 3 else ("+z",)))
        if k == 3:
            bx(g, X(3.75), X(XI + 0.05), y1 - PT - 0.06, y1 + PT + 0.06, WT, WT + 0.18, "Stone",
               0.03 if lod == 0 else 0, skip=() if lod == 0 else ("-z", inner, outer))
        sw_in, sw_out = 0.36, 0.09
        sz0, sz1 = FL + 1.9, FL + 3.6
        if lod == 0:
            # perimeter wall with a splayed arrow slit
            sk = ("-z",)
            bx(g, X(ox0), X(ox1), y0, yc - sw_in, ZB, WT, "Stone", skip=sk + (("-y",) if k > 0 else ()))
            bx(g, X(ox0), X(ox1), yc + sw_in, y1, ZB, WT, "Stone", skip=sk + (("+y",) if k < 3 else ()))
            bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, ZB, sz0, "Stone", skip=("-z", "-y", "+y"))
            bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, sz1, WT, "Stone", skip=("-y", "+y"))
            for sg in (-1, 1):
                poly = [(X(ox0), yc + sg * sw_in), (X(ox1), yc + sg * sw_in), (X(ox1), yc + sg * sw_out),
                        (X(ox0 + 0.32), yc + sg * sw_out)]
                g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), sz0, sz1, "Stone",
                        caps=(False, False))
            bx(g, X(ox0 - 0.05), X(ox1 + 0.07), y0, y1, WT, WT + 0.18, "Stone", 0.03, skip=ends)
            poly = [(X(ox1), ZB), (X(ox1 + 0.12), ZB), (X(ox1 + 0.12), FL + 0.35), (X(ox1), FL + 0.5)]
            g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), y0, y1, "Stone",
                    caps=(k == 0, k == 3))
            # sleeping bench at the back with a wooden kerb
            bx(g, X(9.9), X(XI), cy0, cy1, FL - 0.05, FL + 0.45, "Stone", 0.05, skip=("-z", outer, "-y", "+y"))
            bx(g, X(9.86), X(9.98), cy0 + 0.02, cy1 - 0.02, FL + 0.38, FL + 0.5, "Wood", 0.015)
            # buttress with a set-off
            bx(g, X(XO - 0.02), X(XB), yb0, yb1, ZB, FL + 2.4, "Stone", 0.03, skip=("-z",))
            g.prism([(X(XO - 0.02), FL + 2.4), (X(XB), FL + 2.4), (X(XB - 0.14), FL + 2.62),
                     (X(XO - 0.02), FL + 2.62)], Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0, yb1,
                    "Stone")
            bx(g, X(XO - 0.02), X(XB - 0.14), yb0 + 0.04, yb1 - 0.04, FL + 2.62, FL + 5.0, "Stone", 0.03)
            g.prism([(X(XO - 0.02), FL + 5.0), (X(XB - 0.14), FL + 5.0), (X(XO - 0.02), FL + 6.3)],
                    Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0 + 0.04, yb1 - 0.04, "Stone")
        else:
            # MEDIUM: wall without the slit, bench and buttress as plain boxes
            bx(g, X(ox0), X(ox1), y0, y1, ZB, WT + 0.18, "Stone", skip=("-z",) + ends)
            bx(g, X(9.9), X(XI), cy0, cy1, FL, FL + 0.45, "Stone", skip=("-z", outer, "-y", "+y"))
            bx(g, X(XO), X(XB), yb0, yb1, ZB, FL + 5.6, "Stone", skip=("-z", inner))
        return g

    def walls_phys():
        return [pbox(X(3.8), X(XI), y1 - PT, y1 + PT, ZB, WT if k == 3 else VS),
                pbox(X(XI), X(XO), y0, y1, ZB, WT + 0.18),
                pbox(X(9.86), X(XI), cy0, cy1, FL - 0.05, FL + 0.5),
                pbox(X(XO), X(XB), y1 - 0.45, y1 + 0.45, ZB, FL + 5.6)]

    register(f"{tag}_Walls", "structure", walls, walls_phys)

    # ------------------------------------------------------------ earth floor
    def floor(lod):
        g = Geo()
        x0, x1 = 3.8, XI
        nxg, nyg = {0: (14, 10), 1: (2, 2)}.get(lod, (1, 1))
        rr = rng(f"suelo-{tag}")  # seed text kept so the geometry stays identical
        grid = []
        for i in range(nxg + 1):
            row = []
            for j in range(nyg + 1):
                xx = x0 + (x1 - x0) * i / nxg
                yy = cy0 + (cy1 - cy0) * j / nyg
                edge = i in (0, nxg) or j in (0, nyg)
                z = FL if edge else FL + rr.uniform(0.0, 0.035) * (1 if lod == 0 else 0.4)
                row.append(V((X(xx), yy, z)))
            grid.append(row)
        for i in range(nxg):
            for j in range(nyg):
                g.face([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "Floor", (0, 0, 1))
        if lod == 0:
            bx(g, X(x0), X(x1), cy0, cy1, ZB + 0.1, FL, "Floor", skip=("+z", "-z", "-x", "+x"))
            # loose wisps of straw
            for i in range(60):
                px = X(rr.uniform(4.2, 9.6))
                py = rr.uniform(cy0 + 0.2, cy1 - 0.2)
                a = rr.uniform(0, math.pi)
                L = rr.uniform(0.12, 0.3)
                d = V((math.cos(a), math.sin(a), 0))
                pr = V((-d.y, d.x, 0)) * 0.006
                p = V((px, py, FL + 0.02))
                g.face([p - d * L / 2 - pr, p + d * L / 2 - pr, p + d * L / 2 + pr, p - d * L / 2 + pr], "Straw",
                       (0, 0, 1))
        return g

    register(f"{tag}_Floor", "structure", floor,
             lambda: [pbox(X(3.8), X(XI), cy0, cy1, FL - 0.3, FL + 0.01)], BIG)

    # ------------------------------------------------------------ barrel vault
    def vault(lod):
        g = Geo()
        n = {0: 24, 1: 8, 2: 6, 3: 3}[lod]
        xa, xb = X(3.8), X(XI)
        Ri, Ro = R_VAULT, R_VAULT + T_VAULT

        def ring(rad, i, x):
            a = math.pi * i / n
            return V((x, yc - rad * math.cos(a), VS + rad * math.sin(a)))
        ctr_axis = lambda x: V((x, yc, VS))
        for i in range(n):
            q = [ring(Ro, i, xa), ring(Ro, i + 1, xa), ring(Ro, i + 1, xb), ring(Ro, i, xb)]
            g.face(q, "Stone", sum(q, V()) / 4 - ctr_axis((xa + xb) / 2))
            if lod == 0:
                q = [ring(Ri, i, xa), ring(Ri, i + 1, xa), ring(Ri, i + 1, xb), ring(Ri, i, xb)]
                g.face(q, "Stone", ctr_axis((xa + xb) / 2) - sum(q, V()) / 4)
        if lod == 0:
            # transverse arches with springing corbels
            for xr in (6.35, 9.05):
                xa_r, xb_r = X(xr - 0.18), X(xr + 0.18)
                rin, rout = Ri - 0.13, Ri
                for i in range(n):
                    for x in (xa_r, xb_r):
                        q = [ring(rin, i, x), ring(rin, i + 1, x), ring(rout, i + 1, x), ring(rout, i, x)]
                        g.face(q, "Stone", V((x - X(xr), 0, 0)))
                    q = [ring(rin, i, xa_r), ring(rin, i + 1, xa_r), ring(rin, i + 1, xb_r), ring(rin, i, xb_r)]
                    g.face(q, "Stone", ctr_axis(X(xr)) - sum(q, V()) / 4)
                for sg in (-1, 1):
                    yy = yc + sg * Ri
                    bx(g, X(xr - 0.22), X(xr + 0.22), yy, yy - sg * 0.2, VS - 0.38, VS + 0.02, "Stone", 0.03)
        return g

    def vault_phys():
        Ro = R_VAULT + T_VAULT
        return [pbox(X(3.8), X(XI), yc - 1.2, yc + 1.2, VS + R_VAULT + 0.02, VS + Ro)]

    register(f"{tag}_Vault", "structure", vault, vault_phys, BIG)

    # ------------------------------------------------------------ front: arch + grille
    ya = y0 - (PT if k == 0 else 0)
    yb = y1 + (PT if k == 3 else 0)
    fr = Frame((X(NX), 0, 0), (0, 1, 0), (0, 0, 1), (-s, 0, 0))

    def front(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        arch_wall(g, fr, ya, yb, yc, ARCH_SPAN, ARCH_RATIO, ARCH_SPRING, ZB, WT, FT, n_side, "Stone",
                  skip_u0=(k > 0), skip_u1=(k < 3), thr_top=FL, front_only=(lod == 3), back=(lod == 0),
                  top=(lod == 0))
        ends = (("-y",) if k > 0 else ()) + (("+y",) if k < 3 else ())
        if lod == 0:
            bx(g, *_fx(fr, ya, yb, -FT - 0.07, 0.07), WT, WT + 0.2, "Stone", 0.035, skip=ends)
        elif lod == 1:
            bx(g, *_fx(fr, ya, yb, -FT - 0.07, 0.07), WT, WT + 0.2, "Stone",
               skip=ends + ("-z", flipx(("+x",), s)[0]))
        if lod == 0:
            voussoirs(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 6, 0.55, 0.06, "Stone")
            hood(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 12, 0.68, 0.13, 0.11, "Stone")
            for sg in (-1, 1):  # jamb ashlars, alternating long and short
                zq = FL + 0.56
                nq = 5
                hq = (ARCH_SPRING - 0.26 - zq) / nq
                for i in range(nq):
                    wq = 0.55 if i % 2 == 0 else 0.34
                    u_in = yc + sg * ARCH_SPAN / 2
                    p0 = fr.p(u_in, zq + i * hq + 0.008, 0)
                    p1 = fr.p(u_in + sg * wq, zq + (i + 1) * hq - 0.008, 0.035)
                    bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Stone", 0.012)
            for sg in (-1, 1):  # imposts
                u0 = yc + sg * ARCH_SPAN / 2
                p0 = fr.p(u0, ARCH_SPRING - 0.26, 0)
                p1 = fr.p(u0 + sg * 0.3, ARCH_SPRING, 0.11)
                bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Stone", 0.025)
            # battered plinth on both sides of the opening
            for (a, b) in ((ya, yc - ARCH_SPAN / 2), (yc + ARCH_SPAN / 2, yb)):
                poly = [(0.0, FL - 0.02), (0.09, FL - 0.02), (0.09, FL + 0.42), (0.0, FL + 0.56)]
                g.prism([(d, z) for d, z in poly], Frame((X(NX), 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)),
                        a, b, "Stone", caps=(k == 0 or a > ya, k == 3 or b < yb))
        elif lod == 1:
            hood(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 4, 0.0, 0.62, 0.07, "Stone", stops=False,
                 sides=False)
        return g

    def grille_piece(lod):
        g = Geo()
        grille(g, lod)
        return g

    def grille(g, lod):
        if lod == 3:
            return
        hw = ARCH_SPAN / 2
        d = GRILLE_D
        r = 0.021
        nsides = {0: 8, 1: 3, 2: 3}[lod]
        step = 0.152 if lod <= 1 else 0.45
        P = lambda u, v: fr.p(yc + u, v, d)
        top = lambda u: ARCH_SPRING + arch_height(u, ARCH_SPAN, ARCH_RATIO) + 0.06
        head = FL + DOOR_H + 0.02
        nb = int((2 * hw - 0.16) / step)
        off = -(nb * step) / 2
        for i in range(nb + 1):
            u = off + i * step
            if abs(u) > hw - 0.05:
                continue
            if abs(u) < DOOR_HW + 0.06:
                if lod <= 1:
                    bar(g, P(u, head + 0.03), P(u, top(u)), r, nsides, "Iron")
            else:
                bar(g, P(u, FL - 0.04), P(u, top(u)), r, nsides, "Iron")
        if lod >= 2:
            for sg in (-1, 1):
                bx(g, *_fx(fr, yc + sg * (DOOR_HW + 0.02), yc + sg * (DOOR_HW + 0.08), d - 0.03, d + 0.03),
                   FL, top(DOOR_HW), "Iron")
            bx(g, *_fx(fr, yc - hw, yc + hw, d - 0.03, d + 0.03), head, head + 0.08, "Iron")
            return
        # door posts, header and flat bars
        for sg in (-1, 1):
            u = sg * (DOOR_HW + 0.045)
            bx(g, *_fx(fr, yc + u - 0.04, yc + u + 0.04, d - 0.04, d + 0.04), FL - 0.04, top(abs(u)), "Iron",
               0.008 if lod == 0 else 0)
        bx(g, *_fx(fr, yc - hw - 0.04, yc + hw + 0.04, d - 0.045, d + 0.045), head, head + 0.09, "Iron",
           0.008 if lod == 0 else 0)
        for z in (FL + 0.2, FL + 1.35):
            for sg in (-1, 1):
                a, b = sorted((yc + sg * (DOOR_HW + 0.08), yc + sg * (hw + 0.04)))
                bx(g, *_fx(fr, a, b, d - 0.035, d + 0.035), z, z + 0.055, "Iron")
        bx(g, *_fx(fr, yc - hw - 0.04, yc + hw + 0.04, d - 0.035, d + 0.035), ARCH_SPRING - 0.03,
           ARCH_SPRING + 0.03, "Iron")
        if lod == 0:
            # hinge pins: pins sticking out of the hinge post (south side)
            u_h = -(DOOR_HW + 0.0)
            for z in (FL + 0.42, FL + 2.18):
                p0 = P(u_h - 0.05, z)
                p1 = P(u_h, z)
                g.cyl(p0, p1, 0.016, 6, "Iron")
                g.cyl(P(u_h, z - 0.06), P(u_h, z + 0.07), 0.011, 6, "Iron")
            # strike plate on the north post
            p0 = fr.p(yc + DOOR_HW + 0.0, FL + 1.12, d - 0.06)
            p1 = fr.p(yc + DOOR_HW + 0.09, FL + 1.3, d + 0.06)
            bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Iron", 0.01)
            # spear points under the top rail so the scale reads
            for i in range(nb + 1):
                u = off + i * step
                if abs(u) < hw - 0.1:
                    z = ARCH_SPRING + 0.03
                    g.cyl(P(u, z), P(u, z + 0.12), 0.03, 4, "Iron", caps=(True, False), r1=0.0)

    def front_phys():
        hw = ARCH_SPAN / 2
        g0, g1 = NX - GRILLE_D - 0.06, NX - GRILLE_D + 0.06   # thin slab in the grille plane
        crown = ARCH_SPRING + arch_height(0, ARCH_SPAN, ARCH_RATIO)
        return [pbox(X(NX), X(NX + FT), ya, yc - hw, ZB, WT + 0.2),
                pbox(X(NX), X(NX + FT), yc + hw, yb, ZB, WT + 0.2),
                # threshold: continuous floor between yard and cell (without it the avatar falls when entering)
                pbox(X(NX), X(NX + FT), yc - hw, yc + hw, ZB, FL),
                pbox(X(g0), X(g1), yc - hw, yc - DOOR_HW, FL, crown),
                pbox(X(g0), X(g1), yc + DOOR_HW, yc + hw, FL, crown),
                pbox(X(g0), X(g1), yc - DOOR_HW, yc + DOOR_HW, FL + DOOR_H + 0.02, crown),
                # solid masonry above the arch crown
                pbox(X(NX), X(NX + FT), yc - hw, yc + hw, crown, WT + 0.2)]

    register(f"{tag}_Front", "structure", front, front_phys, BIG)
    register(f"{tag}_Grille", "deco", grille_piece, bbox_phys(grille_piece), BIG)

    # ------------------------------------------------------------ door leaf
    def door(lod):
        g = Geo()
        d = GRILLE_D
        P = lambda u, v, dd=0.0: fr.p(yc + u, v, d + dd)
        z0, z1 = FL + 0.03, FL + DOOR_H - 0.02
        u0, u1 = -DOOR_HW + 0.03, DOOR_HW - 0.02
        if lod == 3:
            g.face([P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)], "Iron", fr.n)
            g.face([P(u0, z0), P(u1, z0), P(u1, z1), P(u0, z1)], "Iron", -fr.n)
            return g
        c = 0.006 if lod == 0 else 0
        # frame
        for (a, b) in ((u0, u0 + 0.06), (u1 - 0.06, u1)):
            bx(g, *_fx(fr, yc + a, yc + b, d - 0.03, d + 0.03), z0, z1, "Iron", c)
        for z in ((z0, z0 + 0.06), (FL + 1.25, FL + 1.3), (z1 - 0.06, z1)):
            bx(g, *_fx(fr, yc + u0 + 0.06, yc + u1 - 0.06, d - 0.025, d + 0.025), z[0], z[1], "Iron")
        # bars
        nb = {0: 7, 1: 7, 2: 3}[lod]
        for i in range(nb):
            u = u0 + 0.06 + (u1 - u0 - 0.12) * (i + 1) / (nb + 1)
            bar(g, P(u, z0 + 0.03), P(u, z1 - 0.03), 0.02, {0: 8, 1: 4, 2: 3}[lod], "Iron")
        if lod == 2:
            return g
        # diagonal brace (from the hinge at the bottom to the lock at the top)
        a, b = P(u0 + 0.06, z0 + 0.06), P(u1 - 0.06, FL + 1.25)
        g.sweep([a, b], 0.022, 4, "Iron")
        a, b = P(u0 + 0.06, FL + 1.3), P(u1 - 0.06, z1 - 0.06)
        g.sweep([a, b], 0.022, 4, "Iron")
        # hinge knuckles
        for z in (FL + 0.42, FL + 2.18):
            for zz in ((z - 0.07, z - 0.005), (z + 0.005, z + 0.07)) if lod == 0 else ((z - 0.07, z + 0.07),):
                g.cyl(P(-DOOR_HW, zz[0]), P(-DOOR_HW, zz[1]), 0.03, 8 if lod == 0 else 4, "Iron")
            g.cyl(P(-DOOR_HW + 0.02, z), P(u0 + 0.05, z), 0.012, 4, "Iron")
            bx(g, *_fx(fr, yc + u0, yc + u0 + 0.35, d - 0.034, d + 0.034), z - 0.03, z + 0.03, "Iron")
        # symmetric lock box and pull rings on both sides
        bx(g, *_fx(fr, yc + u1 - 0.2, yc + u1 + 0.005, d - 0.05, d + 0.05), FL + 1.1, FL + 1.32, "Iron", c)
        if lod == 0:
            for sg in (1, -1):
                face = d + sg * 0.05
                n = fr.n * sg
                sc = fr.p(yc + u1 - 0.1, FL + 1.21, face) + n * 0.02
                g.link(sc, n, V((0, 0, 1)), 0.035, 0.022, 0.008, 8, 4, "Iron")
                rc = sc + n * 0.012 + V((0, 0, -(0.022 - 0.008) + 0.009 - 0.06))
                g.link(rc, V((0, 1, 0)), V((0, 0, 1)), 0.06, 0.06, 0.009, 14, 5, "Iron")
                # keyhole plate
                kp = fr.p(yc + u1 - 0.1, FL + 1.15, face)
                g.cyl(kp, kp + n * 0.006, 0.018, 6, "Iron", caps=(False, True))
        return g

    register(f"{tag}_Door", "door", door,
             lambda: [pbox(*_fx(fr, yc - DOOR_HW + 0.03, yc + DOOR_HW - 0.02, GRILLE_D - 0.05, GRILLE_D + 0.05),
                           FL + 0.03, FL + DOOR_H - 0.02)])

    # ------------------------------------------------------------ chain with collar
    face_y = y1 - PT
    up = V((0, 0, 1))
    nrm = V((0, -1, 0))
    heading = V((math.sin(head_ang) * s * -1, -math.cos(head_ang), 0))

    def chain_piece(lod):
        g = Geo()
        if lod == 3:
            p = V((anchor_x, face_y, anchor_z))
            g.face([p + V((-0.1, 0, -0.1)), p + V((0.1, 0, -0.1)), p + V((0, -0.02, 0.1))], "Iron", nrm)
            fp = V((anchor_x, face_y, FL)) + heading * (floor_len + 0.4)
            g.face([fp + V((-0.15, 0, 0.01)), fp + V((0.15, 0, 0.01)), fp + V((0, 0.15, 0.01))], "Iron", up)
            return g
        r = rng(f"cadena-{tag}")  # seed text kept so the geometry stays identical
        bottom, ring_c, u = wall_anchor(g, (anchor_x, face_y, anchor_z), nrm, up, lod)
        a_c, b_c, wr = 0.07, 0.042, 0.015
        start = bottom + V((0, 0, (0.016 + wr) - a_c))
        zf = FL + b_c * math.cos(math.pi / 4) + wr
        path = chain_path(start, zf, heading, floor_len, 0.12, r)
        centers = chain(g, path, a_c, b_c, wr, lod, r, FL)
        last = centers[-1]
        t = (centers[-1] - centers[-2]).normalized() if len(centers) > 1 else heading
        t = V((t.x, t.y, 0)).normalized()
        R = 0.17
        cc = V((last.x, last.y, FL + 0.022 - 0.002)) + t * ((a_c - wr - 0.022) + R if lod == 0 else R * 0.9)
        collar(g, cc, R, 0.024, lod)
        return g

    register(f"{tag}_Chain", "deco", chain_piece, bbox_phys(chain_piece))

    # ------------------------------------------------------------ stone trough
    ty0 = cy0 + 0.02

    def trough(lod):
        g = Geo()
        x0, x1 = sorted((trough_x - 0.55, trough_x + 0.55))
        y_0, y_1 = ty0, ty0 + 0.5
        h = FL + 0.42
        w = 0.08
        if lod == 3:
            bx(g, x0, x1, y_0, y_1, FL, h, "Stone", skip=("-z", "-y", "-x", "+x"))
            return g
        if lod == 2:
            bx(g, x0, x1, y_0, y_1, FL, h, "Stone", skip=("-z",))
            return g
        c = 0.02 if lod == 0 else 0
        bx(g, x0, x1, y_0, y_0 + w, FL, h, "Stone", c, skip=("-z",))
        bx(g, x0, x1, y_1 - w, y_1, FL, h, "Stone", c, skip=("-z",))
        bx(g, x0, x0 + w, y_0 + w, y_1 - w, FL, h, "Stone", c, skip=("-z", "-y", "+y"))
        bx(g, x1 - w, x1, y_0 + w, y_1 - w, FL, h, "Stone", c, skip=("-z", "-y", "+y"))
        bx(g, x0 + w, x1 - w, y_0 + w, y_1 - w, FL, FL + 0.12, "Stone", skip=("-z", "-y", "+y", "-x", "+x"))
        if lod == 0:  # murky water (flat face, floor material so the user can apply their own water)
            g.face([V((x0 + w, y_0 + w, h - 0.09)), V((x1 - w, y_0 + w, h - 0.09)),
                    V((x1 - w, y_1 - w, h - 0.09)), V((x0 + w, y_1 - w, h - 0.09))], "Floor", (0, 0, 1))
        # staved bucket with hoops and handle
        r = rng(f"cubo-{tag}")  # seed text kept so the geometry stays identical
        bc = V((trough_x + X(0.95), ty0 + 0.32, FL))
        nb = 14 if lod == 0 else 7
        g.cyl(bc, bc + V((0, 0, 0.38)), 0.17, nb, "Wood", caps=(True, False), r1=0.2)
        if lod == 0:
            g.cyl(bc + V((0, 0, 0.3)), bc + V((0, 0, 0.012)), 0.186, nb, "Floor", caps=(True, False), r1=0.171)
            for z, rr in ((0.07, 0.176), (0.3, 0.194)):
                g.cyl(bc + V((0, 0, z - 0.02)), bc + V((0, 0, z + 0.02)), rr + 0.004, nb, "Iron", caps=(False, False),
                      r1=rr + 0.006)
            pts = [bc + V((math.cos(a) * 0.205, 0, 0.37 + math.sin(a) * 0.17)) for a in
                   [i * math.pi / 8 for i in range(9)]]
            g.sweep(pts, 0.008, 4, "Iron")
            # gnawed bones
            for i in range(3):
                c = V((trough_x + X(r.uniform(-1.2, 1.6)), ty0 + r.uniform(0.9, 2.6), FL))
                a = r.uniform(0, math.pi)
                d = V((math.cos(a), math.sin(a), 0))
                L = r.uniform(0.22, 0.36)
                rr = 0.022
                p0, p1 = c - d * L / 2 + V((0, 0, rr + 0.012)), c + d * L / 2 + V((0, 0, rr + 0.012))
                g.cyl(p0, p1, rr, 6, "Straw", caps=(False, False))
                side = V((-d.y, d.x, 0)) * 0.022
                for p in (p0, p1):
                    for sg in (-1, 1):
                        g.blob(p + side * sg - V((0, 0, rr + 0.012)), 0.03, 0.03, 0.035, 6, 2, "Straw", r, 0.1)
        return g

    register(f"{tag}_Trough", "deco", trough, bbox_phys(trough), (0, 0, 2, 3))

    # ------------------------------------------------------------ straw
    def straw(lod):
        g = Geo()
        r = rng(f"paja-{tag}")  # seed text kept so the geometry stays identical
        nu, nv = {0: (16, 5), 1: (8, 2), 2: (5, 1), 3: (4, 1)}[lod]
        bench_x = X(10.75)
        g.blob((bench_x, yc + hay_y, FL + 0.45), 0.75, 1.25, 0.28, nu, nv, "Straw", r, 0.18 if lod == 0 else 0.05,
               flat_bottom=(lod <= 1))
        if lod <= 1:
            g.blob((X(9.5), yc + hay_y * 0.6 + 0.4, FL), 0.55, 0.8, 0.14, nu, max(nv - 1, 1), "Straw", r, 0.2)
        if lod == 0:
            for i in range(40):  # loose wisps on top of the pile
                a = r.uniform(0, 2 * math.pi)
                p = V((bench_x + r.uniform(-0.6, 0.6), yc + hay_y + r.uniform(-1.0, 1.0), FL + 0.45 + 0.24))
                d = V((math.cos(a), math.sin(a), r.uniform(-0.3, 0.3))).normalized()
                pr = V((-d.y, d.x, 0)).normalized() * 0.007
                L = r.uniform(0.15, 0.32)
                g.face([p - d * L / 2 - pr, p + d * L / 2 - pr, p + d * L / 2 + pr, p - d * L / 2 + pr], "Straw",
                       (0, 0, 1))
        return g

    register(f"{tag}_Straw", "deco", straw, bbox_phys(straw))


def _fx(fr, u0, u1, d0, d1):
    """Range (x0,x1,y0,y1) for boxes aligned with the frame of a front (u=Y, n=±X)."""
    p0 = fr.p(u0, 0, d0)
    p1 = fr.p(u1, 0, d1)
    return p0.x, p1.x, p0.y, p1.y


# ================================================================== YARD
def make_yard():
    for k in range(4):
        y0, y1 = YP[k], YP[k + 1]
        yc = (y0 + y1) / 2

        def floor(lod, y0=y0, y1=y1, yc=yc, k=k):
            # seed text "nave-" kept so the geometry stays identical
            return flagstones(f"nave-{k}", -NX, NX, y0, y1, lod, channel=True, grate_y=yc)

        register(f"P{k + 1}_Floor_Yard", "structure", floor,
                 lambda y0=y0, y1=y1: [pbox(-NX, NX, y0, y1, FL - 0.3, FL)], BIG)

    for j in range(5):
        yj = YP[j]

        def beam(lod, yj=yj):
            g = Geo()
            c = 0.03 if lod == 0 else 0
            bx(g, -NX - 0.25, NX + 0.25, yj - 0.17, yj + 0.17, 6.30, 6.74, "Wood", c,
               skip=("-x", "+x", "+z") if lod >= 2 else ())
            if lod <= 1:
                for s in (-1, 1):  # stone corbels
                    g.prism([(0.0, 5.7), (0.46, 6.18), (0.46, 6.30), (0.0, 6.30)],
                            Frame((s * NX, 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)), yj - 0.23, yj + 0.23,
                            "Stone")
            if lod == 0:
                for s in (-1, 1):  # iron straps
                    for xx in (s * (NX - 0.55), s * (NX - 0.75)):
                        bx(g, xx - 0.035, xx + 0.035, yj - 0.18, yj + 0.18, 6.29, 6.75, "Iron")
            return g

        register(f"T{j + 1}_Beam", "deco", beam, bbox_phys(beam), BIG)

    for j in (1, 2, 3):
        yj = YP[j]

        def lantern_piece(lod, yj=yj, j=j):
            return lantern(V((0, yj, 6.30)), lod, f"farol-{j}")  # seed text kept

        register(f"T{j + 1}_Lantern", "deco", lantern_piece, bbox_phys(lantern_piece), SMALL)

    # torches on the piers facing the yard
    for j in range(5):
        for s in (-1, 1):
            y = YP[j]
            nm = f"A{j + 1}{'W' if s < 0 else 'E'}_Torch"

            def torch_piece(lod, y=y, s=s):
                return torch(V((s * NX, y, FL + 2.25)), V((-s, 0, 0)), lod, f"antorcha-{y}-{s}")  # seed text kept

            register(nm, "deco", torch_piece, bbox_phys(torch_piece), SMALL)


def flagstones(seed, x0, x1, y0, y1, lod, channel=False, grate_y=None):
    """Irregular flagstone paving laid in courses, with an optional central drainage channel."""
    g = Geo()
    r = rng(f"losas-{seed}")  # seed text kept so the geometry stays identical
    cw = 0.22
    if lod >= 2:
        g.face([V((x0, y0, FL)), V((x1, y0, FL)), V((x1, y1, FL)), V((x0, y1, FL))], "Floor", (0, 0, 1))
        if lod == 2:
            bx(g, x0, x1, y0, y1, ZB, FL, "Floor", skip=("+z", "-z"))
        return g
    bands = [(x0, -cw), (cw, x1)] if channel else [(x0, x1)]
    gap = 0.014
    # base (visible through the joints)
    bx(g, x0, x1, y0, y1, ZB, FL - 0.03, "Floor", skip=("-z",))
    if lod == 1:
        g.faces, g.verts, g.mats = [], [], []
        for a, b in bands:
            g.face([V((a, y0, FL)), V((b, y0, FL)), V((b, y1, FL)), V((a, y1, FL))], "Floor", (0, 0, 1))
        if channel:
            g.face([V((-cw, y0, FL - 0.12)), V((cw, y0, FL - 0.12)), V((cw, y1, FL - 0.12)), V((-cw, y1, FL - 0.12))],
                   "Stone", (0, 0, 1))
            for sg in (-1, 1):
                g.face([V((sg * cw, y0, FL - 0.12)), V((sg * cw, y1, FL - 0.12)), V((sg * cw, y1, FL)),
                        V((sg * cw, y0, FL))], "Floor", (-sg, 0, 0))
            if grate_y is not None:
                g.face([V((-cw, grate_y - 0.4, FL - 0.005)), V((cw, grate_y - 0.4, FL - 0.005)),
                        V((cw, grate_y + 0.4, FL - 0.005)), V((-cw, grate_y + 0.4, FL - 0.005))], "Iron", (0, 0, 1))
        return g
    else:
        for a, b in bands:
            y = y0
            row = 0
            while y < y1 - 0.05:
                L = r.uniform(0.62, 1.05)
                yn = min(y + L, y1)
                if y1 - yn < 0.35:
                    yn = y1
                x = a
                ncols = max(1, round((b - a) / r.uniform(0.75, 1.1)))
                cuts = sorted([a] + [a + (b - a) * (i + r.uniform(-0.2, 0.2)) / ncols for i in range(1, ncols)] + [b])
                for i in range(len(cuts) - 1):
                    xa, xb = cuts[i] + gap / 2, cuts[i + 1] - gap / 2
                    zt = FL - r.uniform(0.0, 0.008)
                    g.slab(xa, y + gap / 2, xb, yn - gap / 2, FL - 0.03, zt, 0.018, "Floor")
                y = yn
                row += 1
    if channel:
        # channel: side pieces and sunken bottom
        bx(g, -cw, cw, y0, y1, ZB, FL - 0.12, "Stone", skip=("-z", "-y", "+y"))
        if grate_y is not None and lod <= 1:
            gy0, gy1 = grate_y - 0.4, grate_y + 0.4
            bx(g, -cw - 0.01, cw + 0.01, gy0, gy0 + 0.04, FL - 0.03, FL, "Iron")
            bx(g, -cw - 0.01, cw + 0.01, gy1 - 0.04, gy1, FL - 0.03, FL, "Iron")
            for i in range(9 if lod == 0 else 4):
                xx = -cw + (2 * cw) * (i + 0.5) / (9 if lod == 0 else 4)
                bx(g, xx - 0.012, xx + 0.012, gy0, gy1, FL - 0.03, FL, "Iron")
    return g


def torch(P0, n, lod, seed):
    """Wall torch: plate, arm, ring, wooden handle, tow and flame (face 0)."""
    g = Geo()
    r = rng(seed)
    up = V((0, 0, 1))
    u = up.cross(n).normalized()
    fr = Frame(P0, u, up, n)
    ring_c = fr.p(0, 0.18, 0.27)
    tilt = (n * 0.22 + up).normalized()
    t0 = ring_c - tilt * 0.22
    t1 = ring_c + tilt * 0.36
    head = t1 + tilt * 0.13
    if lod == 3:
        g.cyl(t0, head, 0.04, 3, "Wood", caps=(False, False))
        g.spike(head, 0.3, 0.07, "Flame")
        return g
    sides = {0: 8, 1: 5, 2: 3}[lod]
    if lod == 0:
        g.bbox(fr.p(-0.075, -0.17, 0.0) - n * 0.0, fr.p(0.075, 0.17, 0.0) + n * 0.025, "Iron", 0.006)
        for b in (-0.12, 0.12):
            p = fr.p(0, b, 0.025)
            g.cyl(p, p + n * 0.012, 0.014, 6, "Iron", caps=(False, True), r1=0.004)
    else:
        g.prism([(-0.075, -0.17), (0.075, -0.17), (0.075, 0.17), (-0.075, 0.17)], fr, 0.0, 0.025, "Iron",
                caps=(False, True))
    # scrolled arm: from the plate to the ring
    arm = [fr.p(0, -0.1, 0.02), fr.p(0, -0.06, 0.14), fr.p(0, 0.05, 0.2), ring_c - n * 0.045]
    g.sweep(arm, 0.014, 4 if lod <= 1 else 3, "Iron")
    if lod <= 1:
        low_c = ring_c - tilt * 0.12
        g.link(ring_c, n, u, 0.042, 0.042, 0.01, 12 if lod == 0 else 6, 4 if lod == 0 else 3, "Iron")
        g.link(low_c, n, u, 0.036, 0.036, 0.009, 10 if lod == 0 else 6, 3, "Iron")
        g.cyl(ring_c - n * 0.042, low_c - n * 0.036, 0.008, 4, "Iron", caps=(False, False))
    g.cyl(t0, t1, 0.026, sides, "Wood", caps=(True, False), r1=0.036)
    g.cyl(t1, head, 0.05, sides, "Straw", caps=(True, True), r1=0.045)
    if lod == 0:
        g.flame(head, 0.36, 0.075, 7, "Flame", r, lean=n * 0.04)
        g.flame(head + u * 0.025, 0.24, 0.05, 5, "Flame", r, lean=u * 0.05)
    else:
        g.flame(head, 0.34, 0.075, 5 if lod == 1 else 3, "Flame", r)
    return g


def lantern(P_top, lod, seed):
    """Cage lantern hanging from the beam on a short chain."""
    g = Geo()
    r = rng(seed)
    up = V((0, 0, 1))
    if lod == 3:
        zc = P_top.z - 0.85
        g.cyl(V((P_top.x, P_top.y, zc - 0.35)), V((P_top.x, P_top.y, zc + 0.15)), 0.2, 3, "Iron", caps=(False, False))
        g.spike(V((P_top.x, P_top.y, zc - 0.2)), 0.2, 0.05, "Flame")
        g.cyl(V((P_top.x, P_top.y, zc + 0.15)), P_top, 0.012, 3, "Iron", caps=(False, False))
        return g
    # staple under the beam and vertical chain
    a_c, b_c, wr = 0.045, 0.028, 0.009
    pitch = 2 * (a_c - wr)
    sc = P_top + V((0, 0, -0.02))
    if lod <= 1:
        g.link(sc, V((0, 0, -1)), V((1, 0, 0)), 0.04, 0.03, 0.01, 8, 4, "Iron")
    top_link = sc + V((0, 0, -0.04 + (0.01 + wr) - a_c))
    n_links = 9
    for i in range(n_links):
        c = top_link + V((0, 0, -pitch * i))
        if lod == 0:
            w = V((0, 1, 0)) if i % 2 == 0 else V((1, 0, 0))
            g.link(c, V((0, 0, -1)), w, a_c, b_c, wr, 10, 4, "Iron")
    bottom = top_link + V((0, 0, -pitch * (n_links - 1) - a_c))
    if lod >= 1:
        g.cyl(sc, bottom, 0.012, 3, "Iron", caps=(False, False))
    # cage
    ztop = bottom.z - 0.03
    h, w = 0.55, 0.19
    c0 = V((P_top.x, P_top.y, ztop))
    if lod <= 2:
        g.link(c0 + V((0, 0, 0.0)), V((0, 0, 1)), V((1, 0, 0)), 0.05, 0.05, 0.012, 10 if lod == 0 else 6, 3,
               "Iron")
    roof_b = ztop - 0.18
    # small pyramidal roof
    corners = [V((P_top.x + a * w * 1.15, P_top.y + b * w * 1.15, roof_b)) for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
    apex = V((P_top.x, P_top.y, ztop - 0.03))
    for i in range(4):
        g.face_c([corners[i], corners[(i + 1) % 4], apex], "Iron", V((P_top.x, P_top.y, roof_b - 0.1)))
    g.face(corners, "Iron", (0, 0, -1))
    zb = roof_b - h
    if lod <= 2:
        for a, b in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            p0 = V((P_top.x + a * w, P_top.y + b * w, zb))
            bx(g, p0.x - 0.016, p0.x + 0.016, p0.y - 0.016, p0.y + 0.016, zb, roof_b, "Iron")
    bx(g, P_top.x - w - 0.03, P_top.x + w + 0.03, P_top.y - w - 0.03, P_top.y + w + 0.03, zb - 0.05, zb, "Iron",
       0.01 if lod == 0 else 0)
    if lod <= 1:
        for z in (zb + h * 0.5,):
            for a in (-1, 1):
                bx(g, P_top.x - w, P_top.x + w, P_top.y + a * w - 0.01, P_top.y + a * w + 0.01, z - 0.012, z + 0.012,
                   "Iron")
                bx(g, P_top.x + a * w - 0.01, P_top.x + a * w + 0.01, P_top.y - w, P_top.y + w, z - 0.012, z + 0.012,
                   "Iron")
        if lod == 0:
            for a in (-1, 1):
                for t in (-0.33, 0.33):
                    bar(g, V((P_top.x + t * w, P_top.y + a * w, zb)), V((P_top.x + t * w, P_top.y + a * w, roof_b)),
                        0.008, 4, "Iron")
                    bar(g, V((P_top.x + a * w, P_top.y + t * w, zb)), V((P_top.x + a * w, P_top.y + t * w, roof_b)),
                        0.008, 4, "Iron")
    # thick candle and flame
    cand0 = V((P_top.x, P_top.y, zb))
    g.cyl(cand0, cand0 + V((0, 0, 0.2)), 0.06, {0: 10, 1: 6, 2: 4, 3: 3}[lod], "Straw", caps=(False, True))
    g.flame(cand0 + V((0, 0, 0.2)), 0.16 if lod == 0 else 0.15, 0.035, {0: 6, 1: 4, 2: 3, 3: 3}[lod], "Flame", r)
    return g


# ================================================================== HALL AND GATE
def make_entrance():
    YF0, YF1 = -16.0, -15.2          # front wall
    YT0, YT1 = -18.0, -14.4          # towers
    TX0, TX1 = 2.0, 6.0
    YV1 = YP[0] - PT                  # south face of partition 0

    for s in (-1, 1):
        S = "W" if s < 0 else "E"
        X = lambda x, s=s: s * x

        def front_wall(lod, s=s, X=X):
            g = Geo()
            if lod >= 1:
                sk = ("-z", flipx(("-x",), s)[0]) + (("+y",) if lod == 3 else ())
                bx(g, X(TX1), X(XO), YF0, YF1, ZB if lod == 1 else FL, WT + 0.18, "Stone", skip=sk)
                bx(g, X(9.2 - 0.45), X(9.2 + 0.45), YF0 - 0.6, YF0, ZB if lod == 1 else FL, FL + 5.6, "Stone",
                   skip=("-z", "+y"))
                bx(g, X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, ZB if lod == 1 else FL, FL + 5.4, "Stone",
                   skip=("-z", "+y"))
                return g
            sk = ("-z",)
            bx(g, X(TX1), X(XO), YF0, YF1, ZB, WT, "Stone", skip=sk + flipx(("-x",), s))
            if lod <= 1:
                bx(g, X(TX1), X(XO + 0.07), YF0 - 0.07, YF1 + 0.05, WT, WT + 0.18, "Stone", 0.03 if lod == 0 else 0,
                   skip=flipx(("-x",), s))
                # central buttress
                for xx in (9.2,):
                    bx(g, X(xx - 0.45), X(xx + 0.45), YF0 - 0.6, YF0, ZB, FL + 5.0, "Stone",
                       0.03 if lod == 0 else 0, skip=("-z", "+y"))
                    g.prism([(YF0, FL + 5.0), (YF0 - 0.6, FL + 5.0), (YF0, FL + 6.3)],
                            Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), X(xx - 0.45), X(xx + 0.45), "Stone")
            # L-shaped corner buttress
            if lod <= 2:
                bx(g, X(XO - 0.9), X(XO), YF0 - 0.6, YF0, ZB, FL + 5.4, "Stone", 0.03 if lod == 0 else 0,
                   skip=("-z", "+y"))
                bx(g, X(XO), X(XB), YF0 - 0.6, YF0 + 0.9, ZB, FL + 5.4, "Stone", 0.03 if lod == 0 else 0,
                   skip=("-z",) + flipx(("-x",), s))
            if lod == 0:  # battered plinth
                g.prism([(YF0, ZB), (YF0 - 0.12, ZB), (YF0 - 0.12, FL + 0.35), (YF0, FL + 0.5)],
                        Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), *sorted((X(TX1), X(XO - 0.9))), "Stone")
            return g

        register(f"G_Wall_{S}", "structure", front_wall, lod_map=BIG, phys=
                 lambda X=X: [pbox(X(TX1), X(XO), YF0, YF1, ZB, WT + 0.18),
                              pbox(X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, ZB, FL + 5.4)])

        def side_wall(lod, s=s, X=X):
            g = Geo()
            y0, y1 = YF1, YP[0]
            if lod >= 1:
                inner = flipx(("-x",), s)[0]
                zb = ZB if lod == 1 else FL
                bx(g, X(XI), X(XO), y0, y1, zb, WT + 0.18, "Stone",
                   skip=("-z", "+y", "-y") + ((inner,) if lod == 3 else ()))
                bx(g, X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, zb, FL + 5.6, "Stone", skip=("-z", inner))
                if lod == 1:
                    bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT + 0.18, "Stone",
                       skip=("-z", "+y", "-x", "+x"))
                else:
                    bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, WT, WT + 0.18, "Stone",
                       skip=("-z", "+y", "-y", "-x", "+x"))
                return g
            sk = ("-z",) if lod <= 2 else ("-z", "-x" if s > 0 else "+x")
            bx(g, X(XI), X(XO), y0, y1, ZB, WT, "Stone", skip=sk + ("+y",))
            if lod <= 1:
                bx(g, X(XI - 0.05), X(XO + 0.07), y0, y1, WT, WT + 0.18, "Stone", 0.03 if lod == 0 else 0,
                   skip=("+y",))
            # buttress on the axis of partition 0
            yb0, yb1 = YP[0] - 0.45, YP[0] + 0.45
            if lod <= 2:
                bx(g, X(XO), X(XB), yb0, yb1, ZB, FL + 5.0, "Stone", 0.03 if lod == 0 else 0,
                   skip=("-z",) + flipx(("-x",), s))
                g.prism([(X(XO), FL + 5.0), (X(XB), FL + 5.0), (X(XO), FL + 6.3)],
                        Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0, yb1, "Stone")
            # partition 0 (closes the first cell; faces the hall)
            bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT, "Stone",
               skip=("-z",) + flipx(("-x", "+x"), s))
            if lod <= 1:
                bx(g, X(NX + FT - 0.05), X(XI), YP[0] - PT - 0.06, YP[0] + PT + 0.06, WT, WT + 0.18, "Stone",
                   0.03 if lod == 0 else 0)
            return g

        register(f"V_Wall_{S}", "structure", side_wall, lod_map=BIG, phys=
                 lambda X=X: [pbox(X(XI), X(XO), YF1, YP[0], ZB, WT + 0.18),
                              pbox(X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, ZB, FL + 5.0),
                              pbox(X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT + 0.18)])

        def tower_piece(lod, s=s, X=X):
            return tower(lod, s, X, TX0, TX1, YT0, YT1)

        register(f"G_Tower_{S}", "structure", tower_piece, lod_map=BIG, phys=
                 lambda X=X: [pbox(X(TX0), X(TX1), YT0, YT1, ZB, 10.6),
                              pbox(X(TX0), X(TX1 + 0.35), YT0 - 0.35, YT1, ZB, FL + 0.5),
                              pbox(X(TX0), X(TX1 + 0.2), YT0 - 0.2, YT1, ZB, FL + 1.1)])

        for i, xx in enumerate((7.7,)):
            def torch_h(lod, s=s, xx=xx):
                return torch(V((s * xx, YV1, FL + 2.3)), V((0, -1, 0)), lod, f"antv-{s}")  # seed text kept

            register(f"A0{S}_Torch_Hall", "deco", torch_h, bbox_phys(torch_h), SMALL)

            def torch_f(lod, s=s):
                return torch(V((s * 9.2, YF1, FL + 2.3)), V((0, 1, 0)), lod, f"antf-{s}")  # seed text kept

            register(f"A9{S}_Torch_Front", "deco", torch_f, bbox_phys(torch_f), SMALL)

    # hall floors (three sections to limit the radius of each piece)
    for i, (x0, x1) in enumerate(((-XI, -4.0), (-4.0, 4.0), (4.0, XI))):
        def hall_floor(lod, x0=x0, x1=x1, i=i):
            return flagstones(f"vest-{i}", x0, x1, YF1, YP[0], lod)  # seed text kept

        register(f"V_Floor_{i + 1}", "structure", hall_floor, lambda x0=x0, x1=x1: [pbox(x0, x1, YF1, YP[0], FL - 0.3, FL)],
                 BIG)

    def passage(lod):
        return flagstones("paso", -TX0, TX0, YT0, YF1, lod)  # seed text kept

    register("G_Floor_Passage", "structure", passage, lambda: [pbox(-TX0, TX0, YT0, YF1, FL - 0.3, FL)], BIG)

    def stairs(lod):
        g = Geo()
        c = 0.02 if lod == 0 else 0
        if lod == 3:
            bx(g, -3.0, 3.0, -19.2, YT0, -0.1, 0.2, "Stone", skip=("-z", "+y", "-x", "+x"))
            bx(g, -3.0, 3.0, -18.6, YT0, 0.2, FL, "Stone", skip=("-z", "+y", "-x", "+x"))
            return g
        bx(g, -3.0, 3.0, -19.2, YT0, -0.4, 0.0 + 0.2, "Stone", c, skip=("-z", "+y"))
        bx(g, -3.0, 3.0, -18.6, YT0, 0.2, FL, "Stone", c, skip=("-z", "+y"))
        if lod <= 1:
            for s in (-1, 1):  # side stringers
                bx(g, s * 3.0, s * 3.35, -19.25, YT0, -0.4, FL + 0.15, "Stone", c, skip=("-z",))
        return g

    register("G_Stairs", "structure", stairs, lod_map=(0, 0, 3, 3), phys=
             lambda: [pbox(-3.0, 3.0, -19.2, YT0, -0.4, 0.2), pbox(-3.0, 3.0, -18.6, YT0, 0.2, FL),
                      pbox(-3.35, -3.0, -19.25, YT0, -0.4, FL + 0.15), pbox(3.0, 3.35, -19.25, YT0, -0.4, FL + 0.15)])

    # -------------------------------------------------- entrance arch, passage and vault
    def arch(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        sp, ra = 3.4, 0.62
        top = 9.6
        fr_out = Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        arch_wall(g, fr_out, -TX0, TX0, 0.0, sp, ra, FL + 2.9, ZB, top, 0.8, n_side, "Stone",
                  skip_u0=True, skip_u1=True, thr_top=FL, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
        fr_in = Frame((0, YT1, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
        arch_wall(g, fr_in, -TX0, TX0, 0.0, sp, ra, FL + 3.1, ZB, top, 0.8, n_side, "Stone",
                  skip_u0=True, skip_u1=True, thr_top=FL, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
        if lod == 1:
            tp = pointed_arch(sp, ra, n_side)
            fr_t = Frame((0, YT1 - 0.35, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
            g.prism([(u, FL + 3.1 + v) for u, v in tp], fr_t, -0.06, 0.06, "Wood", caps=(False, True))
            bx(g, -TX0, TX0, YT0 - 0.3, YF1, top, top + 1.0, "Stone", skip=("-z", "-x", "+x"))
            return g
        if lod == 3:
            bx(g, -TX0, TX0, YT0, YT1, top, top + 1.0, "Stone", skip=("-z", "-x", "+x"))
            return g
        if lod <= 2:
            # pointed vault over the passage, between the two arches
            fr_v = Frame((0, YT0 + 0.8, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
            pts = pointed_arch(2 * TX0, 0.62, n_side)
            for i in range(len(pts) - 1):
                (a0, b0), (a1, b1) = pts[i], pts[i + 1]
                q = [fr_v.p(a0, FL + 3.0 + b0, 0), fr_v.p(a1, FL + 3.0 + b1, 0),
                     fr_v.p(a1, FL + 3.0 + b1, -(YF1 - YT0 - 0.8)), fr_v.p(a0, FL + 3.0 + b0, -(YF1 - YT0 - 0.8))]
                g.face(q, "Stone", V((0, 0, FL + 1.0)) - sum(q, V()) / 4 + V((0, sum(q, V()).y / 4, 0)))
            bx(g, -TX0, TX0, YT0 + 0.8, YF1, top - 0.02, top, "Stone")
        if lod <= 1:
            # wooden tympanum above the leaves
            tp = pointed_arch(sp, ra, n_side)
            fr_t = Frame((0, YT1 - 0.35, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
            poly = [(u, FL + 3.1 + v) for u, v in tp]
            g.prism(poly, fr_t, -0.06, 0.06, "Wood")
            # parapet between the towers on corbels
            bx(g, -TX0, TX0, YT0 - 0.3, YT0 + 0.05, top, top + 0.95, "Stone", 0.03 if lod == 0 else 0)
            bx(g, -TX0, TX0, YT0 - 0.37, YT0 + 0.12, top + 0.95, top + 1.1, "Stone", 0.03 if lod == 0 else 0)
            bx(g, -TX0, TX0, YF1 - 0.35, YF1, top, top + 0.95, "Stone", 0.03 if lod == 0 else 0)
        if lod == 0:
            for fr_, spring in ((fr_out, FL + 2.9), (fr_in, FL + 3.1)):
                voussoirs(g, fr_, 0.0, spring, sp, ra, 6, 0.6, 0.07, "Stone")
            hood(g, fr_out, 0.0, FL + 2.9, sp, ra, 12, 0.74, 0.14, 0.12, "Stone")
            for i in range(6):  # corbels under the parapet
                xx = -TX0 + 0.35 + i * (2 * TX0 - 0.7) / 5
                g.prism([(0.0, top - 0.42), (0.0, top), (0.3, top), (0.3, top - 0.16)],
                        Frame((0, YT0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0)), xx - 0.11, xx + 0.11, "Stone")
            # plain shield carved above the keystone (for the user's emblem)
            shield = [(-0.42, 7.0), (0.42, 7.0), (0.42, 7.75), (0.0, 7.95), (-0.42, 7.75)]
            g.prism(shield,
                    Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.09, "Stone", caps=(False, True))
            # pivot sockets of the leaves and drawbar brackets
            for s in (-1, 1):
                for z in (FL + 0.5, FL + 2.6):
                    bx(g, s * 1.70, s * 1.84, YT1, YT1 + 0.06, z - 0.05, z + 0.05, "Iron")
                bx(g, s * 1.9, s * 2.0, YT1, YT1 + 0.16, FL + 1.5, FL + 1.64, "Iron")
        return g

    register("G_Arch", "structure", arch, lod_map=BIG, phys=
             lambda: [pbox(-TX0, TX0, YT0, YT0 + 0.8, FL + 5.0, 9.6), pbox(-TX0, TX0, YT1 - 0.8, YT1, FL + 5.2, 9.6),
                      pbox(-TX0, TX0, YT0 + 0.8, YT1 - 0.8, FL + 5.45, 9.6),
                      pbox(-TX0, -1.7, YT0, YT0 + 0.8, ZB, 9.6), pbox(1.7, TX0, YT0, YT0 + 0.8, ZB, 9.6),
                      pbox(-TX0, -1.7, YT1 - 0.8, YT1, ZB, 9.6), pbox(1.7, TX0, YT1 - 0.8, YT1, ZB, 9.6)])

    # -------------------------------------------------- portcullis
    def portcullis(lod):
        g = Geo()
        y0, y1 = YT0 + 0.34, YT0 + 0.46
        x0, x1 = -1.76, 1.76
        zb, zt = FL + 0.14, FL + 5.6
        if lod == 3:
            for y in (y0, y1):
                g.face([V((x0, y, zb)), V((x1, y, zb)), V((x1, y, zt)), V((x0, y, zt))], "Wood",
                       (0, -1 if y == y0 else 1, 0))
            return g
        nv, nh = {0: (13, 10), 1: (9, 7)}.get(lod, (5, 4))
        for i in range(nv):
            x = x0 + 0.04 + (x1 - x0 - 0.08) * i / (nv - 1)
            bx(g, x - 0.045, x + 0.045, y0, y1, zb, zt, "Wood", 0.01 if lod == 0 else 0,
               skip=() if lod == 0 else ("-z", "+z"))
            if lod <= 1:
                g.cyl(V((x, (y0 + y1) / 2, zb)), V((x, (y0 + y1) / 2, FL - 0.0)), 0.05, 4, "Iron",
                      caps=(True, False), r1=0.0, phase=math.pi / 4)
        for j in range(nh):
            z = zb + 0.25 + (zt - zb - 0.35) * j / (nh - 1)
            bx(g, x0, x1, y0 - 0.04, y0, z - 0.045, z + 0.045, "Wood", 0.01 if lod == 0 else 0,
               skip=() if lod == 0 else ("-x", "+x", "+y"))
            if lod == 0:
                for i in range(nv):  # nails at the crossings
                    x = x0 + 0.04 + (x1 - x0 - 0.08) * i / (nv - 1)
                    p = V((x, y0 - 0.04, z))
                    g.cyl(p, p + V((0, -0.015, 0)), 0.016, 4, "Iron", caps=(False, True), r1=0.005)
        return g

    register("G_Portcullis", "door", portcullis, bbox_phys(portcullis), BIG)

    # -------------------------------------------------- gate leaves
    for s in (-1, 1):
        S = "W" if s < 0 else "E"

        def leaf(lod, s=s):
            return gate_leaf(lod, s, YT1)

        register(f"G_Leaf_{S}", "door", leaf,
                 lambda s=s: [pbox(s * 0.005, s * 1.76, YT1 + 0.01, YT1 + 0.13, FL + 0.03, FL + 3.08)])


def gate_leaf(lod, s, yface):
    """Studded wooden leaf with ironwork on both faces. Hinge at x = s*1.80."""
    g = Geo()
    y0, y1 = yface + 0.012, yface + 0.13
    yc = (y0 + y1) / 2
    xa, xb = sorted((s * 0.005, s * 1.76))
    z0, z1 = FL + 0.03, FL + 3.08
    if lod == 3:
        g.box(V((xa, y0, z0)), V((xb, y1, z1)), "Wood", skip=("-z", "+z", "-x", "+x"))
        return g
    n_pl = {0: 6, 1: 3, 2: 1}[lod]
    w = (xb - xa) / n_pl
    for i in range(n_pl):
        bx(g, xa + i * w + 0.004, xa + (i + 1) * w - 0.004, y0, y1, z0, z1, "Wood", 0.012 if lod == 0 else 0)
    if lod == 2:
        return g
    hinge_x = s * 1.80
    for z in (FL + 0.5, FL + 1.55, FL + 2.6):
        for yy, sg in ((y0, -1), (y1, 1)):
            bx(g, xa + 0.03, xb - 0.03, yy, yy + sg * 0.012, z - 0.055, z + 0.055, "Iron")
            if lod == 0:
                for i in range(9):
                    x = xa + 0.1 + (xb - xa - 0.2) * i / 8
                    p = V((x, yy + sg * 0.012, z))
                    g.cyl(p, p + V((0, sg * 0.018, 0)), 0.017, 4, "Iron", caps=(False, True), r1=0.004)
        if z != FL + 1.55:
            g.cyl(V((hinge_x, yc, z - 0.08)), V((hinge_x, yc, z + 0.08)), 0.035, 8 if lod == 0 else 4, "Iron")
            bx(g, *sorted((hinge_x, hinge_x - s * 0.06)), y0, y1, z - 0.03, z + 0.03, "Iron")
    if lod == 0:
        for sg, yy in ((1, y1), (-1, y0)):
            n = V((0, sg, 0))
            sc = V((s * 0.32, yy, FL + 1.3)) + n * 0.02
            g.link(sc, n, V((0, 0, 1)), 0.045, 0.028, 0.01, 8, 4, "Iron")
            rc = sc + n * 0.015 + V((0, 0, -(0.028 - 0.01) + 0.012 - 0.1))
            g.link(rc, V((1, 0, 0)), V((0, 0, 1)), 0.1, 0.1, 0.012, 16, 5, "Iron")
            g.bbox(V((s * 0.32 - 0.07, min(yy, yy + sg * 0.015), FL + 1.24)),
                   V((s * 0.32 + 0.07, max(yy, yy + sg * 0.015), FL + 1.42)), "Iron", 0.004)
    return g


def tower(lod, s, X, x0, x1, y0, y1):
    g = Geo()
    zt = 9.6
    c = 0.03 if lod == 0 else 0
    xa, xb = sorted((X(x0), X(x1)))
    inner = "-x" if s > 0 else "+x"
    if lod == 3:
        bx(g, xa, xb, y0, y1, FL, 10.6, "Stone", skip=("-z", inner))
        return g
    # battered base
    batter = 0.35 if lod <= 1 else 0.0
    if batter:
        o_lo = [V((xa - (batter if s < 0 else 0), y0 - batter, ZB)), V((xb + (batter if s > 0 else 0), y0 - batter, ZB)),
                V((xb + (batter if s > 0 else 0), y1, ZB)), V((xa - (batter if s < 0 else 0), y1, ZB))]
        o_hi = [V((xa, y0, FL + 1.8)), V((xb, y0, FL + 1.8)), V((xb, y1, FL + 1.8)), V((xa, y1, FL + 1.8))]
        ctr = V(((xa + xb) / 2, (y0 + y1) / 2, 0.5))
        for i in range(4):
            j = (i + 1) % 4
            g.face_c([o_lo[i], o_lo[j], o_hi[j], o_hi[i]], "Stone", ctr)
    zb = FL + 1.8 if batter else ZB
    # body with arrow slits on the south and outer faces
    if lod == 0:
        slit_w, sz0, sz1 = 0.09, 5.2, 6.7
        xm = (xa + xb) / 2
        ym = (y0 + y1) / 2
        rec = 0.3
        # south face and outer face with cross slits (two heights)
        xo = xb if s > 0 else xa
        xr = xo - s * rec
        for (za, zb_, zs0, zs1) in ((zb, 6.2, 3.3, 4.7), (6.2, zt, 6.9, 8.6)):
            cross_slit_skin(g, lambda a, b, c, d: (a, b, y0, y0 + rec, c, d), xa, xb, za, zb_, xm, zs0, zs1,
                            "Stone", skip=("+y",))
            cross_slit_skin(g, lambda a, b, c, d: (xo, xr, a, b, c, d), y0 + rec, y1, za, zb_, ym, zs0, zs1,
                            "Stone", skip=(inner,))
        # core
        xi0, xi1 = sorted((X(x0), xr))
        bx(g, xi0, xi1, y0 + rec, y1, zb, zt, "Stone", skip=("-z", "+z"))
    else:
        bx(g, xa, xb, y0, y1, zb, zt, "Stone", skip=("-z",))
    # corbels, parapet and roof
    if lod == 1:
        po = 0.3
        exa = xa - (po if s < 0 else 0)
        exb = xb + (po if s > 0 else 0)
        bx(g, exa, exb, y0 - po, y1, zt, 10.6, "Stone", skip=("-z",))
        return g
    if lod == 0:
        nc = 6
        for i in range(nc):
            xx = xa + 0.3 + (xb - xa - 0.6) * i / (nc - 1)
            g.prism([(0.0, zt - 0.5), (0.0, zt), (0.3, zt), (0.3, zt - 0.18)],
                    Frame((0, y0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0)), xx - 0.1, xx + 0.1, "Stone")
        for i in range(nc):
            yy = y0 + 0.3 + (y1 - y0 - 0.6) * i / (nc - 1)
            xo = xb if s > 0 else xa
            g.prism([(0.0, zt - 0.5), (0.0, zt), (0.3, zt), (0.3, zt - 0.18)],
                    Frame((xo, 0, 0), (s, 0, 0), (0, 0, 1), (0, 1, 0)), yy - 0.1, yy + 0.1, "Stone")
    po = 0.3 if lod <= 1 else 0.0
    exa = xa - (po if s < 0 else 0)
    exb = xb + (po if s > 0 else 0)
    t = 0.4
    bx(g, exa, exb, y0 - po, y0 - po + t, zt, 10.6, "Stone", c)
    bx(g, exa, exb, y1 - t, y1, zt, 10.6, "Stone", c)
    bx(g, exa, exa + t, y0 - po + t, y1 - t, zt, 10.6, "Stone", c)
    bx(g, exb - t, exb, y0 - po + t, y1 - t, zt, 10.6, "Stone", c)
    bx(g, exa + t, exb - t, y0 - po + t, y1 - t, zt - 0.02, zt + 0.25, "Stone", skip=("-z",))
    if lod == 0:
        # wooden door into the tower from the hall, with stone jambs
        xm = (xa + xb) / 2
        bx(g, xm - 0.55, xm + 0.55, y1, y1 + 0.06, FL, FL + 2.25, "Wood", 0.01)
        for a in (-1, 1):
            bx(g, xm + a * 0.55 - 0.12, xm + a * 0.55 + 0.12, y1, y1 + 0.1, FL, FL + 2.4, "Stone", 0.02)
            for z in (FL + 0.45, FL + 1.8):
                bx(g, xm - 0.5, xm + 0.4, y1 + 0.06, y1 + 0.075, z - 0.04, z + 0.04, "Iron")
        bx(g, xm - 0.67, xm + 0.67, y1, y1 + 0.12, FL + 2.4, FL + 2.7, "Stone", 0.02)
    return g


# ================================================================== KENNEL MASTER'S HALL
def make_north():
    YN0 = YP[4] + PT     # 11.8
    YB0, YB1 = 15.2, 16.0
    DAIS = FL + 0.9
    STEP_Y0, STEP_HW = 11.0, 2.2   # dais stairs: leave 0.8 m aisles on each side
    NS_SP, NS_RA, NS_SPR = 3.2, 0.6, DAIS + 2.0

    for s in (-1, 1):
        S = "W" if s < 0 else "E"
        X = lambda x, s=s: s * x

        def lateral(lod, s=s, X=X):
            g = Geo()
            if lod >= 1:
                inner = flipx(("-x",), s)[0]
                zb = ZB if lod == 1 else FL
                bx(g, X(XI), X(XO), YP[4], YB1, zb, WT + 0.18, "Stone",
                   skip=("-z", "-y") + ((inner,) if lod == 3 else ()))
                bx(g, X(XO), X(XB), YB1 - 0.9, YB1, zb, FL + 5.4, "Stone", skip=("-z", inner))
                bx(g, X(4.5), X(XI), YB0, YB1, zb, WT + 0.18, "Stone",
                   skip=("-z", flipx(("+x",), s)[0]) + (("-y",) if lod == 3 else ()))
                return g
            sk = ("-z",) if lod <= 2 else ("-z", "-x" if s > 0 else "+x")
            bx(g, X(XI), X(XO), YP[4], YB1, ZB, WT, "Stone", skip=sk + ("-y",))
            if lod <= 1:
                bx(g, X(XI - 0.05), X(XO + 0.07), YP[4], YB1 + 0.07, WT, WT + 0.18, "Stone",
                   0.03 if lod == 0 else 0, skip=("-y",))
            if lod <= 2:
                bx(g, X(XO), X(XB), YB1 - 0.9, YB1, ZB, FL + 5.4, "Stone", 0.03 if lod == 0 else 0,
                   skip=("-z",) + flipx(("-x",), s))
            # back wall, side section
            bx(g, X(4.5), X(XI), YB0, YB1, ZB, WT, "Stone", skip=("-z",) + flipx(("+x",), s))
            if lod <= 1:
                bx(g, X(4.5), X(XI), YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Stone", 0.03 if lod == 0 else 0)
            return g

        register(f"N_Wall_{S}", "structure", lateral, lod_map=BIG, phys=
                 lambda X=X: [pbox(X(XI), X(XO), YP[4], YB1, ZB, WT + 0.18), pbox(X(4.5), X(XI), YB0, YB1, ZB, WT + 0.18),
                              pbox(X(XO), X(XB), YB1 - 0.9, YB1, ZB, FL + 5.4)])

        def floor_n(lod, s=s, X=X):
            x0, x1 = sorted((X(4.5), X(XI)))
            return flagstones(f"norte-{s}", x0, x1, YN0, YB0, lod)  # seed text kept

        register(f"N_Floor_{S}", "structure", floor_n,
                 lambda X=X: [pbox(X(4.5), X(XI), YN0, YB0, FL - 0.3, FL)], BIG)

        def torch_n(lod, s=s):
            return torch(V((s * 2.75, YB0, DAIS + 2.2)), V((0, -1, 0)), lod, f"antn-{s}")  # seed text kept

        register(f"A8{S}_Torch_Niche", "deco", torch_n, bbox_phys(torch_n), SMALL)

    def floor_c(lod):
        return flagstones("norte-c", -4.5, 4.5, YP[4], YB0, lod)  # seed text kept

    register("N_Floor_C", "structure", floor_c, lambda: [pbox(-4.5, 4.5, YP[4], YB0, FL - 0.3, FL)], BIG)

    # central back wall with a pointed niche
    def back_wall(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        fr = Frame((0, YB0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        depth = 0.5
        arch_wall(g, fr, -4.5, 4.5, 0.0, NS_SP, NS_RA, NS_SPR, DAIS, WT, depth, n_side, "Stone",
                  skip_u0=True, skip_u1=True, thr_top=None, front_only=(lod == 3), back=False, top=(lod == 0))
        # back of the niche and rear of the wall
        bx(g, -4.5, 4.5, YB0 + depth, YB1, ZB if lod <= 1 else FL, WT + (0 if lod == 0 else 0.18), "Stone",
           skip=("-z", "-x", "+x") + (("-y",) if lod == 3 else ()))
        if lod == 0:
            bx(g, -4.5, 4.5, YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Stone", 0.03, skip=("-x", "+x"))
            voussoirs(g, fr, 0.0, NS_SPR, NS_SP, NS_RA, 6, 0.5, 0.07, "Stone")
            hood(g, fr, 0.0, NS_SPR, NS_SP, NS_RA, 12, 0.62, 0.14, 0.12, "Stone")
            # smoke hood: ledge and flue above the niche
            bx(g, -1.9, 1.9, YB0 - 0.35, YB0, DAIS + 4.85, DAIS + 5.05, "Stone", 0.03)
            g.prism([(-1.7, DAIS + 5.05), (1.7, DAIS + 5.05), (0.9, WT), (-0.9, WT)],
                    Frame((0, YB0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.3, "Stone", caps=(False, True))
        return g

    register("N_Wall_Back", "structure", back_wall, lod_map=BIG, phys=
             lambda: [pbox(-4.5, -NS_SP / 2, YB0, YB1, ZB, WT + 0.18), pbox(NS_SP / 2, 4.5, YB0, YB1, ZB, WT + 0.18),
                      pbox(-NS_SP / 2, NS_SP / 2, YB0 + 0.5, YB1, ZB, WT + 0.18),
                      pbox(-NS_SP / 2, NS_SP / 2, YB0, YB0 + 0.5, NS_SPR + 1.9, WT + 0.18)])

    # dais with steps (ramp physics)
    def dais(lod):
        g = Geo()
        c = 0.03 if lod == 0 else 0
        bx(g, -4.5, 4.5, 12.6, YB0 + 0.5, FL - 0.1, DAIS, "Stone", c, skip=("-z", "+y"))
        steps = 4 if lod <= 1 else 1
        for i in range(steps):
            rise = (DAIS - FL) * (i + 1) / steps
            y_front = STEP_Y0 + (12.6 - STEP_Y0) * i / steps
            bx(g, -STEP_HW, STEP_HW, y_front, 12.6, FL - 0.1, FL + rise, "Stone", c * 0.7, skip=("-z", "+y"))
        return g

    def dais_phys():
        y_top = 12.6 - (12.6 - STEP_Y0) / 4
        out = [pbox(-4.5, 4.5, 12.6, YB0 + 0.5, FL - 0.1, DAIS), pbox(-STEP_HW, STEP_HW, y_top, 12.6, FL - 0.1, DAIS)]
        # invisible ramp over the step edges (walk up without tripping)
        out.append(("RAMP", V((-STEP_HW, STEP_Y0 - 0.1, FL)), V((STEP_HW, 12.6 - (12.6 - STEP_Y0) / 4, DAIS))))
        return out

    register("N_Dais", "structure", dais, dais_phys, BIG)

    def brazier_piece(lod):
        return brazier(V((0, 14.35, DAIS)), lod)

    register("N_Brazier", "deco", brazier_piece, bbox_phys(brazier_piece), SMALL)

    def wall_rings(lod):
        g = Geo()
        r = rng("argollas")  # seed text kept so the geometry stays identical
        for s in (-1, 1):
            x = s * 2.75
            if lod == 3:
                continue
            bottom, ring_c, u = wall_anchor(g, (x, YB0, DAIS + 1.35), V((0, -1, 0)), V((0, 0, 1)), lod)
            if lod <= 1:
                a_c, b_c, wr = 0.06, 0.036, 0.013
                start = bottom + V((0, 0, (0.016 + wr) - a_c))
                path = [start + V((0, -0.02 * (i / 30) ** 2, -0.55 * i / 30)) for i in range(31)]
                centers = chain(g, path, a_c, b_c, wr, lod, r, -10)
                end = centers[-1] + V((0, 0, -(a_c - wr) - 0.012))
                cl = end + V((0, 0, -0.16))
                g.link(cl, V((0, 0, 1)), V((1, 0, 0)), 0.16, 0.16, 0.022, 18 if lod == 0 else 8,
                       5 if lod == 0 else 3, "Iron")
        if lod == 3:
            g.face([V((-2.85, YB0 - 0.01, DAIS + 0.5)), V((-2.65, YB0 - 0.01, DAIS + 0.5)),
                    V((-2.75, YB0 - 0.01, DAIS + 1.4))], "Iron", (0, -1, 0))
            g.face([V((2.65, YB0 - 0.01, DAIS + 0.5)), V((2.85, YB0 - 0.01, DAIS + 0.5)),
                    V((2.75, YB0 - 0.01, DAIS + 1.4))], "Iron", (0, -1, 0))
        return g

    register("N_Rings", "deco", wall_rings, bbox_phys(wall_rings), BIG)

    # hay bales and barrels in the hall
    def bales(lod):
        g = Geo()
        r = rng("pacas")  # seed text kept so the geometry stays identical
        spots = [(-8.6, 14.4, 0, 0.1), (-7.4, 14.4, 0, -0.05), (-8.0, 14.45, 1, 0.08), (-9.9, 13.2, 0, 1.45),
                 (-6.3, 14.5, 0, 0.02)]
        for (x, y, lvl, a) in spots:
            L, W, H = 1.05, 0.52, 0.45
            z0 = FL + lvl * H
            cs, sn = math.cos(a), math.sin(a)
            corners = [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2)]
            poly = [(x + cx * cs - cy * sn, y + cx * sn + cy * cs) for cx, cy in corners]
            fr = Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
            if lod == 3:
                g.face([V((p[0], p[1], z0 + H)) for p in poly], "Straw", (0, 0, 1))
                continue
            g.prism(poly, fr, z0, z0 + H, "Straw", caps=(lod <= 1 and lvl > 0, True))
            if lod == 0:  # binding cords
                for t in (-0.25, 0.25):
                    cx, cy = x + t * L * cs, y + t * L * sn
                    q = [V((cx + (-W / 2 - 0.006) * -sn - 0.015 * cs, cy + (-W / 2 - 0.006) * cs - 0.015 * sn, z0 + H + 0.006)),
                         V((cx + (W / 2 + 0.006) * -sn - 0.015 * cs, cy + (W / 2 + 0.006) * cs - 0.015 * sn, z0 + H + 0.006)),
                         V((cx + (W / 2 + 0.006) * -sn + 0.015 * cs, cy + (W / 2 + 0.006) * cs + 0.015 * sn, z0 + H + 0.006)),
                         V((cx + (-W / 2 - 0.006) * -sn + 0.015 * cs, cy + (-W / 2 - 0.006) * cs + 0.015 * sn, z0 + H + 0.006))]
                    g.face(q, "Wood", (0, 0, 1))
        if lod <= 1:
            g.blob((-8.0, 13.6, FL), 0.9, 0.6, 0.16, 10 if lod == 0 else 6, 2, "Straw", r, 0.2)
        return g

    register("N_Bales", "deco", bales, bbox_phys(bales), (0, 0, 1, 3))

    def barrels(lod):
        g = Geo()
        if lod == 3:
            g.face([V((6.72, 13.6, FL + 0.9)), V((8.05, 14.4, FL + 0.9)), V((6.9, 14.8, FL + 0.9))], "Wood",
                   (0, 0, 1))
            g.face([V((6.72, 13.6, FL)), V((8.05, 14.4, FL)), V((8.05, 14.4, FL + 0.9)), V((6.72, 13.6, FL + 0.9))],
                   "Wood", (0, -1, 0))
            return g
        for (x, y) in ((7.0, 14.5), (7.75, 14.65), (7.35, 13.85)):
            n = {0: 14, 1: 8, 2: 5, 3: 4}[lod]
            prof = [(0.0, 0.27), (0.18, 0.31), (0.45, 0.33), (0.72, 0.31), (0.9, 0.27)] if lod <= 1 else \
                [(0.0, 0.28), (0.9, 0.28)]
            rings = [[V((x + math.cos(2 * math.pi * k / n) * rr, y + math.sin(2 * math.pi * k / n) * rr, FL + h))
                      for k in range(n)] for h, rr in prof]
            ctr = V((x, y, FL + 0.45))
            for i in range(len(rings) - 1):
                for k in range(n):
                    k2 = (k + 1) % n
                    g.face_c([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], "Wood", ctr)
            g.face(rings[-1], "Wood", (0, 0, 1))
            if lod == 0:
                for h, rr in ((0.1, 0.295), (0.8, 0.295), (0.3, 0.325), (0.6, 0.325)):
                    g.cyl(V((x, y, FL + h - 0.025)), V((x, y, FL + h + 0.025)), rr + 0.006, n, "Iron",
                          caps=(False, False))
        return g

    register("N_Barrels", "deco", barrels, bbox_phys(barrels), (0, 0, 1, 3))


def brazier(P, lod):
    g = Geo()
    r = rng("brasero")  # seed text kept so the geometry stays identical
    bowl_r, bowl_z = 0.62, P.z + 0.95
    if lod == 3:
        g.cyl(V((P.x, P.y, P.z)), V((P.x, P.y, bowl_z)), 0.2, 3, "Iron", caps=(False, False), r1=bowl_r)
        g.spike(V((P.x, P.y, bowl_z - 0.05)), 1.1, 0.35, "Flame")
        return g
    n = {0: 20, 1: 10, 2: 6, 3: 4}[lod]
    # bowl
    prof = [(0.0, 0.25), (0.12, 0.5), (0.25, 0.6), (0.33, bowl_r)] if lod <= 1 else [(0.0, 0.3), (0.33, bowl_r)]
    rings = [[V((P.x + math.cos(2 * math.pi * k / n) * rr, P.y + math.sin(2 * math.pi * k / n) * rr, bowl_z + h - 0.33))
              for k in range(n)] for h, rr in prof]
    ctr = V((P.x, P.y, bowl_z + 0.3))
    for i in range(len(rings) - 1):
        for k in range(n):
            k2 = (k + 1) % n
            g.face_c([rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]], "Iron", ctr)
    g.face(rings[0], "Iron", (0, 0, -1))
    if lod <= 1:
        g.link(V((P.x, P.y, bowl_z)), V((1, 0, 0)), V((0, 1, 0)), bowl_r, bowl_r, 0.035, n, 4 if lod == 0 else 3,
               "Iron")
    # embers
    g.blob((P.x, P.y, bowl_z - 0.06), bowl_r * 0.93, bowl_r * 0.93, 0.16, max(n // 2, 4), 2 if lod <= 1 else 1,
           "Floor", r, 0.12, flat_bottom=False)
    # curved legs
    for i in range(3):
        a = 2 * math.pi * i / 3 + 0.3
        d = V((math.cos(a), math.sin(a), 0))
        top = V((P.x, P.y, bowl_z - 0.3)) + d * 0.32
        knee = V((P.x, P.y, P.z + 0.45)) + d * 0.55
        foot = V((P.x, P.y, P.z)) + d * 0.72
        if lod == 0:
            pts = []
            for k in range(9):
                t = k / 8
                p = top * (1 - t) ** 2 + knee * 2 * t * (1 - t) + foot * t * t
                pts.append(p)
            pts[-1].z = P.z + 0.025
            g.sweep(pts, 0.035, 6, "Iron")
            g.cyl(foot + V((0, 0, 0.0)), foot + V((0, 0, 0.05)), 0.07, 8, "Iron", caps=(False, True), r1=0.045)
        else:
            g.cyl(top, foot, 0.04, 4 if lod <= 2 else 3, "Iron", caps=(False, False))
    # flames
    nf = {0: 7, 1: 4, 2: 2, 3: 1}[lod]
    for i in range(nf):
        a = 2 * math.pi * i / max(nf, 1) + r.uniform(-0.3, 0.3)
        rad = 0.0 if i == 0 else r.uniform(0.15, 0.38)
        base = V((P.x + math.cos(a) * rad, P.y + math.sin(a) * rad, bowl_z + 0.04))
        g.flame(base, r.uniform(0.55, 0.95) * (1.3 if i == 0 else 1), r.uniform(0.12, 0.2), 7 if lod == 0 else 4,
                "Flame", r, lean=V((r.uniform(-0.08, 0.08), r.uniform(-0.08, 0.08), 0)))
    return g


def build_all():
    PIECES.clear()
    for s in (-1, 1):
        for k in range(4):
            make_cell(k, s)
    make_yard()
    make_entrance()
    make_north()
    return PIECES

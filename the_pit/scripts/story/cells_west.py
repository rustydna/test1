"""Story details: cells_west (see story/__init__.py for the rules).

West row of cells (x < -3): C01 The Press-Gang, C02 The Rack, C03 The Stocks, C04 The Cistern.

Conventions (story bible, section 13): soot, char, ink, tar and dark grooves are Iron; salt, chalk,
lime, tallow and wax are Bone; mud and dark spills are Floor or Iron; rope, cord, weed and straw
figures are Straw; paper, leather and cloth are Cloth. Candle flames are Flame (they glow).

Everything is HIGH-LOD only (lod 0) except a single silhouette quad for each room board (lod 1).
Every item stays inside its piece's bounding box. Surfaces without slack (the thin partitions)
carry "incised" marks a hair proud of the face (EPS); the outer walls have 4 cm of slack.
Floor details are draped over the real (bumpy) earth floor, rebuilt here from the same seed.
"""

import math

from mathutils import Matrix, Vector

from geo import Frame, Geo, rng
from pieces import FL, PT, VS, XI, YP, R_VAULT, bx, wall_anchor

from . import decorates

V = Vector
EPS = 0.0               # "incised": flush with the surface (partitions have no slack at all)
RI = R_VAULT            # intrados radius of the cell vaults
CXV = -7.7              # vault centre (x) of every west cell
WX = -XI                # inner face of the outer wall (x = -11.6)


def ycen(n):
    """Centre (y) of cell C0n."""
    return (YP[n - 1] + YP[n]) / 2


def yspan(n):
    return YP[n - 1] + PT, YP[n] - PT


# ================================================================== surface frames
def wall_fr():
    """Inner face of the outer wall; u = +y (reader's right), v = up, n = into the room (+x)."""
    return Frame((WX, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))


def south_face_fr(y):
    """Face of a partition looking south (-y), read from the south: u = +x."""
    return Frame((0, y, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))


def north_face_fr(y):
    """Face of a partition looking north (+y), read with u = +x (matches world x)."""
    return Frame((0, y, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))


def yard_fr():
    """Yard face of the west fronts (x = -3), read from the yard: u = +y."""
    return Frame((-3.0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))


# ================================================================== strokes and lettering
_O = [(0.12, 0), (0.48, 0), (0.6, 0.2), (0.6, 0.8), (0.48, 1), (0.12, 1), (0, 0.8), (0, 0.2), (0.12, 0)]
_P = [(0, 0), (0, 1), (0.45, 1), (0.6, 0.85), (0.6, 0.62), (0.45, 0.48), (0, 0.48)]
FONT = {
    "A": [[(0, 0), (0.3, 1), (0.6, 0)], [(0.12, 0.38), (0.48, 0.38)]],
    "B": [[(0, 0), (0, 1), (0.45, 1), (0.58, 0.85), (0.58, 0.64), (0.42, 0.52), (0, 0.52)],
          [(0.42, 0.52), (0.6, 0.38), (0.6, 0.14), (0.46, 0), (0, 0)]],
    "C": [[(0.6, 0.85), (0.45, 1), (0.12, 1), (0, 0.8), (0, 0.2), (0.12, 0), (0.45, 0), (0.6, 0.15)]],
    "D": [[(0, 0), (0, 1), (0.35, 1), (0.6, 0.72), (0.6, 0.28), (0.35, 0), (0, 0)]],
    "E": [[(0.6, 1), (0, 1), (0, 0), (0.6, 0)], [(0, 0.52), (0.42, 0.52)]],
    "F": [[(0.6, 1), (0, 1), (0, 0)], [(0, 0.52), (0.42, 0.52)]],
    "G": [[(0.6, 0.85), (0.45, 1), (0.12, 1), (0, 0.8), (0, 0.2), (0.12, 0), (0.6, 0), (0.6, 0.45), (0.32, 0.45)]],
    "H": [[(0, 0), (0, 1)], [(0.6, 0), (0.6, 1)], [(0, 0.52), (0.6, 0.52)]],
    "I": [[(0.3, 0), (0.3, 1)]],
    "J": [[(0.6, 1), (0.6, 0.2), (0.45, 0), (0.15, 0), (0, 0.2)]],
    "K": [[(0, 0), (0, 1)], [(0.6, 1), (0, 0.4)], [(0.2, 0.58), (0.6, 0)]],
    "L": [[(0, 1), (0, 0), (0.6, 0)]],
    "M": [[(0, 0), (0, 1), (0.3, 0.45), (0.6, 1), (0.6, 0)]],
    "N": [[(0, 0), (0, 1), (0.6, 0), (0.6, 1)]],
    "O": [_O],
    "P": [_P],
    "Q": [_O, [(0.35, 0.25), (0.65, -0.1)]],
    "R": [_P, [(0.25, 0.48), (0.6, 0)]],
    "S": [[(0.6, 0.85), (0.45, 1), (0.12, 1), (0, 0.85), (0, 0.62), (0.15, 0.5), (0.45, 0.5), (0.6, 0.38),
           (0.6, 0.15), (0.45, 0), (0.12, 0), (0, 0.15)]],
    "T": [[(0, 1), (0.6, 1)], [(0.3, 1), (0.3, 0)]],
    "U": [[(0, 1), (0, 0.2), (0.15, 0), (0.45, 0), (0.6, 0.2), (0.6, 1)]],
    "V": [[(0, 1), (0.3, 0), (0.6, 1)]],
    "W": [[(0, 1), (0.13, 0), (0.3, 0.6), (0.47, 0), (0.6, 1)]],
    "X": [[(0, 0), (0.6, 1)], [(0, 1), (0.6, 0)]],
    "Y": [[(0, 1), (0.3, 0.5), (0.6, 1)], [(0.3, 0.5), (0.3, 0)]],
    "Z": [[(0, 1), (0.6, 1), (0, 0), (0.6, 0)]],
    "0": [_O],
    "1": [[(0.12, 0.8), (0.3, 1), (0.3, 0)]],
    "2": [[(0, 0.8), (0.15, 1), (0.45, 1), (0.6, 0.8), (0.6, 0.62), (0, 0), (0.6, 0)]],
    "3": [[(0, 1), (0.6, 1), (0.25, 0.58), (0.45, 0.55), (0.6, 0.38), (0.6, 0.15), (0.45, 0), (0.12, 0), (0, 0.15)]],
    "4": [[(0.45, 0), (0.45, 1), (0, 0.3), (0.6, 0.3)]],
    "5": [[(0.6, 1), (0, 1), (0, 0.55), (0.45, 0.55), (0.6, 0.4), (0.6, 0.15), (0.45, 0), (0, 0)]],
    "6": [[(0.55, 1), (0.15, 1), (0, 0.8), (0, 0.15), (0.15, 0), (0.45, 0), (0.6, 0.15), (0.6, 0.4), (0.45, 0.55),
           (0, 0.55)]],
    "7": [[(0, 1), (0.6, 1), (0.2, 0)]],
    "8": [[(0.15, 0.52), (0, 0.68), (0, 0.85), (0.15, 1), (0.45, 1), (0.6, 0.85), (0.6, 0.68), (0.45, 0.52),
           (0.15, 0.52), (0, 0.38), (0, 0.15), (0.15, 0), (0.45, 0), (0.6, 0.15), (0.6, 0.38), (0.45, 0.52)]],
    "9": [[(0.6, 0.45), (0.15, 0.45), (0, 0.6), (0, 0.85), (0.15, 1), (0.45, 1), (0.6, 0.85), (0.6, 0.15),
           (0.45, 0), (0.05, 0)]],
    ".": [[(0.24, 0), (0.36, 0.1)]],
    ",": [[(0.32, 0.1), (0.2, -0.15)]],
    "-": [[(0.1, 0.5), (0.5, 0.5)]],
    "(": [[(0.45, 1.05), (0.2, 0.75), (0.2, 0.25), (0.45, -0.05)]],
    ")": [[(0.15, 1.05), (0.4, 0.75), (0.4, 0.25), (0.15, -0.05)]],
    "'": [[(0.3, 1), (0.25, 0.75)]],
    "/": [[(0, 0), (0.6, 1)]],
}


def stroke(g, fr, pts, w, mat, lift):
    """Flat polyline strip on a frame (u, v) lifted `lift` along its normal. Joints share their
    vertices (they are welded on export), so a strip costs 2 triangles a segment."""
    pts = [V((a, b)) for a, b in pts]
    if len(pts) < 2:
        return
    hw = w / 2
    offs = []
    for i in range(len(pts)):
        if i == 0:
            d = (pts[1] - pts[0])
        elif i == len(pts) - 1:
            d = (pts[-1] - pts[-2])
        else:
            d0 = (pts[i] - pts[i - 1]).normalized()
            d1 = (pts[i + 1] - pts[i]).normalized()
            d = d0 + d1
            if d.length < 1e-6:
                d = d1
        if d.length < 1e-9:
            d = V((1, 0))
        d = d.normalized()
        nrm = V((-d.y, d.x))
        k = hw
        if 0 < i < len(pts) - 1:
            d0 = (pts[i] - pts[i - 1]).normalized()
            c = abs(nrm.x * -d0.y + nrm.y * d0.x)
            k = hw / max(c, 0.5)
        offs.append(nrm * k)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if (b - a).length < 1e-6:
            continue
        q = [a + offs[i], b + offs[i + 1], b - offs[i + 1], a - offs[i]]
        g.face([fr.p(p.x, p.y, lift) for p in q], mat, fr.n)


def text(g, fr, s, u0, v0, h, mat, lift, w=None, rnd=None, jit=0.0, slant=0.0, adv=0.85, keep=None):
    """Carved / painted capitals. Returns the width used. `jit` roughens a scratched hand;
    `keep` (0..1) drops random strokes for a worn or hacked inscription."""
    w = w or h * 0.13
    u = u0
    for ch in s:
        if ch == " ":
            u += h * 0.55
            continue
        for line in FONT.get(ch, []):
            if keep is not None and rnd is not None and rnd.random() > keep:
                continue
            pts = []
            for a, b in line:
                du = dv = 0.0
                if rnd is not None and jit:
                    du, dv = rnd.uniform(-jit, jit) * h, rnd.uniform(-jit, jit) * h
                pts.append((u + (a + b * slant) * h + du, v0 + b * h + dv))
            stroke(g, fr, pts, w, mat, lift)
        u += h * adv
    return u - u0


def text_width(s, h, adv=0.85):
    return sum(h * 0.55 if c == " " else h * adv for c in s)


def tally(g, fr, u0, v0, count, h, mat, lift, rnd, w=None, group=5, gap=None, per_row=None, row_gap=None):
    """Tally strokes grouped in fives (four upright, the fifth across) or tens (`group` 10)."""
    w = w or h * 0.08
    pitch = h * 0.2
    gap = gap or h * 0.45
    u, v = u0, v0
    done = 0
    in_row = 0
    while done < count:
        n = min(group, count - done)
        upright = n if (n < group or group == 10) else group - 1
        for i in range(upright):
            x = u + i * pitch + rnd.uniform(-0.15, 0.15) * pitch
            stroke(g, fr, [(x, v + rnd.uniform(0, 0.08) * h), (x + rnd.uniform(-0.1, 0.1) * h,
                                                                v + h * rnd.uniform(0.92, 1.05))], w, mat, lift)
        width = (upright - 1) * pitch
        if n == group:
            stroke(g, fr, [(u - pitch * 0.4, v + h * 0.2), (u + width + pitch * 0.4, v + h * 0.75)], w, mat, lift)
        done += n
        u += width + gap
        in_row += 1
        if per_row and in_row >= per_row:
            in_row = 0
            u = u0
            v -= row_gap or h * 1.4
    return u - u0


def blot(g, fr, a, b, ra, rb, k, mat, lift, rnd, jit=0.25, rot=0.0):
    """Irregular flat patch (stain, plaster, soot) as a triangle fan on a frame."""
    c = fr.p(a, b, lift)
    ring = []
    for i in range(k):
        t = 2 * math.pi * i / k
        r = 1 + rnd.uniform(-jit, jit)
        x, y = math.cos(t) * ra * r, math.sin(t) * rb * r
        ring.append(fr.p(a + x * math.cos(rot) - y * math.sin(rot), b + x * math.sin(rot) + y * math.cos(rot), lift))
    for i in range(k):
        g.face([c, ring[i], ring[(i + 1) % k]], mat, fr.n)


def rect(g, fr, a0, a1, b0, b1, mat, lift):
    g.face([fr.p(a0, b0, lift), fr.p(a1, b0, lift), fr.p(a1, b1, lift), fr.p(a0, b1, lift)], mat, fr.n)


# ================================================================== the earth floor of a cell
class FloorH:
    """Height of the bumpy earth floor of cell C0n (the grid of make_room_shell, same seed)."""

    def __init__(self, n):
        rr = rng(f"suelo-C{n:02d}")
        self.nx, self.ny = 14, 10
        self.y0, self.y1 = yspan(n)
        self.z = []
        for i in range(self.nx + 1):
            row = []
            for j in range(self.ny + 1):
                edge = i in (0, self.nx) or j in (0, self.ny)
                row.append(FL if edge else FL + rr.uniform(0.0, 0.035))
            self.z.append(row)

    def _both(self, x, y):
        fu = (-x - 3.8) / (XI - 3.8) * self.nx
        fv = (y - self.y0) / (self.y1 - self.y0) * self.ny
        fu = min(max(fu, 0.0), self.nx - 1e-6)
        fv = min(max(fv, 0.0), self.ny - 1e-6)
        i, j = int(fu), int(fv)
        u, v = fu - i, fv - j
        z00, z10, z01, z11 = self.z[i][j], self.z[i + 1][j], self.z[i][j + 1], self.z[i + 1][j + 1]
        a = z00 + u * (z10 - z00) + v * (z11 - z10) if u >= v else z00 + v * (z01 - z00) + u * (z11 - z01)
        b = z00 + u * (z10 - z00) + v * (z01 - z00) if u + v <= 1 else z11 + (1 - u) * (z01 - z11) + (1 - v) * (z10 - z11)
        return a, b

    def top(self, x, y, r=0.0):
        """Highest the surface can be at (x, y) (either triangulation), sampled over radius r."""
        pts = [(x, y)] + ([(x + r, y), (x - r, y), (x, y + r), (x, y - r)] if r else [])
        return max(max(self._both(px, py)) for px, py in pts)

    def low(self, x, y, r=0.0):
        pts = [(x, y)] + ([(x + r, y), (x - r, y), (x, y + r), (x, y - r)] if r else [])
        return min(min(self._both(px, py)) for px, py in pts)


_FLOORS = {}


def floor_h(n):
    if n not in _FLOORS:
        _FLOORS[n] = FloorH(n)
    return _FLOORS[n]


def floor_blot(g, fh, x, y, rx, ry, k, mat, rnd, rings=2, jit=0.25, rot=0.0, lift=0.004, holes=None):
    """Flat stain draped over the earth floor (polar mesh, every vertex just above the surface)."""
    def at(px, py):
        return V((px, py, fh.top(px, py, 0.05) + lift))
    ca, sa = math.cos(rot), math.sin(rot)
    jits = [1 + rnd.uniform(-jit, jit) for _ in range(k)]
    rows = [[at(x, y)]]
    for r in range(1, rings + 1):
        f = r / rings
        row = []
        for i in range(k):
            t = 2 * math.pi * i / k
            ex = math.cos(t) * rx * f * (jits[i] if r == rings else 1 + (jits[i] - 1) * 0.4)
            ey = math.sin(t) * ry * f * (jits[i] if r == rings else 1 + (jits[i] - 1) * 0.4)
            row.append(at(x + ex * ca - ey * sa, y + ex * sa + ey * ca))
        rows.append(row)
    up = V((0, 0, 1))
    for i in range(k):
        g.face([rows[0][0], rows[1][i], rows[1][(i + 1) % k]], mat, up)
    for r in range(1, rings):
        for i in range(k):
            j = (i + 1) % k
            g.face([rows[r][i], rows[r + 1][i], rows[r + 1][j], rows[r][j]], mat, up)


def floor_strip(g, fh, pts, w, mat, lift=0.004):
    """Thin draped streak along a polyline on the earth floor."""
    pts = [V((p[0], p[1], 0)) for p in pts]
    up = V((0, 0, 1))
    prev = None
    for i in range(len(pts)):
        d = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        side = d.cross(up) * (w / 2)
        a, b = pts[i] + side, pts[i] - side
        a.z = fh.top(a.x, a.y, 0.03) + lift
        b.z = fh.top(b.x, b.y, 0.03) + lift
        if prev:
            g.face([prev[0], a, b, prev[1]], mat, up)
        prev = (a, b)


# ================================================================== cutting a recess into a flat face
def cut_pocket(g, axis, val, nsign, a0, a1, b0, b1, depth, back_mat, side_mat):
    """Cuts a rectangular recess into the flat axis-aligned face lying on `axis` = val whose
    normal points to `nsign`: the face is replaced by four quads round the hole, plus the
    pocket (four sides and a back). The bounding box does not change."""
    ua, va = [i for i in range(3) if i != axis]
    found = None
    for idx, f in enumerate(g.faces):
        if len(f) != 4:
            continue
        vs = [g.verts[i] for i in f]
        if any(abs(v[axis] - val) > 1e-5 for v in vs):
            continue
        us, ws = [v[ua] for v in vs], [v[va] for v in vs]
        if min(us) <= a0 and max(us) >= a1 and min(ws) <= b0 and max(ws) >= b1:
            found = idx
            break
    if found is None:
        return False
    vs = [g.verts[i] for i in g.faces[found]]
    U0, U1 = min(v[ua] for v in vs), max(v[ua] for v in vs)
    W0, W1 = min(v[va] for v in vs), max(v[va] for v in vs)
    mat = g.mats[found]

    def P(u, w, d=0.0):
        p = [0.0, 0.0, 0.0]
        p[axis] = val - nsign * d
        p[ua], p[va] = u, w
        return V(p)
    nvec = [0.0, 0.0, 0.0]
    nvec[axis] = nsign
    quads = [(U0, a0, W0, W1), (a1, U1, W0, W1), (a0, a1, W0, b0), (a0, a1, b1, W1)]
    first = True
    for (p0, p1, q0, q1) in quads:
        if p1 - p0 < 1e-6 or q1 - q0 < 1e-6:
            continue
        pts = [P(p0, q0), P(p1, q0), P(p1, q1), P(p0, q1)]
        if first:
            tmp = Geo()
            tmp.face(pts, mat, nvec)
            i0 = len(g.verts)
            g.verts.extend(tmp.verts)
            g.faces[found] = tuple(i0 + k for k in range(4))
            first = False
        else:
            g.face(pts, mat, nvec)
    g.face([P(a0, b0, depth), P(a1, b0, depth), P(a1, b1, depth), P(a0, b1, depth)], back_mat, nvec)
    ctr = P((a0 + a1) / 2, (b0 + b1) / 2, depth / 2)
    for (p, q) in (((a0, b0), (a1, b0)), ((a1, b0), (a1, b1)), ((a1, b1), (a0, b1)), ((a0, b1), (a0, b0))):
        pts = [P(p[0], p[1]), P(q[0], q[1]), P(q[0], q[1], depth), P(p[0], p[1], depth)]
        m = sum(pts, V()) / 4
        g.face(pts, side_mat, ctr - m)
    return True


# ================================================================== vault surface
def vpt(yc, x, s, r=RI - 0.004):
    """Point on the intrados of a west cell vault: s = arc length from the crown (+ = north)."""
    a = s / r
    return V((x, yc + r * math.sin(a), VS + r * math.cos(a)))


def vnorm(s, r=RI):
    a = s / r
    return V((0, -math.sin(a), -math.cos(a)))


def vault_blot(g, yc, x, s, rx, rs, k, mat, rnd, jit=0.25, lift=0.004, rot=0.0):
    r = RI - lift
    c = vpt(yc, x, s, r)
    ring = []
    for i in range(k):
        t = 2 * math.pi * i / k
        f = 1 + rnd.uniform(-jit, jit)
        dx, ds = math.cos(t) * rx * f, math.sin(t) * rs * f
        ring.append(vpt(yc, x + dx * math.cos(rot) - ds * math.sin(rot), s + dx * math.sin(rot) + ds * math.cos(rot), r))
    for i in range(k):
        g.face([c, ring[i], ring[(i + 1) % k]], mat, vnorm(s))


def vault_stroke(g, yc, pts, w, mat, lift=0.004):
    """Strip on the intrados along (x, s) points."""
    r = RI - lift
    prev = None
    for i, (x, s) in enumerate(pts):
        j0, j1 = max(i - 1, 0), min(i + 1, len(pts) - 1)
        dx, ds = pts[j1][0] - pts[j0][0], pts[j1][1] - pts[j0][1]
        ln = math.hypot(dx, ds) or 1.0
        nx_, ns = -ds / ln * w / 2, dx / ln * w / 2
        a, b = vpt(yc, x + nx_, s + ns, r), vpt(yc, x - nx_, s - ns, r)
        if prev:
            g.face([prev[0], a, b, prev[1]], mat, vnorm(s))
        prev = (a, b)


def light_well(g, yc, rnd):
    """Opens the vault crown over the cell centre: a square shaft up through the vault (sky shows
    through it in SL; the build projects the moonlight from here) with a forged iron grate."""
    hw = 0.30                                   # half size along x
    hs = RI * math.cos(math.radians(82.5))      # the two crown strips of the 24-segment intrados
    xa, xb = CXV + hw, CXV - hw
    # 1. split the two crown strips of the intrados, leaving the hole
    for idx in range(len(g.faces)):
        f = g.faces[idx]
        if len(f) != 4 or g.mats[idx] != "Stone":
            continue
        vs = [g.verts[i] for i in f]
        if any(abs(math.hypot(v.y - yc, v.z - VS) - RI) > 1e-4 for v in vs):
            continue
        if max(abs(v.y - yc) for v in vs) > hs + 1e-3:
            continue
        xs = sorted({round(v.x, 4) for v in vs})
        if len(xs) != 2 or not (xs[0] < xb and xs[1] > xa):
            continue
        lo = [v for v in vs if abs(v.x - xs[0]) < 1e-4]
        hi = [v for v in vs if abs(v.x - xs[1]) < 1e-4]
        lo.sort(key=lambda v: v.y)
        hi.sort(key=lambda v: v.y)
        pa, pb = lo[0], lo[1]
        mid = V((CXV, yc, VS))
        A = [V((xa, pa.y, pa.z)), V((xa, pb.y, pb.z)), hi[1].copy(), hi[0].copy()]
        B = [lo[0].copy(), lo[1].copy(), V((xb, pb.y, pb.z)), V((xb, pa.y, pa.z))]
        tmp = Geo()
        tmp.face(A, "Stone", mid - sum(A, V()) / 4)
        i0 = len(g.verts)
        g.verts.extend(tmp.verts)
        g.faces[idx] = tuple(i0 + k for k in range(4))
        g.face(B, "Stone", mid - sum(B, V()) / 4)
    # 2. shaft lining up to the extrados
    zt = VS + RI + 0.275
    arc = [vpt(yc, 0, -hs, RI), vpt(yc, 0, 0, RI), vpt(yc, 0, hs, RI)]
    for x, sg in ((xa, -1), (xb, 1)):
        pts = [V((x, p.y, p.z)) for p in arc] + [V((x, yc + hs, zt)), V((x, yc - hs, zt))]
        g.face(pts, "Stone", (sg, 0, 0))
    ze = arc[0].z
    for y, sg in ((yc - hs, 1), (yc + hs, -1)):
        g.face([V((xb, y, ze)), V((xa, y, ze)), V((xa, y, zt)), V((xb, y, zt))], "Stone", (0, sg, 0))
    # 3. the grate: a flat frame round the shaft, three bars each way (they run into the stone)
    zg = VS + RI + 0.035
    t = 0.035
    bx(g, xb, xa, yc - hs, yc - hs + t, zg - 0.02, zg + 0.03, "Iron", skip=("-x", "+x"))
    bx(g, xb, xa, yc + hs - t, yc + hs, zg - 0.02, zg + 0.03, "Iron", skip=("-x", "+x"))
    bx(g, xb, xb + t, yc - hs, yc + hs, zg - 0.02, zg + 0.03, "Iron", skip=("-y", "+y"))
    bx(g, xa - t, xa, yc - hs, yc + hs, zg - 0.02, zg + 0.03, "Iron", skip=("-y", "+y"))
    for k in (-1, 0, 1):
        y = yc + k * hs / 2
        bx(g, xb, xa, y - 0.012, y + 0.012, zg - 0.012, zg + 0.012, "Iron", skip=("-x", "+x"))
        x = CXV + k * hw / 2
        bx(g, x - 0.012, x + 0.012, yc - hs, yc + hs, zg + 0.012, zg + 0.036, "Iron", skip=("-y", "+y"))
    # 4. rust and damp streaks running down the intrados from the mouth
    for sg in (-1, 1):
        for x in (CXV + rnd.uniform(-0.25, -0.05), CXV + rnd.uniform(0.05, 0.25)):
            s0 = sg * (hs + 0.01)
            L = rnd.uniform(0.35, 0.8)
            pts = [(x + rnd.uniform(-0.02, 0.02) * i, s0 + sg * L * i / 3) for i in range(4)]
            vault_stroke(g, yc, pts, rnd.uniform(0.025, 0.05), "Iron", 0.003)


# ================================================================== small objects
def vessel(g, c, r0, r1, h, n, mat, fill=None, fill_h=0.6, inner=True, wall=0.012):
    """Open turned vessel (bowl, bucket, pot): outer wall, rim, inner wall, and a filling surface."""
    c = V(c)
    ang = [2 * math.pi * i / n for i in range(n)]
    ob = [c + V((math.cos(a) * r0, math.sin(a) * r0, 0)) for a in ang]
    ot = [c + V((math.cos(a) * r1, math.sin(a) * r1, h)) for a in ang]
    ri0, ri1 = max(r0 - wall, 0.002), r1 - wall
    it = [c + V((math.cos(a) * ri1, math.sin(a) * ri1, h)) for a in ang]
    fz = h * fill_h
    rf = ri0 + (ri1 - ri0) * fill_h
    ib = [c + V((math.cos(a) * rf, math.sin(a) * rf, fz)) for a in ang]
    axis = c + V((0, 0, h / 2))
    for i in range(n):
        j = (i + 1) % n
        g.face_c([ob[i], ob[j], ot[j], ot[i]], mat, axis)
        g.face([ot[i], ot[j], it[j], it[i]], mat, (0, 0, 1))
        if inner:
            q = [it[i], it[j], ib[j], ib[i]]
            m = sum(q, V()) / 4
            g.face(q, mat, V((c.x, c.y, m.z)) - m)
    g.face(ib, fill or mat, (0, 0, 1))


def hoop(g, c, r, z, h, n, mat="Iron"):
    c = V(c)
    g.cyl(c + V((0, 0, z)), c + V((0, 0, z + h)), r, n, mat, caps=(False, False))


def spoon(g, p, ang, L, mat="Wood", tilt=0.0):
    p = V(p)
    d = V((math.cos(ang), math.sin(ang), tilt))
    sd = V((-d.y, d.x, 0)).normalized()
    a, b = p, p + d * L
    w = 0.006
    g.face([a - sd * w, b - sd * w, b + sd * w, a + sd * w], mat, (0, 0, 1))
    g.face([a - sd * w, b - sd * w, b + sd * w, a + sd * w], mat, (0, 0, -1))
    g.blob(b + d * 0.02 + V((0, 0, -0.004)), 0.022, 0.016, 0.006, 6, 1, mat, rng("spoon"), 0.05,
           rot=Matrix.Rotation(ang, 3, "Z"))


def candle(g, base, h, r, rnd, runs=3, puddle=1.8, mat="Bone", lit=True):
    """Tallow stub with wax runs, a puddle and (if lit) a small flame."""
    base = V(base)
    top = base + V((0, 0, h))
    g.cyl(base, top, r, 6, mat, caps=(False, True), phase=rnd.uniform(0, 1))
    for i in range(runs):
        a = rnd.uniform(0, 2 * math.pi)
        d = V((math.cos(a), math.sin(a), 0))
        L = rnd.uniform(0.5, 1.0) * h
        g.sweep([top + d * r * 0.9, top + d * (r + 0.003) - V((0, 0, L * 0.5)), top + d * (r + 0.004) - V((0, 0, L))],
                0.004, 3, mat)
    if puddle:
        g.blob(base, r * puddle, r * puddle * rnd.uniform(0.8, 1.1), 0.006, 7, 1, mat, rnd, 0.25)
    g.cyl(top, top + V((0, 0, 0.012)), 0.0018, 3, "Iron", caps=(False, False))
    if lit:
        g.flame(top + V((0, 0, 0.006)), 0.05, 0.011, 4, "Flame", rnd)


# ================================================================== C01 The Press-Gang
@decorates("C01_Vault")
def c01_vault(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-vault")
    yc = ycen(1)
    light_well(g, yc, rnd)
    # soot halo from the branding brazier below (south-west corner): a dark cloud on the intrados
    for i in range(4):
        s = -1.6 + i * 0.3 + rnd.uniform(-0.08, 0.08)
        vault_blot(g, yc, CXV - 1.6 + rnd.uniform(-0.3, 0.3), s, 0.5, 0.4, 8, "Iron", rnd, 0.3, 0.004)
    # six iron pegs with hats hung along the south springer (confiscated beavers, a knitted cap, a marine's hat)
    r_in = RI - 0.02
    s0 = -(R_VAULT * 0.78)
    for i in range(6):
        x = CXV - 2.3 + i * 0.9 + rnd.uniform(-0.04, 0.04)
        # peg
        pb = vpt(yc, x, s0, r_in)
        pt = pb + V((0, -0.08, -0.03))
        g.cyl(pb, pt, 0.012, 4, "Iron")
        # hat: a crumpled oval on and below the peg
        kind = i % 3
        hat_c = pt + V((0, -0.03, -0.14))
        if kind == 0:   # tricorn
            g.blob(hat_c, 0.14, 0.12, 0.05, 8, 2, "Cloth", rnd, 0.2)
            for a in (0, 2.1, 4.2):
                p = hat_c + V((math.cos(a) * 0.14, math.sin(a) * 0.12, 0.02))
                g.cyl(hat_c + V((0, 0, 0.015)), p, 0.012, 3, "Cloth", caps=(False, True))
        elif kind == 1:  # knitted cap
            g.blob(hat_c, 0.09, 0.08, 0.11, 8, 2, "Cloth", rnd, 0.25, flat_bottom=False)
        else:            # beaver merchant's hat
            g.cyl(hat_c + V((0, 0, -0.09)), hat_c + V((0, 0, 0.08)), 0.07, 8, "Cloth", r1=0.08)
            g.blob(hat_c + V((0, 0, -0.09)), 0.14, 0.13, 0.012, 10, 1, "Cloth", rnd, 0.1)


@decorates("C01_Wall")
def c01_wall(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-wall")
    yc = ycen(1)
    fr = wall_fr()
    # 1. three iron shackle rings (not the already-modelled ones on C01_Props: these are rust-shadow stains the hands left)
    for y in (yc - 1.2, yc - 0.4, yc + 0.4, yc + 1.2):
        for z in (FL + 1.6, FL + 1.95):
            blot(g, fr, y, z, 0.08, 0.055, 7, "Iron", 0.003, rnd, 0.35)
    # 2. 77 scratched beside the second ring with a hook cut later
    text(g, fr, "77", yc - 0.8, FL + 1.5, 0.11, "Iron", 0.004, rnd=rnd, jit=0.025, slant=0.08)
    hook_u, hook_v = yc - 0.52, FL + 1.5
    stroke(g, fr, [(hook_u, hook_v + 0.1), (hook_u, hook_v + 0.02), (hook_u + 0.05, hook_v - 0.015),
                   (hook_u + 0.08, hook_v + 0.015)], 0.009, "Iron", 0.006)   # the Lord's own, deeper
    # 3. ragged band of half-names scratched by chained men (started, abandoned)
    halfs = ["T", "WI", "ED", "SA", "J", "ROB", "N", "CHR"]
    u = yc - 1.1
    for s in halfs:
        h = rnd.uniform(0.045, 0.07)
        v = FL + 1.1 + rnd.uniform(-0.08, 0.04)
        text(g, fr, s, u, v, h, "Iron", 0.003, rnd=rnd, jit=0.04, slant=rnd.uniform(-0.08, 0.08))
        u += text_width(s, h) + rnd.uniform(0.03, 0.08)
    # 4. tally marks in fives on the north end of the wall
    tally(g, fr, yc + 1.4, FL + 1.3, 23, 0.07, "Iron", 0.003, rnd, per_row=4, row_gap=0.14)
    # 5. REFUSED REFUSED REFUSED (Absalom Reed) under the arrow slit area, high
    text(g, fr, "REFUSED", yc - 2.1, FL + 2.5, 0.085, "Iron", 0.004, rnd=rnd, jit=0.015)
    text(g, fr, "REFUSED", yc - 1.3, FL + 2.5, 0.085, "Iron", 0.004, rnd=rnd, jit=0.015)
    text(g, fr, "REFUSED", yc - 0.5, FL + 2.5, 0.085, "Iron", 0.004, rnd=rnd, jit=0.015)
    # 6. a few dark hand-stains at chest height
    for _ in range(5):
        y = yc + rnd.uniform(-2.3, 2.3)
        z = FL + rnd.uniform(1.1, 1.7)
        blot(g, fr, y, z, rnd.uniform(0.05, 0.09), rnd.uniform(0.06, 0.1), 7, "Floor", 0.002, rnd, 0.4)


@decorates("C01_Floor")
def c01_floor(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-floor")
    fh = floor_h(1)
    yc = ycen(1)
    # burnt ring and ash spill round the brazier (sw corner); the brazier sits at ~(-9.6, -10.3)
    floor_blot(g, fh, -9.6, -10.3, 0.75, 0.55, 14, "Iron", rnd, rings=3, jit=0.3, lift=0.003)
    # a molar at the east edge of the ring
    g.blob(V((-9.0, -10.3, fh.top(-9.0, -10.3, 0.03) + 0.004)), 0.01, 0.008, 0.012, 6, 2, "Bone", rnd, 0.1)
    # black bootprints walking from the brazier to the desk (sw -> ne)
    for i in range(6):
        t = i / 5
        bx_, by = -9.6 + t * 1.9 + rnd.uniform(-0.05, 0.05), -10.0 + t * 2.4 + rnd.uniform(-0.05, 0.05)
        for sx in (-1, 1):
            floor_blot(g, fh, bx_ + sx * 0.045, by + (i % 2) * 0.08, 0.065, 0.09, 6, "Iron", rnd, 1, 0.2, lift=0.002)
    # drips of sealing wax by the desk (red reads as Iron)
    for _ in range(5):
        floor_blot(g, fh, -7.6 + rnd.uniform(-0.4, 0.4), -7.95 + rnd.uniform(-0.1, 0.1),
                   rnd.uniform(0.015, 0.03), rnd.uniform(0.015, 0.03), 6, "Iron", rnd, 1, 0.2, lift=0.002)
    # three dropped chalk-numbered chits (Wood squares) by the clothes chest
    for i, num in enumerate((79, 80, 81)):
        px, py = -11.1 + rnd.uniform(-0.05, 0.05), -9.4 + i * 0.08
        z = fh.top(px, py, 0.03) + 0.004
        g.face([V((px - 0.03, py - 0.03, z)), V((px + 0.03, py - 0.03, z)), V((px + 0.03, py + 0.03, z)),
                V((px - 0.03, py + 0.03, z))], "Wood", (0, 0, 1))
        # the number scratched on them
        fr = Frame(V((px, py, z + 0.0005)), V((1, 0, 0)), V((0, 1, 0)), V((0, 0, 1)))
        text(g, fr, str(num), -0.02, -0.015, 0.025, "Iron", 0.0005, rnd=rnd, jit=0.01)
    # straw and rat tracks near the rat hole corner (ne corner against outer wall)
    for _ in range(14):
        x = -11.0 + rnd.uniform(-0.3, 0.3)
        y = -6.55 + rnd.uniform(-0.35, 0.1)
        a = rnd.uniform(0, math.pi)
        L = rnd.uniform(0.08, 0.18)
        d = V((math.cos(a), math.sin(a), 0))
        z0 = fh.top(x, y, 0.03) + 0.004
        pr = V((-d.y, d.x, 0)) * 0.004
        p = V((x, y, z0))
        g.face([p - d * L / 2 - pr, p + d * L / 2 - pr, p + d * L / 2 + pr, p - d * L / 2 + pr], "Straw", (0, 0, 1))
    # 'DO NOT LOOK AT THE THRONE' is Fetch's at the Kennel; here, 'HOOK OR PIT' incised in the floor by the kneeling spot
    floor_blot(g, fh, -8.0, -8.1, 0.3, 0.08, 10, "Iron", rnd, 2, 0.15, lift=0.003)


@decorates("C01_Partition")
def c01_partition(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-partition")
    # south face (inside C01): Wren's height scale, 5 to 7 feet in hands
    yp = YP[1]
    fr = south_face_fr(yp - PT)
    # the scale: a vertical reference line with notches at every hand (10 cm)
    stroke(g, fr, [(-6.4, FL + 1.5), (-6.4, FL + 2.15)], 0.006, "Iron", EPS)
    for i in range(8):
        z = FL + 1.52 + i * 0.085
        stroke(g, fr, [(-6.4 - 0.03, z), (-6.4 + 0.08 if i % 5 == 0 else -6.4 + 0.045, z)], 0.006, "Iron", EPS)
    text(g, fr, "15", -6.3, FL + 1.52, 0.03, "Iron", EPS, rnd=rnd, jit=0.005)
    text(g, fr, "17", -6.3, FL + 1.52 + 5 * 0.085, 0.03, "Iron", EPS, rnd=rnd, jit=0.005)
    text(g, fr, "20", -6.3, FL + 1.52 + 7 * 0.085, 0.03, "Iron", EPS, rnd=rnd, jit=0.005)
    text(g, fr, "HANDS", -6.75, FL + 2.22, 0.05, "Iron", EPS, rnd=rnd, jit=0.01)
    # NORTH face of this partition = south wall of C02 (the Rack): I TOLD THE TRUTH / THE FIFTH TIME
    frN = north_face_fr(yp + PT)
    text(g, frN, "I TOLD THE TRUTH", -10.3, FL + 1.4, 0.07, "Iron", EPS, rnd=rnd, jit=0.02)
    text(g, frN, "THE FIFTH TIME", -10.2, FL + 1.25, 0.055, "Iron", EPS, rnd=rnd, jit=0.025, slant=0.05)


@decorates("C01_Arch")
def c01_arch(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-arch")
    yc = ycen(1)
    fr = yard_fr()
    # Room board on the yard face of the arch head, above the hood mould
    # The piece's +x face is at x = -3.38 - 0.49 = -3.87? no: C01_Arch center -3.38, size 0.98, so faces x = -3.87..-2.89
    # The yard face is +x (toward the yard). Use lift so the board sits on the piece.
    # REGISTRY chiselled (hacked out blot), THE PRESS GANG in tar
    base_u, base_v = yc - 0.5, FL + 5.9
    # chiselled scar (where REGISTRY was)
    blot(g, fr, yc, base_v + 0.08, 0.5, 0.08, 14, "Iron", 0.015, rnd, 0.3)
    # new tarred lettering
    text(g, fr, "THE PRESS GANG", base_u - 0.1, base_v - 0.14, 0.09, "Iron", 0.02, rnd=rnd, jit=0.015)


@decorates("C01_Desk")
def c01_desk(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-desk")
    yc = ycen(1)
    cx, cy = -7.6, yc + 0.6
    # sand shaker (horn), stick of red sealing wax, horn cup of quills, wire spectacles
    g.cyl(V((cx + 0.22, cy + 0.3, FL + 1.14)), V((cx + 0.22, cy + 0.3, FL + 1.22)), 0.03, 8, "Bone")
    g.cyl(V((cx + 0.22, cy + 0.3, FL + 1.22)), V((cx + 0.22, cy + 0.3, FL + 1.24)), 0.028, 6, "Iron", r1=0.023)
    # stick of sealing wax (red = Iron reads dark; use Bone for warmth)
    g.cyl(V((cx + 0.14, cy + 0.32, FL + 1.13)), V((cx + 0.11, cy + 0.3, FL + 1.14)), 0.008, 4, "Iron")
    # wire spectacles: two little rings and a bridge
    spz = FL + 1.13
    for sx in (-1, 1):
        c = V((cx - 0.25 + sx * 0.03, cy + 0.33, spz))
        g.link(c, V((0, 1, 0)), V((0, 0, 1)), 0.025, 0.025, 0.002, 10, 3, "Iron")
    g.cyl(V((cx - 0.24, cy + 0.33, spz)), V((cx - 0.28, cy + 0.33, spz)), 0.0015, 3, "Iron")
    # one lens starred: three tiny strokes
    for a in (0, 2.1, 4.2):
        p = V((cx - 0.22, cy + 0.33, spz))
        d = V((math.cos(a) * 0.015, math.sin(a) * 0.015, 0))
        g.cyl(p, p + d, 0.0008, 3, "Iron")
    # horn cup of quills
    g.cyl(V((cx + 0.42, cy + 0.33, FL + 1.14)), V((cx + 0.42, cy + 0.33, FL + 1.3)), 0.028, 8, "Bone", r1=0.034)
    for i in range(5):
        a = rnd.uniform(0, 6.28)
        tip = V((cx + 0.42 + math.cos(a) * 0.02, cy + 0.33 + math.sin(a) * 0.02, FL + 1.44 + rnd.uniform(-0.03, 0.03)))
        base = V((cx + 0.42, cy + 0.33, FL + 1.28))
        g.sweep([base, tip], 0.003, 3, "Bone", caps=False)
    # low shelf between the desk legs (piece y range -8.988..-7.609 forbids poking out)
    sx0, sx1 = cx - 0.55, cx + 0.55
    sy0, sy1 = cy - 0.2, cy + 0.1             # between front/back legs
    bx(g, sx0, sx1, sy0, sy1, FL + 0.42, FL + 0.46, "Wood", 0.005)
    # three stacked ledgers (Book I, Book II, the Crown register)
    bz = FL + 0.46
    for i, dh in enumerate((0.05, 0.055, 0.06)):
        bx(g, sx0 + 0.08 + i * 0.33, sx0 + 0.08 + i * 0.33 + 0.3, sy0 + 0.02, sy0 + 0.02 + 0.26, bz, bz + dh,
           "Cloth", 0.004)


@decorates("C01_Branding_Brazier")
def c01_brazier(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-brazier")
    bz = V((-9.618, -10.336, 0.985))
    # Quench bucket (brine) to the west, outside the three brazier legs
    bc = V((bz.x - 0.65, bz.y + 0.35, FL))
    vessel(g, bc, 0.13, 0.14, 0.28, 10, "Wood", fill="Water", fill_h=0.75, wall=0.012)
    # iron bail across it
    g.cyl(bc + V((-0.14, 0, 0.26)), bc + V((0.14, 0, 0.26)), 0.006, 4, "Iron")
    # scorched leather apron draped over the south leg
    ap = V((bz.x - 0.08, bz.y - 0.44, FL + 0.9))
    bx(g, ap.x - 0.17, ap.x + 0.18, ap.y - 0.02, ap.y + 0.02, ap.z - 0.5, ap.z, "Cloth", 0.01)
    # tiny hook marks burnt into it
    fr = Frame(ap + V((0, -0.03, -0.25)), V((1, 0, 0)), V((0, 0, 1)), V((0, -1, 0)))
    for i in range(5):
        u = -0.14 + i * 0.07
        stroke(g, fr, [(u, 0.1), (u, 0.0), (u + 0.03, -0.015), (u + 0.045, 0.0)], 0.005, "Iron", 0.001)


@decorates("C01_Props")
def c01_props(g, lod):
    if lod > 0:
        return
    rnd = rng("c01-props")
    yc = ycen(1)
    # Confiscated sack by the outer wall, between the chest and the clothes pile
    # The piece centre is (-11.2, -8.72, 1.65); size 0.845 x 4.41 x 2.5. x range: -11.6..-10.77
    sc = V((-11.2, -9.35, FL))
    g.blob(sc + V((0, 0, 0.18)), 0.19, 0.17, 0.18, 10, 3, "Cloth", rnd, 0.2, flat_bottom=False)
    # drawstring tie
    g.cyl(sc + V((0, 0, 0.33)), sc + V((0.03, 0.02, 0.4)), 0.006, 3, "Straw")
    # wooden chit tied to it with a scribbled number
    chit_c = sc + V((0.1, 0.02, 0.3))
    bx(g, chit_c.x - 0.03, chit_c.x + 0.03, chit_c.y - 0.005, chit_c.y + 0.005, chit_c.z - 0.025, chit_c.z + 0.025,
       "Wood")
    # Candle stub pushed into the top of the recruits' chest (chest spans about y = yc-2.2..yc-1.0, top at FL+0.6)
    candle(g, V((-11.0, yc - 2.0, FL + 0.6)), 0.045, 0.012, rnd, runs=2, puddle=1.6)
    # Chamber pot in the north corner (plausible; against outer wall, north end, outside the walkway)
    pot = V((-11.1, yc + 1.9, FL))
    vessel(g, pot, 0.11, 0.13, 0.2, 10, "Wood", wall=0.012)
    g.cyl(pot + V((0, 0, 0.18)), pot + V((0, 0, 0.2)), 0.014, 3, "Iron", r1=0.004)   # the iron wire mend


# ================================================================== C02 The Rack
@decorates("C02_Vault")
def c02_vault(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-vault")
    yc = ycen(2)
    light_well(g, yc, rnd)
    # White painted eye on the intrados above the wheel end of the rack (east of the light well)
    xo = CXV + 1.0
    # a flat oval with a dark pupil
    vault_blot(g, yc, xo, 0.0, 0.2, 0.14, 14, "Bone", rnd, 0.1, 0.004)
    vault_blot(g, yc, xo, 0.0, 0.07, 0.05, 10, "Iron", rnd, 0.1, 0.006)
    # Strappado ring and pulley bolted to the west transverse rib, near the crown
    xp = CXV - 1.3
    p0 = vpt(yc, xp, 0.0, RI - 0.02)
    g.cyl(p0, p0 - V((0, 0, 0.14)), 0.025, 6, "Iron")
    # pulley block
    pz = p0.z - 0.14
    g.cyl(V((xp, yc - 0.04, pz)), V((xp, yc + 0.04, pz)), 0.05, 8, "Iron")
    g.link(V((xp, yc, pz - 0.05)), V((0, 0, 1)), V((1, 0, 0)), 0.045, 0.045, 0.008, 10, 3, "Iron")
    # frayed rope-end hanging in the pulley
    rope_a = V((xp, yc + 0.02, pz - 0.04))
    rope_b = V((xp + 0.03, yc - 0.1, pz - 0.6))
    g.sweep([rope_a, rope_a + V((0, -0.03, -0.2)), rope_b], 0.009, 3, "Straw", caps=False)


@decorates("C02_Wall")
def c02_wall(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-wall")
    yc = ycen(2)
    fr = wall_fr()
    # 1. THE SEA GIVES BACK WHAT THE ROPE TAKES. A.R.
    # Keep inside y range yc-1.45..yc-0.4 (south of the arrow slit at ~sz 1.9-3.6; arrow slit at z 2.3..4.0)
    # Need two lines, roughly 1.0 m wide total. hip height ~ FL + 0.85 = 1.25
    text(g, fr, "THE SEA GIVES BACK", yc - 1.4, FL + 1.0, 0.07, "Iron", 0.004, rnd=rnd, jit=0.012)
    text(g, fr, "WHAT THE ROPE TAKES", yc - 1.4, FL + 0.86, 0.065, "Iron", 0.004, rnd=rnd, jit=0.012)
    text(g, fr, "A.R.", yc - 0.75, FL + 0.72, 0.055, "Iron", 0.004, rnd=rnd, jit=0.008, slant=0.1)
    # 2. Rat hole in the mortar — a dark oval blot
    for i in range(2):
        blot(g, fr, yc + 0.75, FL + 0.09 + i * 0.015, 0.07, 0.045, 10, "Iron", 0.004 + i * 0.004, rnd, 0.25)
    # gnawed scrape rays round the hole
    for a in (0.3, 1.0, -0.5, 2.3):
        d = V((math.cos(a) * 0.09, math.sin(a) * 0.06))
        stroke(g, fr, [(yc + 0.75, FL + 0.09), (yc + 0.75 + d.x, FL + 0.09 + d.y)], 0.004, "Iron", 0.002)
    # 3. 'HASK'S HOLE' scratched above it (small, snide)
    text(g, fr, "HASKS", yc + 0.63, FL + 0.22, 0.04, "Iron", 0.003, rnd=rnd, jit=0.01)
    # 4. a few vertical rope-wear grooves high on the wall above the rack
    for y in (yc + 0.1, yc + 0.3, yc - 0.1):
        stroke(g, fr, [(y, FL + 2.6), (y + rnd.uniform(-0.02, 0.02), FL + 1.9)], 0.008, "Iron", 0.003)


@decorates("C02_Floor")
def c02_floor(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-floor")
    fh = floor_h(2)
    yc = ycen(2)
    # Long dark stain under the rack frame (rack centre -7.315, -2.795, extent 3.075 x 1.2)
    floor_blot(g, fh, -7.3, -2.8, 1.0, 0.35, 18, "Floor", rnd, rings=3, jit=0.2, lift=0.003)
    # a darker core as the body outline
    floor_blot(g, fh, -7.3, -2.8, 0.4, 0.15, 12, "Iron", rnd, rings=2, jit=0.2, lift=0.004)
    # Gnawed knuckle bones laid out at the rat hole (y ≈ yc+0.75 = -2.125, against outer wall)
    for i in range(5):
        x = -11.33 + i * 0.055 + rnd.uniform(-0.015, 0.015)
        y = yc + 0.72 + rnd.uniform(-0.04, 0.04)
        z = fh.top(x, y, 0.02) + 0.005
        g.blob(V((x, y, z + 0.006)), 0.013, 0.008, 0.008, 6, 1, "Bone", rnd, 0.15)
    # chalk dust 'TRUTH' blown round the rack head
    floor_blot(g, fh, -8.9, -2.8, 0.08, 0.14, 10, "Bone", rnd, 1, 0.2, lift=0.002)


@decorates("C02_Partition")
def c02_partition(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-partition")
    # NORTH face of this partition = south wall of C03 (the Stocks). Bent nail in a mortar joint
    yp = YP[2]
    frN = north_face_fr(yp + PT)
    # tiny bent nail: a flat zig lifted a hair
    stroke(g, frN, [(-5.4 - 0.03, FL + 0.22), (-5.4 + 0.015, FL + 0.215), (-5.4 + 0.03, FL + 0.235)], 0.004,
           "Iron", EPS * 2)


@decorates("C02_Arch")
def c02_arch(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-arch")
    yc = ycen(2)
    fr = yard_fr()
    # QUESTION ROOM hacked out, THE RACK in tar
    blot(g, fr, yc - 0.1, FL + 5.98, 0.45, 0.08, 14, "Iron", 0.015, rnd, 0.3)
    text(g, fr, "THE RACK", yc - 0.3, FL + 5.76, 0.11, "Iron", 0.02, rnd=rnd, jit=0.015)


@decorates("C02_Rack")
def c02_rack(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-rack")
    yc = ycen(2)
    # Five notches by the wheel on the north rail (rack center x -7.315, L=3.075 so wheel end at ~ -5.78)
    rail_y = yc + 0.4           # north rail outer face at yc + Wd/2
    xn0 = -6.7
    fr = Frame((0, rail_y + 0.08, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0))
    for i in range(5):
        x = xn0 + i * 0.07
        stroke(g, fr, [(x, FL + 1.13), (x + (0.02 if i == 4 else 0), FL + 1.22)],
               0.005 if i < 4 else 0.008, "Iron", 0.002)
    text(g, fr, "AR", xn0 + 0.3, FL + 1.11, 0.03, "Iron", 0.002, rnd=rnd, jit=0.01)
    # Wooden bite stick on a thong, hanging from the south end of the head roller
    br = V((-8.75, yc - 0.5, FL + 1.0))
    g.cyl(br, br + V((0, 0, -0.12)), 0.007, 3, "Cloth")
    g.blob(br + V((0, 0, -0.14)), 0.025, 0.015, 0.015, 6, 1, "Wood", rnd, 0.1)


@decorates("C02_Props")
def c02_props(g, lod):
    if lod > 0:
        return
    rnd = rng("c02-props")
    yc = ycen(2)
    wy = YP[2] - PT      # the north partition face (south face), ~ -0.3
    # Reed's knot board: a plank pegged above the tool rack, 0.8 x 0.6
    bx(g, -10.3, -9.5, wy - 0.055, wy - 0.005, FL + 1.5, FL + 2.1, "Wood", 0.01)
    # knots on it (little stubs tied in rope)
    for i, (u, v, k) in enumerate((( -10.2, 1.95, "reef"), (-10.0, 1.95, "bowline"), (-10.2, 1.75, "sheep"),
                                    (-10.0, 1.75, "noose"))):
        g.blob(V((u, wy - 0.06, FL + v)), 0.05, 0.02, 0.025, 6, 1, "Straw", rnd, 0.3)
    # Loose stone with Reed's prayer book behind it (foot of north wall, east of the skeleton)
    sx, sy = -10.4, wy - 0.02
    bx(g, sx - 0.1, sx + 0.1, sy - 0.005, sy + 0.02, FL + 0.4, FL + 0.62, "Stone", 0.01)
    # the book corner peeking out between stone and wall
    bx(g, sx + 0.11, sx + 0.14, sy - 0.025, sy - 0.005, FL + 0.46, FL + 0.56, "Cloth", 0.004)
    # Wooden chamber pot in the nw corner (y ≈ -1.3)
    pot = V((-10.95, -1.3, FL))
    vessel(g, pot, 0.1, 0.11, 0.19, 10, "Wood", wall=0.012)
    g.cyl(pot + V((-0.11, 0, 0.12)), pot + V((-0.11, 0, 0.17)), 0.004, 3, "Iron")   # wire mend
    # Rust shadow of the missing hook on the tool rack (west end)
    tool_rack_y = wy - 0.02         # tool rack sits at wy-0.06..wy
    fr = south_face_fr(tool_rack_y)  # looking south from the rack face
    # a rust blot in the shape of a hook, west end
    stroke(g, fr, [(-7.32, FL + 1.75), (-7.32, FL + 2.0), (-7.37, FL + 2.05), (-7.4, FL + 2.0),
                   (-7.4, FL + 1.95)], 0.014, "Iron", 0.004)
    # Dented tin dipper hung on the bucket rim (bucket at X(10.9), wy - 0.4, FL)
    bk = V((-10.9, wy - 0.4, FL))
    dip = bk + V((0.18, 0, 0.34))
    g.cyl(dip, dip + V((0.08, 0, -0.02)), 0.025, 6, "Iron", r1=0.035)
    g.cyl(dip + V((0.08, 0, -0.02)), dip + V((0.14, 0, 0.08)), 0.004, 3, "Iron")   # handle
    # Candle stub on the tool rack
    candle(g, V((-9.3, wy - 0.04, FL + 1.3 + 0.03)), 0.04, 0.011, rnd, puddle=1.5)


# ================================================================== C03 The Stocks
@decorates("C03_Vault")
def c03_vault(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-vault")
    yc = ycen(3)
    light_well(g, yc, rnd)
    # Bell-rope hole with cut rope end (near outer wall, west)
    xh = CXV - 2.3
    # a small iron ring set in the vault at a hole mouth
    p0 = vpt(yc, xh, 0.0, RI - 0.005)
    g.cyl(p0 + V((0, 0, 0.03)), p0 - V((0, 0, 0.02)), 0.025, 8, "Iron", caps=(False, False))
    # frayed rope hanging down
    rope_pts = [p0 - V((0, 0, 0.02)), V((xh, yc + 0.03, VS + 2.0)), V((xh + 0.01, yc, VS + 1.4))]
    g.sweep(rope_pts, 0.012, 3, "Straw", caps=False)
    # Painted stars flaking off (between transverse ribs), 7 small lime-white blots
    stars = [(0.3, -0.3), (-0.5, 0.4), (0.8, 0.6), (-0.2, -0.8), (0.6, -0.1), (-0.9, 0.0), (0.1, 0.9)]
    for dx, ds in stars:
        vault_blot(g, yc, CXV + dx, ds, 0.045, 0.045, 5, "Bone", rnd, 0.3, 0.003)


@decorates("C03_Wall")
def c03_wall(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-wall")
    yc = ycen(3)
    fr = wall_fr()
    # Fresco of Saint Clement under the soot, eyes scratched out
    # A lime-plaster patch (Bone) 1 cm proud, with soot (Iron) over the face, and two scratched eyes
    # Patch roughly 1.0 x 1.2, chest-to-head height; piece y range yc-1.4..yc+1.4, z FL..WT+..
    cy_, cz = yc + 1.0, FL + 1.9
    # the plaster rectangle
    rect(g, fr, cy_ - 0.5, cy_ + 0.5, cz - 0.6, cz + 0.6, "Bone", 0.01)
    # a halo circle
    halo = []
    for a in range(16):
        t = 2 * math.pi * a / 16
        halo.append((cy_ + math.cos(t) * 0.18, cz + 0.42 + math.sin(t) * 0.18))
    stroke(g, fr, halo + [halo[0]], 0.012, "Bone", 0.011)
    # the face (soot)
    blot(g, fr, cy_, cz + 0.42, 0.14, 0.17, 12, "Iron", 0.013, rnd, 0.1)
    # eyes scratched (small lime-coloured scratches crossing)
    for sx in (-1, 1):
        stroke(g, fr, [(cy_ + sx * 0.05 - 0.02, cz + 0.45), (cy_ + sx * 0.05 + 0.02, cz + 0.42)], 0.004,
               "Bone", 0.014)
        stroke(g, fr, [(cy_ + sx * 0.05 - 0.02, cz + 0.42), (cy_ + sx * 0.05 + 0.02, cz + 0.45)], 0.004,
               "Bone", 0.014)
    # body (dark robe shape)
    blot(g, fr, cy_, cz - 0.2, 0.18, 0.3, 10, "Iron", 0.012, rnd, 0.1)
    # the anchor at Clement's feet (he was drowned bound to one)
    stroke(g, fr, [(cy_, cz - 0.5), (cy_, cz - 0.1)], 0.01, "Iron", 0.012)
    stroke(g, fr, [(cy_ - 0.08, cz - 0.47), (cy_ + 0.08, cz - 0.47)], 0.01, "Iron", 0.012)
    stroke(g, fr, [(cy_ - 0.12, cz - 0.52), (cy_ - 0.08, cz - 0.55), (cy_ - 0.04, cz - 0.52)], 0.008, "Iron", 0.012)
    stroke(g, fr, [(cy_ + 0.04, cz - 0.52), (cy_ + 0.08, cz - 0.55), (cy_ + 0.12, cz - 0.52)], 0.008, "Iron", 0.012)
    # Sliver of mirror wedged in a crack (near the foot stocks: yc+1.5 area, knee height)
    stroke(g, fr, [(yc + 1.75, FL + 0.95), (yc + 1.82, FL + 1.05)], 0.012, "Iron", 0.006)
    # Four of Bones under the stocks bench is in C03_Stocks; here a few egg-shell smears from the Mock
    for _ in range(3):
        y = yc + rnd.uniform(-0.5, 1.2)
        z = FL + rnd.uniform(1.4, 2.2)
        blot(g, fr, y, z, rnd.uniform(0.04, 0.07), rnd.uniform(0.03, 0.06), 7, "Bone", 0.003, rnd, 0.4)


@decorates("C03_Floor")
def c03_floor(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-floor")
    fh = floor_h(3)
    yc = ycen(3)
    # Wax runs from the candle in the stoup (-9.8, 5.5): a trail of grey wax down into the room
    for i in range(4):
        x = -9.8 + rnd.uniform(-0.08, 0.08)
        y = YP[2] + PT + 0.05 + i * 0.08 + rnd.uniform(-0.03, 0.03)
        floor_blot(g, fh, x, y, 0.03, 0.025, 6, "Bone", rnd, 1, 0.3, lift=0.002)
    # Rotten crusts and shells trodden in by the pillory
    for _ in range(6):
        x, y = -7.4 + rnd.uniform(-0.9, 0.9), yc + 1.0 + rnd.uniform(-0.2, 0.4)
        floor_blot(g, fh, x, y, rnd.uniform(0.04, 0.08), rnd.uniform(0.03, 0.06), 7, "Bone", rnd, 1, 0.3, lift=0.003)
    # Soot drip under the fresco torch
    for i in range(3):
        y = 3.1 + 1.45 + rnd.uniform(-0.05, 0.05)
        floor_blot(g, fh, -11.1, y, 0.08, 0.05, 8, "Iron", rnd, 1, 0.3, lift=0.002)


@decorates("C03_Partition")
def c03_partition(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-partition")
    yp = YP[3]
    # SOUTH face (inside C03): Tam Wicken's first verse, incised
    fr = south_face_fr(yp - PT)
    verse = ["OH THE TOOTH BITES DEEP", "AND THE TOOTH BITES SLOW"]
    base_u, base_v = -6.9, FL + 1.6
    text(g, fr, verse[0], base_u, base_v, 0.075, "Iron", EPS, rnd=rnd, jit=0.015)
    text(g, fr, verse[1], base_u, base_v - 0.14, 0.075, "Iron", EPS, rnd=rnd, jit=0.015)
    # Old holy-water niche with a candle stub: recess into the partition face
    cut_pocket(g, 1, yp - PT, -1, -9.95, -9.65, FL + 1.4, FL + 1.7, 0.1, "Stone", "Stone")
    # candle on the floor of the niche (inside the partition volume, inset 3 cm)
    candle(g, V((-9.8, yp - PT + 0.03, FL + 1.4 + 0.02)), 0.04, 0.011, rnd, puddle=1.2)
    # wax runs down the niche front
    for i in range(3):
        u = -9.9 + i * 0.1
        stroke(g, fr, [(u, FL + 1.4), (u + rnd.uniform(-0.01, 0.01), FL + 1.3), (u, FL + 1.15)], 0.012, "Bone", EPS * 2)
    # NORTH face (inside C04): Ducking record list, incised
    frN = north_face_fr(yp + PT)
    recs = ["JORY 300", "HAL 140", "NED 90", "KIT 61  CHEATED"]
    for i, s in enumerate(recs):
        text(g, frN, s, -8.5, FL + 2.0 - i * 0.14, 0.07, "Iron", EPS, rnd=rnd, jit=0.015)


@decorates("C03_Arch")
def c03_arch(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-arch")
    yc = ycen(3)
    fr = yard_fr()
    # CHAPEL OF chiselled away, CLEMENT left, THE STOCKS in tar below
    blot(g, fr, yc - 0.3, FL + 6.0, 0.25, 0.08, 12, "Iron", 0.015, rnd, 0.3)
    text(g, fr, "CLEMENT", yc + 0.0, FL + 5.95, 0.09, "Bone", 0.012, rnd=rnd, jit=0.01)   # original Crown lettering
    text(g, fr, "THE STOCKS", yc - 0.25, FL + 5.76, 0.1, "Iron", 0.02, rnd=rnd, jit=0.015)


@decorates("C03_Pillory")
def c03_pillory(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-pillory")
    yc = ycen(3)
    # Initials crowding the yoke's top edge (centre -7.4, yoke top at FL+0.335+1.37)
    base = FL + 0.335
    top_z = base + 1.46
    fr = Frame((0, 0, top_z), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    inits = ["TW", "MK", "OH", "JP", "RC", "WB", "AR", "HS", "GV", "KF", "NM", "ES"]
    for i, s in enumerate(inits):
        u = -7.95 + i * 0.095 + rnd.uniform(-0.015, 0.015)
        text(g, fr, s, u, yc + 0.28 + rnd.uniform(-0.01, 0.01), 0.025, "Iron", 0.001, rnd=rnd, jit=0.004,
             adv=0.6)
    # Crust and egg-shell stains on the platform (face side = +y of pillory; platform z=FL+0.32..FL+0.335)
    pfr = Frame((0, 0, FL + 0.336), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    for _ in range(6):
        x, y = -7.4 + rnd.uniform(-0.4, 0.4), yc + 0.9 + rnd.uniform(-0.1, 0.1)
        blot(g, pfr, x, y, rnd.uniform(0.03, 0.06), rnd.uniform(0.03, 0.06), 7, "Bone", 0.001, rnd, 0.3)
    # Altar stone showing through a broken board on the east side of the platform
    efr = Frame((-6.306, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    # anchor incised (y stays inside piece max yc+1.4 = 4.275 and piece ymax 3.975)
    stroke(g, efr, [(yc + 0.95, FL + 0.52), (yc + 0.95, FL + 0.72)], 0.006, "Iron", 0.002)
    stroke(g, efr, [(yc + 0.88, FL + 0.55), (yc + 1.02, FL + 0.55)], 0.006, "Iron", 0.002)
    stroke(g, efr, [(yc + 0.85, FL + 0.48), (yc + 0.95, FL + 0.44), (yc + 1.05, FL + 0.48)], 0.005,
           "Iron", 0.002)


@decorates("C03_Stocks")
def c03_stocks(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-stocks")
    yc = ycen(3)
    cx, cy = -9.9, yc + 1.5
    # Four of Bones wedging the bench (under the west leg)
    cz = FL + 0.005
    # the card as a tiny flat bone plate
    g.face([V((cx - 0.83, cy - 0.07, cz)), V((cx - 0.74, cy - 0.07, cz)),
            V((cx - 0.74, cy + 0.07, cz)), V((cx - 0.83, cy + 0.07, cz))], "Bone", (0, 0, 1))
    # four pips as tiny bone blobs
    for px, py in ((-0.81, -0.04), (-0.76, -0.04), (-0.81, 0.04), (-0.76, 0.04)):
        g.blob(V((cx + px, cy + py, cz + 0.0012)), 0.006, 0.006, 0.0015, 5, 1, "Bone", rnd, 0.1)
    # Shanty line knifed into the bench front (south face of the seat; piece z range 0.4..0.86)
    fr = Frame((0, cy - 0.15 - 0.005, FL + 0.38), (1, 0, 0), (0, 0, 1), (0, -1, 0))
    text(g, fr, "I WILL NEVER WALK", cx - 0.8, 0.0, 0.045, "Iron", 0.001, rnd=rnd, jit=0.012)


@decorates("C03_Torch")
def c03_torch(g, lod):
    pass


@decorates("C03_Props")
def c03_props(g, lod):
    if lod > 0:
        return
    rnd = rng("c03-props")
    yc = ycen(3)
    # Scrap of red Crown coat and three marine buttons beside the three skulls (at the wheel)
    # The piece bounds: centre (-10.958, 1.359, 2.007), size 1.285 x 2.461 x 3.174 → x -11.6..-10.3, y 0.13..2.59
    cx, cy = -10.9, 2.3
    bz = FL + 0.03
    # ragged cloth patch
    g.blob(V((cx, cy, bz + 0.015)), 0.11, 0.08, 0.015, 8, 1, "Cloth", rnd, 0.3, flat_bottom=True)
    # three buttons: gilt (Bone)
    for i, (dx, dy) in enumerate(((-0.05, 0.03), (0.0, -0.03), (0.05, 0.02))):
        g.cyl(V((cx + dx, cy + dy, bz + 0.02)), V((cx + dx, cy + dy, bz + 0.025)), 0.008, 8, "Bone")
    # Straw figure of a man with an anchor, wedged behind the wheel against the outer wall
    sf = V((-11.52, 1.68, FL + 2.2))
    g.blob(sf, 0.025, 0.025, 0.05, 6, 1, "Straw", rnd, 0.3)
    g.blob(sf + V((0, 0, 0.065)), 0.02, 0.02, 0.025, 6, 1, "Straw", rnd, 0.3)
    g.cyl(sf + V((-0.03, 0, 0.02)), sf + V((0.03, 0, 0.02)), 0.004, 3, "Straw")   # arms
    # a tiny anchor at its feet, on the outer wall face
    efr = Frame((-11.515, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    stroke(g, efr, [(sf.y, sf.z - 0.08), (sf.y, sf.z - 0.03)], 0.004, "Iron", 0.003)
    stroke(g, efr, [(sf.y - 0.025, sf.z - 0.075), (sf.y + 0.025, sf.z - 0.075)], 0.004, "Iron", 0.003)


# ================================================================== C04 The Cistern
@decorates("C04_Vault")
def c04_vault(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-vault")
    yc = ycen(4)
    light_well(g, yc, rnd)
    # Salt crust streaks on the intrados above the tank (west half)
    for i in range(6):
        x = CXV - 1.3 + rnd.uniform(-0.5, 0.5)
        s = rnd.uniform(-0.9, 0.9)
        vault_blot(g, yc, x, s, rnd.uniform(0.12, 0.22), rnd.uniform(0.1, 0.18), 8, "Bone", rnd, 0.3, 0.004)
    # a long drip streak from each
    for i in range(3):
        x0 = CXV - 1.4 + i * 0.5
        vault_stroke(g, yc, [(x0, -0.8), (x0 + rnd.uniform(-0.02, 0.02), -0.2), (x0, 0.4)], 0.025, "Bone", 0.003)


@decorates("C04_Wall")
def c04_wall(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-wall")
    yc = ycen(4)
    fr = wall_fr()
    # 1. Forty-one strokes (Drave), L.D., I WILL COME BACK FOR THE KEY, with a later hook
    base_u, base_v = yc + 0.5, FL + 1.6
    tally(g, fr, base_u, base_v, 41, 0.08, "Iron", 0.004, rnd, per_row=4, row_gap=0.16)
    text(g, fr, "LD", base_u, base_v - 0.22, 0.07, "Iron", 0.004, rnd=rnd, jit=0.015, slant=0.1)
    text(g, fr, "I WILL COME BACK", base_u - 0.1, base_v + 0.6, 0.065, "Iron", 0.004, rnd=rnd, jit=0.012)
    text(g, fr, "FOR THE KEY", base_u - 0.1, base_v + 0.48, 0.065, "Iron", 0.004, rnd=rnd, jit=0.012)
    # the hook (deeper, surer hand): drawn on a flat frame with a bigger lift
    hk_u, hk_v = base_u + 0.4, base_v - 0.22
    stroke(fr=fr, g=g, pts=[(hk_u, hk_v + 0.14), (hk_u, hk_v + 0.02),
                            (hk_u + 0.06, hk_v - 0.02), (hk_u + 0.1, hk_v + 0.02)],
           w=0.011, mat="Iron", lift=0.007)
    # 2. Groups of ten strokes, 300 ringed, a little seal (Jory). Only the first sixty are deeply cut.
    jby, jbz = yc - 1.4, FL + 1.5
    tally(g, fr, jby, jbz, 60, 0.055, "Iron", 0.003, rnd, group=10, per_row=5, row_gap=0.1,
          gap=0.14)
    text(g, fr, "300", jby + 0.5, jbz - 0.2, 0.07, "Iron", 0.004, rnd=rnd, jit=0.015)
    # ring round the 300
    ring = []
    for a in range(14):
        t = 2 * math.pi * a / 14
        ring.append((jby + 0.6 + math.cos(t) * 0.14, jbz - 0.16 + math.sin(t) * 0.1))
    stroke(g, fr, ring + [ring[0]], 0.005, "Iron", 0.004)
    # little seal (profile): an oval and a dot for eye
    sl = (jby + 0.5, jbz - 0.4)
    blot(g, fr, sl[0], sl[1], 0.05, 0.025, 10, "Iron", 0.004, rnd, 0.2)
    g.cyl(fr.p(sl[0] + 0.03, sl[1] + 0.01, 0.003), fr.p(sl[0] + 0.03, sl[1] + 0.01, 0.006), 0.004, 4, "Bone")
    # 3. High-water line (horizontal groove along the whole inner wall at knee height, Y7 flood)
    stroke(g, fr, [(yc - 1.9, FL + 0.9), (yc + 1.9, FL + 0.9)], 0.008, "Iron", 0.003)
    # salt bloom patches high up
    for _ in range(4):
        y = yc + rnd.uniform(-1.6, 1.6)
        z = FL + rnd.uniform(2.4, 3.4)
        blot(g, fr, y, z, rnd.uniform(0.1, 0.18), rnd.uniform(0.08, 0.14), 8, "Bone", 0.003, rnd, 0.3)


@decorates("C04_Floor")
def c04_floor(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-floor")
    fh = floor_h(4)
    yc = ycen(4)
    # Empty bowl one hand beyond reach of the skeleton (east side of the room, out of door path)
    bz0 = fh.low(-5.2, 6.9, 0.1) + 0.001
    bw = V((-5.2, 6.9, bz0))
    vessel(g, bw, 0.07, 0.085, 0.019, 10, "Wood", wall=0.008)
    # Salt rime crust along the tank's east face (tank at x -11.5..-8.2, east face at -8.2)
    for i in range(5):
        x = -8.0 + rnd.uniform(-0.1, 0.1)
        y = yc - 1.2 + i * 0.6
        floor_blot(g, fh, x, y, rnd.uniform(0.12, 0.18), rnd.uniform(0.08, 0.13), 10, "Bone", rnd, 2, 0.3, lift=0.003)
    # Crab shells and fish bones in the nw corner (y 10.6, x -11.0)
    for i in range(7):
        x = -11.0 + rnd.uniform(-0.2, 0.2)
        y = 10.4 + rnd.uniform(-0.15, 0.3)
        if y > yspan(4)[1] - 0.05:
            y = yspan(4)[1] - 0.1
        z = fh.top(x, y, 0.03) + 0.004
        g.blob(V((x, y, z + 0.008)), 0.025, 0.018, 0.01, 6, 1, "Bone", rnd, 0.3)
    # wet footprints leading from the tank out the door (east -> door at x=-3.45, y=8.6)
    for i in range(5):
        t = i / 4
        bx_, by = -8.0 + t * 2.6, 8.0 + t * 0.5
        floor_blot(g, fh, bx_, by, 0.07, 0.1, 6, "Iron", rnd, 1, 0.3, lift=0.002)


@decorates("C04_Partition")
def c04_partition(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-partition")
    yp = YP[4]
    # SOUTH face (inside C04): the Mute's tide slate and high-water lines
    fr = south_face_fr(yp - PT)
    # Tide slate in a wooden frame, 0.9 x 0.6 at x -9.5, z FL+1.5..2.3
    # wooden frame
    rect(g, fr, -9.95, -9.05, FL + 1.5, FL + 2.1, "Wood", 0.03)
    rect(g, fr, -9.9, -9.1, FL + 1.55, FL + 2.05, "Stone", 0.02)   # dark slate
    # chalk tide marks on it
    for i in range(8):
        z = FL + 1.58 + i * 0.06
        stroke(g, fr, [(-9.85, z), (-9.6 + rnd.uniform(-0.05, 0.05), z)], 0.004, "Bone", 0.022)
    # Dead Ebb circled twice
    for r in (0.03, 0.038):
        ring = []
        for a in range(14):
            t = 2 * math.pi * a / 14
            ring.append((-9.3 + math.cos(t) * r, FL + 1.72 + math.sin(t) * r))
        stroke(g, fr, ring + [ring[0]], 0.004, "Bone", 0.022)
    # High-water lines with year letters (south face, near the front)
    for i, (lbl, z) in enumerate((("Y1 EBB", FL + 0.72), ("Y3", FL + 1.1), ("Y5", FL + 1.25), ("FLOOD Y7", FL + 1.5))):
        stroke(g, fr, [(-7.4, z), (-6.6, z)], 0.006, "Iron", EPS)
        text(g, fr, lbl, -6.55, z - 0.02, 0.045, "Iron", EPS, rnd=rnd, jit=0.01)


@decorates("C04_Arch")
def c04_arch(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-arch")
    yc = ycen(4)
    fr = yard_fr()
    # CISTERN (the Crown's word, kept) - no overpaint
    text(g, fr, "CISTERN", yc - 0.3, FL + 5.8, 0.1, "Iron", 0.012, rnd=rnd, jit=0.008)


@decorates("C04_Cistern")
def c04_cistern(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-cistern")
    yc = ycen(4)
    # Culvert grate under the water, bars bent outward, on the inner face of the west wall of the tank
    # Tank x range in piece: tx0=-11.5..-8.2 (centered at -9.072). West inner face at x = -11.5+0.28 = -11.22
    xw = -11.22
    frm = Frame((xw, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    # grate frame
    for z in (0.12, 0.48):
        bx(g, xw, xw + 0.04, yc - 0.25, yc + 0.25, FL + z, FL + z + 0.03, "Iron", skip=("-x", "+x"))
    for y in (yc - 0.25, yc + 0.25):
        bx(g, xw, xw + 0.04, y, y + 0.03, FL + 0.12, FL + 0.51, "Iron", skip=("-y", "+y"))
    # five vertical bars, the middle two bent outward (toward +x into the tank)
    for i, k in enumerate((-2, -1, 0, 1, 2)):
        y = yc + k * 0.09
        if k in (-1, 0):   # bent bars: midpoint pushed inward
            a = V((xw + 0.015, y, FL + 0.14))
            m = V((xw + 0.08, y + 0.01, FL + 0.3))
            b = V((xw + 0.015, y, FL + 0.49))
            g.sweep([a, m, b], 0.01, 4, "Iron", caps=False)
        else:
            g.cyl(V((xw + 0.015, y, FL + 0.14)), V((xw + 0.015, y, FL + 0.49)), 0.009, 4, "Iron")
    # a strand of weed caught on the lower bar
    g.cyl(V((xw + 0.05, yc - 0.15, FL + 0.14)), V((xw + 0.09, yc - 0.3, FL + 0.08)), 0.004, 3, "Straw")


@decorates("C04_Water")
def c04_water(g, lod):
    pass


@decorates("C04_Chair")
def c04_chair(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-chair")
    yc = ycen(4)
    # Knotted counting cord tied to the counterweight end
    piv_x = -7.3
    cz = FL + 1.75
    a0 = V((piv_x + 1.6, yc, cz - 0.1))     # top of counterweight arm (s=-1 so west side is + from piv)
    pts = [a0, a0 + V((0.01, 0, -0.12)), a0 + V((-0.01, 0, -0.24)), a0 + V((0.01, 0, -0.36))]
    g.sweep(pts, 0.004, 3, "Straw", caps=False)
    for p in pts[1:]:
        g.blob(p, 0.014, 0.014, 0.012, 5, 1, "Straw", rnd, 0.2)
    # Names and counts cut into the chair back's inner face (chair end at s * 2.6 = -2.6 from piv; piv_x=-7.3)
    bx_, bz = -10.146, FL + 1.65    # chair back inner face (piece z range 1.6..2.5)
    fr = Frame((bx_, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0))
    text(g, fr, "J.P. 300", yc - 0.2, bz + 0.3, 0.04, "Iron", 0.003, rnd=rnd, jit=0.012)
    text(g, fr, "H.S. 140", yc - 0.2, bz + 0.23, 0.04, "Iron", 0.003, rnd=rnd, jit=0.012)
    text(g, fr, "N.P. 90", yc - 0.2, bz + 0.16, 0.04, "Iron", 0.003, rnd=rnd, jit=0.012)
    text(g, fr, "BEAT IT", yc - 0.18, bz + 0.06, 0.05, "Iron", 0.003, rnd=rnd, jit=0.02, slant=0.08)


@decorates("C04_Torch")
def c04_torch(g, lod):
    pass


@decorates("C04_Props")
def c04_props(g, lod):
    if lod > 0:
        return
    rnd = rng("c04-props")
    # the skeleton of Jory sits here (built in cistern props). Add a slate on his knees and a pearl in his hand
    # Piece centre -5.37, 6.578, 0.94; size 2.08 x 1.116 x 1.04 so x -6.41..-4.33, y 6.02..7.136
    # Slate at x -5.8, y 6.55, z 0.6: leaning against the right shin
    fr = Frame((-5.8, 0, 0), (0, 1, 0), (0, 0, 1), (-1, 0, 0))
    rect(g, fr, 6.5, 6.6, 0.55, 0.68, "Stone", 0.005)
    text(g, fr, "300", 6.52, 0.62, 0.03, "Bone", 0.006, rnd=rnd, jit=0.008)
    text(g, fr, "KEY", 6.52, 0.58, 0.025, "Bone", 0.006, rnd=rnd, jit=0.008)
    text(g, fr, "JP", 6.52, 0.555, 0.025, "Bone", 0.006, rnd=rnd, jit=0.008)
    # Single grey pearl inside the curled bones of the left hand
    g.blob(V((-6.22, 6.52, 0.6)), 0.0075, 0.0075, 0.0075, 6, 2, "Bone", rnd, 0.1, flat_bottom=False)

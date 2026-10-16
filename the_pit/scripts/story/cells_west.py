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
EPS = 0.0005            # "incised": a hair proud of a face that has no slack
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
    """Face of a partition looking north (+y), read from the north: u = -x."""
    return Frame((0, y, 0), (-1, 0, 0), (0, 0, 1), (0, 1, 0))


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

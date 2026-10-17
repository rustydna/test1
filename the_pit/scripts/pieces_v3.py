"""THE PIT V3 — the dungeon of the Press-Gang.

Prison fortress of a pirate lord: captives are broken here and crew are recruited. A pit-yard
with a seawater channel (with a tide) under the fog, seven punishment rooms, a single kennel to
live in and, at the far end, the throne from which the lord sees every grille.

Design rule (the lesson of V2): **no piece has a convex hull that blocks a passage**. Even if
Second Life leaves every mesh as "Convex Hull" and nobody runs any script, every room can be
entered. That is why each front is split into piers, arch heads and leaves; walls, floors and
vaults are separate pieces.

Fixed SL faces on every piece (see geo.FACE_MATS):
  0 Stone · 1 Floor · 2 Wood · 3 Iron · 4 Cloth/leather · 5 Bone · 6 Straw · 7 Flame
"""

import math

from mathutils import Matrix, Vector

import pieces as P
from geo import Frame, Geo, arch_height, pointed_arch, rng
from pieces import (ARCH_RATIO, ARCH_SPAN, ARCH_SPRING, BIG, DOOR_H, DOOR_HW, FL, FT, GRILLE_D, NX, PT, R_VAULT,
                    SMALL, STD, T_VAULT, VS, WT, XB, XI, XO, YP, ZB, _fx, arch_wall, bar, bbox_phys, brazier, bx,
                    chain, chain_path, collar, cross_slit_skin, flagstones, flipx, gate_leaf, hood, lantern, pbox,
                    resample, torch, tower, voussoirs, wall_anchor)

V = Vector
PIECES = P.PIECES
HW = ARCH_SPAN / 2
CROWN = ARCH_SPRING + arch_height(0, ARCH_SPAN, ARCH_RATIO)
DAIS = FL + 0.9

# Random seeds: the text passed to rng(), flagstones(), torch() and lantern() (e.g. rng("leva-atrezzo"),
# rng(f"suelo-{tag}")) is hashed into the random generator, so it is deliberately kept in the original
# Spanish: changing it would change the model.

# Rooms: (side, index) -> (tag, role name)
ROOMS = {(-1, 0): ("C01", "The Press-Gang"), (-1, 1): ("C02", "The Rack"), (-1, 2): ("C03", "The Stocks"),
         (-1, 3): ("C04", "The Cistern"), (1, 0): ("C05", "The Kennel"), (1, 1): ("C06", "The Kennel"),
         (1, 2): ("C07", "The Cages"), (1, 3): ("C08", "The Mast")}


# Seats: name -> (avatar point in the world, yaw in degrees, animation, fallback animation)
SITS = {}


def reg(name, kind, build, phys, lod_map=STD, fire=False, role=""):
    P.register(name, kind, build, phys, lod_map)
    pc = P.PIECES[-1]
    pc.fire = fire          # piece centre at the base of the flame (particles and light come out of there)
    pc.role = role
    return pc


def Q(lod):
    return {0: 1.0, 1: 0.55, 2: 0.3}.get(lod, 0.2)


def n_(x, lod, lo=3):
    return max(lo, int(round(x * Q(lod))))


def proxy(fn):
    """Automatic LOWEST: shell of the HIGH's bounding box (5 faces) in the dominant material."""
    memo = {}

    def build(lod):
        if lod < 3:
            return fn(lod)
        if "g" not in memo:
            memo["g"] = fn(0)
        g0 = memo["g"]
        mn, mx = g0.bounds()
        counts = {}
        for m in g0.mats:
            if m != "Flame":
                counts[m] = counts.get(m, 0) + 1
        mat = max(counts, key=counts.get) if counts else "Stone"
        g = Geo()
        pad = (mx - mn) * 0.15
        g.box(mn + V((pad.x, pad.y, 0)), mx - V((pad.x, pad.y, pad.z)), mat, skip=("-z",))
        if "Flame" in g0.mats:
            lz = [g0.verts[i] for f, m in zip(g0.faces, g0.mats) if m == "Flame" for i in f]
            c = sum(lz, V()) / len(lz)
            g.spike(V((c.x, c.y, min(v.z for v in lz))), max(v.z for v in lz) - min(v.z for v in lz) + 0.05,
                    0.06, "Flame")
        return g
    return build


def xf(sub, loc, rz=0.0, rx=0.0, ry=0.0, scale=1.0):
    m = Matrix.Translation(V(loc)) @ Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ \
        Matrix.Rotation(rx, 4, "X") @ Matrix.Scale(scale, 4)
    return sub.transform(m)


def front_frame(s):
    return Frame((s * NX, 0, 0), (0, 1, 0), (0, 0, 1), (-s, 0, 0))


def cell_center(k):
    return (YP[k] + YP[k + 1]) / 2


# ================================================================== organic details
def garment(g, c, ang, kind, rnd, lod):
    """Discarded men's underwear: breeches (braies), a loincloth or a crumpled shirt."""
    c = V(c)
    rot = Matrix.Rotation(ang, 3, "Z")
    nu, nv = n_(10, lod, 5), (2 if lod == 0 else 1)
    if kind == "breeches":
        for sx in (-1, 1):
            g.blob(c + rot @ V((sx * 0.1, -0.08, 0)), 0.09, 0.2, 0.03, nu, nv, "Cloth", rnd, 0.3,
                   rot=rot @ Matrix.Rotation(sx * 0.25, 3, "Z"))
        g.blob(c + rot @ V((0, 0.13, 0)), 0.2, 0.09, 0.035, nu, nv, "Cloth", rnd, 0.25, rot=rot)
        if lod == 0:  # waist drawstring
            pts = [c + rot @ V((math.cos(a) * 0.17, 0.15 + math.sin(a) * 0.05, 0.03)) for a in
                   [i * 0.5 for i in range(13)]]
            g.sweep(pts, 0.006, 3, "Cloth")
    elif kind == "loincloth":
        w, L = 0.16, 0.6
        pts = []
        for i in range(n_(8, lod, 3) + 1):
            t = i / n_(8, lod, 3)
            pts.append(c + rot @ V((math.sin(t * 5 + ang) * 0.06, -L / 2 + L * t, 0.008 + 0.015 * abs(math.sin(t * 7)))))
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            side = (rot @ V((w / 2, 0, 0)))
            g.face([a - side, a + side, b + side, b - side], "Cloth", (0, 0, 1))
    else:  # shirt
        g.blob(c, 0.32, 0.26, 0.05, nu, nv, "Cloth", rnd, 0.35, rot=rot)
        for sx in (-1, 1):
            g.blob(c + rot @ V((sx * 0.33, 0.1, 0)), 0.18, 0.07, 0.03, max(nu - 2, 4), 1, "Cloth", rnd, 0.3,
                   rot=rot @ Matrix.Rotation(sx * 0.6, 3, "Z"))


def clothes_pile(g, c, n, rnd, lod, spread=0.6, kinds=("breeches", "loincloth", "shirt")):
    for i in range(n):
        k = kinds[i % len(kinds)]
        off = V((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), 0.012 * i))
        garment(g, V(c) + off, rnd.uniform(0, 6.28), k, rnd, lod)


def cobweb(g, corner, d1, d2, size, rnd, lod):
    """Cobweb in a corner: spokes and a spiral of thin threads (face 4)."""
    if lod > 0:
        return
    corner, d1, d2 = V(corner), V(d1).normalized(), V(d2).normalized()
    nrm = d1.cross(d2).normalized()
    anchors = [corner + (d1 * math.cos(a) + d2 * math.sin(a)) * size * rnd.uniform(0.8, 1.15)
               for a in [i * (math.pi / 2) / 5 for i in range(6)]]
    w = 0.0035

    def thread(a, b):
        t = (b - a)
        side = t.cross(nrm).normalized() * w
        g.face([a - side, b - side, b + side, a + side], "Cloth", nrm)
        g.face([a - side, b - side, b + side, a + side], "Cloth", -nrm)
    for a in anchors:
        thread(corner, a)
    for r in (0.3, 0.55, 0.8):
        pts = [corner + (a - corner) * r + nrm * 0.0 for a in anchors]
        for i in range(len(pts) - 1):
            thread(pts[i], pts[i + 1])


def skeleton(pose, lod, rnd):
    """Skeleton in local coordinates (faces +Y, Z up). Poses: sitting, hanging, lying."""
    g = Geo()
    J = {}
    if pose == "sitting":       # sitting against the wall (at -Y), head slumped
        J = dict(pelvis=(0, 0.12, 0.12), chest=(0, 0.05, 0.55), neck=(0.03, 0.06, 0.78), head=(0.06, 0.16, 0.86),
                 shoulderL=(-0.18, 0.04, 0.7), shoulderR=(0.18, 0.04, 0.7), elbowL=(-0.26, 0.2, 0.42),
                 elbowR=(0.25, 0.22, 0.4), handL=(-0.22, 0.42, 0.18), handR=(0.3, 0.38, 0.1),
                 hipL=(-0.11, 0.14, 0.1), hipR=(0.11, 0.14, 0.1), kneeL=(-0.15, 0.55, 0.32),
                 kneeR=(0.18, 0.6, 0.08), footL=(-0.15, 0.9, 0.05), footR=(0.24, 1.0, 0.05))
    elif pose == "hanging":     # standing, slumped, arms hanging
        J = dict(pelvis=(0, 0, 0.98), chest=(0, 0.03, 1.38), neck=(0, 0.05, 1.56), head=(0.03, 0.14, 1.62),
                 shoulderL=(-0.19, 0.02, 1.5), shoulderR=(0.19, 0.02, 1.5), elbowL=(-0.24, 0.04, 1.2),
                 elbowR=(0.23, 0.06, 1.2), handL=(-0.24, 0.08, 0.92), handR=(0.22, 0.1, 0.94),
                 hipL=(-0.11, 0, 0.95), hipR=(0.11, 0, 0.95), kneeL=(-0.12, 0.06, 0.52),
                 kneeR=(0.1, 0.1, 0.53), footL=(-0.13, 0.02, 0.08), footR=(0.1, 0.08, 0.08))
    else:                       # lying face up
        J = dict(pelvis=(0, 0, 0.1), chest=(0, 0.45, 0.12), neck=(0, 0.66, 0.1), head=(0.05, 0.78, 0.1),
                 shoulderL=(-0.19, 0.58, 0.1), shoulderR=(0.19, 0.58, 0.1), elbowL=(-0.42, 0.45, 0.05),
                 elbowR=(0.3, 0.3, 0.05), handL=(-0.6, 0.6, 0.03), handR=(0.28, 0.02, 0.03),
                 hipL=(-0.11, -0.03, 0.08), hipR=(0.11, -0.03, 0.08), kneeL=(-0.2, -0.45, 0.06),
                 kneeR=(0.18, -0.42, 0.2), footL=(-0.24, -0.86, 0.04), footR=(0.16, -0.82, 0.04))
    J = {k: V(v) for k, v in J.items()}
    nb = 6 if lod == 0 else 4
    r = 0.022

    def bone(a, b, rr=r):
        g.cyl(J[a], J[b], rr, nb, "Bone", caps=(False, False))
        if lod == 0:
            for p in (J[a], J[b]):
                g.blob(p - V((0, 0, rr * 1.2)), rr * 1.6, rr * 1.6, rr * 2.2, 6, 2, "Bone", rnd, 0.1, flat_bottom=False)
    for a, b in (("shoulderL", "elbowL"), ("elbowL", "handL"), ("shoulderR", "elbowR"), ("elbowR", "handR"),
                 ("hipL", "kneeL"), ("kneeL", "footL"), ("hipR", "kneeR"), ("kneeR", "footR")):
        bone(a, b, 0.024 if "knee" in a or "hip" in a else 0.018)
    bone("shoulderL", "shoulderR", 0.012)
    # spine
    spine = [J["pelvis"].lerp(J["chest"], t) for t in (0, 0.5, 1.0)] + [J["neck"]]
    g.sweep(spine, 0.02, nb, "Bone")
    # pelvis
    g.blob(J["pelvis"] - V((0, 0, 0.06)), 0.15, 0.08, 0.11, n_(10, lod, 5), 2, "Bone", rnd, 0.12, flat_bottom=False)
    # ribs
    up = (J["neck"] - J["pelvis"]).normalized()
    fwd = (J["head"] - J["neck"])
    fwd = (fwd - up * fwd.dot(up)).normalized() if fwd.length > 0.01 else V((0, 1, 0))
    side = up.cross(fwd).normalized()
    nr = 5 if lod == 0 else 3
    for i in range(nr):
        c = J["chest"].lerp(J["pelvis"], 0.08 + i * 0.13)
        wdt = 0.15 - 0.012 * i
        for sg in (-1, 1):
            pts = [c + side * (sg * wdt * math.sin(a)) + fwd * (0.1 * (1 - math.cos(a)) - 0.02) - up * (0.03 * a)
                   for a in [j * math.pi / 6 for j in range(7)]]
            g.sweep(pts, 0.008, 3, "Bone", caps=False)
    # skull and jaw
    hc = J["head"]
    g.blob(hc, 0.085, 0.1, 0.1, n_(12, lod, 6), 3 if lod == 0 else 2, "Bone", rnd, 0.05, flat_bottom=False)
    g.blob(hc + fwd * 0.05 - up * 0.08, 0.06, 0.05, 0.03, 8, 1, "Bone", rnd, 0.05)
    if lod == 0:  # dark eye sockets: hollows made with two iron discs (they read as black)
        for sg in (-1, 1):
            p = hc + fwd * 0.093 + side * (sg * 0.033) + up * 0.01
            g.cyl(p - fwd * 0.01, p + fwd * 0.004, 0.018, 6, "Iron", caps=(False, True))
        p = hc + fwd * 0.095 - up * 0.03
        g.cyl(p - fwd * 0.01, p + fwd * 0.004, 0.01, 3, "Iron", caps=(False, True))
    return g


def skull(g, c, lod, rnd, look=V((0, 1, 0))):
    c = V(c)
    g.blob(c, 0.085, 0.1, 0.1, n_(10, lod, 5), 2, "Bone", rnd, 0.06, flat_bottom=False)
    if lod == 0:
        f = V(look).normalized()
        sd = f.cross(V((0, 0, 1))).normalized()
        for sg in (-1, 1):
            p = c + f * 0.09 + sd * (sg * 0.033) + V((0, 0, 0.01))
            g.cyl(p - f * 0.01, p + f * 0.004, 0.018, 6, "Iron", caps=(False, True))


def wheel(g, c, axis, up, R, lod, spokes=8, handles=False, mat="Wood"):
    """Spoked wheel (ship's helm, torture wheel, winch wheel)."""
    c, axis, up = V(c), V(axis).normalized(), V(up).normalized()
    side = up.cross(axis).normalized()
    g.link(c, up, side, R, R, R * 0.07, n_(24, lod, 8), 4 if lod == 0 else 3, mat)
    g.cyl(c - axis * 0.08, c + axis * 0.08, R * 0.16, n_(10, lod, 5), mat)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        d = up * math.cos(a) + side * math.sin(a)
        g.cyl(c + d * R * 0.14, c + d * (R * (1.25 if handles else 0.97)), R * 0.04, 4 if lod == 0 else 3, mat,
              caps=(False, handles))
        if handles and lod == 0:
            g.cyl(c + d * R * 1.08, c + d * R * 1.32, R * 0.06, 6, mat, caps=(False, True), r1=R * 0.04)


# ================================================================== fronts: piers and heads
def grille_panel(g, s, yc, sg, lod):
    """Fixed grille panel on one side of the door (sg -1 = south, the hinge side)."""
    fr = front_frame(s)
    d = GRILLE_D
    P_ = lambda u, v: fr.p(yc + u, v, d)
    top = lambda u: ARCH_SPRING + arch_height(u, ARCH_SPAN, ARCH_RATIO) + 0.06
    step = 0.152 if lod <= 1 else 0.45
    nb = int((2 * HW - 0.16) / step)
    off = -(nb * step) / 2
    for i in range(nb + 1):
        u = off + i * step
        if sg * u > DOOR_HW + 0.06 and abs(u) <= HW - 0.05:
            if lod == 0:
                bar(g, P_(u, FL - 0.04), P_(u, top(u)), 0.021, 6, "Iron")
            else:  # flat two-sided strip: reads the same from afar and costs 4 triangles
                a0, a1 = P_(u - 0.02, FL), P_(u + 0.02, FL)
                b0, b1 = P_(u - 0.02, top(u)), P_(u + 0.02, top(u))
                g.face([a0, a1, b1, b0], "Iron", fr.n)
    u = sg * (DOOR_HW + 0.045)
    if lod == 0:
        bx(g, *_fx(fr, yc + u - 0.04, yc + u + 0.04, d - 0.04, d + 0.04), FL - 0.04, top(abs(u)), "Iron",
           skip=("-z", "+z"))
    if lod == 0:
        for z in (FL + 0.2, FL + 1.35):
            a, b = sorted((yc + sg * (DOOR_HW + 0.08), yc + sg * (HW + 0.04)))
            bx(g, *_fx(fr, a, b, d - 0.035, d + 0.035), z, z + 0.055, "Iron")
    if lod == 0:
        if sg < 0:  # hinge pins
            for z in (FL + 0.42, FL + 2.18):
                g.cyl(P_(-DOOR_HW - 0.05, z), P_(-DOOR_HW, z), 0.016, 6, "Iron")
                g.cyl(P_(-DOOR_HW, z - 0.06), P_(-DOOR_HW, z + 0.07), 0.011, 6, "Iron")
        else:       # lock keeper
            p0 = fr.p(yc + DOOR_HW, FL + 1.12, d - 0.06)
            p1 = fr.p(yc + DOOR_HW + 0.09, FL + 1.3, d + 0.06)
            bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Iron", 0.01)


def make_piers(s):
    S = "W" if s < 0 else "E"
    X = lambda x: s * x
    fr = front_frame(s)
    yard_face = flipx(("-x",), s)[0]
    cell_face = flipx(("+x",), s)[0]
    for j in range(5):
        ua = YP[j] - 0.975 if j > 0 else YP[0] - PT
        ub = YP[j] + 0.975 if j < 4 else YP[4] + PT
        sides = []
        if j > 0:
            sides.append((cell_center(j - 1), +1))   # this pier is the north side of bay j-1
        if j < 4:
            sides.append((cell_center(j), -1))

        def build(lod, ua=ua, ub=ub, sides=sides, j=j):
            g = Geo()
            ends = ()
            if lod == 3:
                bx(g, X(NX), X(NX + FT), ua, ub, FL, WT + 0.2, "Stone",
                   skip=("-z", "-y", "+y", cell_face))
                return g
            bx(g, X(NX), X(NX + FT), ua, ub, ZB, WT, "Stone",
               skip=("-z",) + ((cell_face,) if lod == 1 else ()) + ends)
            if lod == 0:
                bx(g, *_fx(fr, ua, ub, -FT - 0.07, 0.07), WT, WT + 0.2, "Stone", 0.035)
                poly = [(0.0, FL - 0.02), (0.09, FL - 0.02), (0.09, FL + 0.42), (0.0, FL + 0.56)]
                g.prism(poly, Frame((X(NX), 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)), ua, ub, "Stone")
                for yc, sg in sides:
                    u_in = yc + sg * HW
                    zq = FL + 0.56
                    hq = (ARCH_SPRING - 0.26 - zq) / 5
                    for i in range(5):
                        wq = 0.55 if i % 2 == 0 else 0.34
                        p0 = fr.p(u_in, zq + i * hq + 0.008, 0)
                        p1 = fr.p(u_in + sg * wq, zq + (i + 1) * hq - 0.008, 0.035)
                        bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Stone", skip=(cell_face,))
                    p0 = fr.p(u_in, ARCH_SPRING - 0.26, 0)
                    p1 = fr.p(u_in + sg * 0.3, ARCH_SPRING, 0.11)
                    bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Stone", skip=(cell_face,))
                    # soot stains: thin dark iron slabs above the torch spot
            for yc, sg in sides:
                grille_panel(g, s, yc, sg, lod)
            return g

        def phys(ua=ua, ub=ub, sides=sides):
            out = [pbox(X(NX), X(NX + FT), ua, ub, ZB, WT + 0.2)]
            g0, g1 = NX - GRILLE_D - 0.06, NX - GRILLE_D + 0.06
            for yc, sg in sides:
                a, b = sorted((yc + sg * HW, yc + sg * DOOR_HW))
                out.append(pbox(X(g0), X(g1), a, b, FL, CROWN))
            return out

        reg(f"M{j}{S}_Pier", "structure", build, phys, BIG)


def make_head(s, k):
    tag = ROOMS[(s, k)][0]
    X = lambda x: s * x
    fr = front_frame(s)
    yc = cell_center(k)
    cell_face = flipx(("+x",), s)[0]

    def build(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        arch_wall(g, fr, yc - HW, yc + HW, yc, ARCH_SPAN, ARCH_RATIO, ARCH_SPRING, ZB, WT, FT, n_side, "Stone",
                  skip_u0=True, skip_u1=True, thr_top=None, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
        if lod == 3:
            return g
        if lod == 0:
            bx(g, *_fx(fr, yc - HW, yc + HW, -FT - 0.07, 0.07), WT, WT + 0.2, "Stone", 0.035,
               skip=("-y", "+y"))
            voussoirs(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 6, 0.55, 0.06, "Stone")
            hood(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 12, 0.68, 0.13, 0.11, "Stone")
        else:
            pass
        # grille above the door, header and the transom at the springing
        d = GRILLE_D
        P_ = lambda u, v: fr.p(yc + u, v, d)
        top = lambda u: ARCH_SPRING + arch_height(u, ARCH_SPAN, ARCH_RATIO) + 0.06
        head = FL + DOOR_H + 0.02
        step = 0.152
        nb = int((2 * HW - 0.16) / step)
        off = -(nb * step) / 2
        for i in range(nb + 1):
            u = off + i * step
            if abs(u) < DOOR_HW + 0.06:
                if lod == 0:
                    bar(g, P_(u, head + 0.03), P_(u, top(u)), 0.021, 6, "Iron")
                else:
                    a0, a1 = P_(u - 0.02, head), P_(u + 0.02, head)
                    g.face([a0, a1, P_(u + 0.02, top(u)), P_(u - 0.02, top(u))], "Iron", fr.n)
            elif lod == 0 and abs(u) < HW - 0.1:
                z = ARCH_SPRING + 0.03
                g.cyl(P_(u, z), P_(u, z + 0.12), 0.03, 4, "Iron", caps=(True, False), r1=0.0)
        sk = () if lod == 0 else ("-y", "+y", "-z", flipx(("+x",), s)[0])
        bx(g, *_fx(fr, yc - HW - 0.04, yc + HW + 0.04, d - 0.045, d + 0.045), head, head + 0.09, "Iron", skip=sk)
        bx(g, *_fx(fr, yc - HW - 0.04, yc + HW + 0.04, d - 0.035, d + 0.035), ARCH_SPRING - 0.03,
           ARCH_SPRING + 0.03, "Iron", skip=sk)
        return g

    def phys():
        g0, g1 = NX - GRILLE_D - 0.06, NX - GRILLE_D + 0.06
        return [pbox(X(NX), X(NX + FT), yc - HW, yc + HW, CROWN, WT + 0.2),
                pbox(X(g0), X(g1), yc - DOOR_HW, yc + DOOR_HW, FL + DOOR_H + 0.02, CROWN)]

    reg(f"{tag}_Arch", "structure", build, phys, BIG, role=ROOMS[(s, k)][1])


def make_door(s, k):
    tag, room = ROOMS[(s, k)]
    fr = front_frame(s)
    yc = cell_center(k)

    def build(lod):
        g = Geo()
        d = GRILLE_D
        P_ = lambda u, v: fr.p(yc + u, v, d)
        z0, z1 = FL + 0.03, FL + DOOR_H - 0.02
        u0, u1 = -DOOR_HW + 0.03, DOOR_HW - 0.02
        if lod == 3:
            g.face([P_(u0, z0), P_(u1, z0), P_(u1, z1), P_(u0, z1)], "Iron", fr.n)
            g.face([P_(u0, z0), P_(u1, z0), P_(u1, z1), P_(u0, z1)], "Iron", -fr.n)
            return g
        c = 0.006 if lod == 0 else 0
        for (a, b) in ((u0, u0 + 0.06), (u1 - 0.06, u1)):
            bx(g, *_fx(fr, yc + a, yc + b, d - 0.03, d + 0.03), z0, z1, "Iron", c)
        for z in ((z0, z0 + 0.06), (FL + 1.25, FL + 1.3), (z1 - 0.06, z1)):
            bx(g, *_fx(fr, yc + u0 + 0.06, yc + u1 - 0.06, d - 0.025, d + 0.025), z[0], z[1], "Iron")
        nb = 7 if lod <= 1 else 3
        for i in range(nb):
            u = u0 + 0.06 + (u1 - u0 - 0.12) * (i + 1) / (nb + 1)
            bar(g, P_(u, z0 + 0.03), P_(u, z1 - 0.03), 0.02, {0: 8, 1: 4}.get(lod, 3), "Iron")
        if lod == 2:
            return g
        g.sweep([P_(u0 + 0.06, z0 + 0.06), P_(u1 - 0.06, FL + 1.25)], 0.022, 4, "Iron")
        g.sweep([P_(u0 + 0.06, FL + 1.3), P_(u1 - 0.06, z1 - 0.06)], 0.022, 4, "Iron")
        for z in (FL + 0.42, FL + 2.18):
            g.cyl(P_(-DOOR_HW, z - 0.07), P_(-DOOR_HW, z + 0.07), 0.03, 8 if lod == 0 else 4, "Iron")
            g.cyl(P_(-DOOR_HW + 0.02, z), P_(u0 + 0.05, z), 0.012, 4, "Iron")
            bx(g, *_fx(fr, yc + u0, yc + u0 + 0.35, d - 0.034, d + 0.034), z - 0.03, z + 0.03, "Iron")
        bx(g, *_fx(fr, yc + u1 - 0.2, yc + u1 + 0.005, d - 0.05, d + 0.05), FL + 1.1, FL + 1.32, "Iron", c)
        if lod == 0:
            for sg in (1, -1):
                face = d + sg * 0.05
                n = fr.n * sg
                sc = fr.p(yc + u1 - 0.1, FL + 1.21, face) + n * 0.02
                g.link(sc, n, V((0, 0, 1)), 0.035, 0.022, 0.008, 8, 4, "Iron")
                rc = sc + n * 0.012 + V((0, 0, -(0.022 - 0.008) + 0.009 - 0.06))
                g.link(rc, V((0, 1, 0)), V((0, 0, 1)), 0.06, 0.06, 0.009, 14, 5, "Iron")
                kp = fr.p(yc + u1 - 0.1, FL + 1.15, face)
                g.cyl(kp, kp + n * 0.006, 0.018, 6, "Iron", caps=(False, True))
            # hanging padlock
            lp = fr.p(yc + u1 - 0.06, FL + 1.0, d + 0.06)
            g.bbox(lp - V((0.04, 0.04, 0.05)), lp + V((0.04, 0.04, 0.03)), "Iron", 0.01)
            g.link(lp + V((0, 0, 0.06)), V((0, 0, 1)), fr.u, 0.035, 0.025, 0.007, 8, 4, "Iron")
        return g

    reg(f"{tag}_Door", "door", build,
        lambda: [pbox(*_fx(fr, yc - DOOR_HW + 0.03, yc + DOOR_HW - 0.02, GRILLE_D - 0.05, GRILLE_D + 0.05),
                      FL + 0.03, FL + DOOR_H - 0.02)], role=room)


# ================================================================== shell of each room
def make_room_shell(s, k0, k1, tag, room, roof="vault"):
    """Floor, outer wall, north partition and roof of rooms k0..k1 (inclusive)."""
    X = lambda x: s * x
    y0, y1 = YP[k0], YP[k1 + 1]
    cy0, cy1 = y0 + PT, y1 - PT
    inner = flipx(("-x",), s)[0]

    # ---------------- earth floor with thresholds
    def floor(lod):
        g = Geo()
        x0, x1 = 3.8, XI
        rr = rng(f"suelo-{tag}")
        nxg, nyg = {0: (14, int(10 * (k1 - k0 + 1))), 1: (2, 2)}.get(lod, (1, 1))
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
        for k in range(k0, k1 + 1):
            yc = cell_center(k)
            bx(g, X(NX), X(NX + FT), yc - HW, yc + HW, ZB if lod <= 1 else FL - 0.01, FL, "Floor",
               skip=("-z", "-y", "+y", inner) if lod >= 1 else ("-z",))
        if lod == 0:
            bx(g, X(x0), X(x1), cy0, cy1, ZB + 0.1, FL, "Floor", skip=("+z", "-z", "-x", "+x"))
            for i in range(70):
                px = X(rr.uniform(4.2, 11.0))
                py = rr.uniform(cy0 + 0.2, cy1 - 0.2)
                a = rr.uniform(0, math.pi)
                L = rr.uniform(0.12, 0.3)
                d = V((math.cos(a), math.sin(a), 0))
                pr = V((-d.y, d.x, 0)) * 0.006
                p = V((px, py, FL + 0.02))
                g.face([p - d * L / 2 - pr, p + d * L / 2 - pr, p + d * L / 2 + pr, p - d * L / 2 + pr], "Straw",
                       (0, 0, 1))
            for i in range(10):  # rubble along the walls
                side = rr.choice((0, 1, 2))
                if side == 0:
                    p = V((X(rr.uniform(10.9, 11.4)), rr.uniform(cy0 + 0.2, cy1 - 0.2), FL))
                else:
                    yy = cy0 + 0.25 if side == 1 else cy1 - 0.25
                    p = V((X(rr.uniform(4.5, 11.0)), yy, FL))
                g.blob(p, rr.uniform(0.04, 0.1), rr.uniform(0.04, 0.09), rr.uniform(0.03, 0.06), 6, 1, "Stone", rr,
                       0.3)
        return g

    reg(f"{tag}_Floor", "structure", floor,
        lambda: [pbox(X(NX), X(XI), cy0, cy1, FL - 0.3, FL + 0.01)], BIG, role=room)

    # ---------------- north partition
    if True:
        top_part = WT if k1 == 3 else VS

        def partition(lod):
            g = Geo()
            if lod == 3:
                bx(g, X(3.8), X(XI), y1 - PT, y1 + PT, top_part - 0.02, top_part, "Stone",
                   skip=("-z", "-x", "+x", "-y", "+y"))
                return g
            bx(g, X(3.8), X(XI), y1 - PT, y1 + PT, ZB, top_part, "Stone",
               skip=("-z", "-x", "+x") + (() if k1 == 3 else ("+z",)))
            if k1 == 3:
                bx(g, X(3.75), X(XI + 0.05), y1 - PT - 0.06, y1 + PT + 0.06, WT, WT + 0.18, "Stone",
                   0.03 if lod == 0 else 0)
            return g

        reg(f"{tag}_Partition", "structure", partition,
            lambda: [pbox(X(3.8), X(XI), y1 - PT, y1 + PT, ZB, top_part + (0.18 if k1 == 3 else 0))], BIG)

    # ---------------- outer wall with arrow slits and buttresses
    def wall(lod):
        g = Geo()
        ox0, ox1 = XI, XO
        ends = (("-y",) if k0 > 0 else ()) + (("+y",) if k1 < 3 else ())
        if lod == 3:
            bx(g, X(ox0), X(ox1), y0, y1, FL, WT, "Stone", skip=("-z", "-y", "+y", inner))
            for k in range(k0, k1 + 1):
                yb = YP[k + 1]
                bx(g, X(XO), X(XB), yb - 0.45, yb + 0.45, FL, FL + 5.6, "Stone", skip=("-z", inner, "-y"))
            return g
        if lod == 1:
            bx(g, X(ox0), X(ox1), y0, y1, ZB, WT + 0.18, "Stone", skip=("-z",) + ends)
        else:
            sw_in, sw_out = 0.36, 0.09
            sz0, sz1 = FL + 1.9, FL + 3.6
            segs = []
            ya = y0
            for k in range(k0, k1 + 1):
                yc = cell_center(k)
                segs.append((ya, yc - sw_in))
                bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, ZB, sz0, "Stone", skip=("-z", "-y", "+y"))
                bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, sz1, WT, "Stone", skip=("-y", "+y"))
                for sg in (-1, 1):
                    poly = [(X(ox0), yc + sg * sw_in), (X(ox1), yc + sg * sw_in), (X(ox1), yc + sg * sw_out),
                            (X(ox0 + 0.32), yc + sg * sw_out)]
                    g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), sz0, sz1, "Stone",
                            caps=(False, False))
                    # bars in the arrow slit
                bar(g, V((X(ox0 + 0.25), yc, sz0)), V((X(ox0 + 0.25), yc, sz1)), 0.018, 6, "Iron")
                ya = yc + sw_in
            segs.append((ya, y1))
            for i, (a, b) in enumerate(segs):
                sk = ("-z",) + (("-y",) if i == 0 and k0 > 0 else ()) + (("+y",) if i == len(segs) - 1 and k1 < 3 else ())
                bx(g, X(ox0), X(ox1), a, b, ZB, WT, "Stone", skip=sk)
            bx(g, X(ox0 - 0.05), X(ox1 + 0.07), y0, y1, WT, WT + 0.18, "Stone", 0.03, skip=ends)
            poly = [(X(ox1), ZB), (X(ox1 + 0.12), ZB), (X(ox1 + 0.12), FL + 0.35), (X(ox1), FL + 0.5)]
            g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), y0, y1, "Stone",
                    caps=(k0 == 0, k1 == 3))
        for k in range(k0, k1 + 1):
            yb0, yb1 = YP[k + 1] - 0.45, YP[k + 1] + 0.45
            if lod == 0:
                bx(g, X(XO - 0.02), X(XB), yb0, yb1, ZB, FL + 2.4, "Stone", 0.03, skip=("-z",))
                g.prism([(X(XO - 0.02), FL + 2.4), (X(XB), FL + 2.4), (X(XB - 0.14), FL + 2.62),
                         (X(XO - 0.02), FL + 2.62)], Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0, yb1,
                        "Stone")
                bx(g, X(XO - 0.02), X(XB - 0.14), yb0 + 0.04, yb1 - 0.04, FL + 2.62, FL + 5.0, "Stone", 0.03)
                g.prism([(X(XO - 0.02), FL + 5.0), (X(XB - 0.14), FL + 5.0), (X(XO - 0.02), FL + 6.3)],
                        Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0 + 0.04, yb1 - 0.04, "Stone")
            else:
                bx(g, X(XO), X(XB), yb0, yb1, ZB, FL + 5.6, "Stone", skip=("-z", inner))
        return g

    def wall_phys():
        out = [pbox(X(XI), X(XO), y0, y1, ZB, WT + 0.18)]
        for k in range(k0, k1 + 1):
            out.append(pbox(X(XO), X(XB), YP[k + 1] - 0.45, YP[k + 1] + 0.45, ZB, FL + 5.6))
        return out

    reg(f"{tag}_Wall", "structure", wall, wall_phys, BIG)

    # ---------------- roof
    if roof == "vault":
        yc = cell_center(k0)

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
                r = rng(f"boveda-{tag}")
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
                # cobwebs where the vault springs
                for sg in (-1, 1):
                    cobweb(g, V((X(XI - 0.02), yc + sg * (Ri - 0.02), VS + 0.05)), V((-s, 0, 0)), V((0, -sg, 0.4)),
                           0.7, r, lod)
                    cobweb(g, V((X(3.82), yc + sg * (Ri - 0.02), VS + 0.05)), V((s, 0, 0)), V((0, -sg, 0.4)),
                           0.55, r, lod)
            return g

        reg(f"{tag}_Vault", "structure", vault,
            lambda: [pbox(X(3.8), X(XI), yc - 1.2, yc + 1.2, VS + R_VAULT + 0.02, VS + R_VAULT + T_VAULT)], BIG)
    else:
        # beamed roof for the double kennel (above the crown of the arches)
        zc = CROWN + 0.15

        def beam_roof(lod):
            g = Geo()
            xa, xb = sorted((X(3.8), X(XI)))
            if lod == 3:
                g.face([V((xa, cy0, zc + 0.32)), V((xb, cy0, zc + 0.32)), V((xb, cy1, zc + 0.32)),
                        V((xa, cy1, zc + 0.32))], "Wood", (0, 0, 1))
                return g
            if lod >= 1:
                g.face([V((xa, cy0, zc + 0.32)), V((xb, cy0, zc + 0.32)), V((xb, cy1, zc + 0.32)),
                        V((xa, cy1, zc + 0.32))], "Wood", (0, 0, 1))
                g.face([V((xa, cy0, zc)), V((xb, cy0, zc)), V((xb, cy1, zc)), V((xa, cy1, zc))], "Wood", (0, 0, -1))
                return g
            nj = int((cy1 - cy0) / 0.9)
            for i in range(nj + 1):
                y = cy0 + 0.1 + (cy1 - cy0 - 0.2) * i / nj
                bx(g, xa, xb, y - 0.12, y + 0.12, zc, zc + 0.26, "Wood", 0.02 if lod == 0 else 0,
                   skip=("-x", "+x") if lod else ())
            bx(g, xa, xb, cy0, cy1, zc + 0.26, zc + 0.32, "Wood", skip=() if lod == 0 else ("-x", "+x", "-y", "+y"))
            if lod == 0:
                for x in (xa + 0.2, xb - 0.2):  # wall plates on corbels
                    bx(g, x - 0.15, x + 0.15, cy0, cy1, zc - 0.25, zc, "Wood", 0.02)
                r = rng(f"techo-{tag}")
                for i in range(6):
                    y = r.uniform(cy0 + 0.4, cy1 - 0.4)
                    cobweb(g, V((xa + 0.02 if i % 2 else xb - 0.02, y, zc - 0.01)), V((1 if i % 2 else -1, 0, 0)),
                           V((0, 1, -0.6)), 0.6, r, lod)
            return g

        reg(f"{tag}_Roof", "structure", beam_roof,
            lambda: [pbox(X(3.8), X(XI), cy0, cy1, zc, zc + 0.32)], BIG)


# ================================================================== wall lights
def _seed_name(name):
    """Original (Spanish) name of a torch or lantern piece. Their flames hash the piece name into
    the random seed, so the old name is kept for the seed only and the geometry stays identical."""
    old = name.replace("_Torch_Hall", "_Antorcha_Vestibulo").replace("_Torch", "_Antorcha")
    old = old.replace("_Lantern", "_Farol")
    if old.startswith("A") and old[2] == "W":   # west code letter W was O
        old = old[:2] + "O" + old[3:]
    return old


def wall_torch(name, P0, n, role=""):
    def build(lod):
        return torch(V(P0), V(n), lod, f"antorcha-{_seed_name(name)}")
    reg(name, "light", build, bbox_phys(build), SMALL, fire=True, role=role)


def hanging_lantern(name, P_top):
    def build(lod):
        return lantern(V(P_top), lod, f"farol-{_seed_name(name)}")
    reg(name, "light", build, bbox_phys(build), SMALL, fire=True)


# ================================================================== room furniture
def sitter(name, build, role, lod_map=SMALL, kind="furniture"):
    """Piece an avatar sits on: convex physics, automatic LOWEST."""
    b = proxy(build)
    reg(name, kind, b, bbox_phys(b), lod_map, role=role)


def deco(name, build, role="", lod_map=SMALL, fire=False):
    b = proxy(build)
    reg(name, "light" if fire else "deco", b, bbox_phys(b), lod_map, fire=fire, role=role)


def chains_from(g, a, b, lod, sag=0.25):
    """Chain hung between two points (approximate catenary)."""
    a, b = V(a), V(b)
    pts = []
    for i in range(25):
        t = i / 24
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    chain(g, pts, 0.05, 0.03, 0.01, lod, rng("c"), -10)


def make_press_gang():
    """C01 The Press-Gang: recruits' register, scribe and branding irons."""
    s, k = -1, 0
    X = lambda x: s * x
    yc = cell_center(k)

    def desk(lod):
        g = Geo()
        r = rng("leva-escritorio")
        cx, cy = X(7.6), yc + 0.6
        q = 0.02 if lod == 0 else 0
        for dx in (-0.6, 0.6):
            for dy in (-0.3, 0.3):
                bx(g, cx + dx - 0.05, cx + dx + 0.05, cy + dy - 0.05, cy + dy + 0.05, FL, FL + 0.95, "Wood", q)
        # scribe's sloping writing board
        top = Geo()
        top.bbox(V((-0.75, -0.42, -0.03)), V((0.75, 0.42, 0.03)), "Wood", 0.01 if lod == 0 else 0)
        g.extend(xf(top, (cx, cy, FL + 1.0), rx=-0.18))
        bx(g, cx - 0.72, cx + 0.72, cy + 0.3, cy + 0.4, FL + 0.98, FL + 1.12, "Wood")
        # the Muster Book, lying open
        book = Geo()
        for sx in (-1, 1):
            book.bbox(V((0 if sx > 0 else -0.27, -0.19, 0)), V((0.27 if sx > 0 else 0, 0.19, 0.035)), "Cloth",
                      0.006 if lod == 0 else 0)
        book.box(V((-0.29, -0.2, -0.012)), V((0.29, 0.2, 0.0)), "Cloth")
        g.extend(xf(book, (cx - 0.1, cy - 0.05, FL + 1.04), rx=-0.18))
        # inkwell, quill, candle and seal
        g.cyl(V((cx + 0.48, cy + 0.33, FL + 1.12)), V((cx + 0.48, cy + 0.33, FL + 1.19)), 0.035, 8, "Iron")
        quill = [V((cx + 0.48, cy + 0.33, FL + 1.16)), V((cx + 0.43, cy + 0.25, FL + 1.38)),
                 V((cx + 0.38, cy + 0.2, FL + 1.5))]
        g.sweep(quill, 0.004, 3, "Bone", caps=False)
        g.face([quill[1] + V((0.02, 0, 0)), quill[2], quill[1] - V((0.02, 0, -0.05))], "Cloth", (0, 1, 0))
        g.face([quill[1] + V((0.02, 0, 0)), quill[2], quill[1] - V((0.02, 0, -0.05))], "Cloth", (0, -1, 0))
        g.cyl(V((cx - 0.55, cy + 0.33, FL + 1.12)), V((cx - 0.55, cy + 0.33, FL + 1.3)), 0.03, 8, "Straw")
        g.flame(V((cx - 0.55, cy + 0.33, FL + 1.3)), 0.07, 0.014, 4, "Flame", r)
        # scribe's stool
        sx_, sy_ = cx, cy - 0.75
        g.cyl(V((sx_, sy_, FL + 0.55)), V((sx_, sy_, FL + 0.6)), 0.22, n_(12, lod, 6), "Wood")
        for a in range(3):
            ang = a * 2.094
            g.cyl(V((sx_, sy_, FL + 0.56)), V((sx_ + math.cos(ang) * 0.2, sy_ + math.sin(ang) * 0.2, FL)), 0.025, 4,
                  "Wood", caps=(False, False))
        return g

    sitter("C01_Desk", desk, "scribe")
    SITS["C01_Desk"] = (V((X(7.6), yc + 0.6 - 0.75, FL + 1.0)), 90, "pit_scribe", "sit")

    def branding_brazier(lod):
        g = Geo()
        P0 = V((X(9.6), yc - 1.7, FL))
        sub = brazier(V((0, 0, 0)), lod if lod < 3 else 3)
        g.extend(xf(sub, P0, scale=0.55))
        if lod <= 1:  # branding irons resting in the embers
            for i, a in enumerate((-0.5, 0.1, 0.7)):
                d = V((math.cos(a), math.sin(a), 0))
                p0 = P0 + V((0, 0, 0.5)) - d * 0.05
                p1 = P0 + d * 0.85 + V((0, 0, 0.15))
                g.cyl(p0, p1, 0.012, 4, "Iron", caps=(False, True))
                g.cyl(p1 - d * 0.18, p1 + d * 0.02, 0.022, 6, "Wood")
                g.link(p0 + V((0, 0, -0.02)), d, V((0, 0, 1)), 0.04, 0.04, 0.008, 8, 3, "Iron")
        return g

    reg("C01_Branding_Brazier", "light", branding_brazier, bbox_phys(branding_brazier), SMALL, fire=True,
        role="branding")

    def props(lod):
        g = Geo()
        r = rng("leva-atrezzo")
        # everything sits against the outer wall: the piece's convex hull does not intrude into the room
        wx = XI                  # inner face of the outer wall
        # Press-Gang notice board: a board with sheets nailed to it
        bx(g, X(wx - 0.06), X(wx), yc - 2.3, yc - 0.3, FL + 1.3, FL + 2.5, "Wood", 0.015 if lod == 0 else 0)
        if lod == 0:
            for i in range(7):
                y0_ = yc - 2.2 + i * 0.27 + r.uniform(-0.03, 0.03)
                z0 = FL + 1.45 + r.uniform(0, 0.55)
                bx(g, X(wx - 0.068), X(wx - 0.06), y0_, y0_ + 0.22, z0, z0 + 0.3, "Cloth")
                g.cyl(V((X(wx - 0.068), y0_ + 0.11, z0 + 0.26)), V((X(wx - 0.085), y0_ + 0.11, z0 + 0.26)), 0.008, 4,
                      "Iron", caps=(False, True))
        # chest of recruits' clothes with folded shirts
        bx(g, X(wx - 0.65), X(wx - 0.05), yc - 2.2, yc - 1.0, FL, FL + 0.6, "Wood", 0.02 if lod == 0 else 0)
        if lod == 0:
            for z in (FL + 0.12, FL + 0.48):
                bx(g, X(wx - 0.66), X(wx - 0.04), yc - 2.21, yc - 0.99, z, z + 0.05, "Iron")
            for i in range(4):
                bx(g, X(wx - 0.55), X(wx - 0.15), yc - 2.1 + i * 0.27, yc - 1.85 + i * 0.27, FL + 0.6,
                   FL + 0.66 + 0.05 * (i % 2), "Cloth", 0.01)
        # press-gang shackles hung on the outer wall
        for i in range(3):
            y = yc + 0.4 + i * 0.8
            bottom, rc, u = wall_anchor(g, (X(XI), y, FL + 1.9), V((-s, 0, 0)), V((0, 0, 1)), min(lod, 2))
            if lod <= 1:  # open shackle hanging from the ring
                g.link(bottom + V((0, 0, -0.07)), V((0, 0, 1)), V((0, 1, 0)), 0.09, 0.09, 0.016, 10, 4, "Iron")
        if lod == 0:
            clothes_pile(g, (X(11.0), yc + 1.4, FL + 0.02), 4, r, lod, 0.35)
        return g

    deco("C01_Props", props)


def make_rack():
    s, k = -1, 1
    X = lambda x: s * x
    yc = cell_center(k)

    def rack(lod):
        g = Geo()
        cx = X(7.6)
        L, Wd, H = 2.5, 0.8, 0.85
        q = 0.02 if lod == 0 else 0
        for sy in (-1, 1):
            bx(g, cx - L / 2, cx + L / 2, yc + sy * Wd / 2 - 0.08, yc + sy * Wd / 2 + 0.08, FL + H - 0.18, FL + H,
               "Wood", q)
            for sx in (-1, 1):
                bx(g, cx + sx * (L / 2 - 0.1) - 0.08, cx + sx * (L / 2 - 0.1) + 0.08, yc + sy * Wd / 2 - 0.08,
                   yc + sy * Wd / 2 + 0.08, FL, FL + H + (0.25 if lod == 0 else 0.2), "Wood", q)
        for i in range(n_(7, lod, 3)):
            x = cx - L / 2 + 0.4 + i * (L - 0.8) / max(n_(7, lod, 3) - 1, 1)
            bx(g, x - 0.06, x + 0.06, yc - Wd / 2, yc + Wd / 2, FL + H - 0.06, FL + H - 0.01, "Wood")
        for sx in (-1, 1):  # rollers with rope
            xr = cx + sx * (L / 2 - 0.1)
            g.cyl(V((xr, yc - Wd / 2 - 0.12, FL + H + 0.12)), V((xr, yc + Wd / 2 + 0.12, FL + H + 0.12)), 0.08,
                  n_(12, lod, 5), "Wood")
            if lod <= 1:
                for t in (-0.15, -0.05, 0.05, 0.15):
                    g.link(V((xr, yc + t, FL + H + 0.12)), V((1, 0, 0)), V((0, 0, 1)), 0.09, 0.09, 0.012,
                           n_(10, lod, 6), 3, "Straw")
                for t in (-0.15, 0.15):
                    a = V((xr, yc + t, FL + H + 0.12))
                    b = V((cx + sx * 0.45, yc + t, FL + H + 0.04))
                    g.sweep([a, b], 0.012, 3, "Straw")
                    g.link(b, V((0, 1, 0)), V((1, 0, 0)), 0.05, 0.05, 0.015, 10, 3, "Cloth")  # leather cuff
        # winch wheel at one end
        wheel(g, V((cx + L / 2 + 0.05, yc + Wd / 2 + 0.2, FL + H + 0.12)), V((0, 1, 0)), V((0, 0, 1)), 0.45, lod,
              6, handles=True)
        return g

    sitter("C02_Rack", rack, "rack")
    SITS["C02_Rack"] = (V((X(7.6), yc, FL + 1.15)), 0, "pit_rack", "dead")

    def props(lod):
        g = Geo()
        r = rng("potro-atrezzo")
        wy = YP[2] - PT  # face of the north partition (faces south)
        # tool rack
        bx(g, X(5.0), X(7.4), wy - 0.06, wy, FL + 1.3, FL + 2.3, "Wood", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for i in range(6):
                x = X(5.25 + i * 0.38)
                g.cyl(V((x, wy - 0.06, FL + 2.1)), V((x, wy - 0.12, FL + 2.1)), 0.012, 4, "Iron")
                tool = Geo()
                if i % 3 == 0:     # pincers
                    tool.cyl(V((-0.03, 0, 0)), V((0.04, 0, -0.55)), 0.012, 4, "Iron")
                    tool.cyl(V((0.03, 0, 0)), V((-0.04, 0, -0.55)), 0.012, 4, "Iron")
                elif i % 3 == 1:   # mallet
                    tool.cyl(V((0, 0, 0)), V((0, 0, -0.5)), 0.016, 5, "Wood")
                    tool.bbox(V((-0.07, -0.04, -0.62)), V((0.07, 0.04, -0.5)), "Iron", 0.008)
                else:              # hook
                    tool.sweep([V((0, 0, 0)), V((0, 0, -0.35)), V((0.06, 0, -0.45)), V((0.1, 0, -0.38))], 0.01, 4,
                               "Iron")
                g.extend(xf(tool, (x, wy - 0.12, FL + 2.08)))
        # water bucket and discarded clothes
        bc = V((X(10.9), wy - 0.4, FL))
        g.cyl(bc, bc + V((0, 0, 0.38)), 0.17, n_(12, lod, 6), "Wood", caps=(True, False), r1=0.2)
        if lod == 0:
            g.cyl(bc + V((0, 0, 0.3)), bc + V((0, 0, 0.02)), 0.186, 12, "Floor", caps=(True, False), r1=0.171)
            clothes_pile(g, (X(8.3), wy - 0.45, FL + 0.02), 5, r, lod, 0.35)
            sk = skeleton("lying", lod, r)   # stretched out along the wall
            g.extend(xf(sk, (X(9.6), wy - 0.55, FL), rz=-1.57 * s))
        return g

    deco("C02_Props", props)
    wall_torch("C02_Torch", (X(XI), yc + 1.8, FL + 2.3), (-s, 0, 0), "The Rack")


def make_stocks():
    s, k = -1, 2
    X = lambda x: s * x
    yc = cell_center(k)

    def pillory(lod):
        g = Geo()
        cx, cy = X(7.4), yc
        q = 0.02 if lod == 0 else 0
        bx(g, cx - 1.1, cx + 1.1, cy - 1.1, cy + 1.1, FL, FL + 0.32, "Wood", q)
        if lod == 0:
            for i in range(9):  # platform boards
                y = cy - 1.1 + i * 2.2 / 9
                bx(g, cx - 1.11, cx + 1.11, y + 0.005, y + 2.2 / 9 - 0.005, FL + 0.32, FL + 0.335, "Wood")
            for i in range(2):  # steps
                bx(g, cx - 0.5, cx + 0.5, cy - 1.1 - 0.3 * (i + 1), cy - 1.1 - 0.3 * i, FL, FL + 0.21 - 0.1 * i,
                   "Wood", q)
        base = FL + 0.335
        bx(g, cx - 0.1, cx + 0.1, cy + 0.2, cy + 0.4, base, base + 2.0, "Wood", q)
        # yoke with three holes (neck and wrists)
        holes = [(-0.38, 0.055), (0.0, 0.085), (0.38, 0.055)]
        w = 0.65
        # (simplified polygon: two notched boards)
        for sgn, z0 in ((-1, 1.42), (1, 1.42)):
            poly = [(-w, 0.0)]
            for hx, hr in holes:
                nseg = 6 if lod == 0 else 3
                for i in range(nseg + 1):
                    a = math.pi * i / nseg
                    poly.append((hx - math.cos(a) * hr, sgn * math.sin(a) * hr))
            poly.append((w, 0.0))
            poly.append((w, sgn * 0.17))
            poly.append((-w, sgn * 0.17))
            if sgn > 0:
                poly = list(reversed(poly))
            fr = Frame((cx, cy + 0.3, base + z0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
            g.prism(poly, fr, -0.06, 0.06, "Wood")
        if lod == 0:
            for sx in (-1, 1):
                bx(g, cx + sx * 0.66 - 0.02, cx + sx * 0.66 + 0.02, cy + 0.23, cy + 0.37, base + 1.22, base + 1.62,
                   "Iron")
            g.bbox(V((cx + 0.62, cy + 0.2, base + 1.35)), V((cx + 0.72, cy + 0.24, base + 1.47)), "Iron", 0.01)
        return g

    sitter("C03_Pillory", pillory, "pillory")
    SITS["C03_Pillory"] = (V((X(7.4), yc - 0.15, FL + 1.35)), 90, "pit_pillory", "stand")

    def stocks(lod):
        g = Geo()
        cx, cy = X(9.9), yc + 1.5
        q = 0.015 if lod == 0 else 0
        bx(g, cx - 0.9, cx + 0.9, cy - 0.15, cy + 0.15, FL + 0.38, FL + 0.46, "Wood", q)  # bench
        for sx in (-0.8, 0.8):
            bx(g, cx + sx - 0.05, cx + sx + 0.05, cy - 0.12, cy + 0.12, FL, FL + 0.38, "Wood", q)
        fy = cy - 0.75
        for z0, z1 in ((FL, FL + 0.2), (FL + 0.2, FL + 0.38)):
            bx(g, cx - 0.7, cx + 0.7, fy - 0.06, fy + 0.06, z0 + 0.003, z1, "Wood", q)
        if lod == 0:
            for hx in (-0.18, 0.18):
                g.cyl(V((cx + hx, fy - 0.07, FL + 0.2)), V((cx + hx, fy + 0.07, FL + 0.2)), 0.05, 8, "Floor",
                      caps=(True, True))
            for sx in (-0.72, 0.72):
                bx(g, cx + sx - 0.02, cx + sx + 0.02, fy - 0.07, fy + 0.07, FL + 0.1, FL + 0.32, "Iron")
        return g

    sitter("C03_Stocks", stocks, "stocks")
    SITS["C03_Stocks"] = (V((X(9.9), yc + 1.5, FL + 0.9)), -90, "pit_stocks", "sit")

    def props(lod):
        g = Geo()
        r = rng("cepo-atrezzo")
        # torture wheel hung on the outer wall
        wheel(g, V((X(XI - 0.18), yc - 1.2, FL + 2.4)), V((-s, 0, 0)), V((0, 0, 1)), 0.75, lod, 10)
        if lod == 0:
            g.link(V((X(XI - 0.18), yc - 1.2, FL + 2.4)), V((0, 0, 1)), V((0, 1, 0)), 0.76, 0.76, 0.03, 28, 4,
                   "Iron")
            g.cyl(V((X(XI), yc - 1.2, FL + 2.4)), V((X(XI - 0.3), yc - 1.2, FL + 2.4)), 0.05, 6, "Iron")
            clothes_pile(g, (X(10.6), yc - 2.0, FL + 0.02), 3, r, lod, 0.4)
            for i in range(3):
                skull(g, V((X(r.uniform(10.2, 11.2)), yc + r.uniform(-0.8, 0.0), FL + 0.09)), lod, r,
                      V((-s, r.uniform(-0.5, 0.5), 0)))
        return g

    deco("C03_Props", props)
    wall_torch("C03_Torch", (X(XI), yc + 0.6, FL + 2.3), (-s, 0, 0), "The Stocks")


def make_cistern():
    s, k = -1, 3
    X = lambda x: s * x
    yc = cell_center(k)
    tx0, tx1 = 8.2, 11.5          # seawater tank against the outer wall
    ty0, ty1 = yc - 1.5, yc + 1.5
    wall = 0.28
    H = FL + 0.95
    piv = V((X(7.3), yc, FL + 1.75))   # pivot axis of the ducking chair

    def cistern(lod):
        g = Geo()
        a, b = sorted((X(tx0), X(tx1)))
        q = 0.025 if lod == 0 else 0
        if lod == 3:
            bx(g, a, b, ty0, ty1, FL, H, "Stone", skip=("-z",))
            return g
        for (xa, xb, ya, yb) in ((a, b, ty0, ty0 + wall), (a, b, ty1 - wall, ty1), (a, a + wall, ty0 + wall, ty1 - wall),
                                 (b - wall, b, ty0 + wall, ty1 - wall)):
            bx(g, xa, xb, ya, yb, FL, H, "Stone", q, skip=("-z",))
        bx(g, a + wall, b - wall, ty0 + wall, ty1 - wall, FL - 0.4, FL - 0.3, "Stone", skip=("-z",))
        # crane trestle
        for sy in (-1, 1):
            g.cyl(piv + V((0, sy * 0.45, -1.75)), piv + V((0, sy * 0.12, 0.05)), 0.07, n_(8, lod, 4), "Wood")
            g.cyl(piv + V((-s * 0.6, sy * 0.45, -1.75)), piv + V((0, sy * 0.12, 0.0)), 0.06, n_(8, lod, 4), "Wood")
        g.cyl(piv + V((0, -0.2, 0)), piv + V((0, 0.2, 0)), 0.035, 8, "Iron")
        return g

    reg("C04_Cistern", "structure", cistern,
        lambda: [pbox(X(tx0), X(tx1), ty0, ty1, FL - 0.3, H), pbox(X(7.3) - 0.35, X(7.3) + 0.35, yc - 0.5, yc + 0.5, FL,
                                                                     FL + 1.8)], BIG)

    def water(lod):
        g = Geo()
        a, b = sorted((X(tx0 + wall), X(tx1 - wall)))
        z = H - 0.18
        g.face([V((a, ty0 + wall, z)), V((b, ty0 + wall, z)), V((b, ty1 - wall, z)), V((a, ty1 - wall, z))], "Water",
               (0, 0, 1))
        if lod == 0:  # dark bottom so the water has depth
            g.face([V((a, ty0 + wall, FL - 0.29)), V((b, ty0 + wall, FL - 0.29)), V((b, ty1 - wall, FL - 0.29)),
                    V((a, ty1 - wall, FL - 0.29))], "Water", (0, 0, 1))
        return g

    reg("C04_Water", "water", water, bbox_phys(water), STD, role="water")

    def chair(lod):
        """Tilting arm with the chair at the end, over the water (it pivots about `piv`)."""
        g = Geo()
        q = 0.015 if lod == 0 else 0
        arm_a = piv + V((-s * 1.6, 0, 0))      # counterweight (yard side)
        arm_b = piv + V((s * 2.6, 0, 0))       # chair (over the water)
        g.cyl(arm_a, arm_b, 0.075, n_(8, lod, 4), "Wood")
        g.link(piv, V((0, 0, 1)), V((1, 0, 0)), 0.08, 0.08, 0.02, 10, 4, "Iron")
        bx(g, *sorted((arm_a.x - 0.25, arm_a.x + 0.25)), yc - 0.25, yc + 0.25, arm_a.z - 0.55, arm_a.z - 0.05,
           "Stone", q)  # counterweight
        g.cyl(arm_a, arm_a - V((0, 0, 0.1)), 0.05, 6, "Iron")
        # chair hung from chains
        seat = arm_b + V((0, 0, -0.55))
        for sx in (-1, 1):
            for sy in (-1, 1):
                a = arm_b + V((0, 0, -0.08))
                b = seat + V((sx * 0.25, sy * 0.25, 0.4))
                if lod <= 1:
                    chains_from(g, a, b, lod, 0.0)
        bx(g, seat.x - 0.28, seat.x + 0.28, yc - 0.28, yc + 0.28, seat.z, seat.z + 0.06, "Wood", q)
        bx(g, seat.x + s * 0.24, seat.x + s * 0.3, yc - 0.28, yc + 0.28, seat.z, seat.z + 0.9, "Wood", q)
        for sy in (-1, 1):
            bx(g, seat.x - 0.28, seat.x + 0.28, yc + sy * 0.28 - 0.03, yc + sy * 0.28 + 0.03, seat.z + 0.3,
               seat.z + 0.36, "Wood")
            bx(g, seat.x - 0.28, seat.x - 0.22, yc + sy * 0.28 - 0.03, yc + sy * 0.28 + 0.03, seat.z, seat.z + 0.36,
               "Wood")
        if lod == 0:
            g.link(seat + V((0, 0, 0.45)), V((0, 1, 0)), V((0, 0, 1)), 0.32, 0.06, 0.012, 14, 4, "Cloth")  # strap
        return g

    pc = reg("C04_Chair", "furniture", proxy(chair), bbox_phys(proxy(chair)), SMALL, role="chair")
    SITS["C04_Chair"] = (piv + V((s * 2.6, 0, -0.55 + 0.45)), 0 if s < 0 else 180, "pit_chair", "sit")
    pc.pivot = piv
    wall_torch("C04_Torch", (X(5.0), YP[4] - PT, FL + 2.3), (0, -1, 0), "The Cistern")

    def props(lod):
        g = Geo()
        r = rng("cisterna-atrezzo")
        # the one who did not last: a skeleton chained to the wall, sitting next to the tank
        sk = skeleton("sitting", lod, r)
        g.extend(xf(sk, (X(6.0), YP[3] + PT + 0.05, FL), rz=0.0))
        for sx in (-0.3, 0.3):
            bottom, rc, u = wall_anchor(g, (X(6.0 + sx), YP[3] + PT, FL + 0.95), V((0, 1, 0)), V((0, 0, 1)), min(lod, 2))
            if lod <= 1:
                chains_from(g, bottom, V((X(6.0 + sx * 0.8), YP[3] + PT + 0.35, FL + 0.35)), lod, 0.1)
        if lod == 0:
            clothes_pile(g, (X(4.9), YP[3] + PT + 0.4, FL + 0.02), 3, r, lod, 0.25)
        return g

    deco("C04_Props", props)


def make_kennel():
    """C05+C06: the only cell to live in. Here the captives live like dogs."""
    s = 1
    X = lambda x: s * x
    y0, y1 = YP[0] + PT, YP[2] - PT

    for i, yy in enumerate((y0 + 1.4, (y0 + y1) / 2, y1 - 1.4)):
        def kennel(lod, yy=yy, i=i):
            g = Geo()
            r = rng(f"jaula-{i}")
            cx = X(10.6)
            L, W, H = 1.5, 1.0, 1.05
            x0, x1 = cx - W / 2, cx + W / 2
            q = 0.012 if lod == 0 else 0
            for xx in (x0, x1):
                for y in (yy - L / 2, yy + L / 2):
                    bx(g, xx - 0.04, xx + 0.04, y - 0.04, y + 0.04, FL, FL + H, "Wood", q)
            for z in (FL + 0.05, FL + H - 0.04):
                for xx in (x0, x1):
                    bx(g, xx - 0.035, xx + 0.035, yy - L / 2, yy + L / 2, z - 0.035, z + 0.035, "Wood")
                for y in (yy - L / 2, yy + L / 2):
                    bx(g, x0, x1, y - 0.035, y + 0.035, z - 0.035, z + 0.035, "Wood")
            nb = n_(9, lod, 3)
            for xx in (x0, x1):           # side bars
                for j in range(nb):
                    y = yy - L / 2 + (j + 1) * L / (nb + 1)
                    bar(g, V((xx, y, FL + 0.05)), V((xx, y, FL + H - 0.04)), 0.013, 4 if lod == 0 else 3, "Iron")
            for y in (yy + L / 2,):
                for j in range(n_(6, lod, 2)):
                    xx = x0 + (j + 1) * W / (n_(6, lod, 2) + 1)
                    bar(g, V((xx, y, FL + 0.05)), V((xx, y, FL + H - 0.04)), 0.013, 4 if lod == 0 else 3, "Iron")
            bx(g, x0 - 0.05, x1 + 0.05, yy - L / 2 - 0.05, yy + L / 2 + 0.05, FL + H, FL + H + 0.05, "Wood", q)
            # small door left open (front towards the yard = -X)
            dp = Geo()
            dp.box(V((0, 0, 0)), V((0.03, 0.75, 0.85)), "Iron", skip=("-x", "+x") if lod else ())
            g.extend(xf(dp, (x0 - 0.02, yy - L / 2 + 0.05, FL + 0.1), rz=-1.9))
            # name plate and straw inside
            bx(g, x0 - 0.06, x0 - 0.02, yy - 0.3, yy + 0.3, FL + H - 0.2, FL + H - 0.02, "Wood", q)
            g.blob((cx, yy, FL), 0.38, 0.6, 0.12, n_(10, lod, 5), 2 if lod == 0 else 1, "Straw", r, 0.2)
            if lod == 0:
                garment(g, V((cx - 0.1, yy + 0.2, FL + 0.11)), r.uniform(0, 6), "breeches", r, lod)
                g.link(V((cx + 0.2, yy - 0.3, FL + 0.03)), V((1, 0, 0)), V((0, 1, 0)), 0.13, 0.13, 0.02, 14, 4,
                       "Cloth")   # leather collar
            return g

        sitter(f"C05_Kennel_{i + 1}", kennel, "kennel")
        SITS[f"C05_Kennel_{i + 1}"] = (V((X(10.6), yy, FL + 0.4)), 180, "pit_dog", "sleep")

    def bowls(lod):
        g = Geo()
        r = rng("comederos")
        wy = y1  # face of the north partition (faces south)
        # tether bar along the wall, with rings and chains ending in collars
        rail_z = FL + 1.0
        g.cyl(V((X(4.3), wy - 0.12, rail_z)), V((X(9.7), wy - 0.12, rail_z)), 0.025, n_(8, lod, 4), "Iron")
        for x in (4.3, 7.0, 9.7):
            bx(g, X(x) - 0.04, X(x) + 0.04, wy - 0.14, wy, rail_z - 0.04, rail_z + 0.04, "Iron")
        if lod <= 1:
            for j, x in enumerate((5.0, 6.2, 7.6, 8.9)):
                c = V((X(x), wy - 0.12, rail_z))
                g.link(c, V((0, 0, 1)), V((1, 0, 0)), 0.05, 0.05, 0.012, 10, 4, "Iron")
                end = V((X(x + r.uniform(-0.3, 0.3)), wy - 0.5 - r.uniform(0, 0.5), FL + 0.03))
                pts = [c - V((0, 0, 0.05))]
                for t in range(1, 9):
                    tt = t / 8
                    p = pts[0].lerp(end, tt)
                    p.z = max(FL + 0.03, (c.z - 0.05) * (1 - tt) ** 1.5 + (FL + 0.03) * (1 - (1 - tt) ** 1.5))
                    pts.append(p)
                chain(g, pts, 0.05, 0.03, 0.01, lod, r, FL)
                collar(g, end + V((0, -0.15, -0.01)), 0.13, 0.02, lod)
        # long feeding trough and bowls
        bx(g, X(4.2), X(6.4), wy - 0.55, wy - 0.05, FL, FL + 0.3, "Stone", 0.02 if lod == 0 else 0)
        if lod == 0:
            bx(g, X(4.3), X(6.3), wy - 0.48, wy - 0.12, FL + 0.18, FL + 0.31, "Floor")
        for j in range(5 if lod <= 1 else 2):
            c = V((X(7.0 + j * 0.62), wy - 0.45, FL))
            g.cyl(c, c + V((0, 0, 0.09)), 0.12, n_(12, lod, 5), "Iron", caps=(True, False), r1=0.15)
            if lod == 0:
                g.cyl(c + V((0, 0, 0.06)), c + V((0, 0, 0.015)), 0.14, 12, "Floor", caps=(True, False), r1=0.125)
        return g

    deco("C05_Bowls", bowls, "bowls")

    def clothes(lod):
        """The underwear of soldiers and slaves, thrown into the kennel to humiliate them."""
        g = Geo()
        r = rng("perrera-ropa")
        wy = y0
        for (x, y, n) in ((5.0, wy + 0.6, 7), (7.6, wy + 0.5, 6), (9.4, wy + 0.7, 5)):
            clothes_pile(g, (X(x), y, FL + 0.02), n if lod == 0 else max(n // 3, 2), r, lod, 0.5)
        if lod <= 1:
            g.blob((X(6.4), wy + 0.65, FL), 0.9, 0.5, 0.18, n_(12, lod, 5), 2 if lod == 0 else 1, "Straw", r, 0.25)
        if lod == 0:
            sk = skeleton("lying", lod, r)
            g.extend(xf(sk, (X(8.6), wy + 0.75, FL), rz=-1.57))
        return g

    deco("C05_Clothes", clothes, "clothes")
    hanging_lantern("C05_Lantern", V((X(7.6), (y0 + y1) / 2, CROWN + 0.15)))


def make_cages():
    s, k = 1, 2
    X = lambda x: s * x
    yc = cell_center(k)
    top = VS + R_VAULT - 0.02

    for i, (x, y) in enumerate(((7.0, yc - 1.1), (9.0, yc + 1.0))):
        def gibbet(lod, x=x, y=y, i=i):
            g = Geo()
            r = rng(f"gibbet-{i}")
            c = V((X(x), y, FL + 0.9))
            R, H = 0.42, 2.05
            nb = n_(12, lod, 5)
            for j in range(nb):
                a = 2 * math.pi * j / nb
                d = V((math.cos(a), math.sin(a), 0))
                pts = [c + d * R, c + d * R + V((0, 0, H * 0.8)), c + d * (R * 0.6) + V((0, 0, H * 0.95)),
                       c + V((0, 0, H)) + d * 0.08]
                g.sweep(pts if lod == 0 else [pts[0], pts[1], pts[3]], 0.012, 4 if lod == 0 else 3, "Iron", caps=False)
            for z in (0.0, 0.9, H * 0.8):
                g.link(c + V((0, 0, z)), V((1, 0, 0)), V((0, 1, 0)), R, R, 0.02, n_(20, lod, 8), 3, "Iron")
            g.cyl(c, c + V((0, 0, 0.03)), R, n_(16, lod, 6), "Iron")
            # chain up to the vault
            a_c = 0.06
            p = c + V((0, 0, H + 0.08))
            pts = [p + V((0, 0, t * (top - p.z) / 20)) for t in range(21)]
            chain(g, pts, a_c, 0.035, 0.012, lod, r, -10)
            if i == 1:  # an old tenant nobody took down
                sk = skeleton("hanging", lod, r)
                g.extend(xf(sk, c + V((0, 0, 0.03)), rz=0.7, scale=0.95))
            return g

        sitter(f"C07_Cage_{i + 1}", gibbet, "cage", lod_map=SMALL)
        SITS[f"C07_Cage_{i + 1}"] = (V((X(x), y, FL + 1.95)), 0, "pit_cage", "stand")

    def winch(lod):
        g = Geo()
        r = rng("jaulas-torno")
        wy = YP[2] + PT
        c = V((X(5.2), wy + 0.35, FL + 1.1))
        for sx in (-0.45, 0.45):
            bx(g, c.x + sx - 0.07, c.x + sx + 0.07, wy, wy + 0.5, FL, FL + 1.4, "Wood", 0.015 if lod == 0 else 0)
        g.cyl(c - V((0.5, 0, 0)), c + V((0.5, 0, 0)), 0.14, n_(12, lod, 6), "Wood")
        wheel(g, c + V((0.6, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.35, lod, 6, handles=True)
        if lod <= 1:
            for t in range(-3, 4):
                g.link(c + V((t * 0.11, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.155, 0.155, 0.012, 12, 3, "Iron")
            chains_from(g, c + V((0.2, 0.1, 0.14)), c + V((0.6, 0.35, -1.05)), lod, 0.1)
        if lod == 0:
            for j in range(3):
                skull(g, V((X(r.uniform(6.0, 7.5)), wy + r.uniform(0.2, 0.6), FL + 0.09)), lod, r,
                      V((r.uniform(-1, 1), 1, 0)))
            for j in range(6):  # loose bones
                p = V((X(r.uniform(6.0, 7.8)), wy + r.uniform(0.2, 0.7), FL + 0.025))
                a = r.uniform(0, 3.14)
                d = V((math.cos(a), math.sin(a), 0)) * r.uniform(0.12, 0.22)
                g.cyl(p - d, p + d, 0.018, 5, "Bone", caps=(True, True))
        return g

    deco("C07_Winch", winch, "cage_winch")
    wall_torch("C07_Torch", (X(XI), yc - 0.2, FL + 2.3), (-s, 0, 0), "The Cages")


def make_mast():
    s, k = 1, 3
    X = lambda x: s * x
    yc = cell_center(k)

    def mast(lod):
        g = Geo()
        r = rng("mastil")
        c = V((X(7.4), yc, FL))
        H = 3.4
        n = n_(12, lod, 5)
        g.cyl(c - V((0, 0, 0.4)), c + V((0, 0, H)), 0.2, n, "Wood", caps=(False, False), r1=0.16)
        if lod == 0:  # splintered top
            for j in range(9):
                a = 2 * math.pi * j / 9
                d = V((math.cos(a), math.sin(a), 0))
                base = c + V((0, 0, H)) + d * 0.12
                g.cyl(base - d * 0.05, base + V((0, 0, r.uniform(0.15, 0.5))) - d * 0.02, 0.05, 3, "Wood",
                      caps=(False, False), r1=0.002)
        for z in (0.4, 1.2, 2.6) if lod <= 1 else (1.2,):
            g.cyl(c + V((0, 0, z)), c + V((0, 0, z + 0.07)), 0.205 - z * 0.012, n, "Iron", caps=(False, False))
        # broken yardarm and a ring with shackles
        g.cyl(c + V((-0.9, 0, 2.95)), c + V((0.6, 0, 2.95)), 0.08, n_(8, lod, 4), "Wood")
        ring_c = c + V((0, -0.24, 2.3))
        g.link(ring_c, V((0, 0, 1)), V((1, 0, 0)), 0.09, 0.09, 0.02, 14 if lod == 0 else 6, 4 if lod == 0 else 3,
               "Iron")
        if lod <= 1:
            for sx in (-0.2, 0.2):
                chains_from(g, ring_c - V((0, 0, 0.09)), ring_c + V((sx, -0.15, -0.45)), lod, 0.05)
                g.link(ring_c + V((sx, -0.15, -0.55)), V((0, 0, 1)), V((0, 1, 0)), 0.07, 0.07, 0.014, 12, 4, "Cloth")
        # ropes coiled at the foot
        for j in range(4 if lod == 0 else 2):
            g.link(c + V((0, 0, 0.04 + j * 0.035)), V((1, 0, 0)), V((0, 1, 0)), 0.42 - j * 0.04, 0.42 - j * 0.04,
                   0.03, n_(20, lod, 8), 4 if lod == 0 else 3, "Straw")
        return g

    sitter("C08_Mast", mast, "mast")
    SITS["C08_Mast"] = (V((X(7.4), yc - 0.55, FL + 1.0)), 90, "pit_mast", "stand")

    def props(lod):
        g = Geo()
        r = rng("mastil-atrezzo")
        wy = YP[4] - PT
        # cat-o'-nine-tails on a board
        bx(g, X(5.0), X(6.6), wy - 0.06, wy, FL + 1.4, FL + 2.2, "Wood", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for j in range(3):
                h0 = V((X(5.3 + j * 0.5), wy - 0.1, FL + 2.05))
                g.cyl(h0, h0 - V((0, 0, 0.3)), 0.022, 6, "Cloth")
                for t in range(9 if lod == 0 else 3):
                    a = (t - 4) * 0.035
                    pts = [h0 - V((0, 0, 0.3)), h0 + V((a, -0.02 - abs(a) * 0.3, -0.62)),
                           h0 + V((a * 1.6, -0.03, -0.95))]
                    g.sweep(pts, 0.004, 3, "Cloth", caps=False)
        # barrel of salt for the wounds (a shipboard custom) and a brine bucket
        bc = V((X(10.6), wy - 0.6, FL))
        prof = [(0.0, 0.27), (0.45, 0.33), (0.9, 0.27)] if lod <= 1 else [(0.0, 0.28), (0.9, 0.28)]
        nn = n_(14, lod, 6)
        rings = [[bc + V((math.cos(2 * math.pi * j / nn) * rr, math.sin(2 * math.pi * j / nn) * rr, h))
                  for j in range(nn)] for h, rr in prof]
        for i in range(len(rings) - 1):
            for j in range(nn):
                j2 = (j + 1) % nn
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Wood", bc + V((0, 0, 0.45)))
        g.face(rings[-1], "Bone", (0, 0, 1))   # white salt
        if lod == 0:
            for h in (0.1, 0.8):
                g.cyl(bc + V((0, 0, h - 0.02)), bc + V((0, 0, h + 0.02)), 0.3, nn, "Iron", caps=(False, False))
            clothes_pile(g, (X(9.7), wy - 0.55, FL + 0.02), 4, r, lod, 0.3)
        return g

    deco("C08_Props", props)
    wall_torch("C08_Torch", (X(XI), yc - 1.6, FL + 2.3), (-s, 0, 0), "The Mast")


# ================================================================== yard
def make_yard():
    for k in range(4):
        def floor(lod, k=k):
            g = flagstones(f"nave-{k}", -NX, NX, YP[k], YP[k + 1], lod, channel=True, grate_y=cell_center(k))
            if lod == 0:  # rubble and chips of broken flagstones
                r = rng(f"nave-rotas-{k}")
                for i in range(4):
                    p = V((r.choice((-1, 1)) * r.uniform(0.6, 2.8), r.uniform(YP[k] + 0.3, YP[k + 1] - 0.3), FL + 0.002))
                    g.blob(p, r.uniform(0.03, 0.08), r.uniform(0.03, 0.07), r.uniform(0.02, 0.04), 5, 1, "Stone", r, 0.3)
            return g

        reg(f"P{k + 1}_Floor", "structure", floor, lambda k=k: [pbox(-NX, NX, YP[k], YP[k + 1], FL - 0.3, FL)], BIG)

    def water(lod):
        """Seawater channel that rises and falls with the tide (script)."""
        g = Geo()
        z = FL - 0.07
        g.face([V((-0.21, YP[0], z)), V((0.21, YP[0], z)), V((0.21, YP[4], z)), V((-0.21, YP[4], z))], "Water", (0, 0, 1))
        return g

    reg("P_Water", "water", water, bbox_phys(water), STD, role="tide")

    for j in range(5):
        def beam(lod, j=j):
            g = Geo()
            yj = YP[j]
            bx(g, -NX - 0.25, NX + 0.25, yj - 0.17, yj + 0.17, 6.30, 6.74, "Wood", 0.03 if lod == 0 else 0,
               skip=("-x", "+x", "+z") if lod >= 2 else ())
            if lod <= 1:
                for s in (-1, 1):
                    g.prism([(0.0, 5.7), (0.46, 6.18), (0.46, 6.30), (0.0, 6.30)],
                            Frame((s * NX, 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)), yj - 0.23, yj + 0.23, "Stone")
            if lod == 0:
                for s in (-1, 1):
                    for xx in (s * (NX - 0.55), s * (NX - 0.75)):
                        bx(g, xx - 0.035, xx + 0.035, yj - 0.18, yj + 0.18, 6.29, 6.75, "Iron")
            return g

        reg(f"T{j}_Beam", "deco", beam, bbox_phys(beam), BIG)

    def hanged_man(lod):
        """The warning at the entrance: an executed man hanging from the second beam, between butcher's hooks."""
        g = Geo()
        r = rng("ajusticiado")
        yj = YP[1]
        sk = skeleton("hanging", lod, r)
        g.extend(xf(sk, (0.9, yj, 3.4), rz=0.4))
        chain(g, [V((0.9, yj, 6.3)) - V((0, 0, t * 0.11)) for t in range(12)], 0.05, 0.03, 0.01, lod, r, -10)
        for xx in (-0.4, 2.0):
            top = V((xx, yj, 6.3))
            chain(g, [top - V((0, 0, t * 0.06)) for t in range(16)], 0.045, 0.028, 0.009, lod, r, -10)
            h = top - V((0, 0, 0.98))
            g.sweep([h, h - V((0, 0, 0.12)), h + V((0.06, 0, -0.2)), h + V((0.1, 0, -0.12))], 0.01, 4, "Iron")
        return g

    deco("P_Gibbet", hanged_man)

    for j in (1, 2, 3):
        hanging_lantern(f"T{j}_Lantern", V((-0.2 if j != 1 else -1.3, YP[j], 6.30)))
    for j in range(5):
        for s in (-1, 1):
            wall_torch(f"A{j}{'W' if s < 0 else 'E'}_Torch", (s * NX, YP[j], FL + 2.25), (-s, 0, 0))


# ================================================================== guardroom and gate
YF0, YF1 = -16.0, -15.2
YT0, YT1 = -18.0, -14.4
TX0, TX1 = 2.0, 6.0


def make_entrance():
    for s in (-1, 1):
        S = "W" if s < 0 else "E"
        X = lambda x, s=s: s * x
        inner = flipx(("-x",), s)[0]

        def front_wall(lod, s=s, X=X):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            sk = ("-z", flipx(("-x",), s)[0]) + (("+y",) if lod == 3 else ())
            bx(g, X(TX1), X(XO), YF0, YF1, zb, WT + (0.18 if lod else 0), "Stone", skip=sk)
            if lod == 0:
                bx(g, X(TX1), X(XO + 0.07), YF0 - 0.07, YF1 + 0.05, WT, WT + 0.18, "Stone", 0.03,
                   skip=(flipx(("-x",), s)[0],))
                g.prism([(YF0, ZB), (YF0 - 0.12, ZB), (YF0 - 0.12, FL + 0.35), (YF0, FL + 0.5)],
                        Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), *sorted((X(TX1), X(XO - 0.9))), "Stone")
            bx(g, X(9.2 - 0.45), X(9.2 + 0.45), YF0 - 0.6, YF0, zb, FL + 5.0, "Stone", 0.03 if lod == 0 else 0,
               skip=("-z", "+y"))
            if lod <= 1:
                g.prism([(YF0, FL + 5.0), (YF0 - 0.6, FL + 5.0), (YF0, FL + 6.3)],
                        Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), *sorted((X(9.2 - 0.45), X(9.2 + 0.45))),
                        "Stone")
            bx(g, X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, zb, FL + 5.4, "Stone", 0.03 if lod == 0 else 0,
               skip=("-z",))
            return g

        reg(f"G_Wall_{S}", "structure", front_wall,
            lambda X=X: [pbox(X(TX1), X(XO), YF0, YF1, ZB, WT + 0.18), pbox(X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, ZB,
                                                                          FL + 5.4),
                         pbox(X(8.75), X(9.65), YF0 - 0.6, YF0, ZB, FL + 5.0)], BIG)

        def lateral(lod, s=s, X=X, inner=inner):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(XI), X(XO), YF1, YP[0], zb, WT + 0.18, "Stone",
               skip=("-z", "+y", "-y") + ((inner,) if lod == 3 else ()))
            bx(g, X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, zb, FL + 5.6, "Stone", skip=("-z", inner))
            return g

        reg(f"V_Wall_{S}", "structure", lateral,
            lambda X=X: [pbox(X(XI), X(XO), YF1, YP[0], ZB, WT + 0.18),
                         pbox(X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, ZB, FL + 5.6)], BIG)

        def partition(lod, s=s, X=X):
            g = Geo()
            if lod == 3:
                bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, WT, WT + 0.18, "Stone",
                   skip=("-z", "-x", "+x", "+y"))
                return g
            bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT, "Stone", skip=("-z", "-x", "+x"))
            bx(g, X(NX + FT - 0.05), X(XI), YP[0] - PT - 0.06, YP[0] + PT + 0.06, WT, WT + 0.18, "Stone",
               0.03 if lod == 0 else 0)
            return g

        reg(f"V_Partition_{S}", "structure", partition,
            lambda X=X: [pbox(X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT + 0.18)], BIG)

        def gate_tower(lod, s=s, X=X):
            g = tower(lod, s, X, TX0, TX1, YT0, YT1)
            if lod <= 2:  # jambs of the two passage arches (they belong to the tower: their hull does not narrow the way)
                for (ya, yb_) in ((YT0, YT0 + 0.8), (YT1 - 0.8, YT1)):
                    bx(g, X(1.7), X(TX0), ya, yb_, ZB if lod <= 1 else FL, FL + 3.0, "Stone",
                       skip=("-z", flipx(("+x",), s)[0]))
            if lod == 0:  # pintles of the gate leaves (here, not on the arch: its hull would reach down to the floor)
                for z in (FL + 0.5, FL + 2.6):
                    bx(g, X(1.70), X(1.84), YT1, YT1 + 0.06, z - 0.05, z + 0.05, "Iron")
            return g

        reg(f"G_Tower_{S}", "structure", gate_tower,
            lambda X=X: [pbox(X(TX0), X(TX1), YT0, YT1, ZB, 10.6), pbox(X(TX0), X(TX1 + 0.35), YT0 - 0.35, YT1, ZB,
                                                                        FL + 0.5),
                         pbox(X(TX0), X(TX1 + 0.2), YT0 - 0.2, YT1, ZB, FL + 1.1),
                         pbox(X(1.7), X(TX0), YT0, YT0 + 0.8, ZB, FL + 3.0), pbox(X(1.7), X(TX0), YT1 - 0.8, YT1, ZB,
                                                                                  FL + 3.0)], BIG)

    wall_torch("A0W_Torch_Hall", (-7.7, YP[0] - PT, FL + 2.3), (0, -1, 0))
    wall_torch("A0E_Torch_Hall", (7.7, YP[0] - PT, FL + 2.3), (0, -1, 0))

    for i, (x0, x1) in enumerate(((-XI, -4.0), (-4.0, 4.0), (4.0, XI))):
        reg(f"V_Floor_{i + 1}", "structure", lambda lod, x0=x0, x1=x1, i=i: flagstones(f"vest-{i}", x0, x1, YF1, YP[0], lod),
            lambda x0=x0, x1=x1: [pbox(x0, x1, YF1, YP[0], FL - 0.3, FL)], BIG)

    def passage(lod):
        g = flagstones("paso", -TX0, TX0, YT0, YF1, lod)
        c = 0.02 if lod == 0 else 0
        bx(g, -3.0, 3.0, -19.2, YT0, -0.4, 0.2, "Stone", c, skip=("-z", "+y"))
        bx(g, -3.0, 3.0, -18.6, YT0, 0.2, FL, "Stone", c, skip=("-z", "+y"))
        return g

    reg("G_Stairs", "structure", passage,
        lambda: [pbox(-TX0, TX0, YT0, YF1, FL - 0.3, FL), pbox(-3.0, 3.0, -19.2, YT0, -0.4, 0.2),
                 pbox(-3.0, 3.0, -18.6, YT0, 0.2, FL)], BIG)

    def gate_head(lod):
        """Everything above the springing of the passage arches (its hull does not come down below 3.3 m)."""
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        sp, ra = 3.4, 0.62
        top = 9.6
        for fr_, spring in ((Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), FL + 2.9),
                            (Frame((0, YT1, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), FL + 3.1)):
            arch_wall(g, fr_, -1.7, 1.7, 0.0, sp, ra, spring, spring, top, 0.8, n_side, "Stone", skip_u0=True,
                      skip_u1=True, thr_top=None, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
            if lod == 0:
                voussoirs(g, fr_, 0.0, spring, sp, ra, 6, 0.6, 0.07, "Stone")
        # solid masonry above the jambs, all the way up
        for s in (-1, 1):
            for (ya, yb_) in ((YT0, YT0 + 0.8), (YT1 - 0.8, YT1)):
                if lod < 3:
                    bx(g, s * 1.7, s * TX0, ya, yb_, FL + 3.0, top, "Stone",
                       skip=("-z", "-y", "+y") if lod else ("-z",))
        if lod == 3:
            bx(g, -TX0, TX0, YT0, YT1, top, top + 1.0, "Stone", skip=("-z", "-x", "+x"))
            return g
        fr_v = Frame((0, YT0 + 0.8, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        pts = pointed_arch(2 * TX0, 0.62, n_side)
        for i in range(len(pts) - 1):
            (a0, b0), (a1, b1) = pts[i], pts[i + 1]
            q = [fr_v.p(a0, FL + 3.0 + b0, 0), fr_v.p(a1, FL + 3.0 + b1, 0),
                 fr_v.p(a1, FL + 3.0 + b1, -(YF1 - YT0 - 0.8)), fr_v.p(a0, FL + 3.0 + b0, -(YF1 - YT0 - 0.8))]
            mid = sum(q, V()) / 4
            g.face(q, "Stone", V((0, mid.y, FL + 1.0)) - mid)
        tp = pointed_arch(sp, ra, n_side)
        g.prism([(u, FL + 3.1 + v) for u, v in tp], Frame((0, YT1 - 0.35, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
                -0.06, 0.06, "Wood")
        bx(g, -TX0, TX0, YT0 - 0.3, YT0 + 0.05, top, top + 0.95, "Stone", 0.03 if lod == 0 else 0)
        bx(g, -TX0, TX0, YF1 - 0.35, YF1, top, top + 0.95, "Stone", 0.03 if lod == 0 else 0)
        bx(g, -TX0, TX0, YT0 + 0.05, YF1 - 0.35, top - 0.02, top, "Stone")
        if lod == 0:
            hood(g, Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, FL + 2.9, sp, ra, 12, 0.74, 0.14,
                 0.12, "Stone")
            for i in range(6):
                xx = -TX0 + 0.35 + i * (2 * TX0 - 0.7) / 5
                g.prism([(0.0, top - 0.42), (0.0, top), (0.3, top), (0.3, top - 0.16)],
                        Frame((0, YT0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0)), xx - 0.11, xx + 0.11, "Stone")
            # the lord's coat of arms with two skulls nailed below it
            g.prism([(-0.42, 7.0), (0.42, 7.0), (0.42, 7.75), (0.0, 7.95), (-0.42, 7.75)],
                    Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.09, "Stone", caps=(False, True))
            r = rng("escudo")
            for sx in (-0.75, 0.75):
                g.cyl(V((sx, YT0, 6.75)), V((sx, YT0 - 0.25, 6.75)), 0.012, 4, "Iron")
                skull(g, V((sx, YT0 - 0.16, 6.75)), lod, r, V((0, -1, 0)))
        return g

    reg("G_Arch", "structure", gate_head,
        lambda: [pbox(-TX0, TX0, YT0, YT0 + 0.8, FL + 5.0, 9.6), pbox(-TX0, TX0, YT1 - 0.8, YT1, FL + 5.2, 9.6),
                 pbox(-TX0, TX0, YT0 + 0.8, YT1 - 0.8, FL + 5.45, 9.6)], BIG)

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
                g.cyl(V((x, (y0 + y1) / 2, zb)), V((x, (y0 + y1) / 2, FL)), 0.05, 4, "Iron", caps=(True, False), r1=0.0,
                      phase=math.pi / 4)
        for j in range(nh):
            z = zb + 0.25 + (zt - zb - 0.35) * j / (nh - 1)
            bx(g, x0, x1, y0 - 0.04, y0, z - 0.045, z + 0.045, "Wood", 0.01 if lod == 0 else 0,
               skip=() if lod == 0 else ("-x", "+x", "+y"))
        return g

    reg("G_Portcullis", "door", portcullis, bbox_phys(portcullis), BIG, role="portcullis")
    for s in (-1, 1):
        S = "W" if s < 0 else "E"
        reg(f"G_Leaf_{S}", "door", lambda lod, s=s: gate_leaf(lod, s, YT1),
            lambda s=s: [pbox(s * 0.005, s * 1.76, YT1 + 0.01, YT1 + 0.13, FL + 0.03, FL + 3.08)], role="gate")

    def winch(lod):
        """Portcullis winch and the press-gang bell, in the hall next to the west tower."""
        g = Geo()
        c = V((-4.2, YT1 + 0.55, FL + 1.0))
        q = 0.015 if lod == 0 else 0
        for sx in (-0.55, 0.55):
            bx(g, c.x + sx - 0.08, c.x + sx + 0.08, c.y - 0.2, c.y + 0.2, FL, FL + 1.3, "Wood", q)
        g.cyl(c - V((0.5, 0, 0)), c + V((0.5, 0, 0)), 0.17, n_(14, lod, 6), "Wood")
        for sx in (-1, 1):
            wheel(g, c + V((sx * 0.68, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.38, lod, 6, handles=True)
        if lod <= 1:
            for t in range(-3, 4):
                g.link(c + V((t * 0.11, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.185, 0.185, 0.013, 12, 3, "Iron")
            r = rng("torno-rastrillo")
            chain(g, [(c + V((0, -0.05, 0.18))).lerp(V((-1.2, YT1 + 0.02, 4.2)), t / 20) for t in range(21)], 0.05, 0.03,
                  0.011, lod, r, -10)
        # press-gang bell
        b = V((-5.6, YT1 + 0.55, FL))
        bx(g, b.x - 0.08, b.x + 0.08, b.y - 0.08, b.y + 0.08, FL, FL + 2.6, "Wood", q)
        bx(g, b.x - 0.08, b.x + 0.7, b.y - 0.07, b.y + 0.07, FL + 2.5, FL + 2.64, "Wood", q)
        bell_c = V((b.x + 0.55, b.y, FL + 2.5))
        prof = [(0.0, 0.05), (-0.06, 0.12), (-0.22, 0.15), (-0.38, 0.22), (-0.42, 0.25)]
        nn = n_(14, lod, 6)
        rings = [[bell_c + V((math.cos(2 * math.pi * j / nn) * rr, math.sin(2 * math.pi * j / nn) * rr, h))
                  for j in range(nn)] for h, rr in prof]
        for i in range(len(rings) - 1):
            for j in range(nn):
                j2 = (j + 1) % nn
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Iron", bell_c - V((0, 0, 0.2)))
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Iron", bell_c + V((0, 0, 3)))
        if lod <= 1:
            g.sweep([bell_c - V((0, 0, 0.05)), bell_c - V((0, 0, 0.38))], 0.02, 4, "Iron")
            g.sweep([bell_c - V((0, 0, 0.38)), bell_c + V((0.05, 0, -1.4))], 0.012, 3, "Straw")
        return g

    sitter("G_Winch", winch, "winch", kind="furniture")
    SITS["G_Winch"] = (V((-4.2, YT1 + 0.0, FL + 1.0)), 90, "pit_winch", "stand")

    def table(lod):
        """Guards' table: dice, jugs, a dagger stuck in it and the Sentence Board above it."""
        g = Geo()
        r = rng("mesa")
        c = V((6.6, -13.4, FL))
        q = 0.02 if lod == 0 else 0
        bx(g, c.x - 1.0, c.x + 1.0, c.y - 0.45, c.y + 0.45, FL + 0.74, FL + 0.82, "Wood", q)
        for sx in (-0.8, 0.8):
            bx(g, c.x + sx - 0.06, c.x + sx + 0.06, c.y - 0.35, c.y + 0.35, FL, FL + 0.74, "Wood", q)
        for sy in (-0.8, 0.8):
            bx(g, c.x - 0.95, c.x + 0.95, c.y + sy - 0.15, c.y + sy + 0.15, FL + 0.42, FL + 0.48, "Wood", q)
            for sx in (-0.8, 0.8):
                bx(g, c.x + sx - 0.05, c.x + sx + 0.05, c.y + sy - 0.1, c.y + sy + 0.1, FL, FL + 0.42, "Wood")
        if lod <= 1:
            top = FL + 0.82
            for i in range(3):  # jugs
                p = V((c.x - 0.6 + i * 0.5 + r.uniform(-0.1, 0.1), c.y + r.uniform(-0.25, 0.25), top))
                g.cyl(p, p + V((0, 0, 0.16)), 0.05, n_(10, lod, 5), "Wood", caps=(True, False), r1=0.055)
                if lod == 0:
                    g.link(p + V((0.065, 0, 0.08)), V((0, 0, 1)), V((1, 0, 0)), 0.04, 0.03, 0.008, 8, 3, "Wood")
            for i in range(2):  # dice
                p = V((c.x + 0.2 + i * 0.08, c.y + 0.1, top))
                g.bbox(p, p + V((0.03, 0.03, 0.03)), "Bone", 0.004 if lod == 0 else 0)
            # dagger stuck in the table
            dp = V((c.x + 0.6, c.y - 0.1, top))
            g.prism([(-0.015, 0.0), (0.015, 0.0), (0.0, -0.2)], Frame(dp + V((0, 0, 0.2)), (1, 0, 0), (0, 0, 1),
                                                                      (0, 1, 0)), -0.003, 0.003, "Iron")
            g.cyl(dp + V((0, 0, 0.2)), dp + V((0, 0, 0.32)), 0.014, 6, "Cloth")
            bx(g, dp.x - 0.05, dp.x + 0.05, dp.y - 0.008, dp.y + 0.008, dp.z + 0.19, dp.z + 0.21, "Iron")
            # candle
            g.cyl(V((c.x - 0.9, c.y + 0.3, top)), V((c.x - 0.9, c.y + 0.3, top + 0.12)), 0.03, 6, "Straw")
            g.flame(V((c.x - 0.9, c.y + 0.3, top + 0.12)), 0.06, 0.012, 4, "Flame", r)
        return g

    sitter("V_Table", table, "table")
    SITS["V_Table"] = (V((6.6, -13.4 - 0.8, FL + 0.9)), 90, "pit_guard", "sit")

    def props_w(lod):
        g = Geo()
        r = rng("vest-o")
        wy = YF1  # inner face of the front wall (faces north)
        # key board: one key per room
        bx(g, -9.9, -8.5, wy, wy + 0.05, FL + 1.5, FL + 2.3, "Wood", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for i in range(8):
                x = -9.75 + i * 0.16
                g.cyl(V((x, wy + 0.05, FL + 2.15)), V((x, wy + 0.1, FL + 2.15)), 0.007, 4, "Iron")
                key = [V((x, wy + 0.09, FL + 2.12)), V((x, wy + 0.09, FL + 1.85))]
                g.sweep(key, 0.008, 3, "Iron")
                g.link(V((x, wy + 0.09, FL + 2.14)), V((0, 0, 1)), V((1, 0, 0)), 0.025, 0.025, 0.005, 8, 3, "Iron")
                bx(g, x, x + 0.04, wy + 0.085, wy + 0.095, FL + 1.85, FL + 1.9, "Iron")
        # weapon rack: pikes and cutlasses
        bx(g, -11.0, -10.2, wy + 0.05, wy + 0.35, FL, FL + 0.12, "Wood")
        bx(g, -11.0, -10.2, wy + 0.05, wy + 0.12, FL + 1.6, FL + 1.7, "Wood")
        for i in range(3 if lod <= 1 else 1):
            x = -10.9 + i * 0.3
            g.cyl(V((x, wy + 0.2, FL + 0.12)), V((x, wy + 0.1, FL + 2.5)), 0.018, 5, "Wood")
            g.prism([(-0.035, 0.0), (0.035, 0.0), (0.0, 0.3)], Frame(V((x, wy + 0.1, FL + 2.5)), (1, 0, 0), (0, 0, 1),
                                                                     (0, 1, 0)), -0.005, 0.005, "Iron")
        # anchor from a captured ship, leaning on the wall, with its chain
        anc = Geo()
        anc.cyl(V((0, 0, 0.25)), V((0, 0, 2.1)), 0.06, n_(8, lod, 4), "Iron")
        arc = [V((math.sin(a) * 0.65, 0, 0.25 + 0.65 - math.cos(a) * 0.65)) for a in [-1.3 + i * 0.325 for i in range(9)]]
        anc.sweep(arc, 0.055, n_(8, lod, 4), "Iron")
        for e in (arc[0], arc[-1]):
            sg = 1 if e.x > 0 else -1
            anc.prism([(0, 0), (sg * 0.2, 0.18), (sg * 0.02, 0.32)], Frame(e - V((0, 0, 0.05)), (1, 0, 0), (0, 0, 1),
                                                                           (0, 1, 0)), -0.02, 0.02, "Iron")
        anc.cyl(V((-0.55, 0, 1.85)), V((0.55, 0, 1.85)), 0.05, 6, "Wood")
        anc.link(V((0, 0, 2.22)), V((0, 0, 1)), V((1, 0, 0)), 0.12, 0.12, 0.025, 12, 4, "Iron")
        g.extend(xf(anc, (-6.9, wy + 0.25, FL), rx=0.22))
        return g

    deco("V_Props_W", props_w, "board")

    def basket(lod):
        """Laundry basket: the guards' dirty underwear, ready to be thrown into the kennel."""
        g = Geo()
        r = rng("cesta")
        c = V((9.6, -13.0, FL))
        nn = n_(16, lod, 6)
        g.cyl(c, c + V((0, 0, 0.6)), 0.32, nn, "Straw", caps=(True, False), r1=0.4)
        g.cyl(c + V((0, 0, 0.58)), c + V((0, 0, 0.12)), 0.385, nn, "Straw", caps=(False, False), r1=0.315)
        g.link(c + V((0, 0, 0.6)), V((1, 0, 0)), V((0, 1, 0)), 0.4, 0.4, 0.025, nn, 3, "Straw")
        g.blob(c + V((0, 0, 0.5)), 0.36, 0.36, 0.2, n_(10, lod, 5), 2 if lod == 0 else 1, "Cloth", r, 0.35)
        if lod <= 1:
            for i in range(6):
                a = r.uniform(0, 6.28)
                p = c + V((math.cos(a) * r.uniform(0.45, 0.7), math.sin(a) * r.uniform(0.45, 0.7), 0.02))
                garment(g, p, r.uniform(0, 6.28), ("breeches", "loincloth", "shirt")[i % 3], r, lod)
            garment(g, c + V((0.1, 0.0, 0.66)), 0.5, "breeches", r, lod)
        return g

    deco("V_Basket", basket, "basket")


# ================================================================== throne room
YN0, YB0, YB1 = YP[4] + PT, 15.2, 16.0



def banner(g, x0, lod):
    """The lord's tattered banner, hanging from an iron bar over the back wall."""
    top = 6.6
    g.cyl(V((x0 - 0.75, YB0 - 0.15, top)), V((x0 + 0.75, YB0 - 0.15, top)), 0.03, 6, "Iron")
    for sx in (-0.7, 0.7):
        g.cyl(V((x0 + sx, YB0, top)), V((x0 + sx, YB0 - 0.18, top)), 0.02, 4, "Iron")
    nx, nz = (6, 10) if lod == 0 else (2, 3)
    w, h = 1.3, 3.4
    grid = []
    for i in range(nx + 1):
        row = []
        for j in range(nz + 1):
            u = -w / 2 + w * i / nx
            zz = top - 0.05 - h * j / nz
            if j == nz:
                zz += (0.25 if i % 2 else 0.0) + (0.1 if i in (0, nx) else 0)
            yy = YB0 - 0.15 - 0.04 * math.sin(i * 1.3 + j * 0.9)
            row.append(V((x0 + u, yy, zz)))
        grid.append(row)
    for i in range(nx):
        for j in range(nz):
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
            g.face(q, "Cloth", (0, -1, 0))
            g.face([p + V((0, 0.006, 0)) for p in q], "Cloth", (0, 1, 0))


def make_throne():
    for s in (-1, 1):
        S = "W" if s < 0 else "E"
        X = lambda x, s=s: s * x
        inner = flipx(("-x",), s)[0]

        def lateral(lod, s=s, X=X, inner=inner):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(XI), X(XO), YP[4], YB1, zb, WT + 0.18, "Stone", skip=("-z", "-y") + ((inner,) if lod == 3 else ()))
            bx(g, X(XO), X(XB), YB1 - 0.9, YB1, zb, FL + 5.4, "Stone", skip=("-z", inner))
            return g

        reg(f"N_Wall_{S}", "structure", lateral,
            lambda X=X: [pbox(X(XI), X(XO), YP[4], YB1, ZB, WT + 0.18), pbox(X(XO), X(XB), YB1 - 0.9, YB1, ZB, FL + 5.4)],
            BIG)

        def back(lod, s=s, X=X):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(4.5), X(XI), YB0, YB1, zb, WT + (0 if lod == 0 else 0.18), "Stone",
               skip=("-z", "-x", "+x") + (("-y",) if lod == 3 else ()))
            if lod == 0:
                bx(g, X(4.5), X(XI), YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Stone", 0.03, skip=("-x", "+x"))
            if lod <= 1:
                banner(g, s * 6.4, lod)
            return g

        reg(f"N_Back_{S}", "structure", back, lambda X=X: [pbox(X(4.5), X(XI), YB0, YB1, ZB, WT + 0.18)], BIG)

    def back_c(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        fr = Frame((0, YB0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        spr = DAIS + 2.2
        arch_wall(g, fr, -4.5, 4.5, 0.0, 3.4, 0.6, spr, DAIS, WT, 0.5, n_side, "Stone", skip_u0=True, skip_u1=True,
                  thr_top=None, front_only=(lod == 3), back=False, top=(lod == 0))
        bx(g, -4.5, 4.5, YB0 + 0.5, YB1, ZB if lod <= 1 else FL, WT + (0 if lod == 0 else 0.18), "Stone",
           skip=("-z", "-x", "+x") + (("-y",) if lod == 3 else ()))
        bx(g, -1.7, 1.7, YB0, YB0 + 0.5, ZB, DAIS, "Stone", skip=("-z", "-x", "+x", "+y", "-y") if lod else ("-z",))
        if lod == 0:
            bx(g, -4.5, 4.5, YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Stone", 0.03, skip=("-x", "+x"))
            voussoirs(g, fr, 0.0, spr, 3.4, 0.6, 6, 0.5, 0.07, "Stone")
            hood(g, fr, 0.0, spr, 3.4, 0.6, 12, 0.62, 0.14, 0.12, "Stone")
            # the helm of the lord's ship, inside the niche
            wheel(g, V((0, YB0 + 0.35, spr + 0.6)), V((0, 1, 0)), V((0, 0, 1)), 0.85, lod, 8, handles=True)
            g.cyl(V((0, YB0 + 0.5, spr + 0.6)), V((0, YB0 + 0.3, spr + 0.6)), 0.06, 8, "Iron")
        return g

    reg("N_Back_C", "structure", back_c,
        lambda: [pbox(-4.5, -1.7, YB0, YB1, ZB, WT + 0.18), pbox(1.7, 4.5, YB0, YB1, ZB, WT + 0.18),
                 pbox(-1.7, 1.7, YB0 + 0.5, YB1, ZB, WT + 0.18), pbox(-1.7, 1.7, YB0, YB0 + 0.5, ZB, DAIS),
                 pbox(-1.7, 1.7, YB0, YB0 + 0.5, DAIS + 2.2 + 1.85, WT + 0.18)], BIG)

    for i, (x0, x1) in enumerate(((-XI, -4.0), (-4.0, 4.0), (4.0, XI))):
        reg(f"N_Floor_{i + 1}", "structure", lambda lod, x0=x0, x1=x1, i=i: flagstones(f"norte-{i}", x0, x1, YP[4], YB0, lod),
            lambda x0=x0, x1=x1: [pbox(x0, x1, YP[4], YB0, FL - 0.3, FL)], BIG)

    # dais stepped on three sides: its convex hull is a ramp you can walk up and down
    def dais(lod):
        g = Geo()
        q = 0.025 if lod == 0 else 0
        steps = 4 if lod <= 1 else 1
        for i in range(steps):
            h = FL + (DAIS - FL) * (i + 1) / steps
            grow = 0.43 * (steps - 1 - i) * (4 / steps)
            bx(g, -3.0 - grow, 3.0 + grow, 12.6 - grow, YB0, FL - 0.1, h, "Stone", q, skip=("-z", "+y"))
        return g

    def dais_phys():
        pts = [V((-4.6, 11.0, FL)), V((4.6, 11.0, FL)), V((-4.6, YB0, FL)), V((4.6, YB0, FL)),
               V((-3.0, 12.6, DAIS)), V((3.0, 12.6, DAIS)), V((-3.0, YB0, DAIS)), V((3.0, YB0, DAIS))]
        return [("HULL", pts)]   # "HULL" marker is read by build_pit.phys_geo: keep it in sync

    reg("N_Dais", "structure", dais, dais_phys, BIG)

    def throne(lod):
        g = Geo()
        r = rng("trono")
        c = V((0, 14.55, DAIS))
        q = 0.02 if lod == 0 else 0
        bx(g, -0.9, 0.9, c.y - 0.6, c.y + 0.55, DAIS, DAIS + 0.2, "Stone", q)          # plinth
        bx(g, -0.65, 0.65, c.y - 0.42, c.y + 0.35, DAIS + 0.2, DAIS + 0.62, "Wood", q)  # seat
        bx(g, -0.75, 0.75, c.y + 0.3, c.y + 0.48, DAIS + 0.2, DAIS + 2.9, "Wood", q)    # high back
        for sx in (-1, 1):  # arms with a ring
            bx(g, sx * 0.62 - 0.1, sx * 0.62 + 0.1, c.y - 0.45, c.y + 0.35, DAIS + 0.62, DAIS + 0.95, "Wood", q)
            bx(g, sx * 0.62 - 0.12, sx * 0.62 + 0.12, c.y - 0.55, c.y + 0.4, DAIS + 0.95, DAIS + 1.02, "Wood", q)
            if lod <= 1:
                g.link(V((sx * 0.75, c.y - 0.45, DAIS + 0.88)), V((0, 0, 1)), V((0, 1, 0)), 0.06, 0.06, 0.014, 10, 4,
                       "Iron")
                chains_from(g, V((sx * 0.75, c.y - 0.45, DAIS + 0.82)), V((sx * 0.95, c.y - 0.8, DAIS + 0.03)), lod, 0.1)
            # side posts of the back, topped with skulls
            bx(g, sx * 0.75 - 0.08, sx * 0.75 + 0.08, c.y + 0.28, c.y + 0.5, DAIS + 0.2, DAIS + 3.1, "Wood", q)
            skull(g, V((sx * 0.75, c.y + 0.39, DAIS + 3.22)), lod, r, V((0, -1, 0)))
        if lod <= 1:
            # crown of iron spikes, and bands
            for i in range(9):
                x = -0.6 + i * 0.15
                h = 0.25 + 0.25 * (1 - abs(i - 4) / 4)
                g.cyl(V((x, c.y + 0.39, DAIS + 2.9)), V((x, c.y + 0.39, DAIS + 2.9 + h)), 0.025, 4, "Iron",
                      caps=(False, False), r1=0.0)
            for z in (DAIS + 0.9, DAIS + 2.1):
                bx(g, -0.77, 0.77, c.y + 0.28, c.y + 0.5, z, z + 0.06, "Iron")
            # hide thrown over the seat, and a cushion
            g.blob(V((0, c.y - 0.05, DAIS + 0.62)), 0.62, 0.45, 0.07, n_(14, lod, 6), 2, "Cloth", r, 0.2)
            pts = [V((x, c.y + 0.28, DAIS + 0.62 + 0.9 * (1 - abs(x) / 0.6))) for x in (-0.5, 0, 0.5)]
            g.blob(V((0, c.y + 0.26, DAIS + 1.1)), 0.55, 0.06, 0.5, n_(12, lod, 6), 2, "Cloth", r, 0.15,
                   flat_bottom=False)
        return g

    sitter("N_Throne", throne, "throne", lod_map=SMALL)
    SITS["N_Throne"] = (V((0, 14.5, DAIS + 1.05)), -90, "pit_lord", "sit")

    def kneeling_stone(lod):
        g = Geo()
        r = rng("piedra")
        c = V((0, 13.15, DAIS))
        g.bbox(c - V((0.45, 0.3, 0)), c + V((0.45, 0.3, 0.28)), "Stone", 0.06 if lod == 0 else 0)
        if lod <= 1:
            g.link(c + V((0, -0.3, 0.2)), V((0, 0, 1)), V((1, 0, 0)), 0.08, 0.08, 0.018, 12, 4, "Iron")
            chains_from(g, c + V((0, -0.32, 0.12)), c + V((0.3, -0.75, 0.02)), lod, 0.03)
            collar(g, c + V((0.42, -0.85, 0.02)), 0.13, 0.02, lod)
        return g

    sitter("N_Kneeling_Stone", kneeling_stone, "kneeling_stone")
    SITS["N_Kneeling_Stone"] = (V((0, 13.15 - 0.55, DAIS + 0.45)), 90, "pit_kneel", "sit_ground_constrained")

    for s in (-1, 1):
        def braz(lod, s=s):
            return brazier(V((s * 2.3, 14.0, DAIS)), lod)
        reg(f"N_Brazier_{'W' if s < 0 else 'E'}", "light", braz, bbox_phys(braz), SMALL, fire=True, role="brazier")



    for s in (-1, 1):
        S = "W" if s < 0 else "E"

        def props(lod, s=s):
            g = Geo()
            r = rng(f"trono-atrezzo-{s}")
            X = lambda x: s * x
            # pike with a skull on each side of the steps
            p = V((X(10.9), 14.8, FL))
            g.cyl(p, p + V((0, 0, 2.4)), 0.025, 5, "Iron", caps=(True, False), r1=0.012)
            bx(g, p.x - 0.18, p.x + 0.18, p.y - 0.18, p.y + 0.18, FL, FL + 0.12, "Stone", 0.02 if lod == 0 else 0)
            skull(g, p + V((0, 0, 2.3)), lod, r, V((-s * 0.5, -1, 0)))
            if s < 0:   # hay bales
                for (x, y, lvl, a) in ((-8.6, 14.4, 0, 0.1), (-7.4, 14.4, 0, -0.05), (-8.0, 14.45, 1, 0.08),
                                       (-9.9, 13.2, 0, 1.45)):
                    L, W, H = 1.05, 0.52, 0.45
                    z0 = FL + lvl * H
                    cs, sn = math.cos(a), math.sin(a)
                    poly = [(x + cx * cs - cy * sn, y + cx * sn + cy * cs) for cx, cy in
                            ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2))]
                    g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), z0, z0 + H, "Straw",
                            caps=(lvl > 0, True))
            else:       # loot chest, half open, and rum barrels
                cc = V((8.0, 14.6, FL))
                bx(g, cc.x - 0.5, cc.x + 0.5, cc.y - 0.3, cc.y + 0.3, FL, FL + 0.45, "Wood", 0.02 if lod == 0 else 0)
                lid = Geo()
                lid.box(V((-0.5, 0, 0)), V((0.5, 0.6, 0.08)), "Wood")
                g.extend(xf(lid, (cc.x, cc.y + 0.3, FL + 0.45), rx=1.15))
                if lod <= 1:
                    g.blob(cc + V((0, 0, 0.42)), 0.42, 0.24, 0.1, 10, 2, "Iron", r, 0.25)  # coins
                    for z in (0.1, 0.35):
                        bx(g, cc.x - 0.51, cc.x + 0.51, cc.y - 0.31, cc.y + 0.31, FL + z, FL + z + 0.04, "Iron")
                for (x, y) in ((9.7, 14.5), (10.4, 14.65), (10.0, 13.85)):
                    nn = n_(14, lod, 6)
                    prof = [(0.0, 0.27), (0.45, 0.33), (0.9, 0.27)]
                    rings = [[V((x + math.cos(2 * math.pi * j / nn) * rr, y + math.sin(2 * math.pi * j / nn) * rr,
                                 FL + h)) for j in range(nn)] for h, rr in prof]
                    for i in range(len(rings) - 1):
                        for j in range(nn):
                            j2 = (j + 1) % nn
                            g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Wood",
                                     V((x, y, FL + 0.45)))
                    g.face(rings[-1], "Wood", (0, 0, 1))
            return g

        deco(f"N_Props_{S}", props)


def build_all():
    P.PIECES.clear()
    SITS.clear()
    for s in (-1, 1):
        make_piers(s)
        for k in range(4):
            make_head(s, k)
            make_door(s, k)
    for k in range(4):
        make_room_shell(-1, k, k, ROOMS[(-1, k)][0], ROOMS[(-1, k)][1])
    make_room_shell(1, 0, 1, "C05", "The Kennel", roof="roof")
    make_room_shell(1, 2, 2, "C07", "The Cages")
    make_room_shell(1, 3, 3, "C08", "The Mast")
    make_press_gang()
    make_rack()
    make_stocks()
    make_cistern()
    make_kennel()
    make_cages()
    make_mast()
    make_yard()
    make_entrance()
    make_throne()
    return P.PIECES

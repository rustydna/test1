"""Story details: cells_east. C05+C06 the Kennel, C07 the Cages, C08 the Mast.

Decorators add geometry INSIDE each piece's bounding box; HIGH only. See story/__init__.py.
"""

import math

from mathutils import Matrix, Vector

from . import decorates

V = Vector


# ---------------------------------------------------------------- helpers

def _rng(seed):
    import random
    return random.Random(seed)


def _tile(g, p0, u, v, mat, out):
    """Little flat quad for a stain, carving, plate, etc. p0 is one corner."""
    a = V(p0)
    b = a + V(u)
    c = a + V(u) + V(v)
    d = a + V(v)
    g.face([a, b, c, d], mat, out)


def _box(g, mn, mx, mat, skip=()):
    mn = V(mn); mx = V(mx)
    mn, mx = V((min(mn.x, mx.x), min(mn.y, mx.y), min(mn.z, mx.z))), \
             V((max(mn.x, mx.x), max(mn.y, mx.y), max(mn.z, mx.z)))
    g.box(mn, mx, mat, skip)


def _plate(g, c, u, v, t, out, mat):
    """A thin plaque: c is the OUTER-face centre; u,v in-plane half axes; t thickness inward."""
    c = V(c); u = V(u); v = V(v); n = V(out).normalized()
    o = c - n * t
    pts_out = [c - u - v, c + u - v, c + u + v, c - u + v]
    pts_in = [p - n * t for p in pts_out]
    g.face(pts_out, mat, n)
    # four side strips
    for i in range(4):
        j = (i + 1) % 4
        g.face([pts_in[i], pts_in[j], pts_out[j], pts_out[i]], mat, (pts_out[i] + pts_out[j]) / 2 - o)


def _carve_strokes(g, c, u, v, rows, cols, mat, out, size=0.012, stroke=0.004):
    """A grid of little incised strokes (tally-mark look) on a surface. c = centre of the panel."""
    c = V(c); u = V(u).normalized(); v = V(v).normalized(); n = V(out).normalized()
    pu = _rng("strokes")
    for i in range(rows):
        for j in range(cols):
            x = (i - rows / 2 + 0.5) * (size * 2.5)
            y = (j - cols / 2 + 0.5) * (size * 2.0)
            p = c + u * x + v * y
            a = p - u * stroke - v * size
            b = p + u * stroke - v * size
            d = p + u * stroke + v * size
            e = p - u * stroke + v * size
            # tiny recessed quad: push IN along -n
            depth = n * -0.004
            g.face([a + depth, e + depth, d + depth, b + depth], mat, n)


def _light_well_grate(g, cx, cy, zc, half, mat="Iron"):
    """Iron grate set into the underside of the vault crown. Everything stays BELOW zc."""
    rim = half + 0.03
    # thin stone frame hanging from the vault (one flat ring quad per side)
    for u0, v0, u1, v1 in ((-rim, -rim, rim, -half),
                            (-rim, half, rim, rim),
                            (-rim, -half, -half, half),
                            (half, -half, rim, half)):
        g.face([V((cx + u0, cy + v0, zc - 0.005)),
                V((cx + u1, cy + v0, zc - 0.005)),
                V((cx + u1, cy + v1, zc - 0.005)),
                V((cx + u0, cy + v1, zc - 0.005))], "Stone", (0, 0, -1))
    # iron bars across the opening (both directions), minimal
    nb = 3
    for i in range(nb):
        t = -half + (i + 1) * (2 * half) / (nb + 1)
        g.cyl(V((cx - half, cy + t, zc - 0.015)),
              V((cx + half, cy + t, zc - 0.015)), 0.012, 4, mat, caps=(False, False))
        g.cyl(V((cx + t, cy - half, zc - 0.028)),
              V((cx + t, cy + half, zc - 0.028)), 0.012, 4, mat, caps=(False, False))


# ================================================================== C07_Vault (light well)

@decorates("C07_Vault")
def c07_vault(g, lod):
    if lod > 0:
        if lod == 1:
            cx, cy = 7.7, 2.875
            g.box(V((cx - 0.3, cy - 0.3, 7.12)), V((cx + 0.3, cy + 0.3, 7.15)), "Iron", skip=("+z",))
        return
    _light_well_grate(g, 7.7, 2.875, 7.17, 0.3)
    # gulls' nest on north-east springer ledge
    r = _rng("c07-nest")
    cnest = V((11.2, 5.05, 4.45))
    # straw ring
    nring = 14
    for i in range(nring):
        a = 2 * math.pi * i / nring
        p = cnest + V((math.cos(a) * 0.18, math.sin(a) * 0.18, 0))
        g.cyl(p, p + V((0, 0, 0.07)), 0.012, 3, "Straw")
    g.blob(cnest + V((0, 0, 0.02)), 0.18, 0.18, 0.04, 10, 2, "Straw", r, 0.3)
    # a couple of fish bones on top
    for k in range(3):
        a = r.uniform(0, 6.28)
        p = cnest + V((math.cos(a) * 0.08, math.sin(a) * 0.08, 0.055))
        d = V((math.cos(a + 1.3), math.sin(a + 1.3), 0)) * 0.08
        g.cyl(p - d, p + d, 0.006, 3, "Bone")


# ================================================================== C08_Vault (light well)

@decorates("C08_Vault")
def c08_vault(g, lod):
    if lod > 0:
        if lod == 1:
            cx, cy = 7.7, 8.625
            g.box(V((cx - 0.3, cy - 0.3, 7.12)), V((cx + 0.3, cy + 0.3, 7.15)), "Iron", skip=("+z",))
        return
    _light_well_grate(g, 7.7, 8.625, 7.17, 0.3)


# ================================================================== C05_Kennel_1 (Old Fetch)

@decorates("C05_Kennel_1")
def c05_kennel_1(g, lod):
    """Old Fetch's kennel. Tally on the front south post, Crown name plate GRIP."""
    if lod > 0:
        return
    r = _rng("kennel1-fetch")
    cx, yc = 10.595, -9.885
    # Crown brass plate on the front face of the kennel (front = -x face, nameplate at x~10.035..10.075)
    # Place a thin iron plaque on the WOODEN nameplate's lower edge; keep inside bbox (x_min=10.04).
    plate_x = 10.055
    g.box(V((plate_x - 0.004, yc - 0.18, 1.2)),
          V((plate_x, yc + 0.18, 1.26)), "Iron", skip=("+x",))
    # Front south post axis x~10.055, y~-10.635. Tally strokes on the OUTER (-x) face of the post:
    # a few thin iron grooves standing in for the hundreds of carved marks.
    px = 10.051
    for i in range(14):
        zz = 0.45 + i * 0.034
        g.cyl(V((px, yc - 0.72, zz)), V((px, yc - 0.57, zz)), 0.002, 3, "Iron")
    # a soup-bone card shard hidden in the straw
    g.box(V((cx - 0.1, yc - 0.3, 0.42)), V((cx - 0.07, yc - 0.22, 0.43)), "Bone")
    # a small personal treasure: a bent iron ring hidden under the straw
    g.link(V((cx + 0.15, yc + 0.1, 0.44)), V((1, 0, 0)), V((0, 1, 0)), 0.04, 0.04, 0.006, 10, 3, "Iron")


# ================================================================== C05_Kennel_2 (middle, HOLDFAST)

@decorates("C05_Kennel_2")
def c05_kennel_2(g, lod):
    if lod > 0:
        return
    yc = -5.835
    plate_x = 10.055
    g.box(V((plate_x - 0.004, yc - 0.18, 1.2)),
          V((plate_x, yc + 0.18, 1.26)), "Iron", skip=("+x",))
    # Ormond's compass rose incised in the straw-worn floor planking of the kennel: a tiny bone chip
    g.box(V((10.5, yc - 0.1, 0.42)), V((10.56, yc - 0.04, 0.428)), "Bone")


# ================================================================== C05_Kennel_3 (SORROW / SEAL)

@decorates("C05_Kennel_3")
def c05_kennel_3(g, lod):
    if lod > 0:
        return
    yc = -1.785
    plate_x = 10.055
    g.box(V((plate_x - 0.004, yc - 0.18, 1.2)),
          V((plate_x, yc + 0.18, 1.26)), "Iron", skip=("+x",))
    # Rusted tag SEAL wired to the END (north) bars of the third kennel; end at y = yy + L/2 = -1.035
    tag_y = -1.04
    g.box(V((10.56, tag_y - 0.001, 1.025)),
          V((10.64, tag_y + 0.001, 1.075)), "Iron")
    # the wire
    g.cyl(V((10.60, tag_y - 0.005, 1.075)), V((10.60, tag_y - 0.03, 1.11)), 0.0015, 3, "Iron")


# ================================================================== C05_Wall (long outer wall)

@decorates("C05_Wall")
def c05_wall(g, lod):
    """Carvings between the kennels: Fetch's rules, the tally stone, the seal, loose stone with Ace of Hooks."""
    if lod > 0:
        return
    # LOOSE STONE with Ace of Hooks (behind kennel 2). Just slightly proud of the inner face.
    # Inner face is at x = 11.6, bbox min 11.55 (0.05 slack).
    sx0, sx1 = 11.555, 11.6
    g.box(V((sx0, -5.55, 0.52)), V((sx1, -5.25, 0.72)), "Stone")
    # the Ace of Hooks peeking out as a sliver of bone
    g.box(V((sx0 - 0.005, -5.42, 0.56)), V((sx0, -5.38, 0.66)), "Bone")

    # OLD FETCH's rules: incised panel between kennels 1 and 2
    _incised_panel(g, 11.598, -7.4, 1.9, 0.9, 0.7)
    # TALLY stone grey with strokes (y -8.5)
    _tally_stone(g, 11.598, -8.5, 0.85, 0.8, 0.7)
    # JORY's scratched seal (beside third kennel below slit)
    _seal_glyph(g, 11.598, -3.5, 1.7, 0.14)


def _incised_panel(g, x_face, cy, cz, dy, dz):
    """A rectangular panel of mortar: a border and a few parallel incised lines (text stand-in).

    x_face is the inner wall surface (the room is at smaller x). Proud detail goes toward -x."""
    xp = x_face - 0.015
    # border frame
    for u0, v0, u1, v1 in ((-dy / 2, -dz / 2, dy / 2, -dz / 2 + 0.03),
                            (-dy / 2, dz / 2 - 0.03, dy / 2, dz / 2),
                            (-dy / 2, -dz / 2 + 0.03, -dy / 2 + 0.03, dz / 2 - 0.03),
                            (dy / 2 - 0.03, -dz / 2 + 0.03, dy / 2, dz / 2 - 0.03)):
        g.face([V((xp, cy + u0, cz + v0)),
                V((xp, cy + u1, cz + v0)),
                V((xp, cy + u1, cz + v1)),
                V((xp, cy + u0, cz + v1))], "Stone", (-1, 0, 0))
    # three lines of "text"
    for row in range(3):
        zz = cz + 0.15 - row * 0.14
        g.face([V((xp - 0.001, cy - 0.35, zz - 0.008)),
                V((xp - 0.001, cy + 0.35, zz - 0.008)),
                V((xp - 0.001, cy + 0.35, zz + 0.008)),
                V((xp - 0.001, cy - 0.35, zz + 0.008))], "Stone", (-1, 0, 0))


def _tally_stone(g, x_face, cy, cz, dy, dz):
    """A big stone block covered in 5-stroke tally groups."""
    xp = x_face - 0.012
    # frame
    g.face([V((xp, cy - dy / 2, cz - dz / 2)),
            V((xp, cy + dy / 2, cz - dz / 2)),
            V((xp, cy + dy / 2, cz + dz / 2)),
            V((xp, cy - dy / 2, cz + dz / 2))], "Stone", (-1, 0, 0))
    # rows of thin dark grooves (iron reads black -> charcoal/soot lines)
    cols = 20
    rows = 7
    for r in range(rows):
        for c in range(cols):
            u = -dy / 2 + 0.05 + c * (dy - 0.1) / (cols - 1)
            v = -dz / 2 + 0.07 + r * (dz - 0.14) / (rows - 1)
            g.face([V((xp - 0.002, cy + u - 0.001, cz + v - 0.025)),
                    V((xp - 0.002, cy + u + 0.001, cz + v - 0.025)),
                    V((xp - 0.002, cy + u + 0.001, cz + v + 0.025)),
                    V((xp - 0.002, cy + u - 0.001, cz + v + 0.025))], "Iron", (-1, 0, 0))


def _seal_glyph(g, x_face, cy, cz, r):
    """A little seal: an iron oval disc for the body, two tiny flippers."""
    xp = x_face - 0.012
    nseg = 10
    pts = []
    for i in range(nseg):
        a = 2 * math.pi * i / nseg
        pts.append(V((xp, cy + math.cos(a) * r, cz + math.sin(a) * r * 0.6)))
    g.face(pts, "Iron", (-1, 0, 0))


# ================================================================== C05_Partition

@decorates("C05_Partition")
def c05_partition(g, lod):
    """Vole's bent nail in the mortar on the NORTH face (= south wall of C07)."""
    if lod > 0:
        return
    # Partition bbox y: -0.3 .. 0.3. North face at y = 0.3 looking +y.
    cx, cz = 10.8, 0.55
    # the nail: a thin iron L shape just proud of the surface
    g.cyl(V((cx, 0.299, cz)), V((cx + 0.04, 0.299, cz + 0.008)), 0.003, 3, "Iron")
    g.cyl(V((cx + 0.04, 0.299, cz + 0.008)), V((cx + 0.065, 0.299, cz + 0.02)), 0.003, 3, "Iron")


# ================================================================== C05_Roof (rag hatch above C06)

@decorates("C05_Roof")
def c05_roof(g, lod):
    if lod > 0:
        return
    # Hatch at world (5.6, -3.9, 6.02) size 0.8x0.8x0.12. Roof bbox z: 5.418..6.082.
    cx, cy, cz = 5.6, -3.9, 5.96
    # trapdoor panel (wood)
    g.box(V((cx - 0.4, cy - 0.4, cz - 0.03)), V((cx + 0.4, cy + 0.4, cz + 0.03)), "Wood")
    # iron strap hinges
    for sx in (-0.3, 0.3):
        g.box(V((cx + sx - 0.03, cy - 0.4, cz + 0.025)),
              V((cx + sx + 0.03, cy + 0.4, cz + 0.035)), "Iron", skip=("-z",))
    # bolt
    g.cyl(V((cx + 0.42, cy - 0.1, cz + 0.03)), V((cx + 0.42, cy + 0.1, cz + 0.03)), 0.012, 4, "Iron")
    # rags snagged on hinge (hanging down INTO the roof thickness bbox); bbox z_min = 5.418
    rx, ry, rz = 5.6, -3.45, 5.78
    for dx in (-0.08, 0.08):
        g.box(V((rx + dx - 0.02, ry - 0.02, 5.54)),
              V((rx + dx + 0.02, ry + 0.02, rz + 0.04)), "Cloth")


# ================================================================== C05_Floor (cards)

@decorates("C05_Floor")
def c05_floor(g, lod):
    if lod > 0:
        return
    # Three of Keys and Queen of Crowns, flat on the floor near kennel 2
    cx, cy = 9.7, -5.1
    for i, dy in enumerate((-0.05, 0.05)):
        _flat_tile(g, (cx, cy + dy, 0.405), (0.09, 0.06), "Bone", (0, 0, 1))


def _flat_tile(g, c, half, mat, out):
    cx, cy, cz = c
    hx, hy = half
    g.face([V((cx - hx, cy - hy, cz)),
            V((cx + hx, cy - hy, cz)),
            V((cx + hx, cy + hy, cz)),
            V((cx - hx, cy + hy, cz))], mat, out)


# ================================================================== C05_Bowls (names, spoons, helmet)

@decorates("C05_Bowls")
def c05_bowls(g, lod):
    if lod > 0:
        return
    r = _rng("bowls-east")
    # Five bowls at x = 7.0, 7.62, 8.24, 8.86, 9.48 ; y = -1.35 ; top z ~ 0.49
    # Two wooden spoons on twine from the tether rail
    for sx in (-0.1, 0.1):
        # twine
        g.cyl(V((8.4 + sx, -0.42, 0.78)), V((8.4 + sx, -0.42, 1.27)), 0.002, 3, "Straw")
        # spoon handle
        g.cyl(V((8.4 + sx, -0.42, 0.78)), V((8.4 + sx, -0.42, 0.60)), 0.006, 3, "Wood")
        # spoon bowl
        g.box(V((8.4 + sx - 0.02, -0.44, 0.55)),
              V((8.4 + sx + 0.02, -0.4, 0.60)), "Wood")
    # Crown marine's helmet as the chamber pot (west end of trough)
    hc = V((4.5, -1.25, 0.52))
    g.cyl(hc - V((0, 0, 0.03)), hc + V((0, 0, 0.1)), 0.14, 8, "Iron", caps=(False, True))
    # a small chin-strap stud
    g.box(V((hc.x - 0.14, hc.y - 0.01, hc.z + 0.03)),
          V((hc.x - 0.125, hc.y + 0.01, hc.z + 0.07)), "Iron")


# ================================================================== C05_Clothes (rag with gilt, collar, extras)

@decorates("C05_Clothes")
def c05_clothes(g, lod):
    if lod > 0:
        return
    r = _rng("clothes-east")
    # A rag strip with a tarnished gold thread (Bone = gilt per bible) laid across middle pile
    rc = V((6.4, -10.3, 0.46))
    g.box(V((rc.x - 0.24, rc.y - 0.06, rc.z - 0.005)),
          V((rc.x + 0.24, rc.y + 0.06, rc.z + 0.005)), "Cloth", skip=("-z",))
    # the gold thread (very thin Bone strip)
    g.box(V((rc.x - 0.24, rc.y - 0.005, rc.z + 0.005)),
          V((rc.x + 0.24, rc.y + 0.005, rc.z + 0.012)), "Bone")
    # Collar with tag FETCH on the lying skeleton's neck (world ~ 9.26, -10.45, 0.5)
    cc = V((9.26, -10.45, 0.5))
    # the collar ring
    g.link(cc, V((0, 1, 0)), V((0, 0, 1)), 0.06, 0.06, 0.008, 10, 3, "Cloth")
    # the brass tag hanging
    g.box(V((cc.x - 0.025, cc.y + 0.003, cc.z - 0.08)),
          V((cc.x + 0.025, cc.y + 0.015, cc.z - 0.04)), "Iron")
    # a few dirty loincloth balls scattered (within bbox y: -11.42..-9.736)
    for sx, sy in ((-0.4, 0.2), (0.6, -0.2), (-1.1, 0.3)):
        p = V((rc.x + sx, rc.y + sy, 0.4))
        g.blob(p, 0.07, 0.05, 0.02, 6, 1, "Cloth", r, 0.2)


# ================================================================== C06_Arch (board)

@decorates("C06_Arch")
def c06_arch(g, lod):
    """GOVERNOR'S HOUNDS - DO NOT FEED, with DO NOT scratched out."""
    if lod > 0:
        return
    # Yard face of arch head above the hood mould (-x face of arch), at (2.96, -2.875, 6.75)
    # Arch bbox x: 2.89..3.87. The yard face is around x = 2.93. Put thin board slightly out at x=2.93.
    cx, cy, cz = 2.935, -2.875, 6.75
    # wood plaque
    g.box(V((cx - 0.015, cy - 0.5, cz - 0.1)),
          V((cx, cy + 0.5, cz + 0.1)), "Wood", skip=("+x",))
    # two iron nails
    for sy in (-0.46, 0.46):
        g.cyl(V((cx - 0.02, cy + sy, cz + 0.08)),
              V((cx - 0.005, cy + sy, cz + 0.08)), 0.006, 3, "Iron")
    # scratched-out section (an iron groove over "DO NOT")
    g.box(V((cx - 0.018, cy - 0.45, cz + 0.03)),
          V((cx - 0.015, cy - 0.1, cz + 0.055)), "Iron")


# ================================================================== C05_Arch (board) and C07/C08 arches

@decorates("C05_Arch")
def c05_arch(g, lod):
    if lod > 0:
        return
    # KENNEL - the one true word. A plain carved stone board flush with the yard face.
    cx, cy, cz = 2.935, -8.625, 6.75
    # a very shallow raised rectangle "panel" with four grooves (letter blocks)
    g.box(V((cx - 0.008, cy - 0.5, cz - 0.1)),
          V((cx, cy + 0.5, cz + 0.1)), "Stone", skip=("+x",))
    for i in range(6):
        y = cy - 0.42 + i * 0.17
        g.box(V((cx - 0.014, y - 0.03, cz - 0.03)),
              V((cx - 0.008, y + 0.03, cz + 0.03)), "Stone")


@decorates("C07_Arch")
def c07_arch(g, lod):
    if lod > 0:
        return
    cx, cy, cz = 2.935, 2.875, 6.75
    g.box(V((cx - 0.015, cy - 0.5, cz - 0.1)),
          V((cx, cy + 0.5, cz + 0.1)), "Wood", skip=("+x",))
    # scratched-out original word (dark iron groove over the top row)
    g.box(V((cx - 0.018, cy - 0.4, cz + 0.03)),
          V((cx - 0.015, cy + 0.3, cz + 0.06)), "Iron")
    # tar lettering (dark groove under)
    g.box(V((cx - 0.018, cy - 0.35, cz - 0.05)),
          V((cx - 0.015, cy + 0.35, cz - 0.02)), "Iron")


@decorates("C08_Arch")
def c08_arch(g, lod):
    if lod > 0:
        return
    cx, cy, cz = 2.935, 8.625, 6.75
    g.box(V((cx - 0.015, cy - 0.5, cz - 0.1)),
          V((cx, cy + 0.5, cz + 0.1)), "Wood", skip=("+x",))
    g.box(V((cx - 0.018, cy - 0.3, cz + 0.03)),
          V((cx - 0.015, cy + 0.3, cz + 0.06)), "Iron")
    g.box(V((cx - 0.018, cy - 0.35, cz - 0.05)),
          V((cx - 0.015, cy + 0.35, cz - 0.02)), "Iron")


# ================================================================== C07_Floor (spoon, crust, stain)

@decorates("C07_Floor")
def c07_floor(g, lod):
    if lod > 0:
        return
    # Spoon and crust under Cage 1 (near 7.0, 1.775)
    # spoon
    g.cyl(V((6.92, 1.75, 0.412)), V((7.08, 1.80, 0.412)), 0.008, 3, "Wood")
    g.box(V((7.08, 1.78, 0.41)), V((7.14, 1.84, 0.418)), "Wood")
    # crust (floor material)
    g.box(V((6.90, 1.84, 0.41)), V((6.97, 1.90, 0.418)), "Floor")
    # Dark stain under Cage 2 (9, 3.875)
    _flat_tile(g, (9.0, 3.875, 0.405), (0.33, 0.33), "Floor", (0, 0, 1))


# ================================================================== C07_Partition (Steadfast + men)

@decorates("C07_Partition")
def c07_partition(g, lod):
    if lod > 0:
        return
    # South face (y=5.45) carved Steadfast; incised = thin raised stone outline
    # The Steadfast silhouette: hull line + 3 masts
    y_s = 5.455  # just inside south face
    cx, cz = 8.5, 1.7
    # hull
    g.box(V((cx - 0.5, y_s - 0.004, cz - 0.1)),
          V((cx + 0.5, y_s, cz - 0.08)), "Stone", skip=("+y",))
    # three masts
    for mx in (cx - 0.4, cx, cx + 0.4):
        g.box(V((mx - 0.012, y_s - 0.004, cz - 0.08)),
              V((mx + 0.012, y_s, cz + 0.3)), "Stone", skip=("+y",))
    # yards on main mast
    for mx in (cx - 0.4, cx, cx + 0.4):
        for yz in (cz + 0.1, cz + 0.22):
            g.box(V((mx - 0.14, y_s - 0.004, yz - 0.005)),
                  V((mx + 0.14, y_s, yz + 0.005)), "Stone", skip=("+y",))
    # Men's lashes list on NORTH face (y = 6.045 inside; +y face)
    y_n = 6.045
    nx = 8.0
    for row in range(10):
        zz = 1.2 + row * 0.07
        g.face([V((nx - 0.5, y_n + 0.004, zz - 0.004)),
                V((nx + 0.5, y_n + 0.004, zz - 0.004)),
                V((nx + 0.5, y_n + 0.004, zz + 0.004)),
                V((nx - 0.5, y_n + 0.004, zz + 0.004))], "Stone", (0, 1, 0))


# ================================================================== C07_Wall (log + carving)

@decorates("C07_Wall")
def c07_wall(g, lod):
    if lod > 0:
        return
    # LOOSE STONE with Ormond's log (y=4.6, z=1.1). Inner face at x=11.6, slack to 11.55.
    sx0, sx1 = 11.555, 11.6
    g.box(V((sx0, 4.45, 1.0)), V((sx1, 4.75, 1.2)), "Stone")
    # a scrap of cloth peeking out
    g.box(V((sx0 - 0.004, 4.55, 1.04)), V((sx0, 4.65, 1.14)), "Cloth")
    # Carving THREE DAYS UP (y=1.5): a bordered incised panel
    _incised_panel(g, 11.598, 1.5, 1.2, 0.5, 0.35)


# ================================================================== C07_Cage_1 (ship, card, rags)

@decorates("C07_Cage_1")
def c07_cage_1(g, lod):
    if lod > 0:
        return
    cx, cy = 7.0, 1.775
    # Ship scratched into cage floor plate (z=1.325 is floor plate top)
    _flat_tile(g, (cx, cy, 1.332), (0.22, 0.12), "Iron", (0, 0, 1))
    # Jack of Keys wedged between east bars (east = +x)
    g.box(V((cx + 0.41, cy - 0.03, 2.14)), V((cx + 0.418, cy + 0.03, 2.26)), "Bone")
    # Reef-knotted rags on west bars (west = -x)
    for z in (2.3, 2.5, 2.7):
        g.box(V((cx - 0.42, cy - 0.07, z - 0.025)), V((cx - 0.38, cy + 0.07, z + 0.025)), "Cloth")


# ================================================================== C07_Cage_2 (hood, notches)

@decorates("C07_Cage_2")
def c07_cage_2(g, lod):
    if lod > 0:
        return
    cx, cy = 9.0, 3.875
    # Black hood crumpled at the skeleton's feet (z=1.36)
    g.blob(V((9.15, cy + 0.075, 1.36)), 0.12, 0.10, 0.03, 8, 1, "Cloth", _rng("hood"), 0.3)
    # Notches on bottom hoop and middle hoop - as thin iron grooves
    # bottom hoop around cage perimeter at z=1.325 (floor plate), middle hoop at z~2.9
    for z, n in ((1.33, 20), (2.90, 9)):
        for i in range(n):
            a = 2 * math.pi * i / n
            px = cx + math.cos(a) * 0.42
            py = cy + math.sin(a) * 0.42
            g.cyl(V((px, py, z - 0.008)), V((px, py, z + 0.008)), 0.002, 3, "Iron")


# ================================================================== C07_Winch (crown plate, water pole)

@decorates("C07_Winch")
def c07_winch(g, lod):
    if lod > 0:
        return
    # Crown plate on north face of west post
    cx, cy, cz = 4.75, 0.805, 1.25
    g.box(V((cx - 0.06, cy - 0.004, cz - 0.1)),
          V((cx + 0.06, cy, cz + 0.1)), "Iron", skip=("+y",))
    # Water pole with hook and small bucket, leaning against east end
    px, py = 7.5, 0.5
    g.cyl(V((px, py, 0.5)), V((px - 0.03, py + 0.05, 1.9)), 0.015, 4, "Wood")
    # hook at the top
    g.cyl(V((px - 0.03, py + 0.05, 1.9)), V((px + 0.03, py + 0.05, 1.95)), 0.006, 3, "Iron")
    # small bucket
    g.cyl(V((px + 0.05, py - 0.08, 1.65)), V((px + 0.05, py - 0.08, 1.78)), 0.06, 6, "Wood", caps=(True, False))


# ================================================================== C08_Mast (brands + L + coin)

@decorates("C08_Mast")
def c08_mast(g, lod):
    if lod > 0:
        return
    # King's Arrow + overburnt Hook on the south face (y_min=8.151) near z=0.7
    cx = 7.4
    yf = 8.157  # just inside the south face of the mast
    # arrow shape (3 small iron grooves)
    g.box(V((cx - 0.03, yf - 0.004, 0.65)), V((cx + 0.03, yf, 0.75)), "Iron", skip=("+y",))
    # Rows of notches on north face (y_max=9.075) between middle & upper bands
    yn = 9.070
    for r in range(8):
        for c in range(10):
            px = cx - 0.09 + c * 0.02
            pz = 1.5 + r * 0.08
            g.box(V((px - 0.0015, yn, pz - 0.012)),
                  V((px + 0.0015, yn + 0.004, pz + 0.012)), "Wood", skip=("-y",))
    # Single L at z=2.45 south face (bound hands height)
    g.box(V((cx - 0.004, yf - 0.004, 2.44)), V((cx + 0.004, yf, 2.49)), "Wood", skip=("+y",))
    g.box(V((cx - 0.004, yf - 0.004, 2.44)), V((cx + 0.015, yf, 2.448)), "Wood", skip=("+y",))
    # Crown coin nailed to mast (south face, z=0.95)
    g.cyl(V((cx, yf - 0.004, 0.95)), V((cx, yf, 0.95)), 0.015, 8, "Iron")


# ================================================================== C08_Floor (salt-crusted stain)

@decorates("C08_Floor")
def c08_floor(g, lod):
    if lod > 0:
        return
    _flat_tile(g, (7.4, 8.2, 0.405), (0.5, 0.4), "Floor", (0, 0, 1))
    # a salt crust (Bone) ring around it
    for a in range(12):
        th = 2 * math.pi * a / 12
        px = 7.4 + math.cos(th) * 0.5
        py = 8.2 + math.sin(th) * 0.35
        g.box(V((px - 0.02, py - 0.02, 0.405)),
              V((px + 0.02, py + 0.02, 0.413)), "Bone")


# ================================================================== C08_Partition (frigate carving + swords)

@decorates("C08_Partition")
def c08_partition(g, lod):
    if lod > 0:
        return
    # SOUTH face (y=11.14): frigate without mainmast + HER MAST IS HERE
    y_s = 11.145
    cx, cz = 8.5, 3.1
    # hull
    g.box(V((cx - 0.4, y_s - 0.004, cz - 0.05)),
          V((cx + 0.4, y_s, cz - 0.03)), "Stone", skip=("+y",))
    # fore + mizzen masts only (middle broken off)
    for mx in (cx - 0.3, cx + 0.3):
        g.box(V((mx - 0.01, y_s - 0.004, cz - 0.03)),
              V((mx + 0.01, y_s, cz + 0.2)), "Stone", skip=("+y",))
    # a broken stump where main would be
    g.box(V((cx - 0.01, y_s - 0.004, cz - 0.03)),
          V((cx + 0.01, y_s, cz)), "Stone", skip=("+y",))
    # NORTH face: swords on pegs. Partition bbox y_max=11.86; wall face at ~11.81, 5cm slack.
    y_face = 11.815
    for i, sx in enumerate((-0.5, 0.0, 0.5)):
        px = 8.5 + sx
        # peg
        g.cyl(V((px, y_face, 2.4)), V((px, y_face + 0.038, 2.4)), 0.008, 3, "Iron")
        # blade
        g.box(V((px - 0.015, y_face + 0.028, 2.1)),
              V((px + 0.015, y_face + 0.042, 2.75)), "Iron")
        # cross-guard
        g.box(V((px - 0.08, y_face + 0.02, 2.08)),
              V((px + 0.08, y_face + 0.042, 2.11)), "Iron")
        # gilt hilt
        g.box(V((px - 0.02, y_face + 0.022, 2.00)),
              V((px + 0.02, y_face + 0.042, 2.08)), "Bone")


# ================================================================== C08_Wall (Wicken chorus + Jory 40)

@decorates("C08_Wall")
def c08_wall(g, lod):
    if lod > 0:
        return
    # Wicken's chorus (y=9.9, z=1.7) - incised panel with lines
    _incised_panel(g, 11.598, 9.9, 1.7, 0.9, 0.6)
    # Jory's seal and 40 (y=7.6, z=1.3) - small panel + seal glyph
    _seal_glyph(g, 11.598, 7.5, 1.3, 0.08)
    # "40" as a couple of grooves
    for i in range(4):
        pz = 1.25 + i * 0.012
        g.face([V((11.597, 7.65, pz)), V((11.597, 7.72, pz)),
                V((11.597, 7.72, pz + 0.004)), V((11.597, 7.65, pz + 0.004))], "Iron", (-1, 0, 0))


# ================================================================== C08_Vault block & tackle

@decorates("C08_Vault")
def c08_vault_tackle(g, lod):
    if lod > 0:
        return
    # Block and tackle hanging from vault crown above the mast
    cx, cy = 7.4, 8.625
    # wooden block
    g.box(V((cx - 0.1, cy - 0.08, 6.65)), V((cx + 0.1, cy + 0.08, 6.9)), "Wood")
    # iron hook up to vault
    g.cyl(V((cx, cy, 6.9)), V((cx, cy, 7.2)), 0.012, 4, "Iron")
    # rope (straw) hanging down
    g.cyl(V((cx - 0.08, cy, 6.65)), V((cx - 0.08, cy, 6.5)), 0.01, 3, "Straw")


# ================================================================== C08_Props (cat names, scoop, book, strap)

@decorates("C08_Props")
def c08_props(g, lod):
    if lod > 0:
        return
    r = _rng("mast-props-east")
    # Burnt cat names MERCY, MARGERY, WIDOW on cat board at (5.8, 11.145, 2.45)
    cbx = 5.8; cby = 11.145; cbz = 2.45
    for i in range(3):
        px = cbx - 0.5 + i * 0.5
        # char rectangle per name
        g.box(V((px - 0.1, cby - 0.006, cbz - 0.02)),
              V((px + 0.1, cby, cbz + 0.02)), "Iron", skip=("+y",))
    # Wooden scoop on top of the salt barrel (10.6, 10.6, 1.33)
    sx, sy, sz = 10.6, 10.6, 1.33
    g.cyl(V((sx - 0.08, sy, sz)), V((sx + 0.08, sy, sz + 0.02)), 0.04, 5, "Wood")
    g.cyl(V((sx + 0.08, sy, sz + 0.01)), V((sx + 0.22, sy - 0.02, sz + 0.05)), 0.008, 3, "Wood")
    # Crake's lash book hung on a nail at (7.2, 11.17, 2.0)
    bx1 = V((7.17, 11.14, 1.80))
    bx2 = V((7.23, 11.17, 2.20))
    g.box(bx1, bx2, "Cloth")
    g.cyl(V((7.2, 11.15, 2.21)), V((7.2, 11.17, 2.21)), 0.004, 3, "Iron")
    # Bitten leather strap on peg (6.8, 11.15, 1.75)
    g.cyl(V((6.80, 11.15, 1.75)), V((6.80, 11.15, 1.6)), 0.015, 4, "Cloth")
    g.cyl(V((6.80, 11.155, 1.75)), V((6.80, 11.17, 1.75)), 0.005, 3, "Iron")

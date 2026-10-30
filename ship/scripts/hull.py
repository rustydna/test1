"""Hull lines of the Second Bride (a 32-gun frigate re-masted as the Lord of the Pit's flagship).

Coordinates: metres, origin on the waterline amidships, +X forward (bow), +Y to port, +Z up.
The hull surface is generated from the half-breadth function y(x, z) on a station x height
grid, mirrored, closed at the transom, given a planking thickness and pierced for the gun ports.
"""

import math

import vmesh as M
from mathutils import Vector

XS = -19.0                  # transom
XB = 19.2                   # stem head (at the rail)
BH = 5.3                    # maximum half-breadth
KEEL = -4.2
T = 0.22                    # hull planking thickness (the inside of the bulwarks is visible)
PORTS_X = [-4.9, -2.5, -0.1, 2.3, 4.7, 7.1, 9.4]      # gun ports in the waist, both sides
PORT_W, PORT_SILL, PORT_HEAD = 0.82, 0.42, 1.2


def smooth(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def deck_z(x):
    """Main (upper) deck at the side: 2.7 m above the waterline amidships, with sheer (the brig below
    it stays above the water line, so the sim's water never shows inside the hull)."""
    return 2.7 + 0.0022 * (x - 1.0) ** 2


def quarter_z(x):
    return deck_z(x) + 2.6


def fore_z(x):
    return deck_z(x) + 2.4


def rail_z(x):
    """Top of the hull side: the waist bulwark, rising to the quarterdeck and forecastle rails."""
    return deck_z(x) + 1.35 + 2.55 * (1 - smooth(-7.6, -5.6, x)) + 2.25 * smooth(9.6, 11.2, x)


def keel_z(x):
    k = KEEL
    if x > 11.0:
        k += 3.0 * ((x - 11.0) / (XB - 11.0)) ** 2
    if x < -15.0:
        k += 0.5 * ((-15.0 - x) / 4.0)
    return k


def stem_x(z):
    """The stem rakes forward: the bow reaches further at the rail than at the forefoot."""
    return 17.6 + (XB - 17.6) * smooth(-3.0, 6.0, z)


def half_breadth(x, z):
    """Half-breadth of the moulded hull at (x, z)."""
    xm = 2.0
    zk = keel_z(x)
    if x >= xm:
        t = min((x - xm) / max(stem_x(z) - xm, 1e-3), 1.0)
        p = 1.7 + 0.9 * smooth(-3.5, 4.0, z)            # fine forefoot, bluff bow at the rail
        b = max(1.0 - t ** p, 0.0)
    else:
        t = min((xm - x) / (xm - XS), 1.0)
        w = 0.74 * smooth(-1.6, 2.6, z)                  # transom width fraction (counter above water)
        b = 1.0 - (1.0 - w) * t ** 1.8
    d = min(max((z - zk) / (0.5 - zk), 0.0), 1.0)
    if z <= 0.5:
        s = math.sin(d * math.pi / 2) ** 0.62            # firm bilge, deep floors
    else:
        s = 1.0 - 0.12 * ((z - 0.5) / 4.5) ** 1.4       # tumblehome
    return max(BH * b * s, 0.18 * (1 - d) + 0.02)


def hull_surface(n_st=60, n_rows=22):
    """Port half of the outer hull surface (open at the rail and along the keel)."""
    s = M.Shape()
    grid = []
    for i in range(n_st + 1):
        u = i / n_st
        col = []
        for j in range(n_rows + 1):
            v = j / n_rows
            # rows bunched near the keel and the rail for a cleaner bilge and sheer line
            vv = 0.5 - 0.5 * math.cos(v * math.pi) if v < 0.5 else v
            x0 = XS + u * (XB - XS)
            zk = keel_z(x0)
            z = zk + vv * (rail_z(x0) - zk)
            x = XS + u * (stem_x(z) - XS)
            zk = keel_z(x)
            z = zk + vv * (rail_z(x) - zk)
            col.append(s.vert((x, half_breadth(x, z), z)))
        grid.append(col)
    for i in range(n_st):
        for j in range(n_rows):
            s.face([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "a_plaster")
    # transom: close the stern between the centre line and the side
    tr = grid[0]
    for j in range(n_rows):
        a, b = tr[j], tr[j + 1]
        c = s.vert((a.co.x, 0.0, b.co.z))
        d = s.vert((a.co.x, 0.0, a.co.z))
        s.face([d, c, b, a], "a_plaster")
    return s


def hull(n_st=60, n_rows=22):
    """Closed, planked hull (both sides), pierced for the waist gun ports."""
    half = hull_surface(n_st, n_rows)
    half.recalc()
    full = half.copy().mirror("Y", 0.0)
    full.weld(2e-3)
    full.recalc()
    # outward normals: a point well outside must see the faces from the front
    if sum(f.normal.y * f.calc_center_median().y for f in full.bm.faces) < 0:
        full.flip()
    ob = full._object()
    for sl in M.ALL:
        ob.data.materials.append(M._slot_material(sl))
    mod = ob.modifiers.new("sol", "SOLIDIFY")
    mod.thickness = T
    mod.offset = -1.0
    mod.use_rim = True
    mod.use_even_offset = True
    mod.material_offset = 2            # the new shell is marked (slot 2) to tell inside from outside
    mod.material_offset_rim = 3
    full._take(ob)
    for x in PORTS_X:
        for side in (1, -1):
            z0 = deck_z(x) + PORT_SILL
            z1 = deck_z(x) + PORT_HEAD
            y = side * half_breadth(x, z0)
            cut = M.box_cage((x - PORT_W / 2, y - 0.6, z0), (x + PORT_W / 2, y + 0.6, z1), "d_stone")
            full.boolean(cut)
    return full


def paint(s):
    """Hull paint outside (black above the waterline, dark sheathing below), plain wood inside,
    red-ochre trim in the port linings. The raised wales carry the gilt strake."""
    marked = [f for f in s.bm.faces if f.material_index == 2]
    plain = [f for f in s.bm.faces if f.material_index == 0]
    def spread(fs):
        return sum(abs(f.calc_center_median().y) for f in fs) / max(len(fs), 1)
    new_is_inside = spread(marked) < spread(plain)
    for f in s.bm.faces:
        c = f.calc_center_median()
        if f.material_index == 3 or f.material_index == M.slot_index("d_stone"):
            f.material_index = M.slot_index("d_stone")          # rims and port linings
            continue
        inside = (f.material_index == 2) == new_is_inside
        if inside:
            f.material_index = M.slot_index("c_wood")
        elif c.z < 0.02:
            f.material_index = M.slot_index("f_metal")
        else:
            f.material_index = M.slot_index("a_plaster")
    return s


def inner_half_breadth(x, z):
    return max(half_breadth(x, z) - T - 0.02, 0.05)


def deck_outline(z_of_x, x0, x1, n=40):
    """2D outline (CCW) of a deck between x0 and x1 that follows the inside of the hull."""
    xs = [x0 + (x1 - x0) * k / n for k in range(n + 1)]
    port = [(x, inner_half_breadth(x, z_of_x(x))) for x in xs]
    star = [(x, -inner_half_breadth(x, z_of_x(x))) for x in reversed(xs)]
    return port + star


def deck(z_of_x, x0, x1, slot="b_floor", thick=0.16, n=40, cols=6):
    """Deck plate following the sheer (cambered a little), from x0 to x1."""
    s = M.Shape()
    top, bot = [], []
    for k in range(n + 1):
        x = x0 + (x1 - x0) * k / n
        w = inner_half_breadth(x, z_of_x(x))
        rt, rb = [], []
        for c in range(cols + 1):
            y = -w + 2 * w * c / cols
            camber = 0.08 * (1 - (y / max(w, 0.1)) ** 2)
            rt.append(s.vert((x, y, z_of_x(x) + camber)))
            rb.append(s.vert((x, y, z_of_x(x) + camber - thick)))
        top.append(rt)
        bot.append(rb)
    for k in range(n):
        for c in range(cols):
            s.face([top[k][c], top[k][c + 1], top[k + 1][c + 1], top[k + 1][c]], slot)
            s.face([bot[k][c], bot[k + 1][c], bot[k + 1][c + 1], bot[k][c + 1]], "c_wood")
    for k in range(n):
        for side in (0, cols):
            a, b, c2, d = top[k][side], top[k + 1][side], bot[k + 1][side], bot[k][side]
            s.face([a, d, c2, b] if side == 0 else [a, b, c2, d], "c_wood")
    for k in (0, n):
        r1, r2 = top[k], bot[k]
        for c in range(cols):
            q = [r1[c], r1[c + 1], r2[c + 1], r2[c]]
            s.face(q if k == n else list(reversed(q)), "c_wood")
    s.recalc()
    return s


def at_deck(x, y, deck="main"):
    z = {"main": deck_z, "quarter": quarter_z, "fore": fore_z}[deck](x)
    w = max(inner_half_breadth(x, z), 0.1)
    return z + 0.08 * (1 - (y / w) ** 2)


def V(x, y, z):
    return Vector((x, y, z))

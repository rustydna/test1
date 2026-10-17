"""The site = the Villa Core linkset: a 36 x 36 m travertine plinth with the pool and spa, the
outdoor lounge, sun deck, garden and the Core totem (root, holds the scripts and the houses).

Coordinates: metres, origin at the centre of the plot at deck level (z = 0), +Y north.
Houses stand on the north part (x -14.5..14.5, y -2..16.5); the pool is in the south.
"""

import math

import vbuild as B
import vmesh as M
from furniture import catalogue as C
from vplace import furn

LS = "Villa_Core"
B.linkset(LS, "Core_Totem", label="Villa Core", role="site")

SITE = M.superellipse(0, 0, 18, 18, 72, 5.0)
POOL = M.rounded_rect(-1.0, -13.1, 15.0, 5.0, 2.2, 6)
SPA_C, SPA_R = (8.4, -12.6), 1.7
SPA = M.superellipse(SPA_C[0], SPA_C[1], SPA_R, SPA_R, 40, 2.0)
WATER_Z = -0.08


@B.piece(LS, "Core_Totem", kind="core", phys="hull", li=1.5)
def totem(lod):
    """The Villa Core: a smooth monolith with a brass band and a glowing ring (touch for the menu)."""
    if lod:
        return None
    rings = []
    for z, sx, sy in ((0.0, 0.34, 0.26), (0.05, 0.37, 0.28), (0.6, 0.33, 0.25), (1.2, 0.27, 0.2), (1.5, 0.2, 0.15),
                      (1.58, 0.1, 0.08)):
        rings.append(M.pts3(M.superellipse(0, 0, sx, sy, 32, 2.4), z))
    body = M.loft(rings, "d_stone", fan=True)
    body.smooth(1)
    band = M.extrude(M.grow(M.superellipse(0, 0, 0.3, 0.226, 32, 2.4), 0.012), 0.95, 1.0, "f_metal")
    ring = M.sweep([(0.31 * math.cos(a * math.pi / 24), 0.235 * math.sin(a * math.pi / 24), 1.06) for a in range(48)],
                   0.012, "h_glow", n=6, closed=True)
    plinth = M.slab(M.superellipse(0, 0, 0.55, 0.45, 32, 2.4), 0.0, 0.05, "f_metal", r=0.01, seg=1)
    return M.join(body, band, ring, plinth).move(15.4, -3.6, 0)


def _deck_phys(_s):
    """Walkable deck around the pool and spa holes (thin boxes), so people can get into the water."""
    V = M.V
    return [("box", V(-18, -10.12, -0.3), V(18, 18, 0.0)),
            ("box", V(-18, -18, -0.3), V(18, -16.08, 0.0)),
            ("box", V(-18, -16.08, -0.3), V(-8.98, -10.12, 0.0)),
            ("box", V(10.55, -16.08, -0.3), V(18, -10.12, 0.0)),
            ("box", V(6.52, -16.08, -0.3), V(6.68, -14.3, 0.0))]


@B.piece(LS, "Site_Deck", kind="structure", phys=_deck_phys, li=9)
def deck(lod):
    if lod:
        return None
    s = M.slab(SITE, -1.2, 0.0, "d_stone", r=0.04, seg=1, top_slot="b_floor", side_slot="d_stone")
    s.boolean(M.extrude(M.grow(POOL, 0.44), -2.0, 0.5, "a_plaster"))
    s.boolean(M.extrude(M.grow(SPA, 0.44), -2.0, 0.5, "a_plaster"))
    # LED line around the plinth edge
    edge = M.grow(SITE, 0.03)
    s.join(M.extrude(edge, -0.12, -0.09, "h_glow"))
    return s


@B.piece(LS, "Site_Coping", kind="structure", phys="none", li=2)
def coping(lod):
    if lod:
        return None
    a = M.wall_band(M.resample(M.grow(POOL, 0.22), 96), 0.44, -0.05, 0.02, "d_stone", closed=True)
    b = M.wall_band(M.resample(M.grow(SPA, 0.22), 48), 0.44, -0.05, 0.12, "d_stone", closed=True)
    return a.join(b)


def basin(outline, depth, n=96, bench=None):
    """Pool shell seen from inside: walls, a soft cove, the floor, an LED line under the coping."""
    o = M.resample(M.ccw(outline), n)
    rings = [M.pts3(o, 0.0), M.pts3(o, -0.3), M.pts3(o, -depth + 0.12),
             M.pts3(M.grow(o, -0.1), -depth), M.pts3(M.grow(o, -0.35), -depth)]
    s = M.loft(rings, "a_plaster", cap0=False, cap1=True)
    s.flip()
    s.join(M.wall_band(M.grow(o, -0.005), 0.02, -0.26, -0.22, "h_glow", closed=True))
    if bench:
        s.join(M.wall_band(M.resample(M.grow(o, -bench[0] / 2), n), bench[0], -depth, bench[1], "a_plaster",
                           closed=True))
    return s


STEPS = [(-8.5 + 0.42 * k, -1.15 + 0.3 * k) for k in range(4)]     # (x start, top) west-end stairs


def _pool_phys(_s):
    V = M.V
    items = [("box", V(-8.5, -15.6, -1.55), V(6.5, -10.6, -1.45)),           # floor
             ("box", V(-8.6, -15.7, -1.45), V(6.6, -15.6, 0.0)), ("box", V(-8.6, -10.6, -1.45), V(6.6, -10.5, 0.0)),
             ("box", V(-8.6, -15.6, -1.45), V(-8.5, -10.6, 0.0)), ("box", V(6.5, -15.6, -1.45), V(6.6, -10.6, 0.0))]
    for k, (x, top) in enumerate(STEPS):
        items.append(("box", V(-8.5, -14.5, -1.45), V(x + 0.42, -11.7, top)))
    return items


@B.piece(LS, "Site_Pool", kind="structure", phys=_pool_phys, li=4)
def pool(lod):
    if lod:
        return None
    s = basin(POOL, 1.45)
    for x, top in STEPS:                       # wide stairs at the shallow west end, with LED nosings
        s.join(M.rounded_box((-8.5, -14.5, -1.45), (x + 0.42, -11.7, top), "a_plaster", r=0.02, seg=1))
        s.join(M.rounded_box((x + 0.36, -14.4, top - 0.035), (x + 0.42, -11.8, top - 0.01), "h_glow", r=0.005, seg=1))
    return s


def _spa_phys(_s):
    V = M.V
    cx, cy, r = SPA_C[0], SPA_C[1], SPA_R
    return [("box", V(cx - r, cy - r, -0.9), V(cx + r, cy + r, -0.8)),
            ("box", V(cx - r, cy - r, -0.8), V(cx - r + 0.42, cy + r, -0.42)),
            ("box", V(cx + r - 0.42, cy - r, -0.8), V(cx + r, cy + r, -0.42))]


@B.piece(LS, "Site_Spa", kind="structure", phys=_spa_phys, li=1.5)
def spa(lod):
    if lod:
        return None
    return basin(SPA, 0.8, 48, bench=(0.42, -0.42))


@B.piece(LS, "Site_Water", kind="water", phys="none", li=1.5)
def water(lod):
    if lod:
        return None
    w = M.panel(M.resample(POOL, 72), WATER_Z, "water")
    w.join(M.panel(M.resample(SPA, 40), WATER_Z + 0.06, "water"))
    return w


# ---------------------------------------------------------------- sun deck and outdoor lounge
for k, x in enumerate((-7.0, -4.5, -2.0, 0.5)):
    furn(LS, f"Site_Lounger_{k + 1}", C.lounger, x, -8.3, yaw=0, seat=(0, 0.5, 0.42, "villa_lounge"))
    if k % 2 == 0:
        furn(LS, f"Site_Side_{k + 1}", lambda: C.side_table(0.2, 0.42), x + 1.25, -7.6, kind="deco", phys="none")

furn(LS, "Site_Daybed", lambda: C.daybed_round(1.25), 12.6, -8.0, yaw=0,
     seat=(0, 0.55, 0.46, "villa_lounge", "villa_sit_curl", "villa_sit_relaxed"))
furn(LS, "Site_Lounge_Sofa", lambda: C.orbit_sofa(0, 0, r_in=1.55, a0=20, a1=160), -12.4, -11.4, yaw=0,
     seat=(0, 2.15, 0.43, "villa_sit_relaxed", "villa_sit_crossed", "villa_sit_curl"))
furn(LS, "Site_Firebowl", lambda: C.firebowl(0.6), -12.4, -11.4, kind="light", phys="hull")
furn(LS, "Site_Rug", lambda: C.rug(M.superellipse(0, 0, 2.8, 2.4, 48, 2.6), "e_fabric"), -12.4, -11.6,
     kind="deco", phys="none")

# ---------------------------------------------------------------- garden
for k, (x, y, s) in enumerate(((-15.6, -15.6, 1), (15.8, -15.4, 2), (-16.2, 3.0, 3), (16.2, 12.0, 4))):
    furn(LS, f"Site_Olive_{k + 1}", lambda s=s: C.olive_tree(3.2, seed=s), x, y, kind="plant", phys="none")
for k, (x, y) in enumerate(((-16.3, -6.0), (16.3, -10.5), (-16.4, 9.0), (-16.4, 15.4), (16.4, 4.5), (16.2, 15.6))):
    furn(LS, f"Site_Plant_{k + 1}", lambda k=k: C.plant(1.3 + 0.2 * (k % 3), 0.34, 11, seed=k + 1), x, y,
         kind="plant", phys="none")
for k, (x, y) in enumerate(((-16.9, -12.0), (-16.9, 6.0), (16.9, -6.0), (16.9, 8.5), (-9.0, -16.9),
                            (9.0, -16.9))):
    furn(LS, f"Site_Bollard_{k + 1}", C.bollard, x, y, kind="light", phys="none")

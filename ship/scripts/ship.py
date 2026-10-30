"""THE SECOND BRIDE - the Lord of the Pit's flagship, a 32-gun frigate (Second Life, all mesh).

Once the Crown frigate Steadfast, taken in fog in Year III, re-masted and renamed. 38 m on
deck (52 m with the jib-boom), three masts, 30 m from the waterline to the main truck.
Walkable main deck, quarterdeck and forecastle, the great cabin under the quarterdeck, the brig
on the lower deck, fourteen guns in the waist that fire a broadside from the menu, set or
furled sails, stern lanterns, the Lord's black flag.

Coordinates: metres, origin on the waterline amidships, +X to the bow, +Y to port.
Slots: 0 hull paint, 1 deck, 2 wood, 3 trim/gilt, 4 canvas, 5 metal, 6 glass, 7 glow.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, os.path.join(REPO, "villa", "scripts"))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401
import bmesh  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import hull as H  # noqa: E402
import vbuild as B  # noqa: E402
import vmesh as M  # noqa: E402

B.OUT = os.path.join(os.path.dirname(HERE), "output")
M.UV_TILE.update({"a_plaster": 2.0, "b_floor": 2.0, "c_wood": 1.2, "d_stone": 1.0, "e_fabric": 1.0,
                  "f_metal": 0.5, "g_glass": 0.6, "h_glow": 1.0, "water": 4.0})
PAINT, DECK, WOOD, TRIM, CANVAS, METAL, GLASS, GLOW = M.SLOTS
LS = "Second_Bride"
B.linkset(LS, "Bride_Deck_Main", label="The Second Bride", role="house")
V = H.V
MASTS = {"fore": (11.6, 17.0), "main": (-0.6, 19.0), "mizzen": (-12.2, 14.2)}     # x, height of the top
CABIN_X0, CABIN_X1 = -18.4, -6.3
BRIG_X0, BRIG_X1, BRIG_Z = 1.2, 10.6, 0.3
HATCH = (3.0, 4.4, -0.7, 0.7)


def tube(p0, p1, r, slot, n=8, r1=None):
    return M.sweep([V(*p0), V(*p1)], [r, r if r1 is None else r1], slot, n=n)


def box(mn, mx, slot, r=0.0):
    if r > 0:
        return M.rounded_box(mn, mx, slot, r=r, seg=1)
    return M.box_cage(mn, mx, slot)


def deck_boxes(z_of_x, x0, x1, step=2.0, t=0.25):
    """Physics for a deck that follows the sheer: one flat box per short stretch."""
    out = []
    x = x0
    while x < x1 - 1e-3:
        xe = min(x + step, x1)
        w = min(H.inner_half_breadth(x, z_of_x(x)), H.inner_half_breadth(xe, z_of_x(xe)))
        z = (z_of_x(x) + z_of_x(xe)) / 2 + 0.06
        out.append(("box", V(x, -w, z - t), V(xe, w, z)))
        x = xe
    return out


# ================================================================ hull (4 pieces)
def wales():
    """Raised wales along the sides: the gilt/ochre strake at the deck line and a black rail cap."""
    parts = []
    xs = [H.XS + 0.05 + k * 0.5 for k in range(int((H.XB - 0.6 - H.XS) / 0.5))]
    for side in (1, -1):
        for dz, h, slot in ((-0.32, 0.3, TRIM), (-1.3, 0.22, PAINT)):
            rows_lo, rows_hi = [], []
            for x in xs:
                z0 = H.deck_z(x) + dz
                if x > H.stem_x(z0) - 0.4:
                    break
                y0 = H.half_breadth(x, z0) + 0.035
                y1 = H.half_breadth(x, z0 + h) + 0.035
                rows_lo.append(V(x, side * y0, z0))
                rows_hi.append(V(x, side * y1, z0 + h))
            s = M.Shape()
            lo = [s.vert(p) for p in rows_lo]
            hi = [s.vert(p) for p in rows_hi]
            lo_in = [s.vert(p - V(0, side * 0.06, 0)) for p in rows_lo]
            hi_in = [s.vert(p - V(0, side * 0.06, 0)) for p in rows_hi]
            for i in range(len(lo) - 1):
                q = [lo[i], lo[i + 1], hi[i + 1], hi[i]]
                s.face(q if side < 0 else list(reversed(q)), slot)
                s.face([hi[i], hi[i + 1], hi_in[i + 1], hi_in[i]] if side < 0 else [hi_in[i], hi_in[i + 1], hi[i + 1], hi[i]], slot)
                s.face([lo_in[i], lo_in[i + 1], lo[i + 1], lo[i]] if side < 0 else [lo[i], lo[i + 1], lo_in[i + 1], lo_in[i]], slot)
            s.recalc()
            parts.append(s)
    # rail cap along the top of the hull side
    for side in (1, -1):
        pts = []
        for k in range(77):
            x = H.XS + 0.1 + (H.XB - 0.5 - H.XS) * k / 76
            z = H.rail_z(x)
            if x > H.stem_x(z) - 0.3:
                break
            pts.append(V(x, side * (H.half_breadth(x, z) - H.T / 2), z + 0.04))
        parts.append(M.sweep(pts, 0.13, WOOD, n=4, profile=[(1, 0.5), (-1, 0.5), (-1, -0.5), (1, -0.5)]))
    return M.join(*parts)


def build_hull():
    h = H.hull()
    # exact waterline: cut the faces along z = 0 so the bottom paint has a clean edge
    geom = list(h.bm.verts) + list(h.bm.edges) + list(h.bm.faces)
    bmesh.ops.bisect_plane(h.bm, geom=geom, plane_co=(0, 0, 0.02), plane_no=(0, 0, 1))
    H.paint(h)
    h.join(wales())
    return h


HULL = build_hull()
CUTS = [-7.8, 2.0, 11.0]


def hull_part(i):
    s = HULL.copy()
    xs = [-1e9] + CUTS + [1e9]
    for x, keep_above in ((xs[i], True), (xs[i + 1], False)):
        if abs(x) > 1e8:
            continue
        geom = list(s.bm.verts) + list(s.bm.edges) + list(s.bm.faces)
        bmesh.ops.bisect_plane(s.bm, geom=geom, plane_co=(x, 0, 0), plane_no=(1, 0, 0), clear_inner=keep_above,
                               clear_outer=not keep_above)
    return s


def _hull_phys(high):
    return [("mesh", high.copy().decimate(max(80, high.tri_count() // 10)))]


for _i, _n in enumerate(("Stern", "Aft", "Fore", "Bow")):
    @B.piece(LS, f"Bride_Hull_{_n}", kind="structure", phys=_hull_phys, li=7)
    def _hull(lod, i=_i):
        return None if lod else hull_part(i)


# ================================================================ decks
@B.piece(LS, "Bride_Deck_Main", kind="core", phys=lambda _s: deck_boxes(H.deck_z, -18.2, 1.5), li=3)
def deck_main(lod):
    if lod:
        return None
    d = H.deck(H.deck_z, -18.3, 1.5, n=22)
    gx0, gx1 = -2.6, -1.2
    zg = H.at_deck(-1.9, 0)
    d.join(box((gx0, -0.8, zg - 0.02), (gx1, 0.8, zg + 0.22), WOOD))
    for k in range(8):
        y = -0.7 + k * 0.2
        d.join(box((gx0 + 0.05, y - 0.03, zg + 0.2), (gx1 - 0.05, y + 0.03, zg + 0.26), WOOD))
    return d


@B.piece(LS, "Bride_Deck_Main_Fore", kind="structure", phys=lambda _s: deck_boxes(H.deck_z, 1.5, HATCH[0] - 0.05)
         + deck_boxes(H.deck_z, HATCH[1] + 0.05, 17.4)
         + [("box", V(HATCH[0] - 0.05, 0.75, H.deck_z(4) - 0.2), V(HATCH[1] + 0.05, 4.8, H.deck_z(4) + 0.06)),
            ("box", V(HATCH[0] - 0.05, -4.8, H.deck_z(4) - 0.2), V(HATCH[1] + 0.05, -0.75, H.deck_z(4) + 0.06))], li=3)
def deck_main_fore(lod):
    if lod:
        return None
    d = H.deck(H.deck_z, 1.5, 17.6, n=22)
    d.boolean(box((HATCH[0], HATCH[2], 0), (HATCH[1], HATCH[3], 6), DECK))
    # hatch coaming and the grating over the main hatch
    x0, x1, y0, y1 = HATCH
    z = H.at_deck((x0 + x1) / 2, 0)
    for a, b in (((x0 - 0.1, y0 - 0.1), (x1 + 0.1, y0)), ((x0 - 0.1, y1), (x1 + 0.1, y1 + 0.1)),
                 ((x0 - 0.1, y0), (x0, y1)), ((x1, y0), (x1 + 0.1, y1))):
        d.join(box((a[0], a[1], z - 0.05), (b[0], b[1], z + 0.28), WOOD))
    return d


@B.piece(LS, "Bride_Deck_Quarter", kind="structure", phys=lambda _s: deck_boxes(H.quarter_z, -18.8, -6.3), li=3)
def deck_quarter(lod):
    if lod:
        return None
    d = H.deck(H.quarter_z, -18.9, -6.25, n=20)
    d.join(beams(H.quarter_z, -18.6, -6.4))
    # balustrade at the break of the quarterdeck, with a gap for each ladder
    x = -6.35
    w = H.inner_half_breadth(x, H.quarter_z(x))
    zt = H.quarter_z(x) + 0.08
    for y0, y1 in ((-w, -w + 1.2), (-w + 2.3, w - 2.3), (w - 1.2, w)):
        d.join(box((x - 0.08, y0, zt + 0.95), (x + 0.08, y1, zt + 1.05), WOOD, 0.02))
        d.join(box((x - 0.06, y0, zt), (x + 0.06, y1, zt + 0.08), WOOD))
        n = max(2, int((y1 - y0) / 0.28))
        for k in range(n + 1):
            y = y0 + (y1 - y0) * k / n
            d.join(M.lathe([(0.045, 0.0), (0.035, 0.1), (0.06, 0.35), (0.03, 0.62), (0.045, 0.87)], WOOD, n=6,
                           center=(x, y, zt + 0.08)))
    return d


def beams(z_of_x, x0, x1, step=1.0):
    s = M.Shape()
    x = x0 + step / 2
    while x < x1:
        w = H.inner_half_breadth(x, z_of_x(x) - 0.3)
        z = z_of_x(x) - 0.16
        s.join(box((x - 0.11, -w, z - 0.22), (x + 0.11, w, z), WOOD))
        x += step
    for y in (-1.6, 1.6):                  # carlings
        s.join(box((x0, y - 0.08, z_of_x(x0) - 0.3), (x1, y + 0.08, z_of_x(x0) - 0.16), WOOD))
    return s


@B.piece(LS, "Bride_Deck_Fore", kind="structure", phys=lambda _s: deck_boxes(H.fore_z, 10.6, 17.8), li=2)
def deck_fore(lod):
    if lod:
        return None
    d = H.deck(H.fore_z, 10.5, 18.1, n=14)
    d.join(beams(H.fore_z, 10.6, 16.6))
    x = 10.55
    w = H.inner_half_breadth(x, H.fore_z(x))
    zt = H.fore_z(x) + 0.08
    for y0, y1 in ((-w, -w + 1.1), (w - 1.1, w), (-1.4, 1.4)):
        d.join(box((x - 0.07, y0, zt + 0.95), (x + 0.07, y1, zt + 1.05), WOOD, 0.02))
        for k in range(int((y1 - y0) / 0.3) + 1):
            y = y0 + (y1 - y0) * k / max(1, int((y1 - y0) / 0.3))
            d.join(tube((x, y, zt), (x, y, zt + 0.96), 0.03, WOOD, n=6))
    return d


@B.piece(LS, "Bride_Deck_Lower", kind="structure", phys=lambda _s: [("box", V(BRIG_X0, -3.6, BRIG_Z - 0.2),
                                                                      V(BRIG_X1, 3.6, BRIG_Z))], li=1.5)
def brig_low(lod):
    zt = H.deck_z(5.5) - 0.2
    s = M.join(box((BRIG_X0 - 0.06, -4.2, BRIG_Z), (BRIG_X0 + 0.06, 4.2, zt), WOOD),
               box((BRIG_X1 - 0.06, -4.2, BRIG_Z), (BRIG_X1 + 0.06, 4.2, zt), WOOD))
    if lod >= 2:
        return s
    for side in (1, -1):
        y = side * 1.05
        for k in range(0, 24, 3):
            x = 6.0 + k * 0.19
            if 7.2 < x < 8.25:
                continue
            s.join(ribbon((x, y, BRIG_Z), (x, y, zt), 0.04, METAL))
        for z in (BRIG_Z + 0.1, zt - 0.08):
            s.join(ribbon((6.0, y, z), (10.5, y, z), 0.06, METAL))
    return s


def deck_lower(lod):
    if lod:
        return None
    return H.deck(lambda x: BRIG_Z, BRIG_X0, BRIG_X1, n=10)


# ================================================================ stairs (walkable ramps)
def stair(x_top, x_bot, y0, y1, z_top, z_bot, steps=None):
    """Ship's ladder-stair from (x_top, z_top) down to (x_bot, z_bot): stringers and treads."""
    n = steps or max(4, int(abs(z_top - z_bot) / 0.22))
    s = M.Shape()
    for k in range(1, n + 1):
        t = k / (n + 1)
        x = x_top + (x_bot - x_top) * t
        z = z_top + (z_bot - z_top) * t
        s.join(box((x - 0.14, y0 + 0.06, z - 0.05), (x + 0.14, y1 - 0.06, z), WOOD))
    for y in (y0, y1 - 0.06):
        s.join(M.sweep([V(x_top, y + 0.03, z_top + 0.05), V(x_bot, y + 0.03, z_bot)], 0.05, WOOD, n=4,
                       profile=[(0.6, 1), (-0.6, 1), (-0.6, -1), (0.6, -1)]))
        s.join(M.sweep([V(x_top, y + 0.03, z_top + 1.0), V(x_bot, y + 0.03, z_bot + 1.0)], 0.03, WOOD, n=6))
    return s


def ramp(x_top, x_bot, y0, y1, z_top, z_bot):
    return [("hull", [V(x_top, y0, z_top), V(x_top, y1, z_top), V(x_bot, y0, z_bot), V(x_bot, y1, z_bot),
                      V(x_top, y0, z_top - 0.15), V(x_top, y1, z_top - 0.15), V(x_bot, y0, z_bot - 0.15),
                      V(x_bot, y1, z_bot - 0.15)])]


QL = [(-6.3, -4.2, side) for side in (1, -1)]
for _k, (_xt, _xb, _side) in enumerate(QL):
    _w = H.inner_half_breadth(-6.3, H.quarter_z(-6.3))
    _y0, _y1 = (_w - 2.2, _w - 1.25) if _side > 0 else (-_w + 1.25, -_w + 2.2)
    _zt, _zb = H.quarter_z(_xt) + 0.08, H.at_deck(_xb, (_y0 + _y1) / 2)

    @B.piece(LS, f"Bride_Stair_Quarter_{_k + 1}", kind="structure",
             phys=lambda _s, a=(_xt, _xb, _y0, _y1, _zt, _zb): ramp(*a), li=0.6)
    def _qs(lod, a=(_xt, _xb, _y0, _y1, _zt, _zb)):
        return None if lod else stair(*a)

_fw = H.inner_half_breadth(10.6, H.fore_z(10.6))
for _k, (_y0, _y1) in enumerate(((_fw - 2.1, _fw - 1.2), (-_fw + 1.2, -_fw + 2.1))):
    _a = (10.55, 8.8, _y0, _y1, H.fore_z(10.55) + 0.08, H.at_deck(8.8, (_y0 + _y1) / 2))

    @B.piece(LS, f"Bride_Stair_Fore_{_k + 1}", kind="structure", phys=lambda _s, a=_a: ramp(*a), li=0.5)
    def _fs(lod, a=_a):
        return None if lod else stair(*a)

_ba = (HATCH[0] - 0.05, HATCH[0] - 2.4, -0.55, 0.55, H.at_deck(HATCH[0], 0), BRIG_Z)


@B.piece(LS, "Bride_Stair_Brig", kind="structure", phys=lambda _s: ramp(*_ba), li=0.5)
def brig_stair(lod):
    return None if lod else stair(*_ba)


# ================================================================ bulkheads, doors, brig
def bulkhead(x, z0, z1, door=(0.0, 1.2), windows=(), slot=WOOD, panel=True):
    """Transverse bulkhead at x between two decks, with a door opening and optional windows."""
    w = H.inner_half_breadth(x, (z0 + z1) / 2)
    s = box((x - 0.06, -w, z0), (x + 0.06, w, z1), slot)
    s.boolean(box((x - 0.3, door[0] - door[1] / 2, z0 - 0.1), (x + 0.3, door[0] + door[1] / 2, z0 + 2.15), slot))
    for (yc, ww) in windows:
        s.boolean(box((x - 0.3, yc - ww / 2, z0 + 1.0), (x + 0.3, yc + ww / 2, z0 + 1.9), slot))
        s.join(M.vpanel([(x, yc - ww / 2), (x, yc + ww / 2)], z0 + 1.0, z0 + 1.9, GLASS))
        for k in range(1, 3):
            s.join(box((x - 0.03, yc - ww / 2 + ww * k / 3 - 0.02, z0 + 1.0), (x + 0.03, yc - ww / 2 + ww * k / 3 + 0.02,
                                                                             z0 + 1.9), WOOD))
    if panel:   # raised panelling: pilasters every 0.9 m on the face towards the open deck
        for k in range(int(2 * w / 0.9) + 1):
            y = -w + k * 0.9
            if abs(y - door[0]) < door[1] / 2 + 0.1 or any(abs(y - yc) < ww / 2 + 0.1 for yc, ww in windows):
                continue
            s.join(box((x + 0.06, y - 0.06, z0), (x + 0.12, y + 0.06, z1 - 0.05), TRIM if slot == WOOD else WOOD))
    return s


_cz0, _cz1 = H.deck_z(CABIN_X1) + 0.08, H.quarter_z(CABIN_X1) - 0.08


@B.piece(LS, "Bride_Bulkhead_Cabin", kind="light", phys="box", li=1.2)
def bulk_cabin(lod):
    if lod:
        return None
    b = bulkhead(CABIN_X1 + 0.05, _cz0, _cz1, door=(0.0, 1.1), windows=((-1.9, 1.0), (1.9, 1.0)))
    return b.join(lanterns([(-6.0, 2.6, H.deck_z(-6.1) + 2.0), (-6.0, -2.6, H.deck_z(-6.1) + 2.0)]))


@B.piece(LS, "Bride_Door_Cabin", kind="door", phys="box", li=0.4)
def door_cabin(lod):
    if lod:
        return None
    x = CABIN_X1 + 0.05
    d = box((x - 0.04, -0.54, _cz0), (x + 0.04, 0.54, _cz0 + 2.12), WOOD, 0.01)
    for z in (_cz0 + 0.5, _cz0 + 1.5):
        d.join(box((x + 0.04, -0.4, z - 0.3), (x + 0.07, 0.4, z + 0.3), TRIM))
    d.join(tube((x + 0.1, 0.38, _cz0 + 1.0), (x + 0.1, 0.38, _cz0 + 1.15), 0.02, METAL, n=6))
    return d


_fz0, _fz1 = H.deck_z(10.5) + 0.08, H.fore_z(10.5) - 0.08


@B.piece(LS, "Bride_Bulkhead_Fore", kind="light", phys="box", li=0.8)
def bulk_fore(lod):
    if lod:
        return None
    b = bulkhead(10.45, _fz0, _fz1, door=(0.0, 1.1))
    return b.join(lanterns([(10.3, 1.9, H.deck_z(10.4) + 1.9), (10.3, -1.9, H.deck_z(10.4) + 1.9)]))


@B.piece(LS, "Bride_Brig", kind="light", phys=lambda _s: [("box", V(BRIG_X0 - 0.1, -4, BRIG_Z), V(BRIG_X0 + 0.1, 4, 2.0)),
                                                              ("box", V(BRIG_X1 - 0.1, -4, BRIG_Z), V(BRIG_X1 + 0.1, 4, 2.0)),
                                                              ("box", V(6.0, 1.0, BRIG_Z), V(10.5, 1.1, 1.9)),
                                                              ("box", V(6.0, -1.1, BRIG_Z), V(10.5, -1.0, 1.9)),
                                                              ("box", V(6.0, 1.0, BRIG_Z), V(6.1, 3.6, 1.9)),
                                                              ("box", V(6.0, -3.6, BRIG_Z), V(6.1, -1.0, 1.9))], li=2.5)
def brig(lod):
    """The brig: two iron-barred cells along the sides, chains and shackles, straw, a lantern."""
    if lod:
        return brig_low(lod)
    zt = H.deck_z(5.5) - 0.2
    s = M.join(box((BRIG_X0 - 0.06, -4.2, BRIG_Z), (BRIG_X0 + 0.06, 4.2, zt), WOOD),
               box((BRIG_X1 - 0.06, -4.2, BRIG_Z), (BRIG_X1 + 0.06, 4.2, zt), WOOD))
    s.join(lanterns([(5.5, 0.0, H.deck_z(5.5) - 0.45)]))
    s.boolean(box((BRIG_X0 - 0.3, -0.6, BRIG_Z - 0.1), (BRIG_X0 + 0.3, 0.6, BRIG_Z + 2.0), WOOD))
    for side in (1, -1):
        y = side * 1.05
        # front grille (x 6.0 .. 10.5) with a door gap at x 7.2 .. 8.2, side grille at x = 6.0
        for k in range(24):
            x = 6.0 + k * 0.19
            if 7.2 < x < 8.25:
                continue
            s.join(tube((x, y, BRIG_Z), (x, y, zt), 0.018, METAL, n=4))
        for k in range(14):
            yy = side * (1.05 + k * 0.19)
            s.join(tube((6.0, yy, BRIG_Z), (6.0, yy, zt), 0.018, METAL, n=4))
        for z in (BRIG_Z + 0.1, BRIG_Z + 1.2, zt - 0.08):
            s.join(box((6.0, y - 0.03, z), (10.5, y + 0.03, z + 0.06), METAL))
        # chains and shackles on the hull side, straw on the floor
        for k, x in enumerate((7.0, 8.6, 10.0)):
            wy = side * (H.inner_half_breadth(x, 0.5) - 0.05)
            s.join(M.join(*[M.sweep([(x - 0.02, wy, 1.2 - 0.09 * j), (x + 0.02, wy - side * 0.03, 1.2 - 0.09 * j - 0.07)],
                                    0.012, METAL, n=4) for j in range(7)]))
            s.join(M.sweep([(x + 0.05 * math.cos(a * math.pi / 6), wy - side * 0.08, 0.55 + 0.05 * math.sin(a * math.pi / 6))
                            for a in range(12)], 0.012, METAL, n=4, closed=True))
        straw = M.blob((8.3, side * 2.3, BRIG_Z), 1.5, 0.9, 0.08, CANVAS, nu=14, nv=6, flat=BRIG_Z)
        s.join(straw)
    return s


for _k, _side in enumerate((1, -1)):
    @B.piece(LS, f"Bride_Brig_Door_{_k + 1}", kind="door", phys="box", li=0.3)
    def _bd(lod, side=_side):
        if lod:
            return None
        y = side * 1.05
        zt = H.deck_z(5.5) - 0.25
        d = M.join(*[tube((x, y, BRIG_Z + 0.02), (x, y, zt), 0.018, METAL, n=6) for x in (7.25, 7.45, 7.65, 7.85, 8.05)])
        for z in (BRIG_Z + 0.15, BRIG_Z + 1.2, zt - 0.1):
            d.join(box((7.2, y - 0.035, z), (8.15, y + 0.035, z + 0.06), METAL))
        d.join(box((8.0, y - 0.09, BRIG_Z + 1.0), (8.12, y + 0.09, BRIG_Z + 1.18), METAL, 0.01))
        return d


# ================================================================ stern: transom, gallery, letters, lanterns
def letters(text, size=0.42, depth=0.04):
    c = bpy.data.curves.new("txt", "FONT")
    c.body = text
    c.size = size
    c.extrude = depth
    c.resolution_u = 2
    c.align_x = "CENTER"
    ob = bpy.data.objects.new("txt", c)
    bpy.context.scene.collection.objects.link(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    bm = bmesh.new()
    bm.from_mesh(me)
    ob.evaluated_get(dg).to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(c)
    s = M.Shape(bm)
    s.set_slot(TRIM)
    return s


@B.piece(LS, "Bride_Stern", kind="structure", phys="none", li=3)
def stern(lod):
    """Stern gallery: five tall windows lit from the great cabin, gilt pilasters and scrolls, the
    ship's name in gilt letters, the quarter galleries on both sides, the taffrail and its crest."""
    if lod:
        return stern_low(lod)
    x = H.XS - 0.02
    s = M.Shape()
    zc = H.deck_z(x) + 1.25                    # window band (great cabin)
    w = H.half_breadth(x + 0.3, zc) - 0.35
    nwin = 5
    for k in range(nwin):
        y = -w + (2 * w) * (k + 0.5) / nwin
        ww = 2 * w / nwin - 0.28
        s.join(M.vpanel([(x - 0.01, y - ww / 2), (x - 0.01, y + ww / 2)], zc - 0.75, zc + 0.75, GLASS, two_sided=True)
               .rotate(90, "Z", (x, y, 0)).rotate(-90, "Z", (x, y, 0)))
        glow = M.vpanel([(x + 0.25, y - ww / 2), (x + 0.25, y + ww / 2)], zc - 0.72, zc + 0.72, GLOW, two_sided=False)
        s.join(glow)
        for yy in (y - ww / 2, y, y + ww / 2):
            s.join(box((x - 0.06, yy - 0.025, zc - 0.75), (x + 0.02, yy + 0.025, zc + 0.75), TRIM))
        for zz in (zc - 0.25, zc + 0.25):
            s.join(box((x - 0.06, y - ww / 2, zz - 0.02), (x + 0.02, y + ww / 2, zz + 0.02), TRIM))
        # arched gilt hood over each window
        arc = [(x - 0.08, y + ww / 2 * math.cos(a * math.pi / 8), zc + 0.78 + 0.18 * math.sin(a * math.pi / 8)) for a in range(9)]
        s.join(M.sweep(arc, 0.04, TRIM, n=6))
    for k in range(nwin + 1):
        y = -w + (2 * w) * k / nwin
        s.join(M.lathe([(0.0, 0.0), (0.09, 0.0), (0.07, 0.2), (0.08, 1.3), (0.1, 1.5), (0.0, 1.5)], TRIM, n=8,
                       center=(x - 0.08, y, zc - 0.82)))
    # balcony rail under the windows
    s.join(box((x - 0.55, -w - 0.1, zc - 1.0), (x, w + 0.1, zc - 0.92), WOOD))
    for k in range(25):
        y = -w + 2 * w * k / 24
        s.join(M.lathe([(0, 0), (0.03, 0), (0.045, 0.2), (0.025, 0.42), (0, 0.42)], TRIM, n=6,
                       center=(x - 0.5, y, zc - 0.92)))
    s.join(box((x - 0.55, -w - 0.1, zc - 0.5), (x - 0.42, w + 0.1, zc - 0.44), TRIM))
    # name board
    name = letters("SECOND BRIDE", 0.42).rotate(90, "X").rotate(-90, "Z")
    name.move(x - 0.08, 0.0, zc - 1.62)
    s.join(name)
    s.join(box((x - 0.06, -2.6, zc - 1.75), (x - 0.01, 2.6, zc - 1.12), PAINT))
    # taffrail crest: the hook through the broken crown, flanked by scrolls
    zt = H.rail_z(x) + 0.05
    s.join(M.sweep(M.bezier3((x - 0.1, -2.8, zt), (x - 0.1, -1.4, zt + 0.9), (x - 0.1, 1.4, zt + 0.9),
                             (x - 0.1, 2.8, zt), 20), 0.07, TRIM, n=8))
    hook = [(x - 0.15, 0.25 * math.cos(a * math.pi / 10) - 0.0, zt + 0.55 + 0.25 * math.sin(a * math.pi / 10))
            for a in range(-12, 7)]
    s.join(M.sweep(hook + [(x - 0.15, 0.25, zt + 1.15)], 0.045, TRIM, n=6))
    crown = M.lathe([(0.0, 0.0), (0.32, 0.0), (0.36, 0.18), (0.26, 0.28), (0.0, 0.3)], TRIM, n=10,
                    center=(x - 0.15, 0.0, zt + 1.1))
    s.join(crown)
    # quarter galleries: a glazed bay on each quarter, gilt-framed, with a domed roof and a finial
    qg = M.Shape()
    outer_s, s = s, qg
    for side in (1, -1):
        cx = H.XS + 2.3
        yb = side * (H.half_breadth(cx, zc) - 0.1)
        y0, y1 = sorted((yb, yb + side * 0.75))
        s.join(M.rounded_box((cx - 1.35, y0, zc - 0.85), (cx + 1.35, y1, zc + 0.85), PAINT, r=0.06, seg=1))
        s.join(M.rounded_box((cx - 1.45, y0 - 0.05, zc - 1.05), (cx + 1.45, y1 + 0.05, zc - 0.85), TRIM, r=0.03, seg=1))
        s.join(M.rounded_box((cx - 1.45, y0 - 0.05, zc + 0.85), (cx + 1.45, y1 + 0.05, zc + 1.0), TRIM, r=0.03, seg=1))
        dome = M.lathe([(1.0, 0.0), (0.95, 0.25), (0.7, 0.5), (0.3, 0.65), (0.0, 0.68)], PAINT, n=16, center=(cx, (y0 + y1) / 2, zc + 1.0))
        dome.scale(1.4, 0.38, 1.0, center=(cx, (y0 + y1) / 2, zc + 1.0))
        s.join(dome)
        s.join(M.lathe([(0.0, 0.0), (0.08, 0.0), (0.12, 0.15), (0.0, 0.32)], TRIM, n=8, center=(cx, (y0 + y1) / 2, zc + 1.66)))
        s.join(M.lathe([(1.0, 0.0), (0.7, -0.35), (0.25, -0.6), (0.0, -0.7)], TRIM, n=16, center=(cx, (y0 + y1) / 2, zc - 1.05))
               .scale(1.3, 0.38, 1.0, center=(cx, (y0 + y1) / 2, zc - 1.05)))
        yf = y1 if side > 0 else y0
        for i in (-0.85, 0.0, 0.85):
            s.join(M.vpanel([(cx + i - 0.32, yf + side * 0.005), (cx + i + 0.32, yf + side * 0.005)], zc - 0.6, zc + 0.6,
                            GLOW, two_sided=True))
            s.join(box((cx + i - 0.4, yf - 0.02, zc - 0.66), (cx + i - 0.32, yf + 0.04 * side + 0.02, zc + 0.66), TRIM))
        s.join(box((cx + 0.77, yf - 0.02, zc - 0.66), (cx + 1.3, yf + 0.02, zc + 0.66), TRIM))

    def hug(v):
        lim = H.half_breadth(v.x, v.z) - 0.12
        if abs(v.y) < lim:
            v.y = math.copysign(lim, v.y)
        return v
    qg.deform(hug)
    s = outer_s.join(qg)
    return s


def stern_low(lod):
    """Distant stern: the lit window band, the name board, the crest and the quarter galleries."""
    x = H.XS - 0.02
    zc = H.deck_z(x) + 1.25
    w = H.half_breadth(x + 0.3, zc) - 0.35
    s = M.vpanel([(x + 0.25, -w), (x + 0.25, w)], zc - 0.72, zc + 0.72, GLOW, two_sided=False)
    s.join(box((x - 0.06, -2.6, zc - 1.75), (x - 0.01, 2.6, zc - 1.12), TRIM))
    if lod == 1:
        zt = H.rail_z(x) + 0.05
        s.join(M.sweep(M.bezier3((x - 0.1, -2.8, zt), (x - 0.1, -1.4, zt + 0.9), (x - 0.1, 1.4, zt + 0.9),
                                 (x - 0.1, 2.8, zt), 8), 0.07, TRIM, n=4))
        for side in (1, -1):
            cx = H.XS + 2.4
            yb = side * (H.half_breadth(cx, zc) + 0.05)
            s.join(box((cx - 1.4, min(yb, yb + side * 0.55), zc - 0.9), (cx + 1.4, max(yb, yb + side * 0.55), zc + 1.0), PAINT))
    return s


@B.piece(LS, "Bride_Stern_Lanterns", kind="light", phys="none", li=1.0)
def stern_lanterns(lod):
    """Three great stern lanterns on iron brackets above the taffrail."""
    if lod:
        return None
    s = M.Shape()
    x = H.XS - 0.2
    zt = H.rail_z(H.XS) + 0.2
    for y, sc in ((-2.4, 0.85), (0.0, 1.1), (2.4, 0.85)):
        z = zt + (1.6 if y == 0 else 1.2)
        s.join(M.sweep([V(x + 0.3, y, zt - 0.2), V(x, y, z - 0.3)], 0.035, METAL, n=6))
        body = M.lathe([(0.0, 0.0), (0.18, 0.0), (0.26, 0.15), (0.3, 0.55), (0.26, 0.7), (0.0, 0.72)], GLASS, n=8,
                       center=(x - 0.1, y, z - 0.35))
        body.scale(sc, sc, sc, center=(x - 0.1, y, z - 0.35))
        s.join(body)
        s.join(M.lathe([(0.0, 0.05), (0.18, 0.05), (0.22, 0.5), (0.0, 0.62)], GLOW, n=8, center=(x - 0.1, y, z - 0.35))
               .scale(sc * 0.85, sc * 0.85, sc * 0.85, center=(x - 0.1, y, z - 0.35)))
        cap = M.lathe([(0.0, 0.7), (0.3, 0.7), (0.12, 0.95), (0.03, 1.1), (0.05, 1.18), (0.0, 1.2)], TRIM, n=8,
                      center=(x - 0.1, y, z - 0.35))
        cap.scale(sc, sc, sc, center=(x - 0.1, y, z - 0.35))
        s.join(cap)
    return s


# ================================================================ bow: figurehead, headrails, bowsprit, anchors
@B.piece(LS, "Bride_Figurehead", kind="deco", phys="none", li=1.5)
def figurehead(lod):
    """The Bride: a veiled woman leaning into the sea, arms crossed on her breast, the veil streaming
    back along the headrails. Gilt."""
    if lod:
        return None
    x0 = H.stem_x(3.0) + 0.1
    z0 = 3.0
    lean = Matrix.Rotation(math.radians(-38), 4, "Y")
    parts = []
    body = []
    for z, rx, ry in ((0.0, 0.18, 0.16), (0.35, 0.3, 0.26), (0.7, 0.34, 0.3), (1.0, 0.3, 0.26), (1.25, 0.2, 0.17),
                      (1.4, 0.1, 0.09), (1.5, 0.11, 0.1)):
        body.append([V(rx * math.cos(a), ry * math.sin(a), z) for a in [2 * math.pi * i / 16 for i in range(16)]])
    torso = M.loft(body, TRIM, cap0=True, cap1=False)
    torso.smooth(1)
    parts.append(torso)
    head = M.blob((0.04, 0, 1.68), 0.12, 0.11, 0.15, TRIM, nu=14, nv=10)
    head.smooth(1)
    parts.append(head)
    veil = []
    for k in range(7):
        t = k / 6
        z = 1.82 - 1.7 * t
        r = 0.16 + 0.32 * t
        veil.append([V(-0.05 - 1.1 * t - r * 0.4 * math.cos(a) + 0.05 * math.sin(a * 5 + k), r * math.sin(a), z + 0.06 * math.cos(a))
                     for a in [math.pi * (0.15 + 0.7 * i / 10) for i in range(11)]])
    vs = M.loft(veil, TRIM, cap0=False, cap1=False, closed=False)
    vs.solidify(0.025, offset=0)
    parts.append(vs)
    for side in (1, -1):
        parts.append(M.sweep(M.bezier3((0.0, side * 0.28, 1.15), (0.25, side * 0.22, 1.0), (0.3, -side * 0.05, 0.95),
                                       (0.18, -side * 0.18, 1.02), 8), 0.055, TRIM, n=8))
    fig = M.join(*parts)
    fig.transform(lean)
    fig.move(x0, 0.0, z0)
    # trailboards: gilt scrolls running back from the figure along both bows
    for side in (1, -1):
        pts = [V(x0 - 0.2 - k * 0.6, side * (0.15 + 0.09 * k), z0 + 0.9 - 0.05 * k) for k in range(6)]
        fig.join(M.sweep(pts, 0.05, TRIM, n=6))
    return fig


@B.piece(LS, "Bride_Bowsprit", kind="structure", phys="none", li=1.5)
def bowsprit(lod):
    """Bowsprit, jib-boom, spritsail yard, dolphin striker, and the two catheads with anchors."""
    if lod:
        return None
    p0 = V(H.stem_x(5.0) - 4.0, 0, H.fore_z(15) + 0.2)
    d = V(math.cos(math.radians(14)), 0, math.sin(math.radians(14)))
    p1 = p0 + d * 13.0
    p2 = p1 - d * 3.0
    s = M.sweep([p0, p1], [0.36, 0.2], WOOD, n=12)
    s.join(M.sweep([p2, p2 + d * 11.0], [0.15, 0.07], WOOD, n=10))
    s.join(M.sweep([p1 - d * 0.6 + V(0, -3.2, 0), p1 - d * 0.6 + V(0, 3.2, 0)], [0.09, 0.09], WOOD, n=8))
    s.join(tube(tuple(p1 - d * 0.3), tuple(p1 - d * 0.3 + V(0, 0, -2.0)), 0.06, WOOD))
    for k in range(4):            # iron bands (gammoning) on the bowsprit
        q = p0 + d * (3.5 + k * 0.35)
        s.join(M.sweep([q + V(0, 0, 0)], 0.38, METAL, n=12) if False else tube(tuple(q), tuple(q + d * 0.08), 0.38, METAL, n=12))
    for side in (1, -1):         # catheads and anchors
        xc = 14.8
        zc = H.fore_z(xc) + 0.3
        yc = side * (H.half_breadth(xc, zc) + 0.2)
        s.join(box((xc - 0.18, yc - side * 1.0 - 0.18, zc - 0.18), (xc + 0.18, yc + side * 0.9 + 0.18, zc + 0.18), WOOD, 0.03)
               if side > 0 else box((xc - 0.18, yc - 0.9 - 0.18, zc - 0.18), (xc + 0.18, yc + 1.0 + 0.18, zc + 0.18), WOOD, 0.03))
        ya = yc + side * 0.75
        za = zc - 0.4
        s.join(tube((xc, ya, za), (xc, ya, za - 2.6), 0.07, METAL, n=8))
        s.join(M.sweep(M.bezier3((xc - 0.9, ya, za - 2.1), (xc - 0.8, ya, za - 2.8), (xc + 0.8, ya, za - 2.8),
                                 (xc + 0.9, ya, za - 2.1), 10), 0.07, METAL, n=8))
        s.join(tube((xc, ya - 0.9, za - 0.2), (xc, ya + 0.9, za - 0.2), 0.08, WOOD, n=8))
    return s


# ================================================================ masts, yards, sails, rigging
def mast_geo(name, upper=False):
    """Lower mast with its top (upper=False) or the topmast, topgallant and truck (upper=True)."""
    x, top = MASTS[name]
    s = M.Shape()
    lower_r = 0.42 if name != "mizzen" else 0.3
    tw = 2.0 if name != "mizzen" else 1.5
    tm_h = 10.0 if name != "mizzen" else 8.0
    if not upper:
        s.join(M.lathe([(lower_r, BRIG_Z), (lower_r, H.deck_z(x)), (lower_r * 0.82, top - 1.0), (lower_r * 0.7, top + 0.4),
                        (0.0, top + 0.45)], WOOD, n=12, center=(x, 0, 0)))
        for z in (H.deck_z(x) + 3.0, (H.deck_z(x) + top) / 2 + 1.0, top - 2.5):
            s.join(M.lathe([(lower_r * 0.95, z - 0.06), (lower_r * 1.03, z - 0.03), (lower_r * 1.03, z + 0.03),
                            (lower_r * 0.95, z + 0.06)], METAL, n=12, center=(x, 0, 0)))
        rr = M.rounded_rect(x - 0.2, 0, tw * 0.9, tw * 1.7, 0.4, 2)
        s.join(M.slab(rr, top, top + 0.16, DECK))
        ring = M.resample(M.grow(rr, -0.03), 24, True)
        s.join(M.wall_band(ring + [ring[0]], 0.06, top + 0.16, top + 0.42, WOOD))
        return s
    s.join(M.lathe([(lower_r * 0.6, top - 1.6), (lower_r * 0.55, top + tm_h * 0.5), (lower_r * 0.42, top + tm_h),
                    (0.0, top + tm_h + 0.05)], WOOD, n=10, center=(x + 0.55, 0, 0)))
    s.join(box((x - 0.3, -0.5, top + tm_h - 0.6), (x + 0.9, 0.5, top + tm_h - 0.45), WOOD))      # crosstrees
    if name != "mizzen":
        s.join(M.lathe([(lower_r * 0.36, top + tm_h - 1.0), (lower_r * 0.25, top + tm_h + 6.0), (0.12, top + tm_h + 6.2),
                        (0.0, top + tm_h + 6.3)], WOOD, n=8, center=(x + 0.55, 0, 0)))
        s.join(M.lathe([(0.0, top + tm_h + 6.25), (0.14, top + tm_h + 6.3), (0.0, top + tm_h + 6.45)], TRIM, n=8,
                       center=(x + 0.55, 0, 0)))                 # gilt truck
    return s


def yards(name):
    """Yard positions: (x, z, half length, radius) per yard of a mast."""
    x, top = MASTS[name]
    if name == "mizzen":
        return [(x + 0.55, top + 4.3, 4.6, 0.14), (x + 0.55, top + 7.6, 3.2, 0.1)]
    k = 1.0 if name == "main" else 0.9
    return [(x + 0.35, top - 1.3, 9.4 * k, 0.24), (x + 0.75, top + 4.2, 7.2 * k, 0.18),
            (x + 0.75, top + 9.2, 5.0 * k, 0.12), (x + 0.75, top + 13.6, 3.4 * k, 0.09)]


def yard_geo(name):
    s = M.Shape()
    for (x, z, hl, r) in yards(name):
        s.join(M.sweep([V(x, -hl, z), V(x, -hl * 0.5, z), V(x, 0, z), V(x, hl * 0.5, z), V(x, hl, z)],
                       [r * 0.5, r * 0.85, r, r * 0.85, r * 0.5], WOOD, n=6))
        for yy in (-hl * 0.95, hl * 0.95):
            s.join(tube((x, yy, z), (x, yy, z + 0.12), r * 0.6, METAL, n=6))
    if name == "mizzen":
        x, top = MASTS[name]
        zb = H.quarter_z(x) + 1.6
        s.join(M.sweep([V(x + 0.3, 0, zb), V(x - 8.5, 0, zb + 0.4)], [0.16, 0.1], WOOD, n=8))       # spanker boom
        s.join(M.sweep([V(x + 0.3, 0, top - 0.8), V(x - 6.0, 0, top + 2.2)], [0.13, 0.08], WOOD, n=8))  # gaff
    return s


def square_sail(xf, z_top, hl_top, z_bot, hl_bot, belly=0.9, nu=10, nv=8):
    """A set square sail hanging from its yard, filled by the wind from astern (bellying forward)."""
    s = M.Shape()
    grid = []
    for j in range(nv + 1):
        v = j / nv
        z = z_top - 0.25 - (z_top - 0.25 - z_bot) * v
        hl = hl_top + (hl_bot - hl_top) * v
        row = []
        for i in range(nu + 1):
            u = i / nu
            y = -hl + 2 * hl * u
            b = belly * math.sin(math.pi * u) * (math.sin(math.pi * min(v * 0.9 + 0.1, 1.0)) ** 0.8)
            foot = -0.35 * (1 - math.sin(math.pi * u)) * v ** 6        # the foot curves up between the clews
            row.append(s.vert((xf + b, y, z + foot * 0.0 + (0.35 * math.sin(math.pi * u) * v ** 8))))
        grid.append(row)
    for j in range(nv):
        for i in range(nu):
            q = [grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]]
            s.face(q, CANVAS)
            s.face(list(reversed(q)), CANVAS)
    return s


def sails_set(name):
    s = M.Shape()
    ys = yards(name)
    if name == "mizzen":
        x, top = MASTS[name]
        zb = H.quarter_z(x) + 1.6
        # spanker (gaff sail) between the gaff and the boom, slightly bellied to starboard
        g = M.Shape()
        rows = []
        for j in range(7):
            v = j / 6
            a = V(x + 0.2, 0, top - 0.9) .lerp(V(x + 0.2, 0, zb + 0.15), v)
            b = V(x - 5.9, 0, top + 2.1).lerp(V(x - 8.3, 0, zb + 0.5), v)
            rows.append([g.vert(a.lerp(b, i / 8) + V(0, -0.6 * math.sin(math.pi * i / 8) * math.sin(math.pi * v), 0))
                         for i in range(9)])
        for j in range(6):
            for i in range(8):
                q = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
                g.face(q, CANVAS)
                g.face(list(reversed(q)), CANVAS)
        s.join(g)
        (x1, z1, hl1, _), (x2, z2, hl2, _) = ys
        s.join(square_sail(x1 + 0.2, z2, hl2, z1 + 0.3, hl1 * 0.95, 0.6))
        return s
    for k in range(len(ys) - 1):
        x1, z1, hl1, _ = ys[k]
        x2, z2, hl2, _ = ys[k + 1]
        s.join(square_sail(x2 + 0.15, z2, hl2, z1 + 0.3, hl1 * 0.97, 0.7 + 0.25 * (k == 0)))
    x0, z0, hl0, _ = ys[0]
    s.join(square_sail(x0 + 0.15, z0, hl0, H.deck_z(x0) + 3.4 if name == "main" else H.fore_z(x0) + 1.6,
                       hl0 * 0.95, 1.1))                    # course
    return s


def sails_furled(name):
    s = M.Shape()
    for (x, z, hl, r) in yards(name):
        pts = [V(x + 0.05, -hl * 0.92 + 2 * hl * 0.92 * k / 12, z + 0.02 + 0.05 * math.sin(k * 1.7)) for k in range(13)]
        s.join(M.sweep(pts, lambda u: (r * 1.25 + 0.06) * (0.75 + 0.25 * math.sin(math.pi * u)), CANVAS, n=8))
    if name == "mizzen":
        x, top = MASTS[name]
        zb = H.quarter_z(x) + 1.6
        s.join(M.sweep([V(x + 0.1, 0, zb + 0.22), V(x - 8.0, 0, zb + 0.6)], [0.2, 0.12], CANVAS, n=8))
    return s


def head_sails(furled=False):
    """Jibs and fore-topmast staysail between the bowsprit and the fore topmast."""
    x, top = MASTS["fore"]
    p0 = V(H.stem_x(5.0) - 4.0, 0, H.fore_z(15) + 0.2)
    d = V(math.cos(math.radians(14)), 0, math.sin(math.radians(14)))
    s = M.Shape()
    for k, (along, head_z) in enumerate(((7.5, top + 8.6), (12.0, top + 12.2), (17.0, top + 15.6))):
        tack = p0 + d * along
        head = V(x + 0.75, 0, head_z)
        if furled:
            s.join(M.sweep([tack + V(0, 0, 0.15), tack.lerp(head, 0.18)], [0.16, 0.06], CANVAS, n=6))
            continue
        clew = tack.lerp(head, 0.15) + V(-3.2 - k * 0.6, -0.2, -3.6 - k * 0.6)
        tri = M.Shape()
        rows = []
        for j in range(6):
            v = j / 5
            a = head.lerp(tack, v)
            b = head.lerp(clew, v)
            rows.append([tri.vert(a.lerp(b, i / 5) + V(0, -0.45 * math.sin(math.pi * i / 5) * math.sin(math.pi * v * 0.9 + 0.1), 0))
                         for i in range(6)])
        for j in range(5):
            for i in range(5):
                q = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
                tri.face(q, CANVAS)
                tri.face(list(reversed(q)), CANVAS)
        s.join(tri)
    return s


def ribbon(a, b, w, slot=METAL, both=True):
    """A rope as a thin flat ribbon facing sideways (2 triangles; 4 with both sides)."""
    a, b = V(*a), V(*b)
    d = (b - a).normalized()
    side = d.cross(V(0, 0, 1))
    if side.length < 1e-3:
        side = V(1, 0, 0)
    side = side.normalized().cross(d).normalized() * (w / 2) if False else side.normalized() * (w / 2)
    s = M.Shape()
    q = [s.vert(a - side), s.vert(b - side), s.vert(b + side), s.vert(a + side)]
    s.face(q, slot)
    if both:
        s.face(list(reversed(q)), slot)
    return s


def rope(a, b, r, slot=METAL, lod=0):
    if lod >= 1:
        return ribbon(a, b, r * 2.2, slot)
    return M.sweep([V(*a), V(*b)], r, slot, n=3, caps=False)


def shrouds(name, side, lod=0):
    """One side of a mast's standing rigging: channel, deadeyes, shrouds, ratlines, topmast shrouds,
    backstay. lod 1 drops the ratlines and the deadeyes, lod 2 keeps every other shroud."""
    x, top = MASTS[name]
    s = M.Shape()
    n_sh = 6 if name != "mizzen" else 4
    tw = 2.0 if name != "mizzen" else 1.5
    zc = H.rail_z(x) - 0.4
    feet = [V(x - 2.4 + 3.2 * k / (n_sh - 1), 0, zc) for k in range(n_sh)]
    feet = [V(f.x, side * (H.half_breadth(f.x, zc) + 0.25), zc) for f in feet]
    heads = [V(x - 0.2 + (k - n_sh / 2) * 0.12, side * tw * 0.8, top) for k in range(n_sh)]
    yc = side * (H.half_breadth(x, zc) + 0.1)
    s.join(box((feet[0].x - 0.3, min(yc, yc + side * 0.3), zc - 0.08), (feet[-1].x + 0.3, max(yc, yc + side * 0.3), zc),
               WOOD))
    for k, (f, h) in enumerate(zip(feet, heads)):
        if lod >= 2 and k % 2:
            continue
        s.join(rope(f, h, 0.03, METAL, lod))
        if lod == 0:
            s.join(rope(f, f + V(0, 0, -1.6), 0.025, METAL, lod))
            s.join(M.blob(tuple(f + V(0, 0, 0.35)), 0.09, 0.09, 0.12, WOOD, nu=6, nv=4))
    if lod == 0:
        steps = int((top - zc) / 0.42)
        for r in range(1, steps):
            t = r / steps
            pts = [f.lerp(h, t) for f, h in zip(feet, heads)]
            for a, b in zip(pts[:-1], pts[1:]):
                s.join(ribbon(a, b + V(0, 0, 0.001), 0.025, CANVAS, both=True))
    for k in range(3 if lod == 0 else 1):
        a = V(x - 0.6 + k * 0.4, side * tw * 0.85, top + 0.4)
        b = V(x + 0.55, side * 0.3, top + (10.0 if name != "mizzen" else 8.0) - 0.6)
        s.join(rope(a, b, 0.022, METAL, lod))
    bx = x - 3.5
    s.join(rope(V(x + 0.55, side * 0.25, top + (9.0 if name != "mizzen" else 7.0)),
                V(bx, side * (H.half_breadth(bx, H.rail_z(bx)) + 0.2), H.rail_z(bx) - 0.4), 0.025, METAL, lod))
    return s


def stays(lod=0):
    """Fore-and-aft stays of all three masts, the head stays and the bobstay."""
    s = M.Shape()
    x, top = MASTS["main"]
    fx, ftop = MASTS["fore"]
    mx, mtop = MASTS["mizzen"]
    s.join(rope(V(x, 0, top - 0.2), V(fx, 0, H.fore_z(fx) + 1.0), 0.06, METAL, lod))
    s.join(rope(V(x + 0.55, 0, top + 9.6), V(fx + 0.4, 0, ftop + 0.3), 0.035, METAL, lod))
    s.join(rope(V(mx, 0, mtop - 0.2), V(x - 0.5, 0, H.deck_z(x) + 2.5), 0.045, METAL, lod))
    p0 = V(H.stem_x(5.0) - 4.0, 0, H.fore_z(15) + 0.2)
    d = V(math.cos(math.radians(14)), 0, math.sin(math.radians(14)))
    s.join(rope(V(fx, 0, ftop - 0.2), p0 + d * 2.5, 0.06, METAL, lod))
    for along, z in ((7.5, ftop + 8.6), (12.0, ftop + 12.2), (17.0, ftop + 15.6)):
        s.join(rope(V(fx + 0.75, 0, z), p0 + d * along, 0.025, METAL, lod))
    s.join(rope(p0 + d * 12.7, V(H.stem_x(0) - 0.3, 0, 0.6), 0.03, METAL, lod))
    return s


for _name in ("fore", "main", "mizzen"):
    _t = _name.title()

    @B.piece(LS, f"Bride_Mast_{_t}", kind="structure", phys="hull", li=3)
    def _mast(lod, name=_name):
        return None if lod else mast_geo(name)

    @B.piece(LS, f"Bride_Topmast_{_t}", kind="structure", phys="none", li=3)
    def _topmast(lod, name=_name):
        return None if lod else M.join(mast_geo(name, upper=True), yard_geo(name))

    @B.piece(LS, f"Bride_Sails_{_t}", kind="deco", phys="none", li=3)
    def _sails(lod, name=_name):
        return None if lod else sails_set(name)

    @B.piece(LS, f"Bride_Furled_{_t}", kind="deco", phys="none", li=1.5)
    def _furled(lod, name=_name):
        return None if lod else sails_furled(name)

    for _side, _tag in ((1, "P"), (-1, "S")):
        @B.piece(LS, f"Bride_Shrouds_{_t}_{_tag}", kind="deco", phys="none", li=2)
        def _shr(lod, name=_name, side=_side):
            if lod == 3:
                return shrouds(name, side, 2)
            return shrouds(name, side, lod)


@B.piece(LS, "Bride_Stays", kind="deco", phys="none", li=2)
def _stays(lod):
    return stays(min(lod, 1))


@B.piece(LS, "Bride_Sails_Head", kind="deco", phys="none", li=2)
def jibs(lod):
    return None if lod else head_sails(False)


@B.piece(LS, "Bride_Furled_Head", kind="deco", phys="none", li=0.6)
def jibs_furled(lod):
    return None if lod else head_sails(True)


def flag(w, h, at, slot=CANVAS, emblem=True):
    """A flag flying aft from its hoist at `at`, rippling; the Lord's hook and broken crown in gilt."""
    s = M.Shape()
    rows = []
    for j in range(7):
        v = j / 6
        rows.append([s.vert(V(at[0] - w * (i / 10), at[1] + 0.25 * math.sin(i * 0.9 + v) * (i / 10), at[2] - h * v))
                     for i in range(11)])
    for j in range(6):
        for i in range(10):
            q = [rows[j][i], rows[j][i + 1], rows[j + 1][i + 1], rows[j + 1][i]]
            s.face(q, slot)
            s.face(list(reversed(q)), slot)
    if emblem:
        cx, cz = at[0] - w * 0.45, at[2] - h * 0.5
        yy = at[1] + 0.25 * math.sin(4.5 + 0.5) * 0.45
        hook = [(cx + 0.35 * h * 0.25 * math.cos(a * math.pi / 8), yy + 0.03, cz - 0.1 * h + 0.25 * h * math.sin(a * math.pi / 8))
                for a in range(-10, 5)]
        s.join(M.sweep(hook + [(cx + 0.09 * h, yy + 0.03, cz + 0.32 * h)], 0.03 * h, TRIM, n=4))
        s.join(M.sweep(hook, 0.03 * h, TRIM, n=4).move(0, -0.06, 0))
        crown = [(cx - 0.18 * h + 0.36 * h * i / 6, yy + 0.04, cz + 0.3 * h + (0.1 * h if i % 2 == 0 else 0.0)) for i in range(7)]
        s.join(M.sweep(crown, 0.025 * h, TRIM, n=4))
    return s


@B.piece(LS, "Bride_Flag_Lord", kind="deco", phys="none", li=0.8)
def flag_lord(lod):
    if lod:
        return None
    x, top = MASTS["main"]
    z = top + 10.0 + 6.2
    return M.join(flag(4.2, 2.6, (x + 0.45, 0, z)), tube((x + 0.5, 0, z - 2.7), (x + 0.5, 0, z + 0.1), 0.02, WOOD))


@B.piece(LS, "Bride_Ensign", kind="deco", phys="none", li=0.8)
def ensign(lod):
    if lod:
        return None
    x = H.XS - 0.6
    zt = H.rail_z(H.XS)
    staff = M.sweep([V(x + 0.6, 0, zt - 0.4), V(x - 0.4, 0, zt + 4.4)], [0.07, 0.04], WOOD, n=8)
    return M.join(staff, flag(3.0, 1.9, (x - 0.35, 0, zt + 4.3)))


# ================================================================ guns and deck fittings
def gun():
    """A long 12-pounder on its truck carriage, pointing out along +Y (local)."""
    barrel = M.lathe([(0.0, -0.15), (0.13, -0.15), (0.18, 0.0), (0.2, 0.25), (0.19, 0.3), (0.17, 1.2), (0.15, 1.25),
                      (0.14, 2.05), (0.16, 2.1), (0.16, 2.2), (0.11, 2.2), (0.0, 2.15)], METAL, n=14)
    barrel.transform(Matrix.Rotation(math.radians(-90), 4, "X"))
    barrel.move(0, -0.45, 0.78)
    bot = M.Shape()
    bot.join(barrel)
    bot.join(M.lathe([(0.0, -0.2), (0.13, -0.2), (0.05, -0.33), (0.07, -0.42), (0.0, -0.44)], METAL, n=10)
             .transform(Matrix.Rotation(math.radians(-90), 4, "X")).move(0, -0.45, 0.78))
    for x in (-0.28, 0.28):            # carriage cheeks (stepped)
        cheek = M.Shape()
        prof = [(-0.75, 0.25), (0.45, 0.25), (0.45, 0.72), (0.1, 0.72), (0.1, 0.6), (-0.3, 0.6), (-0.3, 0.48),
                (-0.75, 0.48)]
        cheek = M.extrude([(y, z) for y, z in prof], -0.06, 0.06, WOOD)
        cheek.transform(Matrix.Rotation(math.radians(90), 4, "Y"))
        cheek.transform(Matrix.Rotation(math.radians(90), 4, "X") @ Matrix.Rotation(0, 4, "Z"))
        bot.join(box((x - 0.06, -0.75, 0.25), (x + 0.06, 0.45, 0.7), WOOD).deform(
            lambda v, x=x: v.__class__((v.x, v.y, min(v.z, 0.7 - max(0.0, -v.y - 0.1) * 0.25)))))
    bot.join(box((-0.34, -0.65, 0.18), (0.34, 0.4, 0.28), WOOD))
    for y in (-0.55, 0.3):
        bot.join(tube((-0.4, y, 0.17), (0.4, y, 0.17), 0.03, METAL, n=6))
        for x in (-0.36, 0.36):
            bot.join(M.lathe([(0.0, -0.05), (0.17, -0.05), (0.17, 0.05), (0.0, 0.05)], WOOD, n=12)
                     .transform(Matrix.Rotation(math.radians(90), 4, "Y")).move(x, y, 0.17))
    # breeching rope and tackle to the side
    bot.join(M.sweep(M.bezier3((-0.6, 0.35, 0.65), (-0.2, -0.9, 0.5), (0.2, -0.9, 0.5), (0.6, 0.35, 0.65), 10), 0.025,
                     CANVAS, n=5))
    return bot


for _k, _x in enumerate(H.PORTS_X):
    for _side, _tag in ((1, "P"), (-1, "S")):
        _z = H.deck_z(_x) + 0.05
        _y = _side * (H.inner_half_breadth(_x, _z + 0.8) - 1.3)

        @B.piece(LS, f"Bride_Gun_{_tag}{_k + 1}", kind="deco", phys="hull", li=0.6)
        def _gun(lod, x=_x, y=_y, z=_z, side=_side):
            if lod:
                return None
            g = gun()
            if side < 0:
                g.rotate(180)
            g.move(x, y, z)
            # the port lid, hinged up and painted red inside
            z1 = H.deck_z(x) + H.PORT_HEAD
            yl = side * (H.half_breadth(x, z1) + 0.04)
            lid = box((x - H.PORT_W / 2 - 0.04, -0.03, 0.0), (x + H.PORT_W / 2 + 0.04, 0.03, 0.82), TRIM)
            lid.transform(Matrix.Translation(V(0, yl, z1)) @ Matrix.Rotation(side * math.radians(-62), 4, "X"))
            return g.join(lid)


@B.piece(LS, "Bride_Helm", kind="furniture", phys="hull", li=1.2,
         seat=(-14.0 - 0.95, 0.0, H.at_deck(-14.95, 0.0, "quarter"), 0.0, "bride_helm"))
def helm(lod):
    """Double steering wheel with gilt hubs, the wheel box and the binnacle with its compass lamp."""
    if lod:
        return None
    x = -14.0
    z = H.at_deck(x, 0, "quarter")
    s = M.join(box((x - 0.25, -0.8, z), (x + 0.25, 0.8, z + 0.55), WOOD, 0.03),
               tube((x, -0.75, z + 1.2), (x, 0.75, z + 1.2), 0.07, WOOD, n=8))
    for y in (-0.6, 0.6):
        s.join(box((x - 0.1, y - 0.06, z + 0.5), (x + 0.1, y + 0.06, z + 1.25), WOOD))
        rim = [(x + 0.82 * math.cos(a * math.pi / 16) * 0.0, y, z + 1.2 + 0.82 * math.sin(a * math.pi / 16)) for a in range(32)]
        rim = [(x + 0.82 * math.cos(a * math.pi / 16), y, z + 1.2 + 0.82 * math.sin(a * math.pi / 16)) for a in range(32)]
        s.join(M.sweep(rim, 0.04, WOOD, n=6, closed=True))
        for k in range(10):
            a = k * math.pi / 5
            p_in = (x, y, z + 1.2)
            p_out = (x + 1.08 * math.cos(a), y, z + 1.2 + 1.08 * math.sin(a))
            s.join(M.sweep([V(*p_in), V(*p_out)], [0.03, 0.022], WOOD, n=6))
            s.join(M.blob(p_out, 0.035, 0.035, 0.05, WOOD, nu=8, nv=5))
        s.join(M.lathe([(0.0, -0.08), (0.16, -0.08), (0.16, 0.08), (0.0, 0.08)], TRIM, n=16)
               .transform(Matrix.Rotation(math.radians(90), 4, "X")).move(x, y, z + 1.2))
    bx = x + 1.6
    s.join(M.lathe([(0.0, 0.0), (0.32, 0.0), (0.3, 0.9), (0.38, 1.0), (0.36, 1.12), (0.0, 1.15)], WOOD, n=12, center=(bx, 0, z)))
    s.join(M.lathe([(0.0, 1.12), (0.28, 1.12), (0.3, 1.25), (0.16, 1.42), (0.0, 1.45)], TRIM, n=12, center=(bx, 0, z)))
    s.join(M.lathe([(0.0, 1.14), (0.2, 1.14), (0.2, 1.2), (0.0, 1.2)], GLOW, n=12, center=(bx, 0, z)))
    return s


@B.piece(LS, "Bride_Capstan", kind="deco", phys="hull", li=0.8)
def capstan(lod):
    if lod:
        return None
    x = -3.6
    z = H.at_deck(x, 0)
    s = M.lathe([(0.0, 0.0), (0.55, 0.0), (0.5, 0.15), (0.32, 0.3), (0.28, 0.8), (0.38, 0.95), (0.55, 1.05),
                 (0.55, 1.18), (0.0, 1.2)], WOOD, n=16, center=(x, 0, z))
    for k in range(8):
        s.join(box((x - 0.05, -0.04, z + 0.3), (x + 0.38, 0.04, z + 0.85), WOOD).rotate(k * 45, "Z", (x, 0, 0)))
    s.join(M.lathe([(0.0, 1.18), (0.22, 1.18), (0.2, 1.24), (0.0, 1.25)], TRIM, n=16, center=(x, 0, z)))
    return s


@B.piece(LS, "Bride_Bell", kind="deco", phys="none", li=0.5)
def bell(lod):
    """The ship's bell in its belfry at the break of the forecastle; touch it to strike the hour."""
    if lod:
        return None
    x = 10.3
    z = H.fore_z(x) + 0.1
    s = M.Shape()
    for y in (-0.45, 0.45):
        s.join(box((x - 0.07, y - 0.07, z), (x + 0.07, y + 0.07, z + 1.4), WOOD))
    s.join(M.sweep(M.bezier3((x, -0.55, z + 1.38), (x, -0.3, z + 1.75), (x, 0.3, z + 1.75), (x, 0.55, z + 1.38), 10),
                   0.07, TRIM, n=6))
    s.join(M.lathe([(0.0, 1.3), (0.06, 1.3), (0.1, 1.24), (0.13, 1.05), (0.19, 0.92), (0.2, 0.9), (0.0, 0.92)], TRIM, n=16,
                   center=(x, 0, z)))
    return s


@B.piece(LS, "Bride_Boat", kind="deco", phys="hull", li=1.2)
def boat(lod):
    """The captain's gig on the skid beams over the waist, upside-right, oars stowed."""
    if lod:
        return None
    cx, cz = 4.6, H.deck_z(4.6) + 2.6
    rings = []
    for k in range(13):
        t = k / 12
        x = cx - 3.2 + 6.4 * t
        w = 0.85 * math.sin(math.pi * t) ** 0.6
        d = 0.6 * math.sin(math.pi * t) ** 0.3
        rings.append([V(x, w * math.cos(a), cz - d * math.sin(a) + 0.1 * (2 * t - 1) ** 2)
                      for a in [math.pi * i / 8 for i in range(9)]])
    hull_b = M.loft(rings, PAINT, cap0=False, cap1=False, closed=False)
    hull_b.solidify(0.04, offset=0)
    s = M.join(hull_b)
    for k in range(4):
        x = cx - 1.8 + k * 1.2
        s.join(box((x - 0.12, -0.75, cz - 0.3), (x + 0.12, 0.75, cz - 0.25), WOOD))
    for y in (-0.25, 0.25):
        s.join(tube((cx - 2.6, y, cz - 0.2), (cx + 2.6, y, cz - 0.2), 0.03, WOOD, n=6))
    for x in (cx - 2.0, cx + 2.0):
        s.join(box((x - 0.12, -4.4, cz - 0.75), (x + 0.12, 4.4, cz - 0.55), WOOD))
        for y in (-4.2, 4.2):
            s.join(box((x - 0.1, y - 0.1, H.deck_z(x)), (x + 0.1, y + 0.1, cz - 0.55), WOOD))
    return s


# ================================================================ the great cabin
def cz(x, y=0.0):
    return H.at_deck(x, y)


@B.piece(LS, "Bride_Cabin_Table", kind="furniture", phys="hull", li=1.2)
def cabin_table(lod):
    """The Lord's table: a long mahogany board on turned legs, the chart of the Narrows, dividers,
    a silver candelabrum, a decanter and two glasses."""
    if lod:
        return None
    x, y = -15.4, 0.0
    z = cz(x)
    s = M.slab(M.rounded_rect(x, y, 3.0, 1.3, 0.12, 4), z + 0.74, z + 0.79, WOOD, r=0.015, seg=1)
    for dx in (-1.35, 1.35):
        for dy in (-0.5, 0.5):
            s.join(M.lathe([(0.0, 0.0), (0.06, 0.0), (0.05, 0.1), (0.07, 0.3), (0.04, 0.55), (0.05, 0.74), (0.0, 0.74)],
                           WOOD, n=10, center=(x + dx, y + dy, z)))
    chart = M.panel(M.rounded_rect(x - 0.3, y, 1.4, 0.95, 0.02, 1), z + 0.795, CANVAS)
    chart.deform(lambda v: v.__class__((v.x, v.y, v.z + 0.01 * math.sin(v.x * 9) * math.cos(v.y * 7))))
    s.join(chart)
    for k in range(5):
        a = k * 2 * math.pi / 5
        s.join(M.lathe([(0.0, 0.0), (0.012, 0.0), (0.012, 0.16), (0.0, 0.17)], CANVAS, n=6,
                       center=(x + 0.9 + 0.12 * math.cos(a), y + 0.12 * math.sin(a), z + 0.79 + 0.32)))
        s.join(M.lathe([(0.0, 0.17), (0.01, 0.17), (0.0, 0.22)], GLOW, n=5,
                       center=(x + 0.9 + 0.12 * math.cos(a), y + 0.12 * math.sin(a), z + 0.79 + 0.32)))
    s.join(M.lathe([(0.0, 0.0), (0.1, 0.0), (0.03, 0.08), (0.025, 0.28), (0.14, 0.3), (0.0, 0.32)], METAL, n=10,
                   center=(x + 0.9, y, z + 0.79)))
    s.join(M.lathe([(0.0, 0.0), (0.07, 0.0), (0.09, 0.08), (0.05, 0.2), (0.02, 0.3), (0.03, 0.34), (0.0, 0.34)], GLASS, n=12,
                   center=(x + 1.2, y - 0.4, z + 0.79)))
    return s


def chair(high=False):
    s = M.join(box((-0.24, -0.22, 0.42), (0.24, 0.24, 0.48), WOOD, 0.01),
               M.pillow(M.rounded_rect(0, 0.0, 0.44, 0.42, 0.05, 2), 0.48, 0.54, CANVAS, r=0.025, crown=0.008, levels=1))
    for x in (-0.2, 0.2):
        for y in (-0.18, 0.2):
            s.join(M.lathe([(0, 0), (0.025, 0), (0.03, 0.2), (0.022, 0.42), (0, 0.42)], WOOD, n=8, center=(x, y, 0)))
    hb = 1.35 if high else 0.95
    for x in (-0.2, 0.2):
        s.join(box((x - 0.025, 0.2, 0.48), (x + 0.025, 0.25, hb), WOOD))
    s.join(box((-0.24, 0.2, hb - 0.12), (0.24, 0.25, hb), TRIM if high else WOOD, 0.01))
    s.join(M.pillow(M.rounded_rect(0, 0.22, 0.36, 0.05, 0.02, 1), 0.6, hb - 0.15, CANVAS, r=0.015, crown=0.0, levels=1)
           .deform(lambda v: v.__class__((v.x, v.y, v.z))))
    return s


for _k, (_x, _y, _yaw, _high) in enumerate(((-17.3, 0.0, 90, True), (-15.9, 1.0, 180, False), (-14.9, 1.0, 180, False),
                                            (-15.9, -1.0, 0, False), (-14.9, -1.0, 0, False))):
    _z = cz(_x, _y)
    _seat = (0.0, 0.2, 0.54) if True else None
    _sx, _sy = math.cos(math.radians(_yaw)) * _seat[0] - math.sin(math.radians(_yaw)) * _seat[1], \
        math.sin(math.radians(_yaw)) * _seat[0] + math.cos(math.radians(_yaw)) * _seat[1]

    @B.piece(LS, f"Bride_Cabin_Chair_{_k + 1}", kind="furniture", phys="hull", li=0.5,
             seat=(_x + _sx, _y + _sy, _z + _seat[2], (_yaw - 90) % 360,
                   *(["bride_sit_upright", "bride_scribe", "bride_sit_relaxed"] if _high else
                     ["bride_sit_upright", "bride_sit_relaxed", "bride_guard"])))
    def _chair(lod, x=_x, y=_y, z=_z, yaw=_yaw, high=_high):
        if lod:
            return None
        return chair(high).rotate(yaw).move(x, y, z)


@B.piece(LS, "Bride_Cabin_Bed", kind="furniture", phys="hull", li=1.0,
         seat=(-11.3, H.inner_half_breadth(-10.6, 3.0) - 0.6, H.at_deck(-10.6, 3.0) + 0.68, 0.0, "bride_lounge",
               "bride_sit_curl"))
def cabin_bed(lod):
    """Box bed against the port side with heavy curtains and a fur throw."""
    if lod:
        return None
    x0, x1 = -11.9, -9.3
    y = H.inner_half_breadth(-10.6, 3.0) - 0.05
    z = cz(-10.6, y - 0.5)
    s = M.join(box((x0, y - 1.15, z), (x1, y, z + 0.5), WOOD, 0.02),
               M.pillow(M.rounded_rect((x0 + x1) / 2, y - 0.58, x1 - x0 - 0.12, 1.02, 0.08, 3), z + 0.5, z + 0.68, CANVAS,
                        r=0.05, crown=0.0, levels=1))
    s.join(M.pillow(M.rounded_rect(x0 + 0.35, y - 0.58, 0.45, 0.9, 0.08, 3), z + 0.66, z + 0.8, CANVAS, r=0.05, crown=0.02,
                    levels=1))
    for xx in (x0, x1):
        s.join(box((xx - 0.05, y - 1.2, z), (xx + 0.05, y - 1.1, z + 2.2), WOOD))
    s.join(box((x0 - 0.05, y - 1.2, z + 2.15), (x1 + 0.05, y, z + 2.25), TRIM))
    s.join(M.curtain([(x0 + 0.1, y - 1.15), (x0 + 0.7, y - 1.18)], z + 0.15, z + 2.12, CANVAS, folds=4, depth=0.05))
    s.join(M.curtain([(x1 - 0.7, y - 1.18), (x1 - 0.1, y - 1.15)], z + 0.15, z + 2.12, CANVAS, folds=4, depth=0.05))
    # bed position for the seat: the middle of the mattress
    return s


@B.piece(LS, "Bride_Cabin_Chest", kind="deco", phys="hull", li=0.6)
def cabin_chest(lod):
    if lod:
        return None
    x, y = -12.6, -2.9
    z = cz(x, y)
    s = M.join(box((x - 0.5, y - 0.3, z), (x + 0.5, y + 0.3, z + 0.48), WOOD, 0.02),
               M.sweep([V(x - 0.5, y, z + 0.48), V(x + 0.5, y, z + 0.48)], 0.3, WOOD, n=10,
                       profile=[(math.cos(a), max(0.0, math.sin(a)) * 0.6) for a in [k * math.pi / 6 for k in range(7)]]))
    for dx in (-0.32, 0.32):
        s.join(box((x + dx - 0.03, y - 0.31, z), (x + dx + 0.03, y + 0.31, z + 0.68), METAL))
    s.join(box((x - 0.06, y - 0.33, z + 0.3), (x + 0.06, y - 0.3, z + 0.42), TRIM))
    return s


@B.piece(LS, "Bride_Cabin_Lamp", kind="light", phys="none", li=0.4)
def cabin_lamp(lod):
    if lod:
        return None
    x = -15.4
    ztop = H.quarter_z(x) - 0.1
    s = M.join(tube((x, 0, ztop), (x, 0, ztop - 0.6), 0.008, METAL, n=4),
               M.lathe([(0.0, -0.95), (0.12, -0.95), (0.16, -0.8), (0.16, -0.68), (0.12, -0.62), (0.0, -0.6)], GLASS, n=8,
                       center=(x, 0, ztop)),
               M.lathe([(0.0, -0.93), (0.1, -0.93), (0.1, -0.68), (0.0, -0.66)], GLOW, n=8, center=(x, 0, ztop)),
               M.lathe([(0.0, -0.62), (0.18, -0.62), (0.06, -0.52), (0.0, -0.5)], METAL, n=8, center=(x, 0, ztop)))
    return s


@B.piece(LS, "Bride_Cabin_Rug", kind="deco", phys="none", li=0.4)
def cabin_rug(lod):
    if lod:
        return None
    x = -15.2
    r = M.slab(M.rounded_rect(x, 0, 4.4, 3.0, 0.1, 2), H.deck_z(x) + 0.005, H.deck_z(x) + 0.025, CANVAS, r=0.005, seg=1)
    r.deform(lambda v: v.__class__((v.x, v.y, v.z + 0.08 * (1 - (v.y / 4.5) ** 2))))
    return r


for _k, (_x, _y) in enumerate(((8.2, 2.3), (8.2, -2.3))):
    @B.piece(LS, f"Bride_Brig_Floor_{_k + 1}", kind="seat", phys="none", li=0.2,
             seat=(_x, _y, BRIG_Z, 0.0 if _y > 0 else 180.0, "bride_kneel", "bride_cage", "bride_dog", "bride_sit_curl"))
    def _bf(lod, x=_x, y=_y):
        if lod:
            return None
        return M.blob((x, y, BRIG_Z + 0.01), 0.45, 0.35, 0.03, CANVAS, nu=10, nv=4, flat=BRIG_Z)


def lanterns(spots):
    s = M.Shape()
    for x, y, z in spots:
        s.join(M.lathe([(0.0, -0.3), (0.1, -0.3), (0.13, -0.18), (0.12, -0.05), (0.0, 0.0)], GLASS, n=8, center=(x, y, z)))
        s.join(M.lathe([(0.0, -0.28), (0.08, -0.28), (0.08, -0.08), (0.0, -0.06)], GLOW, n=8, center=(x, y, z)))
        s.join(M.lathe([(0.0, -0.02), (0.14, -0.02), (0.04, 0.1), (0.0, 0.14)], METAL, n=8, center=(x, y, z)))
    return s

"""The three houses the Villa Core turns into. Each is one linkset (shell + furniture), standing on
the north part of the site (x -14.5..14.5, y -2..16.5), floor at z 0.45 on a stepped podium.

    NAUTILUS  white shell: a soft dome of white microcement with an oculus, curved glass to the
              pool, boucle and brass, a suspended fireplace.
    DUNE      sand house: a thick roof that undulates like dunes over an open courtyard with an
              olive tree, teak, linen, bronze glass.
    NOCTURNE  night house: a charcoal dome with an oculus and LED coves, black marble, velvet,
              a glowing onyx bar, smoked glass.
"""

import math

import vbuild as B
import vmesh as M
from furniture import catalogue as C
from vplace import band_phys, furn, glass_line, outline_arc, split_line

CX, CY, A, BB, E = 0.0, 7.0, 13.0, 8.0, 2.6
OUT = M.superellipse(CX, CY, A, BB, 96, E)
FL = 0.45                       # floor level
H = 3.45                        # wall / glass height (top)


def arc(t0, t1, n=48, inset=0.0):
    return outline_arc(CX, CY, A - inset, BB - inset, E, t0, t1, n)


def house(name, cfg):
    ls = name
    B.linkset(ls, f"{name}_Floor", label=cfg["label"], role="house")
    S = cfg["slots"]

    def podium_phys(_s):
        o = M.resample(OUT, 24)
        return [("slab", M.grow(o, 0.7), 0.0, 0.15), ("slab", M.grow(o, 0.35), 0.0, 0.30), ("slab", o, 0.0, FL)]

    @B.piece(ls, f"{name}_Floor", kind="structure", phys=podium_phys, li=7)
    def floor(lod):
        if lod:
            return None
        o = M.resample(OUT, 64)
        s = M.slab(M.grow(o, 0.7), 0.0, 0.15, "d_stone", top_slot="b_floor")
        s.join(M.slab(M.grow(o, 0.35), 0.15, 0.30, "d_stone", top_slot="b_floor"))
        s.join(M.slab(o, 0.30, FL, "d_stone", top_slot="b_floor"))
        s.join(M.extrude(M.grow(o, 0.72), 0.02, 0.05, "h_glow", cap0=False, cap1=False))     # step light
        return s

    # walls: north arc (plaster) with the entry gap on the east side; sides; glass to the south
    north = arc(18, 162, 56, inset=0.18)
    west = arc(162, 205, 16, inset=0.18)
    east = arc(-25, 18, 16, inset=0.18)

    @B.piece(ls, f"{name}_Wall_N", kind="structure", phys=lambda _s: band_phys(north, 0.32, FL, H, 4), li=5)
    def wall_n(lod):
        if lod:
            return None
        w = M.wall_band(north, 0.32, FL, H + 0.05, "a_plaster")
        w.join(M.wall_band(M.offset2d(north, 0.17, False), 0.02, FL, FL + 0.08, "c_wood"))   # skirting reveal
        return w

    @B.piece(ls, f"{name}_Wall_W", kind="structure", phys=lambda _s: band_phys(west, 0.32, FL, H, 3), li=1.5)
    def wall_w(lod):
        if lod:
            return None
        return M.wall_band(west, 0.32, FL, H + 0.05, "a_plaster")

    e_left, e_right = split_line(east, arc(0, 0, 2, 0.18)[0], 1.5)

    @B.piece(ls, f"{name}_Wall_E", kind="structure",
             phys=lambda _s: band_phys(e_left, 0.32, FL, H, 3) + band_phys(e_right, 0.32, FL, H, 3), li=1.5)
    def wall_e(lod):
        if lod:
            return None
        w = M.wall_band(e_left, 0.32, FL, H + 0.05, "a_plaster")
        w.join(M.wall_band(e_right, 0.32, FL, H + 0.05, "a_plaster"))
        # lintel over the entry
        mid = arc(-3.5, 3.5, 6, 0.18)
        w.join(M.wall_band(mid, 0.32, 2.6, H + 0.05, "a_plaster"))
        return w

    south = arc(205, 335, 64, inset=0.18)
    s_left, s_right = split_line(south, (CX, CY - BB + 0.18), 2.6)

    @B.piece(ls, f"{name}_Glass_S", kind="glass",
             phys=lambda _s: band_phys(s_left, 0.08, FL, H, 4) + band_phys(s_right, 0.08, FL, H, 4), li=4)
    def glass_s(lod):
        if lod:
            return None
        g = glass_line(s_left, FL, H, 2.4)
        g.join(glass_line(s_right, FL, H, 2.4))
        return g

    # the sliding door in the middle of the glass (the scripts slide it along X)
    @B.piece(ls, f"{name}_Door_S", kind="door", phys="box", li=0.6)
    def door_s(lod):
        if lod:
            return None
        y = CY - BB + 0.18 + 0.12
        g = M.vpanel([(-1.25, y), (1.25, y)], FL + 0.02, H - 0.04, "g_glass")
        for x in (-1.25, 1.25):
            g.join(M.sweep([M.V(x, y, FL), M.V(x, y, H - 0.03)], 0.035, "f_metal", n=4,
                           profile=[(1, 1), (-1, 1), (-1, -1), (1, -1)]))
        g.join(M.sweep([M.V(0.95, y - 0.05, 1.0), M.V(0.95, y - 0.05, 1.6)], 0.012, "f_metal", n=6))
        return g

    @B.piece(ls, f"{name}_Door_E", kind="door", phys="box", li=0.6)
    def door_e(lod):
        if lod:
            return None
        p = arc(0, 0, 2, 0.18)[0]
        w = M.rounded_box((p[0] - 0.07, p[1] - 0.72, FL + 0.01), (p[0] + 0.0, p[1] + 0.72, 2.58), "c_wood", r=0.01, seg=1)
        w.join(M.sweep([M.V(p[0] - 0.12, p[1] - 0.55, 0.9), M.V(p[0] - 0.12, p[1] - 0.55, 1.8)], 0.015, "f_metal", n=6))
        return w

    cfg["roof"](ls, name, S)

    # partitions: a curved plaster screen for the bedroom, a fluted glass screen for the bath
    bed_wall = M.catmull([(-12.2, 9.5), (-7.5, 9.25), (-3.2, 9.6)], 8, closed=False)
    bath_screen = M.catmull([(3.0, 10.6), (7.0, 10.9), (11.4, 10.6)], 8, closed=False)

    @B.piece(ls, f"{name}_Partition", kind="structure", phys=lambda _s: band_phys(bed_wall, 0.2, FL, 2.9, 3), li=1.2)
    def partition(lod):
        if lod:
            return None
        w = M.wall_band(bed_wall, 0.2, FL, 2.9, "a_plaster")
        w.join(M.wall_band(M.offset2d(bed_wall, -0.11, False), 0.01, 2.2, 2.24, "h_glow"))
        return w

    @B.piece(ls, f"{name}_Bath_Screen", kind="glass", phys="none", li=0.8)
    def screen(lod):
        if lod:
            return None
        return glass_line(bath_screen, FL, 2.6, 1.2)

    for fn in cfg["furniture"]:
        fn(ls, name)


# ------------------------------------------------------------------ roofs
def cove_ring():
    ring = M.resample(M.grow(OUT, -0.25), 48)
    return M.wall_band(ring + [ring[0]], 0.05, H - 0.06, H - 0.02, "h_glow")


def shell_roof(height, power, oculus, glow_ring=True):
    def make(ls, name, S):
        outline = M.grow(OUT, 0.55)

        @B.piece(ls, f"{name}_Roof", kind="structure", phys="none", li=9)
        def roof(lod):
            """Shell roof with its oculus glass, brass ring and the LED cove under the edge."""
            if lod:
                return None
            r = M.shell(M.resample(outline, 56), H, height, "a_plaster", rings=7, power=power, thickness=0.22,
                        inner_slot="a_plaster", open_top=oculus)
            u = (1 - oculus) * math.pi / 2
            sc = max(math.cos(u) ** (2 / power), 1e-3)
            z = H + height * math.sin(u) ** (2 / power)
            ring = [(CX + (p[0] - CX) * sc, CY + (p[1] - CY) * sc) for p in M.resample(outline, 32)]
            r.join(M.panel(ring, z + 0.01, "g_glass"))
            r.join(M.wall_band(ring + [ring[0]], 0.06, z - 0.02, z + 0.05, "f_metal"))
            if glow_ring:
                inner = M.grow(ring, -0.05)
                r.join(M.wall_band(inner + [inner[0]], 0.03, z - 0.08, z - 0.04, "h_glow"))
            r.join(cove_ring())
            return r
    return make


def dune_roof(ls, name, S):
    hole = M.superellipse(1.5, 7.2, 3.0, 2.4, 40, 2.4)

    @B.piece(ls, f"{name}_Roof", kind="structure", phys="none", li=9)
    def roof(lod):
        if lod:
            return None
        r = M.slab(M.resample(M.grow(OUT, 0.9), 64), H, H + 0.38, "a_plaster", r=0.12, seg=1)
        r.boolean(M.extrude(hole, H - 1, H + 2, "a_plaster"))
        r.deform(lambda v: v.__class__((v.x, v.y, v.z + 0.55 * max(0.0, math.sin(v.x * 0.42 + 0.6)) *
                                        (0.6 + 0.4 * math.cos(v.y * 0.35)))))
        r.join(cove_ring())
        return r

    @B.piece(ls, f"{name}_Courtyard", kind="plant", phys="none", li=2)
    def court(lod):
        if lod:
            return None
        t = C.olive_tree(3.6, seed=5).move(1.5, 7.2, FL)
        t.join(M.slab(hole, FL, FL + 0.12, "d_stone", r=0.03, seg=2, top_slot="b_floor").scale(0.9, 0.9, 1, center=(1.5, 7.2, FL)))
        return t



# ------------------------------------------------------------------ furniture sets
def lounge_orbit(ls, name, cx=-6.5, cy=5.2):
    furn(ls, f"{name}_Sofa", lambda: C.orbit_sofa(0, 0, r_in=1.6, a0=22, a1=158), cx, cy, FL,
         seat=(0, 2.22, 0.43, "villa_sit_relaxed", "villa_sit_crossed", "villa_sit_curl"))
    furn(ls, f"{name}_Coffee_Table", lambda: C.coffee_table(0.7, 0.5), cx, cy + 0.2, FL, kind="deco")
    furn(ls, f"{name}_Rug", lambda: C.rug(M.superellipse(0, 0, 2.9, 2.5, 48, 2.6)), cx, cy + 0.6, FL, kind="deco",
         phys="none")
    furn(ls, f"{name}_Books", lambda: C.books(4), cx - 0.25, cy + 0.15, FL + 0.34, kind="deco", phys="none")
    furn(ls, f"{name}_Vase", lambda: C.vase(0.36, 0.11), cx + 0.35, cy + 0.3, FL + 0.34, kind="deco", phys="none")
    furn(ls, f"{name}_Chair_1", C.lounge_chair, cx - 2.6, cy - 1.6, FL, yaw=-120,
         seat=(0, 0.12, 0.46, "villa_sit_relaxed", "villa_sit_crossed"))
    furn(ls, f"{name}_Chair_2", C.lounge_chair, cx + 2.6, cy - 1.6, FL, yaw=120,
         seat=(0, 0.12, 0.46, "villa_sit_relaxed", "villa_sit_crossed"))
    furn(ls, f"{name}_Arc_Lamp", C.floor_lamp_arc, cx + 3.1, cy + 2.4, FL, yaw=35, kind="light")


def lounge_straight(ls, name, cx=-6.5, cy=6.2, w=3.2):
    furn(ls, f"{name}_Sofa", lambda: C.sofa_frame(w), cx, cy, FL, yaw=0)
    for k, (lx, shape) in enumerate(C.sofa_seats(w)):
        furn(ls, f"{name}_Sofa_Seat_{k + 1}", lambda shape=shape: shape.copy(), cx, cy, FL, kind="seat",
             seat=(lx, 0.22, 0.43, "villa_sit_relaxed", "villa_sit_crossed", "villa_sit_curl"))
    furn(ls, f"{name}_Coffee_Table", lambda: C.coffee_table(0.8, 0.45), cx, cy - 1.35, FL, kind="deco")
    furn(ls, f"{name}_Rug", lambda: C.rug(M.rounded_rect(0, 0, 4.4, 3.2, 0.6, 6)), cx, cy - 1.0, FL, kind="deco",
         phys="none")
    furn(ls, f"{name}_Books", lambda: C.books(3), cx + 0.3, cy - 1.35, FL + 0.34, kind="deco", phys="none")
    furn(ls, f"{name}_Chair_1", C.lounge_chair, cx - 2.2, cy - 2.6, FL, yaw=-70,
         seat=(0, 0.12, 0.46, "villa_sit_relaxed", "villa_sit_crossed"))
    furn(ls, f"{name}_Chair_2", C.lounge_chair, cx + 2.2, cy - 2.6, FL, yaw=70,
         seat=(0, 0.12, 0.46, "villa_sit_relaxed", "villa_sit_crossed"))
    furn(ls, f"{name}_Arc_Lamp", C.floor_lamp_arc, cx + 2.4, cy + 0.6, FL, yaw=60, kind="light")


def fireplace(ls, name, x=-10.4, y=4.3):
    furn(ls, f"{name}_Fireplace", C.fireplace_suspended, x, y, FL, kind="light")


def dining(ls, name, cx=6.5, cy=4.6):
    furn(ls, f"{name}_Dining_Table", lambda: C.dining_table(2.6, 1.1), cx, cy, FL)
    spots = [(-0.75, -0.72, 180), (0.75, -0.72, 180), (-0.75, 0.72, 0), (0.75, 0.72, 0), (-1.62, 0, 90),
             (1.62, 0, -90)]
    for k, (dx, dy, yaw) in enumerate(spots):
        furn(ls, f"{name}_Dining_Chair_{k + 1}", C.dining_chair, cx + dx, cy + dy, FL, yaw=yaw,
             seat=(0, 0.17, 0.48, "villa_sit_upright", "villa_sit_crossed"))
    furn(ls, f"{name}_Dining_Light", lambda: C.pendant_ring(0.75, 2.35, H - FL), cx, cy, FL, kind="light", phys="none")


def kitchen(ls, name, cx=6.5, cy=8.9):
    furn(ls, f"{name}_Island", lambda: C.kitchen_island(3.4, 1.1), cx, cy, FL)
    for k, dx in enumerate((-0.9, 0.0, 0.9)):
        furn(ls, f"{name}_Stool_{k + 1}", C.bar_stool, cx + dx, cy - 0.95, FL, yaw=180,
             seat=(0, 0.0, 0.78, "villa_sit_stool"))
    for k, dx in enumerate((-1.0, 0.0, 1.0)):
        furn(ls, f"{name}_Island_Light_{k + 1}", lambda: C.pendant_globe(0.17, 1.05, H - FL), cx + dx, cy, FL,
             kind="light", phys="none")


def bar(ls, name, cx=7.6, cy=7.2):
    furn(ls, f"{name}_Bar", lambda: C.bar_counter(2.0, 200, 340), cx, cy + 2.4, FL, yaw=0)
    for k, a in enumerate((225, 255, 285, 315)):
        r = 3.1
        x, y = cx + r * math.cos(math.radians(a)), cy + 2.4 + r * math.sin(math.radians(a))
        furn(ls, f"{name}_Stool_{k + 1}", C.bar_stool, x, y, FL, yaw=a - 90 + 180,
             seat=(0, 0.0, 0.78, "villa_sit_stool"))
    furn(ls, f"{name}_Bar_Light", lambda: C.pendant_ring(1.1, 2.6, H - FL), cx, cy + 2.4, FL, kind="light", phys="none")


def bedroom(ls, name, cx=-6.5, cy=12.25):
    furn(ls, f"{name}_Bed", lambda: C.bed(2.0, 2.2), cx, cy, FL, seat=(0.45, 0.7, 0.6, "villa_lounge", "villa_sit_curl"))
    for k, dx in enumerate((-0.48, 0.48)):
        furn(ls, f"{name}_Pillow_{k + 1}", lambda: C.bed_pillow(0.6), cx + dx, cy + 0.82, FL, kind="seat",
             seat=(0, 0.1, 0.6, "villa_lounge", "villa_sit_relaxed"))
    for k, dx in enumerate((-1.45, 1.45)):
        furn(ls, f"{name}_Nightstand_{k + 1}", C.nightstand, cx + dx, cy + 0.85, FL, kind="deco")
        furn(ls, f"{name}_Bed_Lamp_{k + 1}", C.table_lamp, cx + dx, cy + 0.85, FL + 0.53, kind="light", phys="none")
    furn(ls, f"{name}_Bed_Rug", lambda: C.rug(M.rounded_rect(0, 0, 3.2, 2.4, 0.4, 5)), cx, cy - 0.6, FL, kind="deco",
         phys="none")


def bath(ls, name):
    furn(ls, f"{name}_Bathtub", lambda: C.bathtub(1.8, 0.85), 8.6, 12.4, FL, kind="furniture")
    furn(ls, f"{name}_Vanity", lambda: C.vanity(1.8), 4.9, 13.7, FL, kind="furniture")


def decor(ls, name, plants=((-12.0, 3.0), (12.0, 3.4), (-1.6, 13.4)), sculpture=(1.3, 3.8)):
    for k, (x, y) in enumerate(plants):
        furn(ls, f"{name}_Plant_{k + 1}", lambda k=k: C.plant(1.4 + 0.25 * (k % 2), 0.3, 12, seed=k + 7), x, y, FL,
             kind="plant", phys="none")
    furn(ls, f"{name}_Sculpture", lambda: C.sculpture(0.9), sculpture[0], sculpture[1], FL, kind="deco")


def _p(fn, *a):
    return (lambda ls, name, fn=fn, a=a: fn(ls, name, *a)),


HOUSES = {
    "Nautilus": {"label": "Nautilus - white shell", "slots": {},
                 "roof": shell_roof(1.5, 3.0, 0.22),
                 "furniture": [_p(lounge_orbit), _p(fireplace), _p(dining), _p(kitchen), _p(bedroom), _p(bath),
                               _p(decor)]},
    "Dune": {"label": "Dune - sand courtyard house", "slots": {},
             "roof": dune_roof,
             "furniture": [_p(lounge_straight), _p(dining, 7.0, 4.4), _p(kitchen, 7.0, 8.9), _p(bedroom), _p(bath),
                           _p(decor, ((-12.0, 3.0), (12.0, 3.4)), (-2.3, 4.2))]},
    "Nocturne": {"label": "Nocturne - night dome", "slots": {},
                 "roof": shell_roof(2.6, 2.2, 0.16),
                 "furniture": [_p(lounge_orbit, -6.0, 5.0), _p(fireplace, -10.6, 4.6), _p(bar), _p(bedroom),
                               _p(bath), _p(decor, ((-12.0, 3.0), (12.2, 3.6), (-1.6, 13.4)), (0.0, 3.2))]},
}

for _name, _cfg in HOUSES.items():
    _cfg["furniture"] = [f[0] for f in _cfg["furniture"]]
    house(_name, _cfg)

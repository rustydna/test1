"""Parametric furniture for the Villa (all real mesh, built with vmesh).

Every function returns a Shape in LOCAL coordinates: origin on the floor at the centre of the
item, the front (where a person sits or stands) towards -Y. place() turns and moves it into the
site. Seat heights: sofa 0.43, chair 0.46, stool 0.75, bed 0.55, lounger 0.38.
"""

import math

import vmesh as M
from furniture.reference import orbit_sofa  # noqa: F401  (re-exported)


def place(s, x, y, z=0.0, yaw=0.0):
    """yaw in degrees (0 = front towards -Y)."""
    if yaw:
        s.rotate(yaw)
    return s.move(x, y, z)


def rot2(x, y, yaw):
    a = math.radians(yaw)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a)


# ------------------------------------------------------------------ seating
def seat_cushion(w, d, z0=0.24, z1=0.43, slot="e_fabric"):
    """One tailored seat cushion (its own piece: each one is a seat in Second Life)."""
    p = M.soften(M.rounded_rect(0, 0, w, d, 0.07, 4), 0.02)
    s = M.pillow(p, z0, z1, slot, r=0.055, crown=0.02)
    line, z = M.seam_line(p, 0.055, (z0 + z1) / 2)
    return s.join(M.piping(line, z, slot, radius=0.006))


def sofa_frame(w, d=0.95, base="c_wood", fabric="e_fabric", arms=True):
    """Straight sofa without its seat cushions: floating plinth, back cushions, rounded arms."""
    parts = [M.slab(M.rounded_rect(0, 0.02, w - 0.12, d - 0.12, 0.08, 4), 0.0, 0.06, "f_metal", r=0.008, seg=1),
             M.slab(M.rounded_rect(0, 0, w, d, 0.1, 5), 0.06, 0.24, base, r=0.02, seg=2)]
    parts.append(M.extrude(M.grow(M.rounded_rect(0, 0.02, w - 0.12, d - 0.12, 0.08, 4), 0.012), 0.012, 0.018, "h_glow"))
    inner = w - (0.44 if arms else 0.0)
    n = max(1, round(inner / 0.95))
    bw = inner / n
    for k in range(n):
        cx = -inner / 2 + bw * (k + 0.5)
        p = M.soften(M.rounded_rect(cx, d / 2 - 0.14, bw - 0.03, 0.22, 0.08, 4), 0.02)
        back = M.pillow(p, 0.43, 0.88, fabric, r=0.08, crown=0.03)
        back.deform(lambda v: v.__class__((v.x, v.y + (v.z - 0.43) * 0.18, v.z)))
        parts.append(back)
    if arms:
        for sx in (-1, 1):
            x = sx * (w / 2 - 0.11)
            p = M.soften(M.rounded_rect(x, 0.02, 0.2, d - 0.06, 0.09, 4), 0.02)
            parts.append(M.pillow(p, 0.24, 0.66, fabric, r=0.09, crown=0.0))
    return M.join(*parts)


def sofa_seats(w, d=0.95, arms=True):
    """(x_local, shape) per seat cushion of sofa_frame(w, d)."""
    inner = w - (0.44 if arms else 0.0)
    n = max(1, round(inner / 0.8))
    cw = inner / n
    out = []
    for k in range(n):
        cx = -inner / 2 + cw * (k + 0.5)
        out.append((cx, seat_cushion(cw - 0.02, d - 0.32).move(cx, -0.1)))
    return out


def lounge_chair(fabric="e_fabric", shell="a_plaster", leg="f_metal"):
    """Cocoon lounge chair: a moulded shell that wraps the sitter, a tailored cushion, a slim
    brass swivel base."""
    parts = []
    rings = []
    for k, (z, sc) in enumerate(((0.30, 0.82), (0.36, 0.95), (0.55, 1.0), (0.78, 0.96), (0.95, 0.86))):
        ring = []
        for i in range(24):
            a = math.radians(-60 + 300 * i / 23)          # open at the front (-Y)
            r = 0.42 * sc
            ring.append(M.V(r * math.sin(a), r * math.cos(a) * 0.95 + 0.02, z - (0.12 if abs(a - math.pi) > 1.9 else 0)))
        rings.append(ring)
    sh = M.loft(rings, shell, cap0=False, cap1=False, closed=False)
    sh.solidify(0.035, offset=0)
    sh.smooth(1)
    parts.append(sh)
    parts.append(M.pillow(M.superellipse(0, -0.04, 0.34, 0.32, 24, 2.6), 0.30, 0.46, fabric, r=0.06, crown=0.02))
    parts.append(M.lathe([(0, 0.0), (0.26, 0.0), (0.27, 0.012), (0.2, 0.025), (0.035, 0.05), (0.03, 0.29),
                          (0.12, 0.30), (0, 0.31)], leg, n=28))
    return M.join(*parts)


def dining_chair(fabric="e_fabric", wood="c_wood"):
    """Upholstered dining chair with a curved back on four tapered wooden legs."""
    parts = [M.pillow(M.superellipse(0, 0, 0.24, 0.23, 24, 2.8), 0.40, 0.48, fabric, r=0.04, crown=0.012)]
    arc = [M.V(0.24 * math.sin(math.radians(a)), 0.2 + 0.06 * math.cos(math.radians(a)), 0)
           for a in range(-70, 71, 10)]
    back = M.loft([[p + M.V(0, 0, 0.5) for p in arc], [p + M.V(0, 0.03, 0.86) for p in arc]],
                  fabric, cap0=False, cap1=False, closed=False)
    back.solidify(0.06, offset=0)
    back.smooth(1)
    parts.append(back)
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        top = M.V(sx * 0.17, sy * 0.16, 0.41)
        foot = M.V(sx * 0.21, sy * 0.21, 0.0)
        parts.append(M.sweep([foot, top], [0.014, 0.022], wood, n=8))
    return M.join(*parts)


def bar_stool(fabric="e_fabric", metal="f_metal"):
    parts = [M.pillow(M.superellipse(0, 0, 0.2, 0.2, 24, 2.2), 0.7, 0.78, fabric, r=0.035, crown=0.01),
             M.lathe([(0, 0), (0.2, 0), (0.21, 0.01), (0.04, 0.03), (0.025, 0.68), (0.1, 0.7), (0, 0.705)],
                     metal, n=24),
             M.sweep([M.V(0.18 * math.cos(a * math.pi / 12), 0.18 * math.sin(a * math.pi / 12), 0.26)
                      for a in range(24)], 0.009, metal, n=6, closed=True)]
    return M.join(*parts)


def lounger(wood="c_wood", fabric="e_fabric"):
    """Outdoor chaise longue (2.0 x 0.75): a curved teak cradle and a tailored pad; head at +Y."""
    prof = [(0, -1.0, 0.30), (0, -0.4, 0.33), (0, 0.25, 0.35), (0, 0.55, 0.5), (0, 0.95, 0.78)]
    path = [M.V(*p) for p in prof]
    parts = []
    for sx in (-1, 1):
        parts.append(M.sweep([p + M.V(sx * 0.33, 0, -0.03) for p in path], 0.03, wood, n=8))
        parts.append(M.sweep([M.V(sx * 0.33, -0.85, 0), M.V(sx * 0.33, -0.85, 0.27)], 0.025, wood, n=8))
        parts.append(M.sweep([M.V(sx * 0.33, 0.55, 0), M.V(sx * 0.33, 0.55, 0.47)], 0.025, wood, n=8))
    rings = []
    for p in path:
        rings.append([p + M.V(x, 0, z) for x, z in ((-0.34, 0), (-0.36, 0.04), (-0.3, 0.08), (0.3, 0.08),
                                                     (0.36, 0.04), (0.34, 0))])
    pad = M.loft(rings, fabric, cap0=True, cap1=True)
    pad.smooth(1)
    parts.append(pad)
    return M.join(*parts)


def bed(w=2.0, l=2.2, wood="c_wood", fabric="e_fabric"):
    """Bed frame (floating plinth, upholstered wing headboard, mattress, duvet with soft folds).
    Head at +Y. The two pillows are separate pieces (bed_pillow) so each side is a seat."""
    parts = [M.slab(M.rounded_rect(0, 0, w - 0.2, l - 0.2, 0.1, 4), 0, 0.12, "f_metal", r=0.01, seg=1),
             M.extrude(M.grow(M.rounded_rect(0, 0, w - 0.2, l - 0.2, 0.1, 4), 0.012), 0.015, 0.021, "h_glow"),
             M.slab(M.rounded_rect(0, 0, w + 0.1, l + 0.1, 0.12, 5), 0.12, 0.3, wood, r=0.03, seg=2),
             M.pillow(M.rounded_rect(0, -0.02, w - 0.04, l - 0.14, 0.1, 4), 0.3, 0.52, "e_fabric", r=0.07, crown=0.0)]
    duvet = M.pillow(M.rounded_rect(0, -0.32, w + 0.04, l - 0.72, 0.06, 4), 0.49, 0.56, fabric, r=0.03, crown=0.012)
    duvet.deform(lambda v: v.__class__((v.x, v.y, v.z + 0.012 * math.sin(v.x * 7.0 + v.y * 2.0))))
    parts.append(duvet)
    # wing headboard: channel tufted, wraps slightly at the sides
    hb = M.arc_poly(0, -2.2 + l / 2, 2.2 + 0.0, 2.36, 90 - math.degrees((w + 0.5) / 2 / 2.2),
                    90 + math.degrees((w + 0.5) / 2 / 2.2), 16, round_ends=0.06)
    head = M.pillow(hb, 0.12, 1.3, fabric, r=0.06, crown=0.0)
    for v in head.bm.verts:
        if v.co.y < l / 2 and v.co.z > 0.35:
            k = abs(((v.co.x / 0.24) % 1) - 0.5) * 2
            v.co.y += 0.01 * max(0, 1 - k * 5)
    parts.append(head)
    return M.join(*parts)


def bed_pillow(w=0.62):
    p = M.soften(M.rounded_rect(0, 0, w, 0.42, 0.12, 4), 0.03)
    s = M.pillow(p, 0.52, 0.66, "e_fabric", r=0.06, crown=0.015)
    return s


def nightstand(wood="c_wood", stone="d_stone"):
    parts = [M.rounded_box((-0.27, -0.21, 0.12), (0.27, 0.21, 0.5), wood, r=0.03, seg=2),
             M.slab(M.rounded_rect(0, 0, 0.58, 0.45, 0.04, 3), 0.5, 0.53, stone, r=0.008, seg=1),
             M.sweep([M.V(-0.12, -0.215, 0.33), M.V(0.12, -0.215, 0.33)], 0.007, "f_metal", n=6)]
    parts += [M.extrude(M.rounded_rect(0, 0, 0.5, 0.38, 0.03, 2), 0.0, 0.12, "f_metal")]
    return M.join(*parts)


def daybed_round(r=1.25, wood="c_wood", fabric="e_fabric"):
    parts = [M.slab(M.superellipse(0, 0, r, r, 48, 2.0), 0, 0.28, wood, r=0.04, seg=2),
             M.pillow(M.superellipse(0, 0, r - 0.06, r - 0.06, 48, 2.0), 0.28, 0.46, fabric, r=0.07, crown=0.02)]
    back = M.arc_poly(0, 0, r - 0.32, r - 0.06, 20, 160, 20, round_ends=0.08)
    parts.append(M.pillow(back, 0.46, 0.85, fabric, r=0.08, crown=0.0))
    return M.join(*parts)


# ------------------------------------------------------------------ tables and fixtures
def coffee_table(a=0.65, b=0.5, h=0.34, stone="d_stone", base="f_metal"):
    """Pebble table: a thick stone top with soft edges floating on a recessed metal drum."""
    top = M.slab(M.superellipse(0, 0, a, b, 48, 2.6), h - 0.07, h, stone, r=0.03, seg=3)
    drum = M.slab(M.superellipse(0, 0, a * 0.62, b * 0.6, 40, 2.6), 0.0, h - 0.07, base, r=0.01, seg=1)
    return top.join(drum)


def side_table(r=0.24, h=0.5, stone="d_stone", metal="f_metal"):
    return M.join(M.slab(M.superellipse(0, 0, r, r, 32, 2.0), h - 0.03, h, stone, r=0.01, seg=1),
                  M.lathe([(0, 0), (r * 0.6, 0), (r * 0.6, 0.01), (0.03, 0.03), (0.025, h - 0.03), (0, h - 0.03)],
                          metal, n=24))


def dining_table(l=2.6, w=1.1, stone="d_stone", wood="c_wood"):
    """Racetrack stone top on two sculpted wooden pedestals that flare at the floor."""
    parts = [M.slab(M.rounded_rect(0, 0, l, w, w / 2, 8), 0.72, 0.76, stone, r=0.012, seg=2)]
    for sx in (-1, 1):
        rings = []
        for z, sc in ((0.0, 1.0), (0.05, 0.92), (0.3, 0.55), (0.55, 0.62), (0.72, 0.95)):
            rings.append(M.pts3(M.superellipse(sx * l * 0.27, 0, 0.32 * sc, 0.22 * sc, 24, 2.4), z))
        ped = M.loft(rings, wood)
        ped.smooth(1)
        parts.append(ped)
    return M.join(*parts)


def kitchen_island(l=3.4, w=1.1, wood="c_wood", stone="d_stone"):
    """Island with waterfall stone ends, fluted wood fronts, an integrated sink and brass tap,
    a flush cooktop and a glowing toe-kick."""
    parts = [M.extrude(M.rounded_rect(0, 0, l - 0.2, w - 0.2, 0.05, 2), 0.0, 0.1, "f_metal"),
             M.extrude(M.grow(M.rounded_rect(0, 0, l - 0.2, w - 0.2, 0.05, 2), 0.012), 0.01, 0.016, "h_glow"),
             M.rounded_box((-l / 2 + 0.06, -w / 2 + 0.06, 0.1), (l / 2 - 0.06, w / 2 - 0.06, 0.88), wood, r=0.01, seg=1)]
    # flutes on the front (seen from the room)
    for k in range(int((l - 0.2) / 0.06)):
        x = -l / 2 + 0.13 + k * 0.06
        parts.append(M.sweep([M.V(x, -w / 2 + 0.055, 0.12), M.V(x, -w / 2 + 0.055, 0.86)], 0.018, wood, n=6,
                             profile=[(math.cos(a), math.sin(a) * 0.5) for a in [i * math.pi / 3 for i in range(6)]]))
    top = M.slab(M.rounded_rect(0, 0, l, w, 0.02, 2), 0.88, 0.92, stone, r=0.006, seg=1)
    parts.append(top)
    for sx in (-1, 1):
        parts.append(M.rounded_box((sx * (l / 2 - 0.025) - 0.025, -w / 2, 0.0), (sx * (l / 2 - 0.025) + 0.025, w / 2, 0.9),
                                   stone, r=0.006, seg=1))
    # sink (dark recess) and tap
    parts.append(M.rounded_box((0.45, -0.18, 0.89), (1.05, 0.18, 0.921), "f_metal", r=0.04, seg=2))
    tap = M.sweep([M.V(0.75, 0.32, 0.92), M.V(0.75, 0.32, 1.2), M.V(0.75, 0.22, 1.28), M.V(0.75, 0.08, 1.2)],
                  0.012, "f_metal", n=8)
    parts.append(tap)
    # cooktop
    parts.append(M.rounded_box((-1.2, -0.27, 0.915), (-0.5, 0.27, 0.925), "g_glass", r=0.01, seg=1))
    return M.join(*parts)


def bar_counter(r=2.2, a0=200, a1=340, stone="d_stone"):
    """Curved bar: glowing onyx front (h_glow), stone top, metal foot rail."""
    poly = M.arc_poly(0, 0, r, r + 0.6, a0, a1, 24, round_ends=0.06)
    parts = [M.slab(poly, 0.0, 1.05, "h_glow", r=0.02, seg=1),
             M.slab(M.grow(poly, 0.04), 1.05, 1.1, stone, r=0.01, seg=1)]
    rail = M.arc(0, 0, r + 0.68, math.radians(a0 + 2), math.radians(a1 - 2), 24)
    parts.append(M.sweep([(x, y, 0.22) for x, y in rail], 0.018, "f_metal", n=8))
    return M.join(*parts)


def bathtub(l=1.8, w=0.85, stone="d_stone"):
    """Freestanding oval stone tub: soft outer belly, thin rim, deep basin (with water look)."""
    rings = []
    for z, sc in ((0.0, 0.9), (0.06, 0.97), (0.3, 1.0), (0.52, 0.97), (0.56, 0.95)):
        rings.append(M.pts3(M.superellipse(0, 0, l / 2 * sc, w / 2 * sc, 40, 2.3), z))
    for z, sc in ((0.55, 0.88), (0.2, 0.82), (0.12, 0.7)):
        rings.append(M.pts3(M.superellipse(0, 0, l / 2 * sc, w / 2 * sc, 40, 2.3), z))
    tub = M.loft(rings, stone, cap0=True, cap1=True)
    tub.smooth(1)
    return tub


def vanity(l=1.8, stone="d_stone", wood="c_wood"):
    parts = [M.rounded_box((-l / 2, -0.28, 0.5), (l / 2, 0.28, 0.8), wood, r=0.02, seg=2),
             M.slab(M.rounded_rect(0, 0, l + 0.02, 0.58, 0.02, 2), 0.8, 0.84, stone, r=0.006, seg=1),
             M.extrude(M.grow(M.rounded_rect(0, 0, l - 0.1, 0.5, 0.02, 2), 0.01), 0.49, 0.5, "h_glow")]
    for sx in (-0.45, 0.45):
        bowl = M.lathe([(0, 0.84), (0.2, 0.84), (0.21, 0.86), (0.2, 0.97), (0.19, 0.975), (0.17, 0.9), (0, 0.88)],
                       stone, n=32, center=(sx, -0.02, 0))
        parts.append(bowl)
        parts.append(M.sweep([M.V(sx, 0.24, 0.84), M.V(sx, 0.24, 1.12), M.V(sx, 0.12, 1.14)], 0.01, "f_metal", n=8))
        # round backlit mirror
        ring = [(sx + 0.36 * math.cos(a * math.pi / 24), 0.27, 1.55 + 0.36 * math.sin(a * math.pi / 24)) for a in range(48)]
        parts.append(M.sweep(ring, 0.015, "h_glow", n=6, closed=True))
        disc = M.Shape()
        vs = [disc.vert((sx + 0.34 * math.cos(a * math.pi / 24), 0.265, 1.55 + 0.34 * math.sin(a * math.pi / 24)))
              for a in range(48)]
        disc.face(vs, "g_glass")
        parts.append(disc)
    return M.join(*parts)


def fireplace_suspended(metal="f_metal"):
    """Suspended steel hood fireplace (Nordic 'cone') over a stone hearth disc with an ember bed."""
    hood = M.lathe([(0.0, 3.6), (0.09, 3.6), (0.09, 1.55), (0.42, 1.0), (0.45, 0.75), (0.42, 0.62), (0.36, 0.6),
                    (0.3, 0.64), (0.3, 0.98), (0.08, 1.45), (0.0, 1.45)], metal, n=40)
    hood.boolean(M.rounded_box((-0.5, -0.6, 0.66), (0.5, -0.15, 0.96), metal, r=0.12, seg=3))
    hearth = M.slab(M.superellipse(0, 0, 0.75, 0.75, 48, 2), 0.0, 0.12, "d_stone", r=0.02, seg=2)
    ember = M.lathe([(0, 0.66), (0.26, 0.66), (0.26, 0.7), (0, 0.72)], "h_glow", n=24)
    return M.join(hood, hearth, ember)


def firebowl(r=0.55, stone="d_stone"):
    bowl = M.lathe([(0, 0.0), (r * 0.6, 0.0), (r * 0.62, 0.02), (r, 0.36), (r, 0.4), (r - 0.06, 0.4),
                    (r - 0.08, 0.34), (0, 0.32)], stone, n=48)
    ember = M.lathe([(0, 0.33), (r - 0.09, 0.33), (r - 0.1, 0.36), (0, 0.38)], "h_glow", n=32)
    return bowl.join(ember)


def rug(poly, slot="e_fabric", h=0.02):
    return M.slab(poly, 0.0, h, slot, r=0.008, seg=1)


def pendant_globe(r=0.22, drop=1.2, z_ceiling=3.4, metal="f_metal"):
    """Opal globe on a fine cable from a brass canopy (origin at the floor)."""
    zc = z_ceiling - drop
    parts = [M.blob((0, 0, zc), r, r, r * 0.92, "h_glow", nu=24, nv=14),
             M.lathe([(0, zc + r * 0.85), (0.05, zc + r * 0.85), (0.04, zc + r + 0.05), (0, zc + r + 0.06)], metal, n=16),
             M.sweep([M.V(0, 0, zc + r + 0.05), M.V(0, 0, z_ceiling - 0.02)], 0.003, metal, n=4),
             M.lathe([(0, z_ceiling), (0.08, z_ceiling), (0.07, z_ceiling - 0.025), (0, z_ceiling - 0.03)], metal, n=16)]
    return M.join(*parts)


def pendant_ring(r=0.8, z=2.4, z_ceiling=3.4, metal="f_metal"):
    pts = [(r * math.cos(a * math.pi / 32), r * math.sin(a * math.pi / 32), z) for a in range(64)]
    parts = [M.sweep(pts, 0.035, metal, n=8, closed=True),
             M.sweep([(x, y, z - 0.03) for x, y, _ in pts], 0.015, "h_glow", n=6, closed=True)]
    for k in range(3):
        a = k * 2 * math.pi / 3
        parts.append(M.sweep([M.V(r * math.cos(a), r * math.sin(a), z), M.V(0, 0, z_ceiling - 0.02)], 0.003, metal, n=4))
    return M.join(*parts)


def floor_lamp_arc(metal="f_metal", stone="d_stone"):
    """Arc lamp: a marble foot, a brass arc reaching 1.9 m out, an opal dome shade."""
    base = M.slab(M.superellipse(0, 0, 0.2, 0.2, 32, 2), 0, 0.08, stone, r=0.02, seg=2)
    arc = M.bezier3((0, 0, 0.08), (0, 0, 2.3), (0, -1.6, 2.5), (0, -1.9, 1.95), 24)
    tube = M.sweep(arc, 0.012, metal, n=8)
    shade = M.lathe([(0, 2.02), (0.2, 2.0), (0.26, 1.88), (0.25, 1.86), (0.0, 1.9)], "h_glow", n=32, center=(0, -1.9, 0))
    return M.join(base, tube, shade)


def table_lamp(metal="f_metal"):
    return M.join(M.lathe([(0, 0), (0.09, 0), (0.1, 0.02), (0.025, 0.04), (0.02, 0.36), (0, 0.36)], metal, n=24),
                  M.blob((0, 0, 0.42), 0.13, 0.13, 0.11, "h_glow", nu=20, nv=10))


def vase(h=0.6, r=0.18, slot="d_stone"):
    return M.lathe([(0, 0), (r * 0.6, 0), (r, h * 0.35), (r * 0.85, h * 0.7), (r * 0.35, h * 0.92),
                    (r * 0.4, h), (r * 0.33, h), (r * 0.28, h * 0.94), (0, h * 0.9)], slot, n=32)


def sculpture(h=0.9, slot="f_metal"):
    """Abstract loop: a twisted ribbon that rises and closes on itself, on a stone plinth."""
    pts = []
    for i in range(48):
        t = i / 48 * 2 * math.pi
        pts.append((0.22 * math.sin(t), 0.08 * math.sin(2 * t), 0.15 + h * 0.5 * (1 - math.cos(t)) * 0.5 + 0.2))
    ribbon = M.sweep(pts, 0.03, slot, closed=True, profile=[(1.6 * math.cos(a), 0.4 * math.sin(a))
                                                            for a in [k * math.pi / 4 for k in range(8)]], twist=math.pi)
    plinth = M.rounded_box((-0.18, -0.18, 0), (0.18, 0.18, 0.18), "d_stone", r=0.01, seg=1)
    return ribbon.join(plinth)


def books(n=4, slot="c_wood"):
    parts = []
    z = 0.0
    for k in range(n):
        h = 0.03 + 0.012 * ((k * 7) % 3)
        w, d = 0.3 - 0.02 * (k % 2), 0.22 + 0.01 * (k % 3)
        parts.append(M.rounded_box((-w / 2, -d / 2, z), (w / 2, d / 2, z + h), "e_fabric" if k % 2 else slot,
                                   r=0.004, seg=1).rotate(7 * ((k * 3) % 5 - 2)))
        z += h
    return M.join(*parts)


def plant(h=1.4, pot_r=0.32, leaves=11, seed=1, pot="d_stone"):
    """Sculptural plant: a stone pot and long arching blade leaves (e_fabric: tinted green by the
    scripts on plant pieces)."""
    parts = [M.lathe([(0, 0), (pot_r * 0.75, 0), (pot_r, pot_r * 1.2), (pot_r * 0.95, pot_r * 1.25),
                      (pot_r * 0.9, pot_r * 1.15), (0, pot_r * 1.1)], pot, n=32)]
    top = pot_r * 1.15
    for k in range(leaves):
        a = 2 * math.pi * (k / leaves + 0.13 * math.sin(seed * 7 + k * 3.1))
        lean = 0.25 + 0.35 * ((k * 37 + seed * 11) % 10) / 10
        L = h * (0.65 + 0.35 * ((k * 53 + seed) % 7) / 7)
        p0 = M.V(0.03 * math.cos(a), 0.03 * math.sin(a), top)
        p1 = p0 + M.V(math.cos(a) * lean * 0.3 * L, math.sin(a) * lean * 0.3 * L, L * 0.55)
        p2 = p0 + M.V(math.cos(a) * lean * 0.75 * L, math.sin(a) * lean * 0.75 * L, L * 0.85)
        p3 = p0 + M.V(math.cos(a) * lean * 1.1 * L, math.sin(a) * lean * 1.1 * L, L * 0.7)
        path = M.bezier3(p0, p1, p2, p3, 10)
        prof = [(math.cos(t) * 1.0, math.sin(t) * 0.18) for t in [i * math.pi / 3 for i in range(6)]]
        parts.append(M.sweep(path, lambda u: 0.045 * math.sin(math.pi * min(u * 1.15 + 0.08, 1.0)) + 0.004,
                             "e_fabric", n=6, profile=prof, twist=0.6))
    return M.join(*parts)


def olive_tree(h=3.2, seed=3):
    """Stylised olive: a twisting trunk that splits in three, and soft canopy clouds."""
    parts = []
    trunk = M.bezier3((0, 0, 0), (0.25, 0.1, 0.8), (-0.2, 0.0, 1.4), (0.05, 0.05, 1.8), 12)
    parts.append(M.sweep(trunk, lambda u: 0.16 - 0.08 * u, "c_wood", n=10))
    for k in range(3):
        a = k * 2.1 + seed
        end = M.V(0.9 * math.cos(a), 0.9 * math.sin(a), h - 0.6 - 0.2 * k)
        br = M.bezier3((0.05, 0.05, 1.75), (0.3 * math.cos(a), 0.3 * math.sin(a), 2.1), end * 0.8, end, 10)
        parts.append(M.sweep(br, lambda u: 0.08 - 0.05 * u, "c_wood", n=8))
        cl = M.blob(tuple(end + M.V(0, 0, 0.15)), 0.75, 0.65, 0.42, "e_fabric", nu=14, nv=8, e=2.0)
        cl.smooth(1)
        parts.append(cl)
    parts.append(M.slab(M.superellipse(0, 0, 0.7, 0.7, 32, 2), 0, 0.04, "b_floor", r=0.01, seg=1))
    return M.join(*parts)


def bollard(h=0.7, metal="f_metal"):
    return M.join(M.lathe([(0, 0), (0.07, 0), (0.07, h - 0.12), (0.065, h - 0.1), (0, h - 0.1)], metal, n=20),
                  M.lathe([(0, h - 0.1), (0.068, h - 0.1), (0.068, h), (0, h)], "h_glow", n=20))

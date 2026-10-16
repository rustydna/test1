"""Reference piece: the quality bar for every furniture builder.

A curved lounge sofa ("Orbit"): a walnut plinth that floats on a recessed brass-lined shadow
gap, three tailored seat cushions with welted seams, a continuous curved back with channel
tufting, bolster arms, and a cast-glow LED line under the plinth. Built from cages that are
smoothed, so every silhouette is soft and continuous.
"""

import math

import vmesh as M


def orbit_sofa(cx=0.0, cy=0.0, r_in=1.55, depth=0.95, a0=205.0, a1=335.0, seats=3, lod=0):
    """Curved sofa centred on (cx, cy): the seat faces the centre. Returns a Shape."""
    q = 1 if lod == 0 else 0
    r_out = r_in + depth
    n = 28 if lod == 0 else 12
    parts = []
    # plinth (wood) on a set-back shadow base (metal) with a glow line
    base = M.arc_poly(cx, cy, r_in + 0.06, r_out - 0.06, a0 + 1.5, a1 - 1.5, n, round_ends=0.1)
    parts.append(M.slab(base, 0.0, 0.07, "f_metal", r=0.01, seg=1))
    if lod == 0:
        glow = M.grow(base, 0.012)
        parts.append(M.extrude(glow, 0.012, 0.018, "h_glow"))
    plinth = M.arc_poly(cx, cy, r_in, r_out, a0, a1, n, round_ends=0.14)
    parts.append(M.slab(plinth, 0.07, 0.24, "c_wood", r=0.025, seg=2 if q else 1))
    # seat cushions, each a tailored pillow with a welt
    gap = 1.2
    span = (a1 - a0 - 10) / seats
    for k in range(seats):
        s0 = a0 + 5 + k * span + gap / 2
        s1 = s0 + span - gap
        p = M.arc_poly(cx, cy, r_in + 0.03, r_out - 0.3, s0, s1, 10 if q else 5, round_ends=0.08)
        cush = M.pillow(p, 0.24, 0.43, "e_fabric", r=0.055, crown=0.02, levels=2 if q else 0)
        parts.append(cush)
        if lod == 0:
            line, z = M.seam_line(p, 0.055, (0.24 + 0.43) / 2)
            parts.append(M.piping(line, z, "e_fabric", radius=0.006))
    # continuous back: a swept, softened band that leans back 12 degrees, channel-tufted
    back_r = r_out - 0.16
    pts = []
    m = 36 if q else 12
    for i in range(m + 1):
        a = math.radians(a0 + 2 + (a1 - a0 - 4) * i / m)
        pts.append((cx + back_r * math.cos(a), cy + back_r * math.sin(a)))
    prof = M.soften(M.rounded_rect(0, 0, 0.26, 0.5, 0.11, 4), 0.02)       # back section (radial x height)
    rings = []
    for (x, y) in pts:
        rad = math.atan2(y - cy, x - cx)
        ux, uy = math.cos(rad), math.sin(rad)
        ring = []
        for (px, pz) in prof:
            lean = (pz + 0.25) * math.tan(math.radians(12))
            ring.append(M.V(x + ux * (px + lean), y + uy * (px + lean), 0.43 + 0.25 + pz))
        rings.append(ring)
    back = M.loft(rings, "e_fabric", fan=True)
    if lod == 0:
        # channel tufting: shallow vertical grooves every ~32 cm on the front face
        step = 0.32
        L = math.radians(a1 - a0) * back_r
        for v in back.bm.verts:
            rad = math.atan2(v.co.y - cy, v.co.x - cx)
            d = math.hypot(v.co.x - cx, v.co.y - cy)
            if d < back_r + 0.02 and v.co.z > 0.5:
                s = (math.degrees(rad) % 360 - a0) / (a1 - a0) * L
                f = abs((s / step) % 1 - 0.5) * 2
                k = max(0.0, 1 - f * 6)
                v.co.x += math.cos(rad) * 0.012 * k
                v.co.y += math.sin(rad) * 0.012 * k
        back.smooth(1)
    parts.append(back)
    # bolster arms at both ends
    for a, sgn in ((a0 + 1.5, 1), (a1 - 1.5, -1)):
        rad = math.radians(a)
        p0 = M.V(cx + (r_in + 0.12) * math.cos(rad), cy + (r_in + 0.12) * math.sin(rad), 0.52)
        p1 = M.V(cx + (r_out - 0.2) * math.cos(rad), cy + (r_out - 0.2) * math.sin(rad), 0.56)
        path = [p0.lerp(p1, t) for t in (0, 0.33, 0.66, 1)]
        bol = M.sweep(path, lambda u: 0.11 * (0.92 + 0.08 * math.sin(u * math.pi)), "e_fabric", n=16 if q else 8)
        if lod == 0:
            bol.smooth(1)
        parts.append(bol)
    return M.join(*parts)

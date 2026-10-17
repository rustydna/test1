"""Small helpers shared by the site and the houses: furniture placement with seats, physics for
curved walls and glass, outline arcs."""

import math

import vbuild as B
import vmesh as M
from furniture import catalogue as C


def furn(ls, name, fn, x, y, z=0.0, yaw=0.0, kind="furniture", seat=None, phys="hull", li=None):
    """Registers a furniture piece built by fn() in local coordinates, placed at (x, y, z) turned
    by yaw degrees. seat = (lx, ly, lz, pose, pose...) in the item's local frame: the seat top at
    the foot of the back; the sitter faces the item's front (-Y)."""
    meta = {}
    if seat:
        lx, ly, lz, *poses = seat
        sx, sy = C.rot2(lx, ly, yaw)
        meta["seat"] = (x + sx, y + sy, z + lz, (yaw - 90.0) % 360.0, *poses)
    if li:
        meta["li"] = li

    @B.piece(ls, name, kind=kind, phys=phys, **meta)
    def _build(lod, fn=fn, x=x, y=y, z=z, yaw=yaw):
        if lod:
            return None
        return C.place(fn(), x, y, z, yaw)
    return _build


def outline_arc(cx, cy, a, b, e, t0, t1, n):
    """Points of a superellipse outline between parameter angles t0..t1 (degrees)."""
    out = []
    for i in range(n):
        t = math.radians(t0 + (t1 - t0) * i / (n - 1))
        ct, st = math.cos(t), math.sin(t)
        out.append((cx + a * math.copysign(abs(ct) ** (2 / e), ct), cy + b * math.copysign(abs(st) ** (2 / e), st)))
    return out


def band_phys(line, thickness, z0, z1, every=1):
    """Physics for a curved wall/glass line: one thin convex prism per segment."""
    items = []
    a = M.offset2d(line, thickness / 2, False)
    b = M.offset2d(line, -thickness / 2, False)
    for i in range(0, len(line) - 1, every):
        j = min(i + every, len(line) - 1)
        pts = [M.V(p[0], p[1], z) for p in (a[i], a[j], b[i], b[j]) for z in (z0, z1)]
        items.append(("hull", pts))
    return items


def glass_line(line, z0, z1, mullion_every=2.4, glass="g_glass", metal="f_metal", frame=0.04):
    """Curved glass facade: a two-sided glass sheet, slim mullions, a head and a sill."""
    total = sum(math.dist(line[i], line[i + 1]) for i in range(len(line) - 1))
    line = M.resample(line, max(4, int(total / 0.9)), closed=False)
    g = M.vpanel(line, z0, z1, glass, two_sided=True)
    n = max(1, int(total / mullion_every))
    pts = M.resample(line, n + 1, closed=False)
    for p in pts:
        g.join(M.sweep([M.V(p[0], p[1], z0), M.V(p[0], p[1], z1)], frame, metal, n=6,
                       profile=[(1, 1), (-1, 1), (-1, -1), (1, -1)]))
    for z in (z0 + 0.02, z1 - 0.02):
        g.join(M.sweep([M.V(p[0], p[1], z) for p in line], frame, metal, n=4,
                       profile=[(1, 1), (-1, 1), (-1, -1), (1, -1)]))
    return g


def split_line(line, gap_center, gap_w):
    """Splits a polyline around a gap of width gap_w centred on the point nearest gap_center."""
    pts = M.resample(line, 160, closed=False)
    k = min(range(len(pts)), key=lambda i: math.dist(pts[i], gap_center))
    acc = [0.0]
    for i in range(1, len(pts)):
        acc.append(acc[-1] + math.dist(pts[i - 1], pts[i]))
    s0, s1 = acc[k] - gap_w / 2, acc[k] + gap_w / 2
    left = [p for p, s in zip(pts, acc) if s <= s0]
    right = [p for p, s in zip(pts, acc) if s >= s1]
    return left, right

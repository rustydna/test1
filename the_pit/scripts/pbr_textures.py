"""Procedural PBR textures for The Pit (tileable, seamless).

Using only numpy + pillow, generates one PBR set per material:

  output/textures/<Material>_basecolor.png   sRGB
  output/textures/<Material>_normal.png      glTF (OpenGL, +Y up)
  output/textures/<Material>_orm.png         glTF (R occlusion, G roughness, B metallic)
  output/textures/_swatches.png              contact sheet with the 8 basecolor maps
  output/pbr_materials/<Material>.glb        glTF 2.0 material (with a quad) for the
                                             Second Life PBR material uploader

All the noise lives on a torus: white noise filtered in frequency with an FFT,
Voronoi with wrapped neighbours and periodic offsets. So every image matches
edge to edge by construction (and this is checked numerically at the end).
The physical scale follows geo.UV_TILE: one repeat of Stone is 2 m, of Iron
0.5 m, etc., and the relief is computed in real metres so the normals come out
with the correct slope.

Usage:  python the_pit/scripts/pbr_textures.py
"""

import io
import json
import math
import os
import struct
import sys
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from geo import UV_TILE  # noqa: E402  (imports bpy, but we only use the scale table)

ROOT = os.path.dirname(HERE)
TEX_DIR = os.path.join(ROOT, "output", "textures")
GLB_DIR = os.path.join(ROOT, "output", "pbr_materials")
N = 1024
# The order matters: each material's seed is SEED + its index in this list.
PBR_MATERIALS = ["Stone", "Floor", "Wood", "Iron", "Cloth", "Bone", "Straw", "Water"]
SEED = 1666

# ---------------------------------------------------------------------------
# Periodic noise tools
# ---------------------------------------------------------------------------
_FY = np.fft.fftfreq(N)[:, None] * N     # cycles per repeat (rows)
_FX = np.fft.rfftfreq(N)[None, :] * N    # cycles per repeat (columns)
_C = (np.arange(N) + 0.5) / N
U, V = np.meshgrid(_C, _C)               # U horizontal, V vertical (V=0 at the top of the image)


def _s(x, a, b):
    """smoothstep."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    t = np.asarray(t, dtype=float)
    if t.ndim == 2 and (a.ndim in (1, 3) or b.ndim in (1, 3)):   # RGB colour blend
        t = t[..., None]
    return a + (b - a) * t


def noise(rng, f0=1.0, f1=64.0, p=1.0, aniso=1.0, ang=0.0):
    """Periodic fractal noise (mean 0, standard deviation 1).

    White noise filtered in frequency with amplitude ~ 1/f^p between f0 and f1 (cycles
    per repeat, with soft roll-offs): tileable by construction. `aniso` > 1 stretches
    it along the angle `ang` (radians, 0 = horizontal, pi/2 = vertical)."""
    c, s = math.cos(ang), math.sin(ang)
    along = _FX * c + _FY * s
    across = -_FX * s + _FY * c
    f = np.sqrt((along * aniso) ** 2 + across ** 2)
    f = np.maximum(f, 1e-6)
    amp = f ** -p * (1.0 - np.exp(-(f / f0) ** 4)) * np.exp(-(f / f1) ** 2)
    amp[0, 0] = 0.0
    out = np.fft.irfft2(np.fft.rfft2(rng.standard_normal((N, N))) * amp, s=(N, N))
    return (out - out.mean()) / (out.std() + 1e-12)


def blur(x, sigma):
    """Periodic Gaussian blur (sigma in pixels)."""
    if x.ndim == 3:
        return np.stack([blur(x[..., i], sigma) for i in range(x.shape[2])], -1)
    g = np.exp(-2.0 * (math.pi * sigma / N) ** 2 * (_FX ** 2 + _FY ** 2))
    return np.fft.irfft2(np.fft.rfft2(x) * g, s=x.shape)


def voronoi(rng, cells, u, v, jitter=0.9):
    """Periodic Voronoi of cells x cells points.

    Returns (f1, edge, ident): distance to the nearest point, exact distance to the
    cell edge (both in cell units) and cell index."""
    pts = 0.5 + (rng.random((cells, cells, 2)) - 0.5) * jitter
    gu, gv = u * cells, v * cells
    iu, iv = np.floor(gu).astype(np.int32), np.floor(gv).astype(np.int32)
    fu, fv = (gu - iu).astype(np.float32), (gv - iv).astype(np.float32)
    f1 = np.full(u.shape, 9.0, np.float32)
    ru = np.zeros(u.shape, np.float32)
    rv = np.zeros(u.shape, np.float32)
    ident = np.zeros(u.shape, np.int32)
    neighbors = []
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cu, cv = (iu + di) % cells, (iv + dj) % cells
            du = di + pts[cv, cu, 0].astype(np.float32) - fu
            dv = dj + pts[cv, cu, 1].astype(np.float32) - fv
            neighbors.append((du, dv))
            d = du * du + dv * dv
            m = d < f1
            f1 = np.where(m, d, f1)
            ru = np.where(m, du, ru)
            rv = np.where(m, dv, rv)
            ident = np.where(m, cv * cells + cu, ident)
    edge = np.full(u.shape, 9.0, np.float32)
    for du, dv in neighbors:
        eu, ev = du - ru, dv - rv
        l2 = eu * eu + ev * ev
        dist = ((ru + du) * 0.5 * eu + (rv + dv) * 0.5 * ev) / np.sqrt(np.maximum(l2, 1e-10))
        edge = np.where(l2 > 1e-8, np.minimum(edge, dist), edge)
    return np.sqrt(f1), edge, ident


def _wrap(x):
    """Periodic difference in [-0.5, 0.5)."""
    return (x + 0.5) % 1.0 - 0.5


def _rounded(t):
    """Worn edge profile: 0 at the arris, 1 on the face."""
    t = np.clip(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 2


# ---------------------------------------------------------------------------
# Materials. Each one returns sRGB colour (0..1), height in metres, roughness,
# metallic and the typical depth (m) for the occlusion.
# ---------------------------------------------------------------------------
def stone(rng):
    t = UV_TILE["Stone"]                          # 2 m per repeat
    u = (U + 0.0035 * noise(rng, 2, 24, 1.3)) % 1.0
    v = (V + 0.0035 * noise(rng, 2, 24, 1.3)) % 1.0
    # Irregular ashlar: 5 courses of ~0.4 m and blocks of 0.5-0.85 m.
    ncourses = 5
    heights = rng.uniform(0.88, 1.12, ncourses)
    course_edges = np.concatenate([[0.0], np.cumsum(heights / heights.sum())])
    course = np.clip(np.searchsorted(course_edges, v, side="right") - 1, 0, ncourses - 1)
    dist = np.zeros_like(u)
    ident = np.zeros(u.shape, np.int32)
    for r in range(ncourses):
        widths = []
        while sum(widths) < 0.93:
            widths.append(rng.uniform(0.25, 0.42))
        widths = np.array(widths) / sum(widths)
        bx = np.concatenate([[0.0], np.cumsum(widths)])
        m = course == r
        xs = (u[m] - rng.random()) % 1.0
        k = np.clip(np.searchsorted(bx, xs, side="right") - 1, 0, len(widths) - 1)
        dx = np.minimum(xs - bx[k], bx[k + 1] - xs)
        dy = np.minimum(v[m] - course_edges[r], course_edges[r + 1] - v[m])
        dist[m] = dx * dy / np.sqrt(dx * dx + dy * dy + 1e-12)   # rounded corners
        ident[m] = r * 16 + k
    table = rng.random((ncourses * 16, 4))
    # Distance to the joint in metres, with bitten edges and spalls.
    dm = dist * t + 0.006 * noise(rng, 8, 160, 0.8)
    dm -= 0.035 * _s(noise(rng, 5, 60, 1.0), 1.2, 2.2)
    joint = 0.013 + 0.003 * noise(rng, 3, 40, 1.0)
    bevel = 0.035 + 0.012 * noise(rng, 3, 40, 1.0)
    profile = _rounded((dm - joint) / np.maximum(bevel, 0.01))
    face = ((table[ident, 0] - 0.5) * 0.008 + 0.004 * noise(rng, 3, 30, 1.2)
            + 0.0015 * noise(rng, 30, 400, 0.6))
    pores = _s(noise(rng, 40, 300, 0.5), 2.0, 2.9)
    h_block = -0.022 + profile * (0.022 + face) - 0.003 * pores
    h_mortar = -0.024 + 0.002 * noise(rng, 20, 300, 0.7)
    h = np.maximum(h_block, h_mortar)
    is_block = _s(dm - joint, -0.002, 0.004)

    # Block colour: brownish greys, some more ochre.
    color = _mix((0.40, 0.38, 0.35), (0.29, 0.28, 0.27), table[ident, 1])
    color = _mix(color, (0.43, 0.36, 0.28), table[ident, 2] ** 2 * 0.7)
    color = color * (1.0 + 0.10 * noise(rng, 4, 200, 0.9) + 0.05 * noise(rng, 150, 500, 0.3))[..., None]
    mortar = _mix((0.30, 0.28, 0.24), (0.22, 0.20, 0.17), _s(noise(rng, 4, 200, 0.9), -1, 1))
    color = _mix(mortar, color, is_block)
    color = color * (0.72 + 0.28 * profile)[..., None]                # grime on the edges
    # Damp: large patches and vertical streaks.
    damp = _s(noise(rng, 1, 12, 1.6) + 0.9 * noise(rng, 3, 60, 1.2, aniso=7, ang=math.pi / 2), 0.2, 1.8)
    color = color * (1.0 - 0.38 * damp)[..., None]
    # Green slime in the joints and on the damp areas.
    moss = _s(0.8 * noise(rng, 3, 90, 1.0) + 1.2 * damp + 1.4 * (1 - is_block) - 0.5, 0.8, 1.9)
    slime = _mix((0.16, 0.21, 0.10), (0.24, 0.27, 0.13), _s(noise(rng, 20, 300, 0.6), -1, 1))
    color = _mix(color, slime, moss * 0.85)
    # Whitish saltpetre at the bottom (periodic profile: maximum at the bottom edge and
    # a quick falloff when crossing to the top edge so no seam is left).
    tt = (V + 0.5) % 1.0 - 0.5                   # 0 at the bottom/top edge
    bottom = np.where(tt < 0, np.exp(tt / 0.13), np.exp(-tt / 0.025))
    bottom = np.maximum(bottom - 0.03, 0.0) / 0.97
    salt = _s(0.9 * noise(rng, 4, 150, 0.9) + 3.0 * bottom - 1.6, 0.0, 1.2)
    color = _mix(color, (0.66, 0.65, 0.60), salt * 0.6)
    h = h + 0.0008 * salt * _s(noise(rng, 60, 400, 0.5), -0.5, 1.0)

    rough = np.where(is_block > 0.5, 0.86, 0.93) + 0.05 * noise(rng, 6, 100, 1.0)
    rough = rough * (1.0 - 0.42 * damp)
    rough = _mix(rough, 0.72, moss * 0.8)
    rough = _mix(rough, 0.96, salt)
    return color, h, rough, np.zeros_like(h), 0.02


def floor(rng):
    t = UV_TILE["Floor"]                          # 2 m
    u = (U + 0.012 * noise(rng, 2, 30, 1.3)) % 1.0
    v = (V + 0.012 * noise(rng, 2, 30, 1.3)) % 1.0
    cells = 5
    _, edge, ident = voronoi(rng, cells, u, v, 0.85)
    table = rng.random((cells * cells, 3))
    edge_m = edge * (t / cells) + 0.004 * noise(rng, 8, 200, 0.8)
    edge_m -= 0.015 * _s(noise(rng, 5, 50, 1.0), 1.4, 2.4)
    profile = _rounded((edge_m - 0.008) / 0.03)
    slab = -0.02 + profile * (0.02 + (table[ident, 0] - 0.5) * 0.012
                              + 0.003 * noise(rng, 3, 40, 1.2) + 0.0008 * noise(rng, 40, 400, 0.6))
    # Mud: always fills the joints and covers slabs in the low areas.
    mud_mask = _s(noise(rng, 1.5, 20, 1.5), 0.35, 1.2)
    h_mud = -0.013 + 0.003 * noise(rng, 6, 120, 1.2) + 0.036 * mud_mask
    # Small pebbles half buried in the mud.
    pc = 48
    pf1, _, pid = voronoi(rng, pc, U, V, 0.8)
    pt = rng.random((pc * pc, 3))
    rad = 0.16 + 0.22 * pt[pid, 0]
    q = np.clip(1.0 - (pf1 / rad) ** 2, 0.0, 1.0)
    pebble = np.where(pt[pid, 1] < 0.3, np.sqrt(q) * rad * (t / pc) * 0.5, 0.0)
    h_mud = h_mud + np.where(pebble > 0, pebble + 0.002, 0.0)
    h = np.maximum(slab, h_mud)
    shows_mud = _s(h_mud - slab, -0.0005, 0.0015)
    shows_pebble = shows_mud * _s(pebble, 0.0005, 0.0015)

    c_slab = _mix((0.33, 0.31, 0.28), (0.23, 0.22, 0.20), table[ident, 1])
    c_slab = c_slab * (1.0 + 0.10 * noise(rng, 3, 200, 0.9) + 0.05 * noise(rng, 150, 500, 0.3))[..., None]
    c_slab = c_slab * (0.70 + 0.30 * profile)[..., None]
    wet = _s(noise(rng, 2, 40, 1.2), -0.3, 1.2)
    c_mud = _mix((0.24, 0.19, 0.14), (0.13, 0.10, 0.08), wet)
    c_pebble = _mix((0.38, 0.36, 0.32), (0.20, 0.19, 0.17), pt[pid, 2])
    color = _mix(c_slab, c_mud, shows_mud)
    color = _mix(color, c_pebble, shows_pebble)
    # Shallow puddles on the mud.
    puddle = mud_mask * _s(noise(rng, 1, 10, 1.6), 1.0, 1.5)
    color = color * (1.0 - 0.3 * puddle)[..., None]

    rough = 0.78 + 0.06 * noise(rng, 4, 80, 1.0)
    rough = _mix(rough, 0.82 - 0.35 * wet, shows_mud)
    rough = _mix(rough, 0.7, shows_pebble)
    rough = _mix(rough, 0.12, puddle)
    return color, h, rough, np.zeros_like(h), 0.015


def wood(rng):
    t = UV_TILE["Wood"]                           # 1 m
    nplanks = 5                                   # planks of 0.2 m
    py = V * nplanks
    row = np.floor(py).astype(np.int32) % nplanks
    vloc = py - np.floor(py)
    dc = np.full(U.shape, 9.0)
    seg = np.zeros(U.shape, np.int32)
    for r in range(nplanks):
        cuts = np.sort((rng.random() + np.array([0.0, rng.uniform(0.35, 0.65)])[:rng.integers(1, 3)]) % 1.0)
        m = row == r
        xs = U[m]
        d = np.min(np.abs(_wrap(xs[:, None] - cuts[None, :])), axis=1)
        dc[m] = d
        seg[m] = np.searchsorted(cuts, xs) % len(cuts)
    ident = row * 4 + seg
    table = rng.random((nplanks * 4, 4))
    dm = np.minimum(dc * t, np.minimum(vloc, 1 - vloc) * (t / nplanks))
    dm = dm + 0.0008 * noise(rng, 10, 200, 0.8)
    profile = _rounded((dm - 0.0025) / 0.006)
    # Grain: warped growth rings, different on each plank.
    yy = vloc * (t / nplanks) + table[ident, 0] * 0.4
    phase = yy * 42.0 + 1.4 * noise(rng, 1, 16, 1.5, aniso=12) + 0.25 * noise(rng, 4, 60, 1.0, aniso=8)
    knot = np.zeros_like(U)
    for _ in range(rng.integers(2, 4)):
        r = rng.integers(0, nplanks)
        cx, cy = rng.random(), (r + rng.uniform(0.3, 0.7)) / nplanks
        dk = np.sqrt((_wrap(U - cx) * t / 2.4) ** 2 + (_wrap(V - cy) * t) ** 2)
        on_row = row == r
        phase = phase + np.where(on_row, 3.0 * np.exp(-dk / 0.025), 0.0)
        knot = np.maximum(knot, np.where(on_row, _s(0.013 + 0.003 * table[r, 3] - dk, -0.002, 0.003), 0.0))
    rings = (0.5 + 0.5 * np.sin(2 * math.pi * phase)) ** 3
    fiber = noise(rng, 4, 400, 0.6, aniso=30)
    cracks = _s(noise(rng, 3, 220, 0.8, aniso=40), 2.3, 3.0)
    h = -0.006 + profile * (0.006 + 0.0006 * rings + 0.0002 * fiber - 0.0012 * ((vloc - 0.5) * 2) ** 2)
    h = h - 0.002 * cracks + 0.0006 * knot

    color = _mix((0.33, 0.23, 0.15), (0.23, 0.16, 0.10), table[ident, 1])
    color = _mix(color, (0.31, 0.29, 0.26), table[ident, 2] * 0.55)      # old greyed wood
    color = color * (1.0 - 0.42 * rings + 0.10 * fiber)[..., None]
    color = _mix(color, (0.12, 0.07, 0.04), knot * 0.9)
    color = color * (1.0 - 0.6 * cracks)[..., None]
    grime = _s(noise(rng, 1.5, 120, 1.1), 0.3, 1.8)
    color = _mix(color, (0.10, 0.08, 0.06), grime * 0.55)
    color = _mix((0.07, 0.055, 0.04), color * (0.6 + 0.4 * profile)[..., None], _s(profile, 0.0, 0.5))  # grimy gaps
    rough = 0.78 + 0.07 * noise(rng, 3, 60, 1.0) + 0.1 * grime
    rough = _mix(rough, 0.5, _s(noise(rng, 2, 30, 1.3), 1.2, 1.8))      # grease stains
    return color, h, rough, np.zeros_like(h), 0.003


def iron(rng):
    t = UV_TILE["Iron"]                           # 0.5 m
    u = (U + 0.01 * noise(rng, 2, 20, 1.3)) % 1.0
    v = (V + 0.01 * noise(rng, 2, 20, 1.3)) % 1.0
    cells = 10                                    # hammer blows of ~5 cm
    f1, _, ident = voronoi(rng, cells, u, v, 0.9)
    table = rng.random(cells * cells)
    dent = -(1.0 - f1 ** 2) * 0.0006 * (0.5 + table[ident])
    rust = _s(noise(rng, 2, 60, 1.3) + 0.5 * noise(rng, 15, 200, 0.8), 0.35, 1.1)
    pitting = _s(noise(rng, 60, 450, 0.4), 2.2, 3.0) * _s(rust, 0.1, 0.5)
    crust = noise(rng, 30, 300, 0.7)
    h = (dent + 0.0012 * noise(rng, 1, 8, 1.5) + 0.00012 * noise(rng, 30, 400, 0.7)
         + rust * (0.0004 + 0.00015 * crust) - 0.0004 * pitting)
    streak = _s(noise(rng, 2, 80, 1.2, aniso=10, ang=math.pi / 2), 0.8, 2.0)

    metal_c = (0.30, 0.30, 0.31)
    color = _mix(metal_c, (0.19, 0.19, 0.20), _s(noise(rng, 2, 40, 1.2), -1, 1))
    color = color * (1.0 + 0.06 * noise(rng, 40, 400, 0.6))[..., None]
    c_rust = _mix((0.40, 0.19, 0.08), (0.22, 0.11, 0.06), _s(crust, -1.0, 1.0))
    c_rust = _mix(c_rust, (0.55, 0.30, 0.12), _s(noise(rng, 8, 120, 1.0), 1.0, 2.0) * 0.7)
    color = _mix(color, (0.33, 0.19, 0.10), streak * 0.5)
    color = _mix(color, c_rust, rust)
    color = color * (1.0 - 0.5 * pitting)[..., None]
    metal = np.clip(0.9 * (1.0 - rust) * (1.0 - 0.4 * streak), 0.0, 1.0)
    rough = 0.52 + 0.08 * noise(rng, 3, 60, 1.0)
    rough = _mix(rough, 0.68, streak * 0.6)
    rough = _mix(rough, 0.9, rust)
    return color, h, rough, metal, 0.0008


def cloth(rng):
    t = UV_TILE["Cloth"]                          # 0.6 m; 100 threads = 6 mm per thread
    threads = 100
    gx = (U + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    gy = (V + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    i = np.floor(gx).astype(np.int32) % threads
    j = np.floor(gy).astype(np.int32) % threads
    fx, fy = gx - np.floor(gx), gy - np.floor(gy)
    over = ((i + j) % 2) == 0
    gi, gj = rng.random(threads), rng.random(threads)
    width_u = np.clip((0.72 + 0.35 * gi[i]) * (0.9 + 0.12 * noise(rng, 2, 60, 1.0, aniso=8, ang=math.pi / 2)), 0.45, 1.0)
    width_v = np.clip((0.72 + 0.35 * gj[j]) * (0.9 + 0.12 * noise(rng, 2, 60, 1.0, aniso=8)), 0.45, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / width_u) ** 2, 0.0, 1.0))
    cv = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / width_v) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    h_warp = cu * (0.55 + 0.45 * np.where(over, ou, -ou))       # warp (vertical)
    h_weft = cv * (0.55 + 0.45 * np.where(over, -ov, ov))       # weft (horizontal)
    warp = h_warp >= h_weft
    hh = np.maximum(h_warp, h_weft)
    fib = np.where(warp, noise(rng, 20, 500, 0.5, aniso=10, ang=math.pi / 2), noise(rng, 20, 500, 0.5, aniso=10))
    h = hh * 0.0012 + 0.00008 * fib

    color = np.broadcast_to(np.array([0.55, 0.50, 0.41]), U.shape + (3,))
    tone = np.where(warp, gi[i], gj[j])
    color = color * (0.92 + 0.12 * tone + 0.06 * fib)[..., None]
    dirt = _s(noise(rng, 1, 20, 1.5), -0.3, 1.3)
    color = _mix(color, (0.33, 0.29, 0.22), dirt * 0.7)
    nm = noise(rng, 2, 40, 1.4)
    stain = _s(nm, 1.0, 1.25)
    tide_mark = _s(nm, 0.9, 1.02) * (1.0 - _s(nm, 1.05, 1.25))
    color = _mix(color, (0.32, 0.21, 0.12), stain * 0.6)
    color = color * (1.0 - 0.25 * tide_mark)[..., None]
    color = color * (0.55 + 0.45 * hh)[..., None]
    rough = 0.92 + 0.03 * noise(rng, 3, 60, 1.0) - 0.08 * stain
    return color, h, rough, np.zeros_like(h), 0.0008


def bone(rng):
    t = UV_TILE["Bone"]                           # 0.3 m
    u = (U + 0.012 * noise(rng, 2, 30, 1.2)) % 1.0
    v = (V + 0.012 * noise(rng, 2, 30, 1.2)) % 1.0
    cells = 5
    _, edge, _ = voronoi(rng, cells, u, v, 0.9)
    edge_m = edge * (t / cells)
    width = np.clip(0.00035 * (1.0 + 0.8 * noise(rng, 4, 80, 1.0)), 0.00008, None)
    active = _s(noise(rng, 1, 12, 1.5), -0.8, 0.0)
    crack = (1.0 - _s(edge_m, 0.0, width)) * active
    _, edge2, _ = voronoi(rng, 14, (u + 0.3) % 1.0, v, 0.9)
    micro = (1.0 - _s(edge2 * (t / 14), 0.0, 0.00015)) * _s(noise(rng, 3, 40, 1.2), 0.3, 1.0)
    pores = _s(noise(rng, 80, 500, 0.3), 2.0, 2.9)
    lamellae = noise(rng, 4, 200, 0.9, aniso=6, ang=0.4)
    h = (0.0012 * noise(rng, 1, 10, 1.6) + 0.00012 * lamellae
         - 0.0012 * crack - 0.0004 * micro - 0.0004 * pores)

    color = _mix((0.71, 0.63, 0.48), (0.58, 0.49, 0.34), _s(noise(rng, 2, 60, 1.2), -1.2, 1.2))
    color = color * (1.0 + 0.04 * lamellae)[..., None]
    yellowing = _s(noise(rng, 1, 12, 1.5), -0.2, 1.4)
    color = _mix(color, (0.50, 0.38, 0.22), yellowing * 0.6)
    dark = np.clip(crack + 0.6 * micro + pores, 0, 1)
    color = _mix(color, (0.22, 0.16, 0.10), dark * 0.85)
    grime = _s(noise(rng, 2, 120, 1.0), 0.6, 2.0)
    color = _mix(color, (0.30, 0.24, 0.16), grime * 0.45)
    rough = 0.62 + 0.06 * noise(rng, 3, 60, 1.0) + 0.25 * dark + 0.1 * grime
    return color, h, rough, np.zeros_like(h), 0.0008


def straw(rng):
    t = UV_TILE["Straw"]                          # 1 m; ~1 mm per pixel
    zb, ib = Image.new("F", (N, N), 0.0), Image.new("I", (N, N), 0)
    dz, di = ImageDraw.Draw(zb), ImageDraw.Draw(ib)
    nstraws = 2600
    for k in range(nstraws):
        length = rng.uniform(70, 300)
        width = rng.uniform(2.0, 5.0)
        ang = rng.normal(0.35, 0.55) if rng.random() < 0.7 else rng.uniform(0, math.pi)
        x, y = rng.random(2) * N
        bend = rng.normal(0, 0.12)
        pts = [(x, y)]
        for _ in range(4):
            ang += bend
            x += math.cos(ang) * length / 4
            y += math.sin(ang) * length / 4
            pts.append((x, y))
        z = 0.002 + 0.02 * k / nstraws
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                if max(xs) + ox < -6 or min(xs) + ox > N + 6 or max(ys) + oy < -6 or min(ys) + oy > N + 6:
                    continue
                q = [(px + ox, py + oy) for px, py in pts]
                w = max(1, int(round(width)))
                dz.line(q, fill=z, width=w, joint="curve")
                dz.line(q, fill=z + 0.0012, width=max(1, int(round(width * 0.45))), joint="curve")
                di.line(q, fill=k + 1, width=w, joint="curve")
    h = blur(np.array(zb, dtype=float), 0.7)
    ids = np.array(ib)
    table = rng.random((nstraws + 1, 4))
    color = _mix((0.62, 0.52, 0.30), (0.71, 0.64, 0.46), table[ids, 0])
    color = _mix(color, (0.45, 0.40, 0.31), table[ids, 1] * 0.7)
    color = _mix(color, (0.28, 0.22, 0.14), (table[ids, 2] < 0.15) * 0.8)      # rotten strands
    color = color * (1.0 + 0.10 * noise(rng, 60, 500, 0.4))[..., None]
    layer = np.clip((h - 0.002) / 0.02, 0, 1)
    color = color * (0.55 + 0.45 * layer)[..., None]
    color = np.where((ids == 0)[..., None], np.array([0.12, 0.10, 0.07]), color)
    grime = _s(noise(rng, 1.5, 25, 1.4), 0.3, 1.6)
    color = _mix(color, (0.24, 0.19, 0.12), grime * 0.5)
    rough = np.where(ids == 0, 0.95, 0.68 + 0.12 * table[ids, 3]) + 0.12 * grime
    return color, h, rough, np.zeros_like(h), 0.006


def water(rng):
    t = UV_TILE["Water"]                          # 3 m
    h = (0.02 * noise(rng, 1.5, 10, 2.0, aniso=1.8, ang=0.3)
         + 0.004 * noise(rng, 8, 40, 1.5, aniso=1.4, ang=-0.4)
         + 0.0005 * noise(rng, 30, 120, 1.0))
    color = _mix((0.030, 0.065, 0.058), (0.050, 0.095, 0.072), _s(noise(rng, 1, 6, 1.5), -1, 1))
    scum = _s(noise(rng, 2, 40, 1.3), 1.4, 2.2)                       # dirty foam
    color = _mix(color, (0.13, 0.14, 0.11), scum * 0.5)
    rough = 0.05 + 0.03 * _s(noise(rng, 2, 20, 1.2), 0.5, 2.0) + 0.25 * scum
    return color, h, rough, np.zeros_like(h), None


GENERATORS = {"Stone": stone, "Floor": floor, "Wood": wood, "Iron": iron,
              "Cloth": cloth, "Bone": bone, "Straw": straw, "Water": water}


# ---------------------------------------------------------------------------
# Derived maps
# ---------------------------------------------------------------------------
def normal_from_height(h, metres_px):
    """glTF tangent-space normal (OpenGL, +Y up) from a height in metres."""
    h = blur(h, 0.6)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * metres_px)
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * metres_px)   # downwards in the image
    n = np.stack([-gx, gy, np.ones_like(h)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def occlusion(h, depth):
    if depth is None:
        return np.ones_like(h)
    cavity = 0.5 * (blur(h, 4) + blur(h, 18)) - h
    return 1.0 - 0.7 * np.clip(cavity / depth, 0.0, 1.0)


def _u8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def seam(img):
    """Ratio between the edge-to-edge jump and the jump between neighbouring pixels next
    to that same edge (~1 = no seam; a real seam gives several times more). It is compared
    with the local neighbours because a joint or a thread may fall right on the edge."""
    a = img.astype(float)
    sh = np.abs(a[:, 0] - a[:, -1]).mean()
    sv = np.abs(a[0] - a[-1]).mean()
    dh = 0.5 * (np.abs(a[:, 1] - a[:, 0]).mean() + np.abs(a[:, -1] - a[:, -2]).mean())
    dv = 0.5 * (np.abs(a[1] - a[0]).mean() + np.abs(a[-1] - a[-2]).mean())
    return max(sh / max(dh, 1e-6), sv / max(dv, 1e-6))


def generate(name, rng):
    color, h, rough, metal, depth = GENERATORS[name](rng)
    ao = occlusion(h, depth)
    color = np.clip(color, 0, 1) * (1.0 - 0.3 * (1.0 - ao))[..., None]      # grime in the hollows
    n = normal_from_height(h, UV_TILE[name] / N)
    maps = {
        "basecolor": _u8(color),
        "normal": _u8(n * 0.5 + 0.5),
        "orm": _u8(np.stack([ao, np.clip(rough, 0.02, 1.0), np.clip(metal, 0, 1)], -1)),
    }
    return maps


# ---------------------------------------------------------------------------
# Binary glTF: one metallicRoughness material and a quad that uses it
# ---------------------------------------------------------------------------
def write_glb(path, name, pngs, size):
    s = size / 2.0
    pos = np.array([[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]], np.float32)
    nor = np.tile(np.array([0, 0, 1], np.float32), (4, 1))
    uv = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], np.float32)       # glTF: v=0 at the top
    idx = np.array([0, 1, 2, 0, 2, 3], np.uint16)
    blob = bytearray()
    views = []

    def add(data, target=None):
        while len(blob) % 4:
            blob.append(0)
        view = {"buffer": 0, "byteOffset": len(blob), "byteLength": len(data)}
        if target:
            view["target"] = target
        blob.extend(data)
        views.append(view)
        return len(views) - 1

    accessors = [
        {"bufferView": add(pos.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC3",
         "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
        {"bufferView": add(nor.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC3"},
        {"bufferView": add(uv.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC2"},
        {"bufferView": add(idx.tobytes(), 34963), "componentType": 5123, "count": 6, "type": "SCALAR"},
    ]
    kinds = ["basecolor", "normal", "orm"]
    images = [{"name": f"{name}_{k}", "mimeType": "image/png", "bufferView": add(pngs[k])} for k in kinds]
    while len(blob) % 4:
        blob.append(0)
    doc = {
        "asset": {"version": "2.0", "generator": "The Pit - pbr_textures.py"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                                   "indices": 3, "material": 0, "mode": 4}]}],
        "materials": [{
            "name": name,
            "pbrMetallicRoughness": {"baseColorFactor": [1, 1, 1, 1], "baseColorTexture": {"index": 0},
                                     "metallicFactor": 1.0, "roughnessFactor": 1.0,
                                     "metallicRoughnessTexture": {"index": 2}},
            "normalTexture": {"index": 1, "scale": 1.0},
            "occlusionTexture": {"index": 2, "strength": 1.0},
            "alphaMode": "OPAQUE",
            "doubleSided": False,
        }],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "textures": [{"sampler": 0, "source": i} for i in range(3)],
        "images": images,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def validate_glb(path):
    """Checks the header, chunks, JSON references and embedded images. Returns the errors."""
    err = []
    data = open(path, "rb").read()
    magic, version, total = struct.unpack_from("<III", data, 0)
    if magic != 0x46546C67 or version != 2 or total != len(data):
        return [f"bad header ({magic:#x}, v{version}, {total} != {len(data)})"]
    lj, tj = struct.unpack_from("<II", data, 12)
    if tj != 0x4E4F534A or lj % 4:
        return ["the first chunk is not aligned JSON"]
    doc = json.loads(data[20:20 + lj])
    lb, tb = struct.unpack_from("<II", data, 20 + lj)
    blob = data[28 + lj:28 + lj + lb]
    if tb != 0x004E4942 or len(blob) != lb or doc["buffers"][0]["byteLength"] > lb:
        err.append("inconsistent BIN chunk")
    if doc["asset"]["version"] != "2.0" or len(doc["materials"]) != 1:
        err.append("bad asset/materials")
    m = doc["materials"][0]
    refs = [m["pbrMetallicRoughness"]["baseColorTexture"]["index"], m["normalTexture"]["index"],
            m["occlusionTexture"]["index"], m["pbrMetallicRoughness"]["metallicRoughnessTexture"]["index"]]
    for r in refs:
        if not 0 <= r < len(doc["textures"]):
            err.append(f"texture {r} out of range")
    for tx in doc["textures"]:
        if not 0 <= tx["source"] < len(doc["images"]) or not 0 <= tx["sampler"] < len(doc["samplers"]):
            err.append("texture with image/sampler out of range")
    for bv in doc["bufferViews"]:
        if bv["byteOffset"] + bv["byteLength"] > lb:
            err.append("bufferView outside the buffer")
    for im in doc["images"]:
        bv = doc["bufferViews"][im["bufferView"]]
        png = blob[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]]
        if not png.startswith(b"\x89PNG") or Image.open(io.BytesIO(png)).size != (N, N):
            err.append(f"image {im['name']} is not a {N}x{N} PNG")
    prim = doc["meshes"][0]["primitives"][0]
    if prim["material"] != 0 or max(prim["attributes"].values()) >= len(doc["accessors"]):
        err.append("inconsistent primitive")
    return err


def swatches(path, colors):
    side, label_h, cols = 300, 34, 4
    rows = math.ceil(len(colors) / cols)
    sheet = Image.new("RGB", (cols * side + (cols + 1) * 12, rows * (side + label_h) + (rows + 1) * 12), (18, 16, 14))
    try:
        font = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except OSError:
        font = ImageFont.load_default()
    d = ImageDraw.Draw(sheet)
    for k, (name, img) in enumerate(colors):
        x = 12 + (k % cols) * (side + 12)
        y = 12 + (k // cols) * (side + label_h + 12)
        sheet.paste(Image.fromarray(img).resize((side, side), Image.LANCZOS), (x, y))
        d.text((x + 4, y + side + 6), f"{name}  ({UV_TILE[name]:g} m)", fill=(225, 215, 195), font=font)
    sheet.save(path)


def main():
    t0 = time.time()
    os.makedirs(TEX_DIR, exist_ok=True)
    os.makedirs(GLB_DIR, exist_ok=True)
    colors = []
    failures = []
    for k, name in enumerate(PBR_MATERIALS):
        t1 = time.time()
        maps = generate(name, np.random.default_rng(SEED + k))
        pngs = {}
        for kind, img in maps.items():
            buf = io.BytesIO()
            Image.fromarray(img).save(buf, "PNG", optimize=False)
            pngs[kind] = buf.getvalue()
            with open(os.path.join(TEX_DIR, f"{name}_{kind}.png"), "wb") as f:
                f.write(pngs[kind])
        glb_path = os.path.join(GLB_DIR, f"{name}.glb")
        write_glb(glb_path, name, pngs, UV_TILE[name])
        errors = validate_glb(glb_path)
        seams = {kind: seam(img) for kind, img in maps.items()}
        worst = max(seams.values())
        if errors or worst > 1.5:
            failures.append((name, errors, seams))
        colors.append((name, maps["basecolor"]))
        print(f"  {name:7s} {time.time() - t1:5.1f} s  max seam {worst:4.2f}  "
              f"glb {os.path.getsize(glb_path) / 1e6:4.1f} MB  {'OK' if not errors else errors}")
    swatches(os.path.join(TEX_DIR, "_swatches.png"), colors)
    print(f"Textures in {TEX_DIR}\nglTF materials in {GLB_DIR}\nTotal {time.time() - t0:.1f} s")
    if failures:
        print("FAILURES:", failures)
        sys.exit(1)


if __name__ == "__main__":
    main()

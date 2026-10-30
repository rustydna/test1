"""Procedural PBR material library for The Cave (seamless, physically scaled).

The script makes every material variant the owner can pick from the Cave menus, using only
numpy and pillow:

  output/textures/<slot>__<variant>_basecolor.png   sRGB
  output/textures/<slot>__<variant>_normal.png      glTF tangent space (OpenGL, +Y up)
  output/textures/<slot>__<variant>_orm.png         R occlusion, G roughness, B metallic
  output/textures/<slot>__<variant>_emissive.png    sRGB, glowing materials only
  output/textures/_swatches.png                     contact sheet (every variant, labelled)
  output/pbr_materials/cave_<slot>_<variant>.glb    one glTF 2.0 material (plus a quad that
                                                    uses it) for the Second Life bulk uploader
  docs/materials.json                               the catalogue read by the build, the
                                                    renderer and the LSL menus

The slot names are the villa pipeline's; in the cave they mean:
  a_plaster ROCK (walls, ceiling)   b_floor GROUND        c_wood WOOD       d_stone MOSS / WET STONE
  e_fabric  FUR / LEATHER           f_metal METAL         g_glass CRYSTAL   h_glow GLOW    water

Look: a large natural cave. Bedded limestone, basalt, red sandstone and slate, earth, sand,
scree and mud, driftwood, old timber, char and bark, moss, lichen and flowstone, wolf and bear
pelts, rusty iron, verdigris bronze and treasure gold, crystals and glowworms. No feature is
big or unique enough to mark the repeat grid.

Seamless by construction: all noise lives on a torus (white noise filtered with an FFT),
Voronoi wraps its neighbours, beds/boards/threads divide the repeat exactly and everything drawn
is drawn with its copies one repeat away. Edges are checked numerically at the end.

Physical scale: one repeat covers UV_TILE[slot] metres (the table in cave.py; UVs are
world-space box-mapped, on walls v = height, so strata run along U and things that flow or
drip run down the image, +V). Heights are in metres and the normal maps are computed with the
real pixel size, so slopes are physically right. Wood grain runs along U as in the villa.

The toolkit (periodic noise, Voronoi, Canvas, normals, glb writer, seam check, catalogue,
swatches) is copied from villa/scripts/vtextures.py, which takes it from
the_pit/scripts/pbr_textures.py; the embers and water generators are the villa's.

Usage:  python3 cave/scripts/ctextures.py [filter ...] [--jobs N]
        (filters keep only variants whose "<slot>__<variant>" contains one of the words;
         a filtered run rewrites only those files and leaves the catalogue untouched)
"""

import ast
import hashlib
import io
import json
import math
import os
import struct
import sys
import time
import zlib
from multiprocessing import Pool

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
TEX_DIR = os.path.join(ROOT, "output", "textures")
GLB_DIR = os.path.join(ROOT, "output", "pbr_materials")
CATALOGUE = os.path.join(ROOT, "docs", "materials.json")
PREFIX = "cave_"
BUDGET_MB = 70.0          # textures + glb together
DETERMINISM_CHECK = {("a_plaster", "limestone"), ("g_glass", "amethyst")}
# Texture size written per slot. Every material is generated at its design resolution
# (LIB "res", 1024 unless noted) and, where this is smaller, reduced by a seamless periodic
# filter. 512 everywhere keeps the library (PNG + glb copies) inside BUDGET_MB; rock and
# ground at 1024 would cost about 4.5 MB per variant, twice over (PNG and glb).
OUT_RES = {"a_plaster": 512, "b_floor": 512, "c_wood": 512, "d_stone": 512, "e_fabric": 512,
           "f_metal": 512, "g_glass": 512, "h_glow": 512, "water": 512}

CAVE_TILE = {"a_plaster": 4.0, "b_floor": 3.0, "c_wood": 1.2, "d_stone": 3.0, "e_fabric": 0.8,
             "f_metal": 1.0, "g_glass": 1.0, "h_glow": 1.0, "water": 4.0}


def _uv_tile():
    """The UV_TILE.update({...}) table of cave.py (parsed, not imported: cave.py imports
    bpy), falling back to the same values written here."""
    tiles = dict(CAVE_TILE)
    try:
        tree = ast.parse(open(os.path.join(HERE, "cave.py")).read())
        for node in ast.walk(tree):
            if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "update"
                    and isinstance(node.func.value, ast.Attribute) and node.func.value.attr == "UV_TILE"
                    and node.args):
                got = ast.literal_eval(node.args[0])
                tiles.update({k: float(v) for k, v in got.items() if k in tiles})
    except (OSError, SyntaxError, ValueError):
        pass
    return tiles


UV_TILE = _uv_tile()
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow", "water"]
SLOT_TITLE = {"a_plaster": "ROCK", "b_floor": "GROUND", "c_wood": "WOOD", "d_stone": "MOSS / WET STONE",
              "e_fabric": "FUR / LEATHER", "f_metal": "METAL", "g_glass": "CRYSTAL", "h_glow": "GLOW",
              "water": "WATER"}

# ---------------------------------------------------------------------------
# Torus grid. set_res() is called before every material (resolution and repeat size vary).
# ---------------------------------------------------------------------------
N = 1024
T = 1.0          # metres per repeat of the material being made
U = V = _FX = _FY = None


def set_res(n, tile):
    global N, T, U, V, _FX, _FY
    N, T = n, tile
    _FY = np.fft.fftfreq(N)[:, None] * N          # cycles per repeat (rows)
    _FX = np.fft.rfftfreq(N)[None, :] * N         # cycles per repeat (columns)
    c = (np.arange(N) + 0.5) / N
    U, V = np.meshgrid(c, c)                      # U horizontal, V vertical (0 at the image top)


def _s(x, a, b):
    """smoothstep."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    t = np.asarray(t, dtype=float)
    if t.ndim == 2 and (a.ndim in (1, 3) or b.ndim in (1, 3)):
        t = t[..., None]
    return a + (b - a) * t


def _mul(color, f):
    return color * np.asarray(f, dtype=float)[..., None]


def _rgb(c):
    return np.broadcast_to(np.asarray(c, float), (N, N, 3)).copy()


def noise(rng, f0=1.0, f1=64.0, p=1.0, aniso=1.0, ang=0.0):
    """Periodic fractal noise (mean 0, std 1), amplitude ~ 1/f^p between f0 and f1 cycles per
    repeat. aniso > 1 stretches it along the angle ang (0 = along U, pi/2 = along V)."""
    f1 = min(f1, N * 0.5)
    c, s = math.cos(ang), math.sin(ang)
    along = _FX * c + _FY * s
    across = -_FX * s + _FY * c
    f = np.maximum(np.sqrt((along * aniso) ** 2 + across ** 2), 1e-6)
    amp = f ** -p * (1.0 - np.exp(-(f / f0) ** 4)) * np.exp(-(f / f1) ** 2)
    amp[0, 0] = 0.0
    out = np.fft.irfft2(np.fft.rfft2(rng.standard_normal((N, N))) * amp, s=(N, N))
    return (out - out.mean()) / (out.std() + 1e-12)


def nm(rng, big, small, p=1.0, aniso=1.0, ang=0.0):
    """noise() with its band given as wavelengths in metres (largest, smallest)."""
    return noise(rng, T / big, T / small, p, aniso, ang)


def blur(x, sigma):
    """Periodic Gaussian blur (sigma in pixels)."""
    if x.ndim == 3:
        return np.stack([blur(x[..., i], sigma) for i in range(x.shape[2])], -1)
    g = np.exp(-2.0 * (math.pi * sigma / N) ** 2 * (_FX ** 2 + _FY ** 2))
    return np.fft.irfft2(np.fft.rfft2(x) * g, s=x.shape)


def sample(field, du, dv):
    """Bilinear periodic lookup of field at (U + du, V + dv) (offsets in repeats)."""
    x = (U + du) * N - 0.5
    y = (V + dv) * N - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    x0, y0 = x0 % N, y0 % N
    x1, y1 = (x0 + 1) % N, (y0 + 1) % N
    return ((field[y0, x0] * (1 - fx) + field[y0, x1] * fx) * (1 - fy)
            + (field[y1, x0] * (1 - fx) + field[y1, x1] * fx) * fy)


def warped(rng, big, small, p=1.5, amount=0.06, aniso=1.0, ang=0.0):
    """Domain-warped fractal noise (std 1): the flowing turbulence of marble and water."""
    base = nm(rng, big, small, p, aniso, ang)
    wu = nm(rng, big * 1.4, small * 3, 1.6)
    wv = nm(rng, big * 1.4, small * 3, 1.6)
    w = sample(base, amount * wu, amount * wv)
    return (w - w.mean()) / (w.std() + 1e-12)


def grad_px(f):
    """Periodic gradient magnitude per pixel."""
    gx = (np.roll(f, -1, 1) - np.roll(f, 1, 1)) * 0.5
    gy = (np.roll(f, -1, 0) - np.roll(f, 1, 0)) * 0.5
    return np.sqrt(gx * gx + gy * gy)


def voronoi(rng, cells, u, v, jitter=0.9):
    """Periodic Voronoi of cells x cells points (or cu x cv for cells = (cu, cv): cells
    stretched along U when cu < cv). Returns (f1, edge, ident, ru, rv): distance to the
    nearest point, distance to the cell edge (cell units), cell index and the vector from
    the pixel to its point."""
    cu_n, cv_n = (cells, cells) if np.isscalar(cells) else cells
    pts = 0.5 + (rng.random((cv_n, cu_n, 2)) - 0.5) * jitter
    gu, gv = u * cu_n, v * cv_n
    iu, iv = np.floor(gu).astype(np.int32), np.floor(gv).astype(np.int32)
    fu, fv = (gu - iu).astype(np.float32), (gv - iv).astype(np.float32)
    f1 = np.full(u.shape, 9.0, np.float32)
    ru = np.zeros(u.shape, np.float32)
    rv = np.zeros(u.shape, np.float32)
    ident = np.zeros(u.shape, np.int32)
    neighbors = []
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cu, cv = (iu + di) % cu_n, (iv + dj) % cv_n
            du = di + pts[cv, cu, 0].astype(np.float32) - fu
            dv = dj + pts[cv, cu, 1].astype(np.float32) - fv
            neighbors.append((du, dv))
            d = du * du + dv * dv
            m = d < f1
            f1 = np.where(m, d, f1)
            ru = np.where(m, du, ru)
            rv = np.where(m, dv, rv)
            ident = np.where(m, cv * cu_n + cu, ident)
    edge = np.full(u.shape, 9.0, np.float32)
    for du, dv in neighbors:
        eu, ev = du - ru, dv - rv
        l2 = eu * eu + ev * ev
        dist = ((ru + du) * 0.5 * eu + (rv + dv) * 0.5 * ev) / np.sqrt(np.maximum(l2, 1e-10))
        edge = np.where(l2 > 1e-8, np.minimum(edge, dist), edge)
    return np.sqrt(f1), edge, ident, ru, rv


def _wrap(x):
    """Periodic difference in [-0.5, 0.5)."""
    return (x + 0.5) % 1.0 - 0.5


def window(cx, cy, rx, ry=None):
    """Wrapped pixel window around (cx, cy) px: index usable on any N x N array, and the
    offsets dx (1 x w), dy (h x 1) of every pixel centre from (cx, cy)."""
    ry = rx if ry is None else ry
    x0, x1 = int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1
    y0, y1 = int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1
    xs, ys = np.arange(x0, x1), np.arange(y0, y1)
    return np.ix_(ys % N, xs % N), (xs + 0.5 - cx)[None, :], (ys + 0.5 - cy)[:, None]


def stamp_max(dst, idx, val):
    dst[idx] = np.maximum(dst[idx], val)


class Canvas:
    """Anti-aliased drawing on the torus (shapes drawn with their copies up to two repeats
    away at ss x resolution, box-filtered down). Coordinates in output pixels; get() -> 0..1."""

    def __init__(self, ss=3):
        self.ss = ss
        self.im = Image.new("L", (N * ss, N * ss), 0)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _offsets(xs, ys, pad):
        for ox in (-2 * N, -N, 0, N, 2 * N):
            if max(xs) + ox < -pad or min(xs) + ox > N + pad:
                continue
            for oy in (-2 * N, -N, 0, N, 2 * N):
                if max(ys) + oy < -pad or min(ys) + oy > N + pad:
                    continue
                yield ox, oy

    def line(self, pts, width, value=255):
        s = self.ss
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w = max(1, int(round(width * s)))
        for ox, oy in self._offsets(xs, ys, width + 2):
            self.d.line([((x + ox) * s, (y + oy) * s) for x, y in pts], fill=value, width=w, joint="curve")

    def stroke(self, pts, widths, value=255):
        """Polyline whose full width (px) changes from point to point (pinch and swell)."""
        s = self.ss
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        hw = [max(0.0, float(w)) * s * 0.5 for w in widths]
        for ox, oy in self._offsets(xs, ys, max(widths) + 2):
            q = [((x + ox) * s, (y + oy) * s) for x, y in pts]
            for i in range(len(q) - 1):
                (x0, y0), (x1, y1) = q[i], q[i + 1]
                h0, h1 = hw[i], hw[i + 1]
                if h0 < 0.2 and h1 < 0.2:
                    continue
                dx, dy = x1 - x0, y1 - y0
                ln = math.hypot(dx, dy) or 1.0
                nx, ny = -dy / ln, dx / ln
                self.d.polygon([(x0 + nx * h0, y0 + ny * h0), (x1 + nx * h1, y1 + ny * h1),
                                (x1 - nx * h1, y1 - ny * h1), (x0 - nx * h0, y0 - ny * h0)], fill=value)
                if h1 >= 0.75:
                    self.d.ellipse([x1 - h1, y1 - h1, x1 + h1, y1 + h1], fill=value)

    def polygon(self, pts, value=255):
        s = self.ss
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ox, oy in self._offsets(xs, ys, 2):
            self.d.polygon([((x + ox) * s, (y + oy) * s) for x, y in pts], fill=value)

    def get(self):
        return np.asarray(self.im.resize((N, N), Image.BOX), dtype=float) / 255.0


def tiles(nu, nv, off_u=0.0, off_v=0.0, bond=0.0):
    """nu x nv tiles per repeat; alternate rows shifted by `bond` tiles (nv must be even then).
    Returns local coords lu, lv (0..1 in the tile), tile ident, distance to the tile edge in
    metres along U and along V."""
    gv = ((V - off_v) % 1.0) * nv
    row = np.floor(gv).astype(np.int32)
    lv = gv - row
    gu = (((U - off_u) % 1.0) * nu - bond * (row % 2)) % nu
    col = np.floor(gu).astype(np.int32)
    lu = gu - col
    ident = row * nu + col
    du = np.minimum(lu, 1 - lu) * T / nu
    dv = np.minimum(lv, 1 - lv) * T / nv
    return lu, lv, ident, du, dv


def joint_profile(d, half_gap, bevel, depth):
    """Height (m) of a tile/plank edge: recessed gap and a small rounded bevel. d in metres."""
    t = np.clip((d - half_gap) / bevel, 0.0, 1.0)
    face = 1.0 - (1.0 - t) ** 2
    return -depth * (1.0 - face), _s(d, half_gap - 0.5 * T / N, half_gap + 0.5 * T / N)


# ---------------------------------------------------------------------------
# Helpers kept from the villa library (wood figure, meandering paths, veins).
# ---------------------------------------------------------------------------
def wood_figure(rng, Y, bw, ident, nid, sp, xl=None, seg_len=None, flat_share=0.6):
    """Plain (flat) and rift sawn figure. Y: metres across the board (0..bw), xl: metres along
    a plank segment (floor planks; None = continuous boards, periodic along U). The pith lies
    outside the board, so flat-sawn boards show nested cathedral arches, rift boards near
    straight lines. Returns ring fraction, late-wood profile, ring index, d, table."""
    tab = rng.random((nid, 12))
    flat = tab[:, 0] < flat_share
    dmin = np.where(flat, 0.004 + 0.02 * tab[:, 1], 0.05 + 0.2 * tab[:, 1])
    if xl is None:
        k = np.where(tab[:, 2] < 0.65, 1, 2)
        amp = 0.02 + 0.06 * tab[:, 3]
        d = dmin[ident] + amp[ident] * 0.5 * (1 - np.cos(2 * math.pi * (k[ident] * U + tab[ident, 4])))
    else:
        xa = seg_len * (0.2 + 0.6 * tab[ident, 4])
        d = dmin[ident] + (0.04 + 0.25 * tab[ident, 3]) * (xl - xa) ** 2
    d = d + 0.002 * noise(rng, 2, 30, 1.4, aniso=6)
    off = 0.006 + 0.05 * tab[ident, 6]
    yc = np.where(tab[ident, 5] < 0.5, -off, bw + off)
    Yw = Y + 0.0010 * noise(rng, 2, 40, 1.3, aniso=8) + 0.00025 * noise(rng, 10, 160, 1.0, aniso=6)
    radius = np.sqrt(d * d + (Yw - yc) ** 2)
    spacing = sp[0] + (sp[1] - sp[0]) * tab[ident, 7]
    ring = radius / spacing + 0.9 * noise(rng, 2, 24, 1.4, aniso=6)
    fr = ring - np.floor(ring)
    late = _s(fr, 0.35, 0.92) * (1 - _s(fr, 0.96, 1.0))
    return fr, late, ring, d, tab


def boards_v(rng, wmin, wmax):
    """Edge-glued boards across V (widths in metres, summing exactly to the repeat).
    Returns local Y (m), board width per pixel (m), board ident, board count."""
    ws = []
    while sum(ws) < T - wmax:
        ws.append(rng.uniform(wmin, wmax))
    ws.append(T - sum(ws))
    if ws[-1] < wmin * 0.7:
        ws[-2] += ws[-1]
        ws.pop()
    e = np.concatenate([[0.0], np.cumsum(ws)]) / T
    off = rng.random()
    vv = (V + off) % 1.0
    row = np.clip(np.searchsorted(e, vv, side="right") - 1, 0, len(ws) - 1)
    return (vv - e[row]) * T, np.asarray(ws)[row], row, len(ws)


def wood_surface(rng, sp, Y, bw, ident, nid, xl=None, seg_len=None, knots=0, plank_mask=None):
    """Colour, height, roughness of a wood species on boards (ident) with local Y."""
    fr, late, ring, d, tab = wood_figure(rng, Y, bw, ident, nid, sp["sp"], xl, seg_len)
    if knots:
        late, fr = _add_knots(rng, ring, knots, plank_mask)
    early_band = _s(fr, 0.0, 0.04) * (1 - _s(fr, 0.14, 0.30))
    pore_n = noise(rng, 30, N / 2, 0.35, aniso=9)
    if sp["porous"] == "ring":
        pores = _s(pore_n, 0.5, 1.4) * early_band + _s(pore_n, 2.4, 3.0) * (1 - early_band) * 0.5
    elif sp["porous"] == "semi":
        pores = _s(pore_n, 1.1, 1.9) * (0.4 + 0.6 * early_band)
    else:
        pores = _s(pore_n, 1.7, 2.5)
    rays = _s(noise(rng, 30, N / 2, 0.5, aniso=6), 2.4, 3.1)
    quarter = _s(np.abs(d), 0.05, 0.15)                       # rift boards show ray fleck
    fleck = _s(noise(rng, 12, 300, 0.7, aniso=4), 1.7, 2.5) * quarter
    fibre = noise(rng, 8, N / 2, 0.55, aniso=32)
    streak = noise(rng, 2, 160, 1.0, aniso=24)
    board_tone = tab[ident, 8] - 0.5
    color = _mix(sp["early"], sp["late"], late * sp.get("contrast", 1.0))
    color = _mul(color, 1.0 + 0.07 * board_tone + 0.025 * fibre + 0.025 * nm(rng, 0.6, 0.05, 1.3, aniso=4))
    color = _mix(color, sp["streak"], _s(streak, 0.7, 2.3) * 0.5)
    color = _mix(color, sp["sap"], _s(-streak, 1.5, 2.7) * 0.3)
    color = _mix(color, sp["pore"], pores * sp.get("pore_c", 0.55))
    color = _mix(color, sp["ray"], np.clip(rays * 0.2 + fleck * 0.45, 0, 1))
    h = (sp["relief"] * (late - 0.5) + 0.00001 * fibre - sp["pore_depth"] * pores
         + 0.00025 * nm(rng, 0.6, 0.1, 1.6, aniso=3))
    rough = sp["rough"] + 0.015 * fibre + 0.12 * pores - 0.03 * late + 0.015 * streak
    return color, h, rough, late


def _add_knots(rng, ring, count, plank_mask):
    """Small sound knots (sparingly): rings flow around them."""
    px = T / N
    bump = np.zeros_like(ring)
    core = np.zeros_like(ring)
    for _ in range(count):
        for _ in range(200):
            cx, cy = rng.random() * N, rng.random() * N
            if plank_mask is None or plank_mask[int(cy) % N, int(cx) % N] > 0.5:
                break
        r = rng.uniform(0.004, 0.009) / px
        idx, dx, dy = window(cx, cy, r * 9, r * 4)
        el = np.sqrt((dx / 2.2) ** 2 + dy ** 2)
        stamp_max(bump, idx, 3.0 * np.exp(-(el / (r * 1.6)) ** 2))
        stamp_max(core, idx, _s(1.0 - np.sqrt((dx / 1.25) ** 2 + dy ** 2) / r, 0.0, 0.3))
    ring2 = ring + bump
    fr = ring2 - np.floor(ring2)
    late = _s(fr, 0.35, 0.92) * (1 - _s(fr, 0.96, 1.0))
    late = np.maximum(late, core * 0.95)
    return late, fr


def vein_path(rng, x, y, ang0, length, step, turn, pull=0.06):
    """Meandering path (px): correlated turning, pulled back to the bedding direction ang0."""
    pts = [(x, y)]
    a, da = ang0, 0.0
    for _ in range(max(2, int(length / step))):
        da = 0.8 * da + rng.normal(0, turn)
        a += da + pull * (ang0 - a)
        x += math.cos(a) * step
        y += math.sin(a) * step
        pts.append((x, y))
    return pts


def wave_profile(rng, n, waves=(2, 5, 11, 23)):
    """Smooth random profile along a path (-1..1)."""
    t = np.linspace(0, 1, n)
    f = sum(rng.normal(0, 1) / (1 + 0.15 * k) * np.sin(2 * math.pi * (k * t + rng.random())) for k in waves)
    return f / (np.abs(f).max() + 1e-9)


def widths(rng, n, w0, var=1.0, taper=0.12, waves=(2, 5, 11, 23)):
    """Pinch-and-swell width profile (px) that tapers at both ends."""
    t = np.linspace(0, 1, n)
    w = w0 * np.clip(1 + var * wave_profile(rng, n, waves), 0, None)
    return w * np.clip(np.minimum(t, 1 - t) / taper, 0, 1) ** 0.6


def offset_path(pts, off):
    p = np.array(pts)
    d = np.gradient(p, axis=0)
    d /= np.linalg.norm(d, axis=1, keepdims=True) + 1e-9
    nrm = np.stack([-d[:, 1], d[:, 0]], 1)
    return [tuple(x) for x in p + nrm * np.asarray(off)[:, None]]


def ragged(rng, mask, amp_px, small_px=5, big_px=60):
    """Crinkles the edges of a drawn mask (vein edges are never smooth)."""
    du = noise(rng, N / big_px, N / small_px, 0.8) * amp_px / N
    dv = noise(rng, N / big_px, N / small_px, 0.8) * amp_px / N
    return sample(mask, du, dv)


def contour_dist(f):
    """Distance (px) to the zero set of a field."""
    return np.abs(f) / np.maximum(grad_px(f), 1e-7)


def vein(d, width, soft=1.0):
    """Vein profile from a distance (px) and a width field (px)."""
    return np.exp(-(d / np.maximum(width, 0.35)) ** (2.0 * soft))


# ---------------------------------------------------------------------------
# Cave toolkit: warped cells, broken-rock facets, strata, scattered stones, colour ramps.
# ---------------------------------------------------------------------------
def warp_uv(rng, amt_m, big, small, p=1.5):
    """U, V displaced by periodic noise of std amt_m metres (irregular, non-convex cells)."""
    a = amt_m / T
    return (U + a * nm(rng, big, small, p)) % 1.0, (V + a * nm(rng, big, small, p)) % 1.0


def facets(rng, cells, slope, step, warp_m=0.0, jitter=0.95):
    """Broken rock: every (warped) Voronoi cell is a plane with its own tilt (std `slope`,
    dimensionless) through its point at its own offset (std `step`, m), so neighbouring
    cells meet in creases and small chipped steps. cells: int or (along U, along V).
    Returns height (m), cell ident, distance to the cell edge (cell units), f1."""
    cu, cv = (cells, cells) if np.isscalar(cells) else cells
    if warp_m:
        cell = T / max(cu, cv)
        wu, wv = warp_uv(rng, warp_m, cell * 4, cell * 1.0)
    else:
        wu, wv = U, V
    f1, edge, idc, ru, rv = voronoi(rng, (cu, cv), wu, wv, jitter)
    nc = cu * cv
    a, b, c = rng.normal(0, slope, nc), rng.normal(0, slope, nc), rng.normal(0, step, nc)
    h = -(a[idc] * ru * (T / cu) + b[idc] * rv * (T / cv)) + c[idc]
    return h, idc, edge, f1


def broken_rock(rng, octaves, aniso=1.0, warp=0.15):
    """Sum of facet octaves (cell size m, slope, step m, blur px); aniso > 1 widens the
    cells along U (bedded rock). Returns height (m) and the cell idents per octave."""
    h = np.zeros((N, N))
    ids = []
    for size, slope, step, bl in octaves:
        cu = max(2, int(round(T / (size * aniso))))
        cv = max(2, int(round(T / size)))
        hf, idc, _, _ = facets(rng, (cu, cv), slope, step, warp_m=size * warp)
        h += blur(hf, bl)
        ids.append(idc)
    return h, ids


def beds(rng, tmin, tmax, wave_m=0.0, big=2.0, jag_m=0.0):
    """Horizontal beds across V (strata on walls, v = height), random thicknesses tmin..tmax
    (m) summing exactly to the repeat, undulating by wave_m and with jag_m of broken
    roughness. Returns bed index, distance below the bed top (m), above its base (m),
    thickness (m) per pixel and the bed count."""
    ws = []
    while sum(ws) < T - tmax:
        ws.append(rng.uniform(tmin, tmax))
    ws.append(T - sum(ws))
    if ws[-1] < tmin * 0.7 and len(ws) > 1:
        ws[-2] += ws[-1]
        ws.pop()
    e = np.concatenate([[0.0], np.cumsum(ws)]) / T
    vv = V + rng.random()
    if wave_m:
        vv = vv + wave_m / T * nm(rng, big, big / 8, 1.8, aniso=3)
    if jag_m:
        vv = vv + jag_m / T * nm(rng, 0.25, 0.006, 1.1, aniso=1.5)
    vv = vv % 1.0
    row = np.clip(np.searchsorted(e, vv, side="right") - 1, 0, len(ws) - 1)
    th = np.asarray(ws)[row]
    top = np.clip((vv - e[row]) * T, 0, None)
    return row, top, np.clip(th - top, 0, None), th, len(ws)


def stones(rng, size, keep, margin=(0.1, 0.28), power=0.5, warp=0.25, jitter=0.85, jag=0.04):
    """Scattered stones of about `size` m: warped Voronoi chips shrunk by a margin (rounded
    polygonal outline) with a domed top (power 0.5 rounded, lower = flatter, steeper sides).
    Returns coverage, dome (0..1), stone ident, stone count, ru, rv."""
    cells = max(2, int(round(T / size)))
    wu, wv = warp_uv(rng, size * warp, size * 3, size * 0.3)
    f1, edge, idc, ru, rv = voronoi(rng, cells, wu, wv, jitter)
    nc = cells * cells
    on = rng.random(nc) < keep
    m = rng.uniform(*margin, nc)
    inner = edge - m[idc] + jag * noise(rng, cells * 0.5, cells * 6, 0.6)
    aa = cells / N
    cov = _s(inner, -0.6 * aa, 0.6 * aa) * on[idc]
    dome = np.clip(inner / np.maximum(0.5 - m[idc], 0.05), 0, 1) ** power
    return cov, dome, idc, nc, ru, rv


def ramp(t, stops):
    """Piecewise-linear colour ramp: t in 0..1, stops [(position, (r, g, b)), ...]."""
    t = np.clip(t, 0.0, 1.0)
    pos = np.array([p for p, _ in stops], float)
    cols = np.array([c for _, c in stops], float)
    return np.stack([np.interp(t, pos, cols[:, i]) for i in range(3)], -1)


def nrm01(x):
    return (x - x.min()) / (x.max() - x.min() + 1e-12)


def cracks(rng, count, ang0, length_m, width_px, turn=0.05, spread=0.15, value=(150, 255)):
    """Thin meandering cracks/joints (canvas mask, 0..1)."""
    px = T / N
    cv = Canvas(3)
    for _ in range(count):
        pts = vein_path(rng, rng.random() * N, rng.random() * N, ang0 + rng.normal(0, spread),
                        rng.uniform(*length_m) / px, 2.5, turn, pull=0.05)
        cv.stroke(pts, widths(rng, len(pts), rng.uniform(*width_px), 0.8, taper=0.2),
                  value=int(rng.uniform(*value)))
    return cv.get()


# ---------------------------------------------------------------------------
# a_plaster = ROCK (cave walls and ceiling), 4 m per repeat
# ---------------------------------------------------------------------------
def scallops(rng, cells, depth, warp_frac=0.25):
    """Dissolution scallops: packed spoon-shaped hollows with sharp rims where they meet
    (bowls f1^2 of a warped Voronoi). cells: int or (along U, along V). Returns height (m,
    <= 0) and the rim mask."""
    cu, cv = (cells, cells) if np.isscalar(cells) else cells
    cell = T / max(cu, cv)
    wu, wv = warp_uv(rng, warp_frac * cell, cell * 4, cell * 1.2)
    f1, edge, idc, _, _ = voronoi(rng, (cu, cv), wu, wv, 0.9)
    d = rng.uniform(0.5, 1.0, idc.max() + 1)[idc]
    return -depth * d * (0.55 - np.minimum(f1, 0.55) ** 2 / 0.55), 1 - _s(edge, 0.0, 0.08)


def rock_limestone(rng):
    """Cave limestone: warm grey-beige beds 8-60 cm thick; the face is sculpted by water into
    packed scallops (large and small) with sharp rims, rougher corroded zones; bedding planes weather out as soft recessed lines that come and go; pitting
    in porous beds; thin cream calcite streaks and darker seepage stains run down from the
    bedding."""
    px = T / N
    row, top, bot, th, nb = beds(rng, 0.08, 0.6, wave_m=0.05, big=2.5, jag_m=0.003)
    tab = rng.random((nb, 8))
    db = np.minimum(top, bot)
    big = 0.06 * warped(rng, 4.0, 0.4, 1.9, 0.06) + 0.012 * nm(rng, 0.8, 0.1, 1.7)
    sc1, rim1 = scallops(rng, (10, 17), 0.04)
    sc2, rim2 = scallops(rng, (26, 42), 0.012)
    sc1, sc2 = blur(sc1, 1.5), blur(sc2, 1.0)
    corr = 0.3 + 0.7 * _s(nm(rng, 1.2, 0.2, 1.7), -0.6, 1.6)        # rougher corroded zones
    rough_h = 0.003 * nm(rng, 0.06, 0.006, 1.2) + 0.0012 * np.abs(nm(rng, 0.02, 0.004, 1.0))
    plane_on = _s(nm(rng, 1.5, 0.15, 1.5, aniso=5), 0.0, 1.0)
    gw = 0.008 + 0.02 * tab[row, 1]
    groove = np.exp(-(db / gw) ** 2) * plane_on
    rounded = 1 - _s(db, 0.0, 0.04 + 0.04 * tab[row, 1])
    porous = _s(tab[row, 3], 0.5, 0.95)
    pits = _s(nm(rng, 0.03, px * 1.2, 0.5) + 1.6 * porous + 0.6 * nm(rng, 0.8, 0.1, 1.5), 3.0, 3.7)
    joints = cracks(rng, 5, math.pi / 2, (0.4, 1.6), (0.8, 2.0), turn=0.04, spread=0.12)
    # thin streaks running down from the bedding planes
    sv = nm(rng, 0.6, 0.008, 0.9, aniso=18, ang=math.pi / 2)
    seep = _s(nm(rng, 0.8, 0.08, 1.4, aniso=5, ang=math.pi / 2), 0.3, 1.6)
    fade_in = _s(top, 0.0, 0.03)
    run_c = np.exp(-top / (0.1 + 0.5 * tab[row, 4])) * fade_in
    calcite = blur(_s(sv, 1.3, 2.4) * seep * run_c, 0.8)
    run_s = np.exp(-top / (0.08 + 0.4 * tab[row, 5])) * fade_in
    stain = blur(_s(-sv, 1.0, 2.2) * _s(nm(rng, 0.8, 0.08, 1.4, aniso=5, ang=math.pi / 2), 0.2, 1.4) * run_s, 0.8)
    relief = sc1 + sc2 * (0.5 + porous) + rough_h * corr
    h = (big + relief * (0.7 + 0.6 * tab[row, 0]) + (tab[row, 2] - 0.5) * 0.02 - 0.015 * groove
         - 0.01 * rounded * plane_on - 0.004 * pits - 0.005 * joints + 0.0015 * calcite
         + 0.00025 * nm(rng, 0.01, px * 1.5, 0.6))
    color = _mix(_rgb((0.640, 0.600, 0.535)), (0.600, 0.590, 0.565), tab[row, 7] * 0.8)
    color = _mul(color, 0.92 + 0.16 * tab[row, 6])
    color = _mul(color, 1.0 + 0.05 * nm(rng, 3.0, 0.1, 1.4) + 0.03 * nm(rng, 0.25, 0.01, 1.0)
                 + 0.012 * nm(rng, 0.008, px, 0.4) + 0.05 * rim1 - 0.03 * corr)
    iron = _s(nm(rng, 1.4, 0.04, 1.5), 1.1, 2.6)
    color = _mix(color, (0.63, 0.50, 0.37), iron * 0.3)
    color = _mix(color, (0.82, 0.785, 0.71), calcite * 0.6)
    color = _mix(color, (0.36, 0.33, 0.29), stain * 0.45)
    color = _mix(color, (0.45, 0.42, 0.38), groove * 0.3)
    color = _mix(color, (0.30, 0.28, 0.25), pits * 0.7)
    color = _mix(color, (0.22, 0.21, 0.19), joints * 0.7)
    rough = (0.84 + 0.04 * nm(rng, 0.3, 0.02, 1.0) - 0.28 * calcite - 0.22 * stain + 0.08 * pits
             - 0.04 * groove)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.012, cavity=0.3)


def rock_basalt(rng):
    """Volcanic basalt (lava tube wall): dark grey, soft blocky breaks and a few joints, vesicles (gas
    bubbles 3 mm to 4 cm) gathered in horizontal flow bands, a few filled with pale minerals
    (amygdales), rusty-brown weathering films and glassy patches."""
    px = T / N
    row, top, bot, th, nb = beds(rng, 0.25, 1.0, wave_m=0.08, big=3.0, jag_m=0.006)
    tab = rng.random((nb, 6))
    hf, ids = broken_rock(rng, [(0.6, 0.12, 0.004, 3.0), (0.2, 0.12, 0.0015, 2.0), (0.06, 0.14, 0.0005, 1.0)],
                          aniso=1.2, warp=0.12)
    joints = cracks(rng, 5, rng.uniform(0, math.pi), (0.6, 2.0), (1.2, 2.6), turn=0.05, spread=1.2)
    big = (0.05 * warped(rng, 4.0, 0.4, 1.9, 0.06) + 0.008 * nm(rng, 0.5, 0.06, 1.6)
           + 0.0015 * np.abs(nm(rng, 0.05, 0.006, 1.1)) - 0.008 * joints)
    db = np.minimum(top, bot)
    contact = np.exp(-(db / 0.012) ** 2) * _s(nm(rng, 1.5, 0.2, 1.5, aniso=5), -0.6, 0.6)
    band = _s(nm(rng, 1.6, 0.08, 1.4, aniso=7) + 2.0 * (tab[row, 0] - 0.5), -0.6, 1.2)
    ves = np.zeros((N, N))
    vd = np.zeros((N, N))
    fill = np.zeros((N, N))
    for size, keep in ((0.05, 0.2), (0.022, 0.3), (0.011, 0.4), (0.006, 0.45)):
        cells = int(round(T / size))
        wu, wv = warp_uv(rng, size * 0.2, size * 4, size * 0.8)
        f1, edge, idc, ru, rv = voronoi(rng, (cells, int(round(cells * 0.75))), wu, wv, 0.7)
        nc = idc.max() + 1
        r = rng.uniform(0.12, 0.34, nc)
        on = rng.random(nc)[idc] < keep * (0.15 + 1.3 * band)
        inside = np.clip(1 - (f1 / r[idc]) ** 2, 0, 1)
        aa = 0.6 * cells / N
        cov = _s(r[idc] - f1, -aa, aa) * on
        filled = (rng.random(nc) < 0.08)[idc]
        ves = np.maximum(ves, cov * ~filled)
        fill = np.maximum(fill, cov * filled)
        vd = np.maximum(vd, np.sqrt(inside) * r[idc] * size * 0.9 * on * ~filled)
    h = big + hf - vd - 0.008 * contact + 0.0003 * nm(rng, 0.012, px * 1.5, 0.6)
    color = _mul(_rgb((0.225, 0.222, 0.222)), 0.92 + 0.16 * tab[row, 1])
    t1 = rng.normal(0, 1, ids[1].max() + 1)
    color = _mul(color, 1.0 + 0.07 * nm(rng, 3.0, 0.08, 1.4) + 0.04 * nm(rng, 0.2, 0.01, 1.0)
                 + 0.035 * t1[ids[1]])
    spk = nm(rng, 0.006, px, 0.3)
    color = _mix(color, (0.34, 0.335, 0.325), _s(spk, 1.8, 2.8) * 0.45)
    weath = _s(nm(rng, 1.2, 0.03, 1.5), 0.6, 2.2)
    color = _mix(color, (0.31, 0.255, 0.21), weath * 0.55)
    glass = _s(nm(rng, 0.8, 0.05, 1.5), 1.2, 2.4)
    color = _mix(color, (0.14, 0.14, 0.145), glass * 0.5)
    color = _mix(color, (0.09, 0.087, 0.087), ves * 0.85)
    color = _mix(color, (0.25, 0.18, 0.13), ves * _s(nm(rng, 0.3, 0.02, 1.2), 0.5, 1.8) * 0.5)
    color = _mix(color, (0.74, 0.73, 0.69), fill * 0.85)
    color = _mix(color, (0.14, 0.135, 0.13), contact * 0.5)
    color = _mix(color, (0.07, 0.068, 0.066), joints * 0.8)
    rough = 0.86 + 0.03 * nm(rng, 0.3, 0.02, 1.0) - 0.28 * glass + 0.08 * ves - 0.1 * fill
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.012, cavity=0.3)


def profile1d(rng, n, octaves=((1, 1.0),)):
    """Random periodic 1-D profile sampled on n points (std 1); octaves (cycles scale, weight)
    of white noise filtered like the 2-D noise."""
    f = np.fft.rfftfreq(n) * n
    spec = np.zeros(len(f), complex)
    for f0, w in octaves:
        amp = np.where(f > 0, np.exp(-(f / f0) ** 2) * w, 0)
        spec = spec + np.fft.rfft(rng.standard_normal(n)) * amp
    p = np.fft.irfft(spec, n)
    return (p - p.mean()) / (p.std() + 1e-12)


def rock_sandstone(rng):
    """Red and ochre sandstone, water-sculpted: smooth flowing faces showing fine parallel
    laminae (3-10 mm) in cream, ochre and brick-red bands, in trough cross-bedded sets
    15-70 cm thick (curved laminae truncated by each set boundary); soft laminae eroded back
    into fine ridges, fine sand grain."""
    px = T / N
    row, top, bot, th, nb = beds(rng, 0.15, 0.7, wave_m=0.10, big=3.0, jag_m=0.002)
    tab = rng.random((nb, 6))
    k = rng.integers(1, 4, nb)
    amp = (0.03 + 0.12 * tab[:, 0]) / (2 * math.pi * k)
    curve = amp[row] * T * np.cos(2 * math.pi * (k[row] * U + tab[row, 1]))
    s_ = top + curve + 0.004 * nm(rng, 1.0, 0.1, 1.7) + tab[row, 2] * 10.0      # metres across the laminae
    M = 4096
    fine = profile1d(rng, M, ((M / 1.5, 1.0), (M / 6, 0.6)))
    zonep = profile1d(rng, M, ((M / 40, 1.0), (M / 15, 0.5)))
    span = 30.0                                                                 # metres per profile cycle
    idx = (s_ / span * M) % M
    i0 = np.floor(idx).astype(np.int64)
    fr = idx - i0
    lam = fine[i0] * (1 - fr) + fine[(i0 + 1) % M] * fr
    zone = zonep[i0] * (1 - fr) + zonep[(i0 + 1) % M] * fr
    lam = blur(lam, 0.6)
    db = np.minimum(top, bot)
    setline = np.exp(-(db / 0.006) ** 2) * _s(nm(rng, 1.2, 0.1, 1.5, aniso=5) + 0.5, -0.5, 0.5)
    big = 0.06 * warped(rng, 4.0, 0.3, 1.9, 0.08) + 0.01 * nm(rng, 0.8, 0.1, 1.8)
    grain = nm(rng, 0.004, px, 0.2)
    h = (big + 0.0012 * _s(lam, -1.2, 1.2) + 0.002 * zone - 0.006 * setline + 0.00025 * grain)
    t = 0.5 + 0.17 * zone + 0.06 * lam + 0.22 * (tab[row, 4] - 0.5) + 0.07 * nm(rng, 3.0, 0.3, 1.5)
    color = ramp(t, [(0.0, (0.87, 0.76, 0.60)), (0.3, (0.81, 0.63, 0.42)), (0.5, (0.74, 0.50, 0.32)),
                     (0.7, (0.65, 0.38, 0.24)), (1.0, (0.50, 0.27, 0.18))])
    color = _mul(color, 1.0 + 0.025 * nm(rng, 0.3, 0.02, 1.0) + 0.02 * grain)
    color = _mix(color, (0.88, 0.80, 0.67), _s(nm(rng, 1.0, 0.04, 1.4), 1.5, 2.7) * 0.35)
    color = _mix(color, (0.42, 0.26, 0.18), setline * 0.35)
    color = _mix(color, (0.32, 0.21, 0.15), _s(grain, 3.0, 3.7) * 0.4)
    rough = 0.88 + 0.03 * grain - 0.03 * setline
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.008, cavity=0.25)


def rock_slate(rng):
    """Dark blue-grey slate in thin plates (1.5-8 cm) standing out or broken back in sharp
    steps, split into blocks by vertical joints; pale fresh breaks along the plate edges,
    satin cleavage faces, fine lamination, rusty pyrite spots, a few thin quartz veins."""
    px = T / N
    row, top, bot, th, nb = beds(rng, 0.015, 0.08, wave_m=0.04, big=2.5, jag_m=0.0025)
    K = 3
    cuts = np.sort(rng.random((nb, K)), 1)
    uu = (U + 0.006 / T * nm(rng, 0.2, 0.01, 1.2)) % 1.0
    c = cuts[row]
    seg = (uu[..., None] > c).sum(-1) % K
    dcut = np.min(np.abs(_wrap(uu[..., None] - c)), -1) * T
    ident = row * K + seg
    tab = rng.random((nb * K, 6))
    proud = (tab[ident, 0] - 0.5) * 0.04
    lean = (tab[ident, 1] - 0.3) * 0.5
    face = proud + lean * (top - th / 2)
    edge = np.minimum(np.minimum(top, bot), dcut)
    chip = (1 - _s(edge, 0.0, 0.004 + 0.008 * tab[ident, 2])) * _s(nm(rng, 0.2, 0.02, 1.3), -0.8, 0.4)
    hf, ids = broken_rock(rng, [(0.3, 0.06, 0.002, 1.2), (0.08, 0.1, 0.0008, 0.7)], aniso=3.0, warp=0.12)
    lamin = nm(rng, 0.1, 0.002, 0.8, aniso=30)
    big = 0.04 * warped(rng, 4.0, 0.5, 1.9, 0.05)
    h = big + face + hf - 0.004 * chip + 0.0002 * lamin + 0.0001 * nm(rng, 0.01, px * 1.5, 0.6)
    tone = tab[ident, 3] - 0.5
    color = _mix(_rgb((0.255, 0.272, 0.300)), (0.262, 0.282, 0.270), _s(tab[ident, 4], 0.6, 1.0))
    color = _mix(color, (0.285, 0.265, 0.285), _s(tab[ident, 4], 0.0, 0.25) * 0.8)
    color = _mul(color, 1.0 + 0.14 * tone + 0.05 * nm(rng, 3.0, 0.1, 1.4) + 0.03 * lamin
                 + 0.02 * nm(rng, 0.15, 0.008, 1.0))
    color = _mix(color, (0.46, 0.475, 0.49), chip * (0.4 + 0.4 * tab[ident, 5]))
    rust = _s(nm(rng, 0.04, 0.004, 1.0) + 1.5 * _s(nm(rng, 1.0, 0.1, 1.5), 0.5, 1.5), 3.0, 3.8)
    halo = np.clip(blur(rust, 3) * 2.0, 0, 1)
    color = _mix(color, (0.40, 0.28, 0.18), halo * 0.4)
    color = _mix(color, (0.50, 0.30, 0.15), rust * 0.8)
    q = cracks(rng, 3, 0.5, (1.0, 2.5), (0.8, 1.8), turn=0.03, spread=0.5)
    color = _mix(color, (0.76, 0.76, 0.74), q * 0.8)
    rough = 0.58 + 0.15 * chip + 0.05 * tone + 0.03 * lamin + 0.2 * rust - 0.1 * q
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.012, cavity=0.4)


# ---------------------------------------------------------------------------
# b_floor = GROUND, 3 m per repeat
# ---------------------------------------------------------------------------
PEBBLES = np.array([(0.52, 0.50, 0.47), (0.63, 0.59, 0.52), (0.42, 0.38, 0.34), (0.56, 0.45, 0.34),
                    (0.31, 0.30, 0.29), (0.70, 0.67, 0.61)])


def scatter_stones(rng, color, h, sizes, under, power=0.5, height=0.35, bury=(0.0, 0.25), dusty=(0.1, 0.5),
                   margin=(0.1, 0.28), slope=0.0, pal=PEBBLES, rough=None, rough_stone=0.75, warp=0.25, jag=0.04):
    """Stones over a ground (largest first; smaller ones only show where they stand higher).
    sizes: [(size m, keep)]. `under` is the colour the dust on them is mixed toward."""
    px = T / N
    vis_all = np.zeros((N, N))
    base = h.copy()                      # every stone is seated on the ground, not on other stones
    for size, keep in sizes:
        cov, dome, idc, nc, ru, rv = stones(rng, size, keep, margin=margin, power=power, warp=warp, jag=jag)
        lvl = blur(base, size / px * 0.5) if size / px > 2 else base
        tilt = 0.0
        if slope:
            a, b = rng.normal(0, slope, nc), rng.normal(0, slope, nc)
            tilt = -(a[idc] * ru + b[idc] * rv) * size
        top = lvl + size * (height * dome - rng.uniform(*bury, nc)[idc]) + tilt * dome
        vis = cov * _s(top - h, -0.5 * px, 0.5 * px)
        cls = rng.integers(len(pal), size=nc)
        sc = pal[cls][idc] * rng.uniform(0.85, 1.12, nc)[idc][..., None]
        sc = _mul(sc, 1.0 + 0.05 * nm(rng, size * 0.6, px * 1.5, 0.8) + 0.08 * (dome - 0.5))
        sc = _mix(sc, under, rng.uniform(*dusty, nc)[idc] * (1 - 0.6 * dome))
        color = _mix(color, sc, vis)
        h = h + (top - h) * vis
        if rough is not None:
            rough = rough + (rough_stone + 0.05 * nm(rng, size, px * 2, 0.8) - rough) * vis
        vis_all = np.maximum(vis_all, vis)
    return color, h, rough, vis_all


def ground_earth(rng):
    """Packed cave earth: crumbly clods, trodden smoother paths, damp darker patches, dusty
    lighter crowns, small roots and grit, partly buried pebbles from 1 to 5 cm."""
    px = T / N
    trod = _s(nm(rng, 1.5, 0.2, 1.6), -0.4, 1.0)
    f1, edge, idc, _, _ = voronoi(rng, 150, *warp_uv(rng, 0.006, 0.06, 0.008), 0.9)
    clod = _s(edge, 0.0, 0.3) * rng.uniform(0.4, 1.0, idc.max() + 1)[idc]
    f1b, edgeb, idb, _, _ = voronoi(rng, 420, *warp_uv(rng, 0.002, 0.02, 0.003), 0.9)
    crumb = _s(edgeb, 0.0, 0.3) * rng.uniform(0.3, 1.0, idb.max() + 1)[idb]
    h = (0.015 * nm(rng, 3.0, 0.3, 1.9) + 0.003 * nm(rng, 0.3, 0.03, 1.5)
         + (0.003 * clod + 0.0012 * crumb) * (1 - 0.75 * trod) + 0.0002 * nm(rng, 0.006, px, 0.5))
    damp = _s(nm(rng, 1.2, 0.05, 1.6), 0.3, 1.6)
    color = _rgb((0.385, 0.305, 0.228))
    color = _mul(color, 1.0 + 0.06 * nm(rng, 2.5, 0.1, 1.4) + 0.05 * nm(rng, 0.1, 0.006, 0.9)
                 + 0.03 * nm(rng, 0.006, px, 0.4))
    color = _mix(color, (0.29, 0.225, 0.17), damp * 0.6)
    color = _mix(color, (0.47, 0.40, 0.32), (_s(clod, 0.5, 1.0) * 0.35 + trod * 0.15) * (1 - damp))
    roots = cracks(rng, 18, rng.uniform(0, math.pi), (0.05, 0.25), (0.6, 1.4), turn=0.12, spread=2.0)
    color = _mix(color, (0.18, 0.13, 0.09), roots * 0.6)
    h = h + 0.0006 * roots
    rough = 0.9 - 0.08 * trod - 0.15 * damp + 0.02 * nm(rng, 0.1, 0.01, 1.0)
    color, h, rough, _ = scatter_stones(rng, color, h, [(0.06, 0.07), (0.03, 0.12), (0.015, 0.18), (0.007, 0.15)],
                                        (0.40, 0.33, 0.26), power=0.55, height=0.35, bury=(0.02, 0.2),
                                        dusty=(0.05, 0.4), rough=rough, rough_stone=0.72)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.006, cavity=0.3)


def ground_sand(rng):
    """Fine pale cave sand: faint sinuous ripples (~7 cm) that fade in and out, darker
    heavy-mineral grains settled in the troughs, damp patches, the odd small pebble."""
    px = T / N
    a, b = int(rng.integers(-4, 5)), 42
    wu, wv = warp_uv(rng, 0.012, 1.0, 0.1)
    ph = (a * wu + b * wv + 1.2 * nm(rng, 1.5, 0.3, 1.8)) % 1.0
    prof = np.where(ph < 0.72, ph / 0.72, (1 - ph) / 0.28)
    prof = _s(prof, 0.0, 1.0)
    fade = _s(nm(rng, 1.2, 0.2, 1.7), -0.8, 1.0)
    rip = blur(prof, 1.2)
    h = (0.012 * nm(rng, 3.0, 0.4, 1.9) + 0.0025 * rip * fade + 0.0004 * nm(rng, 0.05, 0.005, 1.2)
         + 0.00012 * nm(rng, 0.004, px, 0.3))
    trough = (1 - _s(rip, 0.0, 0.4)) * fade
    damp = _s(nm(rng, 1.5, 0.1, 1.6), 0.6, 1.8)
    grain = nm(rng, 0.004, px, 0.2)
    color = _rgb((0.675, 0.620, 0.530))
    color = _mul(color, 1.0 + 0.04 * nm(rng, 2.5, 0.15, 1.4) + 0.018 * grain + 0.015 * nm(rng, 0.08, 0.008, 1.0))
    color = _mix(color, (0.50, 0.46, 0.40), trough * _s(nm(rng, 0.2, 0.01, 1.0), -0.5, 1.5) * 0.45)
    color = _mix(color, (0.55, 0.50, 0.43), damp * 0.5)
    color = _mix(color, (0.33, 0.31, 0.29), _s(grain, 2.8, 3.6) * 0.5)
    rough = 0.9 - 0.12 * damp + 0.02 * grain
    color, h, rough, _ = scatter_stones(rng, color, h, [(0.02, 0.012), (0.01, 0.02)], (0.62, 0.57, 0.49),
                                        power=0.6, height=0.35, bury=(0.05, 0.25), dusty=(0.2, 0.5),
                                        rough=rough, rough_stone=0.7)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.003, cavity=0.2)


def ground_gravel(rng):
    """Scree: loose angular limestone fragments from 2 to 16 cm with flat broken faces,
    packed so the smaller ones fill the gaps between the large ones, dark dusty hollows."""
    px = T / N
    h = 0.02 * nm(rng, 3.0, 0.4, 1.9) + 0.002 * nm(rng, 0.05, 0.005, 1.2)
    color = _mul(_rgb((0.25, 0.235, 0.22)), 1.0 + 0.08 * nm(rng, 0.2, 0.004, 1.0))
    rough = np.full((N, N), 0.92)
    pal = np.array([(0.60, 0.58, 0.54), (0.66, 0.635, 0.58), (0.53, 0.51, 0.48), (0.47, 0.455, 0.43),
                    (0.62, 0.56, 0.48), (0.71, 0.69, 0.65), (0.40, 0.39, 0.37)])
    color, h, rough, vis = scatter_stones(rng, color, h, [(0.16, 0.6), (0.09, 0.7), (0.05, 0.7), (0.028, 0.6),
                                                           (0.015, 0.5)],
                                          (0.42, 0.40, 0.37), power=0.35, height=0.45, bury=(0.0, 0.2),
                                          dusty=(0.0, 0.35), margin=(0.06, 0.2), slope=0.35, pal=pal,
                                          rough=rough, rough_stone=0.8, warp=0.08, jag=0.015)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.015, cavity=0.55)


def ground_mud(rng):
    """Wet dark cave mud: soft lumps, smears and sunk footprint-like hollows; the lowest
    hollows hold glossy flat puddles, a wet sheen around them, drier crusts on the crowns,
    a few embedded pebbles."""
    px = T / N
    h = 0.008 * nm(rng, 3.0, 0.5, 1.9) + 0.007 * nm(rng, 0.6, 0.05, 1.6)
    smear = nm(rng, 0.3, 0.02, 1.3, aniso=4, ang=rng.uniform(0, math.pi))
    h = h + 0.0015 * smear
    for _ in range(30):
        cx, cy = rng.random() * N, rng.random() * N
        r = rng.uniform(0.04, 0.12) / px
        idx, dx, dy = window(cx, cy, r * 1.6, r * 1.6)
        ang = rng.uniform(0, math.pi)
        ex = (dx * math.cos(ang) + dy * math.sin(ang)) / 1.6
        ey = -dx * math.sin(ang) + dy * math.cos(ang)
        dd = np.sqrt(ex * ex + ey * ey) / r
        h[idx] = h[idx] - rng.uniform(0.004, 0.01) * np.exp(-dd ** 2 * 2.5)
    h = h + 0.0002 * nm(rng, 0.01, px * 1.5, 0.6)
    color = _rgb((0.205, 0.160, 0.122))
    color = _mul(color, 1.0 + 0.07 * nm(rng, 2.0, 0.08, 1.4) + 0.03 * smear)
    rough = 0.5 + 0.1 * nm(rng, 0.3, 0.02, 1.2)
    color, h, rough, _ = scatter_stones(rng, color, h, [(0.04, 0.03), (0.018, 0.05), (0.008, 0.06)],
                                        (0.20, 0.16, 0.12), power=0.6, height=0.3, bury=(0.1, 0.25),
                                        dusty=(0.4, 0.8), rough=rough, rough_stone=0.45)
    hn = (h - h.mean()) / h.std()
    dry = _s(hn + 0.4 * nm(rng, 0.8, 0.05, 1.5), 1.0, 2.2)
    color = _mix(color, (0.33, 0.275, 0.215), dry * 0.7)
    rough = rough + (0.82 - rough) * dry
    hs = blur(h, 5.0)
    level = np.percentile(hs, 16)
    pud = _s(level - hs, 0.0, 0.0008)
    wet = _s(level + 0.003 - hs, 0.0, 0.003)
    color = _mul(color, 1.0 - 0.18 * wet)
    color = _mix(color, _mul(color, 0.62), pud)
    rough = rough - 0.2 * wet * (1 - pud)
    rough = rough + (0.03 - rough) * pud
    h = h + (level - h) * pud
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.006, cavity=0.25)


# ---------------------------------------------------------------------------
# c_wood = WOOD, 1.2 m per repeat (grain along U)
# ---------------------------------------------------------------------------
def log_grain(rng, lines, wave=1.2, knots=0):
    """Continuous grain of a log surface (no boards): `lines` growth lines per repeat across
    V, flowing gently and swirling round a few knots. Periodic in U and V.
    Returns ring fraction, late-wood profile, knot mask."""
    px = T / N
    ring = lines * V + wave * nm(rng, 0.8, 0.06, 1.7, aniso=5) + 0.25 * nm(rng, 0.15, 0.02, 1.3, aniso=6)
    kmask = np.zeros((N, N))
    for _ in range(knots):
        cx, cy = rng.random() * N, rng.random() * N
        r = rng.uniform(0.008, 0.02) / px
        idx, dx, dy = window(cx, cy, r * 8, r * 3)
        el = np.sqrt((dx / 2.5) ** 2 + dy ** 2)
        ring[idx] = ring[idx] + 4.0 * np.exp(-(el / (r * 1.4)) ** 2)
        stamp_max(kmask, idx, _s(1.0 - np.sqrt((dx / 1.2) ** 2 + dy ** 2) / r, 0.0, 0.3))
    fr = ring - np.floor(ring)
    late = _s(fr, 0.4, 0.9) * (1 - _s(fr, 0.95, 1.0))
    return fr, late, kmask


def checks(rng, count, length_m, width_px):
    """Drying checks: cracks along the grain."""
    return cracks(rng, count, 0.0, length_m, width_px, turn=0.015, spread=0.03)


def wood_driftwood(rng):
    """Driftwood: bleached silver-grey, soft early wood worn away so the late-wood lines
    stand proud, long checks, warm brown left in the grooves, smooth worn crowns."""
    px = T / N
    fr, late, kn = log_grain(rng, 160, wave=1.6, knots=3)
    fib = noise(rng, 6, N / 2, 0.55, aniso=30)
    ck = checks(rng, 40, (0.05, 0.5), (0.8, 3.0))
    worn = _s(nm(rng, 0.4, 0.05, 1.6), -0.5, 1.5)
    h = (0.0012 * late * (1 - 0.5 * worn) + 0.00003 * fib + 0.004 * nm(rng, 0.6, 0.05, 1.7, aniso=4)
         - 0.003 * ck + 0.001 * kn)
    color = _mix(_rgb((0.70, 0.675, 0.63)), (0.55, 0.53, 0.50), late * 0.8)
    color = _mul(color, 1.0 + 0.03 * fib + 0.05 * nm(rng, 0.8, 0.05, 1.3, aniso=4))
    groove = 1 - late
    color = _mix(color, (0.50, 0.44, 0.37), groove * _s(nm(rng, 0.5, 0.03, 1.4), -0.2, 1.5) * 0.4)
    color = _mix(color, (0.78, 0.765, 0.73), worn * late * 0.35)
    color = _mix(color, (0.25, 0.21, 0.17), ck * 0.85)
    color = _mix(color, (0.42, 0.36, 0.30), kn * 0.7)
    rough = 0.8 + 0.03 * fib - 0.06 * worn + 0.1 * ck
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0015, cavity=0.3)


def wood_timber(rng):
    """Old dark-brown timber (beams and planks 16-30 cm): weathered grain in relief, worn
    rounded edges and open joints between the boards, long drying checks, shallow adze
    scallops, grime, a few rusty nail holes."""
    px = T / N
    Y, bw, ident, nb = boards_v(rng, 0.16, 0.30)
    sp = dict(early=(0.335, 0.240, 0.160), late=(0.205, 0.140, 0.090), pore=(0.13, 0.085, 0.05),
              ray=(0.37, 0.27, 0.18), streak=(0.17, 0.12, 0.08), sap=(0.42, 0.31, 0.21),
              sp=(0.003, 0.008), porous="ring", rough=0.72, relief=0.0004, pore_depth=0.00015,
              contrast=0.9, pore_c=0.4)
    color, h, rough, late = wood_surface(rng, sp, Y, bw, ident, nb)
    ck = checks(rng, 30, (0.08, 0.6), (0.8, 2.6))
    adze = nm(rng, 0.1, 0.03, 1.2, aniso=2.5, ang=math.pi / 2)
    grime = _s(nm(rng, 0.6, 0.03, 1.5), -0.2, 1.8)
    dm = np.minimum(Y, bw - Y)
    hj, face = joint_profile(dm, 0.0012, 0.006, 0.004)
    h = h * face + hj + 0.0007 * adze - 0.003 * ck
    color = _mul(color, 1.0 - 0.25 * grime)
    color = _mix(color, (0.11, 0.08, 0.06), ck * 0.85)
    color = _mix(_mul(color, 0.5), color, _s(dm, 0.0012, 0.006))
    nails = np.zeros((N, N))
    for _ in range(5):
        cx, cy = rng.random() * N, rng.random() * N
        idx, dx, dy = window(cx, cy, 0.03 / px)
        dd = np.sqrt(dx * dx + dy * dy) * px
        stamp_max(nails, idx, np.exp(-(dd / 0.012) ** 2))
        h[idx] = h[idx] - 0.002 * _s(0.003 - dd, -0.0005, 0.0005)
    color = _mix(color, (0.26, 0.13, 0.07), nails * 0.6)
    rough = rough + 0.08 * grime + 0.15 * ck
    rough = _mix(0.85, rough, face)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.002, cavity=0.3)


def wood_charred(rng):
    """Burnt wood: alligatored char blocks (about 4 x 2 cm) split by deep cracks, rounded
    satin grey-black crowns with the grain still faint in them, red-brown less-burnt wood at
    the bottom of some cracks, a little grey ash."""
    px = T / N
    fr, late, kn = log_grain(rng, 150, wave=1.0, knots=2)
    wu, wv = warp_uv(rng, 0.004, 0.12, 0.02)
    f1, edge, idc, ru, rv = voronoi(rng, (20, 58), wu, wv, 0.9)
    nc = idc.max() + 1
    bh = rng.uniform(0.6, 1.0, nc)[idc]
    cw = 0.06 + 0.06 * rng.random(nc)[idc]
    crack = 1 - _s(edge, 0.0, cw)
    dome = np.sqrt(np.clip(edge / 0.5, 0, 1)) * bh
    fine = 1 - _s(contour_dist(nm(rng, 0.03, 0.006, 1.0, aniso=3)), 0.0, 1.0)
    h = (0.005 * dome - 0.004 * crack + 0.0003 * late - 0.0003 * fine * dome
         + 0.002 * nm(rng, 0.5, 0.05, 1.7, aniso=3))
    sheen = _s(nm(rng, 0.15, 0.01, 1.2) + 0.8 * (bh - 0.8) * 5, -1.0, 1.5)
    crown = _s(dome, 0.2, 0.9)
    color = _mix(_rgb((0.055, 0.050, 0.047)), (0.150, 0.142, 0.135), crown * (0.35 + 0.65 * sheen))
    color = _mul(color, 1.0 + 0.2 * late * crown - 0.25 * fine * crown)
    lessburnt = _s(nm(rng, 0.5, 0.04, 1.5), 0.3, 1.5)
    color = _mix(color, (0.25, 0.12, 0.06), crack * lessburnt * 0.75)
    color = _mix(color, (0.018, 0.016, 0.015), crack * (1 - lessburnt) * 0.85)
    ash = _s(nm(rng, 0.25, 0.01, 1.4), 1.6, 2.6)
    color = _mix(color, (0.42, 0.41, 0.39), ash * crown * 0.6)
    rough = 0.62 - 0.22 * crown * sheen + 0.3 * crack + 0.25 * ash
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.003, cavity=0.35)


def wood_bark(rng):
    """Rough log bark (furrows along the grain): long corky ridges 2-6 cm wide that split and
    rejoin, separated by deep narrow red-brown furrows, broken across here and there; flaky
    layered grey-brown ridge tops, a few grey-green lichen spots."""
    px = T / N
    wu, wv = warp_uv(rng, 0.006, 0.4, 0.03)
    n1 = sample(nm(rng, 0.2, 0.012, 1.1, aniso=6), wu - U, wv - V)
    ridge = _s(np.abs(n1), 0.03, 1.1) * (0.75 + 0.25 * _s(nm(rng, 0.3, 0.03, 1.3), -1, 1))
    flake = nm(rng, 0.06, 0.004, 1.2, aniso=4)
    terr = blur(np.floor(flake * 1.4) / 1.4, 0.8)
    fib = noise(rng, 6, N / 2, 0.6, aniso=14)
    h = 0.016 * ridge + 0.0012 * terr * ridge + 0.0001 * fib + 0.003 * nm(rng, 0.6, 0.06, 1.7)
    t = ridge + 0.1 * nm(rng, 0.3, 0.02, 1.2) + 0.06 * terr
    color = ramp(t, [(0.0, (0.10, 0.065, 0.045)), (0.3, (0.22, 0.14, 0.095)), (0.65, (0.33, 0.25, 0.19)),
                     (1.0, (0.42, 0.36, 0.30))])
    color = _mul(color, 1.0 + 0.05 * fib + 0.05 * terr)
    grey = _s(nm(rng, 0.6, 0.04, 1.5), 0.3, 1.8) * _s(ridge, 0.6, 1.0)
    color = _mix(color, (0.50, 0.48, 0.45), grey * 0.3)
    lich = _s(nm(rng, 0.05, 0.004, 1.0) + 1.5 * _s(nm(rng, 0.8, 0.1, 1.5), 0.5, 1.5), 2.9, 3.4) * _s(ridge, 0.5, 0.8)
    color = _mix(color, (0.55, 0.58, 0.47), lich * 0.8)
    rough = 0.92 - 0.05 * grey + 0.03 * fib
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.008, cavity=0.45)


# ---------------------------------------------------------------------------
# d_stone = MOSS / WET STONE, 3 m per repeat
# ---------------------------------------------------------------------------
def stone_base(rng):
    """Natural stone surface for the moss/wet/lichen family: broad weathered forms, soft
    angular breaks (low-tilt facets, blurred into bevels), knobbly roughness."""
    px = T / N
    hf, ids = broken_rock(rng, [(0.5, 0.08, 0.002, 3.5 * 0.01 / px), (0.16, 0.08, 0.0008, 1.8 * 0.01 / px)],
                          warp=0.12)
    h = (0.045 * warped(rng, 3.0, 0.3, 1.9, 0.06) + hf + 0.004 * nm(rng, 0.12, 0.01, 1.3)
         + 0.0012 * np.abs(nm(rng, 0.03, 0.004, 1.0)) + 0.0002 * nm(rng, 0.01, px * 1.5, 0.6))
    return h, ids




def stone_moss(rng):
    """Damp grey stone under thick green moss: cushions 2-3 cm across, fuzzy tops,
    yellow-green tips on the crowns, dark green in the dips, browned dead patches; bare
    rock shows in the cracks and on the steepest faces."""
    px = T / N
    hs, ids = stone_base(rng)
    stone = _mul(_rgb((0.36, 0.35, 0.325)), 1.0 + 0.08 * nm(rng, 1.0, 0.02, 1.3))
    hn = (hs - hs.mean()) / hs.std()
    cover = nm(rng, 0.8, 0.02, 1.4) + 0.5 * hn + 0.3 * nm(rng, 0.03, 0.006, 1.0)
    moss = _s(cover, -0.6, -0.2)
    f1, edge, idc, _, _ = voronoi(rng, 120, *warp_uv(rng, 0.006, 0.1, 0.01), 0.9)
    cush = np.sqrt(np.clip(edge / 0.5, 0, 1)) * rng.uniform(0.6, 1.0, idc.max() + 1)[idc]
    fuzz = nm(rng, 0.006, px * 1.2, 0.5)
    fuzz2 = nm(rng, 0.02, 0.004, 1.0)
    hm = moss * (0.006 + 0.005 * cush + 0.0008 * fuzz + 0.0008 * fuzz2)
    h = hs + hm
    tone = 0.45 * cush + 0.25 * fuzz + 0.15 * fuzz2
    mc = ramp(0.5 + 0.35 * (tone - 0.45) + 0.15 * nm(rng, 1.0, 0.1, 1.4),
              [(0.0, (0.09, 0.14, 0.05)), (0.35, (0.19, 0.29, 0.09)), (0.65, (0.31, 0.40, 0.13)),
               (1.0, (0.47, 0.52, 0.20))])
    dead = _s(nm(rng, 0.6, 0.03, 1.5), 1.0, 2.2)
    mc = _mix(mc, _mul(_rgb((0.36, 0.30, 0.16)), 0.8 + 0.4 * cush), dead * 0.7)
    color = _mix(stone, mc, moss)
    color = _mul(color, 1.0 - 0.2 * moss * (1 - _s(moss, 0.0, 1.0)))
    rough = _mix(np.full((N, N), 0.6), 0.92 + 0.03 * fuzz, moss)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.008, cavity=0.4)


def stone_wet(rng):
    """Dark wet stone: broken faces under a water film (low roughness), thin calcite veins,
    trickle channels running down, drier crowns slightly rougher, pools in the hollows."""
    px = T / N
    h, ids = stone_base(rng)
    t1 = rng.normal(0, 1, ids[1].max() + 1)
    color = _mul(_rgb((0.175, 0.170, 0.162)), 1.0 + 0.1 * nm(rng, 2.0, 0.05, 1.4) + 0.05 * t1[ids[1]]
                 + 0.04 * nm(rng, 0.1, 0.006, 1.0))
    color = _mix(color, (0.21, 0.18, 0.15), _s(nm(rng, 1.0, 0.05, 1.5), 0.5, 2.0) * 0.5)
    veins = cracks(rng, 6, rng.uniform(0, math.pi), (0.5, 2.0), (0.7, 1.8), turn=0.06, spread=0.6)
    color = _mix(color, (0.55, 0.54, 0.51), veins * 0.7)
    trick = _s(nm(rng, 1.5, 0.01, 1.0, aniso=14, ang=math.pi / 2), 1.3, 2.4)
    color = _mul(color, 1.0 - 0.15 * trick)
    hn = (h - h.mean()) / h.std()
    dry = _s(hn + 0.5 * nm(rng, 0.6, 0.05, 1.5), 1.3, 2.6)
    pool = _s(-hn, 1.6, 2.2)
    color = _mix(color, (0.27, 0.26, 0.245), dry * 0.4)
    rough = 0.22 + 0.06 * nm(rng, 0.3, 0.01, 1.0) + 0.28 * dry - 0.12 * trick
    rough = rough + (0.04 - rough) * pool
    h = h + 0.0003 * trick
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.008, cavity=0.3)


def stone_lichen(rng):
    """Pale grey stone with crustose lichen: round colonies 1-10 cm with lobed margins,
    yellow-orange, grey-green and white, cracked older centres, black fruiting dots."""
    px = T / N
    h, ids = stone_base(rng)
    t1 = rng.normal(0, 1, ids[1].max() + 1)
    color = _mul(_rgb((0.55, 0.54, 0.515)), 1.0 + 0.06 * nm(rng, 2.0, 0.04, 1.4) + 0.03 * t1[ids[1]]
                 + 0.03 * nm(rng, 0.05, 0.005, 1.0))
    color = _mix(color, (0.42, 0.40, 0.37), _s(nm(rng, 1.0, 0.03, 1.4), 0.8, 2.2) * 0.4)
    _, cedge, _, _, _ = voronoi(rng, 380, U, V, 0.9)
    areole = 1 - _s(cedge, 0.0, 0.12)
    cols = np.array([(0.80, 0.56, 0.17), (0.86, 0.68, 0.25), (0.62, 0.67, 0.54), (0.80, 0.80, 0.75),
                     (0.50, 0.55, 0.42), (0.70, 0.45, 0.16)])
    prob = np.array([0.22, 0.14, 0.26, 0.16, 0.14, 0.08])
    lich = np.zeros((N, N))
    lc = np.zeros((N, N, 3))
    cent = np.zeros((N, N))
    dens = _s(nm(rng, 1.0, 0.15, 1.5), -1.0, 0.8)
    for _ in range(1100):
        for _ in range(20):
            cx, cy = rng.random() * N, rng.random() * N
            if rng.random() < dens[int(cy) % N, int(cx) % N]:
                break
        r = rng.choice([rng.uniform(0.008, 0.025), rng.uniform(0.025, 0.07)], p=[0.6, 0.4]) / px
        k = rng.choice(len(cols), p=prob)
        idx, dx, dy = window(cx, cy, r * 1.3)
        dd = np.sqrt(dx * dx + dy * dy)
        ang = np.arctan2(dy, dx)
        lobes = 1 + 0.08 * np.sin(int(rng.integers(9, 18)) * ang + rng.uniform(0, 6)) \
            + 0.05 * np.sin(int(rng.integers(3, 7)) * ang + rng.uniform(0, 6))
        m = _s(r * lobes - dd, -0.7, 0.7)
        new = m * (1 - lich[idx])
        c = cols[k] * rng.uniform(0.9, 1.08)
        lc[idx] = lc[idx] + (c - lc[idx]) * m[..., None]
        lich[idx] = np.maximum(lich[idx], m)
        stamp_max(cent, idx, m * _s(0.6 * r - dd, 0, r * 0.3))
        del new
    dots = _s(nm(rng, 0.005, px, 0.3), 2.6, 3.2) * cent
    lt = _mul(lc, 1.0 + 0.08 * nm(rng, 0.01, px * 1.5, 0.6) - 0.15 * areole * cent)
    color = _mix(color, lt, lich * 0.92)
    color = _mix(color, (0.08, 0.075, 0.07), dots * 0.8)
    h = h + 0.0003 * lich - 0.0002 * areole * lich + 0.0002 * dots
    rough = 0.82 + 0.05 * lich + 0.03 * nm(rng, 0.2, 0.01, 1.0)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.008, cavity=0.3)


def stone_flowstone(rng):
    """Flowstone: creamy calcite poured over the rock in rounded bulging lobes and draperies
    running down (+V), whiter on the thick crowns, honey to orange-brown where iron-stained
    water runs in the grooves, small rimstone ridges across the flow, a wet satin film."""
    px = T / N
    wu, wv = warp_uv(rng, 0.05, 1.5, 0.2)
    f1, edge, idc, _, _ = voronoi(rng, (9, 6), wu, wv, 0.9)
    lobe = np.sqrt(np.clip(1 - (f1 / 0.75) ** 2, 0, 1)) * rng.uniform(0.6, 1.0, idc.max() + 1)[idc]
    f1b, _, idb, _, _ = voronoi(rng, (26, 18), *warp_uv(rng, 0.02, 0.5, 0.06), 0.9)
    lobe2 = np.sqrt(np.clip(1 - (f1b / 0.75) ** 2, 0, 1)) * rng.uniform(0.5, 1.0, idb.max() + 1)[idb]
    drape = nm(rng, 1.0, 0.04, 1.5, aniso=5, ang=math.pi / 2)
    k = 30
    rimf = (k * V + 1.5 * nm(rng, 1.2, 0.1, 1.7, aniso=2) + 0.3 * drape) % 1.0
    rim = np.exp(-((rimf - 0.85) / 0.06) ** 2) * _s(nm(rng, 1.0, 0.1, 1.5), -0.2, 0.8)
    rim = blur(rim, 1.2)
    h = (0.04 * nm(rng, 3.0, 0.5, 1.9) + 0.035 * blur(lobe, 6) + 0.012 * blur(lobe2, 3) + 0.006 * drape
         + 0.002 * rim + 0.0003 * nm(rng, 0.03, 0.004, 1.2))
    hn = nrm01(blur(h, 4))
    groove = _s(drape, 0.3, 1.8) * (1 - _s(hn, 0.4, 0.8))
    t = 0.38 - 0.25 * (hn - 0.5) + 0.35 * groove + 0.1 * nm(rng, 2.0, 0.15, 1.5)
    color = ramp(t, [(0.0, (0.94, 0.90, 0.81)), (0.3, (0.89, 0.81, 0.66)), (0.55, (0.82, 0.68, 0.48)),
                     (0.8, (0.70, 0.52, 0.33)), (1.0, (0.56, 0.38, 0.23))])
    color = _mul(color, 1.0 + 0.02 * nm(rng, 0.05, 0.004, 1.0) + 0.015 * nm(rng, 0.6, 0.008, 1.0, aniso=8,
                                                                          ang=math.pi / 2))
    color = _mix(color, (0.95, 0.93, 0.87), rim * 0.35)
    rough = 0.28 + 0.06 * nm(rng, 0.5, 0.02, 1.2) + 0.1 * rim - 0.06 * groove
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.012, cavity=0.2)


# ---------------------------------------------------------------------------
# e_fabric = FUR / LEATHER, 0.8 m per repeat
# ---------------------------------------------------------------------------
def fur_layers(rng, theta, layers, locks, lock_len, lock_w, per_lock, width, curl, ss=2):
    """Locks of hair drawn on the torus, bottom layer first. Every strand is four tapered
    quads; the canvas channels hold coverage, the strand tone and the position along the
    strand (root 0 .. tip 1). Strands in a lock converge on its tip. Returns a list of
    (coverage, tone, along) per layer."""
    px = T / N
    out = []
    for _ in range(layers):
        im = Image.new("RGB", (N * ss, N * ss), (0, 0, 0))
        d = ImageDraw.Draw(im)
        for _ in range(locks):
            cx, cy = rng.random() * N, rng.random() * N
            a0 = float(theta[int(cy) % N, int(cx) % N]) + rng.normal(0, 0.1)
            L = lock_len / px * rng.uniform(0.7, 1.3)
            Wd = lock_w / px * rng.uniform(0.6, 1.4)
            lt = rng.random()
            bend = rng.normal(0, curl)
            ca, sa = math.cos(a0), math.sin(a0)
            for _ in range(per_lock):
                off = rng.uniform(-0.5, 0.5) * Wd
                al = rng.uniform(-0.3, 0.1) * L
                x, y = cx + ca * al - sa * off, cy + sa * al + ca * off
                a = a0 + rng.normal(0, 0.05) - 0.4 * off / L
                ln = L * rng.uniform(0.55, 1.0)
                k = bend + rng.normal(0, curl * 0.4)
                w0 = width * rng.uniform(0.7, 1.3)
                tone = int(255 * min(1.0, max(0.0, 0.5 * lt + 0.5 * rng.random())))
                pts = [(x, y)]
                ws = [w0]
                for i in range(1, 5):
                    t = i / 4
                    aa = a + k * t
                    x += math.cos(aa) * ln / 4
                    y += math.sin(aa) * ln / 4
                    pts.append((x, y))
                    ws.append(w0 * (1 - 0.8 * t))
                xs = [p[0] for p in pts]
                ys = [p[1] for p in pts]
                oxs = [o for o in (-N, 0, N) if max(xs) + o > -2 and min(xs) + o < N + 2]
                oys = [o for o in (-N, 0, N) if max(ys) + o > -2 and min(ys) + o < N + 2]
                quads = []
                for i in range(4):
                    (x0, y0), (x1, y1) = pts[i], pts[i + 1]
                    dx, dy = x1 - x0, y1 - y0
                    ln_ = math.hypot(dx, dy) or 1.0
                    nx, ny = -dy / ln_, dx / ln_
                    h0, h1 = ws[i] * 0.5, ws[i + 1] * 0.5
                    quads.append(([(x0 + nx * h0, y0 + ny * h0), (x1 + nx * h1, y1 + ny * h1),
                                   (x1 - nx * h1, y1 - ny * h1), (x0 - nx * h0, y0 - ny * h0)],
                                  (255, tone, int(255 * (i + 0.5) / 4))))
                for ox in oxs:
                    for oy in oys:
                        for q, fill in quads:
                            d.polygon([((qx + ox) * ss, (qy + oy) * ss) for qx, qy in q], fill=fill)
        a = np.asarray(im.resize((N, N), Image.BOX), dtype=float)
        cov = a[..., 0] / 255.0
        den = np.maximum(a[..., 0], 1.0)
        out.append((cov, a[..., 1] / den, a[..., 2] / den))
    return out


def fur(rng, pal, under, flow_amp, lock_len, lock_w, per_lock, locks, layers=4, width=1.5, curl=0.25):
    """Animal pelt: hair lying mostly down the repeat (+V) with sweeping partings, drawn as
    locks in layers over a dark undercoat. pal(tone, along, region) -> colour."""
    px = T / N
    theta = (math.pi / 2 + flow_amp * nm(rng, 0.5, 0.08, 1.8)
             + 0.3 * flow_amp * nm(rng, 0.12, 0.03, 1.4))
    region = nm(rng, 0.8, 0.1, 1.6)
    lay = fur_layers(rng, theta, layers, locks, lock_len, lock_w, per_lock, width, curl)
    color = _mul(_rgb(under), 1.0 + 0.12 * nm(rng, 0.03, px * 2, 0.8, aniso=4, ang=math.pi / 2))
    hgt = np.zeros((N, N))
    dl = 0.0005
    for l, (cov, tone, along) in enumerate(lay):
        sc = pal(tone, along, region)
        hl = (l + 1) * dl + dl * (0.5 * along + 0.6 * (tone - 0.5))
        color = color + (sc - color) * cov[..., None]
        hgt = hgt + (hl - hgt) * cov
    top = hgt / hgt.max()
    rough = 0.93 - 0.16 * top
    return dict(color=color, h=hgt, rough=rough, metal=0.0, depth=0.0012, cavity=0.5)


def _wolf(tone, along, region):
    guard = _s(tone + 0.15 * region, 0.32, 0.52)
    banded = ramp(along, [(0.0, (0.60, 0.57, 0.52)), (0.4, (0.68, 0.63, 0.55)), (0.62, (0.56, 0.50, 0.42)),
                          (0.8, (0.20, 0.18, 0.165)), (1.0, (0.10, 0.095, 0.09))])
    pale = ramp(along, [(0.0, (0.52, 0.505, 0.48)), (1.0, (0.70, 0.685, 0.65))])
    c = _mix(pale, banded, guard)
    c = _mix(c, (0.58, 0.47, 0.35), _s(region, 0.3, 1.6)[..., None] * 0.4 * (1 - guard)[..., None])
    return _mul(c, 0.86 + 0.28 * tone)


def _bear(tone, along, region):
    tipped = _s(tone + 0.15 * region, 0.55, 0.75)
    plain = ramp(along, [(0.0, (0.13, 0.085, 0.05)), (1.0, (0.25, 0.16, 0.095))])
    tip = ramp(along, [(0.0, (0.14, 0.09, 0.055)), (0.5, (0.27, 0.175, 0.10)), (1.0, (0.45, 0.31, 0.18))])
    return _mul(_mix(plain, tip, tipped), 0.85 + 0.3 * tone)


def fabric_fur_grey(rng):
    """Grey wolf pelt: agouti guard hairs (pale root, tan band, black tip) over a pale
    grey-cream underfur, lying in locks 2-4 cm long."""
    return fur(rng, _wolf, (0.36, 0.34, 0.31), 0.55, 0.030, 0.008, 9, 2600, layers=4, width=1.5, curl=0.25)


def fabric_fur_brown(rng):
    """Brown bear pelt: long shaggy dark-brown hair with sun-bleached golden tips."""
    return fur(rng, _bear, (0.08, 0.055, 0.035), 0.7, 0.045, 0.010, 10, 1700, layers=4, width=1.8, curl=0.35)


def fabric_leather(rng):
    """Tanned hide: pebbled grain, soft folds and crease lines, uneven tan with darker
    stains and lighter rubbed spots, a healed scar or two."""
    px = T / N
    folds = nm(rng, 0.5, 0.05, 1.8)
    f1, edge, idc, _, _ = voronoi(rng, 260, *warp_uv(rng, 0.0008, 0.02, 0.003), 0.9)
    peb = _s(edge, 0.0, 0.3)
    crease = np.zeros((N, N))
    for _ in range(3):
        n = nm(rng, 0.12, 0.012, 1.3, aniso=4, ang=rng.uniform(0, math.pi))
        crease = np.maximum(crease, _s(-n, 0.8, 2.2) * _s(nm(rng, 0.3, 0.05, 1.4), 0.0, 1.2))
    scars = blur(cracks(rng, 2, rng.uniform(0, math.pi), (0.04, 0.1), (1.5, 2.5), turn=0.03, spread=0.3), 1.5)
    rub = _s(folds + 0.5 * nm(rng, 0.2, 0.02, 1.4), 0.8, 2.0)
    h = 0.0015 * folds + 0.00006 * peb - 0.0004 * crease - 0.00015 * scars + 0.00003 * nm(rng, 0.004, px, 0.5)
    color = _rgb((0.49, 0.335, 0.205))
    color = _mul(color, 1.0 + 0.06 * nm(rng, 0.6, 0.02, 1.4) + 0.05 * peb + 0.025 * nm(rng, 0.006, px, 0.4))
    stain = _s(nm(rng, 0.5, 0.03, 1.5), 1.2, 2.4)
    color = _mix(color, (0.34, 0.215, 0.125), stain * 0.5)
    color = _mix(color, (0.60, 0.45, 0.30), rub * 0.35)
    color = _mix(color, (0.36, 0.23, 0.13), crease * 0.3)
    color = _mix(color, (0.56, 0.42, 0.29), scars * 0.35)
    rough = 0.66 - 0.18 * rub + 0.08 * crease + 0.04 * peb - 0.05 * stain
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0004, cavity=0.3)


def fabric_wool(rng):
    """Rough hand-woven wool, plain weave of thick uneven hand-spun yarn (~4.5 mm), slubs,
    a fuzzy halo and stray fibres. Near-white and low in colour so scripts can tint it."""
    px = T / N
    threads = 176
    gx = (U + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    gy = (V + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    slub_u = 1.0 + 0.3 * _s(noise(rng, 16, N / 2, 0.5, aniso=10, ang=math.pi / 2), 0.4, 2.4) \
        - 0.12 * _s(-noise(rng, 16, N / 2, 0.5, aniso=10, ang=math.pi / 2), 0.8, 2.4)
    slub_v = 1.0 + 0.3 * _s(noise(rng, 16, N / 2, 0.5, aniso=10), 0.4, 2.4) \
        - 0.12 * _s(-noise(rng, 16, N / 2, 0.5, aniso=10), 0.8, 2.4)
    si, sj = rng.random(threads), rng.random(threads)
    i = np.floor(gx).astype(np.int64)
    j = np.floor(gy).astype(np.int64)
    fx, fy = gx - i, gy - j
    over = ((i + j) % 2) == 0
    wu_ = np.clip((0.75 + 0.25 * si[i % threads]) * slub_u, 0.5, 1.0)
    wv_ = np.clip((0.75 + 0.25 * sj[j % threads]) * slub_v, 0.5, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / wu_) ** 2, 0.0, 1.0))
    cvv = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / wv_) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    tw_u = np.sin(2 * math.pi * (gy * 2.2 + fx * 0.8))      # plied twist
    tw_v = np.sin(2 * math.pi * (gx * 2.2 + fy * 0.8))
    h_warp = cu * (0.55 + 0.45 * np.where(over, ou, -ou)) * slub_u
    h_weft = cvv * (0.55 + 0.45 * np.where(over, -ov, ov)) * slub_v
    top = h_warp > h_weft
    hh = np.maximum(h_warp, h_weft)
    tw = np.where(top, tw_u * cu, tw_v * cvv)
    tone_t = np.where(top, si[i % threads], sj[j % threads]) - 0.5
    fuzz = nm(rng, 0.004, px, 0.4)
    stray = cracks(rng, 120, rng.uniform(0, math.pi), (0.01, 0.04), (0.6, 1.0), turn=0.15, spread=2.0,
                   value=(120, 220))
    color = _rgb((0.875, 0.860, 0.825))
    color = _mul(color, (0.80 + 0.2 * hh) * (1.0 + 0.04 * tone_t + 0.03 * tw + 0.03 * fuzz
                                              + 0.02 * nm(rng, 0.3, 0.03, 1.3)))
    color = _mix(color, (0.92, 0.91, 0.88), stray * 0.6)
    h = 0.0012 * hh + 0.00012 * tw + 0.00006 * fuzz + 0.0002 * stray
    rough = 0.93 + 0.02 * fuzz
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0015, cavity=0.2)


# ---------------------------------------------------------------------------
# f_metal = METAL, 1 m per repeat
# ---------------------------------------------------------------------------
def hammered(rng, cells, depth):
    """Overlapping shallow hammer dents (bowls) with soft ridges where they meet."""
    f1, edge, idc, _, _ = voronoi(rng, cells, *warp_uv(rng, 0.25 * T / cells, 2.0 * T / cells, 0.3 * T / cells), 0.9)
    return depth * (f1 ** 2) * rng.uniform(0.6, 1.0, idc.max() + 1)[idc], idc


def metal_iron(rng):
    """Rusty wrought iron: hammer-forged, dark oxide scale, slag fibres along the bar (U),
    worn bright on the high spots; flaky orange and brown rust in patches, in the hollows
    and in runs, pitted underneath."""
    px = T / N
    hd, idc = hammered(rng, 34, 0.0012)
    fib = noise(rng, 3, N / 2, 0.6, aniso=40)
    slag = _s(fib, 1.8, 2.8)
    h0 = -hd + 0.00004 * fib - 0.00005 * slag + 0.0008 * nm(rng, 0.6, 0.05, 1.7)
    hn = (h0 - h0.mean()) / h0.std()
    rmask = nm(rng, 0.5, 0.008, 1.3) - 0.6 * hn + 0.5 * _s(nm(rng, 0.8, 0.02, 1.0, aniso=8, ang=math.pi / 2), 0.5, 2.0)
    rust = _s(rmask, -0.1, 0.9)
    crust = nm(rng, 0.01, px, 0.6)
    pits = _s(nm(rng, 0.006, px, 0.4), 2.2, 3.0) * _s(rmask, -0.4, 0.4)
    worn = _s(hn, 1.0, 2.2) * (1 - rust)
    h = h0 + rust * (0.00025 + 0.00012 * crust) - 0.00025 * pits
    scale = _mul(_rgb((0.215, 0.21, 0.205)), 1.0 + 0.06 * nm(rng, 0.2, 0.01, 1.2) - 0.08 * slag)
    color = _mix(scale, (0.47, 0.455, 0.44), worn)
    rc = ramp(0.5 + 0.25 * nm(rng, 0.05, 0.003, 1.0) + 0.2 * nm(rng, 0.4, 0.05, 1.5),
              [(0.0, (0.20, 0.12, 0.075)), (0.4, (0.36, 0.19, 0.10)), (0.75, (0.50, 0.27, 0.12)),
               (1.0, (0.62, 0.38, 0.17))])
    color = _mix(color, rc, rust)
    color = _mix(color, (0.10, 0.06, 0.04), pits * 0.7)
    metal = 0.85 * (1 - rust) + 0.15 * worn
    rough = _mix(0.62 - 0.25 * worn + 0.04 * fib, 0.88 + 0.04 * crust, rust)
    return dict(color=color, h=h, rough=rough, metal=metal, depth=0.0006, cavity=0.3)


def metal_bronze(rng):
    """Aged cast bronze: dark brown patina with the warm metal rubbed bright on the high
    spots, powdery blue-green verdigris crusting the hollows and spreading in blooms."""
    px = T / N
    hd, idc = hammered(rng, 22, 0.0008)
    cast = nm(rng, 0.5, 0.02, 1.6)
    pores = _s(nm(rng, 0.008, px, 0.4), 2.6, 3.2)
    h0 = -hd + 0.0006 * cast - 0.0002 * pores
    hn = (h0 - h0.mean()) / h0.std()
    vg = _s(0.7 * nm(rng, 0.4, 0.01, 1.5) - 1.0 * hn, 0.4, 1.6)
    worn = _s(hn + 0.3 * nm(rng, 0.2, 0.02, 1.2), 1.3, 2.4) * (1 - vg)
    powder = nm(rng, 0.008, px, 0.5)
    h = h0 + vg * (0.0002 + 0.0001 * powder)
    pat = _mix(_rgb((0.36, 0.25, 0.15)), (0.24, 0.17, 0.11), _s(nm(rng, 0.4, 0.01, 1.4), -1.0, 1.5))
    color = _mix(pat, (0.70, 0.50, 0.30), worn)
    vc = ramp(0.5 + 0.3 * nm(rng, 0.1, 0.004, 1.0) + 0.2 * powder,
              [(0.0, (0.20, 0.38, 0.33)), (0.5, (0.33, 0.56, 0.47)), (1.0, (0.55, 0.71, 0.60))])
    color = _mix(color, vc, vg)
    color = _mix(color, (0.12, 0.09, 0.06), pores * 0.6)
    metal = (0.55 + 0.45 * worn) * (1 - vg)
    rough = _mix(0.55 - 0.25 * worn, 0.9 + 0.03 * powder, vg)
    return dict(color=color, h=h, rough=rough, metal=metal, depth=0.0005, cavity=0.3)


def metal_gold(rng):
    """Polished treasure gold: warm and rich, softly hammered, fine scratches and a little
    darker tarnish left in the hollows."""
    px = T / N
    hd, idc = hammered(rng, 30, 0.0005)
    sw = nm(rng, 0.05, px * 2, 0.6, aniso=3, ang=rng.uniform(0, math.pi))
    scr = cracks(rng, 160, rng.uniform(0, math.pi), (0.01, 0.08), (0.5, 0.9), turn=0.01, spread=1.5,
                 value=(60, 200))
    h = -hd + 0.000002 * sw - 0.00001 * scr + 0.0002 * nm(rng, 0.5, 0.05, 1.6)
    hn = (h - h.mean()) / h.std()
    tarn = _s(-hn, 1.8, 3.0)
    color = _mul(_rgb((0.97, 0.80, 0.47)), 1.0 + 0.02 * nm(rng, 0.4, 0.02, 1.3) + 0.01 * sw)
    color = _mix(color, (0.72, 0.52, 0.27), tarn * 0.45)
    rough = 0.13 + 0.02 * sw + 0.1 * scr + 0.15 * tarn
    return dict(color=color, h=h, rough=rough, metal=1.0, depth=None, cavity=0.0)


# ---------------------------------------------------------------------------
# g_glass = CRYSTAL (alpha BLEND), 1 m per repeat
# ---------------------------------------------------------------------------
def druse(rng, cells, steep=0.6, hvar=0.3, jitter=0.9):
    """A druse of crystal points seen from above: every (periodic, jittered) site carries a
    pyramid with 5-7 flat faces; the highest pyramid wins, so neighbouring crystals
    interpenetrate along sharp creases and there are no steps. Returns height (m), face id,
    crystal id and the polygonal distance from the crystal tip (cell units)."""
    pts = 0.5 + (rng.random((cells, cells, 2)) - 0.5) * jitter
    nc = cells * cells
    a0 = rng.uniform(0, 2 * math.pi, nc)
    sides = rng.integers(5, 8, nc)
    top = rng.uniform(1 - hvar, 1.0, nc)
    gu, gv = U * cells, V * cells
    iu, iv = np.floor(gu).astype(np.int32), np.floor(gv).astype(np.int32)
    fu, fv = gu - iu, gv - iv
    best = np.full(U.shape, -1e9)
    ident = np.zeros(U.shape, np.int64)
    face = np.zeros(U.shape, np.int64)
    pdist = np.zeros(U.shape)
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cu, cv = (iu + di) % cells, (iv + dj) % cells
            k = cv * cells + cu
            dx = fu - (di + pts[cv, cu, 0])
            dy = fv - (dj + pts[cv, cu, 1])
            r = np.sqrt(dx * dx + dy * dy)
            m = sides[k]
            th = (np.arctan2(dy, dx) - a0[k]) % (2 * math.pi)
            sec = np.floor(th / (2 * math.pi / m) + 0.5)
            pd = r * np.cos(th - sec * 2 * math.pi / m)
            hk = top[k] - pd
            w = hk > best
            best = np.where(w, hk, best)
            ident = np.where(w, k, ident)
            face = np.where(w, k * 8 + (sec.astype(np.int64) % m), face)
            pdist = np.where(w, pd, pdist)
    return best * steep * T / cells, face, ident, pdist


def crystal_body(rng, light, deep, inclusion):
    """Crystal druse: large points (~20 cm) with smaller ones crowding the gaps, every face
    a different depth of colour, growth zoning parallel to the faces (phantoms), the tips
    deeper in colour, milky veils and a few bright internal fractures. Returns colour,
    height, a 0..1 depth field (high = deep colour), fracture mask, face-edge mask, veils."""
    px = T / N
    h1, f1, id1, pd1 = druse(rng, 5, 0.55)
    h2, f2, id2, pd2 = druse(rng, 13, 0.5)
    h2 = h2 - 0.06
    small = h2 > h1
    h = np.maximum(h1, h2)
    face = np.where(small, f2 + 10 ** 6, f1)
    pd = np.where(small, pd2, pd1)
    ft = rng.random(10 ** 6 + 13 * 13 * 8)
    zone = 0.5 + 0.5 * np.sin(2 * math.pi * (pd * 7 + 0.3 * nm(rng, 0.3, 0.05, 1.5)))
    tone = 0.45 * ft[face] + 0.35 * (1 - _s(pd, 0.0, 0.6)) + 0.12 * zone + 0.08 * nm(rng, 0.4, 0.02, 1.4)
    edges = np.clip(grad_px(face.astype(float)), 0, 1)
    edges = blur(edges, 0.7)
    veil = _s(warped(rng, 0.4, 0.01, 1.5, 0.05), 1.0, 2.4)
    frac = cracks(rng, 8, rng.uniform(0, math.pi), (0.04, 0.2), (0.6, 1.2), turn=0.005, spread=1.5)
    color = _mix(_rgb(light), deep, _s(tone, 0.2, 0.9))
    color = _mix(color, inclusion, veil * 0.4)
    color = _mix(color, (0.95, 0.95, 0.96), np.clip(frac * 0.55 + edges * 0.25, 0, 1))
    return color, blur(h, 0.5), tone, frac, edges, veil


def crystal_gen(light, deep, inclusion, bubbles=0.0, frost=0.0):
    def gen(rng):
        px = T / N
        color, h, tone, frac, edges, veil = crystal_body(rng, light, deep, inclusion)
        rough = 0.05 + 0.03 * veil + 0.02 * frac + 0.04 * edges
        if bubbles:
            bub = np.zeros((N, N))
            for _ in range(int(bubbles)):
                cx, cy = rng.random() * N, rng.random() * N
                r = rng.uniform(0.0008, 0.004) / px
                idx, dx, dy = window(cx, cy, r + 2)
                dd = np.sqrt(dx * dx + dy * dy)
                stamp_max(bub, idx, _s(r - dd, -0.6, 0.6) * (0.5 + 0.5 * _s(dd, 0.3 * r, r)))
            color = _mix(color, (0.96, 0.97, 0.98), bub * 0.7)
        if frost:
            fr = _s(nm(rng, 0.4, 0.02, 1.4), 0.6, 1.6)
            color = _mix(color, (0.90, 0.94, 0.96), fr * 0.4)
            rough = rough + frost * fr
            h = h + 0.00003 * fr * nm(rng, 0.004, px, 0.5)
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)
    return gen


# ---------------------------------------------------------------------------
# h_glow = GLOW (emissive), 1 m per repeat
# ---------------------------------------------------------------------------
def glow_glowworm(rng):
    """Glowworm colony on a dark wet ceiling: blue-cyan points of light (2-7 mm) with soft
    halos, gathered in drifting colonies, a few faint beaded silk threads."""
    px = T / N
    h, _ = stone_base(rng)
    color = _mul(_rgb((0.075, 0.074, 0.078)), 1.0 + 0.15 * nm(rng, 0.4, 0.01, 1.3))
    colony = _s(nm(rng, 0.45, 0.05, 1.5), -0.6, 1.0)
    core = np.zeros((N, N))
    halo = np.zeros((N, N))
    thread = Canvas(3)
    for _ in range(1100):
        for _ in range(30):
            cx, cy = rng.random() * N, rng.random() * N
            if rng.random() < colony[int(cy) % N, int(cx) % N]:
                break
        r = rng.uniform(0.0012, 0.0035) / px
        b = rng.uniform(0.45, 1.0)
        idx, dx, dy = window(cx, cy, r * 7)
        dd = np.sqrt(dx * dx + dy * dy)
        stamp_max(core, idx, b * _s(r - dd, -0.7, 0.7))
        stamp_max(halo, idx, b * np.exp(-(dd / (r * 3.5)) ** 2))
        if rng.random() < 0.08:
            ln = rng.uniform(0.01, 0.04) / px
            thread.line([(cx, cy), (cx + rng.normal(0, 1), cy + ln)], 0.6, value=int(rng.uniform(60, 140)))
    th = thread.get()
    em = (np.clip(core, 0, 1)[..., None] * np.array([0.55, 0.95, 1.0])
          + np.clip(halo, 0, 1)[..., None] * np.array([0.03, 0.30, 0.52]) * 0.55
          + th[..., None] * np.array([0.05, 0.22, 0.30]))
    color = _mix(color, (0.55, 0.80, 0.85), np.clip(core, 0, 1) * 0.8)
    rough = 0.3 + 0.1 * nm(rng, 0.2, 0.01, 1.2)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.004, cavity=0.3, emissive=np.clip(em, 0, 1))


def glow_crystal(rng):
    """Violet crystal lit from within: faceted body, the light strongest in the deep
    cores of the facets and along internal fractures."""
    color, h, tone, frac, edges, veil = crystal_body(rng, (0.70, 0.52, 0.86), (0.36, 0.14, 0.55), (0.85, 0.78, 0.92))
    core = _s(tone, 0.2, 1.0)
    pulse = _s(nm(rng, 0.5, 0.04, 1.5), -1.2, 1.4)
    g = np.clip(0.25 + 0.55 * core * (0.5 + 0.5 * pulse) + 0.6 * frac + 0.15 * veil - 0.15 * edges, 0, 1.2)
    em = ramp(g / 1.2, [(0.0, (0.10, 0.03, 0.22)), (0.45, (0.42, 0.16, 0.82)), (0.8, (0.70, 0.42, 1.0)),
                        (1.0, (0.92, 0.80, 1.0))])
    return dict(color=color, h=h, rough=0.06 + 0.03 * veil, metal=0.0, depth=None, cavity=0.0, emissive=em)


# ---------------------------------------------------------------------------
# water, 4 m per repeat
# ---------------------------------------------------------------------------
def water_glow(rng):
    """Bioluminescent cave water: deep blue, drifting threads and specks of cold light."""
    out = water_gen((0.05, 0.20, 0.32), (0.03, 0.12, 0.24), 0.6, 0.0)(rng)
    px = T / N
    c1 = warped(rng, 1.2, 0.05, 1.6, 0.1)
    c2 = warped(rng, 0.8, 0.05, 1.6, 0.1)
    trails = np.maximum(vein(contour_dist(c1), 1.4, 0.8), 0.7 * vein(contour_dist(c2), 1.1, 0.8))
    trails = trails * _s(nm(rng, 1.5, 0.2, 1.6), -0.4, 1.0)
    specks = _s(nm(rng, 0.03, px, 0.3), 2.6, 3.3) * _s(nm(rng, 1.0, 0.15, 1.5), -0.5, 1.0)
    bloom = blur(trails + specks, 2.5)
    g = np.clip(0.05 + 0.6 * trails + 0.9 * specks + 0.3 * bloom, 0, 1)
    out["emissive"] = ramp(g, [(0.0, (0.0, 0.03, 0.08)), (0.4, (0.02, 0.32, 0.65)), (0.8, (0.20, 0.70, 1.0)),
                               (1.0, (0.70, 0.95, 1.0))])
    out["color"] = _mix(out["color"], (0.20, 0.60, 0.85), g * 0.4)
    return out


# --- villa generators reused as they are -------------------------------------
def glow_white(rng):
    px = T / N
    f = nm(rng, 0.01, px * 2, 0.4)
    color = _mul(_rgb((0.97, 0.97, 0.97)), 1.0 + 0.003 * f)
    return dict(color=color, h=0.000003 * f, rough=0.30 + 0.02 * f, metal=0.0, depth=None, cavity=0.0,
                emissive=_rgb((1.0, 1.0, 1.0)))


def glow_ember(rng):
    """Ember bed for the fireplaces: lumpy ceramic coals, pale ash on the cooler crowns,
    glowing seams between the coals and fine glowing cracks across them; heat varies across
    the bed in small zones so no hot patch marks the repeat."""
    px = T / N
    wu = (U + 0.004 * noise(rng, 3, 40, 1.2)) % 1.0
    wv = (V + 0.004 * noise(rng, 3, 40, 1.2)) % 1.0
    cells = 16
    f1, edge, idc, _, _ = voronoi(rng, cells, wu, wv, 0.9)
    nc = cells * cells
    hc = rng.uniform(0.55, 1.0, nc)
    dome = np.clip(1 - np.clip(f1 / 0.75, 0, 1) ** 2, 0, 1) ** 0.6 * hc[idc]
    dome = dome * (1 + 0.15 * nm(rng, 0.03, 0.008, 1.0))
    sw = 0.055 * (0.6 + 0.8 * _s(nm(rng, 0.15, 0.02, 1.3), -1.5, 1.5))
    seam = np.exp(-(edge / sw) ** 2)
    cv = Canvas(3)
    for _ in range(220):
        x, y = rng.random() * N, rng.random() * N
        pts = vein_path(rng, x, y, rng.uniform(0, 2 * math.pi), rng.uniform(0.02, 0.06) / px, 2.5, 0.12, pull=0.0)
        cv.stroke(pts, widths(rng, len(pts), rng.uniform(0.9, 1.8), 0.6, taper=0.3), value=int(rng.uniform(140, 255)))
    cracks = cv.get() * _s(dome, 0.05, 0.3)
    heat_s = _s(nm(rng, 0.22, 0.04, 1.4), -1.3, 1.3)                    # smooth: same on both sides of a seam
    heat_c = np.clip(0.55 * rng.random(nc)[idc] + 0.55 * heat_s, 0, 1)  # per coal: cracks and crowns
    under = 1 - _s(dome, 0.05, 0.45)
    glow = np.clip(seam * (0.3 + 0.85 * heat_s) + cracks * heat_c * 0.9 + under * heat_s * 0.2, 0, 1.2)
    ash = _s(dome + 0.15 * nm(rng, 0.06, 0.012, 1.1) - 0.45 * heat_c, 0.5, 0.82)
    color = _mix(_rgb((0.060, 0.055, 0.050)), (0.13, 0.12, 0.112), _s(nm(rng, 0.08, 0.01, 1.0), -1, 1.5) * 0.6)
    color = _mix(color, (0.60, 0.58, 0.55), ash * 0.75)
    color = _mix(color, (0.50, 0.20, 0.06), np.clip(glow, 0, 1) * 0.6)
    t_ = glow * (0.75 + 0.45 * heat_s)
    em = _mix(_rgb((0.0, 0.0, 0.0)), (0.50, 0.07, 0.01), _s(t_, 0.02, 0.35))
    em = _mix(em, (1.0, 0.38, 0.06), _s(t_, 0.3, 0.75))
    em = _mix(em, (1.0, 0.76, 0.40), _s(t_, 0.8, 1.2))
    rough = 0.85 - 0.12 * np.clip(glow, 0, 1)
    h = 0.02 * dome - 0.006 * seam - 0.0008 * cracks
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.006, cavity=0.2, emissive=np.clip(em, 0, 1))


def water_gen(shallow, deep, ripple, caustic):
    def gen(rng):
        wind = rng.uniform(0, math.pi)
        h = ripple * (0.0025 * nm(rng, 0.9, 0.12, 1.8, aniso=2.2, ang=wind)
                      + 0.0010 * nm(rng, 0.3, 0.05, 1.5, aniso=1.6, ang=wind + 0.5)
                      + 0.00025 * nm(rng, 0.08, 0.015, 1.2))
        c1 = warped(rng, 0.6, 0.08, 1.6, 0.08)
        c2 = warped(rng, 0.5, 0.08, 1.6, 0.08)
        net = blur(np.maximum(vein(contour_dist(c1), 2.5, 0.8), vein(contour_dist(c2), 2.5, 0.8)), 1.5)
        depthv = _s(nm(rng, 2.5, 0.5, 1.8), -1.5, 1.5)
        color = _mix(_rgb(shallow), deep, depthv * 0.5)
        color = _mul(color, 1.0 + caustic * (net - 0.2))
        rough = 0.025 + 0.01 * _s(nm(rng, 1.0, 0.2, 1.5), 0.5, 2.0)
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)
    return gen


# ---------------------------------------------------------------------------
# The catalogue. Order inside each slot = menu order. res: texture size.
# ---------------------------------------------------------------------------
LIB = {
    "a_plaster": [
        dict(id="limestone", label="Limestone", gen=rock_limestone),
        dict(id="basalt", label="Basalt", gen=rock_basalt),
        dict(id="sandstone", label="Red sandstone", gen=rock_sandstone),
        dict(id="slate", label="Slate", gen=rock_slate),
    ],
    "b_floor": [
        dict(id="earth", label="Packed earth", gen=ground_earth),
        dict(id="sand", label="Cave sand", gen=ground_sand),
        dict(id="gravel", label="Scree gravel", gen=ground_gravel),
        dict(id="mud", label="Wet mud", gen=ground_mud),
    ],
    "c_wood": [
        dict(id="driftwood", label="Driftwood", gen=wood_driftwood),
        dict(id="timber", label="Old timber", gen=wood_timber),
        dict(id="charred", label="Charred wood", gen=wood_charred),
        dict(id="bark", label="Log bark", gen=wood_bark),
    ],
    "d_stone": [
        dict(id="moss", label="Mossy stone", gen=stone_moss),
        dict(id="wet", label="Wet stone", gen=stone_wet),
        dict(id="lichen", label="Lichen stone", gen=stone_lichen),
        dict(id="flowstone", label="Flowstone", gen=stone_flowstone),
    ],
    "e_fabric": [
        dict(id="fur_grey", label="Wolf fur", gen=fabric_fur_grey),
        dict(id="fur_brown", label="Bear fur", gen=fabric_fur_brown),
        dict(id="leather", label="Leather hide", gen=fabric_leather),
        dict(id="wool", label="Rough wool (tint)", gen=fabric_wool),
    ],
    "f_metal": [
        dict(id="iron", label="Rusty iron", gen=metal_iron),
        dict(id="bronze", label="Aged bronze", gen=metal_bronze),
        dict(id="gold", label="Polished gold", gen=metal_gold),
    ],
    "g_glass": [
        dict(id="amethyst", label="Amethyst", alpha=0.68, res=512,
             gen=crystal_gen((0.74, 0.58, 0.88), (0.40, 0.17, 0.60), (0.88, 0.82, 0.93))),
        dict(id="quartz", label="Quartz", alpha=0.55, res=512,
             gen=crystal_gen((0.93, 0.94, 0.95), (0.80, 0.81, 0.82), (0.97, 0.97, 0.97))),
        dict(id="emerald", label="Emerald", alpha=0.72, res=512,
             gen=crystal_gen((0.30, 0.74, 0.52), (0.04, 0.42, 0.24), (0.20, 0.40, 0.25))),
        dict(id="ice", label="Ice", alpha=0.60, res=512,
             gen=crystal_gen((0.86, 0.94, 0.98), (0.62, 0.80, 0.90), (0.95, 0.97, 0.99), bubbles=500, frost=0.3)),
    ],
    "h_glow": [
        dict(id="embers", label="Embers", gen=glow_ember, res=512),
        dict(id="glowworm", label="Glowworms", gen=glow_glowworm, res=512),
        dict(id="crystal", label="Violet crystal glow", gen=glow_crystal, res=512),
        dict(id="white", label="White light (tint)", gen=glow_white, res=512),
    ],
    "water": [
        dict(id="teal", label="Teal cave lake", gen=water_gen((0.16, 0.47, 0.47), (0.07, 0.31, 0.34), 0.6, 0.05),
             alpha=0.62, double=True, res=512),
        dict(id="dark", label="Black still water", gen=water_gen((0.030, 0.038, 0.042), (0.020, 0.026, 0.030), 0.3, 0.0),
             alpha=0.75, double=True, res=512),
        dict(id="glow", label="Glowing blue water", gen=water_glow, alpha=0.70, double=True, res=512),
    ],
}
DEFAULT = {"a_plaster": "limestone", "b_floor": "earth", "c_wood": "timber", "d_stone": "wet",
           "e_fabric": "fur_brown", "f_metal": "iron", "g_glass": "amethyst", "h_glow": "embers", "water": "teal"}


def entries():
    for slot in SLOTS:
        for v in LIB[slot]:
            yield slot, v


def mat_name(slot, vid):
    return f"{PREFIX}{slot}_{vid}"


# ---------------------------------------------------------------------------
# Derived maps, PNG, glb
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
    cavity = 0.5 * (blur(h, 3) + blur(h, 12)) - h
    return 1.0 - 0.6 * np.clip(cavity / depth, 0.0, 1.0)


def _u8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def png_bytes(img):
    buf = io.BytesIO()
    Image.fromarray(img).save(buf, "PNG", optimize=True)
    return buf.getvalue()


def seam(img):
    """Edge-to-edge jump relative to the jump between neighbouring pixels at that edge
    (~1 = seamless; a real seam gives several times more)."""
    a = img.astype(float)
    sh = np.abs(a[:, 0] - a[:, -1]).mean()
    sv = np.abs(a[0] - a[-1]).mean()
    dh = 0.5 * (np.abs(a[:, 1] - a[:, 0]).mean() + np.abs(a[:, -1] - a[:, -2]).mean())
    dv = 0.5 * (np.abs(a[1] - a[0]).mean() + np.abs(a[-1] - a[-2]).mean())
    if max(sh, sv) < 0.5:          # flat image (e.g. clear glass normal): nothing to compare
        return 0.0
    return max(sh / max(dh, 0.25), sv / max(dv, 0.25))


def write_glb(path, name, pngs, size, alpha=None, emissive=False, double=False):
    """One metallicRoughness material named `name` and a quad (size metres = one repeat)."""
    s = size / 2.0
    pos = np.array([[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]], np.float32)
    nor = np.tile(np.array([0, 0, 1], np.float32), (4, 1))
    uv = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], np.float32)
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
    kinds = ["basecolor", "normal", "orm"] + (["emissive"] if emissive else [])
    images = [{"name": f"{name}_{k}", "mimeType": "image/png", "bufferView": add(pngs[k])} for k in kinds]
    while len(blob) % 4:
        blob.append(0)
    mat = {
        "name": name,
        "pbrMetallicRoughness": {"baseColorFactor": [1.0, 1.0, 1.0, 1.0 if alpha is None else float(alpha)],
                                 "baseColorTexture": {"index": 0},
                                 "metallicFactor": 1.0, "roughnessFactor": 1.0,
                                 "metallicRoughnessTexture": {"index": 2}},
        "normalTexture": {"index": 1, "scale": 1.0},
        "occlusionTexture": {"index": 2, "strength": 1.0},
        "alphaMode": "OPAQUE" if alpha is None else "BLEND",
        "doubleSided": bool(double),
    }
    if emissive:
        mat["emissiveTexture"] = {"index": 3}
        mat["emissiveFactor"] = [1.0, 1.0, 1.0]
    doc = {
        "asset": {"version": "2.0", "generator": "The Cave - ctextures.py"},
        "scene": 0,
        "scenes": [{"name": name, "nodes": [0]}],
        "nodes": [{"name": name, "mesh": 0}],
        "meshes": [{"name": name, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                                   "indices": 3, "material": 0, "mode": 4}]}],
        "materials": [mat],
        "samplers": [{"magFilter": 9729, "minFilter": 9987, "wrapS": 10497, "wrapT": 10497}],
        "textures": [{"sampler": 0, "source": i} for i in range(len(kinds))],
        "images": images,
        "accessors": accessors,
        "bufferViews": views,
        "buffers": [{"byteLength": len(blob)}],
    }
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(blob)
    with open(path, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(blob), 0x004E4942) + bytes(blob))


def validate_glb(path, name, res, alpha=None, emissive=False):
    """Header, chunks, JSON references, embedded images, material name/alpha/emission."""
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
    if tb != 0x004E4942 or len(blob) != lb or doc["buffers"][0]["byteLength"] > lb or 28 + lj + lb != len(data):
        err.append("inconsistent BIN chunk")
    if doc["asset"]["version"] != "2.0" or len(doc.get("materials", [])) != 1:
        return err + ["bad asset/materials"]
    m = doc["materials"][0]
    if m.get("name") != name:
        err.append(f"material name {m.get('name')!r} != {name!r}")
    pbr = m["pbrMetallicRoughness"]
    refs = [pbr["baseColorTexture"]["index"], m["normalTexture"]["index"], m["occlusionTexture"]["index"],
            pbr["metallicRoughnessTexture"]["index"]]
    if emissive:
        if "emissiveTexture" not in m or len(m.get("emissiveFactor", [])) != 3:
            err.append("missing emission")
        else:
            refs.append(m["emissiveTexture"]["index"])
    elif "emissiveTexture" in m:
        err.append("unexpected emission")
    want_mode = "OPAQUE" if alpha is None else "BLEND"
    if m.get("alphaMode") != want_mode:
        err.append(f"alphaMode {m.get('alphaMode')} != {want_mode}")
    if alpha is not None and abs(pbr["baseColorFactor"][3] - alpha) > 1e-6:
        err.append("alpha factor mismatch")
    for r in refs:
        if not 0 <= r < len(doc["textures"]):
            err.append(f"texture {r} out of range")
    for tx in doc["textures"]:
        if not 0 <= tx["source"] < len(doc["images"]) or not 0 <= tx["sampler"] < len(doc["samplers"]):
            err.append("texture with image/sampler out of range")
    for bv in doc["bufferViews"]:
        if bv["byteOffset"] % 4 or bv["byteOffset"] + bv["byteLength"] > lb:
            err.append("bufferView misaligned or outside the buffer")
    for acc in doc["accessors"]:
        if not 0 <= acc["bufferView"] < len(doc["bufferViews"]):
            err.append("accessor bufferView out of range")
    for im in doc["images"]:
        bv = doc["bufferViews"][im["bufferView"]]
        png = blob[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]]
        if not png.startswith(b"\x89PNG") or Image.open(io.BytesIO(png)).size != (res, res):
            err.append(f"image {im['name']} is not a {res}x{res} PNG")
    prim = doc["meshes"][0]["primitives"][0]
    if prim["material"] != 0 or max(prim["attributes"].values()) >= len(doc["accessors"]):
        err.append("inconsistent primitive")
    if doc["nodes"][0]["name"] != name or doc["meshes"][0]["name"] != name:
        err.append("node/mesh name mismatch")
    return err


# ---------------------------------------------------------------------------
# Building one variant (runs in a worker process)
# ---------------------------------------------------------------------------
SWATCH = 240
BACKDROP = None


def _display(maps, kind, alpha, res):
    """The swatch shown to the owner: base colour softly lit by its own normal map; glass and
    water over a pale checker (their transparency), glow materials as they light up."""
    base = maps["basecolor"].astype(float) / 255.0
    n = maps["normal"].astype(float) / 127.5 - 1.0
    ao = maps["orm"][..., 0].astype(float) / 255.0
    lvec = np.array([-0.45, 0.45, 0.77])
    lvec /= np.linalg.norm(lvec)
    shade = 1.0 + 0.9 * ((n @ lvec) - lvec[2])
    if kind == "glow":
        em = maps["emissive"].astype(float) / 255.0
        img = np.clip(0.15 * base + em * 0.95, 0, 1) * shade[..., None]
    else:
        img = base * (shade * (0.85 + 0.15 * ao))[..., None]
        if alpha is not None:
            yy, xx = np.mgrid[0:res, 0:res]
            chk = (((xx * 12 // res) + (yy * 12 // res)) % 2).astype(float)
            back = _mix(np.array([0.91, 0.90, 0.88]), np.array([0.80, 0.79, 0.78]), chk)
            img = img * alpha + back * (1 - alpha)
    im = Image.fromarray(_u8(img)).resize((SWATCH, SWATCH), Image.LANCZOS)
    return np.asarray(im)


def reduce(x, f):
    """Seamless periodic reduction by an integer factor f: anti-alias blur on the torus, then
    the mean of every f x f block (nothing is read across the repeat edge)."""
    if f == 1:
        return x
    x = blur(x, 0.45 * f)
    n = x.shape[0] // f
    return x.reshape(n, f, n, f, *x.shape[2:]).mean(axis=(1, 3))


def build(job):
    slot, k = job[:2]
    write = job[2] if len(job) > 2 else True
    v = LIB[slot][k]
    vid = v["id"]
    name = mat_name(slot, vid)
    gen_res = v.get("res", 1024)
    res = min(gen_res, OUT_RES[slot])
    t0 = time.time()
    set_res(gen_res, UV_TILE[slot])
    rng = np.random.default_rng(zlib.crc32(name.encode()))
    out = v["gen"](rng)
    color = np.clip(out["color"], 0, 1)
    h = np.broadcast_to(np.asarray(out["h"], float), (N, N))
    rough = np.broadcast_to(np.asarray(out["rough"], float), (N, N))
    metal = np.broadcast_to(np.asarray(out["metal"], float), (N, N))
    ao = occlusion(h, out.get("depth"))
    cav = out.get("cavity", 0.0)
    if cav:
        color = color * (1.0 - cav * (1.0 - ao))[..., None]
    nrm = normal_from_height(h, T / N)
    f = gen_res // res
    orm = np.stack([ao, np.clip(rough, 0.02, 1.0), np.clip(metal, 0, 1)], -1)
    nrm = reduce(nrm, f)
    nrm = nrm / np.linalg.norm(nrm, axis=-1, keepdims=True)
    maps = {
        "basecolor": _u8(reduce(color, f)),
        "normal": _u8(nrm * 0.5 + 0.5),
        "orm": _u8(reduce(orm, f)),
    }
    if out.get("emissive") is not None:
        maps["emissive"] = _u8(reduce(np.clip(out["emissive"], 0, 1), f))
    stem = f"{slot}__{vid}"
    pngs = {}
    for kind, img in maps.items():
        pngs[kind] = png_bytes(img)
    sha = {kind: hashlib.sha256(p).hexdigest() for kind, p in pngs.items()}
    if not write:            # determinism re-run: only the hashes are wanted
        return dict(slot=slot, id=vid, sha=sha)
    for kind in maps:
        with open(os.path.join(TEX_DIR, f"{stem}_{kind}.png"), "wb") as f:
            f.write(pngs[kind])
    glb = os.path.join(GLB_DIR, f"{name}.glb")
    alpha = v.get("alpha")
    write_glb(glb, name, pngs, UV_TILE[slot], alpha, "emissive" in maps, v.get("double", False))
    errors = validate_glb(glb, name, res, alpha, "emissive" in maps)
    seams = {kind: round(seam(img), 2) for kind, img in maps.items()}
    kind = "glow" if "emissive" in maps else ("clear" if alpha is not None else "opaque")
    swatch = _display(maps, kind, alpha, res)
    src = maps["emissive"] if "emissive" in maps else maps["basecolor"]
    mean = [int(round(x)) for x in src.reshape(-1, 3).mean(0)]
    stats = {"rough": [round(float(np.percentile(maps["orm"][..., 1], q)) / 255, 2) for q in (5, 50, 95)]}
    return dict(slot=slot, id=vid, name=name, label=v["label"], res=res, alpha=alpha, emissive="emissive" in maps,
                seams=seams, errors=errors, swatch=swatch, mean=mean, secs=time.time() - t0,
                bytes=sum(len(p) for p in pngs.values()), glb_bytes=os.path.getsize(glb), stats=stats, sha=sha)


# ---------------------------------------------------------------------------
# Contact sheet, catalogue, checks
# ---------------------------------------------------------------------------
def _font(size, bold=False):
    for f in (("Inter-SemiBold.otf" if bold else "Inter-Regular.otf"),
              "/usr/share/fonts/opentype/inter/" + ("Inter-SemiBold.otf" if bold else "Inter-Regular.otf"),
              "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(f, size)
        except OSError:
            continue
    return ImageFont.load_default()


def swatches(path, results):
    cols, gap, pad, head, lab = 4, 14, 36, 34, 44
    rows = SLOTS
    W = pad * 2 + cols * SWATCH + (cols - 1) * gap
    H = pad + 64 + len(rows) * (head + SWATCH + lab + 10) + pad - 10
    sheet = Image.new("RGB", (W, H), (27, 25, 23))
    d = ImageDraw.Draw(sheet)
    d.text((pad, pad - 6), "THE CAVE  -  PBR material library", fill=(236, 226, 208), font=_font(26, True))
    d.text((pad, pad + 28), "Swatch = one full repeat, softly lit. Crystal and water shown over a checker at their alpha.",
           fill=(150, 142, 130), font=_font(14))
    y = pad + 64
    by_slot = {}
    for r in results:
        by_slot.setdefault(r["slot"], []).append(r)
    for slot in rows:
        d.text((pad, y + 6), SLOT_TITLE[slot], fill=(214, 180, 120), font=_font(17, True))
        d.text((pad + 200, y + 9), f"{slot}  -  {UV_TILE[slot]:g} m per repeat", fill=(140, 132, 120),
               font=_font(13))
        y += head
        for k, r in enumerate(by_slot.get(slot, [])):
            x = pad + k * (SWATCH + gap)
            sheet.paste(Image.fromarray(r["swatch"]), (x, y))
            d.text((x, y + SWATCH + 6), r["label"], fill=(236, 228, 214), font=_font(15, True))
            d.text((x, y + SWATCH + 25), r["name"], fill=(130, 124, 114), font=_font(12))
        y += SWATCH + lab + 10
    sheet.save(path, optimize=True)


def write_catalogue(results):
    cat = {"slots": {}, "default": dict(DEFAULT)}
    for slot in SLOTS:
        cat["slots"][slot] = []
        for r in (r for r in results if r["slot"] == slot):
            cat["slots"][slot].append({
                "id": r["id"], "name": r["name"], "label": r["label"], "tile_m": UV_TILE[slot],
                "alpha": "BLEND" if r["alpha"] is not None else "OPAQUE",
                "emissive": r["emissive"], "swatch_rgb": r["mean"]})
    with open(CATALOGUE, "w") as f:
        json.dump(cat, f, indent=1)
        f.write("\n")
    return cat


def check_catalogue(cat):
    """materials.json lists exactly the files that exist (and nothing stale is left)."""
    err = []
    want_glb, want_png = set(), set()
    for slot, vs in cat["slots"].items():
        ids = [v["id"] for v in vs]
        if len(set(ids)) != len(ids):
            err.append(f"duplicate ids in {slot}")
        if cat["default"].get(slot) not in ids:
            err.append(f"default for {slot} is not a variant")
        for v in vs:
            if v["name"] != mat_name(slot, v["id"]) or not v["id"].isascii() or v["id"] != v["id"].lower():
                err.append(f"bad name/id {v['name']}")
            if len(v["label"]) > 20:
                err.append(f"label too long: {v['label']}")
            want_glb.add(v["name"] + ".glb")
            for k in ["basecolor", "normal", "orm"] + (["emissive"] if v["emissive"] else []):
                want_png.add(f"{slot}__{v['id']}_{k}.png")
    have_glb = {f for f in os.listdir(GLB_DIR) if f.startswith(PREFIX) and f.endswith(".glb")}
    have_png = {f for f in os.listdir(TEX_DIR) if "__" in f and f.endswith(".png")}
    if want_glb != have_glb:
        err.append(f"glb mismatch: missing {sorted(want_glb - have_glb)} extra {sorted(have_glb - want_glb)}")
    if want_png != have_png:
        err.append(f"png mismatch: missing {sorted(want_png - have_png)} extra {sorted(have_png - want_png)}")
    return err


def main():
    t0 = time.time()
    args = sys.argv[1:]
    jobs = os.cpu_count() or 2
    if "--jobs" in args:
        i = args.index("--jobs")
        jobs = int(args[i + 1])
        del args[i:i + 2]
    filters = [a for a in args if not a.startswith("-")]
    os.makedirs(TEX_DIR, exist_ok=True)
    os.makedirs(GLB_DIR, exist_ok=True)
    os.makedirs(os.path.dirname(CATALOGUE), exist_ok=True)
    todo = [(s, v) for s, v in entries() if not filters or any(f in f"{s}__{v['id']}" for f in filters)]
    if not todo:
        sys.exit(f"no variant matches {filters}; stems look like 'a_plaster__limestone'")
    if not filters:      # full run: clear stale outputs of this script first
        for f in os.listdir(GLB_DIR):
            if f.startswith(PREFIX) and f.endswith(".glb"):
                os.remove(os.path.join(GLB_DIR, f))
        for f in os.listdir(TEX_DIR):
            if "__" in f and f.endswith(".png"):
                os.remove(os.path.join(TEX_DIR, f))
    # biggest jobs first so the pool finishes together
    order = sorted(todo, key=lambda j: -(j[1].get("res", 1024)))
    order = [(s, LIB[s].index(v)) for s, v in order]
    # determinism: two variants are built a second time (without writing) and must hash the same
    again = [(s, k, False) for s, k in order if (s, LIB[s][k]["id"]) in DETERMINISM_CHECK]
    with Pool(min(jobs, len(order))) as pool:
        done = pool.map(build, order + again, chunksize=1)
    reruns = [r for r in done[len(order):]]
    done = done[:len(order)]
    index = {(s, v["id"]): k for k, (s, v) in enumerate(todo)}
    results = sorted(done, key=lambda r: index[(r["slot"], r["id"])])
    failures = []
    for r in results:
        worst = max(r["seams"].values())
        ok = not r["errors"] and worst <= 1.5
        if not ok:
            failures.append((r["name"], r["errors"], r["seams"]))
        print(f"  {r['name']:30s} {r['res']:5d}px {r['secs']:5.1f}s  seam {worst:4.2f}  "
              f"rough {r['stats']['rough']}  png {r['bytes'] / 1e6:4.1f} MB  {'OK' if ok else 'FAIL'}")
    first = {(r["slot"], r["id"]): r["sha"] for r in results}
    for r in reruns:
        if r["sha"] != first[(r["slot"], r["id"])]:
            failures.append((mat_name(r["slot"], r["id"]), ["not deterministic: a second build differs"], {}))
    if reruns:
        print(f"  determinism: {', '.join(mat_name(r['slot'], r['id']) for r in reruns)} rebuilt, "
              f"{'identical' if not any('deterministic' in str(f) for f in failures) else 'DIFFERENT'}")
    if not filters:
        swatches(os.path.join(TEX_DIR, "_swatches.png"), results)
        cat = write_catalogue(results)
        cerr = check_catalogue(cat)
        if cerr:
            failures.append(("catalogue", cerr, {}))
    tex_mb = sum(os.path.getsize(os.path.join(TEX_DIR, f)) for f in os.listdir(TEX_DIR)) / 1e6
    glb_mb = sum(os.path.getsize(os.path.join(GLB_DIR, f)) for f in os.listdir(GLB_DIR)) / 1e6
    print(f"{len(results)} variants. textures {tex_mb:.1f} MB in {TEX_DIR}\n"
          f"glTF materials {glb_mb:.1f} MB in {GLB_DIR}\noutput total {tex_mb + glb_mb:.1f} MB "
          f"(budget {BUDGET_MB:g} MB)\ncatalogue {CATALOGUE}\nTotal {time.time() - t0:.1f} s")
    if not filters and tex_mb + glb_mb > BUDGET_MB:
        failures.append(("size", [f"output {tex_mb + glb_mb:.1f} MB > {BUDGET_MB:g} MB"], {}))
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  ", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

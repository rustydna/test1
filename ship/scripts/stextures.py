"""Procedural PBR material library for The Second Bride (seamless, physically scaled).

The Second Bride is an 18th-century pirate frigate, the flagship of the Lord of the Pit: dark,
majestic, weathered but rich. Tarred black hull, ochre gun strake, red gun-port lids, gilded
carvings, holystoned pine decks, canvas sails. The script makes every material variant the
owner can pick from the ship's menus, using only numpy and pillow:

  output/textures/<slot>__<variant>_basecolor.png   sRGB (RGBA for leaded glass: opaque lead)
  output/textures/<slot>__<variant>_normal.png      glTF tangent space (OpenGL, +Y up)
  output/textures/<slot>__<variant>_orm.png         R occlusion, G roughness, B metallic
  output/textures/<slot>__<variant>_emissive.png    sRGB, glowing materials only
  output/textures/_swatches.png                     contact sheet (every variant, labelled)
  output/pbr_materials/bride_<slot>_<variant>.glb   one glTF 2.0 material (plus a quad that
                                                    uses it) for the Second Life bulk uploader
  docs/materials.json                               the catalogue read by the build, the
                                                    renderer and the LSL menus

The slot names are the villa pipeline's; on the ship they mean:
  a_plaster HULL PAINT   b_floor DECK     c_wood WOOD (masts, rails, yards, carriages, furniture)
  d_stone   TRIM (gun strake, carvings)   e_fabric CANVAS     f_metal METAL
  g_glass   GLASS (stern gallery, lanterns)   h_glow GLOW     water

Seamless by construction: all noise lives on a torus (white noise filtered with an FFT),
Voronoi wraps its neighbours, strakes/planks/threads/quarries divide the repeat exactly and
everything drawn is drawn with its copies one repeat away. Edges are checked numerically.

Physical scale: one repeat covers UV_TILE[slot] metres. UVs are world-space box-mapped, on
vertical faces v = height (image rows run downwards = world down), so planking runs along U
and salt, rust and drips run down the image (+V). Planking is world-aligned: hull and trim
strakes are exactly 0.25 m with seams at 0.125 + 0.25 k m, and frames/beams sit at
0.25 + 0.5 k m, so the ochre strake's seams and treenails line up with the black hull's.
Heights are in metres and the normal maps use the real pixel size. Wood grain runs along U,
except the pine spar, whose grain runs up the mast (along V).

The toolkit (periodic noise, Voronoi, Canvas, normals, glb writer, seam check, catalogue,
swatches) is copied from cave/scripts/ctextures.py (itself from the villa's vtextures.py and
the_pit's pbr_textures.py); the driftwood, rough wool and white-light generators are the cave's,
the boards and plank layout the villa's.

Usage:  python3 ship/scripts/stextures.py [filter ...] [--jobs N]
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
PREFIX = "bride_"
BUDGET_MB = 70.0          # textures + glb together
DETERMINISM_CHECK = {("a_plaster", "tar"), ("g_glass", "leaded")}
# Texture size written per slot. Every material is generated at its design resolution
# (LIB "res", 1024 unless noted) and reduced to this by a seamless periodic filter.
OUT_RES = {"a_plaster": 512, "b_floor": 512, "c_wood": 512, "d_stone": 512, "e_fabric": 512,
           "f_metal": 512, "g_glass": 512, "h_glow": 512, "water": 512}

SHIP_TILE = {"a_plaster": 2.0, "b_floor": 2.0, "c_wood": 1.2, "d_stone": 1.0, "e_fabric": 1.0,
             "f_metal": 0.5, "g_glass": 0.6, "h_glow": 1.0, "water": 4.0}


def _uv_tile():
    """The UV_TILE.update({...}) table of ship.py when the build exists (parsed, not
    imported: it would import bpy), falling back to the same values written here."""
    tiles = dict(SHIP_TILE)
    try:
        tree = ast.parse(open(os.path.join(HERE, "ship.py")).read())
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
SLOT_TITLE = {"a_plaster": "HULL PAINT", "b_floor": "DECK", "c_wood": "WOOD", "d_stone": "TRIM",
              "e_fabric": "CANVAS", "f_metal": "METAL", "g_glass": "GLASS", "h_glow": "GLOW",
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
def wood_figure(rng, Y, bw, ident, nid, sp, xl=None, seg_len=None, flat_share=0.6, loop=None):
    """Plain (flat) and rift sawn figure. Y: metres across the board (0..bw), xl: metres along
    a plank segment (floor planks; None = continuous boards, periodic along U). The pith lies
    outside the board, so flat-sawn boards show nested cathedral arches, rift boards near
    straight lines. loop: planks that run the whole repeat (periodic figure there).
    Returns ring fraction, late-wood profile, ring index, d, table."""
    tab = rng.random((nid, 12))
    flat = tab[:, 0] < flat_share
    dmin = np.where(flat, 0.004 + 0.02 * tab[:, 1], 0.05 + 0.2 * tab[:, 1])
    k = np.where(tab[:, 2] < 0.65, 1, 2)
    amp = 0.02 + 0.06 * tab[:, 3]
    d_loop = dmin[ident] + amp[ident] * 0.5 * (1 - np.cos(2 * math.pi * (k[ident] * U + tab[ident, 4])))
    if xl is None:
        d = d_loop
    else:
        xa = seg_len * (0.2 + 0.6 * tab[ident, 4])
        d = dmin[ident] + (0.04 + 0.25 * tab[ident, 3]) * (xl - xa) ** 2
        if loop is not None:
            d = np.where(loop, d_loop, d)
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


def wood_surface(rng, sp, Y, bw, ident, nid, xl=None, seg_len=None, knots=0, plank_mask=None, loop=None):
    """Colour, height, roughness of a wood species on boards (ident) with local Y."""
    fr, late, ring, d, tab = wood_figure(rng, Y, bw, ident, nid, sp["sp"], xl, seg_len, loop=loop)
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


def smear_down(src, length_px, step=2):
    """Runs: src carried down the image (+V, world down) fading exponentially over length_px."""
    out = src.copy()
    acc = src.copy()
    decay = math.exp(-step / length_px)
    for _ in range(int(3 * length_px / step)):
        acc = np.roll(acc, step, axis=0) * decay
        np.maximum(out, acc, out=out)
    return out


def _norm(x):
    return (x - x.mean()) / (x.std() + 1e-12)


# ---------------------------------------------------------------------------
# Ship toolkit: planking on frames and beams, pegs, plain weave
# ---------------------------------------------------------------------------
def planks(rng, width, spacing, butt_p=0.45, wob=0.0003):
    """Planking along U, planks exactly `width` m wide with their seams on V = (k + 1/2) * width / T
    (slots planked at the same width line up in world space: the 0.25 m strakes of hull and
    trim, seams at 0.125 + 0.25 k m), frames or beams every `spacing` m on
    U = (j + 0.5) * spacing / T (world-aligned too). A share butt_p of the planks butts on a
    frame line, never on the line of the plank beside it; the others run the whole repeat. Returns a dict: Y (m below the plank's upper
    seam), pw (m), row, n, vloc, dside (m to the long seams), dbutt (m to the butt, 9 when
    none), xl, sl (m along the plank from its butt, length), loop (planks without a butt),
    fu (frame lines, repeats), butts {row: frame}."""
    n = int(round(T / width))
    cols = int(round(T / spacing))
    vv = (V + 0.5 / n + wob * noise(rng, 2, 16, 1.4, aniso=4)) % 1.0     # seams off the image edge
    row = np.floor(vv * n).astype(np.int32) % n
    vloc = vv * n - np.floor(vv * n)
    fu = (np.arange(cols) + 0.5) / cols
    dbutt = np.full((N, N), 9.0)
    xl = U * T
    sl = np.full((N, N), T)
    loop = np.ones((N, N), bool)
    butts = {}
    far = 2 if cols >= 4 else 1
    for r in range(n):
        if rng.random() >= butt_p:
            continue
        near = [butts.get(r - 1), butts.get((r + 1) % n)]
        ok = [j for j in range(cols)
              if all(b is None or min((j - b) % cols, (b - j) % cols) >= far for b in near)]
        if not ok:
            continue
        j = int(rng.choice(ok))
        c = (fu[j] + rng.normal(0, 0.002)) % 1.0
        m = row == r
        xs = U[m]
        dbutt[m] = np.abs(_wrap(xs - c)) * T
        xl[m] = ((xs - c) % 1.0) * T
        loop[m] = False
        butts[r] = j
    return dict(Y=vloc * T / n, pw=T / n, row=row, n=n, vloc=vloc, dside=np.minimum(vloc, 1 - vloc) * T / n,
                dbutt=dbutt, xl=xl, sl=sl, loop=loop, fu=fu, butts=butts)


def pegs(rng, L, radius, ys=(0.3, 0.7), off=0.05, jit=0.003):
    """Treenails or deck bungs: two per plank on every frame/beam line, a pair each side of a
    butt. Returns the disc mask, a thin ring at the rim and a tone (-1..1) per peg."""
    px = T / N
    disc, ring, tone = np.zeros((N, N)), np.zeros((N, N)), np.zeros((N, N))
    n = L["n"]
    for r in range(n):
        for j, f in enumerate(L["fu"]):
            us = [f - off / T, f + off / T] if L["butts"].get(r) == j else [f]
            for u0 in us:
                for yf in ys:
                    cx = (u0 + rng.normal(0, jit / T)) * N
                    cy = (r - 0.5 + yf + rng.normal(0, 0.03)) / n * N
                    rad = radius * rng.uniform(0.9, 1.1) / px
                    idx, dx, dy = window(cx, cy, rad + 4)
                    dd = np.sqrt(dx * dx + dy * dy)
                    m = _s(rad - dd, -0.6, 0.6)
                    stamp_max(disc, idx, m)
                    stamp_max(ring, idx, np.exp(-((dd - rad) / 0.8) ** 2))
                    tone[idx] = np.where(m > 0.5, rng.uniform(-1, 1), tone[idx])
    return disc, ring, tone


def weave(rng, threads, jit=0.0012, slub=0.3, thin=0.12, wmin=0.75):
    """Plain weave, `threads` threads per repeat both ways (the cave's wool weave): heights of
    the thread crowns (0..1), which thread is on top, per-thread tone, slub and coordinates."""
    gx = (U + jit * noise(rng, 2, 40, 1.2)) * threads
    gy = (V + jit * noise(rng, 2, 40, 1.2)) * threads
    slub_u = 1.0 + slub * _s(noise(rng, 16, N / 2, 0.5, aniso=10, ang=math.pi / 2), 0.4, 2.4) \
        - thin * _s(-noise(rng, 16, N / 2, 0.5, aniso=10, ang=math.pi / 2), 0.8, 2.4)
    slub_v = 1.0 + slub * _s(noise(rng, 16, N / 2, 0.5, aniso=10), 0.4, 2.4) \
        - thin * _s(-noise(rng, 16, N / 2, 0.5, aniso=10), 0.8, 2.4)
    si, sj = rng.random(threads), rng.random(threads)
    i = np.floor(gx).astype(np.int64)
    j = np.floor(gy).astype(np.int64)
    fx, fy = gx - i, gy - j
    over = ((i + j) % 2) == 0
    wu_ = np.clip((wmin + (1 - wmin) * si[i % threads]) * slub_u, 0.5, 1.0)
    wv_ = np.clip((wmin + (1 - wmin) * sj[j % threads]) * slub_v, 0.5, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / wu_) ** 2, 0.0, 1.0))
    cvv = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / wv_) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    h_warp = cu * (0.55 + 0.45 * np.where(over, ou, -ou)) * slub_u
    h_weft = cvv * (0.55 + 0.45 * np.where(over, -ov, ov)) * slub_v
    top = h_warp > h_weft
    return dict(hh=np.maximum(h_warp, h_weft), top=top, tone=np.where(top, si[i % threads], sj[j % threads]) - 0.5,
                slub=np.where(top, slub_u, slub_v) - 1.0, gx=gx, gy=gy, fx=fx, fy=fy, cu=cu, cv=cvv)


def spots(rng, count, r_m, soft=0.6):
    """count soft round spots of radius r_m (m, a pair = range) anywhere: mask 0..1."""
    px = T / N
    out = np.zeros((N, N))
    for _ in range(count):
        cx, cy = rng.random() * N, rng.random() * N
        r = (rng.uniform(*r_m) if isinstance(r_m, tuple) else r_m) / px
        idx, dx, dy = window(cx, cy, r * 2 + 3)
        dd = np.sqrt((dx * rng.uniform(0.7, 1.3)) ** 2 + dy * dy)
        stamp_max(out, idx, _s(r - dd, -r * soft, r * soft))
    return out


# ---------------------------------------------------------------------------
# a_plaster = HULL PAINT, 2 m per repeat (also the painted trim of d_stone, 1 m)
# ---------------------------------------------------------------------------
def painted_planks(paint, rough0=0.5, wear=0.15, salt=0.4, under=(0.24, 0.17, 0.11), chalk=0.0,
                   crackle=0, rust=4, butt_p=0.45):
    """Carvel planking under paint: 0.25 m strakes caulked and paid with pitch, butts on the
    frames (0.5 m apart), treenails in pairs on every frame, strakes not quite flush and a
    little cupped; the paint brushed along the planks with the grain telegraphing through,
    chipped on the seams' arrises, white salt crusting the seams and streaking down from
    them, a few iron spikes weeping rust."""
    def gen(rng):
        px = T / N
        L = planks(rng, 0.25, 0.5, butt_p=butt_p)
        n, row, vloc = L["n"], L["row"], L["vloc"]
        dm = np.minimum(L["dside"], L["dbutt"])
        hj, face = joint_profile(dm, 0.0025, 0.007, 0.0025)
        tab = rng.random((n, 4))
        cup = (tab[row, 0] - 0.5) * 0.0012 * (1 - (2 * vloc - 1) ** 2)
        lift = (tab[row, 1] - 0.5) * 0.0008
        grain = noise(rng, 6, N / 2, 0.6, aniso=30)
        rings = nm(rng, 0.4, 0.008, 1.2, aniso=10)
        brush = nm(rng, 0.3, 0.003, 0.9, aniso=20)
        coat = nm(rng, 0.8, 0.05, 1.5)
        tn, tr, _ = pegs(rng, L, 0.015)
        tel = 1.0 + 2.5 * chalk                      # thin, sun-worn paint shows the wood more
        h = (hj + face * (cup + lift + 0.00002 * tel * grain + 0.00005 * tel * rings + 0.000025 * brush
                          + 0.00012 * tn - 0.00025 * tr) + 0.0005 * nm(rng, 1.0, 0.1, 1.8))
        # salt: in the seams and streaking down below them, in patches
        drip = nm(rng, 0.5, 0.004, 0.9, aniso=10, ang=math.pi / 2)
        runlen = 0.03 + 0.10 * _s(nm(rng, 0.5, 0.05, 1.3, aniso=4, ang=math.pi / 2), -1.2, 1.2)
        run = np.exp(-L["Y"] / runlen)
        patch = _s(nm(rng, 1.0, 0.08, 1.5), -0.8, 1.4)
        salty = np.clip(salt * patch * (0.8 * _s(drip, 0.3, 1.8) * run + 0.6 * (1 - face)
                                        + 0.3 * _s(nm(rng, 0.6, 0.01, 1.3), 0.6, 2.2)), 0, 1)
        # chipped paint: on the arrises of the seams and in flakes along the grain
        edge = 1 - _s(dm, 0.003, 0.015)
        thr = 3.0 - 2.4 * wear
        flake = nm(rng, 0.25, 0.003, 1.1) + 0.6 * _s(grain, 1.0, 2.5)
        worn = _s(flake + 1.3 * edge, thr, thr + 0.3) * face
        h = h - 0.00015 * worn
        tone = 1.0 + 0.06 * (tab[row, 2] - 0.5) + 0.03 * brush + 0.035 * coat + 0.012 * tel * rings
        color = _mul(_rgb(paint), tone)
        color = _mix(color, under, worn * 0.9)
        color = _mul(color, 1.0 + (0.06 + 0.15 * chalk) * tn - 0.3 * tr)
        rough = rough0 + 0.05 * brush + 0.04 * coat
        if chalk:
            bloom = _s(nm(rng, 0.8, 0.02, 1.4), -0.5, 1.5) * chalk
            color = _mix(color, (0.70, 0.69, 0.66), bloom * 0.3)
            rough = rough + 0.2 * bloom
        if crackle:
            ck = cracks(rng, crackle, 0.0, (0.05, 0.4), (0.6, 1.4), turn=0.02, spread=0.04) * face
            color = _mix(color, _mul(_rgb(under), 0.6), ck * 0.8)
            h = h - 0.0003 * ck
            rough = _mix(rough, 0.85, ck)
        if rust:
            heads = np.zeros((N, N))
            for _ in range(rust):
                cx = (L["fu"][rng.integers(len(L["fu"]))] + rng.normal(0, 0.004 / T)) * N
                cy = (rng.integers(n) + rng.normal(0, 0.05)) / n * N
                idx, dx, dy = window(cx, cy, 0.012 / px)
                stamp_max(heads, idx, _s(0.006 / px - np.maximum(np.abs(dx), np.abs(dy)), -0.6, 0.6))
            weep = smear_down(heads * 0.8, 0.10 / px) * _s(drip + 0.8, 0.0, 1.5)
            weep = np.clip(np.maximum(heads, weep), 0, 1)
            color = _mix(color, (0.40, 0.19, 0.09), weep * 0.55)
            color = _mix(color, (0.16, 0.10, 0.07), heads * 0.8)
            h = h + 0.0004 * heads
        color = _mix(color, (0.80, 0.79, 0.75), salty * 0.7)
        color = _mix(_mul(color, 0.55), color, _s(dm, 0.0025, 0.006))      # pitch in the seams
        rough = _mix(rough, 0.82, worn)
        rough = _mix(rough, 0.9, salty)
        rough = _mix(0.55, rough, face)
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.003, cavity=0.3)
    return gen


# ---------------------------------------------------------------------------
# b_floor = DECK, 2 m per repeat: 0.2 m planks along U, beams every 0.5 m
# ---------------------------------------------------------------------------
DECK = {
    #            early wood            late wood             pore colour           rays/fleck
    "pine": dict(early=(0.82, 0.74, 0.60), late=(0.68, 0.56, 0.41), pore=(0.65, 0.55, 0.43),
                 ray=(0.84, 0.77, 0.65), streak=(0.72, 0.63, 0.50), sap=(0.85, 0.78, 0.66),
                 sp=(0.003, 0.008), porous="diffuse", rough=0.72, relief=0.00015, pore_depth=0.00002,
                 contrast=0.7, pore_c=0.15, knots=4, grey=(0.66, 0.64, 0.60)),
    "oak": dict(early=(0.52, 0.41, 0.29), late=(0.40, 0.30, 0.20), pore=(0.31, 0.24, 0.17),
                ray=(0.58, 0.48, 0.36), streak=(0.43, 0.34, 0.24), sap=(0.56, 0.46, 0.34),
                sp=(0.0028, 0.006), porous="ring", rough=0.74, relief=0.00012, pore_depth=0.0001,
                contrast=0.8, pore_c=0.4, knots=2, grey=(0.46, 0.44, 0.41)),
    "teak": dict(early=(0.64, 0.48, 0.31), late=(0.53, 0.38, 0.23), pore=(0.40, 0.29, 0.18),
                 ray=(0.68, 0.54, 0.37), streak=(0.43, 0.31, 0.19), sap=(0.69, 0.55, 0.38),
                 sp=(0.003, 0.0065), porous="semi", rough=0.66, relief=0.0001, pore_depth=0.00006,
                 contrast=0.75, pore_c=0.4, knots=0, grey=(0.60, 0.57, 0.52)),
}


def deck(name, grey=0.25):
    """Deck planking 0.2 m wide along U: seams caulked and payed with black pitch (8 mm,
    slightly sunk, ragged), butts on the beams, a pair of round bungs over the fastenings on
    every beam; holystoned: scoured flat and pale along the planks, the soft early wood
    worn below the late wood, arrises rounded down to the pitch, silvered in patches, a few
    pitch drips."""
    def gen(rng):
        px = T / N
        sp = DECK[name]
        L = planks(rng, 0.2, 0.5, butt_p=0.35)
        n, row = L["n"], L["row"]
        dm = np.minimum(L["dside"], L["dbutt"])
        cw = 0.0038 + 0.0006 * nm(rng, 0.3, 0.02, 1.2, aniso=4)       # half width of the pitch line
        color, h, rough, late = wood_surface(rng, sp, L["Y"], L["pw"], row, n, xl=L["xl"], seg_len=L["sl"],
                                             knots=sp["knots"], plank_mask=_s(dm, 0.015, 0.025), loop=L["loop"])
        tab = rng.random(n)
        color = _mul(color, 1.0 + 0.08 * (tab[row] - 0.5))
        scour = noise(rng, 20, N / 2, 0.3, aniso=40)
        g = _s(nm(rng, 1.0, 0.05, 1.5) + 0.3 * nm(rng, 0.2, 0.01, 1.3), 0.0, 1.8) * grey
        color = _mix(color, sp["grey"], g)
        color = _mul(color, 1.0 + 0.02 * scour)
        bd, br, bt = pegs(rng, L, 0.011, ys=(0.28, 0.72), off=0.06)
        color = _mul(color, 1.0 + 0.08 * bt * bd - 0.16 * br)
        stain = 1 - _s(dm, cw, cw + 0.004)                             # pitch bled into the edges
        color = _mix(color, _mul(color, 0.6), stain * 0.5)
        drips = spots(rng, 14, (0.002, 0.006), 0.3) * (1 - _s(dm, 0.02, 0.05))
        pitch = np.clip(_s(cw - dm, -0.6 * px, 0.6 * px) + drips, 0, 1)
        pc = _mul(_rgb((0.075, 0.068, 0.062)), 1.0 + 0.15 * nm(rng, 0.2, 0.01, 1.2))
        color = _mix(color, pc, pitch)
        bevel = 1 - _s(dm, cw, cw + 0.005)
        h = h + 0.000006 * scour - 0.0006 * bevel ** 2 - 0.0002 * br
        h = _mix(h, -0.0009 + 0.0002 * nm(rng, 0.1, 0.01, 1.2), pitch * (1 - drips))
        h = h + 0.0002 * drips
        rough = rough + 0.03 * scour + 0.06 * g
        rough = _mix(rough, 0.45, pitch)
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.001, cavity=0.2)
    return gen


# ---------------------------------------------------------------------------
# c_wood = WOOD, 1.2 m per repeat (grain along U; the pine spar along V)
# ---------------------------------------------------------------------------
SHIP_WOODS = {
    "oak": dict(early=(0.60, 0.42, 0.24), late=(0.42, 0.27, 0.14), pore=(0.28, 0.18, 0.09),
                ray=(0.68, 0.50, 0.31), streak=(0.44, 0.30, 0.17), sap=(0.64, 0.48, 0.30),
                sp=(0.0028, 0.006), porous="ring", rough=0.30, relief=0.00004, pore_depth=0.00008,
                contrast=0.9, pore_c=0.45),
    "mahogany": dict(early=(0.50, 0.23, 0.13), late=(0.37, 0.15, 0.08), pore=(0.22, 0.08, 0.04),
                     ray=(0.56, 0.29, 0.16), streak=(0.31, 0.12, 0.07), sap=(0.58, 0.32, 0.19),
                     sp=(0.004, 0.009), porous="diffuse", rough=0.24, relief=0.00002, pore_depth=0.00004,
                     contrast=0.6, pore_c=0.5),
}


def wood_varnished(name, ribbon=0.0, dings=40, wear=0.3):
    """Edge-glued boards (villa) under varnish: amber coat, slightly uneven build-up, dings
    and fine scratches, rubbed dull where hands and ropes wear it; mahogany with the ribbon
    stripe of interlocked grain."""
    def gen(rng):
        px = T / N
        Y, bw, ident, nb = boards_v(rng, 0.10, 0.22)
        color, h, rough, late = wood_surface(rng, SHIP_WOODS[name], Y, bw, ident, nb)
        if ribbon:
            k = int(round(T / 0.025))
            rb = np.sin(2 * math.pi * (V * k + 0.8 * nm(rng, 0.6, 0.06, 1.5, aniso=8)))
            color = _mul(color, 1.0 + ribbon * rb * _s(nm(rng, 0.8, 0.1, 1.5), -1.0, 1.0))
        dg = cracks(rng, dings, rng.uniform(0, math.pi), (0.004, 0.03), (0.6, 1.4), turn=0.1, spread=1.5,
                    value=(80, 200))
        rub = _s(nm(rng, 0.5, 0.03, 1.5), 0.8, 2.0) * wear
        build = nm(rng, 0.4, 0.03, 1.4)
        color = _mul(color, 1.0 - 0.25 * dg + 0.06 * rub)
        h = h - 0.00015 * dg + 0.00002 * build
        rough = rough + 0.04 * build + 0.2 * rub + 0.2 * dg
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0003, cavity=0.1)
    return gen


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


def wood_spar(rng):
    """Pine spar (masts): one long stick, the grain running up the mast (along V) in long
    golden lines with resinous late wood, amber resin streaks, a few small tight knots and
    drying checks; oiled and varnished, the varnish thin and dulled in places."""
    px = T / N
    fr, late, kn = log_grain(rng, 150, wave=1.3, knots=4)
    fib = noise(rng, 6, N / 2, 0.55, aniso=30)
    resin = _s(nm(rng, 0.6, 0.01, 1.1, aniso=20), 1.4, 2.6)
    ck = checks(rng, 14, (0.08, 0.5), (0.6, 1.8))
    dull = _s(nm(rng, 0.5, 0.03, 1.5), 0.6, 2.0)
    color = _mix(_rgb((0.80, 0.60, 0.34)), (0.60, 0.38, 0.17), late * 0.85)
    color = _mul(color, 1.0 + 0.04 * fib + 0.05 * nm(rng, 0.8, 0.05, 1.3, aniso=4))
    color = _mix(color, (0.56, 0.32, 0.12), resin * 0.45)
    color = _mix(color, (0.32, 0.17, 0.07), kn * 0.85)
    color = _mix(color, (0.16, 0.10, 0.06), ck * 0.85)
    color = _mix(color, _mul(color, 0.9) + 0.03, dull * 0.4)
    h = 0.00006 * late + 0.00001 * fib - 0.0025 * ck + 0.0004 * kn + 0.0003 * nm(rng, 0.6, 0.05, 1.6, aniso=4)
    rough = 0.36 + 0.02 * fib - 0.06 * resin + 0.25 * dull + 0.3 * ck
    t = lambda a: np.swapaxes(np.asarray(a), 0, 1)      # grain along V: up the mast
    return dict(color=t(color), h=t(h), rough=t(rough), metal=0.0, depth=0.0008, cavity=0.25)


def wood_driftwood(rng):
    """Driftwood: bleached silver-grey, soft early wood worn away so the late-wood lines
    stand proud, long checks, warm brown left in the grooves, smooth worn crowns."""
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


# ---------------------------------------------------------------------------
# d_stone = TRIM, 1 m per repeat: gilt carving and painted strake / port lids
# ---------------------------------------------------------------------------
def gilt(leaf, wear=0.25, grime=0.3, tarnish=0.0, rough0=0.22):
    """Gold leaf over carved wood: soft chisel facets, 85 mm leaves laid in staggered rows
    (faint overlaps, each leaf its own tone), burnished bright on the high spots, rubbed
    through to the red bole and here and there to the white gesso, a fine craquelure of the
    gesso, dark grime and tarnish in the hollows, small holidays where the leaf did not take."""
    def gen(rng):
        px = T / N
        hf, _ = broken_rock(rng, [(0.07, 0.03, 0.0002, 5.0), (0.025, 0.02, 0.0001, 2.5)], warp=0.25)
        h = 0.0012 * nm(rng, 0.5, 0.05, 1.8) + hf
        hn = 0.5 * _norm(h) + 0.9 * nm(rng, 0.2, 0.012, 1.7)       # high spots: rubbed, low: grime
        k = 12
        wu, wv = warp_uv(rng, 0.002, 0.3, 0.03)
        gv = wv * k
        lrow = np.floor(gv).astype(np.int32) % k
        lv = gv - np.floor(gv)
        gu = wu * k + rng.random(k)[lrow]
        lu = gu - np.floor(gu)
        lid = lrow * k + np.floor(gu).astype(np.int32) % k
        de = np.minimum(np.minimum(lu, 1 - lu), np.minimum(lv, 1 - lv)) * T / k
        lap = np.exp(-(de / 0.0009) ** 2)
        ltone = rng.random(k * k)[lid] - 0.5
        skips = _s(nm(rng, 0.01, px, 0.5), 3.0, 3.5) * (0.3 + 0.7 * lap)
        f1, edge, _, _, _ = voronoi(rng, 50, *warp_uv(rng, 0.005, 0.08, 0.01), 0.9)
        craq = (1 - _s(edge, 0.0, 0.03)) * _s(nm(rng, 0.5, 0.05, 1.4), 0.3, 1.6)
        wn = 0.6 * nm(rng, 0.06, 0.003, 1.1)
        thr = 3.0 - 2.4 * wear
        rub = _s(0.8 * hn + wn, thr, thr + 0.5)
        deep = _s(0.8 * hn + wn, thr + 1.0, thr + 1.3)
        dirt = _s(-hn, 0.3, 2.6) * (0.25 + 0.45 * grime)
        bare = np.clip(rub + skips, 0, 1)
        gold = _mul(_rgb(leaf), 1.0 + 0.04 * ltone + 0.03 * nm(rng, 0.3, 0.02, 1.3) + 0.03 * lap)
        if tarnish:
            gold = _mix(gold, (0.50, 0.38, 0.20), tarnish * _s(nm(rng, 0.4, 0.02, 1.4) - 0.4 * hn, -1.2, 1.8))
        bole = ramp(0.5 + 0.3 * nm(rng, 0.1, 0.005, 1.0), [(0.0, (0.42, 0.15, 0.08)), (1.0, (0.60, 0.27, 0.14))])
        color = _mix(gold, bole, bare)
        color = _mix(color, (0.80, 0.76, 0.66), deep)
        dk = np.clip(dirt + craq * (0.12 + 0.3 * bare), 0, 1)
        color = _mix(color, (0.30, 0.21, 0.11), dk)
        metal = (1 - bare) * (1 - deep) * (1 - dk)
        burn = _s(hn, 0.0, 1.5)                                        # burnished high spots
        rough = _mix(rough0 + 0.08 * (1 - burn) - 0.05 * burn + 0.06 * lap, 0.6, bare)
        rough = _mix(rough, 0.75, deep)
        rough = _mix(rough, 0.85, dk)
        h = h + 0.00004 * lap - 0.0001 * craq - 0.00005 * bare - 0.0001 * deep
        return dict(color=color, h=h, rough=rough, metal=metal, depth=0.002, cavity=0.35)
    return gen


# ---------------------------------------------------------------------------
# e_fabric = CANVAS, 1 m per repeat
# ---------------------------------------------------------------------------
def sailcloth(base, mottle=0.04, weather=0.0, mildew=0.0, fade=0.0, tar=5, stitch_c=(0.55, 0.48, 0.38)):
    """Heavy flax sailcloth: tight plain weave (3.9 mm threads at this scale) with slubs,
    cloths 0.5 m wide (two per repeat; the 0.6 m of real bolts does not divide the 1 m
    repeat) joined by flat seams running up the sail: a 38 mm double layer with folded edges
    and two rows of slanted stitches; soft undulation, weather mottling, mildew specks, a few
    tar smudges."""
    def gen(rng):
        px = T / N
        W = weave(rng, 256, slub=0.25, thin=0.1)
        hh, tone_t, slub = W["hh"], W["tone"], W["slub"]
        cloths = int(round(T / 0.5))
        xu = (U + 0.0008 / T * nm(rng, 0.6, 0.06, 1.5, aniso=6, ang=math.pi / 2)) * cloths
        x = (xu - np.floor(xu) - 0.5) * T / cloths          # m from the seam line
        ax = np.abs(x)
        ov = 0.019
        band = _s(ov - ax, -0.6 * px, 0.6 * px)
        fold = np.exp(-((ax - ov) / 0.0011) ** 2)
        ns = int(round(T / 0.0085))
        sv = V * ns + 0.37 * (x > 0)
        fs = sv - np.floor(sv)
        st_x = ov - 0.0065 + (fs - 0.5) * 0.0025
        stitch = np.exp(-((ax - st_x) / 0.0006) ** 2) * _s(0.32 - np.abs(fs - 0.5), 0.0, 0.08)
        wrink = nm(rng, 0.5, 0.04, 1.8)
        h = 0.0005 * hh + 0.0006 * band + 0.0003 * fold + 0.00015 * stitch + 0.0012 * wrink
        color = _mul(_rgb(base), (0.86 + 0.14 * hh) * (1.0 + 0.06 * tone_t + 0.2 * slub
                                                      + mottle * nm(rng, 0.6, 0.03, 1.4)))
        color = _mul(color, 1.0 - 0.05 * band - 0.08 * fold)
        color = _mix(color, stitch_c, stitch * 0.6)
        rough = 0.86 + 0.05 * (1 - hh) - 0.03 * band
        if weather:
            wb = _s(nm(rng, 0.8, 0.04, 1.5), -0.6, 2.2) * weather
            color = _mix(color, _mul(color, 0.82) * np.array([1.0, 0.97, 0.9]), wb)
            runs = (_s(nm(rng, 0.5, 0.006, 1.0, aniso=12, ang=math.pi / 2), 1.2, 2.6)
                    * _s(nm(rng, 1.0, 0.1, 1.5), 0.0, 1.2))
            color = _mix(color, (0.45, 0.33, 0.20), runs * 0.35 * weather)
        if mildew:
            md = _s(nm(rng, 0.006, px, 0.5), 2.0, 2.9) * _s(nm(rng, 0.5, 0.05, 1.4), 0.4, 1.6) * mildew
            color = _mix(color, (0.25, 0.24, 0.20), md * 0.7)
        if fade:
            fd = _s(nm(rng, 0.7, 0.05, 1.5), -1.5, 2.0) * fade
            color = _mix(color, (0.24, 0.23, 0.22), fd * (0.3 + 0.5 * hh))
            color = _mix(color, (0.52, 0.51, 0.49), _s(nm(rng, 0.3, 0.01, 1.2), 1.0, 2.4) * 0.25 * fade)
        if tar:
            sm = blur(spots(rng, tar, (0.004, 0.015), 0.9), 3.0) * _s(nm(rng, 0.01, 0.002, 0.8), -1.5, 1.0)
            color = _mix(color, (0.16, 0.14, 0.12), np.clip(sm, 0, 1) * 0.55)
            rough = _mix(rough, 0.6, np.clip(sm, 0, 1))
        return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.001, cavity=0.2)
    return gen


def fabric_wool(rng):
    """Wool bunting for flags and pennants: plain weave of uneven worsted (3.9 mm threads),
    slubs, a fuzzy halo and stray fibres. Near-white and low in colour so scripts can tint it."""
    px = T / N
    W = weave(rng, 256)
    hh, top, gx, gy, fx, fy = W["hh"], W["top"], W["gx"], W["gy"], W["fx"], W["fy"]
    tw = np.where(top, np.sin(2 * math.pi * (gy * 2.2 + fx * 0.8)) * W["cu"],
                  np.sin(2 * math.pi * (gx * 2.2 + fy * 0.8)) * W["cv"])
    fuzz = nm(rng, 0.004, px, 0.4)
    stray = cracks(rng, 90, rng.uniform(0, math.pi), (0.01, 0.04), (0.6, 1.0), turn=0.15, spread=2.0,
                   value=(120, 220))
    color = _rgb((0.875, 0.860, 0.825))
    color = _mul(color, (0.82 + 0.18 * hh) * (1.0 + 0.04 * W["tone"] + 0.03 * tw + 0.03 * fuzz
                                              + 0.02 * nm(rng, 0.3, 0.03, 1.3)))
    color = _mix(color, (0.92, 0.91, 0.88), stray * 0.6)
    h = 0.0008 * hh + 0.0001 * tw + 0.00005 * fuzz + 0.00015 * stray + 0.0008 * nm(rng, 0.5, 0.05, 1.8)
    rough = 0.92 + 0.02 * fuzz
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0012, cavity=0.2)


# ---------------------------------------------------------------------------
# f_metal = METAL, 0.5 m per repeat
# ---------------------------------------------------------------------------
def cast_skin(rng, pit_amt=1.0):
    """Sand-cast skin: fine grain, scattered pits, gentle undulation (heights in m)."""
    px = T / N
    sand = nm(rng, 0.004, px, 0.5)
    pits = _s(nm(rng, 0.006, px, 0.35), 2.3, 3.0) * pit_amt
    h = 0.0004 * nm(rng, 0.25, 0.02, 1.8) + 0.000012 * sand - 0.00012 * pits
    return h, sand, pits


RUST = [(0.0, (0.20, 0.12, 0.075)), (0.4, (0.36, 0.19, 0.10)), (0.75, (0.50, 0.27, 0.12)), (1.0, (0.62, 0.38, 0.17))]


def metal_castiron(rng):
    """Black cast iron (guns, fittings): sand-cast skin under a satin blacking of lamp black
    and oil, rubbed to grey metal on the high spots; slightly rusty: orange-brown in the pits
    and in small blooms, with short runs below them."""
    px = T / N
    h0, sand, pits = cast_skin(rng)
    hn = _norm(h0)
    blk = _mul(_rgb((0.125, 0.12, 0.115)), 1.0 + 0.08 * nm(rng, 0.2, 0.01, 1.3) + 0.04 * sand)
    rub = _s(hn + 0.6 * nm(rng, 0.05, 0.004, 1.2), 2.3, 3.2)
    bloom = _s(nm(rng, 0.08, 0.004, 1.2) - 0.4 * hn + 0.6 * _s(nm(rng, 0.4, 0.1, 1.5), 0.0, 1.5), 1.9, 2.7)
    rust = np.clip(bloom + 0.7 * pits, 0, 1)
    runs = smear_down(rust * _s(nm(rng, 0.25, 0.02, 1.4), 0.3, 1.5), 0.04 / px) \
        * _s(nm(rng, 0.3, 0.003, 0.9, aniso=10, ang=math.pi / 2), -0.5, 1.5)
    rust = np.clip(rust + 0.45 * runs, 0, 1)
    h = h0 + 0.0001 * bloom
    rc = ramp(0.5 + 0.25 * nm(rng, 0.03, 0.002, 1.0) + 0.2 * nm(rng, 0.2, 0.03, 1.5), RUST)
    color = _mix(blk, (0.42, 0.41, 0.40), rub)
    color = _mix(color, rc, rust)
    metal = _mix(0.35, 0.9, rub) * (1 - rust)
    rough = _mix(_mix(0.5 + 0.04 * sand, 0.4, rub), 0.88, rust)
    return dict(color=color, h=h, rough=rough, metal=metal, depth=0.0004, cavity=0.3)


def metal_gunbronze(rng):
    """Old bronze guns: cast skin under a dark brown patina, the warm metal rubbed bright on
    the high spots, blue-green verdigris in the hollows and in short runs below them."""
    px = T / N
    h0, sand, pits = cast_skin(rng, 0.6)
    hn = _norm(h0)
    vg = _s(0.6 * nm(rng, 0.06, 0.004, 1.3) - 0.8 * hn + 0.8 * pits, 1.7, 2.6) * 0.85
    vg = np.clip(vg + 0.3 * smear_down(vg, 0.03 / px) * _s(nm(rng, 0.3, 0.003, 0.9, aniso=10, ang=math.pi / 2),
                                                           0.0, 1.5), 0, 1)
    worn = _s(hn + 0.4 * nm(rng, 0.1, 0.006, 1.4), 1.6, 3.2) * (1 - vg)
    powder = nm(rng, 0.004, px, 0.5)
    h = h0 + vg * (0.00015 + 0.00008 * powder)
    pat = _mix(_rgb((0.33, 0.25, 0.16)), (0.24, 0.19, 0.12), _s(nm(rng, 0.25, 0.008, 1.4), -1.5, 1.5))
    pat = _mix(pat, (0.27, 0.27, 0.19), _s(nm(rng, 0.4, 0.02, 1.4), 0.0, 2.0) * 0.4)   # greenish bloom
    color = _mix(pat, (0.60, 0.45, 0.28), worn * 0.8)
    vc = ramp(0.5 + 0.3 * nm(rng, 0.05, 0.003, 1.0) + 0.2 * powder,
              [(0.0, (0.22, 0.33, 0.28)), (0.5, (0.32, 0.47, 0.40)), (1.0, (0.48, 0.60, 0.51))])
    color = _mix(color, vc, vg)
    color = _mix(color, (0.12, 0.09, 0.06), pits * 0.6)
    metal = (0.6 + 0.4 * worn) * (1 - vg)
    rough = _mix(0.5 - 0.22 * worn + 0.03 * sand, 0.9 + 0.03 * powder, vg)
    return dict(color=color, h=h, rough=rough, metal=metal, depth=0.0004, cavity=0.3)


def metal_brass(rng):
    """Polished brass fittings: warm and bright, polishing swirls and fine scratches, a
    browner tarnish creeping in from the hollows, a speck of verdigris in a few pits."""
    px = T / N
    h0, sand, pits = cast_skin(rng, 0.25)
    sw = nm(rng, 0.03, px * 2, 0.6, aniso=3, ang=rng.uniform(0, math.pi))
    scr = cracks(rng, 160, rng.uniform(0, math.pi), (0.01, 0.06), (0.5, 0.9), turn=0.01, spread=1.5,
                 value=(60, 200))
    h = 0.4 * h0 + 0.000002 * sw - 0.00001 * scr
    hn = _norm(h)
    tarn = _s(-0.5 * hn + 0.8 * nm(rng, 0.05, 0.003, 1.2) + 0.5 * nm(rng, 0.4, 0.05, 1.6), 1.6, 2.8) * 0.7
    green = pits * _s(nm(rng, 0.2, 0.02, 1.3), 0.5, 1.5)
    color = _mul(_rgb((0.91, 0.77, 0.47)), 1.0 + 0.02 * nm(rng, 0.2, 0.02, 1.3) + 0.01 * sw)
    color = _mix(color, (0.66, 0.50, 0.28), tarn * 0.6)
    color = _mix(color, (0.35, 0.55, 0.45), green)
    rough = 0.15 + 0.02 * sw + 0.1 * scr + 0.18 * tarn + 0.5 * green
    return dict(color=color, h=h, rough=rough, metal=1.0 - green, depth=None, cavity=0.0)


# ---------------------------------------------------------------------------
# g_glass = GLASS (alpha BLEND), 0.6 m per repeat
# ---------------------------------------------------------------------------
def glass_leaded(tint, alpha):
    """Leaded lights: diamond quarries 10 cm wide and 15 cm tall in 8 mm lead cames with
    soldered joints, the lead dull and whitened by oxide; every quarry of crown glass its own
    thickness of tint and slightly tilted in the lead, wavy, with seeds; grime against the
    cames. The lead is opaque (alpha map in the base colour)."""
    def gen(rng):
        px = T / N
        nu, nv = int(round(T / 0.1)), int(round(T / 0.15))
        a, b = U * nu + V * nv, U * nu - V * nv
        g = math.hypot(nu / T, nv / T)
        da, db = np.abs(_wrap(a)) / g, np.abs(_wrap(b)) / g
        dc = np.minimum(da, db)
        hw = 0.0042
        came = _s(hw - dc, -0.6 * px, 0.6 * px)
        prof = np.sqrt(np.clip(1 - (dc / hw) ** 2, 0, 1))
        blob = _s(0.0085 + 0.001 * nm(rng, 0.02, 0.004, 1.0) - np.hypot(da, db), -px, px)
        cm = np.maximum(came, blob)
        fa, fb = np.floor(a).astype(np.int64), np.floor(b).astype(np.int64)
        pid = ((fa + fb + 1) % (2 * nu)) * (2 * nv) + (fa - fb) % (2 * nv)
        tab = rng.random((4 * nu * nv, 3))
        la, lb = a - fa - 0.5, b - fb - 0.5
        wav = nm(rng, 0.12, 0.01, 1.6)
        seeds = _s(nm(rng, 0.004, px, 0.4), 2.7, 3.3)
        hg = 0.0007 * ((tab[pid, 0] - 0.5) * la + (tab[pid, 1] - 0.5) * lb) + 0.00025 * wav + 0.00003 * seeds
        thick = tab[pid, 2] - 0.5
        gcol = _mul(_rgb(tint), 1.0 + 0.07 * thick + 0.03 * wav)
        near = np.exp(-((dc - hw) / 0.006) ** 2) * (1 - came)
        grime = near * _s(nm(rng, 0.2, 0.01, 1.3), -0.8, 1.2)
        gcol = _mix(gcol, _mul(gcol, 0.8), near * 0.4)
        gcol = _mix(gcol, (0.30, 0.30, 0.24), grime * 0.35)
        gcol = _mix(gcol, (0.97, 0.98, 0.97), seeds * 0.5)
        lead = _mix(_rgb((0.22, 0.22, 0.23)), (0.42, 0.42, 0.41), _s(nm(rng, 0.1, 0.005, 1.2), 0.3, 1.8))
        lead = _mix(lead, (0.40, 0.40, 0.40), blob * 0.6)
        lead = _mul(lead, 0.85 + 0.15 * prof)
        color = _mix(gcol, lead, cm)
        h = _mix(hg, 0.0018 * prof + 0.0003 * blob, cm)
        rough = _mix(0.04 + 0.08 * grime + 0.01 * wav, 0.55, cm)
        amap = _mix(np.clip(alpha + 0.04 * thick + 0.15 * grime, 0, 1), 1.0, cm)
        return dict(color=color, h=h, rough=rough, metal=0.3 * cm, depth=None, cavity=0.0, alpha=amap)
    return gen


def glass_crown(tint):
    """Plain old crown glass: faint green-blue tint, gentle waves and draw lines, seeds."""
    def gen(rng):
        px = T / N
        wav = nm(rng, 0.15, 0.01, 1.6) + 0.3 * nm(rng, 0.3, 0.005, 1.2, aniso=10)
        seeds = _s(nm(rng, 0.004, px, 0.4), 2.8, 3.3)
        color = _mul(_rgb(tint), 1.0 + 0.015 * wav)
        color = _mix(color, (0.98, 0.99, 0.98), seeds * 0.5)
        return dict(color=color, h=0.0003 * wav + 0.00003 * seeds, rough=0.03 + 0.01 * seeds, metal=0.0,
                    depth=None, cavity=0.0)
    return gen


# ---------------------------------------------------------------------------
# h_glow = GLOW (emissive), 1 m per repeat
# ---------------------------------------------------------------------------
def glow_lantern(rng):
    """Lantern flame light: warm candle/oil light in soft tongues stretched up and down (V),
    gently uneven so nothing marks the repeat."""
    fl = nm(rng, 0.5, 0.03, 1.7, aniso=4, ang=math.pi / 2)
    hot = nm(rng, 0.8, 0.1, 1.8)
    gl = np.clip(0.66 + 0.05 * fl + 0.06 * hot, 0, 1)
    em = ramp(gl, [(0.0, (0.80, 0.30, 0.06)), (0.45, (1.0, 0.60, 0.20)), (0.75, (1.0, 0.78, 0.42)),
                   (1.0, (1.0, 0.93, 0.70))])
    color = _mix(_rgb((0.93, 0.80, 0.58)), (0.98, 0.90, 0.74), gl)
    return dict(color=color, h=0.0001 * nm(rng, 0.5, 0.05, 1.5), rough=0.3, metal=0.0, depth=None,
                cavity=0.0, emissive=em)


def glow_white(rng):
    px = T / N
    f = nm(rng, 0.01, px * 2, 0.4)
    color = _mul(_rgb((0.97, 0.97, 0.97)), 1.0 + 0.003 * f)
    return dict(color=color, h=0.000003 * f, rough=0.30 + 0.02 * f, metal=0.0, depth=None, cavity=0.0,
                emissive=_rgb((1.0, 1.0, 1.0)))


# ---------------------------------------------------------------------------
# water, 4 m per repeat
# ---------------------------------------------------------------------------
def water_sea(rng):
    """Open sea: dark green-blue, wind waves with sharpened crests and flat troughs, chop and
    ripples on them, crests a little lighter and greener, sparse foam on the crests and in
    thin streaks along the wind."""
    wind = rng.uniform(0, math.pi)
    sw = nm(rng, 4.0, 0.6, 2.0, aniso=2.0, ang=wind + math.pi / 2)
    sw = sw + 0.25 * (sw * sw - 1.0)
    h = (0.05 * sw + 0.012 * nm(rng, 1.2, 0.15, 1.6, aniso=1.5, ang=wind + math.pi / 2 + 0.4)
         + 0.0012 * nm(rng, 0.25, 0.02, 1.2))
    hn = _norm(h)
    crest = _s(hn + 0.7 * nm(rng, 0.3, 0.01, 1.0), 2.3, 3.2) * _s(nm(rng, 2.0, 0.3, 1.5), -0.2, 1.5)
    streak = _s(nm(rng, 1.5, 0.01, 1.0, aniso=14, ang=wind), 2.0, 3.0) * _s(nm(rng, 2.0, 0.2, 1.5), 0.3, 1.5)
    foam = np.clip(crest + 0.6 * streak, 0, 1) * _s(nm(rng, 0.05, 0.004, 0.8), -1.0, 1.0)
    color = _mix(_rgb((0.035, 0.11, 0.13)), (0.07, 0.24, 0.24), _s(hn, -0.5, 2.5) * 0.6)
    color = _mul(color, 1.0 + 0.06 * nm(rng, 1.5, 0.2, 1.5))
    color = _mix(color, (0.74, 0.80, 0.79), foam * 0.85)
    rough = 0.05 + 0.03 * _s(nm(rng, 1.0, 0.1, 1.4), 0.0, 2.0) + 0.5 * foam
    return dict(color=color, h=h + 0.002 * foam, rough=rough, metal=0.0, depth=None, cavity=0.0)


def water_harbour(rng):
    """Harbour water: murky green, calm, brown silt clouds drifting in it, a grey-brown scum
    gathering in lanes with chips, straws and a few bubbles caught in it (after the Pit's
    sea water)."""
    px = T / N
    wind = rng.uniform(0, math.pi)
    fu_, fv_ = 0.03 * nm(rng, 3.0, 0.5, 1.6), 0.03 * nm(rng, 3.0, 0.5, 1.6)
    silt = sample(nm(rng, 2.0, 0.1, 1.3), fu_, fv_)
    lanes = sample(nm(rng, 2.0, 0.17, 1.4, aniso=2.5, ang=wind), fu_ * 1.5, fv_ * 1.5)
    ridged = 1.0 - np.abs(sample(nm(rng, 1.0, 0.05, 1.2), fu_, fv_))
    h = (0.008 * nm(rng, 2.5, 0.4, 2.0, aniso=1.8, ang=wind) + 0.002 * nm(rng, 0.5, 0.1, 1.5, aniso=1.4)
         + 0.0003 * nm(rng, 0.13, 0.025, 1.0))
    color = _mix(_rgb((0.055, 0.095, 0.065)), (0.10, 0.155, 0.095), _s(silt, -1.2, 1.4))
    color = _mix(color, (0.13, 0.12, 0.075), _s(silt, 1.0, 2.2) * 0.6)
    scum = _s(ridged * 1.2 + 0.9 * lanes - 1.6, 0.0, 0.5) * _s(lanes, -0.2, 0.8)
    scum = np.clip(scum * (0.6 + 0.4 * _s(nm(rng, 0.13, 0.013, 0.6), -1, 1)), 0, 1)
    foam = _s(nm(rng, 0.1, 0.01, 0.5), 0.8, 2.0) * scum
    color = _mix(color, (0.20, 0.19, 0.14), scum * 0.55)
    color = _mix(color, (0.36, 0.35, 0.29), foam * 0.5)
    cv, bub = Canvas(3), Canvas(3)
    lane_p = np.clip(scum * 1.5 + 0.05, 0, 1)
    count = 0
    while count < 260:
        x, y = rng.random() * N, rng.random() * N
        if rng.random() > lane_p[int(y) % N, int(x) % N]:
            continue
        count += 1
        if rng.random() < 0.55:
            a = rng.uniform(0, math.pi)
            ln = rng.uniform(0.012, 0.05) / px
            cv.line([(x, y), (x + math.cos(a) * ln, y + math.sin(a) * ln)], rng.uniform(1.0, 2.0),
                    value=int(rng.uniform(150, 255)))
        else:
            r = rng.uniform(0.6, 1.6)
            bub.polygon([(x + r * math.cos(t), y + r * math.sin(t)) for t in np.linspace(0, 2 * math.pi, 9)[:-1]])
    bits, bubbles = cv.get(), bub.get()
    color = _mix(color, _mix(_rgb((0.33, 0.27, 0.16)), (0.15, 0.11, 0.07), _s(nm(rng, 0.1, 0.01, 0.5), -1, 1)), bits)
    color = _mix(color, (0.42, 0.43, 0.38), bubbles * 0.5)
    h = h + 0.0008 * bits + 0.0012 * bubbles
    rough = 0.04 + 0.03 * _s(nm(rng, 2.0, 0.2, 1.2), 0.5, 2.0) + 0.45 * scum + 0.2 * foam
    rough = _mix(_mix(rough, 0.75, bits), 0.1, bubbles)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)


# ---------------------------------------------------------------------------
# The catalogue. Order inside each slot = menu order (default first). res: texture size.
# ---------------------------------------------------------------------------
LIB = {
    "a_plaster": [
        dict(id="tar", label="Black tar", gen=painted_planks((0.135, 0.125, 0.115), rough0=0.45, wear=0.12,
                                                              salt=0.35, under=(0.24, 0.17, 0.11))),
        dict(id="oxblood", label="Oxblood red", gen=painted_planks((0.33, 0.10, 0.075), rough0=0.5, wear=0.15,
                                                                    salt=0.35, under=(0.15, 0.11, 0.08))),
        dict(id="navy", label="Navy blue", gen=painted_planks((0.085, 0.115, 0.20), rough0=0.5, wear=0.15,
                                                               salt=0.35, under=(0.15, 0.11, 0.08))),
        dict(id="weathered", label="Weathered grey", gen=painted_planks((0.47, 0.46, 0.43), rough0=0.72, wear=0.5,
                                                                        salt=0.5, under=(0.38, 0.34, 0.29),
                                                                        chalk=0.6, crackle=70, rust=6)),
    ],
    "b_floor": [
        dict(id="pine", label="Holystoned pine", gen=deck("pine", grey=0.2)),
        dict(id="oak", label="Oak deck", gen=deck("oak", grey=0.25)),
        dict(id="teak", label="Teak deck", gen=deck("teak", grey=0.3)),
    ],
    "c_wood": [
        dict(id="oak", label="Varnished oak", gen=wood_varnished("oak")),
        dict(id="pine", label="Pine spar", gen=wood_spar),
        dict(id="mahogany", label="Mahogany", gen=wood_varnished("mahogany", ribbon=0.07, dings=25, wear=0.15)),
        dict(id="driftwood", label="Driftwood", gen=wood_driftwood),
    ],
    "d_stone": [
        dict(id="gilt", label="Gilded carving", gen=gilt((0.95, 0.78, 0.44), wear=0.25, grime=0.3)),
        dict(id="ochre", label="Ochre paint", gen=painted_planks((0.74, 0.55, 0.21), rough0=0.5, wear=0.2,
                                                                  salt=0.25, under=(0.28, 0.20, 0.13), rust=2)),
        dict(id="red", label="Gun-port red", gen=painted_planks((0.52, 0.11, 0.07), rough0=0.48, wear=0.18,
                                                                 salt=0.2, under=(0.20, 0.13, 0.09), rust=2)),
        dict(id="faded", label="Faded gilt", gen=gilt((0.76, 0.60, 0.33), wear=0.55, grime=0.6, tarnish=0.6,
                                                      rough0=0.36)),
    ],
    "e_fabric": [
        dict(id="canvas", label="Sailcloth", gen=sailcloth((0.86, 0.83, 0.75), mottle=0.025, weather=0.15,
                                                           mildew=0.1, tar=3)),
        dict(id="tan", label="Weathered canvas", gen=sailcloth((0.70, 0.62, 0.49), mottle=0.07, weather=0.8,
                                                              mildew=0.6, tar=8)),
        dict(id="black", label="Black sailcloth", gen=sailcloth((0.12, 0.115, 0.11), mottle=0.05, fade=0.6, tar=0,
                                                               stitch_c=(0.09, 0.085, 0.08))),
        dict(id="wool", label="Wool bunting (tint)", gen=fabric_wool),
    ],
    "f_metal": [
        dict(id="iron", label="Cast iron", gen=metal_castiron),
        dict(id="bronze", label="Old bronze", gen=metal_gunbronze),
        dict(id="brass", label="Polished brass", gen=metal_brass),
    ],
    "g_glass": [
        dict(id="leaded", label="Leaded diamonds", alpha=0.5, gen=glass_leaded((0.80, 0.87, 0.78), 0.5)),
        dict(id="amber", label="Amber leaded", alpha=0.55, gen=glass_leaded((0.93, 0.68, 0.32), 0.55)),
        dict(id="clear", label="Crown glass", alpha=0.25, res=512, gen=glass_crown((0.92, 0.95, 0.93))),
    ],
    "h_glow": [
        dict(id="lantern", label="Lantern flame", gen=glow_lantern, res=512),
        dict(id="white", label="White light (tint)", gen=glow_white, res=512),
    ],
    "water": [
        dict(id="sea", label="Open sea", gen=water_sea, alpha=0.8, double=True),
        dict(id="harbour", label="Harbour water", gen=water_harbour, alpha=0.85, double=True),
    ],
}
DEFAULT = {"a_plaster": "tar", "b_floor": "pine", "c_wood": "oak", "d_stone": "gilt", "e_fabric": "canvas",
           "f_metal": "iron", "g_glass": "leaded", "h_glow": "lantern", "water": "sea"}

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


def write_glb(path, name, pngs, size, alpha=None, emissive=False, double=False, alpha_tex=False):
    """One metallicRoughness material named `name` and a quad (size metres = one repeat).
    alpha_tex: the base colour PNG carries the alpha (RGBA), so the factor's alpha is 1."""
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
        "pbrMetallicRoughness": {"baseColorFactor": [1.0, 1.0, 1.0, 1.0 if alpha is None or alpha_tex
                                                     else float(alpha)],
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
        "asset": {"version": "2.0", "generator": "The Second Bride - stextures.py"},
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


def validate_glb(path, name, res, alpha=None, emissive=False, alpha_tex=False):
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
    if alpha is not None and abs(pbr["baseColorFactor"][3] - (1.0 if alpha_tex else alpha)) > 1e-6:
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
        elif im["name"].endswith("_basecolor") and (Image.open(io.BytesIO(png)).mode == "RGBA") != alpha_tex:
            err.append(f"image {im['name']}: RGBA expected {alpha_tex}")
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
    base = maps["basecolor"][..., :3].astype(float) / 255.0
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
            a = maps["basecolor"][..., 3:].astype(float) / 255.0 if maps["basecolor"].shape[-1] == 4 else alpha
            img = img * a + back * (1 - a)
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
    alpha_tex = out.get("alpha") is not None
    if alpha_tex:
        color = np.concatenate([color, np.clip(out["alpha"], 0, 1)[..., None]], -1)
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
    write_glb(glb, name, pngs, UV_TILE[slot], alpha, "emissive" in maps, v.get("double", False), alpha_tex)
    errors = validate_glb(glb, name, res, alpha, "emissive" in maps, alpha_tex)
    seams = {kind: round(seam(img), 2) for kind, img in maps.items()}
    kind = "glow" if "emissive" in maps else ("clear" if alpha is not None else "opaque")
    swatch = _display(maps, kind, alpha, res)
    src = maps["emissive"] if "emissive" in maps else maps["basecolor"]
    mean = [int(round(x)) for x in src[..., :3].reshape(-1, 3).mean(0)]
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
    d.text((pad, pad - 6), "THE SECOND BRIDE  -  PBR material library", fill=(236, 226, 208), font=_font(26, True))
    d.text((pad, pad + 28), "Swatch = one full repeat, softly lit. Glass and water over a checker at their alpha.",
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

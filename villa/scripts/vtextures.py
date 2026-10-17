"""Procedural PBR material library for The Villa (seamless, physically scaled).

The script makes every material variant the owner can pick from the Villa menus, using only
numpy and pillow:

  output/textures/<slot>__<variant>_basecolor.png   sRGB
  output/textures/<slot>__<variant>_normal.png      glTF tangent space (OpenGL, +Y up)
  output/textures/<slot>__<variant>_orm.png         R occlusion, G roughness, B metallic
  output/textures/<slot>__<variant>_emissive.png    sRGB, glow materials only
  output/textures/_swatches.png                     contact sheet (every variant, labelled)
  output/pbr_materials/villa_<slot>_<variant>.glb   one glTF 2.0 material (plus a quad that
                                                    uses it) for the Second Life bulk uploader
  docs/materials.json                               the catalogue read by the build, the
                                                    renderer and the LSL menus

Look: pristine, warm, architectural. Microcement and lime plaster, travertine, oak, walnut,
Calacatta, boucle, brushed brass... No dirt, no wear, no grime. Every repeat is varied enough
that no single feature marks the grid.

Seamless by construction: all noise lives on a torus (white noise filtered with an FFT),
Voronoi wraps its neighbours, tile/plank layouts divide the repeat exactly and everything drawn
is drawn with its copies one repeat away. Edges are checked numerically at the end.

Physical scale: one repeat covers UV_TILE[slot] metres (read from vmesh.py, which maps UVs in
world space at that scale). Heights are in metres and the normal maps are computed with the
real pixel size, so slopes are physically right.

The toolkit (periodic noise, Voronoi, Canvas, normals, glb writer, seam check) is adapted from
the_pit/scripts/pbr_textures.py; it is copied here because that module imports bpy and fixes
the resolution.

Usage:  python3 villa/scripts/vtextures.py [filter ...] [--jobs N]
        (filters keep only variants whose "<slot>__<variant>" contains one of the words;
         a filtered run rewrites only those files and leaves the catalogue untouched)
"""

import ast
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


def _uv_tile():
    """UV_TILE from vmesh.py (parsed, not imported: vmesh imports bpy)."""
    try:
        tree = ast.parse(open(os.path.join(HERE, "vmesh.py")).read())
        for node in tree.body:
            if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "UV_TILE" for t in node.targets):
                return ast.literal_eval(node.value)
    except (OSError, SyntaxError, ValueError):
        pass
    return {"a_plaster": 2.0, "b_floor": 1.6, "c_wood": 1.2, "d_stone": 1.6, "e_fabric": 0.5,
            "f_metal": 1.0, "g_glass": 2.0, "h_glow": 1.0, "water": 3.0}


UV_TILE = _uv_tile()
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow", "water"]

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
    """Periodic Voronoi of cells x cells points. Returns (f1, edge, ident, ru, rv): distance to
    the nearest point, distance to the cell edge (cell units), cell index and the vector from
    the pixel to its point."""
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
    return np.sqrt(f1), edge, ident, ru, rv


def _wrap(x):
    """Periodic difference in [-0.5, 0.5)."""
    return (x + 0.5) % 1.0 - 0.5


def _hash(i, j=0):
    x = np.sin(np.asarray(i, dtype=float) * 12.9898 + np.asarray(j, dtype=float) * 78.233) * 43758.5453
    return x - np.floor(x)


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
# Materials. Each returns a dict: color (sRGB 0..1), h (metres), rough, metal, depth (m, for
# the occlusion; None = no occlusion), optional emissive (sRGB), cavity (base colour darkening
# in the hollows, 0..1).
# ---------------------------------------------------------------------------
def _trowel(rng, layers, big, small, aniso, edge):
    """Overlapping trowel passes of a hand-laid finish: each pass is a smooth anisotropic field
    cut into a thin plate with a soft but readable edge; later passes cover earlier ones.
    Returns tone (~std 1), burnish (0..1), lip (raised edge of each pass), stria (swept
    striations), plates (relief, in coats)."""
    tone = np.zeros((N, N))
    bur = np.zeros((N, N))
    lip = np.zeros((N, N))
    stria = np.zeros((N, N))
    coats = np.zeros((N, N))
    for k in range(layers):
        ang = rng.uniform(0, math.pi)
        n = nm(rng, big, small, 1.7, aniso=aniso, ang=ang)
        thr = rng.uniform(-0.4, 0.9)
        e = edge * rng.uniform(0.5, 1.8)
        plate = _s(n, thr, thr + e)
        op = rng.uniform(0.35, 0.85)
        tone = tone + (rng.normal(0, 1) - tone) * plate * op
        bur = bur + (rng.random() - bur) * plate * op
        st = nm(rng, small * 2.5, small * 0.12, 0.7, aniso=6, ang=ang)
        stria = stria + (st - stria) * plate * op
        lip = np.maximum(lip, 4 * plate * (1 - plate) * rng.uniform(0.3, 1.0))
        coats = coats + plate * rng.uniform(0.5, 1.0)
    tone = (tone - tone.mean()) / (tone.std() + 1e-9)
    return tone, bur, lip, stria, coats


def plaster_microcement(rng, dark=False):
    px = T / N
    tone, bur, lip, stria, coats = _trowel(rng, 9, 0.9, 0.06, 2.4, 0.4 if dark else 0.18)
    cloud = nm(rng, 1.6, 0.2, 1.6)
    sand = nm(rng, 0.004, px * 1.2, 0.3)
    pin = _s(nm(rng, 0.01, px * 1.1, 0.2), 3.2, 3.7)
    if not dark:
        base = _rgb((0.872, 0.862, 0.838))
        color = _mix(base, (0.85, 0.85, 0.845), _s(nm(rng, 1.2, 0.3, 1.5), -0.5, 1.5) * 0.6)  # cooler clouds
        color = _mul(color, 1.0 + 0.017 * tone + 0.012 * cloud + 0.008 * stria - 0.01 * bur
                     + 0.01 * sand - 0.05 * pin)
        rough = 0.70 - 0.08 * bur + 0.0125 * stria - 0.03 * lip + 0.02 * cloud
    else:
        base = _rgb((0.168, 0.162, 0.156))
        light = _s(0.6 * tone + 0.6 * cloud + 0.35 * stria, -0.4, 2.8)
        color = _mix(base, (0.245, 0.238, 0.230), light * 0.8)                  # cement bloom
        color = _mul(color, 1.0 + 0.03 * stria + 0.025 * sand - 0.04 * bur - 0.12 * pin)
        rough = 0.64 - 0.08 * bur + 0.05 * light + 0.02 * stria - 0.03 * lip
    h = (0.00008 * coats + 0.00005 * lip + 0.000015 * stria + 0.0005 * nm(rng, 0.8, 0.15, 1.8)
         - 0.00012 * pin)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0002, cavity=0.05)


def plaster_white(rng):
    return plaster_microcement(rng, dark=False)


def plaster_charcoal(rng):
    return plaster_microcement(rng, dark=True)


def plaster_sand(rng):
    """Tadelakt-like lime plaster: warm soft clouding, compressed (slightly darker, glossier)
    passes from the polishing stone, soft sheen."""
    px = T / N
    tone, bur, lip, stria, coats = _trowel(rng, 8, 0.7, 0.05, 1.8, 0.35)
    cloud = nm(rng, 1.4, 0.12, 1.4)
    mott = warped(rng, 0.5, 0.03, 1.4, amount=0.04)
    cv = Canvas(ss=2)
    for _ in range(2600):
        cx, cy = rng.random() * N, rng.random() * N
        r = rng.uniform(0.03, 0.09) / px
        a0 = rng.uniform(0, 2 * math.pi)
        span = rng.uniform(0.6, 1.4)
        pts = [(cx + r * math.cos(a0 + span * k / 6), cy + r * math.sin(a0 + span * k / 6)) for k in range(7)]
        cv.line(pts, rng.uniform(2.0, 5.0), value=int(rng.uniform(60, 255)))
    polish = blur(cv.get(), 1.2)
    color = _rgb((0.795, 0.692, 0.560))
    color = _mix(color, (0.83, 0.74, 0.62), _s(cloud, 0.2, 1.8) * 0.35)
    color = _mix(color, (0.75, 0.635, 0.495), _s(mott, 0.3, 2.2) * 0.3)
    color = _mul(color, 1.0 + 0.014 * tone + 0.01 * stria - 0.025 * polish - 0.02 * bur
                 + 0.006 * nm(rng, 0.005, px, 0.3))
    h = 0.00007 * coats + 0.00004 * lip + 0.00003 * polish + 0.0005 * nm(rng, 0.9, 0.15, 1.8)
    rough = 0.50 - 0.10 * bur - 0.10 * polish + 0.03 * _s(mott, -1, 1.5) + 0.015 * stria
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0002, cavity=0.05)


def plaster_concrete(rng):
    """Soft grey board-formed concrete: 16 boards (~12.5 cm) per 2 m, each a touch different
    in tone with a faint grain imprint, very fine horizontal lines at the board joints, fine
    sand and the odd tiny pore."""
    px = T / N
    nb = 16
    w = rng.uniform(0.85, 1.15, nb)
    edges = np.concatenate([[0.0], np.cumsum(w / w.sum())])
    off = rng.random()
    vv = (V + off + 0.0004 * noise(rng, 2, 40, 1.4, aniso=6)) % 1.0
    row = np.clip(np.searchsorted(edges, vv, side="right") - 1, 0, nb - 1)
    dvv = np.minimum(vv - edges[row], edges[row + 1] - vv) * T              # metres to the joint
    tab = rng.random((nb, 6))
    grain = noise(rng, 20, 500, 0.8, aniso=8)
    fin = np.exp(-(dvv / 0.0018) ** 2)
    line = np.exp(-(dvv / 0.0022) ** 2) * (0.6 + 0.4 * _s(noise(rng, 4, 80, 1.0, aniso=5), -1, 1))
    cloud = nm(rng, 1.6, 0.08, 1.4)
    mott = nm(rng, 0.25, 0.02, 1.2)
    sand = nm(rng, 0.004, px, 0.2)
    bug = _s(nm(rng, 0.02, px * 1.2, 0.3), 3.1, 3.7)
    color = _rgb((0.618, 0.608, 0.588))
    color = _mul(color, 1.0 + 0.045 * (tab[row, 0] - 0.5) + 0.015 * cloud + 0.012 * mott
                 + 0.006 * grain * (0.5 + tab[row, 1]) + 0.018 * sand - 0.07 * line - 0.3 * bug)
    h = (0.0002 * fin + 0.00001 * grain * (0.5 + tab[row, 1]) + 0.00002 * sand + (tab[row, 2] - 0.5) * 0.0004
         + 0.0006 * nm(rng, 1.0, 0.2, 1.8) - 0.0012 * bug)
    rough = 0.76 + 0.02 * cloud + 0.015 * mott + 0.02 * sand + 0.03 * (tab[row, 3] - 0.5) - 0.04 * fin + 0.1 * bug
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0005, cavity=0.1)


# ---------------------------------------------------------------------------
def travertine_body(rng, light, dark, fill, band_amt, pore_amt, warm):
    """Vein-cut travertine (bands along U): layered tones, lens-shaped pores aligned with the
    bands (most filled), a few open pin pits. Returns color, height, rough modifiers."""
    px = T / N
    b1 = nm(rng, 0.5, 0.005, 0.95, aniso=22)
    b2 = nm(rng, 0.8, 0.02, 1.2, aniso=10)
    wv = 0.006 * nm(rng, 1.6, 0.3, 1.6) + 0.0012 * nm(rng, 0.3, 0.05, 1.4)
    b1 = sample(b1, 0, wv)
    b2 = sample(b2, 0, wv)
    color = _mix(light, dark, _s(b1, -1.3, 2.2) * band_amt)
    color = _mix(color, warm, _s(b2, -0.2, 1.8) * 0.4)
    color = _mul(color, 1.0 + 0.012 * nm(rng, 0.01, px, 0.4) + 0.012 * nm(rng, 1.0, 0.2, 1.4))
    porous = _s(sample(nm(rng, 0.4, 0.02, 1.2, aniso=12), 0, wv), -0.4, 1.4)
    pn = sample(nm(rng, 0.05, px * 1.4, 0.6, aniso=7), 0, wv)
    pores = _s(pn + 1.2 * porous * pore_amt, 2.0, 2.4)
    pits = _s(nm(rng, 0.02, px, 0.3, aniso=2.5) + 0.6 * porous, 3.3, 3.8)
    pore_c = _mul(fill, 0.92 + 0.16 * _s(nm(rng, 0.02, px * 2, 0.5), -1, 1))
    color = _mix(color, pore_c, pores * 0.85)
    color = _mul(color, 1.0 - 0.15 * _s(blur(pores, 1.0), 0.05, 0.6) * (1 - pores))   # pore rims
    color = _mix(color, _mul(dark, 0.55), pits * 0.8)
    h = -0.00008 * pores - 0.0004 * pits + 0.00002 * b1
    rough_add = 0.06 * pores + 0.25 * pits
    return color, h, rough_add


def floor_travertine(rng):
    """Large-format ivory travertine, 4 tiles of 0.8 m per 1.6 m repeat, hairline joints, honed."""
    color, hb, radd = travertine_body(rng, _rgb((0.865, 0.800, 0.690)), _rgb((0.745, 0.655, 0.535)),
                                      _rgb((0.84, 0.78, 0.68)), 0.8, 0.7, _rgb((0.85, 0.74, 0.58)))
    lu, lv, ident, du, dv = tiles(2, 2, 0.13, 0.31)
    trng = np.random.default_rng(rng.integers(1 << 30))
    color, hb, radd = tile_shuffle([color, hb, radd], ident, 4, trng)
    shade = 1.0 + 0.035 * (trng.random(4) - 0.5) * 2
    color = _mul(color, shade[ident])
    d = np.minimum(du, dv)
    hj, face = joint_profile(d, 0.0009, 0.0012, 0.0006)
    grout = (0.80, 0.745, 0.655)
    color = _mix(grout, color, face)
    color = _mul(color, 1.0 - 0.08 * (1 - _s(d, 0.0009, 0.003)))
    h = hb * face + hj
    rough = 0.45 + 0.03 * nm(rng, 0.8, 0.1, 1.2) + radd
    rough = _mix(0.7, rough, face)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0006, cavity=0.1)


def tile_shuffle(fields, ident, count, rng, flip=True):
    """Gives every tile its own piece of periodic fields (same roll/flip for all of them)."""
    outs = [np.empty_like(f) for f in fields]
    for k in range(count):
        sh = (int(rng.integers(N)), int(rng.integers(N)))
        fl = flip and rng.random() < 0.5
        m = ident == k
        for f, o in zip(fields, outs):
            g = np.roll(f, sh, (0, 1))
            if fl:
                g = g[:, ::-1]
            o[m] = g[m]
    return outs


# --- wood ------------------------------------------------------------------
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


WOODS = {
    #            early wood            late wood             pore colour           rays/fleck
    "walnut": dict(early=(0.360, 0.235, 0.155), late=(0.215, 0.135, 0.090), pore=(0.13, 0.08, 0.055),
                   ray=(0.40, 0.27, 0.18), streak=(0.27, 0.19, 0.16), sap=(0.47, 0.33, 0.21),
                   sp=(0.0028, 0.0055), porous="diffuse", rough=0.36, relief=0.00003, pore_depth=0.00004,
                   contrast=0.95, pore_c=0.5),
    "oak": dict(early=(0.700, 0.555, 0.375), late=(0.560, 0.410, 0.255), pore=(0.43, 0.31, 0.19),
                ray=(0.78, 0.65, 0.47), streak=(0.62, 0.47, 0.30), sap=(0.74, 0.60, 0.42),
                sp=(0.0028, 0.006), porous="ring", rough=0.46, relief=0.00004, pore_depth=0.00008,
                contrast=0.85, pore_c=0.35),
    "teak": dict(early=(0.585, 0.400, 0.230), late=(0.470, 0.300, 0.160), pore=(0.30, 0.19, 0.10),
                 ray=(0.62, 0.44, 0.26), streak=(0.33, 0.21, 0.11), sap=(0.64, 0.46, 0.28),
                 sp=(0.003, 0.0065), porous="semi", rough=0.52, relief=0.00004, pore_depth=0.00006,
                 contrast=0.8, pore_c=0.45),
    "ebony": dict(early=(0.115, 0.103, 0.093), late=(0.052, 0.047, 0.043), pore=(0.03, 0.027, 0.025),
                  ray=(0.12, 0.11, 0.10), streak=(0.075, 0.067, 0.06), sap=(0.11, 0.10, 0.09),
                  sp=(0.003, 0.007), porous="ring", rough=0.40, relief=0.00010, pore_depth=0.00020,
                  contrast=1.0, pore_c=0.6),
    "smoked": dict(early=(0.395, 0.300, 0.215), late=(0.270, 0.198, 0.140), pore=(0.17, 0.12, 0.085),
                   ray=(0.47, 0.37, 0.27), streak=(0.33, 0.25, 0.18), sap=(0.44, 0.34, 0.25),
                   sp=(0.0028, 0.006), porous="ring", rough=0.50, relief=0.00008, pore_depth=0.00014,
                   contrast=0.85, pore_c=0.45),
}


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


def wood_species(name):
    return lambda rng: _wood_boards(rng, name)


def floor_oak(rng):
    """Wide-plank smoked oak: 6 planks (26.7 cm) per 1.6 m along U, staggered ends, micro
    bevels on every edge, oiled and lightly brushed, two or three small knots per repeat."""
    np_ = 6
    pw = 1.0 / np_
    vv = (V + 0.37 * pw + 0.0004 * noise(rng, 2, 16, 1.4, aniso=4)) % 1.0
    row = np.floor(vv / pw).astype(np.int32) % np_
    vloc = vv / pw - np.floor(vv / pw)
    seg = np.zeros(U.shape, np.int32)
    dc = np.full(U.shape, 9.0)
    xl = np.zeros(U.shape)
    sl = np.zeros(U.shape)
    phase = rng.random()
    for r in range(np_):
        c0 = (phase + r * 0.382 + rng.uniform(-0.05, 0.05)) % 1.0
        cuts = np.array([c0]) if rng.random() < 0.6 else np.sort([c0, (c0 + rng.uniform(0.4, 0.6)) % 1.0])
        m = row == r
        xs = U[m]
        dc[m] = np.min(np.abs(_wrap(xs[:, None] - cuts[None, :])), axis=1)
        k = np.searchsorted(cuts, xs) % len(cuts)
        seg[m] = k
        start = cuts[k - 1]
        xl[m] = ((xs - start) % 1.0) * T
        ln = (cuts[k] - cuts[k - 1]) % 1.0
        sl[m] = np.where(ln == 0, 1.0, ln) * T
    ident = row * 2 + seg
    d_side = np.minimum(vloc, 1 - vloc) * pw * T
    dm = np.minimum(d_side, dc * T)
    Y = vloc * pw * T
    sp = WOODS["smoked"]
    plank_face = _s(dm, 0.02, 0.03)
    color, h, rough, late = wood_surface(rng, sp, Y, pw * T, ident, np_ * 2, xl=xl, seg_len=sl, knots=3,
                                         plank_mask=plank_face)
    tab = rng.random(np_ * 2)
    color = _mul(color, 1.0 + 0.06 * (tab[ident] - 0.5))
    hj, face = joint_profile(dm, 0.0003, 0.0016, 0.0009)
    color = _mix(_mul(color, 0.55), color, _s(dm, 0.0003, 0.0018))
    h = h * face + hj
    rough = _mix(0.7, rough, face)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0006, cavity=0.1)


TERRAZZO_PAL = [((0.93, 0.905, 0.86), 0.26), ((0.80, 0.63, 0.43), 0.17), ((0.68, 0.42, 0.30), 0.14),
                ((0.86, 0.72, 0.62), 0.12), ((0.58, 0.56, 0.53), 0.13), ((0.97, 0.96, 0.94), 0.10),
                ((0.30, 0.27, 0.25), 0.05), ((0.75, 0.55, 0.38), 0.03)]


def floor_terrazzo(rng):
    """Polished terrazzo: warm white matrix, angular marble chips from 5 mm to 4 cm."""
    px = T / N
    wu = (U + 0.0010 * noise(rng, 6, 120, 1.0)) % 1.0
    wv = (V + 0.0010 * noise(rng, 6, 120, 1.0)) % 1.0
    matrix = _rgb((0.890, 0.862, 0.815))
    matrix = _mul(matrix, 1.0 + 0.018 * nm(rng, 0.004, px, 0.3) + 0.01 * nm(rng, 1.0, 0.1, 1.4))
    color = matrix
    chip = np.zeros((N, N))
    pal = np.array([c for c, _ in TERRAZZO_PAL])
    prob = np.array([p for _, p in TERRAZZO_PAL])
    prob /= prob.sum()
    vein = nm(rng, 0.02, px, 0.6)
    for size, keep, mrg in ((0.042, 0.42, (0.06, 0.2)), (0.019, 0.42, (0.08, 0.24)), (0.0085, 0.35, (0.1, 0.28))):
        cells = int(round(T / size))
        uo, vo = rng.random(2)
        f1, edge, idc, _, _ = voronoi(rng, cells, (wu + uo) % 1.0, (wv + vo) % 1.0, 0.85)
        nc = cells * cells
        on = rng.random(nc) < keep
        margin = rng.uniform(*mrg, nc)
        jag = 0.025 * noise(rng, cells * 0.5, cells * 6, 0.6)
        aa = cells / N
        cov = _s(edge - margin[idc] + jag, -0.5 * aa, 0.5 * aa) * on[idc]
        new = cov * (1 - chip)
        cls = rng.choice(len(pal), nc, p=prob)
        bright = rng.uniform(0.9, 1.08, nc)
        cc = pal[cls][idc] * bright[idc][..., None]
        cc = _mul(cc, 1.0 + 0.05 * vein)
        color = _mix(color, cc, new)
        chip = chip + new
    h = 0.00002 * chip + 0.0002 * nm(rng, 0.8, 0.2, 1.6)
    rough = 0.15 - 0.04 * chip + 0.015 * nm(rng, 0.6, 0.05, 1.2)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)


def floor_basalt(rng):
    """Honed basalt / lava stone: 0.8 x 0.4 m tiles in a running bond, fine crystalline speckle,
    sparse small vesicles, slight tone change from tile to tile."""
    px = T / N
    lu, lv, ident, du, dv = tiles(2, 4, 0.07, 0.11, bond=0.5)
    speck = nm(rng, 0.003, px, 0.2)
    light = _s(speck, 1.6, 2.6)
    darkf = _s(-speck, 1.8, 2.8)
    cloud = nm(rng, 0.8, 0.05, 1.4)
    ves = _s(nm(rng, 0.02, px * 1.2, 0.5) + 0.7 * _s(nm(rng, 0.5, 0.05, 1.3), 0.3, 1.5), 2.8, 3.3)
    trng = np.random.default_rng(rng.integers(1 << 30))
    cloud, speck, ves = tile_shuffle([cloud, speck, ves], ident, 8, trng)
    light = _s(speck, 1.6, 2.6)
    darkf = _s(-speck, 1.8, 2.8)
    shade = 1.0 + 0.07 * (trng.random(8) - 0.5) * 2
    color = _rgb((0.235, 0.232, 0.226))
    color = _mul(color, shade[ident] * (1.0 + 0.04 * cloud))
    color = _mix(color, (0.42, 0.41, 0.395), light * 0.6)
    color = _mix(color, (0.12, 0.118, 0.115), darkf * 0.6)
    color = _mix(color, (0.10, 0.098, 0.095), ves * 0.85)
    d = np.minimum(du, dv)
    hj, face = joint_profile(d, 0.0014, 0.0015, 0.0012)
    color = _mix((0.17, 0.168, 0.164), color, face)
    h = (-0.0005 * ves + 0.00002 * speck) * face + hj
    rough = 0.50 + 0.03 * cloud - 0.05 * light + 0.3 * ves
    rough = _mix(0.8, rough, face)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0008, cavity=0.15)


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


def marble_veins(rng, ang0, mains, main_w, branches, secondary, sec_w, hairs, hair_w, hair_spread,
                 main_var=1.1, sec_spread=0.5):
    """Draws a marble vein system. Returns masks: body (main vein bands), thread (darker
    braided threads inside them), sec (secondary veins), hair (hairlines)."""
    body, thread, sec, hair = Canvas(3), Canvas(3), Canvas(3), Canvas(3)
    c, s = math.cos(ang0), math.sin(ang0)
    for k in range(mains):
        # spread the main veins evenly across the bedding (perpendicular to ang0)
        o = (k + rng.uniform(0.25, 0.75)) / mains * N
        x, y = -s * o + rng.random() * N * c, c * o + rng.random() * N * s
        a0 = ang0 + rng.normal(0, 0.1)
        pts = vein_path(rng, x, y, a0, N * rng.uniform(1.3, 1.7), 4.0, 0.03)
        n = len(pts)
        w = widths(rng, n, main_w * rng.uniform(0.75, 1.25), main_var, taper=0.06)
        body.stroke(pts, w)
        for _ in range(int(rng.integers(2, 5))):
            off = w * 0.42 * wave_profile(rng, n, (3, 7, 13))
            tw = widths(rng, n, rng.uniform(0.7, 1.6), 0.7, taper=0.05) * (w > 1.0)
            thread.stroke(offset_path(pts, off), tw, value=int(rng.uniform(150, 255)))
        for _ in range(branches):
            i = int(rng.integers(n // 12, n - n // 12))
            if w[i] < 1.5:
                continue
            ba = a0 + rng.choice([-1, 1]) * rng.uniform(0.25, 0.9)
            bp = vein_path(rng, pts[i][0], pts[i][1], ba, rng.uniform(0.06, 0.35) * N, 3.0, 0.06, pull=0.03)
            m = len(bp)
            bw = np.linspace(min(w[i] * 0.55, main_w * 0.5), 0.15, m) * np.clip(1 + 0.6 * wave_profile(rng, m), 0.2, 2)
            body.stroke(bp, bw, value=int(rng.uniform(170, 240)))
            thread.stroke(bp, np.minimum(bw * 0.35, 1.2), value=200)
            if rng.random() < 0.5:                                # a twig off the branch
                j = int(rng.integers(m // 4, max(m // 4 + 1, 3 * m // 4)))
                tp = vein_path(rng, bp[j][0], bp[j][1], ba + rng.choice([-1, 1]) * rng.uniform(0.3, 0.8),
                               rng.uniform(0.03, 0.12) * N, 3.0, 0.08, pull=0.0)
                sec.stroke(tp, np.linspace(max(bw[j] * 0.5, 0.6), 0.1, len(tp)), value=200)
    for _ in range(secondary):
        a = ang0 + rng.normal(0, sec_spread)
        pts = vein_path(rng, rng.random() * N, rng.random() * N, a, rng.uniform(0.35, 1.0) * N, 3.0, 0.045)
        sec.stroke(pts, widths(rng, len(pts), sec_w * rng.uniform(0.5, 1.4), 1.2, taper=0.15),
                   value=int(rng.uniform(150, 255)))
    for _ in range(hairs):
        a = ang0 + rng.normal(0, hair_spread)
        pts = vein_path(rng, rng.random() * N, rng.random() * N, a, rng.uniform(0.1, 0.55) * N, 3.0, 0.05)
        hair.stroke(pts, widths(rng, len(pts), hair_w * rng.uniform(0.6, 1.4), 1.3, taper=0.25),
                    value=int(rng.uniform(80, 230)))
    return body.get(), thread.get(), sec.get(), hair.get()


def _wood_boards(rng, name):
    """Edge-glued boards running the full repeat along U (no butt joints, no visible glue
    line): the figure changes from board to board as in solid-wood furniture."""
    Y, bw, ident, nb = boards_v(rng, 0.09, 0.19)
    color, h, rough, late = wood_surface(rng, WOODS[name], Y, bw, ident, nb)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0002, cavity=0.05)


# --- marble ------------------------------------------------------------------
def contour_dist(f):
    """Distance (px) to the zero set of a field."""
    return np.abs(f) / np.maximum(grad_px(f), 1e-7)


def vein(d, width, soft=1.0):
    """Vein profile from a distance (px) and a width field (px)."""
    return np.exp(-(d / np.maximum(width, 0.35)) ** (2.0 * soft))


def stone_calacatta(rng):
    """Calacatta: warm white body, bold grey veins that pinch and swell with darker braided
    threads, gold staining, tapering branches and fine hairlines, a soft grey depth halo
    under the veins. Polished."""
    px = T / N
    body = _rgb((0.938, 0.930, 0.912))
    cloud = warped(rng, 0.9, 0.05, 1.5, 0.05)
    body = _mix(body, (0.885, 0.877, 0.862), _s(cloud, 0.3, 2.4) * 0.6)
    body = _mul(body, 1.0 + 0.006 * nm(rng, 0.006, px, 0.3) + 0.008 * nm(rng, 0.3, 0.03, 1.2))
    bm, th, se, ha = marble_veins(rng, ang0=0.62, mains=2, main_w=17, branches=8, secondary=7, sec_w=3.0,
                                  hairs=70, hair_w=0.8, hair_spread=0.45, main_var=0.75)
    bm = ragged(rng, bm, 1.4, 8, 90)
    se = ragged(rng, se, 0.9, 6, 60)
    th = ragged(rng, th, 0.6, 6, 60)
    gold = _s(nm(rng, 1.0, 0.1, 1.5), -0.2, 1.3)
    halo = np.clip(blur(bm, 5) * 0.55 + blur(bm, 22) * 0.45 + blur(bm, 50) * 0.5 + blur(se, 4) * 0.35
                   + blur(ha, 2) * 0.2, 0, 1)
    halo_c = _mix(_rgb((0.80, 0.79, 0.775)), (0.87, 0.79, 0.64), gold * 0.8)
    color = _mix(body, halo_c, halo * 0.6)
    mott = nm(rng, 0.03, px * 1.5, 0.8)
    vc = _mix(_rgb((0.55, 0.535, 0.52)), (0.66, 0.55, 0.38), gold * 0.7)
    vc = _mul(vc, 1.0 + 0.08 * mott)
    color = _mix(color, vc, bm * 0.82)
    color = _mix(color, _mix(_rgb((0.60, 0.585, 0.565)), (0.68, 0.59, 0.44), gold * 0.5), se * 0.8)
    color = _mix(color, _mix(_rgb((0.34, 0.32, 0.305)), (0.48, 0.38, 0.24), gold * 0.6), th * 0.85)
    color = _mix(color, (0.64, 0.63, 0.61), ha * 0.6)
    veins = np.clip(bm + se + th + ha, 0, 1)
    h = -0.000008 * veins + 0.0001 * nm(rng, 0.8, 0.2, 1.8)
    rough = 0.09 + 0.04 * veins + 0.008 * nm(rng, 0.3, 0.02, 1.0)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)


def stone_nero(rng):
    """Nero Marquina: deep black body with faint smoky clouds, crisp white calcite veins that
    branch and cross, and fine crossing hairlines. Polished."""
    px = T / N
    cloud = warped(rng, 0.8, 0.03, 1.4, 0.06)
    body = _mix(_rgb((0.040, 0.040, 0.044)), (0.070, 0.069, 0.074), _s(cloud, 0.2, 2.4))
    body = _mul(body, 1.0 + 0.03 * nm(rng, 0.005, px, 0.3))
    bm, th, se, ha = marble_veins(rng, ang0=-0.55, mains=2, main_w=4.0, branches=9, secondary=10, sec_w=1.3,
                                  hairs=100, hair_w=0.7, hair_spread=0.9, main_var=1.3, sec_spread=0.8)
    bm = ragged(rng, bm, 1.1, 6, 70)
    se = ragged(rng, se, 0.7, 6, 60)
    halo = np.clip(blur(bm, 3) * 0.5 + blur(bm, 12) * 0.35 + blur(se, 2) * 0.3, 0, 1)
    color = _mix(body, (0.16, 0.16, 0.165), halo * 0.55)
    wc = _mix(_rgb((0.86, 0.855, 0.84)), (0.70, 0.69, 0.68), _s(nm(rng, 0.03, px * 1.5, 0.7), 0.4, 2.0))
    color = _mix(color, wc, np.clip(bm * 0.85 + th * 0.4, 0, 1))
    color = _mix(color, (0.88, 0.875, 0.86), se * 0.85)
    color = _mix(color, (0.62, 0.615, 0.61), ha * 0.65)
    veins = np.clip(bm + se + ha, 0, 1)
    h = -0.000008 * veins + 0.0001 * nm(rng, 0.8, 0.2, 1.8)
    rough = 0.075 + 0.045 * veins + 0.008 * nm(rng, 0.3, 0.02, 1.0)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)


def stone_travertine(rng):
    """Classic Roman travertine slab (no joints): warmer, stronger banding, filled pores, honed."""
    color, hb, radd = travertine_body(rng, _rgb((0.835, 0.745, 0.610)), _rgb((0.660, 0.545, 0.405)),
                                      _rgb((0.80, 0.72, 0.60)), 1.0, 1.0, _rgb((0.80, 0.66, 0.48)))
    rough = 0.44 + 0.03 * nm(rng, 0.8, 0.1, 1.2) + radd
    return dict(color=color, h=hb, rough=rough, metal=0.0, depth=0.0004, cavity=0.08)


def stone_sandstone(rng):
    """Fine buff sandstone: calm granular stone with faint straight bedding, soft clouding
    and a few darker mineral grains; sawn and honed."""
    px = T / N
    wv = 0.004 * nm(rng, 1.6, 0.3, 1.6)
    lam = sample(noise(rng, 6, 300, 1.0, aniso=7), 0, wv)
    fine = sample(noise(rng, 20, N / 2, 0.7, aniso=5), 0, wv)
    grain = nm(rng, 0.003, px, 0.15)
    cloud = nm(rng, 1.2, 0.08, 1.6)
    color = _rgb((0.780, 0.662, 0.498))
    color = _mix(color, (0.825, 0.725, 0.575), _s(cloud, -0.3, 1.8) * 0.45)
    color = _mix(color, (0.745, 0.60, 0.43), _s(nm(rng, 0.9, 0.08, 1.5), 0.8, 2.4) * 0.3)     # iron clouding
    color = _mul(color, 1.0 + 0.02 * lam + 0.01 * fine + 0.03 * grain)
    color = _mix(color, (0.45, 0.38, 0.30), _s(grain, 2.7, 3.5) * 0.5)                      # dark grains
    h = 0.00001 * lam + 0.00004 * grain + 0.0002 * nm(rng, 0.6, 0.1, 1.6)
    rough = 0.80 + 0.03 * grain - 0.01 * lam
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0002, cavity=0.05)


def fabric_boucle(rng):
    """Boucle: round yarn loops and curls (4-6 mm) standing on a dense nubby ground of soft
    ivory yarn."""
    px = T / N
    yarn = 0.00055
    ground = 0.00035 * _s(nm(rng, 0.006, px * 2, 0.7), -1.5, 1.5)
    h = ground.copy()
    tone = np.zeros((N, N))
    for cells, hs in ((62, 1.0), (74, 0.9), (54, 1.05)):
        uo, vo = rng.random(2)
        wu = (U + uo + 0.001 * noise(rng, 4, 60, 1.2)) % 1.0
        wv = (V + vo + 0.001 * noise(rng, 4, 60, 1.2)) % 1.0
        _, _, idc, ru, rv = voronoi(rng, cells, wu, wv, 0.6)
        nc = cells * cells
        cell_m = T / cells
        r0 = rng.uniform(0.22, 0.31, nc)
        ratio = rng.uniform(0.7, 1.0, nc)
        th = rng.uniform(0, math.pi, nc)
        cut = rng.uniform(-1.0, -0.1, nc)
        phi = rng.uniform(0, 2 * math.pi, nc)
        hh = rng.uniform(0.7, 1.0, nc) * hs * (rng.random(nc) < 0.8)
        tn = rng.normal(0, 1, nc)
        c, s = np.cos(th)[idc], np.sin(th)[idc]
        a = ru * c + rv * s
        b = (-ru * s + rv * c) / ratio[idc]
        rho = np.sqrt(a * a + b * b)
        prof = np.sqrt(np.clip(1 - ((rho - r0[idc]) / (yarn / cell_m)) ** 2, 0, 1))
        ang = np.arctan2(b, a)
        arc = _s(np.cos(ang - phi[idc]) - cut[idc], 0.0, 0.6)
        lh = prof * arc * hh[idc] * 0.0011 * (0.7 + 0.3 * np.cos(ang - phi[idc])) + 0.0004 * prof * arc * hh[idc]
        m = lh > h
        tone = np.where(m, tn[idc], tone)
        h = np.maximum(h, lh)
    h = blur(h, 0.45)
    fuzz = nm(rng, 0.004, px * 1.5, 0.3)
    hn = _s(h, 0.0002, 0.0013)
    color = _rgb((0.895, 0.870, 0.820))
    color = _mul(color, 0.88 + 0.12 * hn + 0.012 * tone + 0.008 * fuzz)
    color = _mix(color, (0.85, 0.80, 0.71), _s(nm(rng, 0.05, 0.004, 1.0), 1.0, 2.2) * 0.3)   # oatmeal fleck
    rough = 0.93 - 0.03 * hn + 0.015 * fuzz
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0012, cavity=0.2)


def fabric_linen(rng):
    """Heavy upholstery linen: plain weave, 256 x 256 threads per 0.5 m (1.95 mm), slubs,
    heathered flax colour."""
    threads = 256
    gx = (U + 0.0006 * noise(rng, 2, 40, 1.2)) * threads
    gy = (V + 0.0006 * noise(rng, 2, 40, 1.2)) * threads
    slub_u = 1.0 + 0.22 * _s(noise(rng, 20, N / 2, 0.5, aniso=12, ang=math.pi / 2), 0.5, 2.5) \
        - 0.08 * _s(-noise(rng, 20, N / 2, 0.5, aniso=12, ang=math.pi / 2), 1.0, 2.5)
    slub_v = 1.0 + 0.22 * _s(noise(rng, 20, N / 2, 0.5, aniso=12), 0.5, 2.5) \
        - 0.08 * _s(-noise(rng, 20, N / 2, 0.5, aniso=12), 1.0, 2.5)
    si, sj = rng.random(threads), rng.random(threads)
    i = np.floor(gx).astype(np.int64)
    j = np.floor(gy).astype(np.int64)
    fx, fy = gx - i, gy - j
    over = ((i + j) % 2) == 0
    wu_ = np.clip((0.72 + 0.25 * si[i % threads]) * slub_u, 0.45, 1.0)
    wv_ = np.clip((0.72 + 0.25 * sj[j % threads]) * slub_v, 0.45, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / wu_) ** 2, 0.0, 1.0))
    cvv = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / wv_) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    h_warp = cu * (0.55 + 0.45 * np.where(over, ou, -ou)) * slub_u
    h_weft = cvv * (0.55 + 0.45 * np.where(over, -ov, ov)) * slub_v
    top = h_warp > h_weft
    hh = np.maximum(h_warp, h_weft)
    tone_t = np.where(top, si[i % threads], sj[j % threads]) - 0.5
    slub = np.where(top, slub_u, slub_v) - 1.0
    fibre = noise(rng, 60, N / 2, 0.3)
    color = _rgb((0.865, 0.830, 0.765))
    color = _mul(color, 1.0 + 0.07 * tone_t + 0.25 * slub + 0.015 * fibre)
    color = _mix(color, (0.80, 0.75, 0.67), _s(nm(rng, 0.3, 0.02, 1.2, aniso=3), 0.8, 2.2) * 0.3)
    color = _mul(color, 0.84 + 0.16 * hh)
    h = 0.00022 * hh + 0.00001 * fibre
    rough = 0.86 - 0.04 * hh + 0.02 * fibre
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0002, cavity=0.15)


def fabric_velvet(rng):
    """Velvet: almost no relief, the look is in the pile: soft clouds where the pile lies a
    little differently read lighter/glossier or darker/matte (roughness ~0.6-0.9)."""
    px = T / N
    lay = 0.7 * warped(rng, 0.2, 0.02, 1.6, 0.05) + 0.5 * nm(rng, 0.5, 0.08, 1.5)
    lay = (lay - lay.mean()) / lay.std()
    brush = np.zeros((N, N))
    for _ in range(4):
        ang = rng.uniform(0, math.pi)
        plate = _s(nm(rng, 0.25, 0.03, 1.6, aniso=2.0, ang=ang), rng.uniform(-0.5, 0.8), 1.6)
        brush = brush + (nm(rng, 0.04, 0.003, 0.7, aniso=6, ang=ang) - brush) * plate * 0.6
    pile = nm(rng, 0.003, px, 0.2)
    color = _rgb((0.805, 0.785, 0.755))
    color = _mul(color, 1.0 + 0.028 * lay + 0.005 * brush + 0.01 * pile)
    h = 0.00001 * brush + 0.000015 * lay + 0.000008 * pile
    rough = np.clip(0.75 - 0.07 * lay - 0.015 * brush + 0.015 * pile, 0.58, 0.92)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0001, cavity=0.0)


def fabric_wool(rng):
    """Knitted wool, stockinette: 64 wales x 80 courses per 0.5 m (7.8 x 6.25 mm stitches),
    plied yarn with a soft woollen halo."""
    wales, courses = 64, 80
    gx = (U + 0.0008 * noise(rng, 2, 30, 1.3)) * wales
    gy = (V + 0.0008 * noise(rng, 2, 30, 1.3)) * courses
    i = np.floor(gx)
    x = gx - i - 0.5                              # -0.5..0.5 across the wale
    W, H = T / wales, T / courses
    hmax = np.zeros((N, N))
    ply = np.zeros((N, N))
    tone = rng.normal(0, 1, (courses + 2, wales))
    sid = np.zeros((N, N))
    for dj in (-1, 0, 1):
        j = np.floor(gy) + dj
        y = (gy - j)                              # 0..1 down the course (may extend beyond)
        for side in (-1, 1):
            # Leg from the top outer corner (side*0.42, -0.15) to the bottom centre (side*0.04, 1.05).
            ax, ay = side * 0.40, -0.18
            bx, by = side * 0.03, 1.08
            px_, py_ = (x - ax) * W, (y - ay) * H
            vx, vy = (bx - ax) * W, (by - ay) * H
            L2 = vx * vx + vy * vy
            t = np.clip((px_ * vx + py_ * vy) / L2, 0, 1)
            dx, dy = px_ - t * vx, py_ - t * vy
            dist = np.sqrt(dx * dx + dy * dy)
            r = 0.30 * W
            prof = np.sqrt(np.clip(1 - (dist / r) ** 2, 0, 1))
            hh = prof * (0.55 + 0.45 * np.sin(math.pi * t) ** 0.7) * r * 0.9
            along = t * math.sqrt(L2)
            across = (dx * vy - dy * vx) / math.sqrt(L2)
            tw = np.sin(2 * math.pi * (along / 0.0028 + side * across / 0.0035))
            m = hh > hmax
            ply = np.where(m, tw, ply)
            sid = np.where(m, tone[(j.astype(np.int64) + 1) % courses, i.astype(np.int64) % wales], sid)
            hmax = np.maximum(hmax, hh)
    fuzz = noise(rng, 80, N / 2, 0.3)
    halo = nm(rng, 0.01, 0.001, 0.8)
    hn = hmax / (0.30 * W * 0.9)
    color = _rgb((0.875, 0.845, 0.785))
    color = _mul(color, (0.72 + 0.28 * hn) * (1.0 + 0.04 * ply * hn + 0.015 * sid + 0.02 * fuzz + 0.01 * halo))
    h = hmax + 0.00012 * ply * hn + 0.00004 * fuzz
    rough = 0.92 + 0.02 * fuzz
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=0.0015, cavity=0.15)


# --- metal ---------------------------------------------------------------------
def brushed(rng, col, rough0, rvar, depth, tone=0.02):
    """Brushed (satin) metal: fine streaks along U in the normal, roughness and colour."""
    s1 = noise(rng, 3, N / 2, 0.25, aniso=160)
    s2 = noise(rng, 30, N / 2, 0.15, aniso=60)
    lines = _s(noise(rng, 40, N / 2, 0.1, aniso=320), 2.0, 3.2)
    low = nm(rng, 1.0, 0.15, 1.5)
    color = _mul(_rgb(col), 1.0 + tone * (0.6 * s1 + 0.4 * s2) - 0.03 * lines + 0.012 * low)
    h = depth * (0.6 * s1 + 0.4 * s2) - 1.5 * depth * lines
    rough = rough0 + rvar * (0.6 * s1 + 0.4 * s2) + 0.04 * lines + 0.01 * low
    return dict(color=color, h=h, rough=rough, metal=1.0, depth=None, cavity=0.0)


def metal_brass(rng):
    return brushed(rng, (0.835, 0.690, 0.430), 0.30, 0.035, 0.00002)


def metal_bronze(rng):
    return brushed(rng, (0.800, 0.705, 0.570), 0.34, 0.03, 0.000015)


def metal_black(rng):
    return brushed(rng, (0.215, 0.210, 0.205), 0.42, 0.04, 0.000015, tone=0.04)


def metal_chrome(rng):
    """Polished chrome / stainless: near-perfect mirror, the faintest polishing swirls."""
    px = T / N
    sw = nm(rng, 0.05, px * 2, 0.6, aniso=3, ang=rng.uniform(0, math.pi))
    color = _mul(_rgb((0.815, 0.815, 0.825)), 1.0 + 0.004 * sw + 0.004 * nm(rng, 1.0, 0.2, 1.5))
    h = 0.000002 * sw
    rough = 0.06 + 0.012 * sw
    return dict(color=color, h=h, rough=rough, metal=1.0, depth=None, cavity=0.0)


# --- glass ---------------------------------------------------------------------
def glass_plain(col):
    def gen(rng):
        color = _mul(_rgb(col), 1.0 + 0.004 * nm(rng, 1.5, 0.3, 1.5))
        return dict(color=color, h=np.zeros((N, N)), rough=np.full((N, N), 0.03), metal=0.0, depth=None,
                    cavity=0.0)
    return gen


def glass_fluted(rng):
    """Frosted reeded glass: vertical flutes of 25 mm (80 per 2 m), convex, acid-etched."""
    px = T / N
    flutes = 80
    x = (U * flutes + 0.5) % 1.0
    xc = (x - 0.5) * 2                                        # -1..1 across a flute
    h = 0.0035 * np.sqrt(np.clip(1 - xc ** 2 * 0.92, 0, 1))   # rounded reeds, crisp valleys
    frost = nm(rng, 0.01, px * 1.5, 0.4)
    color = _mul(_rgb((0.925, 0.940, 0.940)), 1.0 + 0.04 * (h / 0.0035 - 0.7) + 0.006 * frost)
    rough = 0.38 + 0.03 * frost - 0.06 * _s(np.abs(xc), 0.8, 1.0)
    return dict(color=color, h=h, rough=rough, metal=0.0, depth=None, cavity=0.0)


def glow_led(rng):
    px = T / N
    f = nm(rng, 0.01, px * 2, 0.4)
    cl = nm(rng, 1.0, 0.1, 1.5)
    color = _mul(_rgb((0.975, 0.960, 0.930)), 1.0 + 0.004 * f)
    em = _mul(_rgb((1.0, 0.885, 0.735)), 1.0 + 0.012 * cl + 0.006 * f)
    return dict(color=color, h=0.000004 * f, rough=0.32 + 0.02 * f, metal=0.0, depth=None, cavity=0.0,
                emissive=np.clip(em, 0, 1))


def glow_white(rng):
    px = T / N
    f = nm(rng, 0.01, px * 2, 0.4)
    color = _mul(_rgb((0.97, 0.97, 0.97)), 1.0 + 0.003 * f)
    return dict(color=color, h=0.000003 * f, rough=0.30 + 0.02 * f, metal=0.0, depth=None, cavity=0.0,
                emissive=_rgb((1.0, 1.0, 1.0)))


def glow_opal(rng):
    """Opal (milk) lamp glass: glossy, softly graded luminous clouds."""
    cl = warped(rng, 0.8, 0.05, 1.6, 0.06)
    g = _s(cl, -2.6, 2.6)
    color = _mix(_rgb((0.955, 0.945, 0.925)), (0.985, 0.975, 0.96), g)
    em = _mix(_rgb((0.93, 0.80, 0.63)), (1.0, 0.905, 0.77), g)
    return dict(color=color, h=0.0001 * nm(rng, 0.5, 0.1, 1.5), rough=0.12 + 0.02 * g, metal=0.0,
                depth=None, cavity=0.0, emissive=em)


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
        dict(id="white", label="White microcement", gen=plaster_white),
        dict(id="sand", label="Sand lime plaster", gen=plaster_sand),
        dict(id="concrete", label="Soft concrete", gen=plaster_concrete),
        dict(id="charcoal", label="Charcoal microcement", gen=plaster_charcoal),
    ],
    "b_floor": [
        dict(id="travertine", label="Travertine tiles", gen=floor_travertine),
        dict(id="oak", label="Smoked oak planks", gen=floor_oak),
        dict(id="terrazzo", label="Warm terrazzo", gen=floor_terrazzo),
        dict(id="basalt", label="Honed basalt", gen=floor_basalt),
    ],
    "c_wood": [
        dict(id="walnut", label="Walnut", gen=wood_species("walnut")),
        dict(id="oak", label="Natural oak", gen=wood_species("oak")),
        dict(id="teak", label="Teak", gen=wood_species("teak")),
        dict(id="ebony", label="Ebonised ash", gen=wood_species("ebony")),
    ],
    "d_stone": [
        dict(id="calacatta", label="Calacatta gold", gen=stone_calacatta),
        dict(id="travertine", label="Roman travertine", gen=stone_travertine),
        dict(id="nero", label="Nero Marquina", gen=stone_nero),
        dict(id="sandstone", label="Sandstone", gen=stone_sandstone),
    ],
    "e_fabric": [
        dict(id="boucle", label="Boucle", gen=fabric_boucle),
        dict(id="linen", label="Linen", gen=fabric_linen),
        dict(id="velvet", label="Velvet", gen=fabric_velvet),
        dict(id="wool", label="Knitted wool", gen=fabric_wool),
    ],
    "f_metal": [
        dict(id="brass", label="Brushed brass", gen=metal_brass),
        dict(id="bronze", label="Champagne bronze", gen=metal_bronze),
        dict(id="black", label="Satin black steel", gen=metal_black),
        dict(id="chrome", label="Polished chrome", gen=metal_chrome),
    ],
    "g_glass": [
        dict(id="clear", label="Clear glass", gen=glass_plain((0.94, 0.965, 0.965)), alpha=0.15, res=512),
        dict(id="smoked", label="Smoked grey", gen=glass_plain((0.30, 0.31, 0.315)), alpha=0.5, res=512),
        dict(id="bronze", label="Bronze tint", gen=glass_plain((0.52, 0.40, 0.27)), alpha=0.45, res=512),
        dict(id="fluted", label="Fluted frosted", gen=glass_fluted, alpha=0.72),
    ],
    "h_glow": [
        dict(id="led", label="Warm LED", gen=glow_led, res=512),
        dict(id="opal", label="Opal glass", gen=glow_opal, res=512),
        dict(id="ember", label="Ember bed", gen=glow_ember),
        dict(id="white", label="White light (tint)", gen=glow_white, res=512),
    ],
    "water": [
        dict(id="turquoise", label="Tropical turquoise", gen=water_gen((0.36, 0.80, 0.80), (0.20, 0.66, 0.72), 1.0, 0.07),
             alpha=0.62, double=True),
        dict(id="lagoon", label="Deep lagoon", gen=water_gen((0.10, 0.36, 0.52), (0.06, 0.25, 0.42), 1.0, 0.045),
             alpha=0.70, double=True),
        dict(id="infinity", label="Black mirror", gen=water_gen((0.035, 0.050, 0.060), (0.025, 0.035, 0.045), 0.5, 0.0),
             alpha=0.75, double=True),
    ],
}
DEFAULT = {"a_plaster": "white", "b_floor": "travertine", "c_wood": "walnut", "d_stone": "calacatta",
           "e_fabric": "boucle", "f_metal": "brass", "g_glass": "clear", "h_glow": "led", "water": "turquoise"}


def entries():
    for slot in SLOTS:
        for v in LIB[slot]:
            yield slot, v


def mat_name(slot, vid):
    return f"villa_{slot}_{vid}"


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
        "asset": {"version": "2.0", "generator": "The Villa - vtextures.py"},
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


def build(job):
    slot, k = job
    v = LIB[slot][k]
    vid = v["id"]
    name = mat_name(slot, vid)
    res = v.get("res", 1024)
    t0 = time.time()
    set_res(res, UV_TILE[slot])
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
    maps = {
        "basecolor": _u8(color),
        "normal": _u8(nrm * 0.5 + 0.5),
        "orm": _u8(np.stack([ao, np.clip(rough, 0.02, 1.0), np.clip(metal, 0, 1)], -1)),
    }
    if out.get("emissive") is not None:
        maps["emissive"] = _u8(out["emissive"])
    stem = f"{slot}__{vid}"
    pngs = {}
    for kind, img in maps.items():
        pngs[kind] = png_bytes(img)
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
                bytes=sum(len(p) for p in pngs.values()), glb_bytes=os.path.getsize(glb), stats=stats)


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
    d.text((pad, pad - 6), "THE VILLA  -  PBR material library", fill=(236, 226, 208), font=_font(26, True))
    d.text((pad, pad + 28), "Swatch = one full repeat, softly lit. Glass and water shown over a checker at their alpha.",
           fill=(150, 142, 130), font=_font(14))
    y = pad + 64
    by_slot = {}
    for r in results:
        by_slot.setdefault(r["slot"], []).append(r)
    for slot in rows:
        d.text((pad, y + 6), slot, fill=(214, 180, 120), font=_font(17, True))
        d.text((pad + 120, y + 9), f"{UV_TILE[slot]:g} m per repeat", fill=(140, 132, 120), font=_font(13))
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
    have_glb = {f for f in os.listdir(GLB_DIR) if f.startswith("villa_") and f.endswith(".glb")}
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
    todo = [(s, v) for s, v in entries() if not filters or any(f in f"{s}__{v['id']}" for f in filters)]
    if not filters:      # full run: clear stale outputs of this script first
        for f in os.listdir(GLB_DIR):
            if f.startswith("villa_") and f.endswith(".glb"):
                os.remove(os.path.join(GLB_DIR, f))
        for f in os.listdir(TEX_DIR):
            if "__" in f and f.endswith(".png"):
                os.remove(os.path.join(TEX_DIR, f))
    # biggest jobs first so the pool finishes together
    order = sorted(todo, key=lambda j: -(j[1].get("res", 1024)))
    order = [(s, LIB[s].index(v)) for s, v in order]
    with Pool(min(jobs, len(order))) as pool:
        done = pool.map(build, order, chunksize=1)
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
    if not filters:
        swatches(os.path.join(TEX_DIR, "_swatches.png"), results)
        cat = write_catalogue(results)
        cerr = check_catalogue(cat)
        if cerr:
            failures.append(("catalogue", cerr, {}))
    tex_mb = sum(os.path.getsize(os.path.join(TEX_DIR, f)) for f in os.listdir(TEX_DIR)) / 1e6
    glb_mb = sum(os.path.getsize(os.path.join(GLB_DIR, f)) for f in os.listdir(GLB_DIR)) / 1e6
    print(f"{len(results)} variants. textures {tex_mb:.1f} MB in {TEX_DIR}\n"
          f"glTF materials {glb_mb:.1f} MB in {GLB_DIR}\ncatalogue {CATALOGUE}\nTotal {time.time() - t0:.1f} s")
    if failures:
        print("FAILURES:")
        for f in failures:
            print("  ", f)
        sys.exit(1)


if __name__ == "__main__":
    main()

"""Procedural PBR textures for The Pit (tileable, seamless).

Using only numpy + pillow, generates one PBR set per material:

  output/textures/<Material>_basecolor.png   sRGB
  output/textures/<Material>_normal.png      glTF (OpenGL, +Y up)
  output/textures/<Material>_orm.png         glTF (R occlusion, G roughness, B metallic)
  output/textures/_swatches.png              contact sheet with the 8 basecolor maps
  output/pbr_materials/<Material>.glb        glTF 2.0 material (with a quad) for the
                                             Second Life PBR material uploader

V4 look: "majestic but filthy, dark but full of information". Every repeat carries
small stories that only read at close range (tally marks and initials scratched into
a few wall blocks, rust running from an old iron staple, wax dripped from a guard's
candle, nail heads bleeding black into the oak, bright iron where a chain has rubbed,
a darned shirt, a scrimshaw ship on a bone, rat droppings in the straw...) while the
large-scale variation is kept even so that no single feature marks the repeat grid.

All the noise lives on a torus: white noise filtered in frequency with an FFT,
Voronoi with wrapped neighbours and periodic offsets, and every drawn feature is
drawn with copies one repeat away (or evaluated in wrapped pixel windows). So every
image matches edge to edge by construction (and this is checked numerically at the
end). The physical scale follows geo.UV_TILE: one repeat of Stone is 2 m, of Iron
0.5 m, etc., and the relief is computed in real metres so the normals come out
with the correct slope.

Note on vertical gradients: the build maps textures in world space (v = z / UV_TILE),
so anything tied to the image height repeats every repeat up a wall (a "bottom" band
on Stone would show again at 2.4 m, 4.4 m...). Salt and damp are therefore tied to the
joints and to the lower edge of every block, not to the image height.

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


def _mul(color, f):
    """Multiplies an RGB image by a scalar field."""
    return color * np.asarray(f, dtype=float)[..., None]


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


def sample(field, du, dv):
    """Bilinear periodic lookup of `field` at (U + du, V + dv) (offsets in repeats)."""
    x = (U + du) * N - 0.5
    y = (V + dv) * N - 0.5
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = x - x0, y - y0
    x0, y0 = x0 % N, y0 % N
    x1, y1 = (x0 + 1) % N, (y0 + 1) % N
    return ((field[y0, x0] * (1 - fx) + field[y0, x1] * fx) * (1 - fy)
            + (field[y1, x0] * (1 - fx) + field[y1, x1] * fx) * fy)


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


def window(cx, cy, rx, ry=None):
    """Wrapped pixel window around (cx, cy) (pixel units, pixel i has its centre at i + 0.5).

    Returns an index usable on any N x N array and the offsets dx (1 x w) and dy (h x 1)
    of every pixel centre from (cx, cy). Local features evaluated here tile for free."""
    ry = rx if ry is None else ry
    x0, x1 = int(math.floor(cx - rx)), int(math.ceil(cx + rx)) + 1
    y0, y1 = int(math.floor(cy - ry)), int(math.ceil(cy + ry)) + 1
    xs, ys = np.arange(x0, x1), np.arange(y0, y1)
    return np.ix_(ys % N, xs % N), (xs + 0.5 - cx)[None, :], (ys + 0.5 - cy)[:, None]


def stamp_max(dst, idx, val):
    dst[idx] = np.maximum(dst[idx], val)


class Canvas:
    """Anti-aliased drawing on the torus.

    Shapes are drawn at `ss` x resolution together with their copies one repeat away,
    then box-filtered down to N x N, so the result is a seamless 0..1 coverage mask.
    Coordinates are in output pixels."""

    def __init__(self, ss=4):
        self.ss = ss
        self.im = Image.new("L", (N * ss, N * ss), 0)
        self.d = ImageDraw.Draw(self.im)

    @staticmethod
    def _offsets(xs, ys, pad):
        for ox in (-N, 0, N):
            if max(xs) + ox < -pad or min(xs) + ox > N + pad:
                continue
            for oy in (-N, 0, N):
                if max(ys) + oy < -pad or min(ys) + oy > N + pad:
                    continue
                yield ox, oy

    def line(self, pts, width, value=255):
        s = self.ss
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        w = max(1, int(round(width * s)))
        r = width * s / 2.0
        for ox, oy in self._offsets(xs, ys, width + 2):
            q = [((x + ox) * s, (y + oy) * s) for x, y in pts]
            self.d.line(q, fill=value, width=w, joint="curve")
            if r >= 1.0:
                for x, y in (q[0], q[-1]):
                    self.d.ellipse([x - r, y - r, x + r, y + r], fill=value)

    def taper(self, pts, w0, w1, value=255, steps=4):
        """Polyline whose width goes from w0 to w1 (a scratch that starts deep and fades)."""
        seg = len(pts) - 1
        for i in range(seg):
            (xa, ya), (xb, yb) = pts[i], pts[i + 1]
            for k in range(steps):
                a, b = k / steps, (k + 1) / steps
                w = w0 + (w1 - w0) * (i + (a + b) / 2) / seg
                self.line([(xa + (xb - xa) * a, ya + (yb - ya) * a), (xa + (xb - xa) * b, ya + (yb - ya) * b)],
                          w, value)

    def polygon(self, pts, value=255):
        s = self.ss
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ox, oy in self._offsets(xs, ys, 2):
            self.d.polygon([((x + ox) * s, (y + oy) * s) for x, y in pts], fill=value)

    def ellipse(self, cx, cy, rx, ry, ang=0.0, value=255, n=20):
        c, s_ = math.cos(ang), math.sin(ang)
        pts = [(cx + rx * math.cos(a) * c - ry * math.sin(a) * s_, cy + rx * math.cos(a) * s_ + ry * math.sin(a) * c)
               for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]
        self.polygon(pts, value)

    def get(self):
        return np.asarray(self.im.resize((N, N), Image.BOX), dtype=float) / 255.0


# Single-stroke letters for scratched graffiti (x 0..1 across, y 0..1 downwards).
_O = [(0.5 + 0.5 * math.sin(a), 0.5 - 0.5 * math.cos(a)) for a in np.linspace(0, 2 * math.pi, 13)]
FONT = {
    "A": [[(0, 1), (0.5, 0), (1, 1)], [(0.22, 0.6), (0.78, 0.6)]],
    "C": [[(1, 0.12), (0.7, 0), (0.3, 0), (0, 0.25), (0, 0.75), (0.3, 1), (0.7, 1), (1, 0.88)]],
    "D": [[(0, 0), (0, 1), (0.55, 1), (1, 0.7), (1, 0.3), (0.55, 0), (0, 0)]],
    "E": [[(1, 0), (0, 0), (0, 1), (1, 1)], [(0, 0.5), (0.75, 0.5)]],
    "H": [[(0, 0), (0, 1)], [(1, 0), (1, 1)], [(0, 0.5), (1, 0.5)]],
    "I": [[(0.5, 0), (0.5, 1)]],
    "J": [[(1, 0), (1, 0.75), (0.75, 1), (0.25, 1), (0, 0.75)]],
    "K": [[(0, 0), (0, 1)], [(1, 0), (0, 0.6)], [(0.3, 0.42), (1, 1)]],
    "M": [[(0, 1), (0, 0), (0.5, 0.6), (1, 0), (1, 1)]],
    "N": [[(0, 1), (0, 0), (1, 1), (1, 0)]],
    "O": [_O],
    "P": [[(0, 1), (0, 0), (0.75, 0), (1, 0.15), (1, 0.38), (0.75, 0.52), (0, 0.52)]],
    "R": [[(0, 1), (0, 0), (0.75, 0), (1, 0.15), (1, 0.38), (0.75, 0.52), (0, 0.52)], [(0.4, 0.52), (1, 1)]],
    "S": [[(1, 0.12), (0.75, 0), (0.25, 0), (0, 0.18), (0, 0.35), (0.25, 0.5), (0.75, 0.5), (1, 0.65), (1, 0.85),
           (0.75, 1), (0.25, 1), (0, 0.88)]],
    "T": [[(0, 0), (1, 0)], [(0.5, 0), (0.5, 1)]],
    "W": [[(0, 0), (0.25, 1), (0.5, 0.35), (0.75, 1), (1, 0)]],
    "X": [[(0, 0), (1, 1)], [(1, 0), (0, 1)]],
    "0": [_O],
    "1": [[(0.2, 0.25), (0.6, 0), (0.6, 1)]],
    "2": [[(0, 0.22), (0.25, 0), (0.75, 0), (1, 0.22), (0.9, 0.45), (0, 1), (1, 1)]],
    "6": [[(0.85, 0.05), (0.45, 0), (0.1, 0.25), (0, 0.65), (0.15, 0.95), (0.5, 1), (0.85, 0.85), (0.95, 0.65),
           (0.75, 0.48), (0.4, 0.47), (0.1, 0.6)]],
    "7": [[(0, 0), (1, 0), (0.35, 1)]],
    "8": [[(0.5, 0.5), (0.15, 0.38), (0.1, 0.12), (0.5, 0), (0.9, 0.12), (0.85, 0.38), (0.5, 0.5), (0.05, 0.68),
           (0.1, 0.92), (0.5, 1), (0.9, 0.92), (0.95, 0.68), (0.5, 0.5)]],
    "9": [[(0.9, 0.4), (0.6, 0.52), (0.2, 0.48), (0, 0.28), (0.15, 0.05), (0.5, 0), (0.85, 0.1), (0.95, 0.4),
           (0.8, 0.75), (0.45, 1)]],
    ".": [[(0.4, 0.9), (0.6, 1.0)]],
    "+": [[(0.5, 0), (0.5, 1)], [(0.1, 0.3), (0.9, 0.3)]],
}


def scratch_text(cv, rng, text, x, y, height, width, slant=0.12, jitter=0.05):
    """Scratches `text` (single strokes, hand-wobbled) with its top-left corner at (x, y) px."""
    cw = 0.62 * height
    cx = x
    for ch in text:
        if ch == " ":
            cx += 0.55 * height
            continue
        for pl in FONT[ch]:
            pts = [(cx + px * cw + (1 - py) * slant * height + rng.normal(0, jitter * height),
                    y + py * height + rng.normal(0, jitter * height)) for px, py in pl]
            cv.line(pts, width)
        cx += (0.45 if ch == "." else 0.9) * height


def tally(cv, rng, x, y, count, height, width, pitch, group_gap, row_gap=None):
    """Prison tally marks in groups of five (four strokes and a diagonal), rows of 4 groups."""
    row_gap = row_gap or height * 1.35
    gx, gy = x, y
    for g0 in range(0, count, 5):
        n = min(5, count - g0)
        xs = []
        for k in range(min(n, 4)):
            lean = rng.normal(0.05, 0.05) * height
            xa = gx + k * pitch + rng.normal(0, 0.06 * pitch)
            ya = gy + rng.normal(0, 0.06 * height)
            cv.taper([(xa + lean, ya), (xa, ya + height * rng.uniform(0.9, 1.05))], width * 1.1, width * 0.7)
            xs.append(xa)
        if n == 5:
            cv.taper([(xs[0] - 0.35 * pitch, gy + 0.78 * height), (xs[-1] + 0.45 * pitch, gy + 0.18 * height)],
                     width * 1.1, width * 0.7)
        gx += 4 * pitch + group_gap
        if (g0 // 5) % 4 == 3:
            gx, gy = x, gy + row_gap


def random_walk(rng, x, y, ang, step, n, turn):
    pts = [(x, y)]
    for _ in range(n):
        ang += rng.normal(0, turn)
        x += math.cos(ang) * step
        y += math.sin(ang) * step
        pts.append((x, y))
    return pts


def ashlar(rng, u, v, ncourses, wmin, wmax, hvar=0.12):
    """Coursed blocks on the torus. Returns per-pixel local coordinates (repeat units):
    lx, ly from the block's left/top edge, bw, bh block size, ident, plus the block list."""
    heights = rng.uniform(1 - hvar, 1 + hvar, ncourses)
    ce = np.concatenate([[0.0], np.cumsum(heights / heights.sum())])
    course = np.clip(np.searchsorted(ce, v, side="right") - 1, 0, ncourses - 1)
    lx, ly, bw, bh = (np.zeros_like(u) for _ in range(4))
    ident = np.zeros(u.shape, np.int32)
    blocks = []
    for r in range(ncourses):
        widths = []
        while sum(widths) < 1.0 - 0.5 * (wmin + wmax) * 0.2:
            widths.append(rng.uniform(wmin, wmax))
        widths = np.array(widths) / sum(widths)
        bx = np.concatenate([[0.0], np.cumsum(widths)])
        off = rng.random()
        m = course == r
        xs = (u[m] - off) % 1.0
        k = np.clip(np.searchsorted(bx, xs, side="right") - 1, 0, len(widths) - 1)
        lx[m] = xs - bx[k]
        bw[m] = widths[k]
        ly[m] = v[m] - ce[r]
        bh[m] = ce[r + 1] - ce[r]
        ident[m] = r * 16 + k
        for kk in range(len(widths)):
            blocks.append({"id": r * 16 + kk, "u0": (off + bx[kk]) % 1.0, "w": widths[kk],
                           "v0": ce[r], "h": ce[r + 1] - ce[r]})
    return lx, ly, bw, bh, ident, blocks


def _hash(i, j=0):
    """Deterministic pseudo-random value in [0, 1) for integer arrays."""
    x = np.sin(np.asarray(i, dtype=float) * 12.9898 + np.asarray(j, dtype=float) * 78.233) * 43758.5453
    return x - np.floor(x)


# ---------------------------------------------------------------------------
# Materials. Each one returns sRGB colour (0..1), height in metres, roughness,
# metallic and the typical depth (m) for the occlusion.
# ---------------------------------------------------------------------------
def stone(rng):
    """Dressed ashlar of a sea fortress: tooled faces with drafted margins, worn and
    chipped arrises, lime mortar eaten by salt, salt blooms along the foot of the blocks,
    green-black seepage running down from the joints, soot, an old iron staple bleeding
    rust, and prisoners' scratches (a tally of days, initials, a gallows) on a few blocks."""
    t = UV_TILE["Stone"]                          # 2 m per repeat, ~2 mm per pixel
    u = (U + 0.003 * noise(rng, 2, 24, 1.3)) % 1.0
    v = (V + 0.003 * noise(rng, 2, 24, 1.3)) % 1.0
    lx, ly, bw, bh, ident, blocks = ashlar(rng, u, v, 5, 0.25, 0.42)
    lx, ly, bw, bh = lx * t, ly * t, bw * t, bh * t           # metres
    table = rng.random((5 * 16, 12))
    # Block palette spread evenly over the repeat, so no course or corner reads as one colour.
    nb = len(blocks)
    order = rng.permutation(nb)
    light, ochre, cold, dark = (np.zeros(5 * 16) for _ in range(4))
    for k, b in enumerate(blocks):
        light[b["id"]] = (order[k] + rng.uniform(0.2, 0.8)) / nb
        ochre[b["id"]] = (order[k] * 0.618 + 0.37) % 1.0
    picks = rng.permutation(nb)
    used_rows = set()
    n_cold = 0
    for k in picks:
        b = blocks[k]
        if b["v0"] in used_rows:
            continue
        used_rows.add(b["v0"])
        if n_cold < 2:
            cold[b["id"]] = 1.0
            n_cold += 1
        else:
            dark[b["id"]] = 1.0
            break

    dx = np.minimum(lx, bw - lx)
    dy = np.minimum(ly, bh - ly)
    dist = dx * dy / np.sqrt(dx * dx + dy * dy + 1e-12)        # rounded corners
    corner = _s(0.12 - np.sqrt(dx * dx + dy * dy), 0.0, 0.07)
    near = _s(0.08 - dist, 0.0, 0.05)
    spall = _s(noise(rng, 4, 40, 1.1) + 0.9 * corner, 1.35, 1.7) * near
    dm = dist + 0.004 * noise(rng, 8, 120, 0.9) - 0.018 * spall
    joint = 0.0095 + 0.0025 * noise(rng, 3, 40, 1.0)
    bevel = 0.014 + 0.014 * _s(noise(rng, 3, 40, 1.0), -1.5, 1.5)
    profile = _rounded((dm - joint) / bevel)
    is_block = _s(dm - joint, -0.0015, 0.003)

    # Face: drafted margin (smooth band along the arris) and a batted centre: bands of
    # parallel chisel strokes, each band struck with its own offset.
    margin = 0.026 + 0.01 * table[ident, 0]
    inner = _s(dm - joint - margin, 0.0, 0.006)
    phi = np.where(table[ident, 1] < 0.5, 1, -1) * (1.0 + 0.3 * table[ident, 2])     # stroke direction
    along = lx * np.cos(phi) + ly * np.sin(phi)
    across = -lx * np.sin(phi) + ly * np.cos(phi)
    band_len = 0.04
    fb_raw = along / band_len + 0.25 * noise(rng, 6, 80, 1.0)
    band = np.floor(fb_raw)
    fb = fb_raw - band
    f = across / 0.0115 + _hash(band, ident) * 3.0 + 0.1 * noise(rng, 30, 300, 0.8)
    f = f - np.floor(f)
    groove = (1.0 - np.abs(2 * f - 1)) ** 2.5 * np.sin(math.pi * fb) ** 0.35
    weathered = _s(table[ident, 3] + 0.3 * noise(rng, 3, 40, 1.2), 0.5, 1.15)        # 1 = tooling worn away
    tool = -0.0009 * groove * inner * (1.0 - 0.75 * weathered)
    # Bedding laminations (a few blocks laid on edge) eroded at different rates.
    beta = np.where(table[ident, 4] < 0.8, 0.0, math.pi / 2) + 0.15 * (table[ident, 5] - 0.5)
    lam_c = ly * np.cos(beta) + lx * np.sin(beta)
    lam = np.sin(2 * math.pi * lam_c / (0.012 + 0.02 * table[ident, 6]) + 2.5 * noise(rng, 4, 60, 1.2))
    tilt = ((table[ident, 7] - 0.5) * 0.006 * (lx / bw - 0.5) * 2
            + (table[ident, 8] - 0.5) * 0.005 * (ly / bh - 0.5) * 2)
    face = (0.0028 * noise(rng, 3, 30, 1.2) + 0.00018 * noise(rng, 30, 400, 0.6) + tilt
            + 0.0003 * lam * (0.3 + weathered) + tool)
    pores = _s(noise(rng, 40, 300, 0.5), 2.3, 3.1)
    h_block = -0.02 + profile * (0.02 + face) - 0.0015 * pores - 0.004 * _s(spall, 0.15, 0.3)
    # Mortar: lime, recessed and crumbled where the salt has eaten it.
    eaten = _s(noise(rng, 3, 40, 1.2) + 0.5 * noise(rng, 20, 200, 0.8), -0.2, 1.2)
    crumbs = _s(noise(rng, 60, 450, 0.4), 0.8, 2.4)
    h_mortar = -0.015 - 0.009 * eaten + 0.0012 * crumbs + 0.0006 * noise(rng, 20, 300, 0.7)
    h = np.maximum(h_block, h_mortar)
    is_block = np.minimum(is_block, _s(h_block - h_mortar, -0.0005, 0.001))

    color = _mix((0.45, 0.42, 0.38), (0.31, 0.30, 0.28), light[ident])
    color = _mix(color, (0.47, 0.39, 0.29), ochre[ident] ** 2 * 0.45)
    color = _mix(color, (0.34, 0.34, 0.35), cold[ident] * 0.5)
    color = _mix(color, (0.24, 0.235, 0.23), dark[ident] * 0.6)
    color = _mul(color, 1.0 + 0.07 * noise(rng, 4, 200, 0.9) + 0.05 * noise(rng, 150, 500, 0.3)
                 + 0.04 * lam * (0.4 + 0.6 * weathered) + 0.05 * (groove - 0.3) * inner * (1 - weathered))
    color = _mul(color, 1.0 - 0.35 * pores)
    mortar = _mix((0.46, 0.43, 0.37), (0.27, 0.25, 0.21), _s(noise(rng, 4, 200, 0.9) - 0.8 * eaten, -1.5, 1.0))
    mortar = _mul(mortar, 0.85 + 0.25 * crumbs)
    color = _mix(mortar, color, is_block)
    color = _mul(color, 0.8 + 0.2 * profile)                           # grime along the arrises
    color = _mix(color, (0.52, 0.49, 0.44), _s(spall, 0.15, 0.3) * 0.3)  # fresh broken stone is paler

    # Seepage: water leaks out of the bed joints and runs down every few blocks, a dark
    # wet halo around green-black rivulets.
    core = np.zeros_like(U)
    halo = np.zeros_like(U)
    tips = np.zeros_like(U)
    for b in blocks:
        for _ in range(rng.poisson(1.5)):
            x0 = (b["u0"] + rng.uniform(0.05, 0.95) * b["w"]) * N
            y0 = b["v0"] * N - 2
            L = rng.uniform(0.2, 1.5) * b["h"] * N
            idx, ddx, ddy = window(x0, y0 + L / 2, 30, L / 2 + 4)
            yy = ddy + L / 2
            fade = np.clip(1 - yy / L, 0, 1) ** 0.7 * _s(yy, -2, 5)
            xc = 3.0 * np.sin(yy / rng.uniform(15, 40) + rng.random() * 6) + rng.normal(0, 0.03) * yy
            wh = rng.uniform(5, 10) * (1 + 0.8 * yy / L)
            stamp_max(halo, idx, np.exp(-((ddx - xc) / wh) ** 2) * fade)
            stamp_max(tips, idx, np.exp(-((ddx - xc) / (wh * 1.3)) ** 2) * np.exp(-((yy - 0.85 * L) / (0.2 * L + 4)) ** 2))
            for _ in range(rng.integers(1, 4)):
                o = rng.normal(0, 3.5)
                w = rng.uniform(1.4, 3.2)
                xr = xc + o + 1.2 * np.sin(yy / rng.uniform(6, 14) + rng.random() * 6)
                Lr = L * rng.uniform(0.5, 1.0)
                stamp_max(core, idx, np.exp(-((ddx - xr) / w) ** 2) * np.clip(1 - yy / Lr, 0, 1) ** 0.5
                          * _s(yy, -2, 5) * rng.uniform(0.6, 1.0))
    for _ in range(4):                                                 # long runs from far above
        xc = rng.random() + 0.004 * noise(rng, 2, 20, 1.5, aniso=0.2)
        mod = _s(noise(rng, 2, 30, 1.2, aniso=0.25), -0.6, 1.0)
        halo = np.maximum(halo, np.exp(-(_wrap(U - xc) / 0.006) ** 2) * mod * 0.8)
        core = np.maximum(core, np.exp(-(_wrap(U - xc - 0.001) / 0.0018) ** 2) * mod * 0.7)
    wet = np.clip(0.3 * _s(noise(rng, 3, 20, 1.3), 0.3, 1.8) + 0.7 * halo, 0, 1)
    color = _mul(color, 1.0 - 0.3 * wet)
    algae = np.clip(core * (0.8 + 0.3 * noise(rng, 10, 200, 0.8)), 0, 1)
    slime = _mix((0.05, 0.065, 0.04), (0.12, 0.16, 0.07), _s(noise(rng, 20, 300, 0.6), -1, 1.2))
    color = _mix(color, slime, algae * 0.85)
    moss = _s(0.9 * noise(rng, 3, 90, 1.0) + 1.3 * wet - 0.6, 0.8, 1.6) * (1 - is_block)
    color = _mix(color, (0.14, 0.19, 0.07), moss * 0.7)

    # Salt: crust in the eaten joints and blooms along the foot of the blocks (water
    # evaporates there), plus white tide marks around the seeps.
    salty = table[ident, 9] * 1.1 + 0.15
    foot = np.exp(-np.clip(bh - ly, 0, None) / 0.05) * is_block * salty
    zone = 1.1 * foot + 0.9 * (1 - is_block) * eaten + 0.7 * tips * (1 - core)
    crystal = _s(noise(rng, 60, 450, 0.5), -0.6, 1.4)
    salt = _s(zone + 0.35 * noise(rng, 4, 120, 1.0) - 0.45, 0.0, 0.5) * (0.45 + 0.55 * crystal)
    color = _mix(color, (0.74, 0.73, 0.68), salt * 0.8)
    h = h + 0.0004 * salt * crystal

    # Soot from the torches: dark plumes settling on the faces.
    soot = _s(noise(rng, 3, 40, 1.3, aniso=2.0, ang=math.pi / 2) + 0.4 * noise(rng, 8, 100, 1.0), 0.8, 2.3)
    color = _mix(color, (0.05, 0.045, 0.04), soot * 0.5 * (0.6 + 0.4 * is_block))

    # An old iron staple and a hook, cut off, bleeding rust down the wall.
    rust = np.zeros_like(U)
    lump = np.zeros_like(U)
    big = sorted(blocks, key=lambda b: -b["w"] * b["h"])
    for b in (big[1], big[7]):
        sx = (b["u0"] + rng.uniform(0.2, 0.8) * b["w"]) * N
        sy = (b["v0"] + rng.uniform(0.12, 0.3) * b["h"]) * N
        idx, ddx, ddy = window(sx, sy, 10)
        stamp_max(lump, idx, _s(6.0 - np.sqrt((ddx / 1.3) ** 2 + ddy ** 2), 0, 1.5))
        Lw = rng.uniform(200, 300)
        idx, ddx, ddy = window(sx, sy + Lw / 2, 30, Lw / 2 + 4)
        yy = ddy + Lw / 2
        stamp_max(rust, idx, 0.45 * np.exp(-(ddx / (5 + 10 * yy / Lw)) ** 2) * np.clip(1 - yy / Lw, 0, 1) * _s(yy, -3, 6))
        for _ in range(rng.integers(5, 9)):
            L = rng.uniform(50, 280)
            x0 = sx + rng.normal(0, 6)
            idx, ddx, ddy = window(x0, sy + L / 2, 16, L / 2 + 4)
            yy = ddy + L / 2
            xc = 2.0 * np.sin(yy / rng.uniform(12, 30) + rng.random() * 6)
            w = rng.uniform(1.2, 3.0) * (1 + 0.6 * yy / L)
            stamp_max(rust, idx, np.exp(-((ddx - xc) / w) ** 2) * np.clip(1 - yy / L, 0, 1) ** 0.9 * _s(yy, -3, 3))
        idx, ddx, ddy = window(sx, sy + 6, 30)
        stamp_max(rust, idx, np.exp(-(ddx ** 2 + (ddy * 0.8) ** 2) / 200.0))
    rust = np.clip(rust * (0.75 + 0.25 * noise(rng, 30, 300, 0.7).clip(-1, 1)), 0, 1)
    color = _mix(color, (0.36, 0.17, 0.07), rust * 0.8)
    color = _mix(color, (0.10, 0.07, 0.05), lump)
    color = _mix(color, (0.34, 0.16, 0.06), lump * _s(noise(rng, 60, 400, 0.5), 0.0, 1.0) * 0.8)
    h = h + 0.005 * lump

    # Prisoners' scratches on a few blocks: a tally of days, initials and a year, a gallows,
    # an anchor; a scatter of faint knife and nail scratches everywhere.
    fresh = Canvas()
    old = Canvas()

    def at(b, fx, fy):
        return (b["u0"] + fx * b["w"]) * N, (b["v0"] + fy * b["h"]) * N

    x, y = at(big[0], 0.18, 0.22)
    tally(fresh, rng, x, y, 27, 30, 2.4, 6.5, 12)
    x, y = at(big[0], 0.6, 0.66)
    scratch_text(fresh, rng, "J.R", x, y, 22, 2.2)
    x, y = at(big[2], 0.3, 0.28)
    scratch_text(old, rng, "W.T", x, y, 32, 2.8)
    scratch_text(old, rng, "1698", x - 6, y + 42, 26, 2.5)
    gx, gy = at(big[4], 0.62, 0.2)                      # gallows with a hanged man
    old.line([(gx, gy + 72), (gx, gy)], 2.8)
    old.line([(gx - 6, gy), (gx + 36, gy)], 2.8)
    old.line([(gx, gy + 13), (gx + 13, gy)], 2.2)
    old.line([(gx + 30, gy), (gx + 30, gy + 14)], 1.8)
    old.ellipse(gx + 30, gy + 18.5, 4.6, 4.6)
    old.line([(gx + 30, gy + 22), (gx + 31, gy + 41)], 2.4)
    old.line([(gx + 31, gy + 41), (gx + 26, gy + 56)], 2.2)
    old.line([(gx + 31, gy + 41), (gx + 35, gy + 56)], 2.2)
    old.line([(gx + 24, gy + 30), (gx + 30, gy + 26), (gx + 37, gy + 30)], 2.0)
    old.line([(gx - 15, gy + 72), (gx + 15, gy + 72)], 2.6)
    scratch_text(old, rng, "I.H", gx - 10, gy + 82, 20, 2.2)
    x, y = at(big[6], 0.32, 0.26)                       # a sailor's anchor
    anc = [[(0.5, 0.12), (0.5, 0.92)], [(0.28, 0.24), (0.72, 0.24)],
           [(0.1, 0.62), (0.18, 0.8), (0.32, 0.92), (0.5, 0.97), (0.68, 0.92), (0.82, 0.8), (0.9, 0.62)],
           [(0.1, 0.62), (0.03, 0.72)], [(0.1, 0.62), (0.2, 0.68)], [(0.9, 0.62), (0.97, 0.72)],
           [(0.9, 0.62), (0.8, 0.68)]]
    for pl in anc:
        fresh.line([(x + px_ * 48 + rng.normal(0, 0.6), y + py * 66 + rng.normal(0, 0.6)) for px_, py in pl], 2.3)
    fresh.ellipse(x + 24, y + 4, 4.5, 4.5)
    fresh.ellipse(x + 24, y + 4, 2.2, 2.2, value=0)
    for _ in range(80):
        b = blocks[rng.integers(len(blocks))]
        x, y = at(b, rng.uniform(0.1, 0.9), rng.uniform(0.1, 0.9))
        a = rng.uniform(0, math.pi)
        L = rng.uniform(6, 30)
        old.taper([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], rng.uniform(0.9, 1.5), 0.4, value=150)
    fresh, old = fresh.get() * is_block, old.get() * is_block
    color = _mix(color, (0.60, 0.57, 0.51), fresh * 0.6)
    color = _mix(color, (0.10, 0.09, 0.08), old * 0.6)
    h = h - 0.0015 * fresh - 0.0013 * old

    rough = np.where(is_block > 0.5, 0.86, 0.94) + 0.04 * noise(rng, 6, 100, 1.0) - 0.05 * (1 - weathered) * inner
    rough = rough * (1.0 - 0.35 * wet)
    rough = _mix(rough, 0.5, algae * 0.8)
    rough = _mix(rough, 0.97, salt)
    rough = _mix(rough, 0.96, soot * 0.5)
    rough = _mix(rough, 0.9, rust * 0.5)
    return color, h, rough, np.zeros_like(h), 0.02


def floor(rng):
    """Great flagstones of the hall floor: polished smooth along the walking lines and
    dished by feet, settled and cracked slabs (one shattered where something heavy fell)
    with grit in the cracks, joints of black mud, water standing in the low places, straw
    blown in from the cells, a trail of wax from a guard's candle and old dark stains."""
    t = UV_TILE["Floor"]                          # 2 m, ~2 mm per pixel
    u = (U + 0.004 * noise(rng, 2, 24, 1.3)) % 1.0
    v = (V + 0.004 * noise(rng, 2, 24, 1.3)) % 1.0
    lx, ly, bw, bh, ident, blocks = ashlar(rng, u, v, 4, 0.24, 0.42, hvar=0.18)
    lx, ly, bw, bh = lx * t, ly * t, bw * t, bh * t
    table = rng.random((4 * 16, 8))
    nb = len(blocks)
    order = rng.permutation(nb)
    light = np.zeros(4 * 16)
    for k, b in enumerate(blocks):
        light[b["id"]] = (order[k] + rng.uniform(0.2, 0.8)) / nb
    dx = np.minimum(lx, bw - lx)
    dy = np.minimum(ly, bh - ly)
    dist = dx * dy / np.sqrt(dx * dx + dy * dy + 1e-12)
    corner = _s(0.12 - np.sqrt(dx * dx + dy * dy), 0.0, 0.07)
    chip = _s(noise(rng, 4, 40, 1.1) + 0.9 * corner, 1.35, 1.7) * _s(0.07 - dist, 0.0, 0.04)
    dm = dist + 0.004 * noise(rng, 8, 120, 0.9) - 0.015 * chip
    joint = 0.009 + 0.003 * noise(rng, 3, 40, 1.0)
    profile = _rounded((dm - joint) / (0.024 + 0.014 * _s(noise(rng, 3, 30, 1.0), -1.5, 1.5)))
    # Walking lines: long polished lanes; slab centres dished by feet.
    walk = _s(noise(rng, 2, 16, 1.4, aniso=3.0, ang=0.4) + 0.35 * noise(rng, 3, 12, 1.4), -0.2, 1.2)
    detail = 1.0 - 0.8 * walk
    cx_ = (lx / bw - 0.5) * 2
    cy_ = (ly / bh - 0.5) * 2
    dish = (1 - cx_ ** 2) * (1 - cy_ ** 2)
    sunk = (table[ident, 0] > 0.85) * 0.006                          # a settled slab
    tilt = (table[ident, 1] - 0.5) * 0.004 * cx_ + (table[ident, 2] - 0.5) * 0.004 * cy_
    pits = _s(noise(rng, 50, 400, 0.4), 2.4, 3.2) * detail
    face = (tilt - sunk - 0.003 * dish * (0.3 + walk) + 0.0024 * noise(rng, 3, 40, 1.2)
            + 0.00015 * noise(rng, 40, 400, 0.6) * detail - 0.001 * pits)
    slab = -0.02 + profile * (0.02 + face) - 0.004 * _s(chip, 0.15, 0.3)

    # Cracks: some slabs split right across, one shattered around an impact (its
    # pieces sunk by different amounts).
    cv = Canvas()
    big = sorted(blocks, key=lambda b: -b["w"] * b["h"])
    shattered = big[1]

    def crack_path(b, x, y, ang, turn, step=4.0, jag=1.0):
        x_lo, x_hi = b["u0"] * N + 3, (b["u0"] + b["w"]) * N - 3
        y_lo, y_hi = b["v0"] * N + 3, (b["v0"] + b["h"]) * N - 3
        pts = [(x, y)]
        for _ in range(400):
            ang += rng.normal(0, turn)
            x, y = x + math.cos(ang) * step, y + math.sin(ang) * step
            pts.append((x + rng.normal(0, jag) * abs(math.sin(ang)), y + rng.normal(0, jag) * abs(math.cos(ang))))
            if not (x_lo < x < x_hi and y_lo < y < y_hi):
                break
        return pts

    for b in blocks:
        if b is shattered or rng.random() > 0.4:
            continue
        if rng.random() < 0.5:
            pts = crack_path(b, b["u0"] * N + 4, (b["v0"] + rng.uniform(0.25, 0.75) * b["h"]) * N,
                             rng.normal(0, 0.3), 0.12)
        else:
            pts = crack_path(b, (b["u0"] + rng.uniform(0.2, 0.8) * b["w"]) * N, b["v0"] * N + 4,
                             math.pi / 2 + rng.normal(0, 0.3), 0.12)
        cv.taper(pts, rng.uniform(2.6, 3.6), 1.6)
        for _ in range(rng.integers(0, 3)):
            k = rng.integers(1, len(pts) - 1)
            br = crack_path(b, *pts[k], rng.uniform(0, 2 * math.pi), 0.2)[:rng.integers(5, 20)]
            cv.taper(br, 2.0, 0.8)
    ix, iy = (shattered["u0"] + 0.55 * shattered["w"]) * N, (shattered["v0"] + 0.5 * shattered["h"]) * N
    a0 = rng.random()
    nsec = 6
    rays = (np.arange(nsec) + 0.5 + rng.uniform(-0.25, 0.25, nsec)) * 2 * math.pi / nsec + a0
    for a in rays:
        cv.taper(crack_path(shattered, ix, iy, a, 0.0, jag=0.8), 3.6, 2.2)
    cv.ellipse(ix, iy, 7, 6)
    crack = cv.get() * _s(profile, 0.1, 0.5)
    rel = (np.arctan2(_wrap(V - iy / N), _wrap(U - ix / N)) - a0) % (2 * math.pi)
    sec = np.searchsorted(np.sort((rays - a0) % (2 * math.pi)), rel)
    in_shattered = (ident == shattered["id"]).astype(float)
    slab = slab - in_shattered * (0.001 + 0.003 * _hash(sec % nsec, 3.0))
    crack_edge = np.clip(blur(crack, 2.0) * 2.5, 0, 1)
    slab = slab - 0.006 * crack - 0.0008 * crack_edge

    # Black mud and grit in the joints.
    mud_level = -0.017 + 0.002 * noise(rng, 6, 120, 1.2) + 0.004 * _s(noise(rng, 2, 20, 1.3), 0.5, 1.6)
    grit = _s(noise(rng, 100, 500, 0.2), 1.2, 2.2)
    h_mud = mud_level + 0.0012 * grit
    h = np.maximum(slab, h_mud)
    shows_mud = _s(h_mud - slab, -0.0005, 0.0015)

    c_slab = _mix((0.42, 0.40, 0.36), (0.29, 0.28, 0.26), light[ident])
    c_slab = _mix(c_slab, (0.41, 0.35, 0.28), table[ident, 4] ** 2 * 0.5)
    c_slab = _mul(c_slab, 1.0 + (0.08 * noise(rng, 3, 200, 0.9) + 0.05 * noise(rng, 150, 500, 0.3)) * detail)
    c_slab = _mul(c_slab, 1.0 - 0.4 * pits)
    c_slab = _mix(c_slab, c_slab * 1.15 + 0.015, walk * profile * 0.6)      # polished lanes are paler
    c_slab = _mul(c_slab, 0.72 + 0.28 * profile)
    c_slab = _mix(c_slab, (0.47, 0.44, 0.39), _s(chip, 0.15, 0.3) * 0.3)
    c_mud = _mix((0.16, 0.13, 0.10), (0.07, 0.06, 0.045), _s(noise(rng, 4, 60, 1.0), -1, 1))
    c_mud = _mix(c_mud, (0.34, 0.31, 0.26), grit * 0.5)
    color = _mix(c_slab, c_mud, shows_mud)
    color = _mix(color, (0.04, 0.035, 0.03), crack * 0.9)
    gritc = crack_edge * _s(noise(rng, 100, 500, 0.2), 0.8, 2.0)
    color = _mix(color, (0.44, 0.41, 0.35), gritc * 0.5)
    filth = _s(noise(rng, 3, 60, 1.2), -0.2, 1.8) * (1 - 0.6 * walk)
    color = _mix(color, (0.13, 0.11, 0.09), filth * 0.35)

    # Old stains (wine, blood, lamp oil): dark with a faint tide mark, and a few drops.
    stain = np.zeros_like(U)
    for k in range(4):
        cx, cy = rng.random() * N, rng.random() * N
        R = rng.uniform(45, 80) if k < 2 else rng.uniform(15, 30)
        idx, ddx, ddy = window(cx, cy, R * 2.0)
        ang = np.arctan2(ddy, ddx)
        rr = R * (1 + 0.25 * np.sin(3 * ang + rng.random() * 6) + 0.15 * np.sin(5 * ang + rng.random() * 6))
        d = np.sqrt(ddx ** 2 + ddy ** 2) / rr
        stamp_max(stain, idx, _s(1.0 - d, 0.0, 0.25) * (0.55 + 0.45 * _s(d, 0.7, 0.97)))
        for _ in range(rng.integers(3, 8)):
            a, r_ = rng.uniform(0, 2 * math.pi), R * rng.uniform(1.1, 1.8)
            sx, sy = cx + math.cos(a) * r_, cy + math.sin(a) * r_
            rs = rng.uniform(1.5, 4)
            idx2, ex, ey = window(sx, sy, rs + 2)
            stamp_max(stain, idx2, 0.8 * _s(rs - np.sqrt(ex ** 2 + ey ** 2), -0.5, 0.8))
    stain *= 0.7 + 0.3 * _s(noise(rng, 20, 200, 0.8), -1, 1)
    color = _mix(color, _mul(color, 0.5) * np.array([1.05, 0.85, 0.75]), stain * 0.85)

    # Standing water: joints and low places fill up in the wet areas, perfectly flat.
    wet_area = _s(noise(rng, 2, 14, 1.5), 0.4, 1.4)
    level = -0.012 + 0.009 * wet_area
    puddle = wet_area * _s(level - h, 0.0, 0.0012)
    damp = np.clip(wet_area * 1.2 * _s(level + 0.003 - h, 0.0, 0.004) + 0.4 * wet_area, 0, 1)
    color = _mul(color, 1.0 - 0.25 * damp)
    color = _mix(color, _mul(color, 0.62), puddle)
    h = h + puddle * np.maximum(level - h, 0)

    # Straw blown in from the cells, mostly lodged in the joints.
    sv = Canvas(ss=3)
    joint_w = 1 - profile
    count = 0
    while count < 240:
        x, y = rng.random() * N, rng.random() * N
        if rng.random() > 0.12 + 0.88 * joint_w[int(y) % N, int(x) % N]:
            continue
        count += 1
        a = rng.uniform(0, math.pi)
        L = rng.uniform(10, 40)
        pts = random_walk(rng, x, y, a, L / 3, 3, 0.15)
        sv.line(pts, rng.uniform(1.8, 3.0), value=int(rng.uniform(150, 255)))
    straw = np.clip(sv.get() * 1.4, 0, 1)
    straw_c = _mix((0.55, 0.45, 0.26), (0.30, 0.24, 0.15), _s(noise(rng, 40, 300, 0.6), -1, 1))
    straw_c = _mul(straw_c, 0.75 + 0.25 * _s(noise(rng, 100, 500, 0.3), -1, 1))
    color = _mix(color, straw_c, straw * (1 - 0.5 * puddle))
    h = h + 0.0015 * straw

    # A guard's candle: a trail of wax drops across the floor and a pool where it stood.
    wax = np.zeros_like(U)
    x, y, a = rng.random() * N, rng.random() * N, rng.uniform(0, 2 * math.pi)
    for _ in range(22):
        a += rng.normal(0, 0.25)
        step = rng.uniform(15, 45)
        x, y = x + math.cos(a) * step, y + math.sin(a) * step
        r = rng.uniform(2.5, 6.0)
        el = rng.uniform(0.75, 1.3)
        idx, ddx, ddy = window(x, y, r * 2 + 3)
        stamp_max(wax, idx, np.clip(1 - (ddx ** 2 + (ddy * el) ** 2) / r ** 2, 0, 1) ** 0.5)
        for _ in range(rng.integers(0, 3)):
            rs = r * rng.uniform(0.2, 0.45)
            ex, ey = x + rng.normal(0, r * 1.6), y + rng.normal(0, r * 1.6)
            idx2, ddx2, ddy2 = window(ex, ey, rs + 2)
            stamp_max(wax, idx2, np.clip(1 - (ddx2 ** 2 + ddy2 ** 2) / rs ** 2, 0, 1) ** 0.5)
    pool_x, pool_y = rng.random() * N, rng.random() * N
    for _ in range(9):
        r = rng.uniform(5, 13)
        ex, ey = pool_x + rng.normal(0, 7), pool_y + rng.normal(0, 7)
        idx, ddx, ddy = window(ex, ey, r + 3)
        stamp_max(wax, idx, np.clip(1 - (ddx ** 2 + ddy ** 2) / r ** 2, 0, 1) ** 0.4)
    wax_c = _mix((0.70, 0.64, 0.50), (0.44, 0.40, 0.31), _s(noise(rng, 30, 300, 0.6), -0.5, 1.5))
    wax_cov = _s(wax, 0.0, 0.25)
    color = _mix(color, _mul(wax_c, 0.85 + 0.15 * wax), wax_cov)
    h = h + 0.0018 * wax

    rough = 0.84 + 0.04 * noise(rng, 4, 80, 1.0)
    rough = _mix(rough, 0.45, walk * profile * 0.9)
    rough = _mix(rough, 0.92, shows_mud * (1 - damp))
    rough = rough * (1.0 - 0.4 * damp)
    rough = _mix(rough, 0.6, stain * 0.4)
    rough = _mix(rough, 0.04, puddle)
    rough = _mix(rough, 0.75, straw)
    rough = _mix(rough, 0.35, wax_cov)
    return color, h, rough, np.zeros_like(h), 0.015


def wood(rng):
    """Old oak planks: flat-sawn cathedral grain with open pores eroded deep, adze
    scallops, hand-forged nail heads with rust and black iron-tannin halos (one pulled
    out, only the hole left), seams paid with pitch, wax and tar spills, knife cuts,
    grime packed in the grain and arrises polished by hands."""
    t = UV_TILE["Wood"]                           # 1 m, ~1 mm per pixel
    nplanks = 5                                   # planks of 0.2 m
    pw = t / nplanks
    v = (V + 0.0012 * noise(rng, 2, 16, 1.4, aniso=4)) % 1.0
    py = v * nplanks
    row = np.floor(py).astype(np.int32) % nplanks
    vloc = py - np.floor(py)
    joists = np.array([0.13, 0.63])
    xl = np.zeros_like(U)                         # local x in the plank segment (repeat units)
    seg = np.zeros(U.shape, np.int32)
    dc = np.full(U.shape, 9.0)
    row_cuts = []
    for r in range(nplanks):
        c0 = (r * 0.37 + rng.uniform(-0.08, 0.08)) % 1.0                # staggered butt joints
        cuts = np.array([c0]) if rng.random() < 0.45 else np.sort([c0, (c0 + rng.uniform(0.38, 0.62)) % 1.0])
        row_cuts.append(cuts)
        m = row == r
        xs = U[m]
        d = np.min(np.abs(_wrap(xs[:, None] - cuts[None, :])), axis=1)
        dc[m] = d
        k = np.searchsorted(cuts, xs) % len(cuts)
        xl[m] = (xs - cuts[k - 1]) % 1.0
        seg[m] = k
    ident = row * 4 + seg
    table = rng.random((nplanks * 4, 10))
    X, Y = xl * t, vloc * pw                      # metres along / across the plank
    dm = np.minimum(dc * t, np.minimum(vloc, 1 - vloc) * pw)
    dm = dm + 0.0007 * noise(rng, 10, 200, 0.8)
    edge_wear = 0.004 + 0.0025 * _s(noise(rng, 3, 30, 1.2), -1, 1.5)
    profile = _rounded((dm - 0.0018) / edge_wear)

    # Flat-sawn figure: rings around a pith that runs at a slight angle to the board.
    d = (0.02 + 0.07 * table[ident, 0] + (table[ident, 1] - 0.5) * 0.14 * X
         + 0.004 * noise(rng, 2, 20, 1.4, aniso=6))
    yc = -0.05 + 0.3 * table[ident, 2]
    Yw = Y + 0.0028 * noise(rng, 2, 30, 1.2, aniso=10) + 0.0007 * noise(rng, 10, 120, 1.0, aniso=6)
    radius = np.sqrt(d ** 2 + (Yw - yc) ** 2)
    spacing = 0.0045 + 0.0025 * table[ident, 3]
    ring = radius / spacing
    fr = ring - np.floor(ring)
    early = _s(fr, 0.0, 0.05) * (1 - _s(fr, 0.2, 0.34))               # porous earlywood band
    late = _s(fr, 0.45, 0.9)
    pore_n = noise(rng, 60, 500, 0.4, aniso=12)
    pores = _s(pore_n, 0.4, 1.4) * early + _s(pore_n, 2.0, 2.8) * (1 - early) * 0.6
    rays = _s(noise(rng, 30, 420, 0.6, aniso=7), 2.2, 2.9)
    fiber = noise(rng, 4, 400, 0.6, aniso=30)
    checks = _s(noise(rng, 3, 220, 0.8, aniso=40), 2.45, 3.0)         # drying checks along the grain

    # Adze scallops on most planks (shallow facets with a crisp ridge), a few sawn flat.
    adzed = (table[ident, 4] < 0.75).astype(float)
    sp_ = 0.04 + 0.025 * table[ident, 5]
    lane_f = Y / (pw / 3) + 0.25 * noise(rng, 3, 30, 1.2, aniso=4)    # adze strokes ~7 cm wide
    lane = np.floor(lane_f)
    lc = lane_f - lane - 0.5
    sa = X / sp_ + 0.6 * lc ** 2 + _hash(lane, ident) * 5.0 + 0.03 * noise(rng, 8, 80, 1.2)
    fa = sa - np.floor(sa)
    depth = 0.0012 + 0.0016 * _hash(np.floor(sa), ident + 7 * lane)
    across_fade = (1 - 0.6 * np.abs(lc) ** 3 * 8) * (0.6 + 0.4 * _s(noise(rng, 3, 30, 1.0, aniso=0.3), -1.2, 0.8))
    across_fade = np.clip(across_fade, 0, 1)
    scallop = -(1 - (2 * fa - 1) ** 2) * depth * adzed * across_fade
    ridge = _s(np.abs(2 * fa - 1), 0.8, 1.0) * adzed * across_fade

    hp = (0.0045 + scallop - 0.0009 * early - 0.0005 * pores + 0.00012 * fiber
          - 0.0012 * ((vloc - 0.5) * 2) ** 2 * table[ident, 7])      # cupped planks
    h = -0.005 + profile * (0.005 + hp) - 0.0025 * checks

    color = _mix((0.33, 0.235, 0.155), (0.22, 0.16, 0.105), table[ident, 8])
    color = _mix(color, (0.29, 0.265, 0.235), (table[ident, 9] > 0.88) * 0.55)  # a silvered plank
    color = _mul(color, 1.0 - 0.32 * early - 0.25 * pores + 0.08 * late + 0.06 * fiber)
    color = _mix(color, (0.40, 0.30, 0.19), rays * 0.3)
    color = _mul(color, 1.0 - 0.65 * checks)

    # Grime packed in the grain and the adze hollows; hands have polished arrises and ridges.
    hollow = (1 - _s(np.abs(2 * fa - 1), 0.0, 0.7)) * adzed * across_fade
    grain_cav = np.clip(0.6 * early + 0.6 * pores + 0.35 * hollow, 0, 1)
    dirt = _s(noise(rng, 3, 120, 1.1), -0.2, 1.8)
    color = _mix(color, (0.05, 0.04, 0.03), np.clip(grain_cav * (0.4 + 0.4 * dirt) + 0.22 * dirt, 0, 1) * 0.75)
    polish = np.clip((1 - _s(profile, 0.25, 1.0)) * 0.9 + 0.25 * ridge
                     + _s(noise(rng, 3, 20, 1.3), 0.6, 1.8) * 0.5, 0, 1) * _s(profile, 0.02, 0.2)
    color = _mix(color, (0.44, 0.29, 0.15), polish * 0.4)
    color = _mix((0.035, 0.028, 0.02), _mul(color, 0.55 + 0.45 * profile), _s(profile, 0.0, 0.45))

    # Rings left by wet tankards, and grime gathered along the ends and seams.
    ring = np.zeros_like(U)
    for _ in range(3):
        cx, cy, R = rng.random() * N, rng.random() * N, rng.uniform(36, 46)
        idx, ddx, ddy = window(cx, cy, R + 8)
        rr = np.sqrt(ddx ** 2 + ddy ** 2)
        arc = _s(np.cos(np.arctan2(ddy, ddx) - rng.uniform(0, 6.3)), -0.7, 0.2)
        stamp_max(ring, idx, (np.exp(-((rr - R) / 2.2) ** 2) * (0.5 + 0.5 * arc) + 0.25 * _s(R - rr, 0, 3)))
    color = _mul(color, 1.0 - 0.45 * ring * _s(profile, 0.2, 0.6))
    near_end = 1 - _s(dm, 0.003, 0.03)
    color = _mix(color, (0.05, 0.04, 0.03), near_end * 0.35 * (0.5 + 0.5 * dirt))

    # Seams paid with pitch, overflowing here and there; tar and wax spills.
    edge_d = np.minimum(vloc, 1 - vloc) * pw
    tar = (1 - _s(edge_d, 0.003, 0.0045 + 0.004 * _s(noise(rng, 6, 80, 1.0), 0.6, 2.0))) \
        * _s(noise(rng, 2, 30, 1.2, aniso=0.3), -0.6, 0.2)
    for _ in range(2):
        cx, cy = rng.random() * N, rng.random() * N
        for _ in range(rng.integers(5, 12)):
            r = rng.uniform(2, 11)
            ex, ey = cx + rng.normal(0, 16), cy + rng.normal(0, 9)
            idx, ddx, ddy = window(ex, ey, r * 1.8 + 2)
            stamp_max(tar, idx, _s(1 - (ddx ** 2 / 1.6 + ddy ** 2) / r ** 2, 0, 0.3))
    wax = np.zeros_like(U)
    for _ in range(2):
        cx, cy = rng.random() * N, rng.random() * N
        for _ in range(rng.integers(6, 11)):
            r = rng.uniform(3, 9)
            ex, ey = cx + rng.normal(0, 16), cy + rng.normal(0, 16)
            idx, ddx, ddy = window(ex, ey, r + 2)
            stamp_max(wax, idx, np.clip(1 - (ddx ** 2 + ddy ** 2) / r ** 2, 0, 1) ** 0.5)
    tar_c = _s(tar, 0.0, 0.5)
    color = _mix(color, (0.03, 0.025, 0.02), tar_c * 0.95)
    h = _mix(h, np.maximum(h, -0.0006 + 0.0012 * tar), tar_c)
    wax_c = _s(wax, 0, 0.25)
    color = _mix(color, (0.62, 0.56, 0.43), wax_c)
    h = h + 0.0016 * wax

    # Knife cuts from idle hands.
    cv = Canvas()
    for _ in range(40):
        x, y = rng.random() * N, rng.random() * N
        a = rng.normal(0.3, 0.6)
        L = rng.uniform(10, 45)
        cv.taper([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], rng.uniform(1.0, 1.7), 0.4, value=200)
    cuts = cv.get() * _s(profile, 0.3, 0.8)
    color = _mix(color, (0.45, 0.33, 0.21), cuts * 0.45)
    h = h - 0.0006 * cuts

    # Hand-forged nails on the joist lines (two per plank) and at every plank end.
    head = np.zeros_like(U)
    nail_h = np.zeros_like(U)
    halo = np.zeros_like(U)
    rusty = np.zeros_like(U)
    hole = np.zeros_like(U)
    nails = []
    for r in range(nplanks):
        xs_ = list(joists)
        for c in row_cuts[r]:
            xs_ = [x for x in xs_ if abs(_wrap(x - c)) > 0.06] + [c - 0.03, c + 0.03]
        for xn in xs_:
            for fy in (0.26, 0.74):
                nails.append((xn + rng.normal(0, 0.004), (r + fy + rng.normal(0, 0.025)) / nplanks))
    for xn, yn in nails:
        cx, cy = xn * N, yn * N
        s = rng.uniform(8.0, 10.5)                # half size, px (~1.8 cm heads)
        a = rng.uniform(0, math.pi / 2)
        R = rng.uniform(14, 26)
        idx, ddx, ddy = window(cx, cy, R * 1.9 * 2.6, R * 2.6)
        el = np.sqrt((ddx / 1.9) ** 2 + ddy ** 2)
        stamp_max(halo, idx, np.exp(-(el / R) ** 1.6) * rng.uniform(0.6, 1.0))
        if rng.random() < 0.07:                   # pulled out: only the hole is left
            stamp_max(hole, idx, _s(3.5 - np.sqrt(ddx ** 2 + ddy ** 2), -0.5, 0.8))
            continue
        xr = ddx * math.cos(a) + ddy * math.sin(a)
        yr = -ddx * math.sin(a) + ddy * math.cos(a)
        sq = (np.abs(xr) ** 3 + np.abs(yr) ** 3) ** (1 / 3) / s
        facets = 0.85 + 0.15 * np.cos(xr * 0.7 + rng.random() * 6) * np.cos(yr * 0.6 + rng.random() * 6)
        stamp_max(head, idx, _s(1.0 - sq, -0.06, 0.08))
        stamp_max(nail_h, idx, 0.0028 * np.sqrt(np.clip(1 - sq ** 2, 0, 1)) * facets)
        stamp_max(rusty, idx, np.exp(-((np.sqrt(ddx ** 2 + ddy ** 2) - s) / 4.0) ** 2))
    halo *= 0.7 + 0.3 * _s(noise(rng, 20, 300, 0.8, aniso=4), -1, 1)
    color = _mix(color, (0.04, 0.04, 0.045), np.clip(halo, 0, 1) * 0.85)          # iron + oak tannin = black
    color = _mix(color, (0.30, 0.14, 0.06), np.clip(rusty, 0, 1) * (1 - head) * 0.7)
    color = _mix(color, (0.02, 0.015, 0.01), hole)
    nail_rust = _s(noise(rng, 30, 300, 0.8) + 0.5 * noise(rng, 100, 500, 0.3), -0.3, 1.0)
    nail_c = _mix((0.17, 0.165, 0.16), (0.36, 0.17, 0.07), nail_rust)
    nail_c = _mul(nail_c, 0.8 + 0.35 * _s(nail_h, 0.0015, 0.0028))         # worn bright on top
    color = _mix(color, nail_c, head)
    h = h + nail_h - 0.004 * hole

    rough = 0.80 + 0.05 * noise(rng, 3, 60, 1.0) + 0.08 * dirt
    rough = _mix(rough, 0.4, polish * 0.85)
    rough = _mix(rough, 0.95, checks)
    rough = _mix(rough, 0.2, tar_c)
    rough = _mix(rough, 0.4, wax_c)
    rough = _mix(rough, 0.5 + 0.4 * nail_rust, head)
    metal = head * (1 - nail_rust) * 0.7
    return color, h, rough, metal, 0.003


def iron(rng):
    """Wrought iron: black forge scale over fibrous metal, overlapping hammer blows, a
    riveted lap seam weeping rust, flaking layered rust, scratches, and bright bare metal
    only where a chain has rubbed it (metal 1 and low roughness only there)."""
    t = UV_TILE["Iron"]                           # 0.5 m, ~0.5 mm per pixel
    u = (U + 0.006 * noise(rng, 2, 20, 1.3)) % 1.0
    v = (V + 0.006 * noise(rng, 2, 20, 1.3)) % 1.0
    f1a, _, ida = voronoi(rng, 13, u, v, 0.95)    # hammer blows of ~4 cm
    f1b, _, idb = voronoi(rng, 29, (u + 0.37) % 1, (v + 0.11) % 1, 0.95)
    ta, tb = rng.random(13 * 13), rng.random(29 * 29)
    dent = -0.0012 * (1 - f1a ** 2) * (0.4 + ta[ida]) - 0.0004 * (1 - f1b ** 2) * (0.3 + tb[idb])
    fibre = noise(rng, 6, 500, 0.6, aniso=24)
    # Lap seam: each plate overlaps the next, its edge hammered wavy; rivets above it.
    v0 = 0.62
    v_edge = v0 + 0.003 * noise(rng, 2, 24, 1.5, aniso=30, ang=math.pi / 2)
    dv = (v_edge - V) % 1.0                       # 0 at the edge, growing upwards
    plate = 0.0018 * (1 - dv) * _s(dv, 0.0, 0.003) - 0.0009
    crevice = np.exp(-(_wrap(V - v_edge) / 0.004) ** 2)
    rivet_h = np.zeros_like(U)
    rivet = np.zeros_like(U)
    collar = np.zeros_like(U)
    rivet_top = np.zeros_like(U)
    for i in range(6):
        cx = ((i + 0.5) / 6 + rng.normal(0, 0.006)) * N
        cy = (v0 - 0.03 + rng.normal(0, 0.002)) * N
        r = rng.uniform(15, 18)                  # ~8 mm head radius
        idx, ddx, ddy = window(cx, cy, r + 12)
        d = np.sqrt(ddx ** 2 + ddy ** 2) / r
        flat = 0.85 + 0.15 * np.cos(ddx * 0.25 + rng.random() * 6)
        stamp_max(rivet_h, idx, 0.0035 * np.clip(1 - d ** 2, 0, 1) ** 0.6 * flat)
        stamp_max(rivet, idx, _s(1 - d, -0.05, 0.08))
        stamp_max(collar, idx, np.exp(-((d - 1.08) / 0.16) ** 2))
        stamp_max(rivet_top, idx, _s(0.45 - np.sqrt((ddx / r + 0.15) ** 2 + (ddy / r + 0.2) ** 2), 0, 0.2))
    # Rust: patches, a crust in the crevices, weeping from the seam, flaking in layers.
    weep = np.zeros_like(U)
    for _ in range(9):
        x0 = rng.random() * N
        L = rng.uniform(40, 220)
        y0 = v0 * N + 2
        idx, ddx, ddy = window(x0, y0 + L / 2, 20, L / 2 + 4)
        yy = ddy + L / 2
        w = rng.uniform(2.5, 7) * (1 + 0.5 * yy / L)
        stamp_max(weep, idx, np.exp(-(ddx / w) ** 2) * np.clip(1 - yy / L, 0, 1) * _s(yy, -2, 2))
    rust_n = noise(rng, 2, 50, 1.3) + 0.55 * noise(rng, 12, 200, 0.8)
    rust = _s(rust_n + 0.9 * crevice + 0.8 * weep + 0.9 * collar, 0.55, 1.15)
    flake_n = noise(rng, 6, 120, 1.0)
    l1, l2 = _s(flake_n, -0.25, -0.15), _s(flake_n, 0.65, 0.75)
    flakes = (l1 + l2) * rust
    lit_edge = np.clip(np.roll(flakes, 2, 0) - flakes, 0, 1)          # upper rims of lifted flakes
    flake_edge = (l1 * (1 - l1) + l2 * (1 - l2)) * 4 * rust
    pitting = _s(noise(rng, 60, 450, 0.4), 2.0, 2.9) * (0.3 + 0.7 * rust)
    crust = noise(rng, 40, 400, 0.6)
    # Chain rubs: bright bare metal with striations, inside a burnished black halo.
    rub = np.zeros_like(U)
    burnish = np.zeros_like(U)
    stri = np.zeros_like(U)
    for k in range(2):
        cx, cy = rng.random() * N, rng.uniform(0.08, 0.45) * N
        a = rng.normal(math.pi / 2, 0.45)
        Lr, Wr = rng.uniform(45, 90), rng.uniform(9, 16)
        idx, ddx, ddy = window(cx, cy, Lr * 1.6 + 12)
        al = ddx * math.cos(a) + ddy * math.sin(a)
        ac = -ddx * math.sin(a) + ddy * math.cos(a)
        e = (al / Lr) ** 2 + (ac / Wr) ** 2
        n_e = noise(rng, 20, 200, 0.8, aniso=4, ang=a)[idx]
        stamp_max(rub, idx, _s(1.0 - e + 0.3 * n_e, 0.0, 0.3))
        stamp_max(burnish, idx, _s(1.0 - e / 2.4 + 0.3 * n_e, 0.0, 0.5))
        s_ = noise(rng, 30, 500, 0.4, aniso=30, ang=a)
        stri[idx] = np.where(burnish[idx] > 0, s_[idx], stri[idx])
    rub *= 1 - rivet
    burnish = np.maximum(burnish * (1 - rivet), 0.8 * rivet_top)
    rub = np.maximum(rub, rivet_top * 0.7)
    # Scratches through the scale.
    cv = Canvas()
    for _ in range(30):
        x, y, a = rng.random() * N, rng.random() * N, rng.uniform(0, math.pi)
        L = rng.uniform(15, 70)
        cv.taper([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], rng.uniform(1.0, 1.8), 0.4)
    scratch = cv.get() * (1 - rust)

    h = (dent + 0.0008 * noise(rng, 1, 8, 1.5) + 0.00005 * fibre + plate + rivet_h
         + rust * (0.0003 + 0.0001 * crust) + 0.0004 * flakes - 0.0004 * pitting - 0.0008 * crevice
         - 0.00015 * scratch)
    h = h - 0.0002 * rub + 0.00003 * stri * rub

    scale = _mix((0.11, 0.11, 0.115), (0.20, 0.195, 0.19), _s(noise(rng, 2, 40, 1.2) + 0.1 * fibre, -1.2, 1.2))
    scale = _mix(scale, (0.17, 0.13, 0.10), _s(noise(rng, 4, 80, 1.0), 0.3, 1.5) * 0.6)   # brown oxide
    scale = _mul(scale, 1.0 + 0.03 * fibre + 0.05 * noise(rng, 40, 400, 0.6) + 0.12 * (dent / 0.0012 + 0.6))
    scale = _mix(scale, (0.09, 0.09, 0.095), rivet * 0.6)
    c_rust = _mix((0.43, 0.21, 0.085), (0.20, 0.095, 0.05), _s(crust - 0.8 * flakes, -1.0, 1.4))
    c_rust = _mix(c_rust, (0.56, 0.34, 0.14), _s(noise(rng, 8, 120, 1.0), 1.0, 2.0) * 0.7)
    c_rust = _mix(c_rust, (0.62, 0.38, 0.16), np.clip(flake_edge * 0.4 + lit_edge * 0.8, 0, 1))
    color = _mix(scale, c_rust, rust)
    color = _mul(color, 1.0 - 0.55 * pitting - 0.5 * crevice)
    color = _mix(color, (0.30, 0.30, 0.31), scratch * 0.6)
    color = _mix(color, (0.20, 0.20, 0.21), burnish * (1 - rust * 0.5))
    bright = _mix((0.46, 0.46, 0.47), (0.58, 0.58, 0.59), _s(stri, -1, 1))
    color = _mix(color, bright, rub)
    metal = np.clip(0.6 * (1.0 - rust) * (1.0 - 0.5 * pitting), 0.0, 0.6)
    metal = _mix(metal, 0.85, burnish * (1 - rust))
    metal = _mix(metal, 1.0, rub)
    rough = 0.62 + 0.06 * noise(rng, 3, 60, 1.0) + 0.02 * fibre
    rough = _mix(rough, 0.92, rust)
    rough = _mix(rough, 0.45, scratch * 0.6)
    rough = _mix(rough, 0.4, burnish * (1 - rust))
    rough = _mix(rough, 0.2 + 0.06 * np.abs(stri), rub)
    return color, h, rough, metal, 0.0008


def _weave(gx, gy, wmod_u, wmod_v, seed_i, seed_j):
    """Plain weave heights (warp, weft) on thread coordinates gx, gy (1 unit = 1 thread)."""
    i = np.floor(gx).astype(np.int64)
    j = np.floor(gy).astype(np.int64)
    fx, fy = gx - i, gy - j
    over = ((i + j) % 2) == 0
    width_u = np.clip((0.72 + 0.3 * seed_i[i % len(seed_i)]) * wmod_u, 0.4, 1.0)
    width_v = np.clip((0.72 + 0.3 * seed_j[j % len(seed_j)]) * wmod_v, 0.4, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / width_u) ** 2, 0.0, 1.0))
    cv_ = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / width_v) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    h_warp = cu * (0.55 + 0.45 * np.where(over, ou, -ou))
    h_weft = cv_ * (0.55 + 0.45 * np.where(over, -ov, ov))
    return h_warp, h_weft, i, j


def cloth(rng):
    """Coarse unbleached linen gone grey: slubby plain weave, faded, sweat and dirt
    stains with tide marks, a darned tear, a patch of darker sacking sewn on with big
    stitches and torn loose at one corner, and a small frayed hole."""
    t = UV_TILE["Cloth"]                          # 0.6 m; 128 threads = 4.7 mm per thread
    threads = 128
    gx = (U + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    gy = (V + 0.0012 * noise(rng, 2, 40, 1.2)) * threads
    gi, gj = rng.random(threads), rng.random(threads)
    slub_u = 0.9 + 0.14 * noise(rng, 2, 80, 1.0, aniso=10, ang=math.pi / 2)
    slub_v = 0.9 + 0.14 * noise(rng, 2, 80, 1.0, aniso=10)
    h_warp, h_weft, i, j = _weave(gx, gy, slub_u, slub_v, gi, gj)
    warp = h_warp >= h_weft
    hh = np.maximum(h_warp, h_weft)
    fib = np.where(warp, noise(rng, 20, 500, 0.5, aniso=10, ang=math.pi / 2), noise(rng, 20, 500, 0.5, aniso=10))
    tone = np.where(warp, gi[i % threads], gj[j % threads])

    # Darned tear: an oval of tight darning wool laid across the weave.
    darn = np.zeros_like(U)
    idx, ddx, ddy = window(0.3 * N, 0.62 * N, 80, 60)
    ang = np.arctan2(ddy, ddx)
    row = np.floor((0.62 * N + ddy) / (N / threads / 2.0))
    col = np.floor((0.3 * N + ddx) / (N / threads / 2.0))
    e = np.sqrt((ddx / (62.0 * (0.9 + 0.2 * _hash(row, 5)))) ** 2 + (ddy / (42.0 * (0.9 + 0.2 * _hash(col, 9)))) ** 2)
    e = e * (1 + 0.08 * np.sin(5 * ang + 1.3) + 0.05 * np.sin(9 * ang))
    darn[idx] = _s(1.0 - e, 0.0, 0.08)
    dn = 0.25 * noise(rng, 6, 80, 1.0)
    d_warp, d_weft, _, _ = _weave(gx * 2.0 + dn, gy * 2.0 - dn, 1.0, 1.0, rng.random(32), rng.random(32))
    dh = np.maximum(d_warp, d_weft)
    # Patch of darker sacking, slightly rotated, turned hem, running stitches, a torn corner.
    pcx, pcy, pa = 0.74 * N, 0.27 * N, 0.07
    pw_, ph_ = 88.0, 70.0
    idx_p, ddx, ddy = window(pcx, pcy, 125)
    xr = ddx * math.cos(pa) + ddy * math.sin(pa)
    yr = -ddx * math.sin(pa) + ddy * math.cos(pa)
    box = np.minimum(np.minimum(pw_ - np.abs(xr), ph_ - np.abs(yr)), (pw_ + ph_ - 38) - (xr + yr))
    box = box + 1.5 * noise(rng, 20, 300, 0.8)[idx_p]
    patch, hem, phh, ptone = (np.zeros_like(U) for _ in range(4))
    patch[idx_p] = _s(box, 0.0, 1.5)
    hem[idx_p] = _s(box, 0.0, 1.0) * (1 - _s(box, 8.0, 10.0)) * (0.6 + 0.4 * np.sin(np.clip(box, 0, 9) / 9 * math.pi))
    pw_h, pw_w, pi_, pj_ = _weave((xr + 1000) / 7.0, (yr + 1000) / 7.0, 1.0, 1.0, rng.random(64), rng.random(64))
    phh[idx_p] = np.maximum(pw_h, pw_w)
    ptone[idx_p] = np.where(pw_h >= pw_w, _hash(pi_), _hash(pj_, 1))
    st = Canvas()
    for side in range(4):
        for k in range(11):
            s_ = -1 + 2 * (k + 0.5) / 11
            p, q, a = [(s_ * (pw_ - 14), -(ph_ - 14), 0.0), (pw_ - 14, s_ * (ph_ - 14), math.pi / 2),
                       (-s_ * (pw_ - 14), ph_ - 14, math.pi), (-(pw_ - 14), -s_ * (ph_ - 14), -math.pi / 2)][side]
            if p + q > pw_ + ph_ - 70:
                continue                                              # stitches gone at the torn corner
            a += pa + rng.normal(0, 0.1)
            x0 = pcx + p * math.cos(pa) - q * math.sin(pa)
            y0 = pcy + p * math.sin(pa) + q * math.cos(pa)
            st.line([(x0 - 3.2 * math.cos(a), y0 - 3.2 * math.sin(a)), (x0 + 3.2 * math.cos(a), y0 + 3.2 * math.sin(a))],
                    2.6)
    for _ in range(6):                                               # loose threads at the torn corner
        f = rng.uniform(0.1, 0.9)
        p, q = pw_ - 19 - f * 34, ph_ - 19 - (1 - f) * 34
        x0 = pcx + p * math.cos(pa) - q * math.sin(pa)
        y0 = pcy + p * math.sin(pa) + q * math.cos(pa)
        st.line(random_walk(rng, x0, y0, pa + math.pi / 4 + rng.normal(0, 0.5), 5, rng.integers(4, 9), 0.25), 1.6,
                value=200)
    stitches = st.get()
    # A small hole, frayed.
    hx, hy = 0.12 * N, 0.2 * N
    hole = np.zeros_like(U)
    idx_h, ddx, ddy = window(hx, hy, 30)
    ang = np.arctan2(ddy, ddx)
    rr = 9.0 * (1 + 0.3 * np.sin(3 * ang + 1) + 0.15 * np.sin(7 * ang))
    hole[idx_h] = _s(rr - np.sqrt(ddx ** 2 + ddy ** 2), -1, 1)
    fray = Canvas()
    for a in np.linspace(0, 2 * math.pi, 26, endpoint=False):
        r0 = 9.0 * (1 + 0.3 * math.sin(3 * a + 1)) + 1
        fray.line(random_walk(rng, hx + math.cos(a) * r0, hy + math.sin(a) * r0, a + math.pi + rng.normal(0, 0.5),
                              2.5, rng.integers(2, 5), 0.5), 1.1, value=200)
    frayed = fray.get() * (1 - hole)

    base_h = hh * 0.0011 + 0.00008 * fib
    h = _mix(base_h, np.maximum(base_h * 0.6, 0.0004 + dh * 0.0008), darn)
    h = _mix(h, 0.0012 + phh * 0.0009 + 0.0009 * hem, patch)
    h = h + 0.0006 * stitches - 0.002 * hole + 0.0003 * frayed

    color = np.broadcast_to(np.array([0.56, 0.52, 0.44]), U.shape + (3,))
    color = _mul(color, 0.9 + 0.14 * tone + 0.06 * fib)
    fade = _s(noise(rng, 3, 20, 1.4), -0.4, 1.6)
    color = _mix(color, (0.58, 0.57, 0.53), fade * 0.35)
    dirt = _s(noise(rng, 3, 24, 1.4) + 0.5 * noise(rng, 10, 120, 1.0), 0.0, 2.0)
    color = _mix(color, (0.31, 0.28, 0.22), dirt * 0.4)
    color = _mul(color, 1.0 - 0.25 * (1 - hh) * (0.5 + dirt))                  # grime in the weave
    # Sweat and old stains with tide marks, a few drops of something darker.
    stain = np.zeros_like(U)
    tide = np.zeros_like(U)
    sn = noise(rng, 8, 100, 1.0)
    for _ in range(4):
        cx, cy = rng.random() * N, rng.random() * N
        R = rng.uniform(55, 120)
        idx, ddx, ddy = window(cx, cy, R * 1.6)
        ang = np.arctan2(ddy, ddx)
        rr = R * (1 + 0.22 * np.sin(2 * ang + rng.random() * 6) + 0.12 * np.sin(5 * ang + rng.random() * 6))
        d = np.sqrt(ddx ** 2 + ddy ** 2) / rr + 0.08 * sn[idx]
        stamp_max(stain, idx, _s(1 - d, 0, 0.3))
        stamp_max(tide, idx, np.exp(-((d - 0.97) / 0.035) ** 2))
    color = _mix(color, (0.45, 0.36, 0.19), stain * 0.45)
    color = _mul(color, 1.0 - 0.28 * tide)
    blood = np.zeros_like(U)
    bn = noise(rng, 20, 200, 0.8)
    for _ in range(5):
        cx, cy = rng.random() * N, rng.random() * N
        r = rng.uniform(6, 18)
        idx, ddx, ddy = window(cx, cy, r * 2)
        stamp_max(blood, idx, _s(1 - np.sqrt(ddx ** 2 + (ddy * 0.8) ** 2) / r + 0.25 * bn[idx], 0, 0.4))
    color = _mix(color, (0.24, 0.11, 0.08), blood * 0.55)
    color = _mul(color, 0.5 + 0.5 * hh)                               # weave shadowing
    darn_c = _mix((0.33, 0.28, 0.22), (0.26, 0.22, 0.17), _s(noise(rng, 30, 300, 0.6), -1, 1))
    color = _mix(color, _mul(darn_c, 0.6 + 0.4 * dh), darn)
    patch_c = _mix((0.40, 0.27, 0.21), (0.31, 0.22, 0.17), _s(noise(rng, 8, 100, 1.0), -1, 1))   # faded madder
    patch_c = _mul(patch_c, (0.5 + 0.5 * phh) * (0.9 + 0.2 * ptone) * (1 + 0.25 * hem))
    patch_c = _mix(patch_c, (0.15, 0.12, 0.09), dirt * 0.4)
    color = _mix(color, patch_c, patch)
    color = _mix(color, (0.66, 0.62, 0.52), stitches * 0.85)
    color = _mix(color, (0.03, 0.025, 0.02), hole)
    color = _mix(color, (0.55, 0.51, 0.43), frayed * 0.8)
    rough = 0.9 + 0.04 * noise(rng, 3, 60, 1.0) - 0.08 * stain - 0.1 * blood
    return color, h, rough, np.zeros_like(h), 0.0008


def bone(rng):
    """Old bone from ivory to brown: fibrous cortex and pores, soil and grease stains,
    weathering cracks along the grain with a few across, rat gnaw marks, butcher's knife
    cuts, and a small scrimshaw ship (signed with the same 'I.H' a prisoner scratched into a
    wall block) drawn in soot-filled lines and half worn away."""
    t = UV_TILE["Bone"]                           # 0.3 m, 0.3 mm per pixel
    u = (U + 0.01 * noise(rng, 2, 30, 1.2)) % 1.0
    v = (V + 0.01 * noise(rng, 2, 30, 1.2)) % 1.0
    lamellae = noise(rng, 4, 300, 0.9, aniso=8, ang=0.05)
    pores = _s(noise(rng, 60, 500, 0.3, aniso=3), 2.1, 2.9)
    pits = _s(noise(rng, 20, 200, 0.6), 2.3, 3.0)
    # Weathering cracks: long ones along the grain, short ones across.
    cv = Canvas()
    for _ in range(11):
        x, y = rng.random() * N, rng.random() * N
        pts = random_walk(rng, x, y, rng.normal(0.05, 0.08) + (math.pi if rng.random() < 0.5 else 0), 6,
                          rng.integers(25, 90), 0.05)
        pts = [(px_ + rng.normal(0, 0.5), py + rng.normal(0, 0.5)) for px_, py in pts]
        cv.taper(pts, rng.uniform(1.6, 2.6), 0.5)
        for _ in range(rng.integers(0, 3)):
            k = rng.integers(1, len(pts) - 1)
            cv.taper(random_walk(rng, *pts[k], rng.normal(math.pi / 2, 0.25) * rng.choice([-1, 1]), 5,
                                 rng.integers(3, 8), 0.15), 1.4, 0.4)
    crack = cv.get()
    near_crack = np.clip(blur(crack, 2.5) * 2.5, 0, 1)
    _, edge, _ = voronoi(rng, 9, u, v, 0.9)
    craze = (1.0 - _s(edge, 0.0, 0.008)) * _s(noise(rng, 2, 20, 1.3), 0.6, 1.4)
    # Rat gnawing in one place: paired incisor grooves in a fan.
    gn = Canvas()
    gx, gy = 0.78 * N, 0.7 * N
    for k in range(22):
        a = rng.normal(-1.2, 0.35)
        x, y = gx + rng.normal(0, 22), gy + rng.normal(0, 14)
        L = rng.uniform(8, 20)
        for o in (-1.6, 1.6):
            ox, oy = -math.sin(a) * o, math.cos(a) * o
            gn.taper([(x + ox, y + oy), (x + ox + math.cos(a) * L, y + oy + math.sin(a) * L)], 2.2, 0.8)
    gnaw = gn.get()
    # Butcher's knife cuts in small parallel sets.
    kc = Canvas()
    for _ in range(4):
        x, y, a = rng.random() * N, rng.random() * N, rng.uniform(0, math.pi)
        for k in range(rng.integers(2, 5)):
            o = k * rng.uniform(4, 8)
            L = rng.uniform(20, 50)
            xo, yo = x - math.sin(a) * o, y + math.cos(a) * o
            kc.taper([(xo, yo), (xo + math.cos(a) * L, yo + math.sin(a) * L)], 1.3, 0.3)
    knife = kc.get()
    # Scrimshaw: a three-masted ship on a wavy sea, hatched sails, initials and a year.
    sc = Canvas()
    sx, sy, S = 0.22 * N, 0.14 * N, 170.0            # ~5 cm wide

    def P(x, y):
        return (sx + x * S + rng.normal(0, 0.25), sy + y * S * 0.8 + rng.normal(0, 0.25))

    sc.line([P(0.04, 0.62), P(0.14, 0.76), P(0.84, 0.76), P(0.97, 0.56), P(0.8, 0.6), P(0.04, 0.62)], 1.4)
    sc.line([P(0.1, 0.68), P(0.88, 0.66)], 0.9)
    for k in range(6):
        sc.ellipse(*P(0.25 + 0.1 * k, 0.71), 1.3, 1.3)
    for mx, top in ((0.3, 0.12), (0.52, 0.04), (0.72, 0.14)):
        sc.line([P(mx, 0.61), P(mx, top)], 1.2)
        for y0, y1, wd in ((top + 0.05, top + 0.2, 0.08), (top + 0.23, 0.42 + top * 0.3, 0.11),
                           (0.47 + top * 0.2, 0.56, 0.13)):
            sc.line([P(mx - wd, y0), P(mx + wd, y0), P(mx + wd * 1.05, y1), P(mx, y1 + 0.03), P(mx - wd * 1.05, y1),
                     P(mx - wd, y0)], 1.0)
            for hk in range(3):                                       # hatching
                f = (hk + 1) / 4
                sc.line([P(mx - wd + 2 * wd * f, y0 + 0.01), P(mx - wd * 1.05 + 2.1 * wd * f, y1 - 0.01)], 0.7,
                        value=160)
    sc.line([P(0.52, 0.04), P(0.6, 0.06), P(0.52, 0.08)], 0.9)
    sc.line([P(0.97, 0.56), P(1.12, 0.44)], 1.0)                      # bowsprit and stays
    sc.line([P(1.12, 0.44), P(0.72, 0.14)], 0.7)
    sc.line([P(0.3, 0.12), P(0.04, 0.6)], 0.7)
    for row_ in range(2):
        sc.line([P(-0.05 + k * 0.03, 0.8 + row_ * 0.06 + 0.02 * math.sin(k * 1.3 + row_)) for k in range(41)], 0.9)
    scratch_text(sc, rng, "I.H", sx + 0.08 * S, sy + 0.92 * S, 16, 1.2, jitter=0.03)
    scratch_text(sc, rng, "1692", sx + 0.6 * S, sy + 0.92 * S, 16, 1.2, jitter=0.03)
    wear = _s(noise(rng, 20, 200, 0.9), -1.4, 0.2)
    scrim = sc.get() * (0.35 + 0.65 * wear)

    h = (0.0012 * noise(rng, 1.5, 10, 1.6) + 0.00008 * lamellae - 0.0007 * crack - 0.0002 * near_crack
         - 0.0002 * craze - 0.0003 * pores - 0.0003 * pits - 0.0007 * gnaw - 0.0004 * knife - 0.0001 * scrim)
    color = _mix((0.70, 0.63, 0.49), (0.58, 0.49, 0.36), _s(noise(rng, 2, 40, 1.3), -1.2, 1.2))
    color = _mul(color, 0.93 + 0.025 * lamellae)
    yellowing = _s(noise(rng, 2, 14, 1.5), -0.4, 1.4)
    color = _mix(color, (0.50, 0.39, 0.23), yellowing * 0.5)
    soil = _s(noise(rng, 2, 16, 1.6) + 0.35 * noise(rng, 8, 80, 1.0), 0.3, 1.9)
    color = _mix(color, (0.33, 0.23, 0.13), soil * 0.5)
    grease = _s(noise(rng, 3, 30, 1.3), 0.6, 1.8)
    color = _mix(color, _mul(color, 0.75) * np.array([1.0, 0.95, 0.85]), grease * 0.6)
    grime = np.clip(near_crack * 0.7 + 0.5 * craze + pores + pits, 0, 1)
    color = _mix(color, (0.25, 0.17, 0.10), grime * 0.6)
    color = _mix(color, (0.15, 0.10, 0.06), crack * 0.85)
    color = _mix(color, (0.78, 0.73, 0.60), gnaw * 0.55)              # fresh bone under the teeth
    color = _mix(color, (0.30, 0.22, 0.14), knife * 0.55)
    color = _mix(color, (0.08, 0.06, 0.045), scrim * 0.8)
    rough = 0.56 + 0.05 * noise(rng, 3, 60, 1.0) + 0.3 * np.clip(crack + pores, 0, 1) + 0.08 * soil
    rough = _mix(rough, 0.38, grease * 0.7)
    rough = _mix(rough, 0.8, gnaw)
    return color, h, rough, np.zeros_like(h), 0.0008


def straw(rng):
    """Bedding straw matted flat by bodies: strands lying in combed swirls, broken chaff,
    the bottom layers rotting dark and damp, mould, urine-soaked patches and rat droppings."""
    t = UV_TILE["Straw"]                          # 1 m; ~1 mm per pixel
    ss = 2
    M = N * ss
    zb, ib = Image.new("F", (M, M), 0.0), Image.new("I", (M, M), 0)
    dz, di = ImageDraw.Draw(zb), ImageDraw.Draw(ib)
    flow = noise(rng, 1.5, 6, 1.6)                # matted direction field
    nstraws = 4200
    kinds = np.zeros(nstraws + 1, np.int32)
    for k in range(nstraws):
        x, y = rng.random(2) * N
        chaff = rng.random() < 0.3
        length = rng.uniform(10, 45) if chaff else rng.uniform(70, 280)
        width = rng.uniform(1.6, 3.2) if chaff else rng.uniform(2.2, 4.6)
        ang = 0.4 + 1.3 * flow[int(y) % N, int(x) % N] + rng.normal(0, 0.25 if rng.random() < 0.8 else 1.2)
        bend = rng.normal(0, 0.1)
        pts = [(x, y)]
        for _ in range(4):
            ang += bend
            x += math.cos(ang) * length / 4
            y += math.sin(ang) * length / 4
            pts.append((x, y))
        z = 0.002 + 0.02 * k / nstraws
        kinds[k + 1] = 1 if chaff else 0
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                if max(xs) + ox < -6 or min(xs) + ox > N + 6 or max(ys) + oy < -6 or min(ys) + oy > N + 6:
                    continue
                q = [((px_ + ox) * ss, (py_ + oy) * ss) for px_, py_ in pts]
                w = max(1, int(round(width * ss)))
                dz.line(q, fill=z, width=w, joint="curve")
                dz.line(q, fill=z + 0.0012, width=max(1, int(round(width * 0.45 * ss))), joint="curve")
                di.line(q, fill=k + 1, width=w, joint="curve")
    h = blur(np.asarray(zb.resize((N, N), Image.BOX), dtype=float), 0.6)
    ids = np.asarray(ib.resize((N, N), Image.NEAREST))
    table = rng.random((nstraws + 1, 4))
    depth = np.clip((h - 0.002) / 0.02, 0, 1)                        # 0 = bottom layer, 1 = top
    ridge = np.clip((h - blur(h, 1.5)) / 0.0008, -1, 1)
    color = _mix((0.62, 0.52, 0.30), (0.72, 0.64, 0.45), table[ids, 0])
    color = _mix(color, (0.46, 0.41, 0.32), table[ids, 1] * 0.7)
    color = _mix(color, (0.28, 0.22, 0.14), (table[ids, 2] < 0.18) * 0.8)      # rotten strands
    color = _mul(color, 1.0 + 0.10 * noise(rng, 60, 500, 0.4) + 0.12 * ridge)
    # The lower layers are damp, dark and rotting.
    damp = _s(noise(rng, 2, 20, 1.4), -0.4, 1.4)
    low = (1 - depth) ** 1.6
    color = _mul(color, 0.35 + 0.65 * depth ** 0.8)
    color = _mix(color, (0.17, 0.13, 0.08), low * (0.4 + 0.5 * damp))
    # Underneath: a rotted mat of chopped, blackened stems.
    mf = np.maximum(_s(noise(rng, 20, 400, 0.6, aniso=7, ang=0.5), 0.3, 1.6),
                    _s(noise(rng, 20, 400, 0.6, aniso=7, ang=1.9), 0.5, 1.8))
    mulch = _mix((0.075, 0.058, 0.04), (0.20, 0.15, 0.085), mf)
    mulch = _mix(mulch, (0.08, 0.10, 0.06), _s(noise(rng, 10, 200, 0.8), 1.0, 2.0) * 0.6)   # mould
    color = np.where((ids == 0)[..., None], mulch, color)
    h = h + 0.0008 * mf * (ids == 0)
    mould = _s(noise(rng, 40, 400, 0.5), 1.6, 2.6) * low * damp
    color = _mix(color, (0.10, 0.12, 0.08), mould * 0.8)
    urine = _s(noise(rng, 2, 16, 1.4), 0.7, 1.6)
    color = _mix(color, _mul(color, 0.62) * np.array([1.05, 0.98, 0.75]), urine)
    grime = _s(noise(rng, 1.5, 25, 1.4), 0.3, 1.6)
    color = _mix(color, (0.22, 0.17, 0.11), grime * 0.4)
    # Rat droppings.
    drop = np.zeros_like(U)
    for _ in range(9):
        cx, cy = rng.random() * N, rng.random() * N
        for _ in range(rng.integers(3, 9)):
            x, y = cx + rng.normal(0, 12), cy + rng.normal(0, 12)
            a = rng.uniform(0, math.pi)
            idx, ddx, ddy = window(x, y, 6)
            al = ddx * math.cos(a) + ddy * math.sin(a)
            ac = -ddx * math.sin(a) + ddy * math.cos(a)
            stamp_max(drop, idx, np.sqrt(np.clip(1 - (al / 4.0) ** 2 - (ac / 1.7) ** 2, 0, 1)))
    color = _mix(color, (0.05, 0.04, 0.03), _s(drop, 0, 0.3))
    h = h + 0.0022 * drop
    rough = np.where(ids == 0, 0.95, 0.66 + 0.12 * table[ids, 3]) + 0.1 * grime
    rough = rough * (1 - 0.3 * damp * low) * (1 - 0.25 * urine)
    rough = _mix(rough, 0.5, _s(drop, 0, 0.3))
    return color, h, rough, np.zeros_like(h), 0.006


def water(rng):
    """Dark murky sea water: silt swirls, brown-grey scum gathering in drifting lanes,
    straw, chips and bubbles caught in it; glassy everywhere else."""
    t = UV_TILE["Water"]                          # 3 m, ~3 mm per pixel
    flow_u = 0.03 * noise(rng, 1.5, 8, 1.6)
    flow_v = 0.03 * noise(rng, 1.5, 8, 1.6)
    silt = sample(noise(rng, 2, 40, 1.3), flow_u, flow_v)
    lanes = sample(noise(rng, 2, 24, 1.4, aniso=2.5, ang=0.5), flow_u * 1.5, flow_v * 1.5)
    ridged = 1.0 - np.abs(sample(noise(rng, 4, 80, 1.2), flow_u, flow_v))
    h = (0.016 * noise(rng, 1.5, 10, 2.0, aniso=1.8, ang=0.3)
         + 0.003 * noise(rng, 8, 40, 1.5, aniso=1.4, ang=-0.4)
         + 0.0004 * noise(rng, 30, 160, 1.0))
    color = _mix((0.028, 0.050, 0.044), (0.060, 0.085, 0.060), _s(silt, -1.2, 1.4))
    color = _mix(color, (0.085, 0.080, 0.055), _s(silt, 1.0, 2.2) * 0.6)   # brown silt clouds
    scum = _s(ridged * 1.2 + 0.9 * lanes - 1.6, 0.0, 0.5) * _s(lanes, -0.2, 0.8)
    scum = scum * (0.6 + 0.4 * _s(noise(rng, 30, 300, 0.6), -1, 1))
    foam = _s(noise(rng, 40, 400, 0.5), 0.8, 2.0) * scum
    color = _mix(color, (0.20, 0.19, 0.14), np.clip(scum, 0, 1) * 0.6)
    color = _mix(color, (0.36, 0.35, 0.29), foam * 0.6)
    # Flotsam caught in the scum lanes: straw, chips, bubbles.
    cv = Canvas(ss=3)
    bub = Canvas(ss=3)
    count = 0
    lane_p = np.clip(scum * 1.5 + 0.08, 0, 1)
    while count < 700:
        x, y = rng.random() * N, rng.random() * N
        if rng.random() > lane_p[int(y) % N, int(x) % N]:
            continue
        count += 1
        kind = rng.random()
        if kind < 0.35:
            a = rng.uniform(0, math.pi)
            L = rng.uniform(5, 18)
            cv.line([(x, y), (x + math.cos(a) * L, y + math.sin(a) * L)], rng.uniform(1.0, 1.8), value=255)
        elif kind < 0.55:
            cv.ellipse(x, y, rng.uniform(1.5, 4.5), rng.uniform(1.0, 2.5), rng.uniform(0, math.pi), value=200)
        else:
            r = rng.uniform(0.8, 2.2)
            bub.ellipse(x, y, r, r, value=255)
    bits = cv.get()
    bubbles = bub.get()
    bits_c = _mix((0.35, 0.29, 0.17), (0.16, 0.12, 0.08), _s(noise(rng, 60, 400, 0.5), -1, 1))
    color = _mix(color, bits_c, bits)
    color = _mix(color, (0.45, 0.45, 0.40), bubbles * 0.5)
    h = h + 0.0008 * bits + 0.0012 * bubbles
    rough = 0.04 + 0.03 * _s(noise(rng, 2, 20, 1.2), 0.5, 2.0) + 0.45 * np.clip(scum, 0, 1) + 0.2 * foam
    rough = _mix(rough, 0.75, bits)
    rough = _mix(rough, 0.1, bubbles)
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

"""The Pit V3 - effect textures (fire, smoke, fog, sparks, drips, projector).

Writes RGBA images with clean alpha into output/effects/: the colour of the
transparent pixels is NOT black but the same hue as the effect, so filtering
or mipmapping in SL does not produce a dark halo around it.

  fire_flipbook.png    1024x1024, 4x4 frames (perfect loop 16 -> 1)
  flame_particle.png   256x256, tongue of fire for particles
  smoke.png            256x256, grey puff of smoke
  fog.png              256x256, very soft wisp of fog
  spark.png            64x64, glowing ember
  drip.png             64x128, drop with a trail
  fire_projector.png   512x512, projector light "cookie" (flame behind the grille)

All the noise is periodic (filtered in frequency), which is why the flipbook
fire can rise one full turn and frame 16 links back to frame 1.

Usage:  python scripts/effect_sprites.py
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "output", "effects")
FRAMES = 16          # 4x4
CELL = 256


# ------------------------------------------------------------------ utilities
def noise(h, w, freq, rng):
    """Smooth noise, periodic on both axes (Gaussian low-pass of white noise)."""
    f = np.fft.fft2(rng.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.fftfreq(w)[None, :] * w
    r = np.real(np.fft.ifft2(f * np.exp(-(fx ** 2 + fy ** 2) / (2.0 * freq ** 2))))
    return (r - r.mean()) / (r.std() + 1e-9)


def fbm(h, w, base, octaves, rng, gain=0.5):
    """Sum of octaves of periodic noise, normalised to 0..1."""
    acc = np.zeros((h, w))
    amp = 1.0
    for o in range(octaves):
        acc += amp * noise(h, w, base * 2 ** o, rng)
        amp *= gain
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    return acc


def turbulent(h, w, base, octaves, rng):
    """Turbulent noise (|noise|): thin ridges like tongues of fire."""
    acc = np.zeros((h, w))
    amp = 1.0
    for o in range(octaves):
        acc += amp * np.abs(noise(h, w, base * 2 ** o, rng))
        amp *= 0.55
    return acc / acc.max()


def smooth(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def ramp(i, stops):
    """Interpolates RGB colours along stops [(pos, (r, g, b)), ...]."""
    pos = np.array([p for p, _ in stops])
    cols = np.array([c for _, c in stops])
    return np.stack([np.interp(i, pos, cols[:, k]) for k in range(3)], -1)


FIRE_RAMP = [(0.0, (0.30, 0.03, 0.00)), (0.22, (0.70, 0.10, 0.01)), (0.45, (1.0, 0.36, 0.04)),
             (0.68, (1.0, 0.66, 0.18)), (0.86, (1.0, 0.90, 0.55)), (1.0, (1.0, 0.98, 0.88))]


def save(rgb, alpha, name):
    img = np.concatenate([np.clip(rgb, 0, 1), np.clip(alpha, 0, 1)[..., None]], -1)
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, name))


# ------------------------------------------------------------------ fire
def flame_field(n1, n2, n3, width=0.62):
    """Intensity 0..1 of a CELL x CELL flame built from three layers of noise."""
    rows, cols = np.mgrid[0:CELL, 0:CELL].astype(float)
    x = (cols - (CELL - 1) / 2) / (CELL / 2)
    y = np.clip(((CELL - 1 - rows) / CELL - 0.05) / 0.88, 0.0, 1.2)   # 0 base, 1 tip
    # sideways sway that grows with height
    x = x + (n1 - 0.5) * 0.55 * y ** 1.3 + (n3 - 0.5) * 0.12 * y
    radius = width * np.clip(y / 0.16, 0.0, 1.0) ** 0.5 * np.clip(1.0 - y, 0.0, 1.0) ** 0.6 + 1e-4
    shape = np.clip(1.0 - (x / radius) ** 2, 0.0, 1.0)
    # bright core at the bottom; the turbulence "eats" the flame from the top and
    # leaves loose tongues that break off and rise
    core = shape ** 1.4 * np.clip(1.0 - 1.6 * y, 0.0, 1.0)
    i = 0.55 * shape ** 0.7 + 0.5 * core - (0.95 * n2 + 0.45 * n1 - 0.38) * y ** 0.85 * 1.1 - 0.12 * y
    i = np.clip(np.minimum(i, 1.6 * np.sqrt(shape)), 0.0, 1.0)   # nothing outside the silhouette
    # cell borders always clean (no bleeding between frames)
    border = smooth(0, 10, cols) * smooth(0, 10, CELL - 1 - cols) * smooth(0, 6, rows) * smooth(0, 6, CELL - 1 - rows)
    return i * border


def flame_color(i):
    rgb = ramp(np.clip(i, 0, 1), FIRE_RAMP)
    alpha = smooth(0.02, 0.32, i)
    return rgb, alpha


def fire_flipbook(rng):
    period = 2 * CELL                       # the noise rises one full turn in 16 frames
    a = fbm(period, CELL, 2.0, 4, rng)
    b = turbulent(period, CELL, 4.0, 4, rng)
    c = fbm(period, CELL, 6.0, 3, rng)
    rows = np.arange(CELL)[:, None]
    sheet_rgb = np.zeros((4 * CELL, 4 * CELL, 3))
    sheet_a = np.zeros((4 * CELL, 4 * CELL))

    def frame(k):
        d1 = (rows + k * period // FRAMES) % period        # slow layer: 1 turn
        d2 = (rows + 2 * k * period // FRAMES) % period    # fast layer: 2 turns
        d3 = (rows + 3 * k * period // FRAMES) % period
        cols = np.arange(CELL)[None, :]
        return flame_field(a[d1, cols], b[d2, cols], c[d3, cols])

    for k in range(FRAMES):
        rgb, alpha = flame_color(frame(k))
        r, q = divmod(k, 4)
        sheet_rgb[r * CELL:(r + 1) * CELL, q * CELL:(q + 1) * CELL] = rgb
        sheet_a[r * CELL:(r + 1) * CELL, q * CELL:(q + 1) * CELL] = alpha
    # loop check: "frame 17" is identical to frame 1
    assert np.allclose(frame(FRAMES), frame(0))
    save(sheet_rgb, sheet_a, "fire_flipbook.png")


def flame_particle(rng):
    a = fbm(CELL, CELL, 1.5, 3, rng)
    b = fbm(CELL, CELL, 3.0, 3, rng)
    i = flame_field(0.5 + (a - 0.5) * 0.5, b * 0.6, a, width=0.7)
    rgb, alpha = flame_color(i)
    save(rgb, alpha * 0.95, "flame_particle.png")


# ------------------------------------------------------------------ smoke, fog, spark, drip
def smoke(rng, n=256):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    cloud = fbm(n, n, 2.5, 5, rng)
    puff = np.zeros((n, n))
    for _ in range(7):                       # several blobs that make up the puff
        cx, cy, s = rng.uniform(-0.35, 0.35), rng.uniform(-0.3, 0.3), rng.uniform(0.14, 0.24)
        puff = np.maximum(puff, np.exp(-((cols - cx) ** 2 + (rows - cy) ** 2) / (2 * s * s)))
    alpha = puff * (0.3 + 1.0 * cloud) * smooth(1.0, 0.75, r)
    alpha = smooth(0.12, 0.85, alpha) * 0.85
    grey = 0.42 + 0.22 * cloud
    rgb = np.stack([grey, grey * 0.98, grey * 0.95], -1)
    save(rgb, alpha, "smoke.png")


def fog(rng, n=256):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    cloud = fbm(n, n, 1.5, 5, rng)
    wisp = np.exp(-(cols ** 2) / 0.35 - (rows / 0.55) ** 2 / 0.6)         # stretched horizontally
    alpha = wisp * (0.25 + cloud) * smooth(1.0, 0.55, np.sqrt(cols ** 2 + rows ** 2))
    alpha = np.clip(alpha, 0, 1) * 0.55
    rgb = np.stack([0.78 + 0.12 * cloud, 0.82 + 0.1 * cloud, 0.84 + 0.1 * cloud], -1)
    save(rgb, alpha, "fog.png")


def spark(n=64):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    core = np.exp(-(r / 0.12) ** 2)
    halo = np.exp(-(r / 0.38) ** 2)
    i = np.clip(core + 0.55 * halo, 0, 1)
    rgb = ramp(i, [(0.0, (0.9, 0.25, 0.02)), (0.5, (1.0, 0.6, 0.15)), (1.0, (1.0, 0.97, 0.85))])
    alpha = np.clip(1.2 * core + 0.7 * halo, 0, 1) * smooth(1.0, 0.8, r)
    save(rgb, alpha, "spark.png")


def drip(w=64, h=128):
    rows, cols = np.mgrid[0:h, 0:w].astype(float)
    x = (cols - (w - 1) / 2) / (w / 2)
    y = rows / (h - 1)                                     # 0 top, 1 bottom
    head = np.exp(-((x / 0.32) ** 2 + ((y - 0.80) / 0.11) ** 2))
    trail = np.exp(-(x / (0.07 + 0.12 * y)) ** 2) * smooth(0.05, 0.75, y) * 0.5
    alpha = np.clip(head + trail, 0, 1) * smooth(0.0, 0.05, 1 - y)
    highlight = np.exp(-(((x + 0.1) / 0.1) ** 2 + ((y - 0.77) / 0.035) ** 2))
    rgb = np.stack([0.62 + 0.38 * highlight, 0.72 + 0.28 * highlight, 0.78 + 0.22 * highlight], -1)
    save(rgb, alpha * 0.85, "drip.png")


# ------------------------------------------------------------------ projector
def fire_projector(rng, n=512):
    """Irregular warm light seen through the cage of a lantern (bars and iron band)."""
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    blotches = fbm(n, n, 3.0, 5, rng)
    light = np.exp(-(r / 0.62) ** 2) * (0.55 + 0.7 * blotches)
    # vertical bars, slightly curved (the cage is round) and blurry
    xb = cols + 0.05 * rows ** 2 * np.sign(cols)
    bars = 1.0 - 0.85 * np.clip(np.cos(xb * np.pi * 3.0) * 1.6 - 0.75, 0, 1)
    bands = 1.0 - 0.8 * np.exp(-((rows + 0.38) / 0.05) ** 2) - 0.6 * np.exp(-((rows - 0.47) / 0.07) ** 2)
    chain = 1.0 - 0.55 * np.exp(-((cols - 0.25 * rows - 0.55) / 0.04) ** 2) * (np.sin(rows * 40) > -0.2)
    i = light * bars * bands * chain
    i = i / i.max() * smooth(1.0, 0.82, r)                 # black border: no cookie stretching
    rgb = ramp(np.clip(i, 0, 1), [(0.0, (0.0, 0.0, 0.0)), (0.35, (0.55, 0.16, 0.03)),
                                  (0.7, (1.0, 0.55, 0.18)), (1.0, (1.0, 0.86, 0.6))])
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(
        os.path.join(OUT, "fire_projector.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(1666)
    fire_flipbook(rng)
    flame_particle(rng)
    smoke(rng)
    fog(rng)
    spark()
    drip()
    fire_projector(rng)
    for fn in sorted(os.listdir(OUT)):
        im = Image.open(os.path.join(OUT, fn))
        print(f"  {fn:22s} {im.size[0]}x{im.size[1]} {im.mode}")


if __name__ == "__main__":
    main()

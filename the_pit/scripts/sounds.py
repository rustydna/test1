#!/usr/bin/env python3
"""The Pit V4 - procedural sound design.

Every sound of the build is synthesised from physical models (no recorded samples) and written as
a Second Life upload-ready WAV: 16-bit PCM, mono, 44.1 kHz, shorter than 10 s, sample peak at
-1 dBFS, no DC offset, click-free starts and ends, and (for the *_loop and ambient_wind sounds) an
exactly periodic waveform so that llLoopSound / SOUND_LOOP repeats it with no seam.

    python the_pit/scripts/sounds.py                    # build, verify and preview everything
    python the_pit/scripts/sounds.py fire_loop drip_2   # only these
    python the_pit/scripts/sounds.py --no-previews      # skip the PNG previews

Output: the_pit/output/sounds/<name>.wav, previews/<name>.png (waveform + spectrogram; loops are
drawn twice in a row with the seam marked and zoomed) and sounds_report.json (all the checks).

Only numpy is required (Pillow for the previews). scipy is NOT used: it is not installed in the
build environment, and the few DSP pieces needed (biquads, FFT convolution, STFT synthesis, a
look-ahead limiter, BS.1770 loudness) are implemented here in a few lines each. Everything is
deterministic: each sound draws from its own random generator seeded with its name.

Toolbox (all physically motivated):
  * Filtered noise: Gaussian noise shaped in the frequency domain; RBJ biquads applied exactly
    through their frequency response (causal, with enough zero padding; circular for loops).
  * Modal synthesis: impacts on iron, bronze and wood are sums of exponentially decaying
    sinusoids at the body's (inharmonic) mode frequencies, with T60 = 6.91 Q / (pi f) and a
    half-sine contact force that sets the brightness (short, hard contact = more treble).
  * Stick-slip friction: a spring-loaded contact dragged at velocity v(t) sticks until the
    spring force reaches the (randomly varying) static friction limit, then slips and re-sticks;
    every slip is a force pulse that excites the body modes. Pulse rate follows the drag speed,
    which is what makes a creak glide in pitch.
  * Granular fire: Poisson crackle grains with a heavy-tailed size law, crackle clusters (fibres
    breaking in cascades), pops with an ember ring and a low thump, steam sizzles, over a
    turbulent combustion roar modulated by flame puffing (f ~ 1.5/sqrt(D)) and flutter.
  * Bubbles (van den Doel 2005): Minnaert frequency f0 = 3.26/r, damping 0.13/r + 0.0072 r^-1.5,
    pitch rising as the bubble nears the surface. Used for drips, splash, sea gurgles and pitch.
  * Rooms: a shoebox image-source model for the early reflections (stone walls, absorption
    derived from Sabine's formula and the room's RT60) plus a stochastic late tail whose decay
    is frequency dependent (octave-band RT60s, faster in the treble) and whose level follows the
    Sabine critical distance, so far sources really sound far. Convolution is done by FFT;
    loops are convolved circularly so the reverb tail wraps across the seam.
  * Loops are generated periodic by construction (circular filtering, events whose tails wrap
    around to the start, circular STFT overlap-add, circular reverb and limiter). That is the
    limit case of a crossfade - the seam is as continuous as any other point - and it is
    verified numerically (step, slope and click energy at the seam).

Sounds (the LSL scripts pick them up by these names; see INSTALL.txt):
  fire_loop, torch_loop, sea_loop, ambient_wind  (seamless loops)
  drip_1..3, chains_1..2, door_creak, lock_clank, portcullis_chain, press_gang_bell, whip_crack,
  splash, rack_creak, ambient_rats, ambient_creak, ambient_boom, ambient_drip_echo  (one-shots)
"""

import argparse
import json
import os
import sys
import time
import wave
import zlib

import numpy as np

SR = 44100
TWO_PI = 2.0 * np.pi
LN1000 = 6.907755278982137          # ln(1000): T60 <-> decay rate
PEAK_DBFS = -1.0
MAX_SECONDS = 10.0                  # Second Life upload limit (kept strictly below)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "output", "sounds"))
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")


# =============================================================================================
# Basic helpers
# =============================================================================================

def rng_for(name, salt=""):
    """Deterministic random generator per sound (and per sub-part)."""
    return np.random.default_rng(zlib.crc32(("the_pit/%s/%s" % (name, salt)).encode()))


def ns(seconds):
    """Seconds -> samples."""
    return int(round(seconds * SR))


def fast_len(n):
    """Smallest 2^a 3^b 5^c >= n (an FFT-friendly size)."""
    best = 1 << max(0, int(n - 1).bit_length())
    p5 = 1
    while p5 < best:
        p35 = p5
        while p35 < best:
            p = p35
            while p < n:
                p *= 2
            best = min(best, p)
            p35 *= 3
        p5 *= 5
    return best


def fit(x, n):
    """Trim or zero-pad to n samples."""
    if len(x) >= n:
        return x[:n].copy()
    return np.concatenate([x, np.zeros(n - len(x))])


def loguniform(rng, lo, hi, size=None):
    return np.exp(rng.uniform(np.log(lo), np.log(hi), size))


def smoothstep(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3.0 - 2.0 * u)


def add(out, sig, start, loop=False):
    """Mix sig into out at sample `start`; for loops the part beyond the end wraps to the start."""
    n = len(out)
    start = int(start)
    if loop:
        idx = (start + np.arange(len(sig))) % n
        np.add.at(out, idx, sig)
    else:
        a, b = max(start, 0), min(start + len(sig), n)
        if b > a:
            out[a:b] += sig[a - start:b - start]


def band(f, lo=None, hi=None, olo=2, ohi=2):
    """Butterworth-like band magnitude |H(f)| (lo/hi: -3 dB corners, o*: orders)."""
    f = np.maximum(np.asarray(f, float), 1e-9)
    g = np.ones_like(f)
    if lo is not None:
        g = g / np.sqrt(1.0 + (lo / f) ** (2 * olo))
    if hi is not None:
        g = g / np.sqrt(1.0 + (f / hi) ** (2 * ohi))
    return g


def tilt(f, db_per_oct, ref=1000.0):
    """Spectral tilt (e.g. -3 dB/oct = pink)."""
    return (np.maximum(np.asarray(f, float), 1.0) / ref) ** (db_per_oct / 6.0206)


def lorentz(f, fc, bw):
    return 1.0 / (1.0 + ((f - fc) / bw) ** 2)


# =============================================================================================
# Filters (RBJ biquads, applied through their exact frequency response)
# =============================================================================================

def bq(kind, f0, q=0.7071067811865476, gain_db=0.0):
    """RBJ audio-EQ-cookbook biquad -> (b, a), normalised so a[0] = 1."""
    f0 = min(float(f0), 0.48 * SR)
    w0 = TWO_PI * f0 / SR
    cw, sw = np.cos(w0), np.sin(w0)
    al = sw / (2.0 * q)
    A = 10.0 ** (gain_db / 40.0)
    if kind == "lp":
        b, a = [(1 - cw) / 2, 1 - cw, (1 - cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == "hp":
        b, a = [(1 + cw) / 2, -(1 + cw), (1 + cw) / 2], [1 + al, -2 * cw, 1 - al]
    elif kind == "bp":
        b, a = [al, 0.0, -al], [1 + al, -2 * cw, 1 - al]
    elif kind == "peak":
        b, a = [1 + al * A, -2 * cw, 1 - al * A], [1 + al / A, -2 * cw, 1 - al / A]
    elif kind in ("lshelf", "hshelf"):
        s = 2.0 * np.sqrt(A) * al
        if kind == "lshelf":
            b = [A * ((A + 1) - (A - 1) * cw + s), 2 * A * ((A - 1) - (A + 1) * cw), A * ((A + 1) - (A - 1) * cw - s)]
            a = [(A + 1) + (A - 1) * cw + s, -2 * ((A - 1) + (A + 1) * cw), (A + 1) + (A - 1) * cw - s]
        else:
            b = [A * ((A + 1) + (A - 1) * cw + s), -2 * A * ((A - 1) + (A + 1) * cw), A * ((A + 1) + (A - 1) * cw - s)]
            a = [(A + 1) - (A - 1) * cw + s, 2 * ((A - 1) - (A + 1) * cw), (A + 1) - (A - 1) * cw - s]
    elif kind in ("lp1", "hp1"):
        k = np.tan(w0 / 2.0)
        a = [1.0, (k - 1) / (k + 1), 0.0]
        b = [k / (1 + k), k / (1 + k), 0.0] if kind == "lp1" else [1 / (1 + k), -1 / (1 + k), 0.0]
    else:
        raise ValueError(kind)
    b, a = np.asarray(b, float), np.asarray(a, float)
    return b / a[0], a / a[0]


def _response(sections, nfft):
    z1 = np.exp(-2j * np.pi * np.arange(nfft // 2 + 1) / nfft)
    z2 = z1 * z1
    h = np.ones(len(z1), complex)
    for b, a in sections:
        h *= (b[0] + b[1] * z1 + b[2] * z2) / (a[0] + a[1] * z1 + a[2] * z2)
    return h


def _ring_samples(sections):
    """Samples for the cascade's impulse response to decay by 120 dB."""
    tot = 64
    for _, a in sections:
        poles = np.roots(a) if (a[1] != 0 or a[2] != 0) else np.array([0.0])
        r = float(np.max(np.abs(poles))) if len(poles) else 0.0
        if r > 1e-9:
            tot += int(np.log(1e-6) / np.log(min(r, 0.9999999)))
    return tot


def filt(x, *sections, loop=False):
    """Filter x through a cascade of biquads. One-shots: causal with zero padding (exactly the
    linear IIR output); loops: circular, i.e. the periodic steady-state response."""
    if not sections:
        return x
    n = len(x)
    if loop:
        return np.fft.irfft(np.fft.rfft(x) * _response(sections, n), n)
    nfft = fast_len(n + min(_ring_samples(sections), 10 * SR))
    return np.fft.irfft(np.fft.rfft(x, nfft) * _response(sections, nfft), nfft)[:n]


def conv(x, h, loop=False):
    """FFT convolution. Loops: circular convolution with h folded onto the loop length."""
    if loop:
        n = len(x)
        hf = np.zeros(n)
        for i in range(0, len(h), n):
            seg = h[i:i + n]
            hf[:len(seg)] += seg
        return np.fft.irfft(np.fft.rfft(x) * np.fft.rfft(hf), n)
    m = len(x) + len(h) - 1
    nfft = fast_len(m)
    return np.fft.irfft(np.fft.rfft(x, nfft) * np.fft.rfft(h, nfft), nfft)[:m]


# =============================================================================================
# Noise, control signals, STFT synthesis
# =============================================================================================

def noise(n, rng, mag=None):
    """Unit-RMS Gaussian noise, periodic with period n, coloured by |H(f)| = mag(f)."""
    n = int(n)
    spec = rng.standard_normal(n // 2 + 1) + 1j * rng.standard_normal(n // 2 + 1)
    if mag is not None:
        spec *= mag(np.fft.rfftfreq(n, 1.0 / SR))
    spec[0] = 0.0
    y = np.fft.irfft(spec, n)
    s = y.std()
    return y / s if s > 0 else y


def lfo(n, lo, hi, rng):
    """Smooth random control signal (unit std) with content between lo and hi Hz, periodic in n."""
    return noise(n, rng, lambda f: band(f, lo, hi, 2, 3))


def _divisor_near(n, target):
    for d in range(0, target):
        for c in (target - d, target + d):
            if c > 16 and n % c == 0:
                return c
    return target


def stft_noise(n, mag_fn, rng, loop=True, hop=512, win_hops=8):
    """Noise with a time-varying magnitude spectrum: random-phase frames, Hann windows,
    overlap-add normalised to constant power. mag_fn(t_seconds[frames], f_hz[bins]) returns
    linear magnitudes (frames x bins). Loops: frames wrap around (periodic output)."""
    if loop:
        hop = _divisor_near(n, hop)
    w = win_hops * hop
    w += w % 2
    win = 0.5 - 0.5 * np.cos(TWO_PI * np.arange(w) / w)
    if loop:
        starts = np.arange(n // hop) * hop
    else:
        starts = np.arange(-w, n + hop, hop)
    tc = (starts + w / 2.0) / SR
    f = np.fft.rfftfreq(w, 1.0 / SR)
    out = np.zeros(n)
    norm = np.zeros(n)
    chunk = max(1, 2_000_000 // w)
    for c in range(0, len(starts), chunk):
        st = starts[c:c + chunk]
        mag = mag_fn(tc[c:c + chunk], f)
        ph = rng.uniform(0, TWO_PI, mag.shape)
        frames = np.fft.irfft(mag * np.exp(1j * ph), w, axis=1) * win
        idx = st[:, None] + np.arange(w)[None, :]
        wts = np.broadcast_to(win ** 2, frames.shape)
        if loop:
            idx = idx % n
            out += np.bincount(idx.ravel(), frames.ravel(), minlength=n)
            norm += np.bincount(idx.ravel(), wts.ravel(), minlength=n)
        else:
            ok = (idx >= 0) & (idx < n)
            out += np.bincount(idx[ok], frames[ok], minlength=n)
            norm += np.bincount(idx[ok], wts[ok], minlength=n)
    return out / np.sqrt(np.maximum(norm, 1e-9))


# =============================================================================================
# Excitations and resonators
# =============================================================================================

def contact_weight(f, tau):
    """Spectrum of a half-sine contact force of duration tau (flat, then -12 dB/oct)."""
    if tau <= 0:
        return np.ones_like(f)
    return 1.0 / (1.0 + (np.asarray(f) * tau / 0.6) ** 2)


def modes(freqs, t60, amps, dur, tau=0.0, t_off=0.0, phases=None):
    """Sum of exponentially decaying sinusoids (modal synthesis). t_off: sub-sample start (s).
    The onset is shaped by the contact duration tau so that it is never a hard edge."""
    freqs, t60, amps = (np.atleast_1d(np.asarray(v, float)) for v in (freqs, t60, amps))
    t60 = np.broadcast_to(t60, freqs.shape)
    amps = np.broadcast_to(amps, freqs.shape) * contact_weight(freqs, tau)
    n = ns(dur)
    t = np.maximum(np.arange(n) / SR - t_off, 0.0)
    y = np.zeros(n)
    for i, (f, T, a) in enumerate(zip(freqs, t60, amps)):
        if f >= 0.45 * SR or a == 0:
            continue
        ph = 0.0 if phases is None else phases[i]
        y += a * np.exp(-LN1000 * t / T) * np.sin(TWO_PI * f * t + ph)
    ramp = max(tau, 2.0 / SR)
    y *= smoothstep(t / ramp)
    return y


def random_modes(rng, count, fmin, fmax, q=(40, 150), tilt_db=-3.0):
    """Inharmonic mode set: log-uniform frequencies, Q -> T60 = 6.91 Q / (pi f)."""
    f = np.sort(loguniform(rng, fmin, fmax, count))
    qq = loguniform(rng, q[0], q[1], count)
    t60 = LN1000 * qq / (np.pi * f)
    a = rng.uniform(0.3, 1.0, count) * (f / fmin) ** (tilt_db / 6.0206)
    return f, t60, a


def burst(dur, tau, rng, mag=None, attack=0.0002):
    """Exponentially decaying noise burst (optionally coloured)."""
    n = max(8, ns(dur))
    t = np.arange(n) / SR
    env = np.exp(-t / tau) * smoothstep(t / max(attack, 1.0 / SR))
    return noise(n, rng, mag) * env


def pulse_train(n, times, amps, width, loop=False):
    """Hann-shaped force pulses (slips, clicks) at fractional times (s)."""
    times = np.asarray(times, float)
    amps = np.asarray(amps, float)
    if len(times) == 0:
        return np.zeros(n)
    w = max(width * SR, 1.5)
    L = int(np.ceil(w)) + 2
    st = np.floor(times * SR).astype(int)
    k = st[:, None] + np.arange(L)[None, :]
    u = (k - times[:, None] * SR) / w
    vals = np.where((u >= 0) & (u <= 1), np.sin(np.pi * u) ** 2, 0.0) * amps[:, None]
    if loop:
        k = k % n
        return np.bincount(k.ravel(), vals.ravel(), minlength=n)
    ok = (k >= 0) & (k < n)
    return np.bincount(k[ok], vals[ok], minlength=n)


def stick_slip(v, load, rng, mu_s=1.0, mu_k=0.6, jitter=0.05, slow_jitter=0.0, v_ref=40.0):
    """Quasi-static stick-slip of a contact dragged through a unit spring at velocity v(t)
    (per-sample array) under normal load(t). The contact sticks until the spring force reaches
    the static limit mu_s*load, then slips with an undamped overshoot, leaving (2 mu_k - mu_s)*load.
    The static limit varies from slip to slip (surface roughness): its spread is `jitter` times
    (mu_s - mu_k), i.e. roughly the relative spread of the slip period, plus `slow_jitter` that
    fades in at drag speeds below v_ref (creep makes slow creaks crackly and irregular).
    Returns slip times (s) and force drops. Slip rate ~ v / (2 (mu_s - mu_k) load): the faster
    the drag, the higher the creak pitch."""
    n = len(v)
    span = mu_s - mu_k

    def draw(k):
        j = jitter + slow_jitter * np.exp(-abs(v[min(k, n - 1)]) / v_ref)
        return mu_s + span * max(-0.85, j * rng.standard_normal())

    X = np.cumsum(v) / SR
    times, drops = [], []
    i = 0
    f0 = 0.5 * mu_k * load[0]
    xs = X[0]
    thr = draw(0)
    while i < n - 1:
        j = min(n, i + 4096)
        F = f0 + (X[i:j] - xs) - thr * load[i:j]
        hit = np.flatnonzero(F >= 0)
        if len(hit) == 0:
            i = j
            continue
        h = hit[0]
        k = i + h
        if h > 0:
            fa, fb = F[h - 1], F[h]
            tcross = (k - 1 + fa / (fa - fb)) / SR
        else:
            tcross = k / SR
        top = thr * load[k]
        res = max((2 * mu_k - thr) * load[k], 0.05 * load[k])
        times.append(tcross)
        drops.append(top - res)
        f0, xs = res, X[k]
        i = k + 1
        thr = draw(k)
    return np.array(times), np.array(drops)


def bubble(r, amp=1.0, xi=0.1, dur=None):
    """Minnaert bubble (van den Doel 2005): f0 = 3.26/r Hz (r in m), damping
    d = 0.13/r + 0.0072 r^-1.5, pitch rising as f0 (1 + xi d t) while it rises to the surface."""
    f0 = 3.26 / r
    d = 0.13 / r + 0.0072 * r ** -1.5
    T = dur if dur else min(7.0 / d, 1.5)
    t = np.arange(max(8, ns(T))) / SR
    f = f0 * (1.0 + xi * d * t)
    ph = TWO_PI * np.cumsum(f) / SR
    return amp * np.sin(ph) * np.exp(-d * t) * smoothstep(t / 0.0004)


def drop_plink(f0, rise, tau, amp=1.0, dur=None, click=0.15, rng=None):
    """Water drop into a pool: the entrained bubble rings with a fast upward chirp
    (f0 -> f0 (1 + rise) over ~2 tau) plus a faint impact click."""
    T = dur if dur else 8 * tau
    t = np.arange(ns(T)) / SR
    f = f0 * (1.0 + rise * (1.0 - np.exp(-t / (1.3 * tau))))
    y = np.sin(TWO_PI * np.cumsum(f) / SR) * np.exp(-t / tau) * smoothstep(t / 0.0005)
    if click > 0 and rng is not None:
        c = burst(0.004, 0.0003, rng, lambda ff: band(ff, 1500, 12000, 1, 2))
        y[:len(c)] += click * c
    return amp * y


# =============================================================================================
# Rooms: image-source early reflections + frequency-dependent stochastic tail
# =============================================================================================

BANDS = np.array([63, 125, 250, 500, 1000, 2000, 4000, 8000, 16000], float)

ROOMS = {
    # dims (m); RT60 per octave band 63 Hz .. 16 kHz (s): bare stone keeps the bass and mids
    # ringing; the treble dies faster (scattering off rough blocks, air absorption).
    "cell":    dict(dims=(5.0, 7.6, 4.3), rt=(1.5, 1.6, 1.5, 1.4, 1.3, 1.15, 0.9, 0.6, 0.35)),
    "cave":    dict(dims=(6.5, 9.0, 5.0), rt=(1.9, 2.0, 1.9, 1.8, 1.6, 1.35, 1.0, 0.65, 0.4)),
    "pit":     dict(dims=(10.0, 26.0, 7.0), rt=(2.2, 2.4, 2.3, 2.1, 1.9, 1.6, 1.2, 0.8, 0.45)),
    "hall":    dict(dims=(16.0, 28.0, 11.0), rt=(3.6, 3.9, 3.7, 3.4, 3.0, 2.5, 1.8, 1.1, 0.6)),
    "cistern": dict(dims=(7.0, 9.0, 6.0), rt=(2.0, 2.3, 2.2, 2.1, 1.9, 1.6, 1.2, 0.8, 0.45)),
    "gate":    dict(dims=(12.0, 16.0, 9.0), rt=(1.3, 1.3, 1.25, 1.15, 1.05, 0.9, 0.7, 0.5, 0.3),
                    open_top=True),
}
_IR_CACHE = {}


def room_ir(room, dist, tail=1.0, er_ms=90.0, early=1.0):
    """Impulse response of a stone room for a source `dist` metres from the listener.
    Direct sound = 1 at t = 0. Early part: shoebox image sources (Allen & Berkley) with wall
    reflection factor beta = sqrt(1 - alpha), alpha from Sabine (RT60 at 1 kHz). Late part:
    Gaussian noise split into octave bands, each decaying with its own RT60, fading in up to the
    mixing time; total reverberant energy (dist / r_c)^2 * tail with the Sabine critical distance
    r_c = 0.057 sqrt(V / RT60). `tail` and `early` scale the late and early parts (artistic
    control for sources that should stay close and crisp)."""
    key = (room, round(dist, 3), round(tail, 4), er_ms, early)
    if key in _IR_CACHE:
        return _IR_CACHE[key]
    p = ROOMS[room]
    L = np.array(p["dims"], float)
    rt = np.array(p["rt"], float)
    V = L.prod()
    S = 2 * (L[0] * L[1] + L[0] * L[2] + L[1] * L[2])
    rt_mid = rt[4]
    alpha = float(np.clip(0.161 * V / (S * rt_mid), 0.02, 0.95))
    beta = np.sqrt(1 - alpha)
    rng = rng_for("room", "%s/%.3f" % (room, dist))
    lis = np.array([0.37 * L[0], 0.41 * L[1], 1.65])
    d = rng.normal(size=3)
    d[2] *= 0.25
    d /= np.linalg.norm(d)
    src = np.clip(lis + dist * d, 0.4, L - 0.4)
    d0 = max(0.3, float(np.linalg.norm(src - lis)))
    c = 343.0
    t_er = er_ms / 1000.0
    walls = [(beta, beta), (beta, beta), (beta, 0.0 if p.get("open_top") else beta)]
    comps = []
    for ax in range(3):
        N = int(np.ceil(c * (t_er + d0 / c) / (2 * L[ax]))) + 1
        m = np.arange(-N, N + 1)
        pos, gain = [], []
        for par in (0, 1):
            pos.append((1 - 2 * par) * src[ax] + 2 * m * L[ax] - lis[ax])
            gain.append(walls[ax][0] ** np.abs(m - par) * walls[ax][1] ** np.abs(m))
        comps.append((np.concatenate(pos), np.concatenate(gain)))
    (dx, gx), (dy, gy), (dz, gz) = comps
    D = np.sqrt(dx[:, None, None] ** 2 + dy[None, :, None] ** 2 + dz[None, None, :] ** 2)
    G = gx[:, None, None] * gy[None, :, None] * gz[None, None, :]
    delay = (D - d0) / c
    sel = (delay > 0.5 / SR) & (delay <= t_er) & (G > 0)
    n_ir = ns(min(1.1 * rt.max(), 5.0))
    refl = np.zeros(n_ir)
    pos = delay[sel] * SR
    amp = G[sel] * d0 / D[sel]
    i0 = np.floor(pos).astype(int)
    fr = pos - i0
    refl += np.bincount(i0, amp * (1 - fr), minlength=n_ir)[:n_ir]
    refl += np.bincount(i0 + 1, amp * fr, minlength=n_ir + 1)[:n_ir]
    refl = filt(refl, bq("lp1", 7500.0))         # each bounce off rough stone loses treble
    t1 = float(delay[sel].min()) if sel.any() else 0.003
    t_mix = max(t1 + 0.01, min(0.08, np.sqrt(V) / 1000.0 * 1.5))
    t = np.arange(n_ir) / SR
    X = np.fft.rfft(rng.standard_normal(n_ir))
    f = np.maximum(np.fft.rfftfreq(n_ir, 1.0 / SR), 1.0)
    late = np.zeros(n_ir)
    for i, (fc, T) in enumerate(zip(BANDS, rt)):
        w = np.clip(1.0 - np.abs(np.log2(f / fc)), 0.0, 1.0)
        if i == 0:
            w[f < fc] = 1.0
        if i == len(BANDS) - 1:
            w[f > fc] = 1.0
        late += np.fft.irfft(X * w, n_ir) * np.exp(-LN1000 * t / T)
    late *= smoothstep((t - t1) / (t_mix - t1))
    late = filt(late, bq("hp", 30.0, 0.6))
    rc = 0.057 * np.sqrt(V / rt_mid)
    late *= np.sqrt((d0 / rc) ** 2 * tail / np.sum(late ** 2))
    h = early * refl + late
    h[0] += 1.0
    _IR_CACHE[key] = h
    return h


def reverb(x, room, dist, tail=1.0, loop=False, dry=0.0, early=1.0):
    """Place x in a stone room (direct + reflections + tail). dry adds extra close signal."""
    y = conv(x, room_ir(room, dist, tail, early=early), loop=loop)
    if dry:
        y[:len(x)] += dry * x
    return y


# =============================================================================================
# Mastering: limiter, loudness, normalisation, fades, dither
# =============================================================================================

def running_min(x, w, loop):
    """Centred running minimum over an odd window w (van Herk / Gil-Werman, O(n))."""
    h = w // 2
    n = len(x)
    if loop:
        xp = np.concatenate([x[-h:], x, x[:h]]) if h else x.copy()
    else:
        xp = np.concatenate([np.ones(h), x, np.ones(h)])
    m = len(xp)
    nb = -(-m // w)
    xq = np.concatenate([xp, np.full(nb * w - m + w, np.inf)])
    nb = len(xq) // w
    xq = xq[:nb * w].reshape(nb, w)
    pre = np.minimum.accumulate(xq, axis=1).ravel()
    suf = np.minimum.accumulate(xq[:, ::-1], axis=1)[:, ::-1].ravel()
    i = np.arange(n)
    return np.minimum(suf[i], pre[i + w - 1])


def moving_avg(x, w, loop):
    h = w // 2
    xp = np.concatenate([x[-h:], x, x[:h]]) if loop else np.concatenate([np.ones(h), x, np.ones(h)])
    c = np.concatenate([[0.0], np.cumsum(xp)])
    return (c[w:] - c[:-w])[:len(x)] / w


def true_peak_env(x, loop=False, over=4):
    """Per-sample maximum of |x| oversampled 4x (FFT interpolation): the inter-sample peaks."""
    n = len(x)
    nfft = n if loop else fast_len(n + 2048)
    X = np.fft.rfft(x, nfft)
    up = np.fft.irfft(np.concatenate([X, np.zeros(over * nfft // 2 + 1 - len(X))]), over * nfft) * over
    return np.abs(up[:over * n]).reshape(n, over).max(axis=1)


def limiter(x, reduce_db, loop=False, hold_ms=1.5):
    """Offline look-ahead true-peak limiter: shaves the top reduce_db dB of the (4x oversampled)
    peaks; min-hold then box smoothing of the gain over the same window, so no peak escapes."""
    if reduce_db <= 0:
        return x
    a = np.maximum(np.abs(x), true_peak_env(x, loop))
    thr = a.max() * 10 ** (-reduce_db / 20.0)
    g = np.minimum(1.0, thr / np.maximum(a, 1e-12))
    w = 2 * max(1, int(hold_ms * 1e-3 * SR) // 2) + 1
    g = moving_avg(running_min(g, w, loop), w, loop)
    return x * g


def lufs(x, loop=False):
    """Integrated loudness, ITU-R BS.1770-4 (K-weighting, 400 ms blocks, gating)."""
    y = filt(x, bq("hshelf", 1681.974450955533, 0.7071752369554196, 3.999843853973347),
             bq("hp", 38.13547087602444, 0.5003270373238773), loop=loop)
    blk, hop = ns(0.4), ns(0.1)
    if loop:
        y = np.concatenate([y, y[:blk]])
    if len(y) < blk:
        y = np.concatenate([y, np.zeros(blk - len(y))])
    c = np.concatenate([[0.0], np.cumsum(y * y)])
    starts = np.arange(0, len(y) - blk + 1, hop)
    z = (c[starts + blk] - c[starts]) / blk
    with np.errstate(divide="ignore"):
        lj = -0.691 + 10 * np.log10(z)
    z1 = z[lj > -70]
    if len(z1) == 0:
        return -np.inf
    rel = -0.691 + 10 * np.log10(z1.mean()) - 10
    z2 = z[(lj > -70) & (lj > rel)]
    return float(-0.691 + 10 * np.log10(z2.mean()))


def finish(x, loop, limit_db=0.0, hold_ms=1.5, fade_in=0.003, fade_out=None, target_lufs=None):
    """DC removal (18 Hz high-pass), peak limiting, fades (one-shots), peak -1 dBFS.
    With target_lufs: the limiter shaves exactly what is needed (at most limit_db) for the sound
    to reach that integrated loudness with its true peak at -1 dBFS, so loops of very different
    crest factor (crackle vs wind) come out at consistent loudness. Without: fixed limit_db."""
    x = np.asarray(x, float)
    if loop:
        x = filt(x - x.mean(), bq("hp", 18.0), loop=True)
    else:
        x = filt(x, bq("hp", 18.0))
    if target_lufs is not None:
        done = 0.0
        for _ in range(3):
            tp = max(np.abs(x).max(), true_peak_env(x, loop).max())
            need = 20 * np.log10(tp) + (target_lufs - lufs(x, loop)) - PEAK_DBFS
            step = min(need, limit_db - done)
            if step < 0.2:
                break
            x = limiter(x, step, loop, hold_ms)
            done += step
    elif limit_db > 0:
        x = limiter(x, limit_db, loop, hold_ms)
    if loop:
        x = x - x.mean()
    else:
        n = len(x)
        fi = max(2, ns(fade_in))
        x[:fi] *= 0.5 - 0.5 * np.cos(np.pi * np.arange(fi) / fi)
        fo = ns(fade_out) if fade_out else int(np.clip(0.08 * n, ns(0.05), ns(0.6)))
        x[n - fo:] *= 0.5 + 0.5 * np.cos(np.pi * (np.arange(fo) + 1) / fo)
    return x * (10 ** (PEAK_DBFS / 20.0) / np.abs(x).max())


def to_pcm16(x, rng):
    """Float [-1, 1] -> int16 with TPDF dither (+-1 LSB)."""
    d = rng.random(len(x)) - rng.random(len(x))
    return np.clip(np.round(x * 32767.0 + d), -32768, 32767).astype("<i2")


# =============================================================================================
# Shared sound builders
# =============================================================================================

def flame_roar(n, rng, f_body=150.0, puff=(1.6, 3.2), flutter=(5.0, 13.0), flutter_depth=0.35,
               hiss=0.05, breath=0.5, low_order=2):
    """Turbulent combustion noise: a low body peaking near f_body that swells with the flame's
    puffing, a breathy mid band fluttering with the flame tongues, and a faint hiss. Small
    flames have little energy below their body band (low_order sets that slope)."""
    body = noise(n, rng, lambda f: band(f, f_body * 0.35, f_body, low_order, 2))
    mid = noise(n, rng, lambda f: band(f, f_body * 1.3, f_body * 7, 1, 2))
    hs = noise(n, rng, lambda f: band(f, 2500, 9000, 2, 2))
    p = lfo(n, puff[0], puff[1], rng)
    s = lfo(n, 0.12, 0.7, rng)
    fl = lfo(n, flutter[0], flutter[1], rng)
    s2 = lfo(n, 0.2, 1.5, rng)
    e1 = np.exp(0.32 * p + 0.28 * s)
    e2 = np.exp(0.25 * p + flutter_depth * fl + 0.2 * s)
    e3 = np.exp(0.45 * s2)
    return body * e1 + breath * mid * e2 + hiss * hs * e3


def crackle(n, rng, clusters=4.0, ticks=28.0, pops=0.7, sizzles=0.3, bright=1.0, loop=True, pop_amp=1.0,
            cluster_max=1.0):
    """Granular wood-fire crackle. Returns (crackle bus, low thump bus). In a short loop no
    single event may stand out too much (it would mark the repetition): pop_amp and
    cluster_max cap the largest grains."""
    dur = n / SR
    bus = np.zeros(n)
    low = np.zeros(n)

    def grain(a, tau, fq, mix):
        L = max(8, int(tau * SR * 7))
        t = np.arange(L) / SR
        e = np.exp(-t / tau)
        e[:2] *= (0.4, 0.85)
        s = np.sin(TWO_PI * fq * t + rng.uniform(0, TWO_PI))
        return a * e * ((1 - mix) * rng.standard_normal(L) + 1.4 * mix * s)

    for _ in range(rng.poisson(clusters * dur)):            # fibre cascades: "crk-k-k"
        t0 = rng.uniform(0, dur)
        A = min(0.12 + 0.22 * rng.pareto(1.6), cluster_max)
        m = 1 + rng.geometric(0.2)
        tt = t0 + np.cumsum(rng.exponential(0.0045, m))
        for j, tj in enumerate(tt):
            a = A * rng.uniform(0.25, 1.0) * 0.86 ** j
            add(bus, grain(a, loguniform(rng, 0.07e-3, 0.7e-3) / bright, loguniform(rng, 1200, 7500),
                           rng.uniform(0, 0.6)), ns(tj), loop)
    for _ in range(rng.poisson(ticks * dur)):                # embers ticking
        a = 0.2 * loguniform(rng, 0.08, 1.0)
        add(bus, grain(a, loguniform(rng, 0.05e-3, 0.4e-3) / bright, loguniform(rng, 2000, 9000),
                       rng.uniform(0, 0.4)), ns(rng.uniform(0, dur)), loop)
    for _ in range(rng.poisson(pops * dur)):                 # sap pockets bursting
        t0 = ns(rng.uniform(0, dur))
        A = pop_amp * rng.uniform(0.6, 1.0)
        add(bus, grain(A, loguniform(rng, 1.0e-3, 3.0e-3), loguniform(rng, 1500, 4000), 0.2), t0, loop)
        if rng.random() < 0.6:
            add(bus, 0.4 * A * modes([loguniform(rng, 2200, 5200)], [0.03], [1.0], 0.04, tau=0.0002), t0, loop)
        tt = np.arange(ns(0.08)) / SR
        th = np.sin(TWO_PI * loguniform(rng, 110, 240) * tt) * np.exp(-tt / 0.012) * smoothstep(tt / 0.001)
        add(low, 0.35 * A * th, t0, loop)
    for _ in range(rng.poisson(sizzles * dur)):              # steam escaping wet wood
        t0 = rng.uniform(0, dur)
        d = rng.uniform(0.25, 0.7)
        k = int(rng.uniform(300, 800) * d)
        env_t = rng.uniform(0, d, k)
        for tj in env_t:
            a = 0.035 * np.sin(np.pi * tj / d) ** 2 * loguniform(rng, 0.2, 1.0)
            add(bus, grain(a, loguniform(rng, 0.04e-3, 0.15e-3), loguniform(rng, 3500, 9000), 0.3),
                ns(t0 + tj), loop)
    bus = filt(bus, bq("hp", 450.0), bq("peak", 3200.0, 0.9, 3.0), bq("lp", 12500.0), loop=loop)
    return bus, low


def iron_link_bank(rng, k=8, f1=(650.0, 1300.0)):
    """Mode sets of k wrought-iron chain links: in-plane ring modes f_n ~ n(n^2-1)/sqrt(n^2+1)
    (ratios 1, 2.83, 5.42, 8.77, 12.87) split into doublets by the oval shape, plus two
    out-of-plane modes; Q 40-140 (contact with the neighbouring links damps them hard)."""
    ring = np.array([1.0, 2.83, 5.42, 8.77, 12.87])
    bank = []
    for _ in range(k):
        base = loguniform(rng, *f1)
        fr = []
        for r in ring:
            sp = rng.uniform(0.008, 0.03)
            fr += [base * r * (1 - sp), base * r * (1 + sp)]
        fr += [base * rng.uniform(1.6, 2.2), base * rng.uniform(3.4, 4.3)]
        f = np.array(fr)
        q = loguniform(rng, 40, 140, len(f))
        bank.append((f, LN1000 * q / (np.pi * f), rng.uniform(0.4, 1.0, len(f)) * (f / base) ** -0.35))
    return bank


def chain_hit(rng, bank, amp, dur=0.45, tau=None, thunk=0.35):
    f, t60, a = bank[rng.integers(len(bank))]
    tau = tau if tau is not None else loguniform(rng, 0.06e-3, 0.35e-3)
    w = rng.uniform(0.15, 1.0, len(f))
    s = modes(f * (1 + rng.normal(0, 0.004, len(f))), t60, a * w, dur, tau=tau)
    s /= np.abs(s).max() + 1e-12
    if thunk:
        b = burst(0.03, rng.uniform(0.002, 0.006), rng, lambda ff: band(ff, 250, 3000, 1, 2))
        s[:len(b)] += thunk * b / (np.abs(b).max() + 1e-12)
    return amp * s


def stone_hit(rng, amp, dur=0.35, f_lo=110.0, f_hi=260.0):
    """Heavy iron landing on flagstones: dull low thump + gritty impact noise."""
    f, t60, a = random_modes(rng, 6, f_lo, f_hi * 3, q=(6, 14), tilt_db=-6)
    s = modes(f, t60, a, dur, tau=0.002)
    s /= np.abs(s).max() + 1e-12
    b = burst(0.05, 0.006, rng, lambda ff: band(ff, 200, 3500, 1, 2))
    s[:len(b)] += 0.6 * b / (np.abs(b).max() + 1e-12)
    return amp * s


def thinning_times(rng, rate_fn, t0, t1, rmax):
    """Inhomogeneous Poisson process (Lewis-Shedler thinning)."""
    k = rng.poisson(rmax * (t1 - t0))
    t = np.sort(rng.uniform(t0, t1, k))
    return t[rng.random(k) < rate_fn(t) / rmax]


def creak_voice(n, rng, v, load, body, pulse_ms=0.35, jitter=0.05, noise_amt=0.15, slow_jitter=0.0,
                v_ref=40.0, direct=0.7, direct_band=(250.0, 6000.0)):
    """Stick-slip creak: slips from stick_slip() rendered as force pulses (plus a little rubbing
    noise per slip), radiated by the body modes (convolution with the modal response) and, for
    `direct` of the level, by the small stiff contact itself (broad band-pass), which keeps the
    pulse train's harmonic series - the creak's pitch - audible between the body modes."""
    tt, dr = stick_slip(v, load, rng, jitter=jitter, slow_jitter=slow_jitter, v_ref=v_ref)
    if len(tt) == 0:
        return np.zeros(n)
    amp = dr * rng.uniform(0.8, 1.2, len(dr))
    p = pulse_train(n, tt, amp, pulse_ms * 1e-3)
    if noise_amt:
        env = pulse_train(n, tt, amp, 4 * pulse_ms * 1e-3)
        p += noise_amt * env * noise(n, rng, lambda f: band(f, 1500, 9000, 1, 2))
    y = conv(p, body)[:n]
    y /= np.sqrt(np.mean(y ** 2)) + 1e-12
    if direct:
        dpath = filt(p, bq("hp", direct_band[0], 0.6), bq("lp", direct_band[1], 0.6))
        y += direct * dpath / (np.sqrt(np.mean(dpath ** 2)) + 1e-12)
    return y


def body_ir(freqs, t60, amps, dur):
    h = modes(freqs, t60, amps, dur)
    return h / (np.sqrt(np.sum(h ** 2)) + 1e-12)


# =============================================================================================
# The sounds
# =============================================================================================

SOUNDS = {}


def sound(name, seconds, loop=False, limit_db=0.0, hold_ms=1.5, fade_out=None, zoom=None, lufs=None,
          desc=""):
    """Register a sound. limit_db: (maximum) peak limiting; lufs: loudness target (see finish);
    zoom: time (s) of a 120 ms detail view in the preview."""
    def deco(fn):
        SOUNDS[name] = dict(fn=fn, seconds=seconds, loop=loop, limit_db=limit_db, lufs=lufs,
                            hold_ms=hold_ms, fade_out=fade_out, zoom=zoom, desc=desc)
        return fn
    return deco


# ---------------------------------------------------------------------------- fire and flame

@sound("fire_loop", 8.0, loop=True, limit_db=14.0, hold_ms=0.5, lufs=-20.0,
       desc="Brazier: granular wood crackle, sap pops, steam sizzle over a low puffing roar (8 s loop)")
def fire_loop(n, rng):
    roar = flame_roar(n, rng, f_body=150.0, puff=(1.6, 3.2), flutter=(5, 13), flutter_depth=0.35,
                      hiss=0.06, breath=0.5)
    cr, low = crackle(n, rng, clusters=6.0, ticks=45.0, pops=0.8, sizzles=0.3)
    x = 0.032 * roar + 1.6 * cr + low
    return reverb(x, "hall", 3.0, tail=0.1, early=0.25, loop=True)


@sound("torch_loop", 6.0, loop=True, limit_db=10.0, hold_ms=0.5, lufs=-19.0,
       desc="Pitch torch: fluttering small flame, hiss, sputtering pitch bubbles, light crackle (6 s loop)")
def torch_loop(n, rng):
    roar = flame_roar(n, rng, f_body=320.0, puff=(3.5, 6.5), flutter=(7, 16), flutter_depth=0.55,
                      hiss=0.16, breath=0.8, low_order=4)
    cr, low = crackle(n, rng, clusters=1.6, ticks=16.0, pops=0.3, sizzles=0.25, bright=1.3, pop_amp=0.2,
                      cluster_max=0.6)
    sp = np.zeros(n)
    dur = n / SR
    for _ in range(rng.poisson(4.0 * dur)):                  # molten pitch bubbling and spitting
        b = bubble(loguniform(rng, 0.7e-3, 2.2e-3), xi=0.4)
        add(sp, 0.25 * loguniform(rng, 0.15, 1.0) * b, ns(rng.uniform(0, dur)), loop=True)
    x = 0.016 * roar + 1.5 * cr + 0.4 * low + filt(sp, bq("hp", 900.0), loop=True)
    x = filt(x, bq("hp", 110.0, 0.6), loop=True)              # a hand torch has no deep roar
    return reverb(x, "cell", 2.5, tail=0.1, early=0.25, loop=True)


# ---------------------------------------------------------------------------- sea and wind

@sound("sea_loop", 9.9, loop=True, limit_db=6.0, hold_ms=15.0, lufs=-18.0,
       desc="Waves breaking on the rock outside, heard through the stone: thumps, muffled wash, "
            "backwash gurgles, ground rumble (9.9 s loop)")
def sea_loop(n, rng):
    dur = n / SR
    low = np.zeros(n)
    wash = np.zeros(n)
    for t0, s in ((0.35, 1.0), (4.55, 0.72), (7.7, 0.42)):
        L = ns(2.5)
        t = np.arange(L) / SR
        env = (1 - np.exp(-t / 0.05)) * np.exp(-t / 0.55)
        boom = noise(L, rng, lambda f: band(f, 22, 110, 2, 3)) * env
        fth = 46.0 - 9.0 * (1 - np.exp(-t / 0.3))
        thump = np.sin(TWO_PI * np.cumsum(fth) / SR) * (1 - np.exp(-t / 0.015)) * np.exp(-t / 0.32)
        add(low, s * (0.7 * boom + 0.9 * thump), ns(t0), loop=True)
        L = ns(6.0)
        t = np.arange(L) / SR
        env = smoothstep(t / 0.5) * np.exp(-np.maximum(t - 0.55, 0) / (1.3 + 0.5 * s))
        foam = np.maximum(0.0, 1 + 0.55 * lfo(L, 12, 50, rng))
        w = noise(L, rng, lambda f: band(f, 60, 7000, 1, 1) * tilt(f, -2.0)) * env * foam
        add(wash, 2.0 * s * w, ns(t0 - 0.15), loop=True)
        for _ in range(int(30 * s)):                       # backwash draining through the rocks
            tb = t0 + 1.0 + rng.gamma(2.0, 0.7)
            add(wash, 1.2 * s * bubble(loguniform(rng, 0.006, 0.022)), ns(tb), loop=True)
    rumble = noise(n, rng, lambda f: band(f, 16, 75, 2, 3)) * np.exp(0.3 * lfo(n, 0.1, 0.4, rng))
    surf = noise(n, rng, lambda f: band(f, 150, 4000, 1, 2)) * np.exp(0.4 * lfo(n, 0.1, 0.5, rng))
    stone = (bq("lp1", 150.0), bq("lp", 1700.0, 0.6), bq("peak", 70.0, 1.0, 3.0))
    x = low + 0.1 * rumble + filt(wash + 0.15 * surf, *stone, loop=True)
    return reverb(x, "cell", 2.0, tail=0.35, loop=True)


@sound("ambient_wind", 9.9, loop=True, limit_db=4.0, hold_ms=10.0, lufs=-18.0,
       desc="Draught moaning through arrow slits: gusts, pitched aeolian moans that rise with the "
            "gusts, breathy edge hiss (9.9 s loop)")
def ambient_wind(n, rng):
    gust_s = lfo(n, 0.09, 0.4, rng) + 0.45 * lfo(n, 0.4, 1.3, rng)
    gust = 0.5 + 0.5 * np.tanh(1.1 * gust_s + 0.15)
    wob = [lfo(n, 0.3, 1.5, rng) for _ in range(3)]
    tones = ((236.0, 7.0, 1.0, 0.30), (351.0, 9.0, 0.55, 0.45), (529.0, 12.0, 0.3, 0.6))

    def at(sig, tc):
        return np.interp(tc * SR, np.arange(n), sig, period=n)

    def mag(tc, f):
        g = at(gust, tc)[:, None]
        F = f[None, :]
        bb = band(F, 35, 320, 2, 2) * (0.45 + g) ** 1.6
        bb = bb + 0.025 * band(F, 1200, 5000, 2, 2) * g ** 2.5
        m = bb
        for k, (f0, bw, A, th) in enumerate(tones):
            fk = f0 * (0.86 + 0.28 * g) * (1 + 0.012 * at(wob[k], tc)[:, None])
            ak = A * np.clip((g - th) / (1 - th), 0, 1) ** 1.3 + 0.04 * A
            m = m + 14.0 * ak * (lorentz(F, fk, bw) + 0.1 * lorentz(F, 2 * fk, 2 * bw))
        return m

    x = stft_noise(n, mag, rng, loop=True, hop=490, win_hops=16)
    return reverb(x, "gate", 5.0, tail=0.5, loop=True)


# ---------------------------------------------------------------------------- drips

def _drip_scene(n, rng, parts, room="cave", dist=1.5, tail=0.6):
    x = np.zeros(n)
    for (t0, f0, rise, tau, amp, click) in parts:
        add(x, drop_plink(f0, rise, tau, amp, click=click, rng=rng), ns(t0))
    return fit(reverb(x, room, dist, tail=tail), n)


@sound("drip_1", 2.2, fade_out=0.4, zoom=0.1, desc="Cave drip: classic rising 'plink' (1.05 -> 2 kHz) in a stone vault")
def drip_1(n, rng):
    return _drip_scene(n, rng, [(0.05, 1050.0, 0.9, 0.022, 1.0, 0.15)])


@sound("drip_2", 2.2, fade_out=0.4, zoom=0.1, desc="Cave drip: short high 'tik-plip' with a second tiny bubble")
def drip_2(n, rng):
    return _drip_scene(n, rng, [(0.05, 1750.0, 0.5, 0.012, 1.0, 0.25),
                                (0.078, 2600.0, 0.35, 0.007, 0.35, 0.0)])


@sound("drip_3", 2.2, fade_out=0.4, zoom=0.1, desc="Cave drip: deep 'bloop' (620 Hz rising) and a rebound droplet")
def drip_3(n, rng):
    x = _drip_scene(n, rng, [(0.05, 620.0, 1.1, 0.03, 1.0, 0.1),
                             (0.125, 3000.0, 0.3, 0.006, 0.18, 0.05)])
    return x


@sound("ambient_drip_echo", 9.5, fade_out=1.2,
       desc="Slow drips falling far away in the great hall, long stone echo")
def ambient_drip_echo(n, rng):
    x = np.zeros(n)
    for t0 in (0.2, 1.85, 3.3, 5.35, 6.6):
        f0 = loguniform(rng, 750, 1900)
        add(x, drop_plink(f0, rng.uniform(0.5, 1.0), rng.uniform(0.012, 0.028), rng.uniform(0.6, 1.0),
                          click=0.12, rng=rng), ns(t0))
    x = filt(x, bq("lp", 6000.0, 0.6))                      # air absorption over the distance
    return fit(reverb(x, "hall", 11.0, tail=1.0), n)


# ---------------------------------------------------------------------------- chains

@sound("chains_1", 3.4, fade_out=0.5, zoom=0.62,
       desc="Heavy chain shaken in its wall ring, then dropped on flagstones and settling")
def chains_1(n, rng):
    bank = iron_link_bank(rng, k=16)
    x = np.zeros(n)
    shake = lambda t: (12 + 480 * np.abs(np.sin(TWO_PI * 2.1 * (t - 0.1))) ** 10) * (t < 1.35)
    for t in thinning_times(rng, shake, 0.1, 1.35, 500):
        add(x, chain_hit(rng, bank, loguniform(rng, 0.08, 0.6)), ns(t))
    drop = lambda t: 450 * np.exp(-(t - 1.62) / 0.09)
    for t in thinning_times(rng, drop, 1.62, 2.3, 450):
        add(x, chain_hit(rng, bank, loguniform(rng, 0.1, 0.9) * np.exp(-(t - 1.62) / 0.35)), ns(t))
    for t, a in ((1.63, 1.0), (1.69, 0.7), (1.78, 0.55), (1.9, 0.35)):
        add(x, stone_hit(rng, a), ns(t))
    for t in np.sort(rng.uniform(2.3, 2.9, 9)):              # last links sliding off the pile
        add(x, chain_hit(rng, bank, loguniform(rng, 0.03, 0.15)), ns(t))
    return fit(reverb(x, "cell", 2.2, tail=0.7), n)


@sound("chains_2", 3.6, fade_out=0.5, zoom=0.6,
       desc="Heavy chain hauled hand over hand through an iron ring, dragged on stone, then slumping")
def chains_2(n, rng):
    bank = iron_link_bank(rng, k=16)
    ring = (np.array([455.0, 1260.0, 2410.0, 3900.0, 5700.0]), np.array([0.2, 0.15, 0.12, 0.09, 0.06]),
            np.array([1.0, 0.7, 0.5, 0.3, 0.2]))
    x = np.zeros(n)
    drag = np.zeros(n)
    for s0, s1 in ((0.1, 1.05), (1.3, 2.25)):
        t = s0 + rng.uniform(0.0, 0.04)
        while t < s1:
            u = (t - s0) / (s1 - s0)
            a = 0.5 + 0.5 * np.sin(np.pi * u)
            add(x, chain_hit(rng, bank, a * rng.uniform(0.7, 1.0), tau=0.0004, thunk=0.9), ns(t))
            add(x, 0.3 * a * modes(ring[0] * (1 + rng.normal(0, 0.003, 5)), ring[1], ring[2], 0.5,
                                   tau=0.0005), ns(t + 0.004))
            t += 0.2 / (0.6 + 0.8 * np.sin(np.pi * u)) * rng.uniform(0.85, 1.15)
        for tj in thinning_times(rng, lambda tt: 25 + 0 * tt, s0, s1, 25):
            add(x, chain_hit(rng, bank, loguniform(rng, 0.03, 0.15)), ns(tj))
        L = ns(s1 - s0 + 0.1)
        tt = np.arange(L) / L
        sc = noise(L, rng, lambda f: band(f, 700, 5000, 1, 2)) * np.sin(np.pi * tt) ** 1.5
        sc *= np.maximum(0, 1 + 0.8 * lfo(L, 20, 80, rng))
        add(drag, 0.03 * sc, ns(s0))
    drop = lambda t: 380 * np.exp(-(t - 2.5) / 0.1)
    for t in thinning_times(rng, drop, 2.5, 3.1, 380):
        add(x, chain_hit(rng, bank, loguniform(rng, 0.1, 0.8) * np.exp(-(t - 2.5) / 0.3)), ns(t))
    for t, a in ((2.51, 0.9), (2.6, 0.6), (2.72, 0.4)):
        add(x, stone_hit(rng, a), ns(t))
    return fit(reverb(x + drag, "cell", 2.2, tail=0.7), n)


# ---------------------------------------------------------------------------- doors, locks, gate

@sound("door_creak", 2.3, fade_out=0.35, zoom=0.6,
       desc="Iron grille door swinging on two dry hinges: stick-slip creak gliding with the swing "
            "speed through the grille's ringing modes, bars rattling as it stops")
def door_creak(n, rng):
    t = np.arange(n) / SR
    speed = smoothstep(t / 0.45) * (1 - smoothstep((t - 0.45) / 1.3))   # pushed, then coasting
    speed *= np.exp(0.22 * lfo(n, 1.5, 5.0, rng))                       # uneven hand, sticky pin
    load = 1.0 + 0.1 * lfo(n, 1.0, 4.0, rng)
    hk_f = np.array([1850.0, 2920.0, 4100.0, 5600.0])
    gf, gt, ga = random_modes(rng, 34, 140.0, 4500.0, q=(15, 50), tilt_db=-2.0)
    body = body_ir(np.concatenate([gf, hk_f]), np.concatenate([gt, LN1000 * 30 / (np.pi * hk_f)]),
                   np.concatenate([ga, [0.9, 0.7, 0.5, 0.35]]), 0.8)
    x = creak_voice(n, rng, 480.0 * speed, load, body, pulse_ms=0.3, jitter=0.015, slow_jitter=0.5,
                    v_ref=60.0, noise_amt=0.08)
    x += 0.3 * creak_voice(n, rng, 330.0 * speed * np.exp(0.15 * lfo(n, 0.5, 2, rng)), load, body,
                           pulse_ms=0.45, jitter=0.06, slow_jitter=0.5, v_ref=60.0)
    x /= np.abs(x).max()
    bank = iron_link_bank(rng, k=4, f1=(500, 1100))
    for tj in np.sort(1.76 + rng.exponential(0.06, 9)):        # loose bars buzzing in the frame
        add(x, chain_hit(rng, bank, 0.2 * np.exp(-(tj - 1.76) / 0.12), thunk=0.2), ns(tj))
    return fit(reverb(x, "pit", 2.5, tail=0.3), n)


@sound("lock_clank", 1.25, fade_out=0.3, zoom=0.5,
       desc="Big iron lock: key rasping into the wards, levers ticking, bolt slamming home, hasp rattle")
def lock_clank(n, rng):
    x = np.zeros(n)
    for tj in np.sort(rng.uniform(0.0, 0.14, 14)):           # key scraping into the wards
        b = burst(0.012, loguniform(rng, 0.0008, 0.003), rng, lambda f: band(f, 2000, 7000, 2, 2))
        add(x, 0.05 * b * rng.uniform(0.3, 1), ns(tj))
    small = (np.array([2350.0, 3880.0, 5120.0, 7400.0]), np.array([0.06, 0.045, 0.035, 0.025]),
             np.array([1.0, 0.7, 0.5, 0.3]))
    for tj, a in ((0.05, 0.05), (0.15, 0.08), (0.29, 0.11), (0.37, 0.15)):  # wards, levers lifting
        add(x, a * modes(small[0] * rng.uniform(0.9, 1.1), small[1], small[2], 0.2, tau=0.00015), ns(tj))
    t = np.arange(ns(0.2)) / SR
    v = np.where(t < 0.13, 1.0, 0.0) * 500.0                 # key turning: short rasp of iron on iron
    rasp_body = body_ir(*random_modes(rng, 12, 1500, 6000, q=(30, 80)), 0.15)
    add(x, 0.02 * creak_voice(len(t), rng, v, np.ones(len(t)), rasp_body, pulse_ms=0.15, jitter=0.2), ns(0.2))
    t0 = ns(0.45)                                             # the bolt shoots home
    case = random_modes(rng, 22, 380.0, 4200.0, q=(80, 260), tilt_db=-2.5)
    bolt = (1677.0 * np.array([1, 2.756, 5.404, 8.933]), np.array([0.5, 0.3, 0.18, 0.1]),
            np.array([1.0, 0.6, 0.35, 0.2]))
    door = random_modes(rng, 10, 90.0, 600.0, q=(25, 60), tilt_db=-1.0)
    clank = (modes(*case, 1.0, tau=0.0004) / 4.0 + 0.6 * modes(*bolt, 1.0, tau=0.0003)
             + 0.35 * modes(*door, 1.0, tau=0.0015) / 3.0)
    thud = burst(0.08, 0.01, rng, lambda f: band(f, 60, 900, 2, 2))
    clank[:len(thud)] += 0.5 * thud / np.abs(thud).max()
    clank += 1.0 * fit(burst(0.03, 0.0012, rng, lambda f: band(f, 1500, 12000, 1, 2)), len(clank))
    add(x, clank / np.abs(clank).max(), t0)
    bank = iron_link_bank(rng, k=3, f1=(900, 1600))
    for tj, a in ((0.57, 0.18), (0.63, 0.1), (0.7, 0.06)):   # the hasp jiggles
        add(x, chain_hit(rng, bank, a, dur=0.3), ns(tj))
    return fit(reverb(x, "cell", 1.2, tail=0.35), n)


@sound("portcullis_chain", 5.2, fade_out=0.5, zoom=1.5,
       desc="Gate winch: ratchet pawl clicking with each crank stroke, chain links over the drum, "
            "the grate grinding in its stone grooves, drum timber creaking, final pawl clank")
def portcullis_chain(n, rng):
    t = np.arange(n) / SR
    crank = smoothstep(t / 0.4) * (1 - smoothstep((t - 4.1) / 0.35))
    crank *= 0.45 + 0.55 * np.sin(TWO_PI * t / 1.15) ** 2     # two heaves per crank turn
    omega = 0.95 * crank                                       # drum revolutions per second
    theta = np.cumsum(omega) / SR
    x = np.zeros(n)
    pawl = (np.array([1880.0, 3170.0, 4630.0, 6900.0]), np.array([0.09, 0.06, 0.05, 0.03]),
            np.array([1.0, 0.8, 0.5, 0.3]))
    frame = random_modes(rng, 8, 160.0, 900.0, q=(10, 20), tilt_db=-2.0)
    teeth = np.flatnonzero(np.diff(np.floor(theta * 8)) > 0)  # 8 ratchet teeth per turn
    for i in teeth:
        a = 1.8 * rng.uniform(0.6, 1.0)
        add(x, a * (modes(pawl[0] * rng.uniform(0.97, 1.03), pawl[1], pawl[2], 0.25, tau=0.0001)
                    + 0.5 * modes(*frame, 0.25, tau=0.001) / 2.0), i + rng.integers(0, 40))
    bank = iron_link_bank(rng, k=6, f1=(550, 1000))
    links = np.flatnonzero(np.diff(np.floor(theta * 16)) > 0)  # 16 links wind on per turn
    for i in links:
        add(x, chain_hit(rng, bank, rng.uniform(0.1, 0.3), tau=0.0003, thunk=0.5), i + rng.integers(0, 300))
    for tj in thinning_times(rng, lambda tt: 40 * np.interp(tt, t, crank), 0, 4.6, 40):
        add(x, chain_hit(rng, bank, loguniform(rng, 0.03, 0.12)), ns(tj))
    grind = noise(n, rng, lambda f: band(f, 60, 700, 2, 2)) * crank
    grind *= np.maximum(0, 1 + 0.9 * lfo(n, 8, 40, rng))
    x += 0.06 * grind
    wood = body_ir(*random_modes(rng, 14, 120.0, 1500.0, q=(12, 30), tilt_db=-3.0), 0.5)
    x += 0.1 * creak_voice(n, rng, 70.0 * crank * (0.6 + 0.4 * np.sin(TWO_PI * t / 1.15) ** 4),
                            np.ones(n), wood, pulse_ms=0.9, jitter=0.08, slow_jitter=0.6, noise_amt=0.05)
    x /= np.abs(x).max()
    tf = ns(4.48)                                              # pawl drops, grate caught by the chain
    add(x, 0.9 * modes(pawl[0] * 0.8, pawl[1] * 2, pawl[2], 0.4, tau=0.0003), tf)
    add(x, stone_hit(rng, 0.9, dur=0.5, f_lo=70.0, f_hi=180.0), tf + ns(0.02))
    for tj in np.sort(4.5 + rng.exponential(0.12, 12)):
        add(x, chain_hit(rng, bank, 0.3 * np.exp(-(tj - 4.5) / 0.25)), ns(tj))
    return fit(reverb(x, "gate", 4.0, tail=0.7), n)


@sound("press_gang_bell", 8.3, fade_out=0.9, zoom=2.8,
       desc="Three slow tolls of a cracked bronze bell: hum/prime/tierce/quint/nominal partials "
            "split into beating doublets, sour mistuning, crack rattle, clapper clack")
def press_gang_bell(n, rng):
    prime = 277.0
    #            ratio  amp   T60 (healthy bell, s)
    table = [(0.500, 0.55, 9.0), (1.000, 0.50, 6.0), (1.188, 0.60, 4.5), (1.502, 0.25, 3.5),
             (2.000, 1.00, 3.0), (2.512, 0.35, 2.2), (2.667, 0.30, 2.0), (3.011, 0.35, 1.6),
             (4.030, 0.30, 1.1), (4.410, 0.18, 0.9), (5.060, 0.16, 0.8), (5.350, 0.12, 0.7),
             (6.020, 0.10, 0.55), (6.650, 0.08, 0.45), (7.330, 0.06, 0.4), (8.100, 0.05, 0.35)]
    parts = []
    for ratio, amp, t60 in table:                     # the casting: cracked = mistuned, split, dead
        f = prime * ratio * (1 + (rng.uniform(-0.018, 0.018) if ratio > 0.6 else 0.004))
        sp = rng.uniform(0.004, 0.016)
        damp = 0.7 if ratio < 0.6 else 0.6
        parts.append((f * (1 - sp / 2), amp, t60 * damp, ratio <= 1.2))
        parts.append((f * (1 + sp / 2), amp * rng.uniform(0.55, 1.0), t60 * damp * 0.7, ratio <= 1.2))
    for _ in range(5):                                # spurious modes of the cracked shell
        parts.append((loguniform(rng, 700, 3000), 0.15, rng.uniform(0.2, 0.5), False))
    x = np.zeros(n)
    for k, (t0, s) in enumerate(((0.05, 1.0), (2.75, 0.92), (5.45, 0.97))):
        L = ns(7.0)
        tt = np.arange(L) / SR
        y = np.zeros(L)
        lo = np.zeros(L)
        for f, a, T, is_low in parts:
            w = a * rng.uniform(0.8, 1.2) * contact_weight(np.array([f]), 0.0005)[0]
            m = w * np.exp(-LN1000 * tt / T) * np.sin(TWO_PI * f * tt + rng.uniform(0, TWO_PI))
            y += m
            if is_low:
                lo += m
        y *= smoothstep(tt / 0.0008)
        lo *= smoothstep(tt / 0.0008)
        pk = np.abs(y).max()
        y = np.tanh(0.9 * y / pk) * pk / 0.9               # sour intermodulation of the crack
        gate = np.maximum(0.0, lo / np.abs(lo).max() - 0.2)  # crack faces clapping each cycle
        rattle = noise(L, rng, lambda f: band(f, 1200, 6000, 2, 2)) * gate
        y += 0.5 * pk * rattle
        clack = burst(0.05, 0.005, rng, lambda f: band(f, 1500, 9000, 1, 2))
        hi = modes(loguniform(rng, 4500, 11000, 6), rng.uniform(0.05, 0.15, 6), np.ones(6), 0.3, tau=0.0002)
        y[:len(clack)] += 0.3 * pk * clack / np.abs(clack).max()
        y[:len(hi)] += 0.15 * pk * hi / np.abs(hi).max()
        b0 = ns(rng.uniform(0.035, 0.06))                   # the clapper bounces back
        y[b0:b0 + len(clack)] += 0.12 * pk * clack / np.abs(clack).max()
        add(x, s * y / pk, ns(t0))
    return fit(reverb(x, "gate", 6.0, tail=0.8), n)


# ---------------------------------------------------------------------------- punishments

@sound("whip_crack", 1.7, fade_out=0.4, limit_db=2.0, hold_ms=0.4, zoom=0.44,
       desc="Bullwhip: rising swish of the thong, supersonic N-wave crack from the tip and its "
            "popper, stone-vault echo")
def whip_crack(n, rng):
    tc = 0.42
    L = ns(tc + 0.08)

    def mag(t, f):
        u = np.clip((t - 0.06) / (tc - 0.06), 0, 1)[:, None]
        fc = 300.0 + 2300.0 * u ** 2
        env = u ** 2.2 * np.where(t[:, None] > tc, np.exp(-(t[:, None] - tc) / 0.015), 1.0)
        return env * band(f[None, :], 0.5 * fc, 1.6 * fc, 2, 2)

    swish = stft_noise(L, mag, rng, loop=False, hop=128, win_hops=4)
    swish *= 0.08 / (np.abs(swish).max() + 1e-12)
    x = np.zeros(n)
    add(x, swish, 0)

    def nwave(T, a):
        m = max(3, int(round(T * SR)))
        w = 1 - 2 * np.arange(m) / (m - 1)
        return a * np.convolve(w, [0.25, 0.5, 0.25])

    i0 = ns(tc)
    add(x, nwave(0.001, 1.0), i0)
    add(x, nwave(0.0006, 0.4), i0 + ns(0.0017))
    for _ in range(5):                                          # the frayed popper fluttering
        add(x, nwave(0.00015, rng.uniform(0.04, 0.14)), i0 + ns(rng.uniform(0.002, 0.009)))
    snap = burst(0.03, 0.0028, rng, lambda f: band(f, 900, 12000, 1, 1))   # shocked air, frayed fibres
    add(x, 0.3 * snap / np.abs(snap).max(), i0 + ns(0.0012))
    wake = burst(0.06, 0.008, rng, lambda f: band(f, 2000, 12000, 2, 1))
    add(x, 0.06 * wake / np.abs(wake).max(), i0)
    return fit(reverb(x, "pit", 3.5, tail=0.5), n)


@sound("splash", 4.0, fade_out=0.6,
       desc="Body dunked in the cistern tank: slap, cavity collapse 'gloop', spray falling back, "
            "bubbles from body and clothes, water slopping against the walls")
def splash(n, rng):
    x = np.zeros(n)
    t0 = 0.12
    slap = burst(0.15, 0.025, rng, lambda f: band(f, 150, 6000, 1, 2))
    thud = burst(0.25, 0.06, rng, lambda f: band(f, 40, 220, 2, 2))
    add(x, slap / np.abs(slap).max(), ns(t0))
    add(x, 0.7 * thud / np.abs(thud).max(), ns(t0))
    wood = modes(*random_modes(rng, 10, 150.0, 1400.0, q=(10, 25)), 0.3, tau=0.002)
    add(x, 0.2 * wood / np.abs(wood).max(), ns(t0 + 0.03))          # chair knocks the rim
    for tb, r in ((0.27, 0.025), (0.33, 0.018), (0.41, 0.014), (0.5, 0.011)):
        add(x, 0.9 * (r / 0.025) * bubble(r, xi=0.25), ns(tb))    # the cavity behind the body collapses
    L = ns(2.0)
    tt = np.arange(L) / SR
    spray = noise(L, rng, lambda f: band(f, 300, 9000, 1, 2)) * smoothstep(tt / 0.08) * np.exp(-tt / 0.35)
    add(x, 0.45 * spray, ns(t0 + 0.04))
    for _ in range(420):                                             # droplets falling back
        tj = t0 + 0.2 + rng.gamma(1.6, 0.25)
        a = 0.12 * loguniform(rng, 0.1, 1.0) * np.exp(-(tj - t0) / 0.9)
        if rng.random() < 0.35:
            add(x, a * bubble(loguniform(rng, 0.0006, 0.0025)), ns(tj))
        else:
            add(x, 0.5 * a * burst(0.004, loguniform(rng, 0.0002, 0.0009), rng), ns(tj))
    for _ in range(170):                                             # air out of body and clothes
        tj = t0 + 0.25 + rng.gamma(1.3, 0.55)
        r = loguniform(rng, 0.002, 0.012)
        add(x, 0.35 * (r / 0.012) * np.exp(-(tj - t0) / 1.6) * bubble(r), ns(tj))
    L = ns(3.6)
    tt = np.arange(L) / SR
    slosh = noise(L, rng, lambda f: band(f, 60, 700, 1, 2)) * np.abs(np.sin(np.pi * 1.25 * tt)) ** 2
    slosh *= smoothstep(tt / 0.3) * np.exp(-tt / 1.1)
    add(x, 0.25 * slosh, ns(t0 + 0.2))
    for k, tj in enumerate((0.95, 1.7, 2.45)):                       # waves lapping the tank wall
        lap = burst(0.25, 0.05, rng, lambda f: band(f, 250, 3000, 1, 2))
        add(x, 0.18 * 0.6 ** k * lap / np.abs(lap).max(), ns(tj))
    return fit(reverb(x, "cistern", 3.0, tail=0.7), n)


@sound("rack_creak", 4.4, fade_out=0.5, zoom=0.9,
       desc="The rack wound tighter: oak roller groaning in its socket (slow stick-slip), hemp rope "
            "creaking and crackling under tension, wooden pawl knocking over the ratchet")
def rack_creak(n, rng):
    t = np.arange(n) / SR
    pull = smoothstep((t - 0.15) / 0.3) * (1 - smoothstep((t - 1.45) / 0.3))
    pull += 0.9 * smoothstep((t - 2.25) / 0.3) * (1 - smoothstep((t - 3.45) / 0.35))
    pull *= np.exp(0.25 * lfo(n, 1.0, 4.0, rng))
    tension = 0.6 + 0.4 * smoothstep(t / 3.6)
    oak = body_ir(*random_modes(rng, 22, 140.0, 3000.0, q=(5, 14), tilt_db=-1.5), 0.4)
    x = creak_voice(n, rng, 85.0 * pull, tension, oak, pulse_ms=0.5, jitter=0.06, slow_jitter=0.6,
                    v_ref=25.0, noise_amt=0.08, direct=0.5, direct_band=(150.0, 3000.0))
    x /= np.abs(x).max()
    rope = body_ir(*random_modes(rng, 12, 700.0, 4000.0, q=(4, 10), tilt_db=-1.5), 0.15)
    r = creak_voice(n, rng, 160.0 * pull * tension * (1 + 0.3 * lfo(n, 2, 6, rng)), 1 + 0 * t, rope,
                    pulse_ms=0.25, jitter=0.15, slow_jitter=0.8, v_ref=50.0, noise_amt=0.3, direct=0.4,
                    direct_band=(800.0, 7000.0))
    x += 0.45 * r / np.abs(r).max()
    fib = np.zeros(n)
    for tj in thinning_times(rng, lambda tt: 260 * np.interp(tt, t, pull * tension), 0, 4.0, 260):
        add(fib, loguniform(rng, 0.05, 1.0) * burst(0.004, loguniform(rng, 0.0001, 0.0006), rng), ns(tj))
    x += 0.12 * filt(fib, bq("hp", 1500.0), bq("lp", 8000.0)) / (np.abs(fib).max() + 1e-12)
    knock = random_modes(rng, 8, 280.0, 1800.0, q=(10, 22))
    for tj in (0.62, 1.18, 2.85):                                   # pawl drops over a tooth
        k = modes(*knock, 0.25, tau=0.0008)
        add(x, 0.55 * k / np.abs(k).max(), ns(tj))
    return fit(reverb(x, "cell", 2.5, tail=0.55), n)


# ---------------------------------------------------------------------------- ambient one-shots

@sound("ambient_rats", 6.0, fade_out=0.6,
       desc="Rats in a dark corner: claws skittering over stone and straw, squeaks and a brief squabble")
def ambient_rats(n, rng):
    x = np.zeros(n)

    def run(t0, t1, level, straw_from=None):
        tt = t0
        while tt < t1:
            u = (tt - t0) / (t1 - t0)
            a = level * np.sin(np.pi * u) ** 0.7
            on_straw = straw_from is not None and tt > straw_from
            for k in range(4):                                     # gallop: 4 feet per stride
                tk = tt + 0.006 * k + rng.uniform(0, 0.004)
                if on_straw:                                       # stalks snapping and rustling
                    for tg in tk + rng.exponential(0.006, 6).cumsum():
                        c = burst(0.002, loguniform(rng, 0.00005, 0.0002), rng)
                        add(x, 0.6 * a * rng.uniform(0.2, 1.0) * c, ns(tg))
                else:
                    c = burst(0.003, loguniform(rng, 0.00012, 0.0004), rng, lambda f: band(f, 2500, 11000, 2, 2))
                    add(x, a * rng.uniform(0.4, 1.0) * c, ns(tk))
            tt += 1.0 / rng.uniform(9.0, 12.0)

    def squeak(t0, f_a, f_b, f_c, dur, amp):
        L = ns(dur)
        u = np.arange(L) / L
        fctl = 2 * f_b - 0.5 * (f_a + f_c)
        f = (1 - u) ** 2 * f_a + 2 * u * (1 - u) * fctl + u ** 2 * f_c
        tt = np.arange(L) / SR
        f = f * (1 + 0.02 * np.sin(TWO_PI * rng.uniform(35, 60) * tt + rng.uniform(0, 6)))
        ph = TWO_PI * np.cumsum(f) / SR
        y = np.sin(ph) + 0.3 * np.sin(2 * ph) + 0.08 * np.sin(3 * ph) * (f.max() * 3 < 18000)
        env = smoothstep(tt / 0.008) * smoothstep((dur - tt) / 0.02)
        y = y * env + 0.15 * noise(L, rng, lambda ff: band(ff, 3000, 9000, 2, 2)) * env
        add(x, amp * y, ns(t0))

    run(0.15, 1.25, 0.8, straw_from=0.8)
    for k, t0 in enumerate((1.45, 1.6, 1.78)):
        squeak(t0, 3300 + 200 * k, 4700 - 150 * k, 3900, rng.uniform(0.08, 0.13), 0.13)
    for t0 in (1.98, 2.1):
        squeak(t0, 2600, 3500, 3000, 0.11, 0.09)
    for k in range(6):                                              # squabble
        squeak(3.0 + 0.055 * k + rng.uniform(0, 0.02), loguniform(rng, 3000, 4000),
               loguniform(rng, 4300, 5600), loguniform(rng, 3200, 4200), 0.045, 0.1)
    run(3.4, 4.5, 0.6)
    run(4.7, 5.3, 0.25)
    x = filt(x, bq("hp", 700.0), bq("lp", 9000.0, 0.6))
    return fit(reverb(x, "cell", 2.5, tail=0.35), n)


@sound("ambient_creak", 7.0, fade_out=0.8, zoom=0.9,
       desc="Old ceiling timbers settling: slow groaning stick-slip creaks of loaded oak beams and "
            "a fibre tick, in the hall")
def ambient_creak(n, rng):
    t = np.arange(n) / SR
    bf = np.array([72, 118, 165, 231, 310, 402, 515, 660, 830, 1050, 1350, 1800, 2300, 2900], float)
    beam = body_ir(bf, LN1000 * loguniform(rng, 5, 12, len(bf)) / (np.pi * bf),
                   rng.uniform(0.4, 1.0, len(bf)) * np.linspace(0.6, 1.0, len(bf)), 0.6)
    v = np.zeros(n)
    for t0, d, r0, r1 in ((0.2, 1.1, 20.0, 140.0), (2.6, 0.55, 80.0, 190.0), (4.0, 1.5, 15.0, 110.0)):
        u = np.clip((t - t0) / d, 0, 1)
        prof = np.sin(np.pi * u) ** 0.6 * ((t >= t0) & (t <= t0 + d))
        v += (r0 + (r1 - r0) * np.sin(np.pi * u * 0.8)) * prof
    load = 1.0 + 0.15 * lfo(n, 0.5, 2.0, rng)
    x = creak_voice(n, rng, 0.8 * v, load, beam, pulse_ms=0.6, jitter=0.06, slow_jitter=0.5, v_ref=30.0,
                    noise_amt=0.05, direct=0.45, direct_band=(150.0, 3500.0))
    x /= np.abs(x).max()
    for tj, a in ((3.55, 0.55), (5.95, 0.35)):                   # a fibre lets go
        tick = burst(0.01, 0.0006, rng, lambda f: band(f, 800, 8000, 1, 2))
        tick = np.concatenate([tick, np.zeros(ns(0.4))])
        tick += 0.8 * modes(*random_modes(rng, 6, 180, 1200, q=(8, 20)), len(tick) / SR, tau=0.0005)
        add(x, a * tick / np.abs(tick).max(), ns(tj))
    return fit(reverb(x, "hall", 5.0, tail=0.5), n)


@sound("ambient_boom", 6.6, fade_out=1.0,
       desc="A heavy iron-bound door slammed somewhere far off: low thud, latch clank, corridor "
            "echoes and the long tail of the great vaults")
def ambient_boom(n, rng):
    dry = np.zeros(ns(1.5))
    df = np.array([48.0, 71.0, 97.0, 126.0, 158.0, 197.0, 241.0, 300.0, 372.0, 455.0])
    door = modes(df, rng.uniform(0.25, 0.6, 10), np.linspace(1.0, 0.35, 10), 1.5, tau=0.004)
    dry += door / np.abs(door).max()
    thud = burst(0.4, 0.05, rng, lambda f: band(f, 30, 300, 2, 2))
    hit = burst(0.1, 0.012, rng, lambda f: band(f, 400, 4000, 1, 2))
    dry[:len(thud)] += 0.9 * thud / np.abs(thud).max()
    dry[:len(hit)] += 0.3 * hit / np.abs(hit).max()
    latch = modes(*random_modes(rng, 10, 700, 3500, q=(80, 200)), 0.6, tau=0.0003)
    add(dry, 0.25 * latch / np.abs(latch).max(), ns(0.025))
    dry = filt(dry, bq("lp", 1100.0, 0.55), bq("lp1", 900.0))        # far away, round corners
    x = np.zeros(n)
    add(x, dry, ns(0.12))
    for k, (d, a) in enumerate(((0.19, 0.75), (0.42, 0.55), (0.68, 0.38), (0.97, 0.25), (1.3, 0.15))):
        e = filt(dry, bq("lp", 1000.0 / (1 + 0.25 * k), 0.6))      # corridor flutter, darker each time
        add(x, a * e, ns(0.12 + d))
    return fit(reverb(x, "hall", 14.0, tail=0.6), n)


# =============================================================================================
# Verification
# =============================================================================================

def verify(path, loop, x_float=None):
    with wave.open(path, "rb") as w:
        info = dict(channels=w.getnchannels(), bits=8 * w.getsampwidth(), rate=w.getframerate(),
                    comptype=w.getcomptype(), frames=w.getnframes())
        raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float)
    x = raw / 32768.0
    n = len(x)
    info["seconds"] = round(n / SR, 4)
    pk = np.abs(x).max()
    info["peak_dbfs"] = round(20 * np.log10(pk), 2)
    nfft = fast_len(n) if loop else fast_len(n + 2048)
    X = np.fft.rfft(x, nfft)
    up = np.fft.irfft(np.concatenate([X, np.zeros(2 * nfft + 1 - len(X))]), 4 * nfft) * 4
    info["true_peak_dbfs"] = round(20 * np.log10(np.abs(up).max()), 2)
    info["dc_offset"] = float("%.2e" % x.mean())
    info["clipped_samples"] = int(np.sum(np.abs(raw) >= 32767))
    info["rms_dbfs"] = round(10 * np.log10(np.mean(x * x)), 2)
    info["lufs"] = round(lufs(x, loop), 1)
    checks = {
        "format_16bit_mono_44k1": info["channels"] == 1 and info["bits"] == 16 and info["rate"] == SR
                                  and info["comptype"] == "NONE",
        "under_10s": n / SR < MAX_SECONDS,
        "peak_-1dBFS": abs(info["peak_dbfs"] - PEAK_DBFS) < 0.15,
        "true_peak_below_0": info["true_peak_dbfs"] < 0.0,
        "no_dc": abs(x.mean()) < 1e-3,
        "no_clipping": info["clipped_samples"] == 0,
    }
    if loop:
        d1 = np.diff(x)
        d2 = np.diff(x, 2)
        seam_step = x[0] - x[-1]
        seam_curv = max(abs(x[1] - 2 * x[0] + x[-1]), abs(x[0] - 2 * x[-1] + x[-2]))
        p_d1 = np.percentile(np.abs(d1), 99.5)
        p_d2 = np.percentile(np.abs(d2), 99.5)
        # click detector: 2nd-difference energy in a 2 ms window centred on each sample (circular)
        xw = np.concatenate([x[-2:], x, x[:2]])
        e = np.diff(xw, 2)[1:n + 1] ** 2                         # e[i] centred on x[i]
        w = ns(0.002) | 1
        win = moving_avg(e, w, loop=True)
        rank = float(np.mean(win < win[0]))
        info.update(seam_first=int(raw[0]), seam_last=int(raw[-1]),
                    seam_step=float("%.3e" % seam_step), seam_curvature=float("%.3e" % seam_curv),
                    p995_step=float("%.3e" % p_d1), p995_curvature=float("%.3e" % p_d2),
                    seam_click_rank=round(rank, 3))
        checks["seam_step_ok"] = abs(seam_step) <= p_d1
        checks["seam_slope_ok"] = seam_curv <= p_d2
        checks["seam_no_click"] = rank < 0.99
    else:
        info.update(first_sample=int(raw[0]), last_sample=int(raw[-1]),
                    tail_rms_dbfs=round(10 * np.log10(np.mean(x[-ns(0.01):] ** 2) + 1e-20), 1))
        checks["starts_at_zero"] = abs(raw[0]) <= 2
        checks["ends_at_zero"] = abs(raw[-1]) <= 2
    info["checks"] = {k: bool(v) for k, v in checks.items()}
    info["ok"] = all(info["checks"].values())
    return info


# =============================================================================================
# Previews (Pillow): waveform + multi-resolution log-frequency spectrogram
# =============================================================================================

_CMAP = np.array([[0, 0, 4], [31, 12, 72], [85, 15, 109], [136, 34, 106], [186, 54, 85],
                  [227, 89, 51], [249, 140, 10], [249, 201, 50], [252, 255, 164]], float)


def _colormap(v):
    i = v * (len(_CMAP) - 1)
    i0 = np.clip(np.floor(i).astype(int), 0, len(_CMAP) - 2)
    fr = (i - i0)[..., None]
    return (_CMAP[i0] * (1 - fr) + _CMAP[i0 + 1] * fr).astype(np.uint8)


def _spec_rows(xs, ncols, rows_f, loop):
    """dB magnitude at log-spaced frequencies, blending 8192 / 2048 / 512-point analyses."""
    n = len(xs)
    centers = ((np.arange(ncols) + 0.5) * n / ncols).astype(int)
    out = np.zeros((len(rows_f), ncols))
    wsum = np.zeros(len(rows_f))
    lf = np.log2(rows_f)
    weights = {8192: np.clip(np.log2(400.0) - lf + 0.5, 0, 1),
               512: np.clip(lf - np.log2(3000.0) + 0.5, 0, 1)}
    weights[2048] = np.clip(1 - weights[8192] - weights[512], 0, 1)
    for nfft, wt in weights.items():
        if not wt.any():
            continue
        win = 0.5 - 0.5 * np.cos(TWO_PI * np.arange(nfft) / nfft)
        pad = nfft
        xp = np.concatenate([xs[-pad:], xs, xs[:pad]]) if loop else np.concatenate([np.zeros(pad), xs, np.zeros(pad)])
        spec = np.zeros((ncols, nfft // 2 + 1))
        for c in range(0, ncols, 128):
            st = centers[c:c + 128] - nfft // 2 + pad
            fr = xp[st[:, None] + np.arange(nfft)[None, :]] * win
            spec[c:c + 128] = np.abs(np.fft.rfft(fr, axis=1)) ** 2 / np.sum(win ** 2)
        db = 10 * np.log10(spec + 1e-14)
        b = rows_f * nfft / SR
        b0 = np.clip(np.floor(b).astype(int), 0, nfft // 2 - 1)
        fr = b - b0
        val = db[:, b0] * (1 - fr) + db[:, b0 + 1] * fr
        out += wt[:, None] * val.T
        wsum += wt
    return out / np.maximum(wsum, 1e-9)[:, None]


def render_preview(name, x, loop, desc, info, path, zoom=None):
    from PIL import Image, ImageDraw, ImageFont

    def font(sz):
        try:
            return ImageFont.load_default(size=sz)
        except Exception:
            return ImageFont.load_default()

    f12, f14, f18 = font(12), font(14), font(18)
    xs = np.concatenate([x, x]) if loop else x
    dur = len(xs) / SR
    W, L, R = 1400, 64, 16
    PW = W - L - R
    y_wave, h_wave = 62, 170
    y_spec, h_spec = y_wave + h_wave + 16, 420
    y_axis = y_spec + h_spec
    y_seam, h_seam = y_axis + 34, 150
    y_text = (y_seam + h_seam + 14) if (loop or zoom is not None) else (y_axis + 34)
    H = y_text + 6 * 17 + 10
    img = Image.new("RGB", (W, H), (18, 18, 22))
    d = ImageDraw.Draw(img)
    d.text((L, 8), name + ("   [seamless loop, shown twice; seam at the dashed line]" if loop else ""),
           fill=(240, 220, 170), font=f18)
    d.text((L, 34), desc, fill=(190, 190, 200), font=f12)
    # waveform
    d.rectangle([L, y_wave, L + PW, y_wave + h_wave], fill=(10, 10, 14))
    cols = PW
    edges = np.linspace(0, len(xs), cols + 1).astype(int)
    mid = y_wave + h_wave / 2
    sc = (h_wave / 2 - 2)
    for lvl in (1.0, 10 ** (PEAK_DBFS / 20), 0.5, 0.0, -0.5, -10 ** (PEAK_DBFS / 20), -1.0):
        yy = mid - lvl * sc
        d.line([L, yy, L + PW, yy], fill=(60, 60, 70) if abs(lvl) != 10 ** (PEAK_DBFS / 20) else (90, 40, 40))
    for c in range(cols):
        seg = xs[edges[c]:max(edges[c + 1], edges[c] + 1)]
        lo, hi = seg.min(), seg.max()
        rms = np.sqrt(np.mean(seg ** 2))
        d.line([L + c, mid - hi * sc, L + c, mid - lo * sc], fill=(90, 150, 220))
        d.line([L + c, mid - rms * sc, L + c, mid + rms * sc], fill=(170, 210, 255))
    d.text((4, y_wave + 2), "wave", fill=(160, 160, 170), font=f12)
    d.text((4, y_wave + h_wave / 2 - 7), " 0", fill=(160, 160, 170), font=f12)
    # spectrogram
    fmin, fmax = 25.0, 20000.0
    rows_f = fmin * (fmax / fmin) ** (np.arange(h_spec)[::-1] / (h_spec - 1))
    db = _spec_rows(xs, PW, rows_f, loop)
    top = np.percentile(db, 99.9)
    v = np.clip((db - (top - 90.0)) / 90.0, 0, 1)
    img.paste(Image.fromarray(_colormap(v)), (L, y_spec))
    for fq, lab in ((50, "50"), (100, "100"), (200, "200"), (500, "500"), (1000, "1k"), (2000, "2k"),
                    (5000, "5k"), (10000, "10k"), (20000, "20k")):
        yy = y_spec + (h_spec - 1) * (1 - np.log(fq / fmin) / np.log(fmax / fmin))
        d.line([L - 5, yy, L, yy], fill=(200, 200, 200))
        d.text((L - 40, yy - 7), lab, fill=(200, 200, 200), font=f12)
    d.text((4, y_spec - 14), "Hz", fill=(160, 160, 170), font=f12)
    # time axis
    step = 0.1 if dur <= 1.5 else 0.25 if dur <= 3 else 0.5 if dur <= 7 else 1.0 if dur <= 12 else 2.0
    tk = 0.0
    while tk <= dur + 1e-9:
        xx = L + PW * tk / dur
        d.line([xx, y_axis, xx, y_axis + 5], fill=(200, 200, 200))
        d.text((xx - 10, y_axis + 7), ("%.2f" % tk).rstrip("0").rstrip(".") + "s", fill=(200, 200, 200), font=f12)
        tk += step
    if loop:
        xx = L + PW / 2
        for yy in range(y_wave, y_spec + h_spec, 8):
            d.line([xx, yy, xx, yy + 4], fill=(255, 255, 255))
        # seam zoom: 5 ms either side, sample by sample
        k = ns(0.005)
        seg = np.concatenate([x[-k:], x[:k]])
        d.rectangle([L, y_seam, L + PW, y_seam + h_seam], fill=(10, 10, 14))
        m2 = y_seam + h_seam / 2
        s2 = (h_seam / 2 - 4) / max(np.abs(seg).max(), 1e-6)
        pts = [(L + PW * i / (len(seg) - 1), m2 - seg[i] * s2) for i in range(len(seg))]
        d.line(pts, fill=(120, 220, 140), width=1)
        for (px, py) in pts:
            d.point((px, py), fill=(230, 255, 230))
        d.line([L + PW / 2, y_seam, L + PW / 2, y_seam + h_seam], fill=(255, 80, 80))
        d.text((L + 6, y_seam + 4), "seam zoom: last 5 ms | first 5 ms (auto-scaled)", fill=(200, 200, 200), font=f12)
    elif zoom is not None:
        a = max(0, ns(zoom - 0.06))
        seg = xs[a:a + ns(0.12)]
        d.rectangle([L, y_seam, L + PW, y_seam + h_seam], fill=(10, 10, 14))
        m2 = y_seam + h_seam / 2
        s2 = (h_seam / 2 - 4) / max(np.abs(seg).max(), 1e-6)
        pts = [(L + PW * i / (len(seg) - 1), m2 - seg[i] * s2) for i in range(len(seg))]
        d.line(pts, fill=(120, 220, 140), width=1)
        for k in range(0, 121, 10):
            xx = L + PW * k / 120.0
            d.line([xx, y_seam + h_seam - 6, xx, y_seam + h_seam], fill=(200, 200, 200))
        d.text((L + 6, y_seam + 4), "detail: 120 ms from %.3f s (ticks every 10 ms, auto-scaled)" % (a / SR),
               fill=(200, 200, 200), font=f12)
        x0 = L + PW * a / len(xs)
        x1 = L + PW * (a + len(seg)) / len(xs)
        d.rectangle([x0, y_wave, x1, y_wave + h_wave], outline=(120, 220, 140))
    ck = info.get("checks", {})
    lines = [
        "%.3f s  %d Hz  %d-bit  %s  |  peak %.2f dBFS  true peak %.2f dBFS  RMS %.1f dBFS  loudness %.1f LUFS  DC %.1e"
        % (info["seconds"], info["rate"], info["bits"], "mono" if info["channels"] == 1 else "stereo",
           info["peak_dbfs"], info["true_peak_dbfs"], info["rms_dbfs"], info["lufs"], info["dc_offset"]),
    ]
    if loop:
        lines.append("seam: first %d / last %d LSB, step %.2e (p99.5 of steps %.2e), curvature %.2e (p99.5 %.2e), click rank %.3f"
                     % (info["seam_first"], info["seam_last"], info["seam_step"], info["p995_step"],
                        info["seam_curvature"], info["p995_curvature"], info["seam_click_rank"]))
    else:
        lines.append("edges: first sample %d LSB, last sample %d LSB, last 10 ms at %.1f dBFS"
                     % (info["first_sample"], info["last_sample"], info["tail_rms_dbfs"]))
    lines.append("checks: " + "  ".join(("%s %s" % ("OK" if v else "FAIL", k)) for k, v in ck.items()))
    for i, s in enumerate(lines):
        d.text((L, y_text + 17 * i), s, fill=(220, 220, 220) if "FAIL" not in s else (255, 120, 120), font=f14)
    img.save(path, optimize=True)


# =============================================================================================
# Main
# =============================================================================================

def build(name, previews=True):
    spec = SOUNDS[name]
    rng = rng_for(name)
    n = ns(spec["seconds"])
    t0 = time.time()
    x = spec["fn"](n, rng)
    x = fit(x, n)
    x = finish(x, spec["loop"], spec["limit_db"], spec["hold_ms"], fade_out=spec["fade_out"],
               target_lufs=spec["lufs"])
    pcm = to_pcm16(x, rng_for(name, "dither"))
    path = os.path.join(OUT_DIR, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    info = verify(path, spec["loop"])
    info.update(name=name, loop=spec["loop"], description=spec["desc"], build_s=round(time.time() - t0, 2))
    if previews:
        render_preview(name, pcm.astype(float) / 32768.0, spec["loop"], spec["desc"], info,
                       os.path.join(PREVIEW_DIR, name + ".png"), zoom=spec["zoom"])
    return info


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="sounds to build (default: all)")
    ap.add_argument("--no-previews", action="store_true")
    args = ap.parse_args(argv)
    names = args.names or list(SOUNDS)
    bad = [s for s in names if s not in SOUNDS]
    if bad:
        ap.error("unknown sound(s): %s (known: %s)" % (", ".join(bad), ", ".join(SOUNDS)))
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    report_path = os.path.join(OUT_DIR, "sounds_report.json")
    report = {}
    if os.path.exists(report_path):
        try:
            with open(report_path) as fh:
                report = json.load(fh)
        except Exception:
            report = {}
    print("%-18s %5s %6s %7s %7s %6s %9s  %s" % ("sound", "loop", "sec", "peak", "tpeak", "LUFS", "DC", "checks"))
    all_ok = True
    for name in names:
        info = build(name, previews=not args.no_previews)
        report[name] = info
        all_ok &= info["ok"]
        failed = [k for k, v in info["checks"].items() if not v]
        print("%-18s %5s %6.2f %7.2f %7.2f %6.1f %9.1e  %s" % (
            name, "yes" if info["loop"] else "", info["seconds"], info["peak_dbfs"], info["true_peak_dbfs"],
            info["lufs"], info["dc_offset"], "OK" if not failed else "FAIL: " + ", ".join(failed)))
    report = {k: report[k] for k in SOUNDS if k in report}
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=1)
    print("wrote %d sound(s) to %s" % (len(names), OUT_DIR))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())

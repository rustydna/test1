#!/usr/bin/env python3
"""The Villa - procedural sound design (luxury, calm, warm).

Every sound is synthesised from physical / musical models (no recorded samples) and written as a
Second Life upload-ready WAV: 16-bit PCM, mono, 44.1 kHz, shorter than 10 s, no DC offset,
click-free. Loops are exactly periodic (built circularly: events whose tails wrap to the start,
circular filters, circular reverb, circular STFT, oscillators at whole cycles per loop) so that
llLoopSound repeats them with no seam; this is verified numerically at the seam.

Levels: loops are loudness-normalised (ITU-R BS.1770 integrated) to -24 LUFS (fire, rain and
surf -20 LUFS) with the true peak kept at or below -1 dBFS; one-shots are peak-normalised to
-1 dBFS. Every file name starts with villa_ so the owner finds everything with one inventory
search.

    python3 villa/scripts/vsounds.py                      # build, verify and preview everything
    python3 villa/scripts/vsounds.py villa_fire villa_click
    python3 villa/scripts/vsounds.py --no-previews -j 1

Output: villa/output/sounds/<name>.wav, previews/<name>.png (waveform + spectrogram, loops drawn
twice with the seam zoomed, plus an analysis strip: long-term spectrum with the 8 kHz line and the
short-term loudness with the loudest events marked) and sounds_report.json (all checks).

The generic DSP comes from The Pit's toolkit (the_pit/scripts/sounds.py, loaded by path and not
modified): biquads applied through their exact response, coloured periodic noise, STFT noise
synthesis, modal synthesis with contact-time brightness, Minnaert bubbles (van den Doel),
image-source rooms with frequency-dependent tails, true-peak limiter and BS.1770 loudness.
This file adds the villa's spaces (open-plan living room, glass-roofed lounge, stone foyer,
outdoor terrace and garden with air absorption), the analysis ("listening") tools, and the
sounds themselves:

  loops     villa_pool_lap, villa_spillway, villa_spa_jets, villa_fire, villa_rain_glass,
            villa_surf, villa_night, villa_garden, villa_chimes, villa_lounge
  one-shots villa_door_slide, villa_door_soft, villa_curtain, villa_click, villa_splash,
            villa_ignite, villa_arrival

Analysis checks (on top of format, length, peak, DC, clipping, seam/edges):
  * loudness on target (loops, +-0.5 LU) and peak <= -1 dBFS;
  * harshness: share of energy above 8 kHz, worst 6 ms frame share above 8 kHz (a digital-noise
    click is white: ~ -2 dB; a soft natural transient is below -12 dB), and tonal whistles above
    8 kHz standing out of the local spectrum;
  * loops: no single event marking the repetition (loudest event vs the third loudest, short-term
    K-weighted loudness), and for every ambience (all loops but the lounge music, whose bars
    repeat by design) no repetition inside the loop: the highest peak of the spectro-temporal
    self-similarity at lags >= 0.6 s.
"""

import argparse
import importlib.util
import json
import os
import sys
import time
import wave
import zlib
from concurrent.futures import ProcessPoolExecutor

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
PIT_SOUNDS = os.path.normpath(os.path.join(HERE, "..", "..", "the_pit", "scripts", "sounds.py"))
_spec = importlib.util.spec_from_file_location("pit_sounds", PIT_SOUNDS)
S = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(S)

OUT_DIR = os.path.normpath(os.path.join(HERE, "..", "output", "sounds"))
PREVIEW_DIR = os.path.join(OUT_DIR, "previews")

SR = S.SR
TWO_PI = S.TWO_PI
LN1000 = S.LN1000
PEAK_DBFS = -1.0
MAX_SECONDS = 10.0

# generic toolkit (The Pit)
ns, fit, noise, lfo, band, tilt = S.ns, S.fit, S.noise, S.lfo, S.band, S.tilt
bq, filt, conv, smoothstep, loguniform = S.bq, S.filt, S.conv, S.smoothstep, S.loguniform
modes, random_modes, burst, bubble, drop_plink = S.modes, S.random_modes, S.burst, S.bubble, S.drop_plink
pulse_train, body_ir = S.pulse_train, S.body_ir

# analysis thresholds (see the docstring)
LUFS_TOL = 0.5
HF_SPLIT = 8000.0
HF_SHARE_MAX_DB = -20.0
HF_FRAME_MAX_DB = -12.0
HF_TONAL_MAX_DB = 15.0
STANDOUT_MAX_DB = 4.0
SELF_SIM_MAX = 0.35


# =============================================================================================
# Helpers
# =============================================================================================

def rng_for(name, salt=""):
    """Deterministic random generator per sound (and per sub-part)."""
    return np.random.default_rng(zlib.crc32(("villa/%s/%s" % (name, salt)).encode()))


def addw(out, sig, start, loop=False):
    """Mix sig into out at sample `start`; loops: whatever runs past the end wraps to the start
    (as many times as needed), which is exactly the steady state of the loop playing forever."""
    n, m, start = len(out), len(sig), int(start)
    if not loop:
        a, b = max(start, 0), min(start + m, n)
        if b > a:
            out[a:b] += sig[a - start:b - start]
        return
    pos, s = 0, start % n
    while pos < m:
        k = min(m - pos, n - s)
        out[s:s + k] += sig[pos:pos + k]
        pos += k
        s = 0


def rms(x):
    return float(np.sqrt(np.mean(np.square(x)))) + 1e-12


def unit(x):
    """Scale to unit RMS."""
    return x / rms(x)


def peak1(x):
    return x / (np.abs(x).max() + 1e-12)


def qf(f, n):
    """Quantise an oscillator frequency to a whole number of cycles per loop of n samples."""
    return max(1, round(f * n / SR)) * SR / n


def spread_times(rng, k, dur, jitter=0.3):
    """k event times around a loop of `dur` s: quasi-regular, each gap 1 +- jitter of the mean,
    random phase. Gaps are normalised so the rhythm continues across the seam."""
    g = rng.uniform(1 - jitter, 1 + jitter, k)
    return (rng.uniform(0, dur) + dur * np.concatenate([[0.0], np.cumsum(g)[:-1]]) / g.sum()) % dur


# air absorption, dB per metre (ISO 9613-1, 20 C, 70 % RH, octave centres, rounded)
_AIR_F = np.array([63.0, 125.0, 250.0, 500.0, 1000.0, 2000.0, 4000.0, 8000.0, 16000.0, 22050.0])
_AIR_DB = np.array([0.0001, 0.0004, 0.0011, 0.0024, 0.0045, 0.0086, 0.0236, 0.0838, 0.28, 0.42])


def air(f, d):
    """Magnitude response of d metres of air."""
    f = np.clip(np.asarray(f, float), 20.0, 22050.0)
    a = np.exp(np.interp(np.log(f), np.log(_AIR_F), np.log(_AIR_DB)))
    return 10.0 ** (-a * d / 20.0)


def shape(x, mag, loop=False):
    """Zero-phase filtering by a magnitude response mag(f) (circular for loops)."""
    n = len(x)
    if loop:
        return np.fft.irfft(np.fft.rfft(x) * mag(np.fft.rfftfreq(n, 1.0 / SR)), n)
    nf = S.fast_len(n + 8192)
    return np.fft.irfft(np.fft.rfft(x, nf) * mag(np.fft.rfftfreq(nf, 1.0 / SR)), nf)[:n]


# =============================================================================================
# Spaces: villa rooms (image sources + tail, The Pit's room model) and outdoor acoustics
# =============================================================================================

ROOMS = {
    # dims (m); RT60 per octave band 63 Hz .. 16 kHz (s). Microcement, glass and stone, but
    # rugs, deep sofas and curtains: short, warm, the treble absorbed first.
    "living":     dict(dims=(14.0, 9.5, 4.2), rt=(0.8, 0.7, 0.62, 0.58, 0.55, 0.5, 0.44, 0.36, 0.28)),
    "glasshouse": dict(dims=(9.0, 7.0, 4.6), rt=(0.9, 0.85, 0.8, 0.75, 0.7, 0.62, 0.52, 0.4, 0.3)),
    "foyer":      dict(dims=(7.5, 6.0, 6.5), rt=(1.25, 1.15, 1.05, 1.0, 0.95, 0.85, 0.7, 0.55, 0.4)),
}
S.ROOMS.update({"villa_" + k: v for k, v in ROOMS.items()})   # extends the dict at run time only


def room(x, name, dist, tail=1.0, loop=False, early=1.0):
    """Place x in a villa room, `dist` metres from the listener."""
    return S.reverb(x, "villa_" + name, dist, tail=tail, loop=loop, early=early)


def diffuse_tail(n_ir, rt, rng, t_on=0.005, t_mix=0.05):
    """Unit-energy stochastic reverb tail: noise split into octave bands (triangular weights in
    log frequency, a partition of unity), each decaying with its own RT60."""
    t = np.arange(n_ir) / SR
    X = np.fft.rfft(rng.standard_normal(n_ir))
    f = np.maximum(np.fft.rfftfreq(n_ir, 1.0 / SR), 1.0)
    late = np.zeros(n_ir)
    for i, (fc, T) in enumerate(zip(S.BANDS, rt)):
        w = np.clip(1.0 - np.abs(np.log2(f / fc)), 0.0, 1.0)
        if i == 0:
            w[f < fc] = 1.0
        if i == len(S.BANDS) - 1:
            w[f > fc] = 1.0
        late += np.fft.irfft(X * w, n_ir) * np.exp(-LN1000 * t / T)
    late *= smoothstep((t - t_on) / max(t_mix - t_on, 1e-3))
    return late / np.sqrt(np.sum(late ** 2))


OUTDOOR = {
    # sparse reflections (delay s, gain) from the facade, pergola, pool water and trees, and a
    # faint diffuse tail scattered back by the garden; `tail` = late energy re direct at 0 m
    "terrace": dict(refl=((0.006, 0.5), (0.019, 0.32), (0.034, 0.22), (0.058, 0.16), (0.085, 0.1)),
                    rt=(0.7, 0.7, 0.65, 0.6, 0.55, 0.45, 0.35, 0.25, 0.18), tail=0.12),
    "garden":  dict(refl=((0.011, 0.3), (0.037, 0.18), (0.075, 0.12), (0.13, 0.08)),
                    rt=(0.9, 0.9, 0.85, 0.8, 0.75, 0.65, 0.5, 0.35, 0.25), tail=0.2),
}
_OUT_CACHE = {}


def outdoor_ir(space, dist):
    key = (space, round(dist, 3))
    if key in _OUT_CACHE:
        return _OUT_CACHE[key]
    p = OUTDOOR[space]
    rng = rng_for("space", "%s/%.3f" % key)
    rt = np.array(p["rt"], float)
    n_ir = ns(1.1 * rt.max())
    refl = np.zeros(n_ir)
    for dly, g in p["refl"]:
        d = dly * rng.uniform(0.85, 1.15)
        gain = g * dist / (dist + 343.0 * d)                 # longer path, 1/r spreading
        for _ in range(4):                                   # a rough surface: a short cluster
            refl[ns(d + rng.uniform(0.0, 0.0015))] += 0.25 * gain * rng.uniform(0.6, 1.4)
    refl = filt(refl, bq("lp1", 5000.0))                    # foliage and plaster lose the treble
    late = diffuse_tail(n_ir, rt, rng, t_on=p["refl"][0][0], t_mix=0.08)
    h = refl + late * np.sqrt(p["tail"] * (1.0 + dist / 8.0))
    h[0] += 1.0
    _OUT_CACHE[key] = h
    return h


def outdoors(x, space, dist, loop=False):
    return conv(x, outdoor_ir(space, dist), loop=loop)


def plate(x, rng, rt=2.2, predelay=0.022, loop=True):
    """Lush musical reverb tail (for the lounge music)."""
    rts = rt * np.array([1.2, 1.15, 1.1, 1.05, 1.0, 0.9, 0.75, 0.55, 0.4])
    n_ir = ns(1.2 * rts.max())
    h = np.zeros(n_ir + ns(predelay))
    h[ns(predelay):] = diffuse_tail(n_ir, rts, rng, 0.0, 0.03)
    return conv(x, h, loop=loop)


# =============================================================================================
# Shared sound builders
# =============================================================================================

def lap_event(rng, a, cavity=True):
    """A small wave slapping the pool edge: water sheet slap, the overflow gutter's hollow air
    cavity 'clop', entrained bubbles, a few droplets falling off the lip, the gurgling backwash."""
    L = ns(1.4)
    t = np.arange(L) / SR
    att, dec = rng.uniform(0.05, 0.12), rng.uniform(0.12, 0.25)
    env = smoothstep(t / att) * np.exp(-np.maximum(t - att, 0.0) / dec)
    y = 0.5 * noise(L, rng, lambda f: band(f, 140, 2200, 1, 2) * tilt(f, -2.0)) * env
    if cavity:                                               # a soft 'clop': long contact, no click
        f1 = rng.uniform(170.0, 300.0)
        f2 = f1 * rng.uniform(2.1, 2.6)
        y += rng.uniform(0.25, 0.5) * peak1(modes([f1, f2], [LN1000 * 5 / (np.pi * f1), LN1000 * 6 / (np.pi * f2)],
                                                  [1.0, 0.4], 1.4, tau=rng.uniform(0.01, 0.018), t_off=att * 0.6))
    for _ in range(rng.poisson(10)):
        r = loguniform(rng, 1.5e-3, 6e-3)
        amp = 0.25 * (r / 6e-3) ** 0.5 * loguniform(rng, 0.3, 1.0)
        addw(y, amp * bubble(r, xi=rng.uniform(0.05, 0.3)), ns(0.02 + rng.gamma(1.5, 0.07)))
    for _ in range(rng.poisson(1.2)):
        pl = drop_plink(loguniform(rng, 900, 1900), rng.uniform(0.3, 0.8), rng.uniform(0.008, 0.018), 0.1, click=0.0)
        addw(y, pl, ns(rng.uniform(0.2, 0.7)))
    env2 = smoothstep((t - 0.15) / 0.25) * np.exp(-np.maximum(t - 0.4, 0.0) / 0.3)
    gurgle = noise(L, rng, lambda f: band(f, 90, 800, 2, 2)) * env2 * np.maximum(0.0, 1 + 0.7 * lfo(L, 8, 25, rng))
    y += 0.25 * gurgle
    y *= 1.0 - smoothstep((t - 1.3) / 0.1)
    return a * y


def soft_crackle(n, rng, clusters=3.0, ticks=20.0, settles=0.35, loop=True):
    """Refined wood crackle: rounded grains (no sample-step onsets), modest cluster sizes and no
    sap pops; ember settles as soft 'shff's. Band-limited below ~6 kHz."""
    dur = n / SR
    bus = np.zeros(n)

    def grain(a, tau, fq, mix):
        L = max(16, int(tau * SR * 8))
        t = np.arange(L) / SR
        e = np.exp(-t / tau) * smoothstep(t / max(0.3 * tau, 2.0 / SR))
        s = np.sin(TWO_PI * fq * t + rng.uniform(0, TWO_PI))
        return a * e * ((1 - mix) * rng.standard_normal(L) + 1.4 * mix * s)

    for _ in range(rng.poisson(clusters * dur)):            # fibre cascades: "crk-k-k"
        t0 = rng.uniform(0, dur)
        A = min(0.15 + 0.08 * rng.pareto(2.5), 0.3)
        m = 1 + rng.geometric(0.3)
        for j, tj in enumerate(t0 + np.cumsum(rng.exponential(0.006, m))):
            a = A * rng.uniform(0.3, 1.0) * 0.85 ** j
            addw(bus, grain(a, loguniform(rng, 0.15e-3, 0.8e-3), loguniform(rng, 900, 4000),
                            rng.uniform(0.2, 0.7)), ns(tj), loop)
    for _ in range(rng.poisson(ticks * dur)):                # embers ticking
        a = 0.08 * loguniform(rng, 0.1, 1.0)
        addw(bus, grain(a, loguniform(rng, 0.12e-3, 0.5e-3), loguniform(rng, 1500, 4500),
                        rng.uniform(0.0, 0.5)), ns(rng.uniform(0, dur)), loop)
    for _ in range(rng.poisson(settles * dur)):              # a log or ember settling
        t0 = rng.uniform(0, dur)
        b = burst(0.12, rng.uniform(0.015, 0.03), rng, lambda f: band(f, 250, 2500, 1, 2), attack=0.004)
        addw(bus, 0.05 * b, ns(t0), loop)
        for tj in t0 + rng.uniform(0, 0.08, 4):
            addw(bus, grain(0.05, loguniform(rng, 0.3e-3, 1e-3), loguniform(rng, 700, 2500), 0.5), ns(tj), loop)
    return filt(bus, bq("hp", 300.0), bq("peak", 2200.0, 0.8, 2.0), bq("lp", 5500.0, 0.6),
                bq("lp", 7500.0, 0.6), loop=loop)


def cricket_chirp(fc, npulse, pd, gap):
    """Field cricket chirp: npulse syllables (one closing stroke of the wing each), a pure tone
    from the harp resonance, gliding down slightly as the file slows, growing in level. No
    harmonics: the 2nd (~9 kHz) would whistle above 8 kHz, and at garden distance it is gone."""
    L = ns(npulse * (pd + gap) + 0.01)
    y = np.zeros(L)
    m = ns(pd)
    u = np.arange(m) / m
    for i in range(npulse):
        f = fc * (1 - 0.03 * u)
        ph = TWO_PI * np.cumsum(f) / SR
        env = np.sin(np.pi * u) ** 1.5 * (0.75 + 0.25 * i / max(1, npulse - 1))
        addw(y, env * np.sin(ph), ns(i * (pd + gap)))
    return y


def bird_syllable(rng, kind, f0, d, harm=(1.0, 0.1, 0.02)):
    """One syllable of a songbird: the syrinx makes a nearly pure, frequency-modulated tone."""
    L = max(ns(d), 64)
    u = np.arange(L) / L
    t = np.arange(L) / SR
    if kind == "whistle":
        f = f0 * (1 + rng.uniform(-0.05, 0.05) * u + 0.01 * np.sin(TWO_PI * rng.uniform(5, 9) * t))
    elif kind == "up":
        f = f0 * (1 + rng.uniform(0.15, 0.5) * u ** rng.uniform(0.6, 1.6))
    elif kind == "down":
        f = f0 * (1 + rng.uniform(0.15, 0.6) * (1 - u) ** rng.uniform(0.6, 1.6))
    elif kind == "arch":
        f = f0 * (1 + rng.uniform(0.08, 0.3) * np.sin(np.pi * u))
    elif kind == "warble":
        f = f0 * (1 + rng.uniform(0.04, 0.12) * np.sin(TWO_PI * rng.uniform(14, 30) * t + rng.uniform(0, TWO_PI)))
    else:                                                    # "chip": fast downward sweep
        f = f0 * (1.45 - 0.45 * u ** 0.7)
    ph = TWO_PI * np.cumsum(f) / SR + rng.uniform(0, TWO_PI)
    y = sum(h * np.sin(k * ph) for k, h in enumerate(harm, 1) if k * f.max() < 0.4 * SR)
    a, r = rng.uniform(0.08, 0.25), rng.uniform(0.15, 0.4)
    env = smoothstep(u / a) * smoothstep((1 - u) / r) * (1 + rng.uniform(-0.3, 0.3) * (u - 0.5))
    return y * env


def bird_phrase(rng, sylls, harm):
    """sylls: list of (kind, f0, dur, gap_after, amp) -> one phrase."""
    total = sum(d + g for _, _, d, g, _ in sylls) + 0.05
    y = np.zeros(ns(total))
    t = 0.0
    for kind, f0, d, g, a in sylls:
        addw(y, a * bird_syllable(rng, kind, f0, d, harm), ns(t))
        t += d + g
    return y


def blackbird(rng):
    """Mellow fluting phrase (1.5-3 kHz) of 3-5 varied notes, often ending in a soft twitter."""
    base = rng.uniform(1700, 2300)
    sy = []
    for _ in range(rng.integers(3, 6)):
        sy.append((rng.choice(["arch", "whistle", "down", "up", "arch"]), base * 2 ** rng.uniform(-0.35, 0.45),
                   rng.uniform(0.09, 0.26), rng.uniform(0.02, 0.07), rng.uniform(0.7, 1.0)))
    if rng.random() < 0.7:
        f = rng.uniform(3200, 4000)
        for _ in range(rng.integers(3, 7)):
            sy.append(("chip", f * rng.uniform(0.95, 1.05), rng.uniform(0.025, 0.04), rng.uniform(0.015, 0.03), 0.3))
    return bird_phrase(rng, sy, (1.0, 0.12, 0.03))


def robin(rng):
    """Thin, liquid warble: 6-10 short varied syllables jumping between 2.6 and 5 kHz."""
    sy = [(rng.choice(["whistle", "warble", "down", "up"]), loguniform(rng, 2600, 5000),
           rng.uniform(0.04, 0.14), rng.uniform(0.01, 0.05), rng.uniform(0.5, 1.0))
          for _ in range(rng.integers(6, 11))]
    return bird_phrase(rng, sy, (1.0, 0.05))


def finch(rng):
    """A few bright call chips, irregularly spaced."""
    sy = [("chip", rng.uniform(3000, 4200), rng.uniform(0.03, 0.05), rng.uniform(0.09, 0.25), rng.uniform(0.7, 1.0))
          for _ in range(rng.integers(2, 5))]
    return bird_phrase(rng, sy, (1.0, 0.15, 0.04))


def wren_trill(rng):
    """Distant fast trill of identical-ish chips, fading."""
    f = rng.uniform(3600, 4400)
    m = rng.integers(10, 18)
    rate = rng.uniform(14, 20)
    sy = [("chip", f * rng.uniform(0.98, 1.02), 0.6 / rate, 0.4 / rate, 1.0 - 0.4 * k / m) for k in range(m)]
    return bird_phrase(rng, sy, (1.0, 0.08))


def mtof(m):
    return 440.0 * 2.0 ** ((m - 69) / 12.0)


def pad_note(f, dur, rng, att=0.9, rel=1.5, cutoff=1500.0, voices=(-7.0, 0.0, 6.0)):
    """Warm analogue-style pad note: three detuned saw voices (additive, 1/k partials) through a
    gentle 12 dB/oct low-pass, slow attack and release."""
    L = ns(dur + rel)
    t = np.arange(L) / SR
    env = smoothstep(t / att) * (1.0 - smoothstep((t - dur) / rel))
    y = np.zeros(L)
    for c in voices:
        fv = f * 2 ** (c / 1200.0)
        for k in range(1, int(min(24, 7000 // fv)) + 1):
            a = (1.0 / k) / np.sqrt(1.0 + (k * fv / cutoff) ** 4)
            y += a * np.sin(TWO_PI * k * fv * t + rng.uniform(0, TWO_PI))
    return y * env / len(voices)


def epiano(f, vel, rng, dur=3.0):
    """Electric-piano tine (1:1 phase modulation with a decaying index, a faint tine 'ding')."""
    L = ns(dur)
    t = np.arange(L) / SR
    index = (0.6 + 1.2 * vel) * np.exp(-t / 0.3) + 0.12
    ph = TWO_PI * f * t + rng.uniform(0, TWO_PI)
    y = np.sin(ph + index * np.sin(ph))
    env = (0.55 * np.exp(-t / 0.45) + 0.45 * np.exp(-t / 2.6)) * smoothstep(t / 0.0025)
    env *= 1.0 - smoothstep((t - (dur - 0.25)) / 0.25)
    out = y * env
    if f * 7.02 < 7000:
        out += 0.05 * vel * np.sin(TWO_PI * f * 7.02 * t) * np.exp(-t / 0.02) * smoothstep(t / 0.0015)
    return vel ** 1.3 * out


def bass_note(f, dur, vel):
    L = ns(dur + 0.12)
    t = np.arange(L) / SR
    env = smoothstep(t / 0.012) * np.exp(-t / 1.6) * (1.0 - smoothstep((t - dur) / 0.1))
    ph = TWO_PI * f * t
    y = np.sin(ph) + 0.22 * np.sin(2 * ph + 0.3) + 0.06 * np.sin(3 * ph + 0.5) + 0.12 * np.sin(4 * ph) * np.exp(-t / 0.05)
    return vel * y * env


# =============================================================================================
# The sounds
# =============================================================================================

SOUNDS = {}


def sound(name, seconds, loop=False, lufs=None, limit_db=0.0, hold_ms=1.5, fade_out=None, zoom=None,
          unique=None, desc=""):
    """Register a sound. Loops: lufs = loudness target. One-shots: peak -1 dBFS (limit_db shaves
    peaks first). unique (default: every loop): the loop must not repeat itself within
    (self-similarity check)."""
    assert name.startswith("villa_")
    unique = loop if unique is None else unique

    def deco(fn):
        SOUNDS[name] = dict(fn=fn, seconds=seconds, loop=loop, lufs=lufs, limit_db=limit_db, hold_ms=hold_ms,
                            fade_out=fade_out, zoom=zoom, unique=unique, desc=desc)
        return fn
    return deco


# ---------------------------------------------------------------------------- water

@sound("villa_pool_lap", 9.8, loop=True, lufs=-24.0,
       desc="Gentle water lapping at the pool's overflow edge: irregular small waves slapping the lip, "
            "hollow gutter 'clop', bubbles, droplets, soft gurgle and trickle (9.8 s loop)")
def pool_lap(n, rng):
    dur = n / SR
    x = np.zeros(n)
    for t0 in spread_times(rng, 6, dur, 0.5):                # wave groups: uneven swell
        addw(x, lap_event(rng, rng.uniform(0.5, 1.0)), ns(t0), True)
        if rng.random() < 0.5:                               # the backwash of the same wave
            addw(x, lap_event(rng, rng.uniform(0.25, 0.45)), ns(t0 + rng.uniform(0.3, 0.6)), True)
    for _ in range(rng.poisson(5)):                          # reflected ripples, smaller
        addw(x, lap_event(rng, rng.uniform(0.2, 0.4), cavity=False), ns(rng.uniform(0, dur)), True)
    tr = np.zeros(n)
    for _ in range(rng.poisson(30 * dur)):                   # trickle down the gutter
        r = loguniform(rng, 1.2e-3, 4e-3)
        addw(tr, loguniform(rng, 0.2, 1.0) * bubble(r, xi=0.2), ns(rng.uniform(0, dur)), True)
    bed = noise(n, rng, lambda f: band(f, 250, 2500, 1, 2)) * np.exp(0.3 * lfo(n, 0.2, 1.0, rng))
    x = x / rms(x) + 0.3 * unit(tr) + 0.15 * bed
    x = outdoors(x, "terrace", 2.5, loop=True)
    return filt(x, bq("lp", 7000.0, 0.6), loop=True)


@sound("villa_spillway", 9.6, loop=True, lufs=-24.0,
       desc="Infinity edge: a thin water sheet falling softly into the catch trough - sheet hush, "
            "dense bubble chorus, low plunge (9.6 s loop)")
def spillway(n, rng):
    dur = n / SR
    lo = noise(n, rng, lambda f: band(f, 120, 900, 2, 2) * tilt(f, -1.0))
    lo *= np.exp(0.18 * lfo(n, 0.1, 0.6, rng) + 0.1 * lfo(n, 4, 12, rng))
    hi = noise(n, rng, lambda f: band(f, 700, 5000, 1, 3) * tilt(f, -3.0))
    hi *= np.exp(0.15 * lfo(n, 0.1, 0.6, rng) + 0.2 * lfo(n, 6, 18, rng))
    plunge = noise(n, rng, lambda f: band(f, 45, 220, 2, 2)) * np.exp(0.25 * lfo(n, 0.15, 0.8, rng))
    bub = np.zeros(n)
    for _ in range(rng.poisson(180 * dur)):
        r = loguniform(rng, 1.5e-3, 7e-3)
        a = (r / 7e-3) ** 0.6 * loguniform(rng, 0.3, 1.0)
        addw(bub, a * bubble(r, xi=rng.uniform(0.0, 0.25)), ns(rng.uniform(0, dur)), True)
    for _ in range(rng.poisson(1.2 * dur)):                  # an occasional larger 'blub'
        addw(bub, 0.6 * bubble(loguniform(rng, 8e-3, 14e-3), xi=0.1), ns(rng.uniform(0, dur)), True)
    x = unit(lo) + 0.6 * unit(hi) + 0.5 * unit(plunge) + 0.5 * unit(bub)
    x = outdoors(x, "terrace", 4.0, loop=True)
    return filt(x, bq("lp", 6500.0, 0.6), loop=True)


@sound("villa_spa_jets", 8.0, loop=True, lufs=-24.0,
       desc="Spa jets: pulsing underwater jets, dense rising bubbles, bubbles bursting and churning "
            "at the surface (8 s loop)")
def spa_jets(n, rng):
    dur = n / SR
    churn = np.exp(0.35 * lfo(n, 0.15, 0.8, rng) + 0.25 * lfo(n, 2, 6, rng))
    jet = noise(n, rng, lambda f: band(f, 70, 1000, 2, 2) * tilt(f, -1.5)) * churn
    bub = np.zeros(n)
    tt = rng.uniform(0, dur, rng.poisson(650 * dur))
    keep = rng.random(len(tt)) < np.interp(tt * SR, np.arange(n), churn / churn.max())
    for t0 in tt[keep]:
        r = loguniform(rng, 2e-3, 9e-3)
        addw(bub, (r / 9e-3) ** 0.7 * loguniform(rng, 0.25, 1.0) * bubble(r, xi=rng.uniform(0.1, 0.5)), ns(t0), True)
    sp = np.zeros(n)
    for _ in range(rng.poisson(160 * dur)):                  # bubble films bursting
        b = burst(0.006, loguniform(rng, 0.25e-3, 0.9e-3), rng, lambda f: band(f, 500, 5000, 1, 2), attack=0.0004)
        addw(sp, loguniform(rng, 0.1, 1.0) * b, ns(rng.uniform(0, dur)), True)
    slosh = noise(n, rng, lambda f: band(f, 200, 3500, 1, 2)) * np.maximum(0.0, 1 + 0.8 * lfo(n, 8, 25, rng)) * churn
    x = 0.7 * unit(jet) + unit(bub) + 0.25 * unit(sp) + 0.35 * unit(slosh)
    x = outdoors(x, "terrace", 2.0, loop=True)
    return filt(x, bq("lp", 6500.0, 0.6), loop=True)


# ---------------------------------------------------------------------------- fire

@sound("villa_fire", 9.5, loop=True, lufs=-20.0, hold_ms=1.0,
       desc="Refined fireplace: the flame's slow breathing roar, soft crackle and ember ticks, "
            "no sap pops (9.5 s loop)")
def fire(n, rng):
    roar = S.flame_roar(n, rng, f_body=125.0, puff=(1.1, 2.4), flutter=(4, 10), flutter_depth=0.3,
                        hiss=0.015, breath=0.4)
    roar *= np.exp(0.3 * lfo(n, 0.12, 0.45, rng))           # the flame breathing
    roar = filt(roar, bq("lp", 4000.0, 0.6), loop=True)
    cr = soft_crackle(n, rng, clusters=3.0, ticks=20.0, settles=0.35)
    x = unit(roar) + 0.8 * unit(cr)
    return room(x, "living", 2.5, tail=0.3, early=0.4, loop=True)


# ---------------------------------------------------------------------------- rain

@sound("villa_rain_glass", 9.8, loop=True, lufs=-20.0,
       desc="Rain on the glass roof, heard from the lounge: drops of every size tapping the panes, "
            "soft splashes, muffled rain on the garden outside, a drip from the eaves (9.8 s loop)")
def rain_glass(n, rng):
    dur = n / SR
    inten = np.exp(0.25 * lfo(n, 0.06, 0.3, rng))           # gusts
    k = rng.poisson(1200 * dur)
    tt = np.sort(rng.uniform(0, dur, k))
    tt = tt[rng.random(k) < np.interp(tt * SR, np.arange(n), inten / inten.max())]
    lam = 4.1 * 4.0 ** -0.21                                 # Marshall-Palmer, 4 mm/h (1/mm)
    D = np.minimum(0.4 + rng.exponential(1.0 / lam, len(tt)), 4.0)
    v = 9.65 - 10.3 * np.exp(-0.6 * D)                       # terminal velocity (m/s), Atlas
    amp = (D ** 3 * v) ** 0.6 / loguniform(rng, 1.2, 7.0, len(tt))
    amp = np.minimum(amp, np.percentile(amp, 99.5)) / np.percentile(amp, 99.5)
    tau_c = D * 1e-3 / v                                     # contact time of the drop
    pane_of = rng.integers(0, 6, len(tt))
    glass = np.zeros(n)
    for p in range(6):                                       # 3 panes x 2 impact regions
        h = body_ir(*random_modes(rng, 36, 220.0, 5200.0, q=(25, 90), tilt_db=-1.0), 0.35)
        exc = np.zeros(n)
        for lo, hi in ((0, 0.25e-3), (0.25e-3, 0.4e-3), (0.4e-3, 1.0)):
            sel = (pane_of == p) & (tau_c >= lo) & (tau_c < hi)
            if sel.any():
                exc += pulse_train(n, tt[sel], amp[sel], float(np.clip(np.median(tau_c[sel]), 0.15e-3, 0.6e-3)), loop=True)
        glass += conv(exc, h, loop=True)
    sp_env = pulse_train(n, tt, amp, 1.5e-3, loop=True)      # the water of each drop splashing
    splash = sp_env * noise(n, rng, lambda f: band(f, 800, 4500, 1, 2))
    bed = noise(n, rng, lambda f: band(f, 120, 4000, 1, 2) * tilt(f, -3.0) / np.sqrt(1 + (f / 500.0) ** 2))
    bed *= np.exp(0.2 * lfo(n, 0.06, 0.3, rng))             # garden rain through the glass (mass law)
    drips = np.zeros(n)
    for t0 in spread_times(rng, 4, dur, 0.4):
        addw(drips, drop_plink(loguniform(rng, 700, 1500), rng.uniform(0.5, 0.9), rng.uniform(0.012, 0.022),
                               rng.uniform(0.6, 1.0), click=0.0), ns(t0), True)
    drips = filt(drips, bq("lp", 2200.0, 0.6), loop=True)
    x = unit(glass) + 0.3 * unit(splash) + 0.35 * unit(bed) + 0.12 * unit(drips)
    x = room(x, "glasshouse", 2.0, tail=0.5, loop=True)
    return filt(x, bq("lp", 6500.0, 0.6), loop=True)


# ---------------------------------------------------------------------------- sea

@sound("villa_surf", 9.9, loop=True, lufs=-20.0, hold_ms=10.0,
       desc="Distant ocean surf below the villa: overlapping breakers along the shore at 140-320 m "
            "(air absorption), continuous roar, soft low thumps (9.9 s loop)")
def surf(n, rng):
    dur = n / SR
    waves = []
    for t0 in spread_times(rng, 5, dur, 0.3):
        waves.append(dict(t0=t0, a=rng.uniform(0.75, 1.0), d=rng.uniform(140, 320), rise=rng.uniform(0.6, 1.2),
                          decay=rng.uniform(1.6, 2.8), tilt=rng.uniform(-2.2, -1.0)))
    bed_l = np.exp(0.25 * lfo(n, 0.05, 0.3, rng))

    def env_of(w, tc):                                       # periodic sum over wraps
        e = np.zeros_like(tc)
        for m in (-1, 0, 1):
            dt = tc - w["t0"] - m * dur
            e += smoothstep((dt + w["rise"]) / w["rise"]) * np.where(dt > 0, np.exp(-np.maximum(dt, 0) / w["decay"]), 1.0)
        return w["a"] * e

    def crash_of(w, tc):
        e = np.zeros_like(tc)
        for m in (-1, 0, 1):
            dt = tc - w["t0"] - m * dur
            e += smoothstep((dt + 0.25) / 0.25) * np.where(dt > 0, np.exp(-np.maximum(dt, 0) / 0.6), 1.0)
        return w["a"] * e

    def mag(tc, f):
        F = f[None, :]
        bed = band(F, 25, 1500, 2, 2) * tilt(F, -2.0) * air(F, 400.0)
        p = (0.35 * np.interp(tc * SR, np.arange(n), bed_l, period=n)[:, None] * bed) ** 2
        for w in waves:
            sk = band(F, 35, 2200, 2, 1) * tilt(F, w["tilt"]) * air(F, w["d"])
            fk = band(F, 400, 6000, 1, 2) * tilt(F, -1.0) * air(F, w["d"])
            p = p + (env_of(w, tc)[:, None] * sk) ** 2 + (0.5 * crash_of(w, tc)[:, None] * fk) ** 2
        return np.sqrt(p)

    x = S.stft_noise(n, mag, rng, loop=True, hop=512, win_hops=8)
    low = np.zeros(n)
    for w in waves:                                          # the breaker's low thump, far away
        L = ns(2.5)
        t = np.arange(L) / SR
        th = noise(L, rng, lambda f: band(f, 22, 90, 2, 3)) * smoothstep(t / 0.15) * np.exp(-t / 0.6)
        addw(low, w["a"] * th, ns(w["t0"] - 0.1), True)
    x = unit(x) + 0.35 * unit(low)
    return filt(x, bq("hp", 22.0, 0.6), loop=True)


# ---------------------------------------------------------------------------- night and garden

@sound("villa_night", 9.6, loop=True, lufs=-24.0,
       desc="Warm summer night in the garden: three field crickets chirping at their own pace, a "
            "distant chorus of tree crickets, a faint far cicada, the softest breeze (9.6 s loop)")
def night(n, rng):
    dur = n / SR
    t = np.arange(n) / SR
    crickets = np.zeros(n)
    for _ in range(3):
        fc, d = rng.uniform(4300, 4900), rng.uniform(6, 22)
        k = max(1, int(round(dur / rng.uniform(0.38, 0.55))))
        chirp = cricket_chirp(fc, int(rng.integers(3, 5)), rng.uniform(0.012, 0.018), rng.uniform(0.008, 0.014))
        one = np.zeros(n)
        for s in spread_times(rng, k, dur, 0.05):
            addw(one, rng.uniform(0.85, 1.0) * chirp, ns(s), True)
        crickets += shape(one, lambda f: air(f, d), loop=True) * (6.0 / d)
    chorus = np.zeros(n)
    for _ in range(6):                                       # tree crickets: continuous trills
        fc, fp = qf(rng.uniform(2400, 3300), n), qf(rng.uniform(35, 55), n)
        pul = (0.5 - 0.5 * np.cos(TWO_PI * fp * t + rng.uniform(0, TWO_PI))) ** 2.5
        chorus += (np.sin(TWO_PI * fc * t + rng.uniform(0, TWO_PI)) * pul * np.exp(0.3 * lfo(n, 0.05, 0.3, rng))
                   * loguniform(rng, 0.3, 1.0))
    chorus = shape(chorus, lambda f: air(f, 40.0), loop=True)
    fb = qf(190.0, n)                                        # cicada: tymbal clicks at ~190 Hz
    cic = noise(n, rng, lambda f: band(f, 4200, 5600, 3, 3)) * (0.5 - 0.5 * np.cos(TWO_PI * fb * t)) ** 4
    cic = shape(cic, lambda f: air(f, 60.0), loop=True) * np.exp(0.4 * lfo(n, 0.05, 0.2, rng))
    breeze = noise(n, rng, lambda f: band(f, 80, 1500, 1, 2) * tilt(f, -3.0)) * np.exp(0.4 * lfo(n, 0.04, 0.25, rng))
    x = unit(crickets) + 0.3 * unit(chorus) + 0.12 * unit(cic) + 0.4 * unit(breeze)
    return outdoors(x, "garden", 12.0, loop=True)


@sound("villa_garden", 9.9, loop=True, lufs=-24.0,
       desc="Morning garden: a blackbird, a robin, finch calls and a distant wren trill, sparse and "
            "never the same phrase twice; leaves in a light breeze (9.9 s loop)")
def garden(n, rng):
    dur = n / SR
    makers = [blackbird, robin, finch, blackbird, wren_trill, robin, finch]
    order = [makers[i] for i in rng.permutation(len(makers))]
    calls = []
    for mk in order:
        y = mk(rng)
        d = rng.uniform(10, 30)
        y = shape(y, lambda f: air(f, d))
        env = np.sqrt(np.convolve(y * y, np.ones(ns(0.02)) / ns(0.02), "same"))
        calls.append(rng.uniform(0.75, 1.0) * y / env.max())
    free = dur - sum(len(c) for c in calls) / SR
    while free < 0.25 * len(calls):
        calls.pop()
        free = dur - sum(len(c) for c in calls) / SR
    gaps = free * rng.dirichlet(np.full(len(calls), 3.0))
    x = np.zeros(n)
    t = rng.uniform(0, dur)
    for c, g in zip(calls, gaps):
        addw(x, c, ns(t), True)
        t += len(c) / SR + g
    leaves = noise(n, rng, lambda f: band(f, 150, 3000, 1, 2) * tilt(f, -4.0)) * np.exp(0.45 * lfo(n, 0.05, 0.3, rng))
    x = x + 0.05 * leaves
    return outdoors(x, "garden", 15.0, loop=True)


@sound("villa_chimes", 9.9, loop=True, lufs=-24.0,
       desc="Tuned aluminium wind chimes, E-flat major pentatonic (Eb4 F4 G4 Bb4 C5 Eb5): sparse "
            "gusts, free-free tube partials with slowly beating doublets, a soft breeze (9.9 s loop)")
def chimes(n, rng):
    dur = n / SR
    notes = [311.13, 349.23, 392.00, 466.16, 523.25, 622.25]
    ratios = np.array([1.0, 2.756, 5.404, 8.933])           # free-free beam modes
    tubes = []
    for f1 in notes:
        fr = f1 * ratios * np.r_[1.0, 1 + rng.normal(0, 0.002, 3)]
        t60 = np.array([7.5, 3.8, 1.7, 0.8]) * (440.0 / f1) ** 0.35
        split = rng.uniform(0.4, 1.2, 4)                    # Hz: slightly oval tube -> doublets
        tubes.append((fr, t60, np.array([1.0, 0.65, 0.3, 0.12]), split))
    strikes = []
    for g in spread_times(rng, 3, dur, 0.35):              # three gusts
        tt = g + np.cumsum(np.r_[0.0, rng.exponential(0.3, int(rng.integers(1, 4)))])
        strikes += [(tj, rng.uniform(0.6, 1.0) * 0.85 ** j) for j, tj in enumerate(tt)]
    strikes += [(rng.uniform(0, dur), rng.uniform(0.5, 0.8)) for _ in range(2)]
    x = np.zeros(n)
    last = -1
    for tj, a in sorted(strikes):
        i = rng.integers(len(tubes))
        while i == last:
            i = rng.integers(len(tubes))
        last = i
        fr, t60, am, sp = tubes[i]
        w = am * rng.uniform(0.5, 1.0, 4) * 0.5
        y = modes(np.r_[fr - sp / 2, fr + sp / 2], np.r_[t60, t60 * 0.9], np.r_[w, w], min(dur, 1.1 * t60.max()),
                  tau=rng.uniform(0.0006, 0.0011))
        tok = modes(loguniform(rng, 700, 1600, 3), [0.03] * 3, [1.0] * 3, 0.05, tau=0.0005)
        y[:len(tok)] += 0.04 * tok
        addw(x, a * y, ns(tj), True)
    breeze = noise(n, rng, lambda f: band(f, 100, 1200, 1, 2) * tilt(f, -3.0)) * np.exp(0.5 * lfo(n, 0.05, 0.3, rng))
    x = x + 0.12 * rms(x) * unit(breeze)
    x = outdoors(x, "terrace", 3.0, loop=True)
    return filt(x, bq("lp", 9000.0, 0.6), loop=True)


# ---------------------------------------------------------------------------- music

LOUNGE_BPM = 100.0
BEAT = 60.0 / LOUNGE_BPM            # 0.6 s = 26460 samples
# 4 bars of 4/4 = 16 beats = 9.6 s = 423360 samples exactly: E-flat major,
# Ebmaj9 | Cm9 | Abmaj9 | Bb9sus4 (each: bass MIDI note, pad voicing, low-pass cutoff)
LOUNGE_CHORDS = [(39, [55, 58, 62, 65], 1300.0), (36, [51, 55, 58, 62], 1450.0),
                 (32, [55, 58, 60, 63], 1650.0), (34, [56, 60, 63, 65], 1400.0)]
# electric piano: (bar, beat, MIDI notes, velocity) - a soft stab on each downbeat, a melody above
LOUNGE_EP = [(0, 0.0, [58, 62, 67], 0.62), (0, 1.5, [74], 0.5), (0, 2.0, [70], 0.42), (0, 3.0, [77], 0.48),
             (1, 0.0, [58, 63, 67], 0.6), (1, 1.0, [74], 0.45), (1, 1.5, [75], 0.5), (1, 2.5, [70], 0.4),
             (1, 3.5, [67], 0.38),
             (2, 0.0, [60, 63, 67], 0.62), (2, 1.5, [70], 0.48), (2, 2.0, [72], 0.45), (2, 3.0, [75], 0.5),
             (2, 3.5, [74], 0.36),
             (3, 0.0, [60, 63, 68], 0.6), (3, 1.5, [72], 0.45), (3, 2.0, [70], 0.42), (3, 3.0, [72], 0.44),
             (3, 3.5, [74], 0.4)]
LOUNGE_BASS = [(0, 0.0, 39, 1.4, 0.8), (0, 2.5, 34, 0.4, 0.55), (0, 3.0, 39, 0.9, 0.6),
               (1, 0.0, 36, 1.8, 0.8), (1, 3.0, 34, 0.9, 0.6),
               (2, 0.0, 32, 1.4, 0.8), (2, 2.5, 39, 0.4, 0.55), (2, 3.0, 32, 0.9, 0.6),
               (3, 0.0, 34, 1.8, 0.8), (3, 2.5, 34, 0.4, 0.5), (3, 3.5, 38, 0.5, 0.55)]


@sound("villa_lounge", 9.6, loop=True, lufs=-24.0, unique=False,
       desc="Original warm chill-lounge loop, 100 BPM, 4 bars in E-flat: Ebmaj9 - Cm9 - Abmaj9 - "
            "Bb9sus4; analogue pad, electric piano melody, round bass, soft shaker (9.6 s loop)")
def lounge(n, rng):
    assert n == 16 * ns(BEAT)
    bar = 4 * BEAT
    t = np.arange(n) / SR
    pad = np.zeros(n)
    for b, (_, voicing, cut) in enumerate(LOUNGE_CHORDS):
        for m in voicing:
            addw(pad, pad_note(mtof(m), bar + 0.2, rng, cutoff=cut), ns(b * bar - 0.2), True)
    pad *= 1.0 + 0.06 * np.sin(TWO_PI * 2.0 * t / (n / SR))   # slow swell, 2 cycles per loop
    ep = np.zeros(n)
    for b, beat, notes, vel in LOUNGE_EP:
        for j, m in enumerate(notes):
            tj = b * bar + beat * BEAT + 0.012 * j + rng.normal(0, 0.005)
            addw(ep, epiano(mtof(m), vel * rng.uniform(0.94, 1.06), rng), ns(tj), True)
    ep *= 1.0 + 0.1 * np.sin(TWO_PI * qf(5.0, n) * t)        # tremolo, 48 cycles per loop
    bass = np.zeros(n)
    for b, beat, m, d, vel in LOUNGE_BASS:
        addw(bass, bass_note(mtof(m), d, vel), ns(b * bar + beat * BEAT + rng.normal(0, 0.003)), True)
    bass = filt(bass, bq("lp", 700.0, 0.6), loop=True)
    shaker = np.zeros(n)
    for i in range(32):                                      # eighths, off-beats leaning
        b = burst(0.07, 0.018 if i % 2 else 0.012, rng, lambda f: band(f, 2500, 6000, 2, 3), attack=0.004)
        addw(shaker, (1.0 if i % 2 else 0.55) * rng.uniform(0.85, 1.0) * b, ns(i * BEAT / 2 + rng.normal(0, 0.004)), True)
    shaker = filt(shaker, bq("lp", 6500.0, 0.6), loop=True)
    pad, ep, bass, shaker = unit(pad), 0.55 * unit(ep), 0.6 * unit(bass), 0.06 * unit(shaker)
    wet = plate(0.3 * pad + 0.45 * ep + 0.5 * shaker + 0.03 * bass, rng_for("villa_lounge", "plate"), loop=True)
    return pad + ep + bass + shaker + 0.8 * wet


# ---------------------------------------------------------------------------- doors and controls

@sound("villa_door_slide", 3.6, fade_out=0.5, zoom=2.62,
       desc="Heavy glass sliding door on a magnetic track: lock release, smooth linear-motor glide "
            "(brush seals, moving air, the pane's mass), magnetic soft stop into the gasket, latch")
def door_slide(n, rng):
    t = np.arange(n) / SR
    vmax = 0.75
    v = vmax * (smoothstep((t - 0.22) / 0.45) - smoothstep((t - 1.75) / 0.8))
    accel = np.abs(np.gradient(v) * SR)
    x = np.zeros(n)
    rel = peak1(modes(*random_modes(rng, 6, 700, 3200, q=(8, 18)), 0.12, tau=0.0004))
    addw(x, 0.18 * rel, ns(0.12))
    addw(x, 0.25 * peak1(modes([95.0, 160.0], [0.08, 0.06], [1.0, 0.5], 0.15, tau=0.004)), ns(0.12))
    ph = TWO_PI * np.cumsum(v / 0.012) / SR                  # pole pitch 12 mm
    drive = 0.6 * accel / accel.max() + 0.4 * v / vmax
    motor = (np.sin(ph) + 0.5 * np.sin(2 * ph) + 0.25 * np.sin(3 * ph) + 0.15 * np.sin(6 * ph)) * drive
    seal = noise(n, rng, lambda f: band(f, 250, 4000, 1, 2) * tilt(f, -2.5)) * (v / vmax) ** 1.3
    seal *= 1 + 0.15 * lfo(n, 20, 60, rng)
    whoosh = noise(n, rng, lambda f: band(f, 60, 600, 2, 2)) * (v / vmax) ** 2
    pane = body_ir(*random_modes(rng, 16, 45, 900, q=(15, 40), tilt_db=-3.0), 0.6)
    mass = conv(0.5 * seal + whoosh, pane)[:n]
    x += 0.06 * peak1(motor) + 0.05 * seal + 0.05 * whoosh + 0.05 * mass / (rms(mass) / rms(seal))
    t_end = 2.58
    thud = peak1(modes(*random_modes(rng, 10, 50, 400, q=(8, 18), tilt_db=-2.0), 0.7, tau=0.012))
    addw(x, 0.9 * thud, ns(t_end))
    addw(x, 0.4 * peak1(burst(0.2, 0.04, rng, lambda f: band(f, 30, 300, 2, 2), attack=0.006)), ns(t_end))
    addw(x, 0.12 * peak1(modes(*random_modes(rng, 5, 900, 2800, q=(10, 20)), 0.15, tau=0.0005)), ns(t_end + 0.06))
    return fit(room(x, "living", 3.0, tail=0.5), n)


@sound("villa_door_soft", 2.0, fade_out=0.45, zoom=0.5,
       desc="Heavy door closing under a hydraulic damper: gliding air, damper hiss, soft thud into "
            "the gasket, room air puff, quiet magnetic latch")
def door_soft(n, rng):
    t = np.arange(n) / SR
    t_hit = 0.5
    sw = smoothstep(t / 0.12) * (1 - smoothstep((t - (t_hit - 0.18)) / 0.18))
    x = 0.08 * noise(n, rng, lambda f: band(f, 50, 500, 2, 2)) * sw ** 2
    hiss = noise(n, rng, lambda f: band(f, 600, 3500, 2, 2)) * smoothstep((t - 0.15) / 0.1) * (1 - smoothstep((t - t_hit + 0.05) / 0.07))
    x += 0.025 * hiss
    addw(x, peak1(modes(*random_modes(rng, 12, 55, 420, q=(6, 14), tilt_db=-2.0), 1.2, tau=0.011)), ns(t_hit))
    addw(x, 0.35 * peak1(modes(*random_modes(rng, 8, 120, 900, q=(8, 16)), 0.5, tau=0.006)), ns(t_hit + 0.002))
    addw(x, 0.5 * peak1(burst(0.25, 0.035, rng, lambda f: band(f, 18, 140, 2, 2), attack=0.008)), ns(t_hit))
    addw(x, 0.1 * peak1(modes(*random_modes(rng, 5, 900, 2600, q=(10, 20)), 0.15, tau=0.0005)), ns(t_hit + 0.035))
    return fit(room(x, "living", 2.5, tail=0.5), n)


@sound("villa_curtain", 4.2, fade_out=0.5, zoom=0.35,
       desc="Motorised curtain: relay tick, quiet geared motor whirr ramping up, runners gliding in "
            "the track, heavy drapes swishing as the pleats gather, soft stop and settle")
def curtain(n, rng):
    t = np.arange(n) / SR
    s = smoothstep((t - 0.15) / 0.35) * (1 - smoothstep((t - 3.15) / 0.45))
    x = np.zeros(n)
    addw(x, 0.08 * peak1(modes(*random_modes(rng, 4, 1200, 3500, q=(10, 20)), 0.08, tau=0.0004)), ns(0.08))
    fc = 456.0 * s                                           # commutator ripple
    ph = TWO_PI * np.cumsum(fc) / SR
    rot = np.cumsum(fc / 12.0) / SR * TWO_PI
    motor = (np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.12 * np.sin(3 * ph) + 0.5 * np.sin(0.47 * ph)) * (1 + 0.1 * np.sin(rot))
    motor = motor * s + 0.3 * noise(n, rng, lambda f: band(f, 300, 3000, 2, 2)) * s
    roll = noise(n, rng, lambda f: band(f, 300, 2500, 1, 2)) * s
    bumps = np.zeros(n)
    for tj in S.thinning_times(rng, lambda tt: 8.0 * np.interp(tt, t, s), 0.0, 3.6, 8.0):
        addw(bumps, rng.uniform(0.3, 1.0) * burst(0.03, 0.006, rng, lambda f: band(f, 300, 1500, 1, 2), attack=0.002), ns(tj))
    drape = lambda f: band(f, 200, 3000, 1, 3) * tilt(f, -3.0)     # heavy lined fabric: no sizzle
    fabric = noise(n, rng, drape) * s ** 1.2
    fabric *= 0.7 + 0.3 * np.exp(0.6 * lfo(n, 1.5, 4.0, rng)) / 1.2
    pleats = np.zeros(n)                                     # each pleat folding onto the stack: 'fff'
    for tj in S.thinning_times(rng, lambda tt: 3.0 * np.interp(tt, t, s), 0.2, 3.5, 3.0):
        L = ns(0.4)
        u = np.arange(L) / SR
        a_, d_ = rng.uniform(0.03, 0.08), rng.uniform(0.07, 0.16)
        e = smoothstep(u / a_) * np.exp(-np.maximum(u - a_, 0.0) / d_)
        addw(pleats, rng.uniform(0.5, 1.0) * e * noise(L, rng, drape), ns(tj))
    x += (0.04 * unit(motor) + 0.05 * unit(roll) + 0.03 * peak1(bumps) + 0.08 * unit(fabric)
          + 0.07 * unit(pleats))
    t_stop = 3.6
    addw(x, 0.3 * peak1(modes(*random_modes(rng, 6, 120, 700, q=(6, 12)), 0.3, tau=0.004)), ns(t_stop))
    L = ns(0.6)
    tt = np.arange(L) / SR
    settle = noise(L, rng, lambda f: band(f, 300, 3000, 1, 2)) * smoothstep(tt / 0.02) * np.exp(-tt / 0.15)
    addw(x, 0.1 * settle, ns(t_stop))
    x = filt(x, bq("lp", 6500.0, 0.6))
    return fit(room(x, "living", 3.5, tail=0.4), n)


@sound("villa_click", 0.35, fade_out=0.12, zoom=0.06,
       desc="Premium light switch / menu tick: rocker leaving its detent, crisp damped snap and a "
            "low 'thock' from the plate")
def click(n, rng):
    x = np.zeros(n)
    t0 = 0.02
    addw(x, 0.12 * peak1(modes(*random_modes(rng, 4, 1500, 4000, q=(8, 14)), 0.05, tau=0.0003)), ns(t0))
    f = np.array([1850.0, 2950.0, 4300.0, 6100.0]) * rng.uniform(0.97, 1.03, 4)
    tick = modes(f, LN1000 * np.array([16, 18, 14, 12]) / (np.pi * f), [1.0, 0.7, 0.45, 0.25], 0.08, tau=0.00013)
    addw(x, 0.75 * peak1(tick), ns(t0 + 0.006))
    thock = modes(*random_modes(rng, 6, 300, 1300, q=(6, 11), tilt_db=-1.0), 0.12, tau=0.0007)
    addw(x, peak1(thock), ns(t0 + 0.0062))
    x = filt(x, bq("lp", 8500.0, 0.7))
    return fit(room(x, "living", 0.7, tail=0.08, early=0.5), n)


# ---------------------------------------------------------------------------- pool, fire, chime

@sound("villa_splash", 3.8, fade_out=0.7, zoom=0.25,
       desc="Someone slipping into the pool: water parting, soft body entry and 'gloop', light spray, "
            "droplets falling back, bubbles from hair and swimsuit, ripples lapping the edge")
def splash(n, rng):
    x = np.zeros(n)
    t0 = 0.08
    L = ns(0.8)
    tt = np.arange(L) / SR
    part = noise(L, rng, lambda f: band(f, 150, 3000, 1, 2)) * smoothstep(tt / 0.05) * np.exp(-tt / 0.18)
    addw(x, 0.5 * peak1(part), ns(t0))
    addw(x, 0.55 * peak1(burst(0.3, 0.07, rng, lambda f: band(f, 40, 220, 2, 2), attack=0.01)), ns(t0 + 0.06))
    for tb, r, a in ((0.18, 0.02, 0.7), (0.24, 0.016, 0.5), (0.3, 0.012, 0.35)):
        addw(x, a * bubble(r, xi=0.25), ns(t0 + tb))
    spray = noise(L, rng, lambda f: band(f, 400, 5500, 1, 2)) * smoothstep(tt / 0.03) * np.exp(-tt / 0.2)
    addw(x, 0.18 * peak1(spray), ns(t0 + 0.05))
    for _ in range(160):                                     # droplets falling back
        tj = t0 + 0.12 + rng.gamma(1.6, 0.18)
        a = 0.08 * loguniform(rng, 0.1, 1.0) * np.exp(-(tj - t0) / 0.8)
        if rng.random() < 0.4:
            addw(x, a * bubble(loguniform(rng, 0.8e-3, 3e-3)), ns(tj))
        else:
            addw(x, 0.5 * a * burst(0.004, loguniform(rng, 0.2e-3, 0.8e-3), rng, lambda f: band(f, 500, 5000, 1, 2)), ns(tj))
    for _ in range(120):                                     # air from hair and swimsuit
        tj = t0 + 0.2 + rng.gamma(1.3, 0.5)
        r = loguniform(rng, 2e-3, 9e-3)
        addw(x, 0.25 * (r / 9e-3) ** 0.5 * np.exp(-(tj - t0) / 1.5) * bubble(r), ns(tj))
    for k, tl in enumerate((0.85, 1.55, 2.3)):               # the ripples reach the edge
        addw(x, lap_event(rng, 0.35 * 0.65 ** k), ns(tl))
    x = filt(x, bq("hp", 40.0), bq("lp", 7000.0, 0.6))
    return fit(outdoors(x, "terrace", 3.0), n)


@sound("villa_ignite", 3.4, fade_out=0.9, zoom=0.62,
       desc="Gas fireplace ignition: two soft igniter ticks, valve thunk and gas hiss, the burner "
            "lighting with a low 'whoomp', flames spreading and settling to a gentle roar")
def ignite(n, rng):
    t = np.arange(n) / SR
    x = np.zeros(n)
    for tk in (0.06, 0.24):                                  # piezo spark: a tiny snap and a tick
        tick = 0.5 * peak1(modes(loguniform(rng, 2500, 4500, 3), [0.01] * 3, [1.0] * 3, 0.05, tau=0.0002))
        b = burst(0.004, 0.00025, rng, lambda f: band(f, 1500, 6000, 1, 2))
        tick[:len(b)] += peak1(b)
        addw(x, 0.22 * peak1(filt(tick, bq("lp", 5000.0, 0.6), bq("lp", 7000.0, 0.6))), ns(tk))
    addw(x, 0.2 * peak1(modes(*random_modes(rng, 6, 180, 900, q=(8, 14)), 0.2, tau=0.0015)), ns(0.36))
    # gas through the valve: a soft, rounded hiss (steep above 4 kHz - a bright 2nd-order hiss
    # alone, before the flame covers it, reads as digital noise)
    hiss = noise(n, rng, lambda f: band(f, 900, 4000, 2, 4) * tilt(f, -1.5)) * smoothstep((t - 0.36) / 0.05)
    x += 0.035 * hiss * (1 - 0.6 * smoothstep((t - 0.6) / 0.4))
    ti = 0.6
    pulse = np.where((t >= ti) & (t < ti + 0.07), np.sin(np.pi * (t - ti) / 0.07) ** 2, 0.0)
    x += 1.0 * peak1(filt(pulse, bq("hp", 30.0, 0.6), bq("lp", 250.0, 0.7)))
    whoosh = noise(n, rng, lambda f: band(f, 100, 3500, 1, 2) * tilt(f, -3.0))
    whoosh *= smoothstep((t - ti) / 0.03) * np.exp(-np.maximum(t - ti - 0.05, 0) / 0.22)
    x += 0.25 * whoosh
    roar = S.flame_roar(n, rng, f_body=140.0, puff=(1.5, 3.0), flutter=(5, 12), flutter_depth=0.3, hiss=0.02, breath=0.45)
    roar = filt(roar, bq("lp", 4500.0, 0.6))
    x += 0.18 * unit(roar) * smoothstep((t - ti) / 0.35) * (0.6 + 0.4 * np.exp(-np.maximum(t - ti, 0) / 0.6))
    return fit(room(x, "living", 2.5, tail=0.35), n)


@sound("villa_arrival", 3.4, fade_out=0.9, zoom=0.66,
       desc="Arrival chime: two soft tuned tone bars (G5 then E-flat5) struck by felt-tipped "
            "plungers, resonator bloom, in the stone foyer")
def arrival(n, rng):
    def tone_bar(f1, vel):
        fr = f1 * np.array([1.0, 3.98, 9.85])
        y = modes(np.r_[fr, f1 * 1.0007], np.r_[3.4, 1.1, 0.35, 2.6], np.r_[1.0, 0.22, 0.05, 0.3], 3.3, tau=0.0013)
        tok = burst(0.02, 0.002, rng, lambda f: band(f, 300, 2500, 1, 2), attack=0.0005)
        y[:len(tok)] += 0.03 * tok
        return vel * y
    x = np.zeros(n)
    addw(x, tone_bar(783.99, 1.0), ns(0.04))
    addw(x, tone_bar(622.25, 0.92), ns(0.66))
    return fit(room(x, "foyer", 3.0, tail=0.6), n)


# =============================================================================================
# Mastering
# =============================================================================================

def true_peak(x, loop):
    return float(max(np.abs(x).max(), S.true_peak_env(x, loop).max()))


def master_loop(x, target, hold_ms=1.5):
    """DC removal, gain to the loudness target, true-peak limiting at -1 dBFS if needed."""
    x = filt(x - x.mean(), bq("hp", 18.0), loop=True)
    ceil = 10 ** (PEAK_DBFS / 20.0)
    limited = 0.0
    for _ in range(6):
        x = x * 10 ** ((target - S.lufs(x, True)) / 20.0)
        tp = true_peak(x, True)
        if tp <= ceil * 10 ** (-0.05 / 20):
            break
        step = 20 * np.log10(tp / ceil) + 0.15
        x = S.limiter(x, step, True, hold_ms)
        limited += step
    x = x - x.mean()
    tp = true_peak(x, True)
    if tp > ceil:
        x *= ceil / tp
    return x, limited


def build(name, previews=True):
    spec = SOUNDS[name]
    rng = rng_for(name)
    n = ns(spec["seconds"])
    t0 = time.time()
    x = fit(np.asarray(spec["fn"](n, rng), float), n)
    if spec["loop"]:
        x, limited = master_loop(x, spec["lufs"], spec["hold_ms"])
    else:
        x = S.finish(x, False, spec["limit_db"], spec["hold_ms"], fade_out=spec["fade_out"])
        limited = spec["limit_db"]
    pcm = S.to_pcm16(x, rng_for(name, "dither"))
    path = os.path.join(OUT_DIR, name + ".wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())
    info = verify(path, spec)
    info.update(name=name, file=os.path.relpath(path, os.path.join(HERE, "..")), loop=spec["loop"],
                description=spec["desc"], limiter_db=round(float(limited), 2), build_s=round(time.time() - t0, 2))
    if name == "villa_lounge":
        info.update(bpm=LOUNGE_BPM, bars=4, beats=16, samples_per_beat=ns(BEAT))
    if previews:
        xs = pcm.astype(float) / 32768.0
        ppath = os.path.join(PREVIEW_DIR, name + ".png")
        base = dict(info, checks={k: v for k, v in info["checks"].items() if k in BASE_CHECKS})
        S.render_preview(name, xs, spec["loop"], spec["desc"], base, ppath, zoom=spec["zoom"])
        extend_preview(ppath, xs, spec["loop"], info)
    return info


# =============================================================================================
# Verification and analysis ("listening")
# =============================================================================================

BASE_CHECKS = ("format_16bit_mono_44k1", "under_10s", "peak_-1dBFS", "true_peak_below_0", "no_dc", "no_clipping",
               "seam_step_ok", "seam_slope_ok", "seam_no_click", "starts_at_zero", "ends_at_zero")


def read_wav(path):
    with wave.open(path, "rb") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(float) / 32768.0


def kweight(x, loop):
    return filt(x, bq("hshelf", 1681.974450955533, 0.7071752369554196, 3.999843853973347),
                bq("hp", 38.13547087602444, 0.5003270373238773), loop=loop)


def short_term_db(x, loop, win=0.05, hop=0.01):
    """K-weighted loudness in 50 ms windows every 10 ms (dB, BS.1770 scale)."""
    y = kweight(x, loop)
    e = y * y
    w = ns(win) | 1
    h = w // 2
    ep = np.concatenate([e[-h:], e, e[:h]]) if loop else np.concatenate([np.zeros(h), e, np.zeros(h)])
    c = np.concatenate([[0.0], np.cumsum(ep)])
    m = (c[w:] - c[:-w])[:len(x)] / w
    return -0.691 + 10 * np.log10(m[::ns(hop)] + 1e-14)


def events(env, loop, hop=0.01, sep=0.3, prom=3.0):
    """Peaks of the short-term loudness: local maxima over +-sep/2 that stand prom dB above the
    minimum within +-0.4 s. Returns (indices sorted loudest first)."""
    k, kp = int(round(sep / 2 / hop)), int(round(0.4 / hop))
    m = len(env)
    pad = (lambda a, q: np.concatenate([a[-q:], a, a[:q]])) if loop else \
          (lambda a, q: np.concatenate([np.full(q, -np.inf), a, np.full(q, -np.inf)]))
    ev = pad(env, k)
    win = np.lib.stride_tricks.sliding_window_view(ev, 2 * k + 1)[:m]
    is_max = env >= win.max(axis=1)
    lo = pad(env, kp)
    lo = np.where(np.isinf(lo), np.inf, lo)
    mins = np.lib.stride_tricks.sliding_window_view(lo, 2 * kp + 1)[:m].min(axis=1)
    idx = np.flatnonzero(is_max & (env - mins >= prom))
    return idx[np.argsort(-env[idx])]


def welch_db(x, loop, nfft=4096):
    hop = nfft // 2
    win = 0.5 - 0.5 * np.cos(TWO_PI * np.arange(nfft) / nfft)
    xp = np.concatenate([x, x[:nfft]]) if loop else np.concatenate([x, np.zeros(nfft)])
    st = np.arange(0, len(x), hop)
    fr = xp[st[:, None] + np.arange(nfft)[None, :]] * win
    p = np.mean(np.abs(np.fft.rfft(fr, axis=1)) ** 2, axis=0)
    return np.fft.rfftfreq(nfft, 1.0 / SR), 10 * np.log10(p + 1e-20)


def self_similarity(x, min_lag=0.6, nfft=2048, hop=512, nbhd=0.25):
    """Repetition inside the loop: the highest peak, at lags >= min_lag, of the circular
    autocorrelation of the z-scored log band energies (18 bands, 100 Hz - 9 kHz). 1 = the loop
    contains an exact repetition of itself. Only local maxima (the highest point within +-nbhd s)
    count: a sound that merely evolves slowly (long chime decays, a bird phrase still going on)
    stays correlated at short lags without repeating anything. No peak at all -> 0."""
    n = len(x)
    win = 0.5 - 0.5 * np.cos(TWO_PI * np.arange(nfft) / nfft)
    xp = np.concatenate([x, x[:nfft]])
    st = np.arange(0, n, hop)
    P = np.abs(np.fft.rfft(xp[st[:, None] + np.arange(nfft)[None, :]] * win, axis=1)) ** 2
    f = np.fft.rfftfreq(nfft, 1.0 / SR)
    edges = np.geomspace(100.0, 9000.0, 19)
    B = np.stack([P[:, (f >= a) & (f < b)].sum(axis=1) for a, b in zip(edges[:-1], edges[1:])], axis=1)
    keep = B.mean(axis=0) > 1e-6 * B.mean(axis=0).max()
    Z = np.log10(B[:, keep] + 1e-14)
    Z = (Z - Z.mean(axis=0)) / (Z.std(axis=0) + 1e-9)
    T = len(Z)
    ac = np.fft.irfft(np.abs(np.fft.rfft(Z, axis=0)) ** 2, T, axis=0).mean(axis=1) / T
    ac /= ac[0]
    l0 = int(np.ceil(min_lag * SR / hop))
    k = max(1, int(round(nbhd * SR / hop)))
    acp = np.concatenate([ac[-k:], ac, ac[:k]])              # circular: lag T-1 neighbours lag 0
    lags = np.arange(l0, T // 2 + 1)
    peaks = [i for i in lags if ac[i] >= acp[i:i + 2 * k + 1].max()]
    if not peaks:
        return 0.0, 0.0
    i = max(peaks, key=lambda j: ac[j])
    return max(0.0, float(ac[i])), i * hop / SR


def hf_analysis(x, loop):
    """Harshness: whole-file share above 8 kHz, the worst 6 ms frame's share (frames within 30 dB
    of the loudest), and tonal peaks above 8 kHz standing out of the local spectrum."""
    X = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    share = 10 * np.log10(X[f >= HF_SPLIT].sum() / (X[f > 20].sum() + 1e-20) + 1e-20)
    nfft, hop = 256, 128
    win = 0.5 - 0.5 * np.cos(TWO_PI * np.arange(nfft) / nfft)
    xp = np.concatenate([x, x[:nfft]]) if loop else np.concatenate([x, np.zeros(nfft)])
    st = np.arange(0, len(x), hop)
    P = np.abs(np.fft.rfft(xp[st[:, None] + np.arange(nfft)[None, :]] * win, axis=1)) ** 2
    ff = np.fft.rfftfreq(nfft, 1.0 / SR)
    tot = P[:, 1:].sum(axis=1)
    hf = P[:, ff >= HF_SPLIT].sum(axis=1)
    lvl = 10 * np.log10(tot + 1e-20)
    sel = (lvl > lvl.max() - 30) & (lvl > 10 * np.log10(nfft * 0.375) - 70)
    frac = 10 * np.log10(hf[sel] / tot[sel] + 1e-20)
    worst = int(np.flatnonzero(sel)[np.argmax(frac)])
    fw, pdb = welch_db(x, loop)
    tonal = -99.0
    for i in np.flatnonzero((fw >= HF_SPLIT) & (fw < 20000)):
        if pdb[i] < pdb.max() - 45:
            continue
        nb = (fw >= fw[i] * 2 ** (-1 / 6)) & (fw <= fw[i] * 2 ** (1 / 6))
        tonal = max(tonal, pdb[i] - np.median(pdb[nb]))
    return dict(hf_share_db=round(float(share), 1), hf_frame_max_db=round(float(frac.max()), 1),
                hf_frame_max_at_s=round(st[worst] / SR, 3), hf_tonal_db=round(float(tonal), 1))


def analyse(x, loop):
    a = {}
    X = np.abs(np.fft.rfft(x)) ** 2
    f = np.fft.rfftfreq(len(x), 1.0 / SR)
    tot = X[f > 20].sum() + 1e-20
    bands = (("sub", 20, 60), ("low", 60, 250), ("lowmid", 250, 1000), ("mid", 1000, 4000),
             ("high", 4000, 8000), ("air", 8000, 22050))
    a["band_db"] = {k: round(float(10 * np.log10(X[(f >= lo) & (f < hi)].sum() / tot + 1e-20)), 1)
                    for k, lo, hi in bands}
    a["centroid_hz"] = int(round(float((f * X).sum() / X.sum())))
    a.update(hf_analysis(x, loop))
    env = short_term_db(x, loop)
    idx = events(env, loop)
    gated = env[env > env.max() - 60]
    med = float(np.median(gated))
    if len(idx) >= 3:
        standout = env[idx[0]] - env[idx[2]]
    elif len(idx):
        standout = env[idx[0]] - med
    else:
        standout = 0.0
    a["events"] = int(len(idx))
    a["top_events_s"] = [round(i * 0.01, 2) for i in idx[:3]]
    a["standout_db"] = round(float(standout), 1)
    a["event_crest_db"] = round(float(env.max() - med), 1)
    a["short_term_max_lufs"] = round(float(env.max()), 1)
    if loop:
        r, lag = self_similarity(x)
        a["self_similarity"] = round(r, 3)
        a["self_similarity_lag_s"] = round(lag, 2)
    return a


def verify(path, spec):
    loop = spec["loop"]
    info = S.verify(path, loop)                              # format, peaks, DC, clipping, seam / edges
    x = read_wav(path)
    info.update(analyse(x, loop))
    ck = info["checks"]
    if loop:
        ck.pop("peak_-1dBFS", None)
        ck["peak_le_-1dBFS"] = info["peak_dbfs"] <= PEAK_DBFS + 0.05
        info["lufs_target"] = spec["lufs"]
        ck["loudness_on_target"] = abs(info["lufs"] - spec["lufs"]) <= LUFS_TOL
        ck["no_standout_event"] = info["standout_db"] <= STANDOUT_MAX_DB
        if spec["unique"]:
            ck["not_repetitive"] = info["self_similarity"] <= SELF_SIM_MAX
    ck["hf_share_ok"] = info["hf_share_db"] <= HF_SHARE_MAX_DB
    ck["no_hf_spikes"] = info["hf_frame_max_db"] <= HF_FRAME_MAX_DB
    ck["no_hf_whistles"] = info["hf_tonal_db"] <= HF_TONAL_MAX_DB
    info["checks"] = {k: bool(v) for k, v in ck.items()}
    info["ok"] = all(info["checks"].values())
    return info


def extend_preview(path, x, loop, info):
    """Append an analysis strip to The Pit's preview: long-term spectrum (8 kHz line) and the
    short-term loudness with the three loudest events marked, then the villa checks."""
    from PIL import Image, ImageDraw, ImageFont

    def font(sz):
        try:
            return ImageFont.load_default(size=sz)
        except Exception:
            return ImageFont.load_default()

    f12, f14 = font(12), font(14)
    base = Image.open(path).convert("RGB")
    W, H0 = base.size
    villa = [k for k in info["checks"] if k not in BASE_CHECKS]
    lines = []
    if loop:
        lines.append("loudness %.1f LUFS (target %.0f)   limiter %.1f dB   loudest event vs 3rd loudest %.1f dB   "
                     "event crest %.1f dB   self-similarity %.2f (lag %.2f s)"
                     % (info["lufs"], info["lufs_target"], info["limiter_db"], info["standout_db"],
                        info["event_crest_db"], info["self_similarity"], info["self_similarity_lag_s"]))
    else:
        lines.append("loudness %.1f LUFS   short-term max %.1f LUFS   events %d   event crest %.1f dB"
                     % (info["lufs"], info["short_term_max_lufs"], info["events"], info["event_crest_db"]))
    b = info["band_db"]
    lines.append("spectrum: centroid %d Hz   sub %.0f  low %.0f  low-mid %.0f  mid %.0f  high %.0f  air %.0f dB   |   "
                 ">8 kHz share %.1f dB, worst 6 ms frame %.1f dB at %.2f s, HF tonal peak %.1f dB"
                 % (info["centroid_hz"], b["sub"], b["low"], b["lowmid"], b["mid"], b["high"], b["air"],
                    info["hf_share_db"], info["hf_frame_max_db"], info["hf_frame_max_at_s"], info["hf_tonal_db"]))
    lines.append("villa checks: " + "  ".join("%s %s" % ("OK" if info["checks"][k] else "FAIL", k) for k in villa))
    ph = 200
    H = H0 + ph + 40 + 18 * len(lines) + 10
    img = Image.new("RGB", (W, H), (18, 18, 22))
    img.paste(base, (0, 0))
    d = ImageDraw.Draw(img)
    y0 = H0 + 22
    # long-term spectrum
    L, PW = 64, 600
    d.rectangle([L, y0, L + PW, y0 + ph], fill=(10, 10, 14))
    fw, pdb = welch_db(x, loop)
    top = pdb[1:].max()
    fmin, fmax = 25.0, 20000.0
    sel = (fw >= fmin) & (fw <= fmax)
    xs_ = L + PW * np.log(fw[sel] / fmin) / np.log(fmax / fmin)
    ys_ = y0 + ph * np.clip((top + 3 - pdb[sel]) / 83.0, 0, 1)
    d.line(list(zip(xs_.tolist(), ys_.tolist())), fill=(250, 190, 90))
    for fq, lab in ((100, "100"), (1000, "1k"), (8000, "8k"), (10000, "10k")):
        xx = L + PW * np.log(fq / fmin) / np.log(fmax / fmin)
        d.line([xx, y0, xx, y0 + ph], fill=(200, 70, 70) if fq == 8000 else (60, 60, 70))
        d.text((xx - 8, y0 + ph + 3), lab, fill=(200, 200, 200), font=f12)
    d.text((L + 6, y0 + 4), "long-term spectrum (dB, 80 dB range); red line = 8 kHz", fill=(200, 200, 200), font=f12)
    # short-term loudness
    L2 = L + PW + 60
    PW2 = W - L2 - 16
    d.rectangle([L2, y0, L2 + PW2, y0 + ph], fill=(10, 10, 14))
    env = short_term_db(x, loop)
    emax = env.max()
    yy = lambda v: y0 + ph * np.clip((emax + 3 - v) / 50.0, 0, 1)
    xs2 = L2 + PW2 * np.arange(len(env)) / max(1, len(env) - 1)
    d.line(list(zip(xs2.tolist(), yy(env).tolist())), fill=(120, 200, 240))
    med = np.median(env[env > emax - 60])
    d.line([L2, yy(med), L2 + PW2, yy(med)], fill=(90, 90, 110))
    for k, ts in enumerate(info["top_events_s"]):
        xx = L2 + PW2 * (ts / 0.01) / max(1, len(env) - 1)
        d.line([xx, y0, xx, y0 + ph], fill=(240, 120, 120) if k == 0 else (200, 160, 90))
    d.text((L2 + 6, y0 + 4), "short-term loudness, 50 ms K-weighted (50 dB range); grey = median; "
           "lines = loudest 3 events", fill=(200, 200, 200), font=f12)
    for i, s in enumerate(lines):
        d.text((L, y0 + ph + 22 + 18 * i), s, fill=(220, 220, 220) if "FAIL" not in s else (255, 120, 120), font=f14)
    img.save(path, optimize=True)


# =============================================================================================
# Main
# =============================================================================================

def _job(args):
    name, previews = args
    return build(name, previews)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("names", nargs="*", help="sounds to build (default: all)")
    ap.add_argument("--no-previews", action="store_true")
    ap.add_argument("-j", "--jobs", type=int, default=min(4, os.cpu_count() or 1))
    args = ap.parse_args(argv)
    names = args.names or list(SOUNDS)
    bad = [s for s in names if s not in SOUNDS]
    if bad:
        ap.error("unknown sound(s): %s (known: %s)" % (", ".join(bad), ", ".join(SOUNDS)))
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    report_path = os.path.join(OUT_DIR, "sounds_report.json")
    old = {}
    if os.path.exists(report_path):
        try:
            with open(report_path) as fh:
                old = json.load(fh).get("sounds", {})
        except Exception:
            old = {}
    t0 = time.time()
    jobs = [(nm, not args.no_previews) for nm in names]
    if args.jobs > 1 and len(jobs) > 1:
        with ProcessPoolExecutor(max_workers=args.jobs) as ex:
            infos = list(ex.map(_job, jobs))
    else:
        infos = [_job(j) for j in jobs]
    runtime = time.time() - t0
    print("%-18s %4s %6s %7s %7s %6s %6s %6s %6s  %s" % ("sound", "loop", "sec", "peak", "tpeak", "LUFS",
                                                         "stand", ">8k", "frame", "checks"))
    for info in infos:
        failed = [k for k, v in info["checks"].items() if not v]
        print("%-18s %4s %6.2f %7.2f %7.2f %6.1f %6.1f %6.1f %6.1f  %s" % (
            info["name"], "yes" if info["loop"] else "", info["seconds"], info["peak_dbfs"], info["true_peak_dbfs"],
            info["lufs"], info["standout_db"], info["hf_share_db"], info["hf_frame_max_db"],
            "OK" if not failed else "FAIL: " + ", ".join(failed)))
    sounds = dict(old)
    sounds.update({i["name"]: i for i in infos})
    sounds = {k: sounds[k] for k in SOUNDS if k in sounds}
    failed = [k for k, v in sounds.items() if not v["ok"]]
    report = dict(
        generator="villa/scripts/vsounds.py (DSP toolkit: the_pit/scripts/sounds.py)",
        format="WAV PCM 16-bit mono 44100 Hz, < 10 s, TPDF-dithered",
        levels="loops: integrated loudness on target (-24 LUFS; fire, rain, surf -20), true peak <= -1 dBFS; "
               "one-shots: sample peak -1 dBFS",
        thresholds=dict(lufs_tolerance_lu=LUFS_TOL, hf_split_hz=HF_SPLIT, hf_share_max_db=HF_SHARE_MAX_DB,
                        hf_frame_max_db=HF_FRAME_MAX_DB, hf_tonal_max_db=HF_TONAL_MAX_DB,
                        standout_max_db=STANDOUT_MAX_DB, self_similarity_max=SELF_SIM_MAX),
        runtime_s=round(runtime, 1), built=sorted(names), jobs=args.jobs,
        summary=dict(count=len(sounds), loops=sum(v["loop"] for v in sounds.values()),
                     one_shots=sum(not v["loop"] for v in sounds.values()),
                     total_seconds=round(sum(v["seconds"] for v in sounds.values()), 2),
                     all_ok=not failed, failed=failed),
        sounds=sounds)
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=1)
    print("wrote %d sound(s) to %s in %.1f s%s" % (len(names), OUT_DIR, runtime,
                                                   "" if not failed else "  FAILED: " + ", ".join(failed)))
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())

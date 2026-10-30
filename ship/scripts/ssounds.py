"""The Second Bride's own sound: a cannon shot (sharp crack, chest-deep boom, rolling echo off the
sea). The other ship sounds are taken from The Pit's library (sea, creak, wind, bell, door, chains).

    python3 ship/scripts/ssounds.py  ->  ship/output/sounds/bride_cannon.wav (16-bit mono 44.1 kHz)
"""

import os
import wave

import numpy as np

SR = 44100
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output", "sounds")


def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR)
    y = np.empty_like(x)
    acc = 0.0
    for i, v in enumerate(x):
        acc = (1 - a) * v + a * acc
        y[i] = acc
    return y


def cannon(seconds=4.5, seed=12):
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    t = np.arange(n) / SR
    crack = rng.standard_normal(n) * np.exp(-t / 0.012) * 1.2
    blast = lowpass(rng.standard_normal(n), 900) * np.exp(-t / 0.18) * 3.5
    boom = np.sin(2 * np.pi * (48 - 18 * t) * t) * np.exp(-t / 0.45) * 0.9
    rumble = lowpass(rng.standard_normal(n), 160) * np.exp(-t / 1.4) * 2.2
    x = crack + blast + boom + rumble
    # echoes off the water and a distant shore
    for d, g in ((0.09, 0.35), (0.23, 0.22), (0.61, 0.16), (1.3, 0.1)):
        k = int(d * SR)
        x[k:] += lowpass(x[:-k], 700) * g
    fade = np.ones(n)
    fade[-int(0.4 * SR):] = np.linspace(1, 0, int(0.4 * SR)) ** 2
    x *= fade
    x -= x.mean()
    x *= (10 ** (-1 / 20)) / np.abs(x).max()
    return x


def main():
    os.makedirs(OUT, exist_ok=True)
    x = cannon()
    path = os.path.join(OUT, "bride_cannon.wav")
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes((x * 32767).astype("<i2").tobytes())
    print(path, round(len(x) / SR, 2), "s")


if __name__ == "__main__":
    main()

"""Texturas PBR procedurales del Foso (repetibles, sin costuras).

Genera, sólo con numpy + pillow, un juego PBR por material:

  salida/texturas/<Material>_basecolor.png   sRGB
  salida/texturas/<Material>_normal.png      glTF (OpenGL, +Y arriba)
  salida/texturas/<Material>_orm.png         glTF (R oclusión, G rugosidad, B metalicidad)
  salida/texturas/_muestrario.png            hoja de contacto con las 8 basecolor
  salida/materiales_pbr/<Material>.glb       material glTF 2.0 (con un quad) para el
                                             subidor de materiales PBR de Second Life

Todo el ruido vive sobre un toro: ruido blanco filtrado en frecuencia con FFT,
Voronoi con vecinos envueltos y desplazamientos periódicos. Así cada imagen encaja
borde con borde por construcción (y se comprueba numéricamente al final).
La escala física sigue geo.UV_TILE: una repetición de Piedra son 2 m, de Hierro
0,5 m, etc., y el relieve se calcula en metros reales para que las normales salgan
con la pendiente correcta.

Uso:  python foso_mazmorra/scripts/texturas_pbr.py
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

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AQUI)
from geo import UV_TILE  # noqa: E402  (importa bpy, pero sólo usamos la tabla de escalas)

RAIZ = os.path.dirname(AQUI)
DIR_TEX = os.path.join(RAIZ, "salida", "texturas")
DIR_GLB = os.path.join(RAIZ, "salida", "materiales_pbr")
N = 1024
MATERIALES_PBR = ["Piedra", "Suelo", "Madera", "Hierro", "Tela", "Hueso", "Paja", "Agua"]
SEMILLA = 1666

# ---------------------------------------------------------------------------
# Herramientas de ruido periódico
# ---------------------------------------------------------------------------
_FY = np.fft.fftfreq(N)[:, None] * N     # ciclos por repetición (filas)
_FX = np.fft.rfftfreq(N)[None, :] * N    # ciclos por repetición (columnas)
_C = (np.arange(N) + 0.5) / N
U, V = np.meshgrid(_C, _C)               # U horizontal, V vertical (V=0 arriba de la imagen)


def _s(x, a, b):
    """smoothstep."""
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _mix(a, b, t):
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    t = np.asarray(t, dtype=float)
    if t.ndim == 2 and (a.ndim in (1, 3) or b.ndim in (1, 3)):   # mezcla de colores RGB
        t = t[..., None]
    return a + (b - a) * t


def ruido(rng, f0=1.0, f1=64.0, p=1.0, aniso=1.0, ang=0.0):
    """Ruido fractal periódico (media 0, desviación 1).

    Ruido blanco filtrado en frecuencia con amplitud ~ 1/f^p entre f0 y f1 (ciclos
    por repetición, con caídas suaves): tileable por construcción. `aniso` > 1 lo
    estira a lo largo del ángulo `ang` (radianes, 0 = horizontal, pi/2 = vertical)."""
    c, s = math.cos(ang), math.sin(ang)
    largo = _FX * c + _FY * s
    ancho = -_FX * s + _FY * c
    f = np.sqrt((largo * aniso) ** 2 + ancho ** 2)
    f = np.maximum(f, 1e-6)
    amp = f ** -p * (1.0 - np.exp(-(f / f0) ** 4)) * np.exp(-(f / f1) ** 2)
    amp[0, 0] = 0.0
    out = np.fft.irfft2(np.fft.rfft2(rng.standard_normal((N, N))) * amp, s=(N, N))
    return (out - out.mean()) / (out.std() + 1e-12)


def desenfocar(x, sigma):
    """Desenfoque gaussiano periódico (sigma en píxeles)."""
    if x.ndim == 3:
        return np.stack([desenfocar(x[..., i], sigma) for i in range(x.shape[2])], -1)
    g = np.exp(-2.0 * (math.pi * sigma / N) ** 2 * (_FX ** 2 + _FY ** 2))
    return np.fft.irfft2(np.fft.rfft2(x) * g, s=x.shape)


def voronoi(rng, celdas, u, v, jitter=0.9):
    """Voronoi periódico de celdas x celdas puntos.

    Devuelve (f1, borde, ident): distancia al punto más cercano, distancia exacta al
    borde de la celda (ambas en unidades de celda) e índice de la celda."""
    pts = 0.5 + (rng.random((celdas, celdas, 2)) - 0.5) * jitter
    gu, gv = u * celdas, v * celdas
    iu, iv = np.floor(gu).astype(np.int32), np.floor(gv).astype(np.int32)
    fu, fv = (gu - iu).astype(np.float32), (gv - iv).astype(np.float32)
    f1 = np.full(u.shape, 9.0, np.float32)
    ru = np.zeros(u.shape, np.float32)
    rv = np.zeros(u.shape, np.float32)
    ident = np.zeros(u.shape, np.int32)
    vecinos = []
    for dj in (-1, 0, 1):
        for di in (-1, 0, 1):
            cu, cv = (iu + di) % celdas, (iv + dj) % celdas
            du = di + pts[cv, cu, 0].astype(np.float32) - fu
            dv = dj + pts[cv, cu, 1].astype(np.float32) - fv
            vecinos.append((du, dv))
            d = du * du + dv * dv
            m = d < f1
            f1 = np.where(m, d, f1)
            ru = np.where(m, du, ru)
            rv = np.where(m, dv, rv)
            ident = np.where(m, cv * celdas + cu, ident)
    borde = np.full(u.shape, 9.0, np.float32)
    for du, dv in vecinos:
        eu, ev = du - ru, dv - rv
        l2 = eu * eu + ev * ev
        dist = ((ru + du) * 0.5 * eu + (rv + dv) * 0.5 * ev) / np.sqrt(np.maximum(l2, 1e-10))
        borde = np.where(l2 > 1e-8, np.minimum(borde, dist), borde)
    return np.sqrt(f1), borde, ident


def _envolver(x):
    """Diferencia periódica en [-0.5, 0.5)."""
    return (x + 0.5) % 1.0 - 0.5


def _redondeo(t):
    """Perfil de borde gastado: 0 en la arista, 1 en la cara."""
    t = np.clip(t, 0.0, 1.0)
    return 1.0 - (1.0 - t) ** 2


# ---------------------------------------------------------------------------
# Materiales. Cada uno devuelve color sRGB (0..1), altura en metros, rugosidad,
# metalicidad y la profundidad típica (m) para la oclusión.
# ---------------------------------------------------------------------------
def piedra(rng):
    t = UV_TILE["Piedra"]                         # 2 m por repetición
    u = (U + 0.0035 * ruido(rng, 2, 24, 1.3)) % 1.0
    v = (V + 0.0035 * ruido(rng, 2, 24, 1.3)) % 1.0
    # Sillería irregular: 5 hiladas de ~0,4 m y sillares de 0,5-0,85 m.
    nf = 5
    alt = rng.uniform(0.88, 1.12, nf)
    bordes = np.concatenate([[0.0], np.cumsum(alt / alt.sum())])
    fila = np.clip(np.searchsorted(bordes, v, side="right") - 1, 0, nf - 1)
    dist = np.zeros_like(u)
    ident = np.zeros(u.shape, np.int32)
    for r in range(nf):
        anchos = []
        while sum(anchos) < 0.93:
            anchos.append(rng.uniform(0.25, 0.42))
        anchos = np.array(anchos) / sum(anchos)
        bx = np.concatenate([[0.0], np.cumsum(anchos)])
        m = fila == r
        xs = (u[m] - rng.random()) % 1.0
        k = np.clip(np.searchsorted(bx, xs, side="right") - 1, 0, len(anchos) - 1)
        dx = np.minimum(xs - bx[k], bx[k + 1] - xs)
        dy = np.minimum(v[m] - bordes[r], bordes[r + 1] - v[m])
        dist[m] = dx * dy / np.sqrt(dx * dx + dy * dy + 1e-12)   # esquinas redondeadas
        ident[m] = r * 16 + k
    tabla = rng.random((nf * 16, 4))
    # Distancia a la junta en metros, con aristas mordidas y desconchones.
    dm = dist * t + 0.006 * ruido(rng, 8, 160, 0.8)
    dm -= 0.035 * _s(ruido(rng, 5, 60, 1.0), 1.2, 2.2)
    junta = 0.013 + 0.003 * ruido(rng, 3, 40, 1.0)
    bisel = 0.035 + 0.012 * ruido(rng, 3, 40, 1.0)
    perfil = _redondeo((dm - junta) / np.maximum(bisel, 0.01))
    cara = ((tabla[ident, 0] - 0.5) * 0.008 + 0.004 * ruido(rng, 3, 30, 1.2)
            + 0.0015 * ruido(rng, 30, 400, 0.6))
    poros = _s(ruido(rng, 40, 300, 0.5), 2.0, 2.9)
    h_bloque = -0.022 + perfil * (0.022 + cara) - 0.003 * poros
    h_mortero = -0.024 + 0.002 * ruido(rng, 20, 300, 0.7)
    h = np.maximum(h_bloque, h_mortero)
    es_bloque = _s(dm - junta, -0.002, 0.004)

    # Color de los sillares: grises pardos, algunos más ocres.
    color = _mix((0.40, 0.38, 0.35), (0.29, 0.28, 0.27), tabla[ident, 1])
    color = _mix(color, (0.43, 0.36, 0.28), tabla[ident, 2] ** 2 * 0.7)
    color = color * (1.0 + 0.10 * ruido(rng, 4, 200, 0.9) + 0.05 * ruido(rng, 150, 500, 0.3))[..., None]
    mortero = _mix((0.30, 0.28, 0.24), (0.22, 0.20, 0.17), _s(ruido(rng, 4, 200, 0.9), -1, 1))
    color = _mix(mortero, color, es_bloque)
    color = color * (0.72 + 0.28 * perfil)[..., None]                # mugre en las aristas
    # Humedad: manchas grandes y chorretones verticales.
    hum = _s(ruido(rng, 1, 12, 1.6) + 0.9 * ruido(rng, 3, 60, 1.2, aniso=7, ang=math.pi / 2), 0.2, 1.8)
    color = color * (1.0 - 0.38 * hum)[..., None]
    # Verdín en las juntas y en lo húmedo.
    musgo = _s(0.8 * ruido(rng, 3, 90, 1.0) + 1.2 * hum + 1.4 * (1 - es_bloque) - 0.5, 0.8, 1.9)
    verdin = _mix((0.16, 0.21, 0.10), (0.24, 0.27, 0.13), _s(ruido(rng, 20, 300, 0.6), -1, 1))
    color = _mix(color, verdin, musgo * 0.85)
    # Salitre blanquecino abajo (perfil periódico: máximo en el borde inferior y
    # caída rápida al cruzar al borde superior para no dejar costura).
    tt = (V + 0.5) % 1.0 - 0.5                   # 0 en el borde inferior/superior
    prof = np.where(tt < 0, np.exp(tt / 0.13), np.exp(-tt / 0.025))
    prof = np.maximum(prof - 0.03, 0.0) / 0.97
    sal = _s(0.9 * ruido(rng, 4, 150, 0.9) + 3.0 * prof - 1.6, 0.0, 1.2)
    color = _mix(color, (0.66, 0.65, 0.60), sal * 0.6)
    h = h + 0.0008 * sal * _s(ruido(rng, 60, 400, 0.5), -0.5, 1.0)

    rough = np.where(es_bloque > 0.5, 0.86, 0.93) + 0.05 * ruido(rng, 6, 100, 1.0)
    rough = rough * (1.0 - 0.42 * hum)
    rough = _mix(rough, 0.72, musgo * 0.8)
    rough = _mix(rough, 0.96, sal)
    return color, h, rough, np.zeros_like(h), 0.02


def suelo(rng):
    t = UV_TILE["Suelo"]                          # 2 m
    u = (U + 0.012 * ruido(rng, 2, 30, 1.3)) % 1.0
    v = (V + 0.012 * ruido(rng, 2, 30, 1.3)) % 1.0
    cel = 5
    _, borde, ident = voronoi(rng, cel, u, v, 0.85)
    tabla = rng.random((cel * cel, 3))
    bm = borde * (t / cel) + 0.004 * ruido(rng, 8, 200, 0.8)
    bm -= 0.015 * _s(ruido(rng, 5, 50, 1.0), 1.4, 2.4)
    perfil = _redondeo((bm - 0.008) / 0.03)
    losa = -0.02 + perfil * (0.02 + (tabla[ident, 0] - 0.5) * 0.012
                             + 0.003 * ruido(rng, 3, 40, 1.2) + 0.0008 * ruido(rng, 40, 400, 0.6))
    # Barro: rellena siempre las juntas y cubre losas en las zonas bajas.
    barro_m = _s(ruido(rng, 1.5, 20, 1.5), 0.35, 1.2)
    h_barro = -0.013 + 0.003 * ruido(rng, 6, 120, 1.2) + 0.036 * barro_m
    # Piedrecillas medio enterradas en el barro.
    pc = 48
    pf1, _, pid = voronoi(rng, pc, U, V, 0.8)
    pt = rng.random((pc * pc, 3))
    rad = 0.16 + 0.22 * pt[pid, 0]
    q = np.clip(1.0 - (pf1 / rad) ** 2, 0.0, 1.0)
    canto = np.where(pt[pid, 1] < 0.3, np.sqrt(q) * rad * (t / pc) * 0.5, 0.0)
    h_barro = h_barro + np.where(canto > 0, canto + 0.002, 0.0)
    h = np.maximum(losa, h_barro)
    ve_barro = _s(h_barro - losa, -0.0005, 0.0015)
    ve_canto = ve_barro * _s(canto, 0.0005, 0.0015)

    c_losa = _mix((0.33, 0.31, 0.28), (0.23, 0.22, 0.20), tabla[ident, 1])
    c_losa = c_losa * (1.0 + 0.10 * ruido(rng, 3, 200, 0.9) + 0.05 * ruido(rng, 150, 500, 0.3))[..., None]
    c_losa = c_losa * (0.70 + 0.30 * perfil)[..., None]
    humedo = _s(ruido(rng, 2, 40, 1.2), -0.3, 1.2)
    c_barro = _mix((0.24, 0.19, 0.14), (0.13, 0.10, 0.08), humedo)
    c_canto = _mix((0.38, 0.36, 0.32), (0.20, 0.19, 0.17), pt[pid, 2])
    color = _mix(c_losa, c_barro, ve_barro)
    color = _mix(color, c_canto, ve_canto)
    # Charcos poco profundos sobre el barro.
    charco = barro_m * _s(ruido(rng, 1, 10, 1.6), 1.0, 1.5)
    color = color * (1.0 - 0.3 * charco)[..., None]

    rough = 0.78 + 0.06 * ruido(rng, 4, 80, 1.0)
    rough = _mix(rough, 0.82 - 0.35 * humedo, ve_barro)
    rough = _mix(rough, 0.7, ve_canto)
    rough = _mix(rough, 0.12, charco)
    return color, h, rough, np.zeros_like(h), 0.015


def madera(rng):
    t = UV_TILE["Madera"]                         # 1 m
    nt = 5                                        # tablones de 0,2 m
    py = V * nt
    fila = np.floor(py).astype(np.int32) % nt
    vloc = py - np.floor(py)
    dc = np.full(U.shape, 9.0)
    seg = np.zeros(U.shape, np.int32)
    for r in range(nt):
        cortes = np.sort((rng.random() + np.array([0.0, rng.uniform(0.35, 0.65)])[:rng.integers(1, 3)]) % 1.0)
        m = fila == r
        xs = U[m]
        d = np.min(np.abs(_envolver(xs[:, None] - cortes[None, :])), axis=1)
        dc[m] = d
        seg[m] = np.searchsorted(cortes, xs) % len(cortes)
    ident = fila * 4 + seg
    tabla = rng.random((nt * 4, 4))
    dm = np.minimum(dc * t, np.minimum(vloc, 1 - vloc) * (t / nt))
    dm = dm + 0.0008 * ruido(rng, 10, 200, 0.8)
    perfil = _redondeo((dm - 0.0025) / 0.006)
    # Veta: anillos deformados, distintos en cada tablón.
    yy = vloc * (t / nt) + tabla[ident, 0] * 0.4
    fase = yy * 42.0 + 1.4 * ruido(rng, 1, 16, 1.5, aniso=12) + 0.25 * ruido(rng, 4, 60, 1.0, aniso=8)
    nudo = np.zeros_like(U)
    for _ in range(rng.integers(2, 4)):
        r = rng.integers(0, nt)
        cx, cy = rng.random(), (r + rng.uniform(0.3, 0.7)) / nt
        dk = np.sqrt((_envolver(U - cx) * t / 2.4) ** 2 + (_envolver(V - cy) * t) ** 2)
        en = fila == r
        fase = fase + np.where(en, 3.0 * np.exp(-dk / 0.025), 0.0)
        nudo = np.maximum(nudo, np.where(en, _s(0.013 + 0.003 * tabla[r, 3] - dk, -0.002, 0.003), 0.0))
    anillos = (0.5 + 0.5 * np.sin(2 * math.pi * fase)) ** 3
    fibra = ruido(rng, 4, 400, 0.6, aniso=30)
    grietas = _s(ruido(rng, 3, 220, 0.8, aniso=40), 2.3, 3.0)
    h = -0.006 + perfil * (0.006 + 0.0006 * anillos + 0.0002 * fibra - 0.0012 * ((vloc - 0.5) * 2) ** 2)
    h = h - 0.002 * grietas + 0.0006 * nudo

    color = _mix((0.33, 0.23, 0.15), (0.23, 0.16, 0.10), tabla[ident, 1])
    color = _mix(color, (0.31, 0.29, 0.26), tabla[ident, 2] * 0.55)      # madera vieja agrisada
    color = color * (1.0 - 0.42 * anillos + 0.10 * fibra)[..., None]
    color = _mix(color, (0.12, 0.07, 0.04), nudo * 0.9)
    color = color * (1.0 - 0.6 * grietas)[..., None]
    mugre = _s(ruido(rng, 1.5, 120, 1.1), 0.3, 1.8)
    color = _mix(color, (0.10, 0.08, 0.06), mugre * 0.55)
    color = _mix((0.07, 0.055, 0.04), color * (0.6 + 0.4 * perfil)[..., None], _s(perfil, 0.0, 0.5))  # rendijas con mugre
    rough = 0.78 + 0.07 * ruido(rng, 3, 60, 1.0) + 0.1 * mugre
    rough = _mix(rough, 0.5, _s(ruido(rng, 2, 30, 1.3), 1.2, 1.8))      # manchas de grasa
    return color, h, rough, np.zeros_like(h), 0.003


def hierro(rng):
    t = UV_TILE["Hierro"]                         # 0,5 m
    u = (U + 0.01 * ruido(rng, 2, 20, 1.3)) % 1.0
    v = (V + 0.01 * ruido(rng, 2, 20, 1.3)) % 1.0
    cel = 10                                      # martillazos de ~5 cm
    f1, _, ident = voronoi(rng, cel, u, v, 0.9)
    tabla = rng.random(cel * cel)
    golpe = -(1.0 - f1 ** 2) * 0.0006 * (0.5 + tabla[ident])
    oxido = _s(ruido(rng, 2, 60, 1.3) + 0.5 * ruido(rng, 15, 200, 0.8), 0.35, 1.1)
    picado = _s(ruido(rng, 60, 450, 0.4), 2.2, 3.0) * _s(oxido, 0.1, 0.5)
    costra = ruido(rng, 30, 300, 0.7)
    h = (golpe + 0.0012 * ruido(rng, 1, 8, 1.5) + 0.00012 * ruido(rng, 30, 400, 0.7)
         + oxido * (0.0004 + 0.00015 * costra) - 0.0004 * picado)
    chorro = _s(ruido(rng, 2, 80, 1.2, aniso=10, ang=math.pi / 2), 0.8, 2.0)

    metal_c = (0.30, 0.30, 0.31)
    color = _mix(metal_c, (0.19, 0.19, 0.20), _s(ruido(rng, 2, 40, 1.2), -1, 1))
    color = color * (1.0 + 0.06 * ruido(rng, 40, 400, 0.6))[..., None]
    c_oxido = _mix((0.40, 0.19, 0.08), (0.22, 0.11, 0.06), _s(costra, -1.0, 1.0))
    c_oxido = _mix(c_oxido, (0.55, 0.30, 0.12), _s(ruido(rng, 8, 120, 1.0), 1.0, 2.0) * 0.7)
    color = _mix(color, (0.33, 0.19, 0.10), chorro * 0.5)
    color = _mix(color, c_oxido, oxido)
    color = color * (1.0 - 0.5 * picado)[..., None]
    metal = np.clip(0.9 * (1.0 - oxido) * (1.0 - 0.4 * chorro), 0.0, 1.0)
    rough = 0.52 + 0.08 * ruido(rng, 3, 60, 1.0)
    rough = _mix(rough, 0.68, chorro * 0.6)
    rough = _mix(rough, 0.9, oxido)
    return color, h, rough, metal, 0.0008


def tela(rng):
    t = UV_TILE["Tela"]                           # 0,6 m; 100 hilos = 6 mm por hilo
    hilos = 100
    gx = (U + 0.0012 * ruido(rng, 2, 40, 1.2)) * hilos
    gy = (V + 0.0012 * ruido(rng, 2, 40, 1.2)) * hilos
    i = np.floor(gx).astype(np.int32) % hilos
    j = np.floor(gy).astype(np.int32) % hilos
    fx, fy = gx - np.floor(gx), gy - np.floor(gy)
    arriba = ((i + j) % 2) == 0
    gi, gj = rng.random(hilos), rng.random(hilos)
    ancho_u = np.clip((0.72 + 0.35 * gi[i]) * (0.9 + 0.12 * ruido(rng, 2, 60, 1.0, aniso=8, ang=math.pi / 2)), 0.45, 1.0)
    ancho_v = np.clip((0.72 + 0.35 * gj[j]) * (0.9 + 0.12 * ruido(rng, 2, 60, 1.0, aniso=8)), 0.45, 1.0)
    cu = np.sqrt(np.clip(1.0 - ((fx - 0.5) * 2 / ancho_u) ** 2, 0.0, 1.0))
    cv = np.sqrt(np.clip(1.0 - ((fy - 0.5) * 2 / ancho_v) ** 2, 0.0, 1.0))
    ou, ov = np.sin(math.pi * fy), np.sin(math.pi * fx)
    h_urd = cu * (0.55 + 0.45 * np.where(arriba, ou, -ou))      # urdimbre (vertical)
    h_tra = cv * (0.55 + 0.45 * np.where(arriba, -ov, ov))      # trama (horizontal)
    urd = h_urd >= h_tra
    hh = np.maximum(h_urd, h_tra)
    fib = np.where(urd, ruido(rng, 20, 500, 0.5, aniso=10, ang=math.pi / 2), ruido(rng, 20, 500, 0.5, aniso=10))
    h = hh * 0.0012 + 0.00008 * fib

    color = np.broadcast_to(np.array([0.55, 0.50, 0.41]), U.shape + (3,))
    tono = np.where(urd, gi[i], gj[j])
    color = color * (0.92 + 0.12 * tono + 0.06 * fib)[..., None]
    sucio = _s(ruido(rng, 1, 20, 1.5), -0.3, 1.3)
    color = _mix(color, (0.33, 0.29, 0.22), sucio * 0.7)
    nm = ruido(rng, 2, 40, 1.4)
    mancha = _s(nm, 1.0, 1.25)
    cerco = _s(nm, 0.9, 1.02) * (1.0 - _s(nm, 1.05, 1.25))
    color = _mix(color, (0.32, 0.21, 0.12), mancha * 0.6)
    color = color * (1.0 - 0.25 * cerco)[..., None]
    color = color * (0.55 + 0.45 * hh)[..., None]
    rough = 0.92 + 0.03 * ruido(rng, 3, 60, 1.0) - 0.08 * mancha
    return color, h, rough, np.zeros_like(h), 0.0008


def hueso(rng):
    t = UV_TILE["Hueso"]                          # 0,3 m
    u = (U + 0.012 * ruido(rng, 2, 30, 1.2)) % 1.0
    v = (V + 0.012 * ruido(rng, 2, 30, 1.2)) % 1.0
    cel = 5
    _, borde, _ = voronoi(rng, cel, u, v, 0.9)
    bm = borde * (t / cel)
    anchura = np.clip(0.00035 * (1.0 + 0.8 * ruido(rng, 4, 80, 1.0)), 0.00008, None)
    activa = _s(ruido(rng, 1, 12, 1.5), -0.8, 0.0)
    grieta = (1.0 - _s(bm, 0.0, anchura)) * activa
    _, borde2, _ = voronoi(rng, 14, (u + 0.3) % 1.0, v, 0.9)
    micro = (1.0 - _s(borde2 * (t / 14), 0.0, 0.00015)) * _s(ruido(rng, 3, 40, 1.2), 0.3, 1.0)
    poros = _s(ruido(rng, 80, 500, 0.3), 2.0, 2.9)
    lamelas = ruido(rng, 4, 200, 0.9, aniso=6, ang=0.4)
    h = (0.0012 * ruido(rng, 1, 10, 1.6) + 0.00012 * lamelas
         - 0.0012 * grieta - 0.0004 * micro - 0.0004 * poros)

    color = _mix((0.71, 0.63, 0.48), (0.58, 0.49, 0.34), _s(ruido(rng, 2, 60, 1.2), -1.2, 1.2))
    color = color * (1.0 + 0.04 * lamelas)[..., None]
    amarillo = _s(ruido(rng, 1, 12, 1.5), -0.2, 1.4)
    color = _mix(color, (0.50, 0.38, 0.22), amarillo * 0.6)
    oscuro = np.clip(grieta + 0.6 * micro + poros, 0, 1)
    color = _mix(color, (0.22, 0.16, 0.10), oscuro * 0.85)
    mugre = _s(ruido(rng, 2, 120, 1.0), 0.6, 2.0)
    color = _mix(color, (0.30, 0.24, 0.16), mugre * 0.45)
    rough = 0.62 + 0.06 * ruido(rng, 3, 60, 1.0) + 0.25 * oscuro + 0.1 * mugre
    return color, h, rough, np.zeros_like(h), 0.0008


def paja(rng):
    t = UV_TILE["Paja"]                           # 1 m; ~1 mm por píxel
    zb, ib = Image.new("F", (N, N), 0.0), Image.new("I", (N, N), 0)
    dz, di = ImageDraw.Draw(zb), ImageDraw.Draw(ib)
    nh = 2600
    for k in range(nh):
        largo = rng.uniform(70, 300)
        ancho = rng.uniform(2.0, 5.0)
        ang = rng.normal(0.35, 0.55) if rng.random() < 0.7 else rng.uniform(0, math.pi)
        x, y = rng.random(2) * N
        curva = rng.normal(0, 0.12)
        pts = [(x, y)]
        for _ in range(4):
            ang += curva
            x += math.cos(ang) * largo / 4
            y += math.sin(ang) * largo / 4
            pts.append((x, y))
        z = 0.002 + 0.02 * k / nh
        xs, ys = [p[0] for p in pts], [p[1] for p in pts]
        for ox in (-N, 0, N):
            for oy in (-N, 0, N):
                if max(xs) + ox < -6 or min(xs) + ox > N + 6 or max(ys) + oy < -6 or min(ys) + oy > N + 6:
                    continue
                q = [(px + ox, py + oy) for px, py in pts]
                w = max(1, int(round(ancho)))
                dz.line(q, fill=z, width=w, joint="curve")
                dz.line(q, fill=z + 0.0012, width=max(1, int(round(ancho * 0.45))), joint="curve")
                di.line(q, fill=k + 1, width=w, joint="curve")
    h = desenfocar(np.array(zb, dtype=float), 0.7)
    ids = np.array(ib)
    tabla = rng.random((nh + 1, 4))
    color = _mix((0.62, 0.52, 0.30), (0.71, 0.64, 0.46), tabla[ids, 0])
    color = _mix(color, (0.45, 0.40, 0.31), tabla[ids, 1] * 0.7)
    color = _mix(color, (0.28, 0.22, 0.14), (tabla[ids, 2] < 0.15) * 0.8)      # hebras podridas
    color = color * (1.0 + 0.10 * ruido(rng, 60, 500, 0.4))[..., None]
    capa = np.clip((h - 0.002) / 0.02, 0, 1)
    color = color * (0.55 + 0.45 * capa)[..., None]
    color = np.where((ids == 0)[..., None], np.array([0.12, 0.10, 0.07]), color)
    mugre = _s(ruido(rng, 1.5, 25, 1.4), 0.3, 1.6)
    color = _mix(color, (0.24, 0.19, 0.12), mugre * 0.5)
    rough = np.where(ids == 0, 0.95, 0.68 + 0.12 * tabla[ids, 3]) + 0.12 * mugre
    return color, h, rough, np.zeros_like(h), 0.006


def agua(rng):
    t = UV_TILE["Agua"]                           # 3 m
    h = (0.02 * ruido(rng, 1.5, 10, 2.0, aniso=1.8, ang=0.3)
         + 0.004 * ruido(rng, 8, 40, 1.5, aniso=1.4, ang=-0.4)
         + 0.0005 * ruido(rng, 30, 120, 1.0))
    color = _mix((0.030, 0.065, 0.058), (0.050, 0.095, 0.072), _s(ruido(rng, 1, 6, 1.5), -1, 1))
    nata = _s(ruido(rng, 2, 40, 1.3), 1.4, 2.2)                       # espuma sucia
    color = _mix(color, (0.13, 0.14, 0.11), nata * 0.5)
    rough = 0.05 + 0.03 * _s(ruido(rng, 2, 20, 1.2), 0.5, 2.0) + 0.25 * nata
    return color, h, rough, np.zeros_like(h), None


GENERADORES = {"Piedra": piedra, "Suelo": suelo, "Madera": madera, "Hierro": hierro,
               "Tela": tela, "Hueso": hueso, "Paja": paja, "Agua": agua}


# ---------------------------------------------------------------------------
# Mapas derivados
# ---------------------------------------------------------------------------
def normal_de_altura(h, metros_px):
    """Normal tangente glTF (OpenGL, +Y arriba) a partir de una altura en metros."""
    h = desenfocar(h, 0.6)
    gx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) / (2 * metros_px)
    gy = (np.roll(h, -1, 0) - np.roll(h, 1, 0)) / (2 * metros_px)   # hacia abajo en la imagen
    n = np.stack([-gx, gy, np.ones_like(h)], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


def oclusion(h, prof):
    if prof is None:
        return np.ones_like(h)
    cav = 0.5 * (desenfocar(h, 4) + desenfocar(h, 18)) - h
    return 1.0 - 0.7 * np.clip(cav / prof, 0.0, 1.0)


def _u8(x):
    return (np.clip(x, 0.0, 1.0) * 255.0 + 0.5).astype(np.uint8)


def costura(img):
    """Razón entre el salto borde-borde y el salto entre píxeles vecinos junto a ese mismo
    borde (~1 = sin costura; una costura real da varias veces más). Se compara con los
    vecinos locales porque una junta o un hilo pueden caer justo en el borde."""
    a = img.astype(float)
    sh = np.abs(a[:, 0] - a[:, -1]).mean()
    sv = np.abs(a[0] - a[-1]).mean()
    dh = 0.5 * (np.abs(a[:, 1] - a[:, 0]).mean() + np.abs(a[:, -1] - a[:, -2]).mean())
    dv = 0.5 * (np.abs(a[1] - a[0]).mean() + np.abs(a[-1] - a[-2]).mean())
    return max(sh / max(dh, 1e-6), sv / max(dv, 1e-6))


def generar(nombre, rng):
    color, h, rough, metal, prof = GENERADORES[nombre](rng)
    ao = oclusion(h, prof)
    color = np.clip(color, 0, 1) * (1.0 - 0.3 * (1.0 - ao))[..., None]      # mugre en lo hundido
    n = normal_de_altura(h, UV_TILE[nombre] / N)
    mapas = {
        "basecolor": _u8(color),
        "normal": _u8(n * 0.5 + 0.5),
        "orm": _u8(np.stack([ao, np.clip(rough, 0.02, 1.0), np.clip(metal, 0, 1)], -1)),
    }
    return mapas


# ---------------------------------------------------------------------------
# glTF binario: un material metallicRoughness y un quad que lo usa
# ---------------------------------------------------------------------------
def escribir_glb(ruta, nombre, pngs, lado):
    s = lado / 2.0
    pos = np.array([[-s, -s, 0], [s, -s, 0], [s, s, 0], [-s, s, 0]], np.float32)
    nor = np.tile(np.array([0, 0, 1], np.float32), (4, 1))
    uv = np.array([[0, 1], [1, 1], [1, 0], [0, 0]], np.float32)       # glTF: v=0 arriba
    idx = np.array([0, 1, 2, 0, 2, 3], np.uint16)
    binario = bytearray()
    vistas = []

    def agregar(datos, objetivo=None):
        while len(binario) % 4:
            binario.append(0)
        vista = {"buffer": 0, "byteOffset": len(binario), "byteLength": len(datos)}
        if objetivo:
            vista["target"] = objetivo
        binario.extend(datos)
        vistas.append(vista)
        return len(vistas) - 1

    accesores = [
        {"bufferView": agregar(pos.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC3",
         "min": pos.min(0).tolist(), "max": pos.max(0).tolist()},
        {"bufferView": agregar(nor.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC3"},
        {"bufferView": agregar(uv.tobytes(), 34962), "componentType": 5126, "count": 4, "type": "VEC2"},
        {"bufferView": agregar(idx.tobytes(), 34963), "componentType": 5123, "count": 6, "type": "SCALAR"},
    ]
    tipos = ["basecolor", "normal", "orm"]
    imagenes = [{"name": f"{nombre}_{k}", "mimeType": "image/png", "bufferView": agregar(pngs[k])} for k in tipos]
    while len(binario) % 4:
        binario.append(0)
    doc = {
        "asset": {"version": "2.0", "generator": "El Foso de la Leva - texturas_pbr.py"},
        "scene": 0,
        "scenes": [{"name": nombre, "nodes": [0]}],
        "nodes": [{"name": nombre, "mesh": 0}],
        "meshes": [{"name": nombre, "primitives": [{"attributes": {"POSITION": 0, "NORMAL": 1, "TEXCOORD_0": 2},
                                                     "indices": 3, "material": 0, "mode": 4}]}],
        "materials": [{
            "name": nombre,
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
        "images": imagenes,
        "accessors": accesores,
        "bufferViews": vistas,
        "buffers": [{"byteLength": len(binario)}],
    }
    js = json.dumps(doc, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    js += b" " * (-len(js) % 4)
    total = 12 + 8 + len(js) + 8 + len(binario)
    with open(ruta, "wb") as f:
        f.write(struct.pack("<III", 0x46546C67, 2, total))
        f.write(struct.pack("<II", len(js), 0x4E4F534A) + js)
        f.write(struct.pack("<II", len(binario), 0x004E4942) + bytes(binario))


def validar_glb(ruta):
    """Comprueba cabecera, trozos, referencias del JSON e imágenes embebidas. Devuelve errores."""
    err = []
    datos = open(ruta, "rb").read()
    magia, version, total = struct.unpack_from("<III", datos, 0)
    if magia != 0x46546C67 or version != 2 or total != len(datos):
        return [f"cabecera incorrecta ({magia:#x}, v{version}, {total} != {len(datos)})"]
    lj, tj = struct.unpack_from("<II", datos, 12)
    if tj != 0x4E4F534A or lj % 4:
        return ["el primer trozo no es JSON alineado"]
    doc = json.loads(datos[20:20 + lj])
    lb, tb = struct.unpack_from("<II", datos, 20 + lj)
    binario = datos[28 + lj:28 + lj + lb]
    if tb != 0x004E4942 or len(binario) != lb or doc["buffers"][0]["byteLength"] > lb:
        err.append("trozo BIN incoherente")
    if doc["asset"]["version"] != "2.0" or len(doc["materials"]) != 1:
        err.append("asset/materials incorrectos")
    m = doc["materials"][0]
    refs = [m["pbrMetallicRoughness"]["baseColorTexture"]["index"], m["normalTexture"]["index"],
            m["occlusionTexture"]["index"], m["pbrMetallicRoughness"]["metallicRoughnessTexture"]["index"]]
    for r in refs:
        if not 0 <= r < len(doc["textures"]):
            err.append(f"textura {r} fuera de rango")
    for tx in doc["textures"]:
        if not 0 <= tx["source"] < len(doc["images"]) or not 0 <= tx["sampler"] < len(doc["samplers"]):
            err.append("textura con imagen/sampler fuera de rango")
    for bv in doc["bufferViews"]:
        if bv["byteOffset"] + bv["byteLength"] > lb:
            err.append("bufferView fuera del buffer")
    for im in doc["images"]:
        bv = doc["bufferViews"][im["bufferView"]]
        png = binario[bv["byteOffset"]:bv["byteOffset"] + bv["byteLength"]]
        if not png.startswith(b"\x89PNG") or Image.open(io.BytesIO(png)).size != (N, N):
            err.append(f"imagen {im['name']} no es un PNG {N}x{N}")
    prim = doc["meshes"][0]["primitives"][0]
    if prim["material"] != 0 or max(prim["attributes"].values()) >= len(doc["accessors"]):
        err.append("primitiva incoherente")
    return err


def muestrario(ruta, colores):
    lado, rot, cols = 300, 34, 4
    filas = math.ceil(len(colores) / cols)
    hoja = Image.new("RGB", (cols * lado + (cols + 1) * 12, filas * (lado + rot) + (filas + 1) * 12), (18, 16, 14))
    try:
        fuente = ImageFont.truetype("DejaVuSans-Bold.ttf", 20)
    except OSError:
        fuente = ImageFont.load_default()
    d = ImageDraw.Draw(hoja)
    for k, (nombre, img) in enumerate(colores):
        x = 12 + (k % cols) * (lado + 12)
        y = 12 + (k // cols) * (lado + rot + 12)
        hoja.paste(Image.fromarray(img).resize((lado, lado), Image.LANCZOS), (x, y))
        d.text((x + 4, y + lado + 6), f"{nombre}  ({UV_TILE[nombre]:g} m)", fill=(225, 215, 195), font=fuente)
    hoja.save(ruta)


def main():
    t0 = time.time()
    os.makedirs(DIR_TEX, exist_ok=True)
    os.makedirs(DIR_GLB, exist_ok=True)
    colores = []
    fallos = []
    for k, nombre in enumerate(MATERIALES_PBR):
        t1 = time.time()
        mapas = generar(nombre, np.random.default_rng(SEMILLA + k))
        pngs = {}
        for tipo, img in mapas.items():
            buf = io.BytesIO()
            Image.fromarray(img).save(buf, "PNG", optimize=False)
            pngs[tipo] = buf.getvalue()
            with open(os.path.join(DIR_TEX, f"{nombre}_{tipo}.png"), "wb") as f:
                f.write(pngs[tipo])
        ruta_glb = os.path.join(DIR_GLB, f"{nombre}.glb")
        escribir_glb(ruta_glb, nombre, pngs, UV_TILE[nombre])
        errores = validar_glb(ruta_glb)
        cost = {tipo: costura(img) for tipo, img in mapas.items()}
        peor = max(cost.values())
        if errores or peor > 1.5:
            fallos.append((nombre, errores, cost))
        colores.append((nombre, mapas["basecolor"]))
        print(f"  {nombre:7s} {time.time() - t1:5.1f} s  costura máx {peor:4.2f}  "
              f"glb {os.path.getsize(ruta_glb) / 1e6:4.1f} MB  {'OK' if not errores else errores}")
    muestrario(os.path.join(DIR_TEX, "_muestrario.png"), colores)
    print(f"Texturas en {DIR_TEX}\nMateriales glTF en {DIR_GLB}\nTotal {time.time() - t0:.1f} s")
    if fallos:
        print("FALLOS:", fallos)
        sys.exit(1)


if __name__ == "__main__":
    main()

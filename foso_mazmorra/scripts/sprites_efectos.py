"""El Foso V3 - texturas de efectos (fuego, humo, niebla, chispas, gotas, proyector).

Genera en salida/efectos/ imágenes RGBA con alfa limpio: el color de los
píxeles transparentes NO es negro sino el mismo tono del efecto, así que al
filtrar o hacer mipmaps en SL no aparece el halo oscuro alrededor.

  fuego_flipbook.png   1024x1024, 4x4 fotogramas (bucle perfecto 16 -> 1)
  llama_particula.png  256x256, lengua de fuego para partículas
  humo.png             256x256, bocanada de humo gris
  niebla.png           256x256, jirón de niebla muy suave
  chispa.png           64x64, ascua brillante
  gota.png             64x128, gota con estela
  proyector_fuego.png  512x512, "cookie" de luz proyectora (llama tras la reja)

Todo el ruido es periódico (filtrado en frecuencia), por eso el fuego del
flipbook puede subir una vuelta completa y el fotograma 16 enlaza con el 1.

Uso:  python scripts/sprites_efectos.py
"""
import os

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "..", "salida", "efectos")
FOTOGRAMAS = 16          # 4x4
CELDA = 256


# ------------------------------------------------------------------ utilidades
def ruido(h, w, freq, rng):
    """Ruido suave periódico en ambos ejes (paso bajo gaussiano de ruido blanco)."""
    f = np.fft.fft2(rng.standard_normal((h, w)))
    fy = np.fft.fftfreq(h)[:, None] * h
    fx = np.fft.fftfreq(w)[None, :] * w
    r = np.real(np.fft.ifft2(f * np.exp(-(fx ** 2 + fy ** 2) / (2.0 * freq ** 2))))
    return (r - r.mean()) / (r.std() + 1e-9)


def fbm(h, w, base, octavas, rng, ganancia=0.5):
    """Suma de octavas de ruido periódico normalizada a 0..1."""
    acc = np.zeros((h, w))
    amp = 1.0
    for o in range(octavas):
        acc += amp * ruido(h, w, base * 2 ** o, rng)
        amp *= ganancia
    acc = (acc - acc.min()) / (acc.max() - acc.min())
    return acc


def turbulento(h, w, base, octavas, rng):
    """Ruido turbulento (|ruido|): crestas finas como lenguas de fuego."""
    acc = np.zeros((h, w))
    amp = 1.0
    for o in range(octavas):
        acc += amp * np.abs(ruido(h, w, base * 2 ** o, rng))
        amp *= 0.55
    return acc / acc.max()


def suave(a, b, x):
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def rampa(i, paradas):
    """Interpola colores RGB según paradas [(pos, (r, g, b)), ...]."""
    pos = np.array([p for p, _ in paradas])
    cols = np.array([c for _, c in paradas])
    return np.stack([np.interp(i, pos, cols[:, k]) for k in range(3)], -1)


RAMPA_FUEGO = [(0.0, (0.30, 0.03, 0.00)), (0.22, (0.70, 0.10, 0.01)), (0.45, (1.0, 0.36, 0.04)),
               (0.68, (1.0, 0.66, 0.18)), (0.86, (1.0, 0.90, 0.55)), (1.0, (1.0, 0.98, 0.88))]


def guardar(rgb, alfa, nombre):
    img = np.concatenate([np.clip(rgb, 0, 1), np.clip(alfa, 0, 1)[..., None]], -1)
    Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA").save(os.path.join(OUT, nombre))


# ------------------------------------------------------------------ fuego
def campo_llama(n1, n2, n3, ancho=0.62):
    """Intensidad 0..1 de una llama de CELDA x CELDA a partir de tres capas de ruido."""
    rows, cols = np.mgrid[0:CELDA, 0:CELDA].astype(float)
    x = (cols - (CELDA - 1) / 2) / (CELDA / 2)
    y = np.clip(((CELDA - 1 - rows) / CELDA - 0.05) / 0.88, 0.0, 1.2)   # 0 base, 1 punta
    # balanceo lateral que crece con la altura
    x = x + (n1 - 0.5) * 0.55 * y ** 1.3 + (n3 - 0.5) * 0.12 * y
    radio = ancho * np.clip(y / 0.16, 0.0, 1.0) ** 0.5 * np.clip(1.0 - y, 0.0, 1.0) ** 0.6 + 1e-4
    forma = np.clip(1.0 - (x / radio) ** 2, 0.0, 1.0)
    # núcleo brillante abajo; la turbulencia "come" la llama desde arriba y
    # deja lenguas sueltas que se separan y suben
    nucleo = forma ** 1.4 * np.clip(1.0 - 1.6 * y, 0.0, 1.0)
    i = 0.55 * forma ** 0.7 + 0.5 * nucleo - (0.95 * n2 + 0.45 * n1 - 0.38) * y ** 0.85 * 1.1 - 0.12 * y
    i = np.clip(np.minimum(i, 1.6 * np.sqrt(forma)), 0.0, 1.0)   # nada fuera de la silueta
    # bordes de la celda siempre limpios (sin sangrado entre fotogramas)
    marco = suave(0, 10, cols) * suave(0, 10, CELDA - 1 - cols) * suave(0, 6, rows) * suave(0, 6, CELDA - 1 - rows)
    return i * marco


def color_llama(i):
    rgb = rampa(np.clip(i, 0, 1), RAMPA_FUEGO)
    alfa = suave(0.02, 0.32, i)
    return rgb, alfa


def fuego_flipbook(rng):
    periodo = 2 * CELDA                     # el ruido sube una vuelta entera en 16 fotogramas
    a = fbm(periodo, CELDA, 2.0, 4, rng)
    b = turbulento(periodo, CELDA, 4.0, 4, rng)
    c = fbm(periodo, CELDA, 6.0, 3, rng)
    filas = np.arange(CELDA)[:, None]
    hoja_rgb = np.zeros((4 * CELDA, 4 * CELDA, 3))
    hoja_a = np.zeros((4 * CELDA, 4 * CELDA))

    def fotograma(k):
        d1 = (filas + k * periodo // FOTOGRAMAS) % periodo        # capa lenta: 1 vuelta
        d2 = (filas + 2 * k * periodo // FOTOGRAMAS) % periodo    # capa rápida: 2 vueltas
        d3 = (filas + 3 * k * periodo // FOTOGRAMAS) % periodo
        cols = np.arange(CELDA)[None, :]
        return campo_llama(a[d1, cols], b[d2, cols], c[d3, cols])

    for k in range(FOTOGRAMAS):
        rgb, al = color_llama(fotograma(k))
        r, q = divmod(k, 4)
        hoja_rgb[r * CELDA:(r + 1) * CELDA, q * CELDA:(q + 1) * CELDA] = rgb
        hoja_a[r * CELDA:(r + 1) * CELDA, q * CELDA:(q + 1) * CELDA] = al
    # comprobación del bucle: el "fotograma 17" es idéntico al 1
    assert np.allclose(fotograma(FOTOGRAMAS), fotograma(0))
    guardar(hoja_rgb, hoja_a, "fuego_flipbook.png")


def llama_particula(rng):
    a = fbm(CELDA, CELDA, 1.5, 3, rng)
    b = fbm(CELDA, CELDA, 3.0, 3, rng)
    i = campo_llama(0.5 + (a - 0.5) * 0.5, b * 0.6, a, ancho=0.7)
    rgb, al = color_llama(i)
    guardar(rgb, al * 0.95, "llama_particula.png")


# ------------------------------------------------------------------ humo, niebla, chispa, gota
def humo(rng, n=256):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    nub = fbm(n, n, 2.5, 5, rng)
    bocanada = np.zeros((n, n))
    for _ in range(7):                       # varias bolas que forman la bocanada
        cx, cy, s = rng.uniform(-0.35, 0.35), rng.uniform(-0.3, 0.3), rng.uniform(0.14, 0.24)
        bocanada = np.maximum(bocanada, np.exp(-((cols - cx) ** 2 + (rows - cy) ** 2) / (2 * s * s)))
    al = bocanada * (0.3 + 1.0 * nub) * suave(1.0, 0.75, r)
    al = suave(0.12, 0.85, al) * 0.85
    gris = 0.42 + 0.22 * nub
    rgb = np.stack([gris, gris * 0.98, gris * 0.95], -1)
    guardar(rgb, al, "humo.png")


def niebla(rng, n=256):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    nub = fbm(n, n, 1.5, 5, rng)
    jiron = np.exp(-(cols ** 2) / 0.35 - (rows / 0.55) ** 2 / 0.6)         # alargado en horizontal
    al = jiron * (0.25 + nub) * suave(1.0, 0.55, np.sqrt(cols ** 2 + rows ** 2))
    al = np.clip(al, 0, 1) * 0.55
    rgb = np.stack([0.78 + 0.12 * nub, 0.82 + 0.1 * nub, 0.84 + 0.1 * nub], -1)
    guardar(rgb, al, "niebla.png")


def chispa(n=64):
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    nucleo = np.exp(-(r / 0.12) ** 2)
    halo = np.exp(-(r / 0.38) ** 2)
    i = np.clip(nucleo + 0.55 * halo, 0, 1)
    rgb = rampa(i, [(0.0, (0.9, 0.25, 0.02)), (0.5, (1.0, 0.6, 0.15)), (1.0, (1.0, 0.97, 0.85))])
    al = np.clip(1.2 * nucleo + 0.7 * halo, 0, 1) * suave(1.0, 0.8, r)
    guardar(rgb, al, "chispa.png")


def gota(w=64, h=128):
    rows, cols = np.mgrid[0:h, 0:w].astype(float)
    x = (cols - (w - 1) / 2) / (w / 2)
    y = rows / (h - 1)                                     # 0 arriba, 1 abajo
    cabeza = np.exp(-((x / 0.32) ** 2 + ((y - 0.80) / 0.11) ** 2))
    estela = np.exp(-(x / (0.07 + 0.12 * y)) ** 2) * suave(0.05, 0.75, y) * 0.5
    al = np.clip(cabeza + estela, 0, 1) * suave(0.0, 0.05, 1 - y)
    brillo = np.exp(-(((x + 0.1) / 0.1) ** 2 + ((y - 0.77) / 0.035) ** 2))
    rgb = np.stack([0.62 + 0.38 * brillo, 0.72 + 0.28 * brillo, 0.78 + 0.22 * brillo], -1)
    guardar(rgb, al * 0.85, "gota.png")


# ------------------------------------------------------------------ proyector
def proyector_fuego(rng, n=512):
    """Luz cálida irregular vista a través de la jaula de un farol (barrotes y fleje)."""
    rows, cols = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.sqrt(cols ** 2 + rows ** 2)
    manchas = fbm(n, n, 3.0, 5, rng)
    luz = np.exp(-(r / 0.62) ** 2) * (0.55 + 0.7 * manchas)
    # barrotes verticales algo curvados (la jaula es redonda) y difusos
    xb = cols + 0.05 * rows ** 2 * np.sign(cols)
    barrotes = 1.0 - 0.85 * np.clip(np.cos(xb * np.pi * 3.0) * 1.6 - 0.75, 0, 1)
    flejes = 1.0 - 0.8 * np.exp(-((rows + 0.38) / 0.05) ** 2) - 0.6 * np.exp(-((rows - 0.47) / 0.07) ** 2)
    cadena = 1.0 - 0.55 * np.exp(-((cols - 0.25 * rows - 0.55) / 0.04) ** 2) * (np.sin(rows * 40) > -0.2)
    i = luz * barrotes * flejes * cadena
    i = i / i.max() * suave(1.0, 0.82, r)                  # borde negro: sin estiramiento del cookie
    rgb = rampa(np.clip(i, 0, 1), [(0.0, (0.0, 0.0, 0.0)), (0.35, (0.55, 0.16, 0.03)),
                                   (0.7, (1.0, 0.55, 0.18)), (1.0, (1.0, 0.86, 0.6))])
    Image.fromarray((np.clip(rgb, 0, 1) * 255 + 0.5).astype(np.uint8), "RGB").save(
        os.path.join(OUT, "proyector_fuego.png"))


def main():
    os.makedirs(OUT, exist_ok=True)
    rng = np.random.default_rng(1666)
    fuego_flipbook(rng)
    llama_particula(rng)
    humo(rng)
    niebla(rng)
    chispa()
    gota()
    proyector_fuego(rng)
    for fn in sorted(os.listdir(OUT)):
        im = Image.open(os.path.join(OUT, fn))
        print(f"  {fn:22s} {im.size[0]}x{im.size[1]} {im.mode}")


if __name__ == "__main__":
    main()

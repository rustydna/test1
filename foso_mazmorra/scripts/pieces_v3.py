"""EL FOSO V3 — la mazmorra de la Leva.

Fortaleza-prisión de un señor pirata: aquí se doblega a los cautivos y se recluta
tripulación. Un patio-foso con un canal de agua de mar (con marea) bajo la niebla,
siete salas de castigo, una única perrera de estancia y, al fondo, el trono desde el
que el señor ve todas las rejas.

Regla de diseño (la lección de la V2): **ninguna pieza tiene un casco convexo que tape
un paso**. Aunque Second Life deje todas las mallas en «Convex Hull» y nadie ejecute
ningún script, se puede entrar en todas las salas. Por eso cada frente se divide en
machones, cabezas de arco y hojas; los muros, suelos y bóvedas van por separado.

Caras SL fijas en todas las piezas (ver geo.FACE_MATS):
  0 Piedra · 1 Suelo · 2 Madera · 3 Hierro · 4 Tela/cuero · 5 Hueso · 6 Paja · 7 Llama
"""

import math

from mathutils import Matrix, Vector

import pieces as P
from geo import Frame, Geo, arch_height, pointed_arch, rng
from pieces import (ARCH_RATIO, ARCH_SPAN, ARCH_SPRING, BIG, DOOR_H, DOOR_HW, FL, FT, GRILLE_D, NX, PT, R_VAULT,
                    SMALL, STD, T_VAULT, VS, WT, XB, XI, XO, YP, ZB, _fx, arch_wall, bar, bbox_phys, brazier, bx,
                    chain, chain_path, collar, cross_slit_skin, flagstones, flipx, gate_leaf, hood, lantern, pbox,
                    resample, torch, tower, voussoirs, wall_anchor)

V = Vector
PIECES = P.PIECES
HW = ARCH_SPAN / 2
CROWN = ARCH_SPRING + arch_height(0, ARCH_SPAN, ARCH_RATIO)
DAIS = FL + 0.9

# Salas: (lado, índice) -> (etiqueta, nombre de rol)
ROOMS = {(-1, 0): ("C01", "La Leva"), (-1, 1): ("C02", "El Potro"), (-1, 2): ("C03", "El Cepo"),
         (-1, 3): ("C04", "La Cisterna"), (1, 0): ("C05", "La Perrera"), (1, 1): ("C06", "La Perrera"),
         (1, 2): ("C07", "Las Jaulas"), (1, 3): ("C08", "El Mástil")}


# Asientos: nombre -> (punto del avatar en el mundo, giro en grados, animación, animación de reserva)
SITS = {}


def reg(name, kind, build, phys, lod_map=STD, fire=False, role=""):
    P.register(name, kind, build, phys, lod_map)
    pc = P.PIECES[-1]
    pc.fire = fire          # centro de la pieza en la base de la llama (partículas y luz salen de ahí)
    pc.role = role
    return pc


def Q(lod):
    return {0: 1.0, 1: 0.55, 2: 0.3}.get(lod, 0.2)


def n_(x, lod, lo=3):
    return max(lo, int(round(x * Q(lod))))


def proxy(fn):
    """LOWEST automático: cáscara de la caja del HIGH (5 caras) con el material dominante."""
    memo = {}

    def build(lod):
        if lod < 3:
            return fn(lod)
        if "g" not in memo:
            memo["g"] = fn(0)
        g0 = memo["g"]
        mn, mx = g0.bounds()
        counts = {}
        for m in g0.mats:
            if m != "Llama":
                counts[m] = counts.get(m, 0) + 1
        mat = max(counts, key=counts.get) if counts else "Piedra"
        g = Geo()
        pad = (mx - mn) * 0.15
        g.box(mn + V((pad.x, pad.y, 0)), mx - V((pad.x, pad.y, pad.z)), mat, skip=("-z",))
        if "Llama" in g0.mats:
            lz = [g0.verts[i] for f, m in zip(g0.faces, g0.mats) if m == "Llama" for i in f]
            c = sum(lz, V()) / len(lz)
            g.spike(V((c.x, c.y, min(v.z for v in lz))), max(v.z for v in lz) - min(v.z for v in lz) + 0.05,
                    0.06, "Llama")
        return g
    return build


def xf(sub, loc, rz=0.0, rx=0.0, ry=0.0, scale=1.0):
    m = Matrix.Translation(V(loc)) @ Matrix.Rotation(rz, 4, "Z") @ Matrix.Rotation(ry, 4, "Y") @ \
        Matrix.Rotation(rx, 4, "X") @ Matrix.Scale(scale, 4)
    return sub.transform(m)


def front_frame(s):
    return Frame((s * NX, 0, 0), (0, 1, 0), (0, 0, 1), (-s, 0, 0))


def cell_center(k):
    return (YP[k] + YP[k + 1]) / 2


# ================================================================== detalles orgánicos
def garment(g, c, ang, kind, rnd, lod):
    """Ropa interior masculina tirada: calzones (braies), taparrabos o camisa arrugada."""
    c = V(c)
    rot = Matrix.Rotation(ang, 3, "Z")
    nu, nv = n_(10, lod, 5), (2 if lod == 0 else 1)
    if kind == "calzon":
        for sx in (-1, 1):
            g.blob(c + rot @ V((sx * 0.1, -0.08, 0)), 0.09, 0.2, 0.03, nu, nv, "Tela", rnd, 0.3,
                   rot=rot @ Matrix.Rotation(sx * 0.25, 3, "Z"))
        g.blob(c + rot @ V((0, 0.13, 0)), 0.2, 0.09, 0.035, nu, nv, "Tela", rnd, 0.25, rot=rot)
        if lod == 0:  # cordón de la cintura
            pts = [c + rot @ V((math.cos(a) * 0.17, 0.15 + math.sin(a) * 0.05, 0.03)) for a in
                   [i * 0.5 for i in range(13)]]
            g.sweep(pts, 0.006, 3, "Tela")
    elif kind == "taparrabos":
        w, L = 0.16, 0.6
        pts = []
        for i in range(n_(8, lod, 3) + 1):
            t = i / n_(8, lod, 3)
            pts.append(c + rot @ V((math.sin(t * 5 + ang) * 0.06, -L / 2 + L * t, 0.008 + 0.015 * abs(math.sin(t * 7)))))
        for i in range(len(pts) - 1):
            a, b = pts[i], pts[i + 1]
            side = (rot @ V((w / 2, 0, 0)))
            g.face([a - side, a + side, b + side, b - side], "Tela", (0, 0, 1))
    else:  # camisa
        g.blob(c, 0.32, 0.26, 0.05, nu, nv, "Tela", rnd, 0.35, rot=rot)
        for sx in (-1, 1):
            g.blob(c + rot @ V((sx * 0.33, 0.1, 0)), 0.18, 0.07, 0.03, max(nu - 2, 4), 1, "Tela", rnd, 0.3,
                   rot=rot @ Matrix.Rotation(sx * 0.6, 3, "Z"))


def ropa_pile(g, c, n, rnd, lod, spread=0.6, kinds=("calzon", "taparrabos", "camisa")):
    for i in range(n):
        k = kinds[i % len(kinds)]
        off = V((rnd.uniform(-spread, spread), rnd.uniform(-spread, spread), 0.012 * i))
        garment(g, V(c) + off, rnd.uniform(0, 6.28), k, rnd, lod)


def cobweb(g, corner, d1, d2, size, rnd, lod):
    """Telaraña en una esquina: radios y espiral de hilos finos (cara 4)."""
    if lod > 0:
        return
    corner, d1, d2 = V(corner), V(d1).normalized(), V(d2).normalized()
    nrm = d1.cross(d2).normalized()
    anchors = [corner + (d1 * math.cos(a) + d2 * math.sin(a)) * size * rnd.uniform(0.8, 1.15)
               for a in [i * (math.pi / 2) / 5 for i in range(6)]]
    w = 0.0035

    def thread(a, b):
        t = (b - a)
        side = t.cross(nrm).normalized() * w
        g.face([a - side, b - side, b + side, a + side], "Tela", nrm)
        g.face([a - side, b - side, b + side, a + side], "Tela", -nrm)
    for a in anchors:
        thread(corner, a)
    for r in (0.3, 0.55, 0.8):
        pts = [corner + (a - corner) * r + nrm * 0.0 for a in anchors]
        for i in range(len(pts) - 1):
            thread(pts[i], pts[i + 1])


def skeleton(pose, lod, rnd):
    """Esqueleto en coordenadas locales (mira a +Y, Z arriba). Poses: sentado, colgado, tirado."""
    g = Geo()
    J = {}
    if pose == "sentado":       # sentado contra la pared (en -Y), cabeza caída
        J = dict(pelvis=(0, 0.12, 0.12), pecho=(0, 0.05, 0.55), cuello=(0.03, 0.06, 0.78), cabeza=(0.06, 0.16, 0.86),
                 hombroL=(-0.18, 0.04, 0.7), hombroR=(0.18, 0.04, 0.7), codoL=(-0.26, 0.2, 0.42),
                 codoR=(0.25, 0.22, 0.4), manoL=(-0.22, 0.42, 0.18), manoR=(0.3, 0.38, 0.1),
                 caderaL=(-0.11, 0.14, 0.1), caderaR=(0.11, 0.14, 0.1), rodillaL=(-0.15, 0.55, 0.32),
                 rodillaR=(0.18, 0.6, 0.08), pieL=(-0.15, 0.9, 0.05), pieR=(0.24, 1.0, 0.05))
    elif pose == "colgado":     # de pie, desplomado, brazos colgando
        J = dict(pelvis=(0, 0, 0.98), pecho=(0, 0.03, 1.38), cuello=(0, 0.05, 1.56), cabeza=(0.03, 0.14, 1.62),
                 hombroL=(-0.19, 0.02, 1.5), hombroR=(0.19, 0.02, 1.5), codoL=(-0.24, 0.04, 1.2),
                 codoR=(0.23, 0.06, 1.2), manoL=(-0.24, 0.08, 0.92), manoR=(0.22, 0.1, 0.94),
                 caderaL=(-0.11, 0, 0.95), caderaR=(0.11, 0, 0.95), rodillaL=(-0.12, 0.06, 0.52),
                 rodillaR=(0.1, 0.1, 0.53), pieL=(-0.13, 0.02, 0.08), pieR=(0.1, 0.08, 0.08))
    else:                       # tirado boca arriba
        J = dict(pelvis=(0, 0, 0.1), pecho=(0, 0.45, 0.12), cuello=(0, 0.66, 0.1), cabeza=(0.05, 0.78, 0.1),
                 hombroL=(-0.19, 0.58, 0.1), hombroR=(0.19, 0.58, 0.1), codoL=(-0.42, 0.45, 0.05),
                 codoR=(0.3, 0.3, 0.05), manoL=(-0.6, 0.6, 0.03), manoR=(0.28, 0.02, 0.03),
                 caderaL=(-0.11, -0.03, 0.08), caderaR=(0.11, -0.03, 0.08), rodillaL=(-0.2, -0.45, 0.06),
                 rodillaR=(0.18, -0.42, 0.2), pieL=(-0.24, -0.86, 0.04), pieR=(0.16, -0.82, 0.04))
    J = {k: V(v) for k, v in J.items()}
    nb = 6 if lod == 0 else 4
    r = 0.022

    def bone(a, b, rr=r):
        g.cyl(J[a], J[b], rr, nb, "Hueso", caps=(False, False))
        if lod == 0:
            for p in (J[a], J[b]):
                g.blob(p - V((0, 0, rr * 1.2)), rr * 1.6, rr * 1.6, rr * 2.2, 6, 2, "Hueso", rnd, 0.1, flat_bottom=False)
    for a, b in (("hombroL", "codoL"), ("codoL", "manoL"), ("hombroR", "codoR"), ("codoR", "manoR"),
                 ("caderaL", "rodillaL"), ("rodillaL", "pieL"), ("caderaR", "rodillaR"), ("rodillaR", "pieR")):
        bone(a, b, 0.024 if "rodilla" in a or "cadera" in a else 0.018)
    bone("hombroL", "hombroR", 0.012)
    # columna
    spine = [J["pelvis"].lerp(J["pecho"], t) for t in (0, 0.5, 1.0)] + [J["cuello"]]
    g.sweep(spine, 0.02, nb, "Hueso")
    # pelvis
    g.blob(J["pelvis"] - V((0, 0, 0.06)), 0.15, 0.08, 0.11, n_(10, lod, 5), 2, "Hueso", rnd, 0.12, flat_bottom=False)
    # costillas
    up = (J["cuello"] - J["pelvis"]).normalized()
    fwd = (J["cabeza"] - J["cuello"])
    fwd = (fwd - up * fwd.dot(up)).normalized() if fwd.length > 0.01 else V((0, 1, 0))
    side = up.cross(fwd).normalized()
    nr = 5 if lod == 0 else 3
    for i in range(nr):
        c = J["pecho"].lerp(J["pelvis"], 0.08 + i * 0.13)
        wdt = 0.15 - 0.012 * i
        for sg in (-1, 1):
            pts = [c + side * (sg * wdt * math.sin(a)) + fwd * (0.1 * (1 - math.cos(a)) - 0.02) - up * (0.03 * a)
                   for a in [j * math.pi / 6 for j in range(7)]]
            g.sweep(pts, 0.008, 3, "Hueso", caps=False)
    # cráneo y mandíbula
    hc = J["cabeza"]
    g.blob(hc, 0.085, 0.1, 0.1, n_(12, lod, 6), 3 if lod == 0 else 2, "Hueso", rnd, 0.05, flat_bottom=False)
    g.blob(hc + fwd * 0.05 - up * 0.08, 0.06, 0.05, 0.03, 8, 1, "Hueso", rnd, 0.05)
    if lod == 0:  # órbitas oscuras: hundimientos hechos con dos discos de hierro (se ven negros)
        for sg in (-1, 1):
            p = hc + fwd * 0.093 + side * (sg * 0.033) + up * 0.01
            g.cyl(p - fwd * 0.01, p + fwd * 0.004, 0.018, 6, "Hierro", caps=(False, True))
        p = hc + fwd * 0.095 - up * 0.03
        g.cyl(p - fwd * 0.01, p + fwd * 0.004, 0.01, 3, "Hierro", caps=(False, True))
    return g


def skull(g, c, lod, rnd, look=V((0, 1, 0))):
    c = V(c)
    g.blob(c, 0.085, 0.1, 0.1, n_(10, lod, 5), 2, "Hueso", rnd, 0.06, flat_bottom=False)
    if lod == 0:
        f = V(look).normalized()
        sd = f.cross(V((0, 0, 1))).normalized()
        for sg in (-1, 1):
            p = c + f * 0.09 + sd * (sg * 0.033) + V((0, 0, 0.01))
            g.cyl(p - f * 0.01, p + f * 0.004, 0.018, 6, "Hierro", caps=(False, True))


def wheel(g, c, axis, up, R, lod, spokes=8, handles=False, mat="Madera"):
    """Rueda de radios (timón de barco, rueda de tormento, rueda de torno)."""
    c, axis, up = V(c), V(axis).normalized(), V(up).normalized()
    side = up.cross(axis).normalized()
    g.link(c, up, side, R, R, R * 0.07, n_(24, lod, 8), 4 if lod == 0 else 3, mat)
    g.cyl(c - axis * 0.08, c + axis * 0.08, R * 0.16, n_(10, lod, 5), mat)
    for i in range(spokes):
        a = 2 * math.pi * i / spokes
        d = up * math.cos(a) + side * math.sin(a)
        g.cyl(c + d * R * 0.14, c + d * (R * (1.25 if handles else 0.97)), R * 0.04, 4 if lod == 0 else 3, mat,
              caps=(False, handles))
        if handles and lod == 0:
            g.cyl(c + d * R * 1.08, c + d * R * 1.32, R * 0.06, 6, mat, caps=(False, True), r1=R * 0.04)


# ================================================================== frentes: machones y cabezas
def grille_panel(g, s, yc, sg, lod):
    """Paño fijo de reja a un lado de la puerta (sg -1 = sur, lado de la bisagra)."""
    fr = front_frame(s)
    d = GRILLE_D
    P_ = lambda u, v: fr.p(yc + u, v, d)
    top = lambda u: ARCH_SPRING + arch_height(u, ARCH_SPAN, ARCH_RATIO) + 0.06
    step = 0.152 if lod <= 1 else 0.45
    nb = int((2 * HW - 0.16) / step)
    off = -(nb * step) / 2
    for i in range(nb + 1):
        u = off + i * step
        if sg * u > DOOR_HW + 0.06 and abs(u) <= HW - 0.05:
            if lod == 0:
                bar(g, P_(u, FL - 0.04), P_(u, top(u)), 0.021, 6, "Hierro")
            else:  # lámina plana a dos caras: desde lejos se lee igual y cuesta 4 triángulos
                a0, a1 = P_(u - 0.02, FL), P_(u + 0.02, FL)
                b0, b1 = P_(u - 0.02, top(u)), P_(u + 0.02, top(u))
                g.face([a0, a1, b1, b0], "Hierro", fr.n)
    u = sg * (DOOR_HW + 0.045)
    if lod == 0:
        bx(g, *_fx(fr, yc + u - 0.04, yc + u + 0.04, d - 0.04, d + 0.04), FL - 0.04, top(abs(u)), "Hierro",
           skip=("-z", "+z"))
    if lod == 0:
        for z in (FL + 0.2, FL + 1.35):
            a, b = sorted((yc + sg * (DOOR_HW + 0.08), yc + sg * (HW + 0.04)))
            bx(g, *_fx(fr, a, b, d - 0.035, d + 0.035), z, z + 0.055, "Hierro")
    if lod == 0:
        if sg < 0:  # pernios
            for z in (FL + 0.42, FL + 2.18):
                g.cyl(P_(-DOOR_HW - 0.05, z), P_(-DOOR_HW, z), 0.016, 6, "Hierro")
                g.cyl(P_(-DOOR_HW, z - 0.06), P_(-DOOR_HW, z + 0.07), 0.011, 6, "Hierro")
        else:       # cerradero
            p0 = fr.p(yc + DOOR_HW, FL + 1.12, d - 0.06)
            p1 = fr.p(yc + DOOR_HW + 0.09, FL + 1.3, d + 0.06)
            bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Hierro", 0.01)


def make_piers(s):
    S = "O" if s < 0 else "E"
    X = lambda x: s * x
    fr = front_frame(s)
    nave_face = flipx(("-x",), s)[0]
    cell_face = flipx(("+x",), s)[0]
    for j in range(5):
        ua = YP[j] - 0.975 if j > 0 else YP[0] - PT
        ub = YP[j] + 0.975 if j < 4 else YP[4] + PT
        sides = []
        if j > 0:
            sides.append((cell_center(j - 1), +1))   # este machón es el lado norte del vano j-1
        if j < 4:
            sides.append((cell_center(j), -1))

        def build(lod, ua=ua, ub=ub, sides=sides, j=j):
            g = Geo()
            ends = ()
            if lod == 3:
                bx(g, X(NX), X(NX + FT), ua, ub, FL, WT + 0.2, "Piedra",
                   skip=("-z", "-y", "+y", cell_face))
                return g
            bx(g, X(NX), X(NX + FT), ua, ub, ZB, WT, "Piedra",
               skip=("-z",) + ((cell_face,) if lod == 1 else ()) + ends)
            if lod == 0:
                bx(g, *_fx(fr, ua, ub, -FT - 0.07, 0.07), WT, WT + 0.2, "Piedra", 0.035)
                poly = [(0.0, FL - 0.02), (0.09, FL - 0.02), (0.09, FL + 0.42), (0.0, FL + 0.56)]
                g.prism(poly, Frame((X(NX), 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)), ua, ub, "Piedra")
                for yc, sg in sides:
                    u_in = yc + sg * HW
                    zq = FL + 0.56
                    hq = (ARCH_SPRING - 0.26 - zq) / 5
                    for i in range(5):
                        wq = 0.55 if i % 2 == 0 else 0.34
                        p0 = fr.p(u_in, zq + i * hq + 0.008, 0)
                        p1 = fr.p(u_in + sg * wq, zq + (i + 1) * hq - 0.008, 0.035)
                        bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Piedra", skip=(cell_face,))
                    p0 = fr.p(u_in, ARCH_SPRING - 0.26, 0)
                    p1 = fr.p(u_in + sg * 0.3, ARCH_SPRING, 0.11)
                    bx(g, p0.x, p1.x, p0.y, p1.y, p0.z, p1.z, "Piedra", skip=(cell_face,))
                    # manchas de hollín: losas finas oscuras de hierro sobre el sitio de la antorcha
            for yc, sg in sides:
                grille_panel(g, s, yc, sg, lod)
            return g

        def phys(ua=ua, ub=ub, sides=sides):
            out = [pbox(X(NX), X(NX + FT), ua, ub, ZB, WT + 0.2)]
            g0, g1 = NX - GRILLE_D - 0.06, NX - GRILLE_D + 0.06
            for yc, sg in sides:
                a, b = sorted((yc + sg * HW, yc + sg * DOOR_HW))
                out.append(pbox(X(g0), X(g1), a, b, FL, CROWN))
            return out

        reg(f"M{j}{S}_Machon", "estructura", build, phys, BIG)


def make_head(s, k):
    tag = ROOMS[(s, k)][0]
    X = lambda x: s * x
    fr = front_frame(s)
    yc = cell_center(k)
    cell_face = flipx(("+x",), s)[0]

    def build(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        arch_wall(g, fr, yc - HW, yc + HW, yc, ARCH_SPAN, ARCH_RATIO, ARCH_SPRING, ZB, WT, FT, n_side, "Piedra",
                  skip_u0=True, skip_u1=True, thr_top=None, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
        if lod == 3:
            return g
        if lod == 0:
            bx(g, *_fx(fr, yc - HW, yc + HW, -FT - 0.07, 0.07), WT, WT + 0.2, "Piedra", 0.035,
               skip=("-y", "+y"))
            voussoirs(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 6, 0.55, 0.06, "Piedra")
            hood(g, fr, yc, ARCH_SPRING, ARCH_SPAN, ARCH_RATIO, 12, 0.68, 0.13, 0.11, "Piedra")
        else:
            pass
        # reja sobre la puerta, cabecero y travesaño del arranque
        d = GRILLE_D
        P_ = lambda u, v: fr.p(yc + u, v, d)
        top = lambda u: ARCH_SPRING + arch_height(u, ARCH_SPAN, ARCH_RATIO) + 0.06
        head = FL + DOOR_H + 0.02
        step = 0.152
        nb = int((2 * HW - 0.16) / step)
        off = -(nb * step) / 2
        for i in range(nb + 1):
            u = off + i * step
            if abs(u) < DOOR_HW + 0.06:
                if lod == 0:
                    bar(g, P_(u, head + 0.03), P_(u, top(u)), 0.021, 6, "Hierro")
                else:
                    a0, a1 = P_(u - 0.02, head), P_(u + 0.02, head)
                    g.face([a0, a1, P_(u + 0.02, top(u)), P_(u - 0.02, top(u))], "Hierro", fr.n)
            elif lod == 0 and abs(u) < HW - 0.1:
                z = ARCH_SPRING + 0.03
                g.cyl(P_(u, z), P_(u, z + 0.12), 0.03, 4, "Hierro", caps=(True, False), r1=0.0)
        sk = () if lod == 0 else ("-y", "+y", "-z", flipx(("+x",), s)[0])
        bx(g, *_fx(fr, yc - HW - 0.04, yc + HW + 0.04, d - 0.045, d + 0.045), head, head + 0.09, "Hierro", skip=sk)
        bx(g, *_fx(fr, yc - HW - 0.04, yc + HW + 0.04, d - 0.035, d + 0.035), ARCH_SPRING - 0.03,
           ARCH_SPRING + 0.03, "Hierro", skip=sk)
        return g

    def phys():
        g0, g1 = NX - GRILLE_D - 0.06, NX - GRILLE_D + 0.06
        return [pbox(X(NX), X(NX + FT), yc - HW, yc + HW, CROWN, WT + 0.2),
                pbox(X(g0), X(g1), yc - DOOR_HW, yc + DOOR_HW, FL + DOOR_H + 0.02, CROWN)]

    reg(f"{tag}_Arco", "estructura", build, phys, BIG, role=ROOMS[(s, k)][1])


def make_door(s, k):
    tag, room = ROOMS[(s, k)]
    fr = front_frame(s)
    yc = cell_center(k)

    def build(lod):
        g = Geo()
        d = GRILLE_D
        P_ = lambda u, v: fr.p(yc + u, v, d)
        z0, z1 = FL + 0.03, FL + DOOR_H - 0.02
        u0, u1 = -DOOR_HW + 0.03, DOOR_HW - 0.02
        if lod == 3:
            g.face([P_(u0, z0), P_(u1, z0), P_(u1, z1), P_(u0, z1)], "Hierro", fr.n)
            g.face([P_(u0, z0), P_(u1, z0), P_(u1, z1), P_(u0, z1)], "Hierro", -fr.n)
            return g
        c = 0.006 if lod == 0 else 0
        for (a, b) in ((u0, u0 + 0.06), (u1 - 0.06, u1)):
            bx(g, *_fx(fr, yc + a, yc + b, d - 0.03, d + 0.03), z0, z1, "Hierro", c)
        for z in ((z0, z0 + 0.06), (FL + 1.25, FL + 1.3), (z1 - 0.06, z1)):
            bx(g, *_fx(fr, yc + u0 + 0.06, yc + u1 - 0.06, d - 0.025, d + 0.025), z[0], z[1], "Hierro")
        nb = 7 if lod <= 1 else 3
        for i in range(nb):
            u = u0 + 0.06 + (u1 - u0 - 0.12) * (i + 1) / (nb + 1)
            bar(g, P_(u, z0 + 0.03), P_(u, z1 - 0.03), 0.02, {0: 8, 1: 4}.get(lod, 3), "Hierro")
        if lod == 2:
            return g
        g.sweep([P_(u0 + 0.06, z0 + 0.06), P_(u1 - 0.06, FL + 1.25)], 0.022, 4, "Hierro")
        g.sweep([P_(u0 + 0.06, FL + 1.3), P_(u1 - 0.06, z1 - 0.06)], 0.022, 4, "Hierro")
        for z in (FL + 0.42, FL + 2.18):
            g.cyl(P_(-DOOR_HW, z - 0.07), P_(-DOOR_HW, z + 0.07), 0.03, 8 if lod == 0 else 4, "Hierro")
            g.cyl(P_(-DOOR_HW + 0.02, z), P_(u0 + 0.05, z), 0.012, 4, "Hierro")
            bx(g, *_fx(fr, yc + u0, yc + u0 + 0.35, d - 0.034, d + 0.034), z - 0.03, z + 0.03, "Hierro")
        bx(g, *_fx(fr, yc + u1 - 0.2, yc + u1 + 0.005, d - 0.05, d + 0.05), FL + 1.1, FL + 1.32, "Hierro", c)
        if lod == 0:
            for sg in (1, -1):
                face = d + sg * 0.05
                n = fr.n * sg
                sc = fr.p(yc + u1 - 0.1, FL + 1.21, face) + n * 0.02
                g.link(sc, n, V((0, 0, 1)), 0.035, 0.022, 0.008, 8, 4, "Hierro")
                rc = sc + n * 0.012 + V((0, 0, -(0.022 - 0.008) + 0.009 - 0.06))
                g.link(rc, V((0, 1, 0)), V((0, 0, 1)), 0.06, 0.06, 0.009, 14, 5, "Hierro")
                kp = fr.p(yc + u1 - 0.1, FL + 1.15, face)
                g.cyl(kp, kp + n * 0.006, 0.018, 6, "Hierro", caps=(False, True))
            # candado colgante
            lp = fr.p(yc + u1 - 0.06, FL + 1.0, d + 0.06)
            g.bbox(lp - V((0.04, 0.04, 0.05)), lp + V((0.04, 0.04, 0.03)), "Hierro", 0.01)
            g.link(lp + V((0, 0, 0.06)), V((0, 0, 1)), fr.u, 0.035, 0.025, 0.007, 8, 4, "Hierro")
        return g

    reg(f"{tag}_Puerta", "puerta", build,
        lambda: [pbox(*_fx(fr, yc - DOOR_HW + 0.03, yc + DOOR_HW - 0.02, GRILLE_D - 0.05, GRILLE_D + 0.05),
                      FL + 0.03, FL + DOOR_H - 0.02)], role=room)


# ================================================================== cascarón de cada sala
def make_room_shell(s, k0, k1, tag, room, roof="boveda"):
    """Suelo, muro exterior, divisorio norte y cubierta de las salas k0..k1 (inclusive)."""
    X = lambda x: s * x
    y0, y1 = YP[k0], YP[k1 + 1]
    cy0, cy1 = y0 + PT, y1 - PT
    inner = flipx(("-x",), s)[0]

    # ---------------- suelo de tierra con umbrales
    def suelo(lod):
        g = Geo()
        x0, x1 = 3.8, XI
        rr = rng(f"suelo-{tag}")
        nxg, nyg = {0: (14, int(10 * (k1 - k0 + 1))), 1: (2, 2)}.get(lod, (1, 1))
        grid = []
        for i in range(nxg + 1):
            row = []
            for j in range(nyg + 1):
                xx = x0 + (x1 - x0) * i / nxg
                yy = cy0 + (cy1 - cy0) * j / nyg
                edge = i in (0, nxg) or j in (0, nyg)
                z = FL if edge else FL + rr.uniform(0.0, 0.035) * (1 if lod == 0 else 0.4)
                row.append(V((X(xx), yy, z)))
            grid.append(row)
        for i in range(nxg):
            for j in range(nyg):
                g.face([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "Suelo", (0, 0, 1))
        for k in range(k0, k1 + 1):
            yc = cell_center(k)
            bx(g, X(NX), X(NX + FT), yc - HW, yc + HW, ZB if lod <= 1 else FL - 0.01, FL, "Suelo",
               skip=("-z", "-y", "+y", inner) if lod >= 1 else ("-z",))
        if lod == 0:
            bx(g, X(x0), X(x1), cy0, cy1, ZB + 0.1, FL, "Suelo", skip=("+z", "-z", "-x", "+x"))
            for i in range(70):
                px = X(rr.uniform(4.2, 11.0))
                py = rr.uniform(cy0 + 0.2, cy1 - 0.2)
                a = rr.uniform(0, math.pi)
                L = rr.uniform(0.12, 0.3)
                d = V((math.cos(a), math.sin(a), 0))
                pr = V((-d.y, d.x, 0)) * 0.006
                p = V((px, py, FL + 0.02))
                g.face([p - d * L / 2 - pr, p + d * L / 2 - pr, p + d * L / 2 + pr, p - d * L / 2 + pr], "Paja",
                       (0, 0, 1))
            for i in range(10):  # cascotes junto a los muros
                side = rr.choice((0, 1, 2))
                if side == 0:
                    p = V((X(rr.uniform(10.9, 11.4)), rr.uniform(cy0 + 0.2, cy1 - 0.2), FL))
                else:
                    yy = cy0 + 0.25 if side == 1 else cy1 - 0.25
                    p = V((X(rr.uniform(4.5, 11.0)), yy, FL))
                g.blob(p, rr.uniform(0.04, 0.1), rr.uniform(0.04, 0.09), rr.uniform(0.03, 0.06), 6, 1, "Piedra", rr,
                       0.3)
        return g

    reg(f"{tag}_Suelo", "estructura", suelo,
        lambda: [pbox(X(NX), X(XI), cy0, cy1, FL - 0.3, FL + 0.01)], BIG, role=room)

    # ---------------- divisorio norte
    if True:
        top_part = WT if k1 == 3 else VS

        def particion(lod):
            g = Geo()
            if lod == 3:
                bx(g, X(3.8), X(XI), y1 - PT, y1 + PT, top_part - 0.02, top_part, "Piedra",
                   skip=("-z", "-x", "+x", "-y", "+y"))
                return g
            bx(g, X(3.8), X(XI), y1 - PT, y1 + PT, ZB, top_part, "Piedra",
               skip=("-z", "-x", "+x") + (() if k1 == 3 else ("+z",)))
            if k1 == 3:
                bx(g, X(3.75), X(XI + 0.05), y1 - PT - 0.06, y1 + PT + 0.06, WT, WT + 0.18, "Piedra",
                   0.03 if lod == 0 else 0)
            return g

        reg(f"{tag}_Particion", "estructura", particion,
            lambda: [pbox(X(3.8), X(XI), y1 - PT, y1 + PT, ZB, top_part + (0.18 if k1 == 3 else 0))], BIG)

    # ---------------- muro exterior con aspilleras y contrafuertes
    def muro(lod):
        g = Geo()
        ox0, ox1 = XI, XO
        ends = (("-y",) if k0 > 0 else ()) + (("+y",) if k1 < 3 else ())
        if lod == 3:
            bx(g, X(ox0), X(ox1), y0, y1, FL, WT, "Piedra", skip=("-z", "-y", "+y", inner))
            for k in range(k0, k1 + 1):
                yb = YP[k + 1]
                bx(g, X(XO), X(XB), yb - 0.45, yb + 0.45, FL, FL + 5.6, "Piedra", skip=("-z", inner, "-y"))
            return g
        if lod == 1:
            bx(g, X(ox0), X(ox1), y0, y1, ZB, WT + 0.18, "Piedra", skip=("-z",) + ends)
        else:
            sw_in, sw_out = 0.36, 0.09
            sz0, sz1 = FL + 1.9, FL + 3.6
            segs = []
            ya = y0
            for k in range(k0, k1 + 1):
                yc = cell_center(k)
                segs.append((ya, yc - sw_in))
                bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, ZB, sz0, "Piedra", skip=("-z", "-y", "+y"))
                bx(g, X(ox0), X(ox1), yc - sw_in, yc + sw_in, sz1, WT, "Piedra", skip=("-y", "+y"))
                for sg in (-1, 1):
                    poly = [(X(ox0), yc + sg * sw_in), (X(ox1), yc + sg * sw_in), (X(ox1), yc + sg * sw_out),
                            (X(ox0 + 0.32), yc + sg * sw_out)]
                    g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), sz0, sz1, "Piedra",
                            caps=(False, False))
                    # barrotes en la aspillera
                bar(g, V((X(ox0 + 0.25), yc, sz0)), V((X(ox0 + 0.25), yc, sz1)), 0.018, 6, "Hierro")
                ya = yc + sw_in
            segs.append((ya, y1))
            for i, (a, b) in enumerate(segs):
                sk = ("-z",) + (("-y",) if i == 0 and k0 > 0 else ()) + (("+y",) if i == len(segs) - 1 and k1 < 3 else ())
                bx(g, X(ox0), X(ox1), a, b, ZB, WT, "Piedra", skip=sk)
            bx(g, X(ox0 - 0.05), X(ox1 + 0.07), y0, y1, WT, WT + 0.18, "Piedra", 0.03, skip=ends)
            poly = [(X(ox1), ZB), (X(ox1 + 0.12), ZB), (X(ox1 + 0.12), FL + 0.35), (X(ox1), FL + 0.5)]
            g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), y0, y1, "Piedra",
                    caps=(k0 == 0, k1 == 3))
        for k in range(k0, k1 + 1):
            yb0, yb1 = YP[k + 1] - 0.45, YP[k + 1] + 0.45
            if lod == 0:
                bx(g, X(XO - 0.02), X(XB), yb0, yb1, ZB, FL + 2.4, "Piedra", 0.03, skip=("-z",))
                g.prism([(X(XO - 0.02), FL + 2.4), (X(XB), FL + 2.4), (X(XB - 0.14), FL + 2.62),
                         (X(XO - 0.02), FL + 2.62)], Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0, yb1,
                        "Piedra")
                bx(g, X(XO - 0.02), X(XB - 0.14), yb0 + 0.04, yb1 - 0.04, FL + 2.62, FL + 5.0, "Piedra", 0.03)
                g.prism([(X(XO - 0.02), FL + 5.0), (X(XB - 0.14), FL + 5.0), (X(XO - 0.02), FL + 6.3)],
                        Frame((0, 0, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), yb0 + 0.04, yb1 - 0.04, "Piedra")
            else:
                bx(g, X(XO), X(XB), yb0, yb1, ZB, FL + 5.6, "Piedra", skip=("-z", inner))
        return g

    def muro_phys():
        out = [pbox(X(XI), X(XO), y0, y1, ZB, WT + 0.18)]
        for k in range(k0, k1 + 1):
            out.append(pbox(X(XO), X(XB), YP[k + 1] - 0.45, YP[k + 1] + 0.45, ZB, FL + 5.6))
        return out

    reg(f"{tag}_Muro", "estructura", muro, muro_phys, BIG)

    # ---------------- cubierta
    if roof == "boveda":
        yc = cell_center(k0)

        def boveda(lod):
            g = Geo()
            n = {0: 24, 1: 8, 2: 6, 3: 3}[lod]
            xa, xb = X(3.8), X(XI)
            Ri, Ro = R_VAULT, R_VAULT + T_VAULT

            def ring(rad, i, x):
                a = math.pi * i / n
                return V((x, yc - rad * math.cos(a), VS + rad * math.sin(a)))
            ctr_axis = lambda x: V((x, yc, VS))
            for i in range(n):
                q = [ring(Ro, i, xa), ring(Ro, i + 1, xa), ring(Ro, i + 1, xb), ring(Ro, i, xb)]
                g.face(q, "Piedra", sum(q, V()) / 4 - ctr_axis((xa + xb) / 2))
                if lod == 0:
                    q = [ring(Ri, i, xa), ring(Ri, i + 1, xa), ring(Ri, i + 1, xb), ring(Ri, i, xb)]
                    g.face(q, "Piedra", ctr_axis((xa + xb) / 2) - sum(q, V()) / 4)
            if lod == 0:
                r = rng(f"boveda-{tag}")
                for xr in (6.35, 9.05):
                    xa_r, xb_r = X(xr - 0.18), X(xr + 0.18)
                    rin, rout = Ri - 0.13, Ri
                    for i in range(n):
                        for x in (xa_r, xb_r):
                            q = [ring(rin, i, x), ring(rin, i + 1, x), ring(rout, i + 1, x), ring(rout, i, x)]
                            g.face(q, "Piedra", V((x - X(xr), 0, 0)))
                        q = [ring(rin, i, xa_r), ring(rin, i + 1, xa_r), ring(rin, i + 1, xb_r), ring(rin, i, xb_r)]
                        g.face(q, "Piedra", ctr_axis(X(xr)) - sum(q, V()) / 4)
                    for sg in (-1, 1):
                        yy = yc + sg * Ri
                        bx(g, X(xr - 0.22), X(xr + 0.22), yy, yy - sg * 0.2, VS - 0.38, VS + 0.02, "Piedra", 0.03)
                # telarañas en los arranques de la bóveda
                for sg in (-1, 1):
                    cobweb(g, V((X(XI - 0.02), yc + sg * (Ri - 0.02), VS + 0.05)), V((-s, 0, 0)), V((0, -sg, 0.4)),
                           0.7, r, lod)
                    cobweb(g, V((X(3.82), yc + sg * (Ri - 0.02), VS + 0.05)), V((s, 0, 0)), V((0, -sg, 0.4)),
                           0.55, r, lod)
            return g

        reg(f"{tag}_Boveda", "estructura", boveda,
            lambda: [pbox(X(3.8), X(XI), yc - 1.2, yc + 1.2, VS + R_VAULT + 0.02, VS + R_VAULT + T_VAULT)], BIG)
    else:
        # techo de vigas para la perrera doble (por encima de la clave de los arcos)
        zc = CROWN + 0.15

        def techo(lod):
            g = Geo()
            xa, xb = sorted((X(3.8), X(XI)))
            if lod == 3:
                g.face([V((xa, cy0, zc + 0.32)), V((xb, cy0, zc + 0.32)), V((xb, cy1, zc + 0.32)),
                        V((xa, cy1, zc + 0.32))], "Madera", (0, 0, 1))
                return g
            if lod >= 1:
                g.face([V((xa, cy0, zc + 0.32)), V((xb, cy0, zc + 0.32)), V((xb, cy1, zc + 0.32)),
                        V((xa, cy1, zc + 0.32))], "Madera", (0, 0, 1))
                g.face([V((xa, cy0, zc)), V((xb, cy0, zc)), V((xb, cy1, zc)), V((xa, cy1, zc))], "Madera", (0, 0, -1))
                return g
            nj = int((cy1 - cy0) / 0.9)
            for i in range(nj + 1):
                y = cy0 + 0.1 + (cy1 - cy0 - 0.2) * i / nj
                bx(g, xa, xb, y - 0.12, y + 0.12, zc, zc + 0.26, "Madera", 0.02 if lod == 0 else 0,
                   skip=("-x", "+x") if lod else ())
            bx(g, xa, xb, cy0, cy1, zc + 0.26, zc + 0.32, "Madera", skip=() if lod == 0 else ("-x", "+x", "-y", "+y"))
            if lod == 0:
                for x in (xa + 0.2, xb - 0.2):  # carreras sobre ménsulas
                    bx(g, x - 0.15, x + 0.15, cy0, cy1, zc - 0.25, zc, "Madera", 0.02)
                r = rng(f"techo-{tag}")
                for i in range(6):
                    y = r.uniform(cy0 + 0.4, cy1 - 0.4)
                    cobweb(g, V((xa + 0.02 if i % 2 else xb - 0.02, y, zc - 0.01)), V((1 if i % 2 else -1, 0, 0)),
                           V((0, 1, -0.6)), 0.6, r, lod)
            return g

        reg(f"{tag}_Techo", "estructura", techo,
            lambda: [pbox(X(3.8), X(XI), cy0, cy1, zc, zc + 0.32)], BIG)


# ================================================================== luces de pared
def wall_torch(name, P0, n, role=""):
    def build(lod):
        return torch(V(P0), V(n), lod, f"antorcha-{name}")
    reg(name, "luz", build, bbox_phys(build), SMALL, fire=True, role=role)


def hanging_lantern(name, P_top):
    def build(lod):
        return lantern(V(P_top), lod, f"farol-{name}")
    reg(name, "luz", build, bbox_phys(build), SMALL, fire=True)


# ================================================================== mobiliario de las salas
def sitter(name, build, role, lod_map=SMALL, kind="mueble"):
    """Pieza en la que se sienta un avatar: física convexa, LOWEST automático."""
    b = proxy(build)
    reg(name, kind, b, bbox_phys(b), lod_map, role=role)


def deco(name, build, role="", lod_map=SMALL, fire=False):
    b = proxy(build)
    reg(name, "luz" if fire else "deco", b, bbox_phys(b), lod_map, fire=fire, role=role)


def chains_from(g, a, b, lod, sag=0.25):
    """Cadena colgada entre dos puntos (catenaria aproximada)."""
    a, b = V(a), V(b)
    pts = []
    for i in range(25):
        t = i / 24
        p = a.lerp(b, t)
        p.z -= sag * 4 * t * (1 - t)
        pts.append(p)
    chain(g, pts, 0.05, 0.03, 0.01, lod, rng("c"), -10)


def make_leva():
    """C01 La Leva: registro de reclutas, escriba y hierros de marcar."""
    s, k = -1, 0
    X = lambda x: s * x
    yc = cell_center(k)

    def escritorio(lod):
        g = Geo()
        r = rng("leva-escritorio")
        cx, cy = X(7.6), yc + 0.6
        q = 0.02 if lod == 0 else 0
        for dx in (-0.6, 0.6):
            for dy in (-0.3, 0.3):
                bx(g, cx + dx - 0.05, cx + dx + 0.05, cy + dy - 0.05, cy + dy + 0.05, FL, FL + 0.95, "Madera", q)
        # tablero inclinado de escriba
        top = Geo()
        top.bbox(V((-0.75, -0.42, -0.03)), V((0.75, 0.42, 0.03)), "Madera", 0.01 if lod == 0 else 0)
        g.extend(xf(top, (cx, cy, FL + 1.0), rx=-0.18))
        bx(g, cx - 0.72, cx + 0.72, cy + 0.3, cy + 0.4, FL + 0.98, FL + 1.12, "Madera")
        # libro de la leva abierto
        book = Geo()
        for sx in (-1, 1):
            book.bbox(V((0 if sx > 0 else -0.27, -0.19, 0)), V((0.27 if sx > 0 else 0, 0.19, 0.035)), "Tela",
                      0.006 if lod == 0 else 0)
        book.box(V((-0.29, -0.2, -0.012)), V((0.29, 0.2, 0.0)), "Tela")
        g.extend(xf(book, (cx - 0.1, cy - 0.05, FL + 1.04), rx=-0.18))
        # tintero, pluma, vela y sello
        g.cyl(V((cx + 0.48, cy + 0.33, FL + 1.12)), V((cx + 0.48, cy + 0.33, FL + 1.19)), 0.035, 8, "Hierro")
        quill = [V((cx + 0.48, cy + 0.33, FL + 1.16)), V((cx + 0.43, cy + 0.25, FL + 1.38)),
                 V((cx + 0.38, cy + 0.2, FL + 1.5))]
        g.sweep(quill, 0.004, 3, "Hueso", caps=False)
        g.face([quill[1] + V((0.02, 0, 0)), quill[2], quill[1] - V((0.02, 0, -0.05))], "Tela", (0, 1, 0))
        g.face([quill[1] + V((0.02, 0, 0)), quill[2], quill[1] - V((0.02, 0, -0.05))], "Tela", (0, -1, 0))
        g.cyl(V((cx - 0.55, cy + 0.33, FL + 1.12)), V((cx - 0.55, cy + 0.33, FL + 1.3)), 0.03, 8, "Paja")
        g.flame(V((cx - 0.55, cy + 0.33, FL + 1.3)), 0.07, 0.014, 4, "Llama", r)
        # taburete del escriba
        sx_, sy_ = cx, cy - 0.75
        g.cyl(V((sx_, sy_, FL + 0.55)), V((sx_, sy_, FL + 0.6)), 0.22, n_(12, lod, 6), "Madera")
        for a in range(3):
            ang = a * 2.094
            g.cyl(V((sx_, sy_, FL + 0.56)), V((sx_ + math.cos(ang) * 0.2, sy_ + math.sin(ang) * 0.2, FL)), 0.025, 4,
                  "Madera", caps=(False, False))
        return g

    sitter("C01_Escritorio", escritorio, "escriba")
    SITS["C01_Escritorio"] = (V((X(7.6), yc + 0.6 - 0.75, FL + 1.0)), 90, "foso_escriba", "sit")

    def brasero_marcar(lod):
        g = Geo()
        P0 = V((X(9.6), yc - 1.7, FL))
        sub = brazier(V((0, 0, 0)), lod if lod < 3 else 3)
        g.extend(xf(sub, P0, scale=0.55))
        if lod <= 1:  # hierros de marcar apoyados en las brasas
            for i, a in enumerate((-0.5, 0.1, 0.7)):
                d = V((math.cos(a), math.sin(a), 0))
                p0 = P0 + V((0, 0, 0.5)) - d * 0.05
                p1 = P0 + d * 0.85 + V((0, 0, 0.15))
                g.cyl(p0, p1, 0.012, 4, "Hierro", caps=(False, True))
                g.cyl(p1 - d * 0.18, p1 + d * 0.02, 0.022, 6, "Madera")
                g.link(p0 + V((0, 0, -0.02)), d, V((0, 0, 1)), 0.04, 0.04, 0.008, 8, 3, "Hierro")
        return g

    reg("C01_Brasero_Marcar", "luz", brasero_marcar, bbox_phys(brasero_marcar), SMALL, fire=True, role="marcar")

    def atrezzo(lod):
        g = Geo()
        r = rng("leva-atrezzo")
        # todo pegado al muro exterior: el casco convexo de la pieza no invade la sala
        wx = XI                  # cara interior del muro exterior
        # tablón de la leva: tablero con pliegos clavados
        bx(g, X(wx - 0.06), X(wx), yc - 2.3, yc - 0.3, FL + 1.3, FL + 2.5, "Madera", 0.015 if lod == 0 else 0)
        if lod == 0:
            for i in range(7):
                y0_ = yc - 2.2 + i * 0.27 + r.uniform(-0.03, 0.03)
                z0 = FL + 1.45 + r.uniform(0, 0.55)
                bx(g, X(wx - 0.068), X(wx - 0.06), y0_, y0_ + 0.22, z0, z0 + 0.3, "Tela")
                g.cyl(V((X(wx - 0.068), y0_ + 0.11, z0 + 0.26)), V((X(wx - 0.085), y0_ + 0.11, z0 + 0.26)), 0.008, 4,
                      "Hierro", caps=(False, True))
        # arcón de ropa de recluta con camisas dobladas
        bx(g, X(wx - 0.65), X(wx - 0.05), yc - 2.2, yc - 1.0, FL, FL + 0.6, "Madera", 0.02 if lod == 0 else 0)
        if lod == 0:
            for z in (FL + 0.12, FL + 0.48):
                bx(g, X(wx - 0.66), X(wx - 0.04), yc - 2.21, yc - 0.99, z, z + 0.05, "Hierro")
            for i in range(4):
                bx(g, X(wx - 0.55), X(wx - 0.15), yc - 2.1 + i * 0.27, yc - 1.85 + i * 0.27, FL + 0.6,
                   FL + 0.66 + 0.05 * (i % 2), "Tela", 0.01)
        # grilletes de leva colgados en el muro exterior
        for i in range(3):
            y = yc + 0.4 + i * 0.8
            bottom, rc, u = wall_anchor(g, (X(XI), y, FL + 1.9), V((-s, 0, 0)), V((0, 0, 1)), min(lod, 2))
            if lod <= 1:  # grillete abierto colgado de la argolla
                g.link(bottom + V((0, 0, -0.07)), V((0, 0, 1)), V((0, 1, 0)), 0.09, 0.09, 0.016, 10, 4, "Hierro")
        if lod == 0:
            ropa_pile(g, (X(11.0), yc + 1.4, FL + 0.02), 4, r, lod, 0.35)
        return g

    deco("C01_Atrezzo", atrezzo)


def make_potro():
    s, k = -1, 1
    X = lambda x: s * x
    yc = cell_center(k)

    def potro(lod):
        g = Geo()
        cx = X(7.6)
        L, Wd, H = 2.5, 0.8, 0.85
        q = 0.02 if lod == 0 else 0
        for sy in (-1, 1):
            bx(g, cx - L / 2, cx + L / 2, yc + sy * Wd / 2 - 0.08, yc + sy * Wd / 2 + 0.08, FL + H - 0.18, FL + H,
               "Madera", q)
            for sx in (-1, 1):
                bx(g, cx + sx * (L / 2 - 0.1) - 0.08, cx + sx * (L / 2 - 0.1) + 0.08, yc + sy * Wd / 2 - 0.08,
                   yc + sy * Wd / 2 + 0.08, FL, FL + H + (0.25 if lod == 0 else 0.2), "Madera", q)
        for i in range(n_(7, lod, 3)):
            x = cx - L / 2 + 0.4 + i * (L - 0.8) / max(n_(7, lod, 3) - 1, 1)
            bx(g, x - 0.06, x + 0.06, yc - Wd / 2, yc + Wd / 2, FL + H - 0.06, FL + H - 0.01, "Madera")
        for sx in (-1, 1):  # rodillos con soga
            xr = cx + sx * (L / 2 - 0.1)
            g.cyl(V((xr, yc - Wd / 2 - 0.12, FL + H + 0.12)), V((xr, yc + Wd / 2 + 0.12, FL + H + 0.12)), 0.08,
                  n_(12, lod, 5), "Madera")
            if lod <= 1:
                for t in (-0.15, -0.05, 0.05, 0.15):
                    g.link(V((xr, yc + t, FL + H + 0.12)), V((1, 0, 0)), V((0, 0, 1)), 0.09, 0.09, 0.012,
                           n_(10, lod, 6), 3, "Paja")
                for t in (-0.15, 0.15):
                    a = V((xr, yc + t, FL + H + 0.12))
                    b = V((cx + sx * 0.45, yc + t, FL + H + 0.04))
                    g.sweep([a, b], 0.012, 3, "Paja")
                    g.link(b, V((0, 1, 0)), V((1, 0, 0)), 0.05, 0.05, 0.015, 10, 3, "Tela")  # grillete de cuero
        # rueda del torno en un extremo
        wheel(g, V((cx + L / 2 + 0.05, yc + Wd / 2 + 0.2, FL + H + 0.12)), V((0, 1, 0)), V((0, 0, 1)), 0.45, lod,
              6, handles=True)
        return g

    sitter("C02_Potro", potro, "potro")
    SITS["C02_Potro"] = (V((X(7.6), yc, FL + 1.15)), 0, "foso_potro", "dead")

    def atrezzo(lod):
        g = Geo()
        r = rng("potro-atrezzo")
        wy = YP[2] - PT  # cara del divisorio norte (mira al sur)
        # panoplia de herramientas
        bx(g, X(5.0), X(7.4), wy - 0.06, wy, FL + 1.3, FL + 2.3, "Madera", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for i in range(6):
                x = X(5.25 + i * 0.38)
                g.cyl(V((x, wy - 0.06, FL + 2.1)), V((x, wy - 0.12, FL + 2.1)), 0.012, 4, "Hierro")
                tool = Geo()
                if i % 3 == 0:     # tenazas
                    tool.cyl(V((-0.03, 0, 0)), V((0.04, 0, -0.55)), 0.012, 4, "Hierro")
                    tool.cyl(V((0.03, 0, 0)), V((-0.04, 0, -0.55)), 0.012, 4, "Hierro")
                elif i % 3 == 1:   # mazo
                    tool.cyl(V((0, 0, 0)), V((0, 0, -0.5)), 0.016, 5, "Madera")
                    tool.bbox(V((-0.07, -0.04, -0.62)), V((0.07, 0.04, -0.5)), "Hierro", 0.008)
                else:              # garfio
                    tool.sweep([V((0, 0, 0)), V((0, 0, -0.35)), V((0.06, 0, -0.45)), V((0.1, 0, -0.38))], 0.01, 4,
                               "Hierro")
                g.extend(xf(tool, (x, wy - 0.12, FL + 2.08)))
        # cubo de agua y ropa tirada
        bc = V((X(10.9), wy - 0.4, FL))
        g.cyl(bc, bc + V((0, 0, 0.38)), 0.17, n_(12, lod, 6), "Madera", caps=(True, False), r1=0.2)
        if lod == 0:
            g.cyl(bc + V((0, 0, 0.3)), bc + V((0, 0, 0.02)), 0.186, 12, "Suelo", caps=(True, False), r1=0.171)
            ropa_pile(g, (X(8.3), wy - 0.45, FL + 0.02), 5, r, lod, 0.35)
            sk = skeleton("tirado", lod, r)   # tendido a lo largo del muro
            g.extend(xf(sk, (X(9.6), wy - 0.55, FL), rz=-1.57 * s))
        return g

    deco("C02_Atrezzo", atrezzo)
    wall_torch("C02_Antorcha", (X(XI), yc + 1.8, FL + 2.3), (-s, 0, 0), "El Potro")


def make_cepo():
    s, k = -1, 2
    X = lambda x: s * x
    yc = cell_center(k)

    def picota(lod):
        g = Geo()
        cx, cy = X(7.4), yc
        q = 0.02 if lod == 0 else 0
        bx(g, cx - 1.1, cx + 1.1, cy - 1.1, cy + 1.1, FL, FL + 0.32, "Madera", q)
        if lod == 0:
            for i in range(9):  # tablas de la tarima
                y = cy - 1.1 + i * 2.2 / 9
                bx(g, cx - 1.11, cx + 1.11, y + 0.005, y + 2.2 / 9 - 0.005, FL + 0.32, FL + 0.335, "Madera")
            for i in range(2):  # peldaños
                bx(g, cx - 0.5, cx + 0.5, cy - 1.1 - 0.3 * (i + 1), cy - 1.1 - 0.3 * i, FL, FL + 0.21 - 0.1 * i,
                   "Madera", q)
        base = FL + 0.335
        bx(g, cx - 0.1, cx + 0.1, cy + 0.2, cy + 0.4, base, base + 2.0, "Madera", q)
        # yugo con tres agujeros (cuello y muñecas)
        holes = [(-0.38, 0.055), (0.0, 0.085), (0.38, 0.055)]
        w = 0.65
        # (polígono simplificado: dos tableros con muescas)
        for sgn, z0 in ((-1, 1.42), (1, 1.42)):
            poly = [(-w, 0.0)]
            for hx, hr in holes:
                nseg = 6 if lod == 0 else 3
                for i in range(nseg + 1):
                    a = math.pi * i / nseg
                    poly.append((hx - math.cos(a) * hr, sgn * math.sin(a) * hr))
            poly.append((w, 0.0))
            poly.append((w, sgn * 0.17))
            poly.append((-w, sgn * 0.17))
            if sgn > 0:
                poly = list(reversed(poly))
            fr = Frame((cx, cy + 0.3, base + z0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
            g.prism(poly, fr, -0.06, 0.06, "Madera")
        if lod == 0:
            for sx in (-1, 1):
                bx(g, cx + sx * 0.66 - 0.02, cx + sx * 0.66 + 0.02, cy + 0.23, cy + 0.37, base + 1.22, base + 1.62,
                   "Hierro")
            g.bbox(V((cx + 0.62, cy + 0.2, base + 1.35)), V((cx + 0.72, cy + 0.24, base + 1.47)), "Hierro", 0.01)
        return g

    sitter("C03_Picota", picota, "picota")
    SITS["C03_Picota"] = (V((X(7.4), yc - 0.15, FL + 1.35)), 90, "foso_picota", "stand")

    def cepos(lod):
        g = Geo()
        cx, cy = X(9.9), yc + 1.5
        q = 0.015 if lod == 0 else 0
        bx(g, cx - 0.9, cx + 0.9, cy - 0.15, cy + 0.15, FL + 0.38, FL + 0.46, "Madera", q)  # banco
        for sx in (-0.8, 0.8):
            bx(g, cx + sx - 0.05, cx + sx + 0.05, cy - 0.12, cy + 0.12, FL, FL + 0.38, "Madera", q)
        fy = cy - 0.75
        for z0, z1 in ((FL, FL + 0.2), (FL + 0.2, FL + 0.38)):
            bx(g, cx - 0.7, cx + 0.7, fy - 0.06, fy + 0.06, z0 + 0.003, z1, "Madera", q)
        if lod == 0:
            for hx in (-0.18, 0.18):
                g.cyl(V((cx + hx, fy - 0.07, FL + 0.2)), V((cx + hx, fy + 0.07, FL + 0.2)), 0.05, 8, "Suelo",
                      caps=(True, True))
            for sx in (-0.72, 0.72):
                bx(g, cx + sx - 0.02, cx + sx + 0.02, fy - 0.07, fy + 0.07, FL + 0.1, FL + 0.32, "Hierro")
        return g

    sitter("C03_Cepos", cepos, "cepos")
    SITS["C03_Cepos"] = (V((X(9.9), yc + 1.5, FL + 0.9)), -90, "foso_cepos", "sit")

    def atrezzo(lod):
        g = Geo()
        r = rng("cepo-atrezzo")
        # rueda de tormento colgada del muro exterior
        wheel(g, V((X(XI - 0.18), yc - 1.2, FL + 2.4)), V((-s, 0, 0)), V((0, 0, 1)), 0.75, lod, 10)
        if lod == 0:
            g.link(V((X(XI - 0.18), yc - 1.2, FL + 2.4)), V((0, 0, 1)), V((0, 1, 0)), 0.76, 0.76, 0.03, 28, 4,
                   "Hierro")
            g.cyl(V((X(XI), yc - 1.2, FL + 2.4)), V((X(XI - 0.3), yc - 1.2, FL + 2.4)), 0.05, 6, "Hierro")
            ropa_pile(g, (X(10.6), yc - 2.0, FL + 0.02), 3, r, lod, 0.4)
            for i in range(3):
                skull(g, V((X(r.uniform(10.2, 11.2)), yc + r.uniform(-0.8, 0.0), FL + 0.09)), lod, r,
                      V((-s, r.uniform(-0.5, 0.5), 0)))
        return g

    deco("C03_Atrezzo", atrezzo)
    wall_torch("C03_Antorcha", (X(XI), yc + 0.6, FL + 2.3), (-s, 0, 0), "El Cepo")


def make_cisterna():
    s, k = -1, 3
    X = lambda x: s * x
    yc = cell_center(k)
    tx0, tx1 = 8.2, 11.5          # pila de agua de mar contra el muro exterior
    ty0, ty1 = yc - 1.5, yc + 1.5
    wall = 0.28
    H = FL + 0.95
    piv = V((X(7.3), yc, FL + 1.75))   # eje de la silla de inmersión

    def cisterna(lod):
        g = Geo()
        a, b = sorted((X(tx0), X(tx1)))
        q = 0.025 if lod == 0 else 0
        if lod == 3:
            bx(g, a, b, ty0, ty1, FL, H, "Piedra", skip=("-z",))
            return g
        for (xa, xb, ya, yb) in ((a, b, ty0, ty0 + wall), (a, b, ty1 - wall, ty1), (a, a + wall, ty0 + wall, ty1 - wall),
                                 (b - wall, b, ty0 + wall, ty1 - wall)):
            bx(g, xa, xb, ya, yb, FL, H, "Piedra", q, skip=("-z",))
        bx(g, a + wall, b - wall, ty0 + wall, ty1 - wall, FL - 0.4, FL - 0.3, "Piedra", skip=("-z",))
        # caballete de la grúa
        for sy in (-1, 1):
            g.cyl(piv + V((0, sy * 0.45, -1.75)), piv + V((0, sy * 0.12, 0.05)), 0.07, n_(8, lod, 4), "Madera")
            g.cyl(piv + V((-s * 0.6, sy * 0.45, -1.75)), piv + V((0, sy * 0.12, 0.0)), 0.06, n_(8, lod, 4), "Madera")
        g.cyl(piv + V((0, -0.2, 0)), piv + V((0, 0.2, 0)), 0.035, 8, "Hierro")
        return g

    reg("C04_Cisterna", "estructura", cisterna,
        lambda: [pbox(X(tx0), X(tx1), ty0, ty1, FL - 0.3, H), pbox(X(7.3) - 0.35, X(7.3) + 0.35, yc - 0.5, yc + 0.5, FL,
                                                                     FL + 1.8)], BIG)

    def agua(lod):
        g = Geo()
        a, b = sorted((X(tx0 + wall), X(tx1 - wall)))
        z = H - 0.18
        g.face([V((a, ty0 + wall, z)), V((b, ty0 + wall, z)), V((b, ty1 - wall, z)), V((a, ty1 - wall, z))], "Agua",
               (0, 0, 1))
        if lod == 0:  # fondo oscuro para que el agua tenga profundidad
            g.face([V((a, ty0 + wall, FL - 0.29)), V((b, ty0 + wall, FL - 0.29)), V((b, ty1 - wall, FL - 0.29)),
                    V((a, ty1 - wall, FL - 0.29))], "Agua", (0, 0, 1))
        return g

    reg("C04_Agua", "agua", agua, bbox_phys(agua), STD, role="agua")

    def silla(lod):
        """Brazo basculante con la silla en el extremo sobre el agua (gira alrededor de `piv`)."""
        g = Geo()
        q = 0.015 if lod == 0 else 0
        arm_a = piv + V((-s * 1.6, 0, 0))      # contrapeso (lado patio)
        arm_b = piv + V((s * 2.6, 0, 0))       # silla (sobre el agua)
        g.cyl(arm_a, arm_b, 0.075, n_(8, lod, 4), "Madera")
        g.link(piv, V((0, 0, 1)), V((1, 0, 0)), 0.08, 0.08, 0.02, 10, 4, "Hierro")
        bx(g, *sorted((arm_a.x - 0.25, arm_a.x + 0.25)), yc - 0.25, yc + 0.25, arm_a.z - 0.55, arm_a.z - 0.05,
           "Piedra", q)  # contrapeso
        g.cyl(arm_a, arm_a - V((0, 0, 0.1)), 0.05, 6, "Hierro")
        # silla colgada con cadenas
        seat = arm_b + V((0, 0, -0.55))
        for sx in (-1, 1):
            for sy in (-1, 1):
                a = arm_b + V((0, 0, -0.08))
                b = seat + V((sx * 0.25, sy * 0.25, 0.4))
                if lod <= 1:
                    chains_from(g, a, b, lod, 0.0)
        bx(g, seat.x - 0.28, seat.x + 0.28, yc - 0.28, yc + 0.28, seat.z, seat.z + 0.06, "Madera", q)
        bx(g, seat.x + s * 0.24, seat.x + s * 0.3, yc - 0.28, yc + 0.28, seat.z, seat.z + 0.9, "Madera", q)
        for sy in (-1, 1):
            bx(g, seat.x - 0.28, seat.x + 0.28, yc + sy * 0.28 - 0.03, yc + sy * 0.28 + 0.03, seat.z + 0.3,
               seat.z + 0.36, "Madera")
            bx(g, seat.x - 0.28, seat.x - 0.22, yc + sy * 0.28 - 0.03, yc + sy * 0.28 + 0.03, seat.z, seat.z + 0.36,
               "Madera")
        if lod == 0:
            g.link(seat + V((0, 0, 0.45)), V((0, 1, 0)), V((0, 0, 1)), 0.32, 0.06, 0.012, 14, 4, "Tela")  # correa
        return g

    pc = reg("C04_Silla", "mueble", proxy(silla), bbox_phys(proxy(silla)), SMALL, role="silla")
    SITS["C04_Silla"] = (piv + V((s * 2.6, 0, -0.55 + 0.45)), 0 if s < 0 else 180, "foso_silla", "sit")
    pc.pivot = piv
    wall_torch("C04_Antorcha", (X(5.0), YP[4] - PT, FL + 2.3), (0, -1, 0), "La Cisterna")

    def atrezzo(lod):
        g = Geo()
        r = rng("cisterna-atrezzo")
        # el que no aguantó: esqueleto encadenado al muro, sentado junto a la pila
        sk = skeleton("sentado", lod, r)
        g.extend(xf(sk, (X(6.0), YP[3] + PT + 0.05, FL), rz=0.0))
        for sx in (-0.3, 0.3):
            bottom, rc, u = wall_anchor(g, (X(6.0 + sx), YP[3] + PT, FL + 0.95), V((0, 1, 0)), V((0, 0, 1)), min(lod, 2))
            if lod <= 1:
                chains_from(g, bottom, V((X(6.0 + sx * 0.8), YP[3] + PT + 0.35, FL + 0.35)), lod, 0.1)
        if lod == 0:
            ropa_pile(g, (X(4.9), YP[3] + PT + 0.4, FL + 0.02), 3, r, lod, 0.25)
        return g

    deco("C04_Atrezzo", atrezzo)


def make_perrera():
    """C05+C06: la única celda de estancia. Aquí los cautivos viven como perros."""
    s = 1
    X = lambda x: s * x
    y0, y1 = YP[0] + PT, YP[2] - PT

    for i, yy in enumerate((y0 + 1.4, (y0 + y1) / 2, y1 - 1.4)):
        def jaula(lod, yy=yy, i=i):
            g = Geo()
            r = rng(f"jaula-{i}")
            cx = X(10.6)
            L, W, H = 1.5, 1.0, 1.05
            x0, x1 = cx - W / 2, cx + W / 2
            q = 0.012 if lod == 0 else 0
            for xx in (x0, x1):
                for y in (yy - L / 2, yy + L / 2):
                    bx(g, xx - 0.04, xx + 0.04, y - 0.04, y + 0.04, FL, FL + H, "Madera", q)
            for z in (FL + 0.05, FL + H - 0.04):
                for xx in (x0, x1):
                    bx(g, xx - 0.035, xx + 0.035, yy - L / 2, yy + L / 2, z - 0.035, z + 0.035, "Madera")
                for y in (yy - L / 2, yy + L / 2):
                    bx(g, x0, x1, y - 0.035, y + 0.035, z - 0.035, z + 0.035, "Madera")
            nb = n_(9, lod, 3)
            for xx in (x0, x1):           # barrotes laterales
                for j in range(nb):
                    y = yy - L / 2 + (j + 1) * L / (nb + 1)
                    bar(g, V((xx, y, FL + 0.05)), V((xx, y, FL + H - 0.04)), 0.013, 4 if lod == 0 else 3, "Hierro")
            for y in (yy + L / 2,):
                for j in range(n_(6, lod, 2)):
                    xx = x0 + (j + 1) * W / (n_(6, lod, 2) + 1)
                    bar(g, V((xx, y, FL + 0.05)), V((xx, y, FL + H - 0.04)), 0.013, 4 if lod == 0 else 3, "Hierro")
            bx(g, x0 - 0.05, x1 + 0.05, yy - L / 2 - 0.05, yy + L / 2 + 0.05, FL + H, FL + H + 0.05, "Madera", q)
            # puertecilla abierta (frente hacia el patio = -X)
            dp = Geo()
            dp.box(V((0, 0, 0)), V((0.03, 0.75, 0.85)), "Hierro", skip=("-x", "+x") if lod else ())
            g.extend(xf(dp, (x0 - 0.02, yy - L / 2 + 0.05, FL + 0.1), rz=-1.9))
            # placa del nombre y paja dentro
            bx(g, x0 - 0.06, x0 - 0.02, yy - 0.3, yy + 0.3, FL + H - 0.2, FL + H - 0.02, "Madera", q)
            g.blob((cx, yy, FL), 0.38, 0.6, 0.12, n_(10, lod, 5), 2 if lod == 0 else 1, "Paja", r, 0.2)
            if lod == 0:
                garment(g, V((cx - 0.1, yy + 0.2, FL + 0.11)), r.uniform(0, 6), "calzon", r, lod)
                g.link(V((cx + 0.2, yy - 0.3, FL + 0.03)), V((1, 0, 0)), V((0, 1, 0)), 0.13, 0.13, 0.02, 14, 4,
                       "Tela")   # collar de cuero
            return g

        sitter(f"C05_Caseta_{i + 1}", jaula, "caseta")
        SITS[f"C05_Caseta_{i + 1}"] = (V((X(10.6), yy, FL + 0.4)), 180, "foso_perro", "sleep")

    def comederos(lod):
        g = Geo()
        r = rng("comederos")
        wy = y1  # cara del divisorio norte (mira al sur)
        # barra de trailla a lo largo del muro con anillas y cadenas con collar
        rail_z = FL + 1.0
        g.cyl(V((X(4.3), wy - 0.12, rail_z)), V((X(9.7), wy - 0.12, rail_z)), 0.025, n_(8, lod, 4), "Hierro")
        for x in (4.3, 7.0, 9.7):
            bx(g, X(x) - 0.04, X(x) + 0.04, wy - 0.14, wy, rail_z - 0.04, rail_z + 0.04, "Hierro")
        if lod <= 1:
            for j, x in enumerate((5.0, 6.2, 7.6, 8.9)):
                c = V((X(x), wy - 0.12, rail_z))
                g.link(c, V((0, 0, 1)), V((1, 0, 0)), 0.05, 0.05, 0.012, 10, 4, "Hierro")
                end = V((X(x + r.uniform(-0.3, 0.3)), wy - 0.5 - r.uniform(0, 0.5), FL + 0.03))
                pts = [c - V((0, 0, 0.05))]
                for t in range(1, 9):
                    tt = t / 8
                    p = pts[0].lerp(end, tt)
                    p.z = max(FL + 0.03, (c.z - 0.05) * (1 - tt) ** 1.5 + (FL + 0.03) * (1 - (1 - tt) ** 1.5))
                    pts.append(p)
                chain(g, pts, 0.05, 0.03, 0.01, lod, r, FL)
                collar(g, end + V((0, -0.15, -0.01)), 0.13, 0.02, lod)
        # comedero corrido y escudillas
        bx(g, X(4.2), X(6.4), wy - 0.55, wy - 0.05, FL, FL + 0.3, "Piedra", 0.02 if lod == 0 else 0)
        if lod == 0:
            bx(g, X(4.3), X(6.3), wy - 0.48, wy - 0.12, FL + 0.18, FL + 0.31, "Suelo")
        for j in range(5 if lod <= 1 else 2):
            c = V((X(7.0 + j * 0.62), wy - 0.45, FL))
            g.cyl(c, c + V((0, 0, 0.09)), 0.12, n_(12, lod, 5), "Hierro", caps=(True, False), r1=0.15)
            if lod == 0:
                g.cyl(c + V((0, 0, 0.06)), c + V((0, 0, 0.015)), 0.14, 12, "Suelo", caps=(True, False), r1=0.125)
        return g

    deco("C05_Comederos", comederos, "comederos")

    def ropa(lod):
        """La ropa interior de soldados y esclavos que arrojan a la perrera para humillar."""
        g = Geo()
        r = rng("perrera-ropa")
        wy = y0
        for (x, y, n) in ((5.0, wy + 0.6, 7), (7.6, wy + 0.5, 6), (9.4, wy + 0.7, 5)):
            ropa_pile(g, (X(x), y, FL + 0.02), n if lod == 0 else max(n // 3, 2), r, lod, 0.5)
        if lod <= 1:
            g.blob((X(6.4), wy + 0.65, FL), 0.9, 0.5, 0.18, n_(12, lod, 5), 2 if lod == 0 else 1, "Paja", r, 0.25)
        if lod == 0:
            sk = skeleton("tirado", lod, r)
            g.extend(xf(sk, (X(8.6), wy + 0.75, FL), rz=-1.57))
        return g

    deco("C05_Ropa", ropa, "ropa")
    hanging_lantern("C05_Farol", V((X(7.6), (y0 + y1) / 2, CROWN + 0.15)))


def make_jaulas():
    s, k = 1, 2
    X = lambda x: s * x
    yc = cell_center(k)
    top = VS + R_VAULT - 0.02

    for i, (x, y) in enumerate(((7.0, yc - 1.1), (9.0, yc + 1.0))):
        def gibbet(lod, x=x, y=y, i=i):
            g = Geo()
            r = rng(f"gibbet-{i}")
            c = V((X(x), y, FL + 0.9))
            R, H = 0.42, 2.05
            nb = n_(12, lod, 5)
            for j in range(nb):
                a = 2 * math.pi * j / nb
                d = V((math.cos(a), math.sin(a), 0))
                pts = [c + d * R, c + d * R + V((0, 0, H * 0.8)), c + d * (R * 0.6) + V((0, 0, H * 0.95)),
                       c + V((0, 0, H)) + d * 0.08]
                g.sweep(pts if lod == 0 else [pts[0], pts[1], pts[3]], 0.012, 4 if lod == 0 else 3, "Hierro", caps=False)
            for z in (0.0, 0.9, H * 0.8):
                g.link(c + V((0, 0, z)), V((1, 0, 0)), V((0, 1, 0)), R, R, 0.02, n_(20, lod, 8), 3, "Hierro")
            g.cyl(c, c + V((0, 0, 0.03)), R, n_(16, lod, 6), "Hierro")
            # cadena hasta la bóveda
            a_c = 0.06
            p = c + V((0, 0, H + 0.08))
            pts = [p + V((0, 0, t * (top - p.z) / 20)) for t in range(21)]
            chain(g, pts, a_c, 0.035, 0.012, lod, r, -10)
            if i == 1:  # un viejo inquilino que nadie bajó
                sk = skeleton("colgado", lod, r)
                g.extend(xf(sk, c + V((0, 0, 0.03)), rz=0.7, scale=0.95))
            return g

        sitter(f"C07_Jaula_{i + 1}", gibbet, "jaula", lod_map=SMALL)
        SITS[f"C07_Jaula_{i + 1}"] = (V((X(x), y, FL + 1.95)), 0, "foso_jaula", "stand")

    def torno(lod):
        g = Geo()
        r = rng("jaulas-torno")
        wy = YP[2] + PT
        c = V((X(5.2), wy + 0.35, FL + 1.1))
        for sx in (-0.45, 0.45):
            bx(g, c.x + sx - 0.07, c.x + sx + 0.07, wy, wy + 0.5, FL, FL + 1.4, "Madera", 0.015 if lod == 0 else 0)
        g.cyl(c - V((0.5, 0, 0)), c + V((0.5, 0, 0)), 0.14, n_(12, lod, 6), "Madera")
        wheel(g, c + V((0.6, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.35, lod, 6, handles=True)
        if lod <= 1:
            for t in range(-3, 4):
                g.link(c + V((t * 0.11, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.155, 0.155, 0.012, 12, 3, "Hierro")
            chains_from(g, c + V((0.2, 0.1, 0.14)), c + V((0.6, 0.35, -1.05)), lod, 0.1)
        if lod == 0:
            for j in range(3):
                skull(g, V((X(r.uniform(6.0, 7.5)), wy + r.uniform(0.2, 0.6), FL + 0.09)), lod, r,
                      V((r.uniform(-1, 1), 1, 0)))
            for j in range(6):  # huesos sueltos
                p = V((X(r.uniform(6.0, 7.8)), wy + r.uniform(0.2, 0.7), FL + 0.025))
                a = r.uniform(0, 3.14)
                d = V((math.cos(a), math.sin(a), 0)) * r.uniform(0.12, 0.22)
                g.cyl(p - d, p + d, 0.018, 5, "Hueso", caps=(True, True))
        return g

    deco("C07_Torno", torno, "torno_jaulas")
    wall_torch("C07_Antorcha", (X(XI), yc - 0.2, FL + 2.3), (-s, 0, 0), "Las Jaulas")


def make_mastil():
    s, k = 1, 3
    X = lambda x: s * x
    yc = cell_center(k)

    def mastil(lod):
        g = Geo()
        r = rng("mastil")
        c = V((X(7.4), yc, FL))
        H = 3.4
        n = n_(12, lod, 5)
        g.cyl(c - V((0, 0, 0.4)), c + V((0, 0, H)), 0.2, n, "Madera", caps=(False, False), r1=0.16)
        if lod == 0:  # remate astillado
            for j in range(9):
                a = 2 * math.pi * j / 9
                d = V((math.cos(a), math.sin(a), 0))
                base = c + V((0, 0, H)) + d * 0.12
                g.cyl(base - d * 0.05, base + V((0, 0, r.uniform(0.15, 0.5))) - d * 0.02, 0.05, 3, "Madera",
                      caps=(False, False), r1=0.002)
        for z in (0.4, 1.2, 2.6) if lod <= 1 else (1.2,):
            g.cyl(c + V((0, 0, z)), c + V((0, 0, z + 0.07)), 0.205 - z * 0.012, n, "Hierro", caps=(False, False))
        # verga rota y argolla con grilletes
        g.cyl(c + V((-0.9, 0, 2.95)), c + V((0.6, 0, 2.95)), 0.08, n_(8, lod, 4), "Madera")
        ring_c = c + V((0, -0.24, 2.3))
        g.link(ring_c, V((0, 0, 1)), V((1, 0, 0)), 0.09, 0.09, 0.02, 14 if lod == 0 else 6, 4 if lod == 0 else 3,
               "Hierro")
        if lod <= 1:
            for sx in (-0.2, 0.2):
                chains_from(g, ring_c - V((0, 0, 0.09)), ring_c + V((sx, -0.15, -0.45)), lod, 0.05)
                g.link(ring_c + V((sx, -0.15, -0.55)), V((0, 0, 1)), V((0, 1, 0)), 0.07, 0.07, 0.014, 12, 4, "Tela")
        # cabos enrollados al pie
        for j in range(4 if lod == 0 else 2):
            g.link(c + V((0, 0, 0.04 + j * 0.035)), V((1, 0, 0)), V((0, 1, 0)), 0.42 - j * 0.04, 0.42 - j * 0.04,
                   0.03, n_(20, lod, 8), 4 if lod == 0 else 3, "Paja")
        return g

    sitter("C08_Mastil", mastil, "mastil")
    SITS["C08_Mastil"] = (V((X(7.4), yc - 0.55, FL + 1.0)), 90, "foso_mastil", "stand")

    def atrezzo(lod):
        g = Geo()
        r = rng("mastil-atrezzo")
        wy = YP[4] - PT
        # gatos de nueve colas en un tablero
        bx(g, X(5.0), X(6.6), wy - 0.06, wy, FL + 1.4, FL + 2.2, "Madera", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for j in range(3):
                h0 = V((X(5.3 + j * 0.5), wy - 0.1, FL + 2.05))
                g.cyl(h0, h0 - V((0, 0, 0.3)), 0.022, 6, "Tela")
                for t in range(9 if lod == 0 else 3):
                    a = (t - 4) * 0.035
                    pts = [h0 - V((0, 0, 0.3)), h0 + V((a, -0.02 - abs(a) * 0.3, -0.62)),
                           h0 + V((a * 1.6, -0.03, -0.95))]
                    g.sweep(pts, 0.004, 3, "Tela", caps=False)
        # barril de sal para las heridas (costumbre de a bordo) y cubo de salmuera
        bc = V((X(10.6), wy - 0.6, FL))
        prof = [(0.0, 0.27), (0.45, 0.33), (0.9, 0.27)] if lod <= 1 else [(0.0, 0.28), (0.9, 0.28)]
        nn = n_(14, lod, 6)
        rings = [[bc + V((math.cos(2 * math.pi * j / nn) * rr, math.sin(2 * math.pi * j / nn) * rr, h))
                  for j in range(nn)] for h, rr in prof]
        for i in range(len(rings) - 1):
            for j in range(nn):
                j2 = (j + 1) % nn
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Madera", bc + V((0, 0, 0.45)))
        g.face(rings[-1], "Hueso", (0, 0, 1))   # sal blanca
        if lod == 0:
            for h in (0.1, 0.8):
                g.cyl(bc + V((0, 0, h - 0.02)), bc + V((0, 0, h + 0.02)), 0.3, nn, "Hierro", caps=(False, False))
            ropa_pile(g, (X(9.7), wy - 0.55, FL + 0.02), 4, r, lod, 0.3)
        return g

    deco("C08_Atrezzo", atrezzo)
    wall_torch("C08_Antorcha", (X(XI), yc - 1.6, FL + 2.3), (-s, 0, 0), "El Mástil")


# ================================================================== patio
def make_nave():
    for k in range(4):
        def suelo(lod, k=k):
            g = flagstones(f"nave-{k}", -NX, NX, YP[k], YP[k + 1], lod, channel=True, grate_y=cell_center(k))
            if lod == 0:  # cascotes y lascas de losas rotas
                r = rng(f"nave-rotas-{k}")
                for i in range(4):
                    p = V((r.choice((-1, 1)) * r.uniform(0.6, 2.8), r.uniform(YP[k] + 0.3, YP[k + 1] - 0.3), FL + 0.002))
                    g.blob(p, r.uniform(0.03, 0.08), r.uniform(0.03, 0.07), r.uniform(0.02, 0.04), 5, 1, "Piedra", r, 0.3)
            return g

        reg(f"P{k + 1}_Suelo", "estructura", suelo, lambda k=k: [pbox(-NX, NX, YP[k], YP[k + 1], FL - 0.3, FL)], BIG)

    def agua(lod):
        """Canal de agua de mar que sube y baja con la marea (script)."""
        g = Geo()
        z = FL - 0.07
        g.face([V((-0.21, YP[0], z)), V((0.21, YP[0], z)), V((0.21, YP[4], z)), V((-0.21, YP[4], z))], "Agua", (0, 0, 1))
        return g

    reg("P_Agua", "agua", agua, bbox_phys(agua), STD, role="marea")

    for j in range(5):
        def viga(lod, j=j):
            g = Geo()
            yj = YP[j]
            bx(g, -NX - 0.25, NX + 0.25, yj - 0.17, yj + 0.17, 6.30, 6.74, "Madera", 0.03 if lod == 0 else 0,
               skip=("-x", "+x", "+z") if lod >= 2 else ())
            if lod <= 1:
                for s in (-1, 1):
                    g.prism([(0.0, 5.7), (0.46, 6.18), (0.46, 6.30), (0.0, 6.30)],
                            Frame((s * NX, 0, 0), (-s, 0, 0), (0, 0, 1), (0, 1, 0)), yj - 0.23, yj + 0.23, "Piedra")
            if lod == 0:
                for s in (-1, 1):
                    for xx in (s * (NX - 0.55), s * (NX - 0.75)):
                        bx(g, xx - 0.035, xx + 0.035, yj - 0.18, yj + 0.18, 6.29, 6.75, "Hierro")
            return g

        reg(f"T{j}_Viga", "deco", viga, bbox_phys(viga), BIG)

    def ajusticiado(lod):
        """El aviso de la entrada: un ajusticiado colgado de la segunda viga, entre ganchos de carnicero."""
        g = Geo()
        r = rng("ajusticiado")
        yj = YP[1]
        sk = skeleton("colgado", lod, r)
        g.extend(xf(sk, (0.9, yj, 3.4), rz=0.4))
        chain(g, [V((0.9, yj, 6.3)) - V((0, 0, t * 0.11)) for t in range(12)], 0.05, 0.03, 0.01, lod, r, -10)
        for xx in (-0.4, 2.0):
            top = V((xx, yj, 6.3))
            chain(g, [top - V((0, 0, t * 0.06)) for t in range(16)], 0.045, 0.028, 0.009, lod, r, -10)
            h = top - V((0, 0, 0.98))
            g.sweep([h, h - V((0, 0, 0.12)), h + V((0.06, 0, -0.2)), h + V((0.1, 0, -0.12))], 0.01, 4, "Hierro")
        return g

    deco("P_Ajusticiado", ajusticiado)

    for j in (1, 2, 3):
        hanging_lantern(f"T{j}_Farol", V((-0.2 if j != 1 else -1.3, YP[j], 6.30)))
    for j in range(5):
        for s in (-1, 1):
            wall_torch(f"A{j}{'O' if s < 0 else 'E'}_Antorcha", (s * NX, YP[j], FL + 2.25), (-s, 0, 0))


# ================================================================== cuerpo de guardia y puerta
YF0, YF1 = -16.0, -15.2
YT0, YT1 = -18.0, -14.4
TX0, TX1 = 2.0, 6.0


def make_entrance():
    for s in (-1, 1):
        S = "O" if s < 0 else "E"
        X = lambda x, s=s: s * x
        inner = flipx(("-x",), s)[0]

        def muro_frontal(lod, s=s, X=X):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            sk = ("-z", flipx(("-x",), s)[0]) + (("+y",) if lod == 3 else ())
            bx(g, X(TX1), X(XO), YF0, YF1, zb, WT + (0.18 if lod else 0), "Piedra", skip=sk)
            if lod == 0:
                bx(g, X(TX1), X(XO + 0.07), YF0 - 0.07, YF1 + 0.05, WT, WT + 0.18, "Piedra", 0.03,
                   skip=(flipx(("-x",), s)[0],))
                g.prism([(YF0, ZB), (YF0 - 0.12, ZB), (YF0 - 0.12, FL + 0.35), (YF0, FL + 0.5)],
                        Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), *sorted((X(TX1), X(XO - 0.9))), "Piedra")
            bx(g, X(9.2 - 0.45), X(9.2 + 0.45), YF0 - 0.6, YF0, zb, FL + 5.0, "Piedra", 0.03 if lod == 0 else 0,
               skip=("-z", "+y"))
            if lod <= 1:
                g.prism([(YF0, FL + 5.0), (YF0 - 0.6, FL + 5.0), (YF0, FL + 6.3)],
                        Frame((0, 0, 0), (0, 1, 0), (0, 0, 1), (1, 0, 0)), *sorted((X(9.2 - 0.45), X(9.2 + 0.45))),
                        "Piedra")
            bx(g, X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, zb, FL + 5.4, "Piedra", 0.03 if lod == 0 else 0,
               skip=("-z",))
            return g

        reg(f"G_Muro_{S}", "estructura", muro_frontal,
            lambda X=X: [pbox(X(TX1), X(XO), YF0, YF1, ZB, WT + 0.18), pbox(X(XO - 0.9), X(XB), YF0 - 0.6, YF0 + 0.9, ZB,
                                                                          FL + 5.4),
                         pbox(X(8.75), X(9.65), YF0 - 0.6, YF0, ZB, FL + 5.0)], BIG)

        def lateral(lod, s=s, X=X, inner=inner):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(XI), X(XO), YF1, YP[0], zb, WT + 0.18, "Piedra",
               skip=("-z", "+y", "-y") + ((inner,) if lod == 3 else ()))
            bx(g, X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, zb, FL + 5.6, "Piedra", skip=("-z", inner))
            return g

        reg(f"V_Muro_{S}", "estructura", lateral,
            lambda X=X: [pbox(X(XI), X(XO), YF1, YP[0], ZB, WT + 0.18),
                         pbox(X(XO), X(XB), YP[0] - 0.45, YP[0] + 0.45, ZB, FL + 5.6)], BIG)

        def particion(lod, s=s, X=X):
            g = Geo()
            if lod == 3:
                bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, WT, WT + 0.18, "Piedra",
                   skip=("-z", "-x", "+x", "+y"))
                return g
            bx(g, X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT, "Piedra", skip=("-z", "-x", "+x"))
            bx(g, X(NX + FT - 0.05), X(XI), YP[0] - PT - 0.06, YP[0] + PT + 0.06, WT, WT + 0.18, "Piedra",
               0.03 if lod == 0 else 0)
            return g

        reg(f"V_Particion_{S}", "estructura", particion,
            lambda X=X: [pbox(X(NX + FT), X(XI), YP[0] - PT, YP[0] + PT, ZB, WT + 0.18)], BIG)

        def torre(lod, s=s, X=X):
            g = tower(lod, s, X, TX0, TX1, YT0, YT1)
            if lod <= 2:  # jambas de los dos arcos del paso (van con la torre: su casco no estrecha el paso)
                for (ya, yb_) in ((YT0, YT0 + 0.8), (YT1 - 0.8, YT1)):
                    bx(g, X(1.7), X(TX0), ya, yb_, ZB if lod <= 1 else FL, FL + 3.0, "Piedra",
                       skip=("-z", flipx(("+x",), s)[0]))
            if lod == 0:  # gorroneras de las hojas del portón (aquí, no en el arco: su casco bajaría al suelo)
                for z in (FL + 0.5, FL + 2.6):
                    bx(g, X(1.70), X(1.84), YT1, YT1 + 0.06, z - 0.05, z + 0.05, "Hierro")
            return g

        reg(f"G_Torre_{S}", "estructura", torre,
            lambda X=X: [pbox(X(TX0), X(TX1), YT0, YT1, ZB, 10.6), pbox(X(TX0), X(TX1 + 0.35), YT0 - 0.35, YT1, ZB,
                                                                        FL + 0.5),
                         pbox(X(TX0), X(TX1 + 0.2), YT0 - 0.2, YT1, ZB, FL + 1.1),
                         pbox(X(1.7), X(TX0), YT0, YT0 + 0.8, ZB, FL + 3.0), pbox(X(1.7), X(TX0), YT1 - 0.8, YT1, ZB,
                                                                                  FL + 3.0)], BIG)

    wall_torch("A0O_Antorcha_Vestibulo", (-7.7, YP[0] - PT, FL + 2.3), (0, -1, 0))
    wall_torch("A0E_Antorcha_Vestibulo", (7.7, YP[0] - PT, FL + 2.3), (0, -1, 0))

    for i, (x0, x1) in enumerate(((-XI, -4.0), (-4.0, 4.0), (4.0, XI))):
        reg(f"V_Suelo_{i + 1}", "estructura", lambda lod, x0=x0, x1=x1, i=i: flagstones(f"vest-{i}", x0, x1, YF1, YP[0], lod),
            lambda x0=x0, x1=x1: [pbox(x0, x1, YF1, YP[0], FL - 0.3, FL)], BIG)

    def paso(lod):
        g = flagstones("paso", -TX0, TX0, YT0, YF1, lod)
        c = 0.02 if lod == 0 else 0
        bx(g, -3.0, 3.0, -19.2, YT0, -0.4, 0.2, "Piedra", c, skip=("-z", "+y"))
        bx(g, -3.0, 3.0, -18.6, YT0, 0.2, FL, "Piedra", c, skip=("-z", "+y"))
        return g

    reg("G_Escalinata", "estructura", paso,
        lambda: [pbox(-TX0, TX0, YT0, YF1, FL - 0.3, FL), pbox(-3.0, 3.0, -19.2, YT0, -0.4, 0.2),
                 pbox(-3.0, 3.0, -18.6, YT0, 0.2, FL)], BIG)

    def cabeza(lod):
        """Todo lo que queda por encima del arranque de los arcos del paso (su casco no baja de 3,3 m)."""
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        sp, ra = 3.4, 0.62
        top = 9.6
        for fr_, spring in ((Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), FL + 2.9),
                            (Frame((0, YT1, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)), FL + 3.1)):
            arch_wall(g, fr_, -1.7, 1.7, 0.0, sp, ra, spring, spring, top, 0.8, n_side, "Piedra", skip_u0=True,
                      skip_u1=True, thr_top=None, front_only=(lod == 3), back=(lod == 0), top=(lod == 0))
            if lod == 0:
                voussoirs(g, fr_, 0.0, spring, sp, ra, 6, 0.6, 0.07, "Piedra")
        # macizos sobre las jambas, hasta arriba
        for s in (-1, 1):
            for (ya, yb_) in ((YT0, YT0 + 0.8), (YT1 - 0.8, YT1)):
                if lod < 3:
                    bx(g, s * 1.7, s * TX0, ya, yb_, FL + 3.0, top, "Piedra",
                       skip=("-z", "-y", "+y") if lod else ("-z",))
        if lod == 3:
            bx(g, -TX0, TX0, YT0, YT1, top, top + 1.0, "Piedra", skip=("-z", "-x", "+x"))
            return g
        fr_v = Frame((0, YT0 + 0.8, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        pts = pointed_arch(2 * TX0, 0.62, n_side)
        for i in range(len(pts) - 1):
            (a0, b0), (a1, b1) = pts[i], pts[i + 1]
            q = [fr_v.p(a0, FL + 3.0 + b0, 0), fr_v.p(a1, FL + 3.0 + b1, 0),
                 fr_v.p(a1, FL + 3.0 + b1, -(YF1 - YT0 - 0.8)), fr_v.p(a0, FL + 3.0 + b0, -(YF1 - YT0 - 0.8))]
            mid = sum(q, V()) / 4
            g.face(q, "Piedra", V((0, mid.y, FL + 1.0)) - mid)
        tp = pointed_arch(sp, ra, n_side)
        g.prism([(u, FL + 3.1 + v) for u, v in tp], Frame((0, YT1 - 0.35, 0), (1, 0, 0), (0, 0, 1), (0, 1, 0)),
                -0.06, 0.06, "Madera")
        bx(g, -TX0, TX0, YT0 - 0.3, YT0 + 0.05, top, top + 0.95, "Piedra", 0.03 if lod == 0 else 0)
        bx(g, -TX0, TX0, YF1 - 0.35, YF1, top, top + 0.95, "Piedra", 0.03 if lod == 0 else 0)
        bx(g, -TX0, TX0, YT0 + 0.05, YF1 - 0.35, top - 0.02, top, "Piedra")
        if lod == 0:
            hood(g, Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, FL + 2.9, sp, ra, 12, 0.74, 0.14,
                 0.12, "Piedra")
            for i in range(6):
                xx = -TX0 + 0.35 + i * (2 * TX0 - 0.7) / 5
                g.prism([(0.0, top - 0.42), (0.0, top), (0.3, top), (0.3, top - 0.16)],
                        Frame((0, YT0, 0), (0, -1, 0), (0, 0, 1), (1, 0, 0)), xx - 0.11, xx + 0.11, "Piedra")
            # escudo del señor con dos calaveras clavadas debajo
            g.prism([(-0.42, 7.0), (0.42, 7.0), (0.42, 7.75), (0.0, 7.95), (-0.42, 7.75)],
                    Frame((0, YT0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0)), 0.0, 0.09, "Piedra", caps=(False, True))
            r = rng("escudo")
            for sx in (-0.75, 0.75):
                g.cyl(V((sx, YT0, 6.75)), V((sx, YT0 - 0.25, 6.75)), 0.012, 4, "Hierro")
                skull(g, V((sx, YT0 - 0.16, 6.75)), lod, r, V((0, -1, 0)))
        return g

    reg("G_Arco", "estructura", cabeza,
        lambda: [pbox(-TX0, TX0, YT0, YT0 + 0.8, FL + 5.0, 9.6), pbox(-TX0, TX0, YT1 - 0.8, YT1, FL + 5.2, 9.6),
                 pbox(-TX0, TX0, YT0 + 0.8, YT1 - 0.8, FL + 5.45, 9.6)], BIG)

    def rastrillo(lod):
        g = Geo()
        y0, y1 = YT0 + 0.34, YT0 + 0.46
        x0, x1 = -1.76, 1.76
        zb, zt = FL + 0.14, FL + 5.6
        if lod == 3:
            for y in (y0, y1):
                g.face([V((x0, y, zb)), V((x1, y, zb)), V((x1, y, zt)), V((x0, y, zt))], "Madera",
                       (0, -1 if y == y0 else 1, 0))
            return g
        nv, nh = {0: (13, 10), 1: (9, 7)}.get(lod, (5, 4))
        for i in range(nv):
            x = x0 + 0.04 + (x1 - x0 - 0.08) * i / (nv - 1)
            bx(g, x - 0.045, x + 0.045, y0, y1, zb, zt, "Madera", 0.01 if lod == 0 else 0,
               skip=() if lod == 0 else ("-z", "+z"))
            if lod <= 1:
                g.cyl(V((x, (y0 + y1) / 2, zb)), V((x, (y0 + y1) / 2, FL)), 0.05, 4, "Hierro", caps=(True, False), r1=0.0,
                      phase=math.pi / 4)
        for j in range(nh):
            z = zb + 0.25 + (zt - zb - 0.35) * j / (nh - 1)
            bx(g, x0, x1, y0 - 0.04, y0, z - 0.045, z + 0.045, "Madera", 0.01 if lod == 0 else 0,
               skip=() if lod == 0 else ("-x", "+x", "+y"))
        return g

    reg("G_Rastrillo", "puerta", rastrillo, bbox_phys(rastrillo), BIG, role="rastrillo")
    for s in (-1, 1):
        S = "O" if s < 0 else "E"
        reg(f"G_Hoja_{S}", "puerta", lambda lod, s=s: gate_leaf(lod, s, YT1),
            lambda s=s: [pbox(s * 0.005, s * 1.76, YT1 + 0.01, YT1 + 0.13, FL + 0.03, FL + 3.08)], role="porton")

    def torno(lod):
        """Torno del rastrillo y campana de la leva, en el vestíbulo junto a la torre oeste."""
        g = Geo()
        c = V((-4.2, YT1 + 0.55, FL + 1.0))
        q = 0.015 if lod == 0 else 0
        for sx in (-0.55, 0.55):
            bx(g, c.x + sx - 0.08, c.x + sx + 0.08, c.y - 0.2, c.y + 0.2, FL, FL + 1.3, "Madera", q)
        g.cyl(c - V((0.5, 0, 0)), c + V((0.5, 0, 0)), 0.17, n_(14, lod, 6), "Madera")
        for sx in (-1, 1):
            wheel(g, c + V((sx * 0.68, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.38, lod, 6, handles=True)
        if lod <= 1:
            for t in range(-3, 4):
                g.link(c + V((t * 0.11, 0, 0)), V((1, 0, 0)), V((0, 0, 1)), 0.185, 0.185, 0.013, 12, 3, "Hierro")
            r = rng("torno-rastrillo")
            chain(g, [(c + V((0, -0.05, 0.18))).lerp(V((-1.2, YT1 + 0.02, 4.2)), t / 20) for t in range(21)], 0.05, 0.03,
                  0.011, lod, r, -10)
        # campana de la leva
        b = V((-5.6, YT1 + 0.55, FL))
        bx(g, b.x - 0.08, b.x + 0.08, b.y - 0.08, b.y + 0.08, FL, FL + 2.6, "Madera", q)
        bx(g, b.x - 0.08, b.x + 0.7, b.y - 0.07, b.y + 0.07, FL + 2.5, FL + 2.64, "Madera", q)
        bell_c = V((b.x + 0.55, b.y, FL + 2.5))
        prof = [(0.0, 0.05), (-0.06, 0.12), (-0.22, 0.15), (-0.38, 0.22), (-0.42, 0.25)]
        nn = n_(14, lod, 6)
        rings = [[bell_c + V((math.cos(2 * math.pi * j / nn) * rr, math.sin(2 * math.pi * j / nn) * rr, h))
                  for j in range(nn)] for h, rr in prof]
        for i in range(len(rings) - 1):
            for j in range(nn):
                j2 = (j + 1) % nn
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Hierro", bell_c - V((0, 0, 0.2)))
                g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Hierro", bell_c + V((0, 0, 3)))
        if lod <= 1:
            g.sweep([bell_c - V((0, 0, 0.05)), bell_c - V((0, 0, 0.38))], 0.02, 4, "Hierro")
            g.sweep([bell_c - V((0, 0, 0.38)), bell_c + V((0.05, 0, -1.4))], 0.012, 3, "Paja")
        return g

    sitter("G_Torno", torno, "torno", kind="mueble")
    SITS["G_Torno"] = (V((-4.2, YT1 + 0.0, FL + 1.0)), 90, "foso_torno", "stand")

    def mesa(lod):
        """Mesa de la guardia: dados, jarras, una daga clavada y el tablón de condenas encima."""
        g = Geo()
        r = rng("mesa")
        c = V((6.6, -13.4, FL))
        q = 0.02 if lod == 0 else 0
        bx(g, c.x - 1.0, c.x + 1.0, c.y - 0.45, c.y + 0.45, FL + 0.74, FL + 0.82, "Madera", q)
        for sx in (-0.8, 0.8):
            bx(g, c.x + sx - 0.06, c.x + sx + 0.06, c.y - 0.35, c.y + 0.35, FL, FL + 0.74, "Madera", q)
        for sy in (-0.8, 0.8):
            bx(g, c.x - 0.95, c.x + 0.95, c.y + sy - 0.15, c.y + sy + 0.15, FL + 0.42, FL + 0.48, "Madera", q)
            for sx in (-0.8, 0.8):
                bx(g, c.x + sx - 0.05, c.x + sx + 0.05, c.y + sy - 0.1, c.y + sy + 0.1, FL, FL + 0.42, "Madera")
        if lod <= 1:
            top = FL + 0.82
            for i in range(3):  # jarras
                p = V((c.x - 0.6 + i * 0.5 + r.uniform(-0.1, 0.1), c.y + r.uniform(-0.25, 0.25), top))
                g.cyl(p, p + V((0, 0, 0.16)), 0.05, n_(10, lod, 5), "Madera", caps=(True, False), r1=0.055)
                if lod == 0:
                    g.link(p + V((0.065, 0, 0.08)), V((0, 0, 1)), V((1, 0, 0)), 0.04, 0.03, 0.008, 8, 3, "Madera")
            for i in range(2):  # dados
                p = V((c.x + 0.2 + i * 0.08, c.y + 0.1, top))
                g.bbox(p, p + V((0.03, 0.03, 0.03)), "Hueso", 0.004 if lod == 0 else 0)
            # daga clavada
            dp = V((c.x + 0.6, c.y - 0.1, top))
            g.prism([(-0.015, 0.0), (0.015, 0.0), (0.0, -0.2)], Frame(dp + V((0, 0, 0.2)), (1, 0, 0), (0, 0, 1),
                                                                      (0, 1, 0)), -0.003, 0.003, "Hierro")
            g.cyl(dp + V((0, 0, 0.2)), dp + V((0, 0, 0.32)), 0.014, 6, "Tela")
            bx(g, dp.x - 0.05, dp.x + 0.05, dp.y - 0.008, dp.y + 0.008, dp.z + 0.19, dp.z + 0.21, "Hierro")
            # vela
            g.cyl(V((c.x - 0.9, c.y + 0.3, top)), V((c.x - 0.9, c.y + 0.3, top + 0.12)), 0.03, 6, "Paja")
            g.flame(V((c.x - 0.9, c.y + 0.3, top + 0.12)), 0.06, 0.012, 4, "Llama", r)
        return g

    sitter("V_Mesa", mesa, "mesa")
    SITS["V_Mesa"] = (V((6.6, -13.4 - 0.8, FL + 0.9)), 90, "foso_guardia", "sit")

    def atrezzo_o(lod):
        g = Geo()
        r = rng("vest-o")
        wy = YF1  # cara interior del muro frontal (mira al norte)
        # tablero de llaves: una por sala
        bx(g, -9.9, -8.5, wy, wy + 0.05, FL + 1.5, FL + 2.3, "Madera", 0.015 if lod == 0 else 0)
        if lod <= 1:
            for i in range(8):
                x = -9.75 + i * 0.16
                g.cyl(V((x, wy + 0.05, FL + 2.15)), V((x, wy + 0.1, FL + 2.15)), 0.007, 4, "Hierro")
                key = [V((x, wy + 0.09, FL + 2.12)), V((x, wy + 0.09, FL + 1.85))]
                g.sweep(key, 0.008, 3, "Hierro")
                g.link(V((x, wy + 0.09, FL + 2.14)), V((0, 0, 1)), V((1, 0, 0)), 0.025, 0.025, 0.005, 8, 3, "Hierro")
                bx(g, x, x + 0.04, wy + 0.085, wy + 0.095, FL + 1.85, FL + 1.9, "Hierro")
        # armero: picas y alfanjes
        bx(g, -11.0, -10.2, wy + 0.05, wy + 0.35, FL, FL + 0.12, "Madera")
        bx(g, -11.0, -10.2, wy + 0.05, wy + 0.12, FL + 1.6, FL + 1.7, "Madera")
        for i in range(3 if lod <= 1 else 1):
            x = -10.9 + i * 0.3
            g.cyl(V((x, wy + 0.2, FL + 0.12)), V((x, wy + 0.1, FL + 2.5)), 0.018, 5, "Madera")
            g.prism([(-0.035, 0.0), (0.035, 0.0), (0.0, 0.3)], Frame(V((x, wy + 0.1, FL + 2.5)), (1, 0, 0), (0, 0, 1),
                                                                     (0, 1, 0)), -0.005, 0.005, "Hierro")
        # ancla de un barco apresado, apoyada en el muro, con su cadena
        anc = Geo()
        anc.cyl(V((0, 0, 0.25)), V((0, 0, 2.1)), 0.06, n_(8, lod, 4), "Hierro")
        arc = [V((math.sin(a) * 0.65, 0, 0.25 + 0.65 - math.cos(a) * 0.65)) for a in [-1.3 + i * 0.325 for i in range(9)]]
        anc.sweep(arc, 0.055, n_(8, lod, 4), "Hierro")
        for e in (arc[0], arc[-1]):
            sg = 1 if e.x > 0 else -1
            anc.prism([(0, 0), (sg * 0.2, 0.18), (sg * 0.02, 0.32)], Frame(e - V((0, 0, 0.05)), (1, 0, 0), (0, 0, 1),
                                                                           (0, 1, 0)), -0.02, 0.02, "Hierro")
        anc.cyl(V((-0.55, 0, 1.85)), V((0.55, 0, 1.85)), 0.05, 6, "Madera")
        anc.link(V((0, 0, 2.22)), V((0, 0, 1)), V((1, 0, 0)), 0.12, 0.12, 0.025, 12, 4, "Hierro")
        g.extend(xf(anc, (-6.9, wy + 0.25, FL), rx=0.22))
        return g

    deco("V_Atrezzo_O", atrezzo_o, "tablero")

    def cesta(lod):
        """Cesto de la colada: la ropa interior sucia de la guardia, lista para arrojarla a la perrera."""
        g = Geo()
        r = rng("cesta")
        c = V((9.6, -13.0, FL))
        nn = n_(16, lod, 6)
        g.cyl(c, c + V((0, 0, 0.6)), 0.32, nn, "Paja", caps=(True, False), r1=0.4)
        g.cyl(c + V((0, 0, 0.58)), c + V((0, 0, 0.12)), 0.385, nn, "Paja", caps=(False, False), r1=0.315)
        g.link(c + V((0, 0, 0.6)), V((1, 0, 0)), V((0, 1, 0)), 0.4, 0.4, 0.025, nn, 3, "Paja")
        g.blob(c + V((0, 0, 0.5)), 0.36, 0.36, 0.2, n_(10, lod, 5), 2 if lod == 0 else 1, "Tela", r, 0.35)
        if lod <= 1:
            for i in range(6):
                a = r.uniform(0, 6.28)
                p = c + V((math.cos(a) * r.uniform(0.45, 0.7), math.sin(a) * r.uniform(0.45, 0.7), 0.02))
                garment(g, p, r.uniform(0, 6.28), ("calzon", "taparrabos", "camisa")[i % 3], r, lod)
            garment(g, c + V((0.1, 0.0, 0.66)), 0.5, "calzon", r, lod)
        return g

    deco("V_Cesta", cesta, "cesta")


# ================================================================== sala del trono
YN0, YB0, YB1 = YP[4] + PT, 15.2, 16.0



def estandarte(g, x0, lod):
    """Estandarte desgarrado del señor, colgado de una barra de hierro sobre el muro del fondo."""
    top = 6.6
    g.cyl(V((x0 - 0.75, YB0 - 0.15, top)), V((x0 + 0.75, YB0 - 0.15, top)), 0.03, 6, "Hierro")
    for sx in (-0.7, 0.7):
        g.cyl(V((x0 + sx, YB0, top)), V((x0 + sx, YB0 - 0.18, top)), 0.02, 4, "Hierro")
    nx, nz = (6, 10) if lod == 0 else (2, 3)
    w, h = 1.3, 3.4
    grid = []
    for i in range(nx + 1):
        row = []
        for j in range(nz + 1):
            u = -w / 2 + w * i / nx
            zz = top - 0.05 - h * j / nz
            if j == nz:
                zz += (0.25 if i % 2 else 0.0) + (0.1 if i in (0, nx) else 0)
            yy = YB0 - 0.15 - 0.04 * math.sin(i * 1.3 + j * 0.9)
            row.append(V((x0 + u, yy, zz)))
        grid.append(row)
    for i in range(nx):
        for j in range(nz):
            q = [grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]]
            g.face(q, "Tela", (0, -1, 0))
            g.face([p + V((0, 0.006, 0)) for p in q], "Tela", (0, 1, 0))


def make_trono():
    for s in (-1, 1):
        S = "O" if s < 0 else "E"
        X = lambda x, s=s: s * x
        inner = flipx(("-x",), s)[0]

        def lateral(lod, s=s, X=X, inner=inner):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(XI), X(XO), YP[4], YB1, zb, WT + 0.18, "Piedra", skip=("-z", "-y") + ((inner,) if lod == 3 else ()))
            bx(g, X(XO), X(XB), YB1 - 0.9, YB1, zb, FL + 5.4, "Piedra", skip=("-z", inner))
            return g

        reg(f"N_Muro_{S}", "estructura", lateral,
            lambda X=X: [pbox(X(XI), X(XO), YP[4], YB1, ZB, WT + 0.18), pbox(X(XO), X(XB), YB1 - 0.9, YB1, ZB, FL + 5.4)],
            BIG)

        def fondo(lod, s=s, X=X):
            g = Geo()
            zb = ZB if lod <= 1 else FL
            bx(g, X(4.5), X(XI), YB0, YB1, zb, WT + (0 if lod == 0 else 0.18), "Piedra",
               skip=("-z", "-x", "+x") + (("-y",) if lod == 3 else ()))
            if lod == 0:
                bx(g, X(4.5), X(XI), YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Piedra", 0.03, skip=("-x", "+x"))
            if lod <= 1:
                estandarte(g, s * 6.4, lod)
            return g

        reg(f"N_Fondo_{S}", "estructura", fondo, lambda X=X: [pbox(X(4.5), X(XI), YB0, YB1, ZB, WT + 0.18)], BIG)

    def fondo_c(lod):
        g = Geo()
        n_side = {0: 10, 1: 4, 2: 3, 3: 2}[lod]
        fr = Frame((0, YB0, 0), (1, 0, 0), (0, 0, 1), (0, -1, 0))
        spr = DAIS + 2.2
        arch_wall(g, fr, -4.5, 4.5, 0.0, 3.4, 0.6, spr, DAIS, WT, 0.5, n_side, "Piedra", skip_u0=True, skip_u1=True,
                  thr_top=None, front_only=(lod == 3), back=False, top=(lod == 0))
        bx(g, -4.5, 4.5, YB0 + 0.5, YB1, ZB if lod <= 1 else FL, WT + (0 if lod == 0 else 0.18), "Piedra",
           skip=("-z", "-x", "+x") + (("-y",) if lod == 3 else ()))
        bx(g, -1.7, 1.7, YB0, YB0 + 0.5, ZB, DAIS, "Piedra", skip=("-z", "-x", "+x", "+y", "-y") if lod else ("-z",))
        if lod == 0:
            bx(g, -4.5, 4.5, YB0 - 0.06, YB1 + 0.07, WT, WT + 0.18, "Piedra", 0.03, skip=("-x", "+x"))
            voussoirs(g, fr, 0.0, spr, 3.4, 0.6, 6, 0.5, 0.07, "Piedra")
            hood(g, fr, 0.0, spr, 3.4, 0.6, 12, 0.62, 0.14, 0.12, "Piedra")
            # timón del barco del señor dentro de la hornacina
            wheel(g, V((0, YB0 + 0.35, spr + 0.6)), V((0, 1, 0)), V((0, 0, 1)), 0.85, lod, 8, handles=True)
            g.cyl(V((0, YB0 + 0.5, spr + 0.6)), V((0, YB0 + 0.3, spr + 0.6)), 0.06, 8, "Hierro")
        return g

    reg("N_Fondo_C", "estructura", fondo_c,
        lambda: [pbox(-4.5, -1.7, YB0, YB1, ZB, WT + 0.18), pbox(1.7, 4.5, YB0, YB1, ZB, WT + 0.18),
                 pbox(-1.7, 1.7, YB0 + 0.5, YB1, ZB, WT + 0.18), pbox(-1.7, 1.7, YB0, YB0 + 0.5, ZB, DAIS),
                 pbox(-1.7, 1.7, YB0, YB0 + 0.5, DAIS + 2.2 + 1.85, WT + 0.18)], BIG)

    for i, (x0, x1) in enumerate(((-XI, -4.0), (-4.0, 4.0), (4.0, XI))):
        reg(f"N_Suelo_{i + 1}", "estructura", lambda lod, x0=x0, x1=x1, i=i: flagstones(f"norte-{i}", x0, x1, YP[4], YB0, lod),
            lambda x0=x0, x1=x1: [pbox(x0, x1, YP[4], YB0, FL - 0.3, FL)], BIG)

    # estrado escalonado por tres lados: su casco convexo es una rampa por la que se sube y se baja
    def estrado(lod):
        g = Geo()
        q = 0.025 if lod == 0 else 0
        steps = 4 if lod <= 1 else 1
        for i in range(steps):
            h = FL + (DAIS - FL) * (i + 1) / steps
            grow = 0.43 * (steps - 1 - i) * (4 / steps)
            bx(g, -3.0 - grow, 3.0 + grow, 12.6 - grow, YB0, FL - 0.1, h, "Piedra", q, skip=("-z", "+y"))
        return g

    def estrado_phys():
        pts = [V((-4.6, 11.0, FL)), V((4.6, 11.0, FL)), V((-4.6, YB0, FL)), V((4.6, YB0, FL)),
               V((-3.0, 12.6, DAIS)), V((3.0, 12.6, DAIS)), V((-3.0, YB0, DAIS)), V((3.0, YB0, DAIS))]
        return [("CASCO", pts)]

    reg("N_Estrado", "estructura", estrado, estrado_phys, BIG)

    def trono(lod):
        g = Geo()
        r = rng("trono")
        c = V((0, 14.55, DAIS))
        q = 0.02 if lod == 0 else 0
        bx(g, -0.9, 0.9, c.y - 0.6, c.y + 0.55, DAIS, DAIS + 0.2, "Piedra", q)          # peana
        bx(g, -0.65, 0.65, c.y - 0.42, c.y + 0.35, DAIS + 0.2, DAIS + 0.62, "Madera", q)  # asiento
        bx(g, -0.75, 0.75, c.y + 0.3, c.y + 0.48, DAIS + 0.2, DAIS + 2.9, "Madera", q)    # respaldo alto
        for sx in (-1, 1):  # brazos con argolla
            bx(g, sx * 0.62 - 0.1, sx * 0.62 + 0.1, c.y - 0.45, c.y + 0.35, DAIS + 0.62, DAIS + 0.95, "Madera", q)
            bx(g, sx * 0.62 - 0.12, sx * 0.62 + 0.12, c.y - 0.55, c.y + 0.4, DAIS + 0.95, DAIS + 1.02, "Madera", q)
            if lod <= 1:
                g.link(V((sx * 0.75, c.y - 0.45, DAIS + 0.88)), V((0, 0, 1)), V((0, 1, 0)), 0.06, 0.06, 0.014, 10, 4,
                       "Hierro")
                chains_from(g, V((sx * 0.75, c.y - 0.45, DAIS + 0.82)), V((sx * 0.95, c.y - 0.8, DAIS + 0.03)), lod, 0.1)
            # columnillas laterales del respaldo rematadas en calavera
            bx(g, sx * 0.75 - 0.08, sx * 0.75 + 0.08, c.y + 0.28, c.y + 0.5, DAIS + 0.2, DAIS + 3.1, "Madera", q)
            skull(g, V((sx * 0.75, c.y + 0.39, DAIS + 3.22)), lod, r, V((0, -1, 0)))
        if lod <= 1:
            # corona de púas de hierro y bandas
            for i in range(9):
                x = -0.6 + i * 0.15
                h = 0.25 + 0.25 * (1 - abs(i - 4) / 4)
                g.cyl(V((x, c.y + 0.39, DAIS + 2.9)), V((x, c.y + 0.39, DAIS + 2.9 + h)), 0.025, 4, "Hierro",
                      caps=(False, False), r1=0.0)
            for z in (DAIS + 0.9, DAIS + 2.1):
                bx(g, -0.77, 0.77, c.y + 0.28, c.y + 0.5, z, z + 0.06, "Hierro")
            # piel echada sobre el asiento y cojín
            g.blob(V((0, c.y - 0.05, DAIS + 0.62)), 0.62, 0.45, 0.07, n_(14, lod, 6), 2, "Tela", r, 0.2)
            pts = [V((x, c.y + 0.28, DAIS + 0.62 + 0.9 * (1 - abs(x) / 0.6))) for x in (-0.5, 0, 0.5)]
            g.blob(V((0, c.y + 0.26, DAIS + 1.1)), 0.55, 0.06, 0.5, n_(12, lod, 6), 2, "Tela", r, 0.15,
                   flat_bottom=False)
        return g

    sitter("N_Trono", trono, "trono", lod_map=SMALL)
    SITS["N_Trono"] = (V((0, 14.5, DAIS + 1.05)), -90, "foso_senor", "sit")

    def piedra(lod):
        g = Geo()
        r = rng("piedra")
        c = V((0, 13.15, DAIS))
        g.bbox(c - V((0.45, 0.3, 0)), c + V((0.45, 0.3, 0.28)), "Piedra", 0.06 if lod == 0 else 0)
        if lod <= 1:
            g.link(c + V((0, -0.3, 0.2)), V((0, 0, 1)), V((1, 0, 0)), 0.08, 0.08, 0.018, 12, 4, "Hierro")
            chains_from(g, c + V((0, -0.32, 0.12)), c + V((0.3, -0.75, 0.02)), lod, 0.03)
            collar(g, c + V((0.42, -0.85, 0.02)), 0.13, 0.02, lod)
        return g

    sitter("N_Piedra", piedra, "piedra")
    SITS["N_Piedra"] = (V((0, 13.15 - 0.55, DAIS + 0.45)), 90, "foso_rodillas", "sit_ground_constrained")

    for s in (-1, 1):
        def bras(lod, s=s):
            return brazier(V((s * 2.3, 14.0, DAIS)), lod)
        reg(f"N_Brasero_{'O' if s < 0 else 'E'}", "luz", bras, bbox_phys(bras), SMALL, fire=True, role="brasero")



    for s in (-1, 1):
        S = "O" if s < 0 else "E"

        def atrezzo(lod, s=s):
            g = Geo()
            r = rng(f"trono-atrezzo-{s}")
            X = lambda x: s * x
            # pica con calavera a cada lado de la escalinata
            p = V((X(10.9), 14.8, FL))
            g.cyl(p, p + V((0, 0, 2.4)), 0.025, 5, "Hierro", caps=(True, False), r1=0.012)
            bx(g, p.x - 0.18, p.x + 0.18, p.y - 0.18, p.y + 0.18, FL, FL + 0.12, "Piedra", 0.02 if lod == 0 else 0)
            skull(g, p + V((0, 0, 2.3)), lod, r, V((-s * 0.5, -1, 0)))
            if s < 0:   # pacas de heno
                for (x, y, lvl, a) in ((-8.6, 14.4, 0, 0.1), (-7.4, 14.4, 0, -0.05), (-8.0, 14.45, 1, 0.08),
                                       (-9.9, 13.2, 0, 1.45)):
                    L, W, H = 1.05, 0.52, 0.45
                    z0 = FL + lvl * H
                    cs, sn = math.cos(a), math.sin(a)
                    poly = [(x + cx * cs - cy * sn, y + cx * sn + cy * cs) for cx, cy in
                            ((-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2))]
                    g.prism(poly, Frame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)), z0, z0 + H, "Paja",
                            caps=(lvl > 0, True))
            else:       # cofre del botín, entreabierto, y barriles de ron
                cc = V((8.0, 14.6, FL))
                bx(g, cc.x - 0.5, cc.x + 0.5, cc.y - 0.3, cc.y + 0.3, FL, FL + 0.45, "Madera", 0.02 if lod == 0 else 0)
                lid = Geo()
                lid.box(V((-0.5, 0, 0)), V((0.5, 0.6, 0.08)), "Madera")
                g.extend(xf(lid, (cc.x, cc.y + 0.3, FL + 0.45), rx=1.15))
                if lod <= 1:
                    g.blob(cc + V((0, 0, 0.42)), 0.42, 0.24, 0.1, 10, 2, "Hierro", r, 0.25)  # monedas
                    for z in (0.1, 0.35):
                        bx(g, cc.x - 0.51, cc.x + 0.51, cc.y - 0.31, cc.y + 0.31, FL + z, FL + z + 0.04, "Hierro")
                for (x, y) in ((9.7, 14.5), (10.4, 14.65), (10.0, 13.85)):
                    nn = n_(14, lod, 6)
                    prof = [(0.0, 0.27), (0.45, 0.33), (0.9, 0.27)]
                    rings = [[V((x + math.cos(2 * math.pi * j / nn) * rr, y + math.sin(2 * math.pi * j / nn) * rr,
                                 FL + h)) for j in range(nn)] for h, rr in prof]
                    for i in range(len(rings) - 1):
                        for j in range(nn):
                            j2 = (j + 1) % nn
                            g.face_c([rings[i][j], rings[i][j2], rings[i + 1][j2], rings[i + 1][j]], "Madera",
                                     V((x, y, FL + 0.45)))
                    g.face(rings[-1], "Madera", (0, 0, 1))
            return g

        deco(f"N_Atrezzo_{S}", atrezzo)


def build_all():
    P.PIECES.clear()
    SITS.clear()
    for s in (-1, 1):
        make_piers(s)
        for k in range(4):
            make_head(s, k)
            make_door(s, k)
    for k in range(4):
        make_room_shell(-1, k, k, ROOMS[(-1, k)][0], ROOMS[(-1, k)][1])
    make_room_shell(1, 0, 1, "C05", "La Perrera", roof="techo")
    make_room_shell(1, 2, 2, "C07", "Las Jaulas")
    make_room_shell(1, 3, 3, "C08", "El Mástil")
    make_leva()
    make_potro()
    make_cepo()
    make_cisterna()
    make_perrera()
    make_jaulas()
    make_mastil()
    make_nave()
    make_entrance()
    make_trono()
    return P.PIECES

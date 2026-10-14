"""Primitivas geométricas del Foso V2.

Todo se construye en coordenadas de mundo (metros, Z arriba) dentro de un
acumulador `Geo`, que luego se convierte en malla de Blender. Cada cara se
añade con una pista de dirección exterior (`out`) para garantizar normales
correctas aunque la pieza no sea una superficie cerrada.
"""

import math
import random

import bpy  # noqa: F401  (necesario antes de bmesh con el módulo de PyPI)
import bmesh
from mathutils import Matrix, Vector

# Distribución FIJA de caras para Second Life: todas las piezas tienen las mismas
# 8 caras en el mismo orden (las que no usan se rellenan con un triángulo oculto),
# así un material PBR se aplica de golpe a "toda la piedra", "todo el hierro"...
#   cara 0 Piedra · 1 Suelo · 2 Madera · 3 Hierro · 4 Tela (y cuero) · 5 Hueso · 6 Paja · 7 Llama
# "Agua" va sola en sus propias piezas (canal, cisterna).
MATS = ["Piedra", "Suelo", "Madera", "Hierro", "Tela", "Hueso", "Paja", "Llama", "Agua"]
FACE_MATS = MATS[:8]

# Metros por repetición de textura en el mapeado de caja en coordenadas de mundo.
UV_TILE = {"Llama": 0.4, "Piedra": 2.0, "Suelo": 2.0, "Madera": 1.0, "Hierro": 0.5, "Paja": 1.0,
           "Tela": 0.6, "Hueso": 0.3, "Agua": 3.0}

# Ángulo a partir del cual una arista se considera dura, por material.
SMOOTH_ANGLE = {"Llama": 89, "Piedra": 32, "Suelo": 32, "Madera": 32, "Hierro": 70, "Paja": 80,
                "Tela": 80, "Hueso": 60, "Agua": 89}

V = Vector


def newell(pts):
    n = V((0, 0, 0))
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        n.x += (a.y - b.y) * (a.z + b.z)
        n.y += (a.z - b.z) * (a.x + b.x)
        n.z += (a.x - b.x) * (a.y + b.y)
    return n


class Frame:
    """Sistema local: o + u*a + v*b + n*c."""

    def __init__(self, o, u, v, n):
        self.o, self.u, self.v, self.n = V(o), V(u), V(v), V(n)

    def p(self, a, b, c=0.0):
        return self.o + self.u * a + self.v * b + self.n * c


class Geo:
    def __init__(self):
        self.verts = []
        self.faces = []
        self.mats = []

    # ------------------------------------------------------------ básicos
    def face(self, pts, mat, out=None):
        pts = [V(p) for p in pts]
        if out is not None:
            if newell(pts).dot(V(out)) < 0:
                pts.reverse()
        i = len(self.verts)
        self.verts.extend(pts)
        self.faces.append(tuple(range(i, i + len(pts))))
        self.mats.append(mat)

    def face_c(self, pts, mat, center):
        """Cara orientada hacia fuera de `center`."""
        pts = [V(p) for p in pts]
        c = sum(pts, V()) / len(pts)
        self.face(pts, mat, c - V(center))

    def extend(self, other):
        off = len(self.verts)
        self.verts.extend(other.verts)
        self.faces.extend(tuple(i + off for i in f) for f in other.faces)
        self.mats.extend(other.mats)

    def transform(self, m):
        """Aplica una matriz 4x4 (rotación/traslación) a toda la geometría."""
        self.verts = [m @ v for v in self.verts]
        return self

    def ngon(self, pts, mat, out):
        self.face(pts, mat, out)

    def tri_count(self):
        return sum(len(f) - 2 for f in self.faces)

    def bounds(self):
        xs = [v.x for v in self.verts]
        ys = [v.y for v in self.verts]
        zs = [v.z for v in self.verts]
        return V((min(xs), min(ys), min(zs))), V((max(xs), max(ys), max(zs)))

    # ------------------------------------------------------------ cajas
    def box(self, mn, mx, mat, skip=()):
        mn, mx = V(mn), V(mx)
        (x0, y0, z0) = (min(mn.x, mx.x), min(mn.y, mx.y), min(mn.z, mx.z))
        (x1, y1, z1) = (max(mn.x, mx.x), max(mn.y, mx.y), max(mn.z, mx.z))
        c = V(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
        F = {
            "-x": [(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)],
            "+x": [(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)],
            "-y": [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
            "+y": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
            "-z": [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
            "+z": [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
        }
        for k, pts in F.items():
            if k not in skip:
                self.face_c(pts, mat, c)

    def bbox(self, mn, mx, mat, c=0.03, skip=()):
        """Caja achaflanada (chaflán `c`). Si c es 0, caja normal."""
        a, b = V(mn), V(mx)
        mn = V((min(a.x, b.x), min(a.y, b.y), min(a.z, b.z)))
        mx = V((max(a.x, b.x), max(a.y, b.y), max(a.z, b.z)))
        size = mx - mn
        c = min(c, min(size) * 0.45)
        if c <= 0.001:
            return self.box(mn, mx, mat, skip)
        bm = bmesh.new()
        bmesh.ops.create_cube(bm, size=1.0)
        for v in bm.verts:
            v.co = V((mn.x + (v.co.x + 0.5) * size.x, mn.y + (v.co.y + 0.5) * size.y,
                      mn.z + (v.co.z + 0.5) * size.z))
        bmesh.ops.bevel(bm, geom=list(bm.verts) + list(bm.edges), offset=c, segments=1,
                        affect="EDGES", profile=0.5, clamp_overlap=True)
        ctr = (mn + mx) / 2
        for f in bm.faces:
            n = f.normal
            if skip:
                key = None
                for ax, name in ((0, "x"), (1, "y"), (2, "z")):
                    if abs(n[ax]) > 0.99:
                        key = ("+" if n[ax] > 0 else "-") + name
                if key in skip:
                    continue
            self.face_c([v.co.copy() for v in f.verts], mat, ctr)
        bm.free()

    def slab(self, x0, y0, x1, y1, z0, z1, c, mat):
        """Losa con la cara superior achaflanada; sin cara inferior."""
        c = min(c, (x1 - x0) * 0.4, (y1 - y0) * 0.4, (z1 - z0) * 0.9)
        zc = z1 - c
        top = [(x0 + c, y0 + c, z1), (x1 - c, y0 + c, z1), (x1 - c, y1 - c, z1), (x0 + c, y1 - c, z1)]
        mid = [(x0, y0, zc), (x1, y0, zc), (x1, y1, zc), (x0, y1, zc)]
        bot = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)]
        ctr = ((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2)
        self.face(top, mat, (0, 0, 1))
        for i in range(4):
            j = (i + 1) % 4
            self.face_c([mid[i], mid[j], top[j], top[i]], mat, ctr)
            if z0 < zc - 1e-4:
                self.face_c([bot[i], bot[j], mid[j], mid[i]], mat, ctr)

    # ------------------------------------------------------------ prismas
    def prism(self, poly, fr, d0, d1, mat, caps=(True, True)):
        """Extruye un polígono convexo (coords del Frame) entre profundidades d0 y d1."""
        a = [fr.p(u, v, d0) for u, v in poly]
        b = [fr.p(u, v, d1) for u, v in poly]
        cu = sum(u for u, _ in poly) / len(poly)
        cv = sum(v for _, v in poly) / len(poly)
        ctr = fr.p(cu, cv, (d0 + d1) / 2)
        if caps[0]:
            self.face(a, mat, fr.n * (1 if d0 > d1 else -1))
        if caps[1]:
            self.face(b, mat, fr.n * (1 if d1 > d0 else -1))
        n = len(poly)
        for i in range(n):
            j = (i + 1) % n
            self.face_c([a[i], a[j], b[j], b[i]], mat, ctr)

    def cyl(self, p0, p1, r, n, mat, caps=(True, True), phase=0.0, r1=None):
        p0, p1 = V(p0), V(p1)
        ax = (p1 - p0)
        if ax.length < 1e-6:
            return
        ax.normalize()
        t = ax.orthogonal().normalized()
        b = ax.cross(t)
        r1 = r if r1 is None else r1
        ring0, ring1 = [], []
        for i in range(n):
            a = phase + 2 * math.pi * i / n
            d = t * math.cos(a) + b * math.sin(a)
            ring0.append(p0 + d * r)
            ring1.append(p1 + d * r1)
        for i in range(n):
            j = (i + 1) % n
            mid = (p0 + p1) / 2
            self.face_c([ring0[i], ring0[j], ring1[j], ring1[i]], mat, mid)
        if caps[0]:
            self.face(ring0, mat, -ax)
        if caps[1] and r1 > 1e-5:
            self.face(ring1, mat, ax)

    def sweep(self, path, r, n, mat, caps=True, radii=None):
        """Tubo de sección poligonal a lo largo de una polilínea."""
        path = [V(p) for p in path]
        rings = []
        prev_t = None
        prev_side = None
        for i, p in enumerate(path):
            if i == 0:
                t = path[1] - p
            elif i == len(path) - 1:
                t = p - path[i - 1]
            else:
                t = path[i + 1] - path[i - 1]
            t.normalize()
            if prev_side is None:
                side = t.orthogonal().normalized()
            else:
                side = (prev_side - t * prev_side.dot(t)).normalized()
            prev_side, prev_t = side, t
            up = t.cross(side)
            rr = r if radii is None else radii[i]
            rings.append([p + (side * math.cos(2 * math.pi * k / n) + up * math.sin(2 * math.pi * k / n)) * rr
                          for k in range(n)])
        for i in range(len(path) - 1):
            mid = (path[i] + path[i + 1]) / 2
            for k in range(n):
                j = (k + 1) % n
                self.face_c([rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]], mat, mid)
        if caps:
            self.face(rings[0], mat, path[0] - path[1])
            self.face(rings[-1], mat, path[-1] - path[-2])

    def link(self, c, t, w, half_len, half_wid, r, nmaj, nmin, mat):
        """Eslabón tipo estadio (o anillo si half_len == half_wid).

        c: centro; t: eje largo; w: eje ancho (ambos en el plano del eslabón).
        half_len/half_wid se miden sobre la línea central del alambre.
        """
        c, t, w = V(c), V(t).normalized(), V(w).normalized()
        k = max(half_len - half_wid, 0.0)
        pts = []
        half = max(nmaj // 2, 2)
        for s in (1, -1):
            cen = c + t * (s * k)
            for i in range(half):
                phi = -math.pi / 2 + math.pi * i / (half - 1) if half > 1 else 0
                pts.append(cen + (t * math.cos(phi) + w * math.sin(phi)) * (s * half_wid))
        if k < 1e-6:  # anillo: quitar duplicados del empalme
            pts = [pts[i] for i in range(len(pts)) if i % half != half - 1]
        nrm = t.cross(w).normalized()
        rings = []
        m = len(pts)
        for i in range(m):
            tan = (pts[(i + 1) % m] - pts[i - 1]).normalized()
            radial = tan.cross(nrm).normalized()
            if radial.dot(pts[i] - c) < 0:
                radial = -radial
            rings.append([(pts[i], pts[i] + (radial * math.cos(2 * math.pi * j / nmin)
                                              + nrm * math.sin(2 * math.pi * j / nmin)) * r)
                          for j in range(nmin)])
        for i in range(m):
            i2 = (i + 1) % m
            for j in range(nmin):
                j2 = (j + 1) % nmin
                quad = [rings[i][j][1], rings[i][j2][1], rings[i2][j2][1], rings[i2][j][1]]
                axis_mid = (rings[i][0][0] + rings[i2][0][0]) / 2
                self.face_c(quad, mat, axis_mid)

    def blob(self, center, rx, ry, rz, nu, nv, mat, rnd, jitter=0.15, flat_bottom=True, zmin=None, rot=None):
        """Montón irregular (paja, carbón): elipsoide perturbado con base plana."""
        center = V(center)
        rows = []
        for i in range(nv + 1):
            th = (math.pi / 2) * i / nv  # 0 = ecuador, pi/2 = polo
            row = []
            for j in range(nu):
                ph = 2 * math.pi * j / nu
                k = 1 + (rnd.uniform(-jitter, jitter) if i < nv else 0)
                x = math.cos(th) * math.cos(ph) * rx * k
                y = math.cos(th) * math.sin(ph) * ry * k
                z = math.sin(th) * rz * (1 + (rnd.uniform(-jitter, jitter) * 0.6 if 0 < i < nv else 0))
                off = V((x, y, z))
                if rot is not None:
                    off = rot @ off
                p = center + off
                if zmin is not None:
                    p.z = max(p.z, zmin)
                row.append(p)
            rows.append(row)
        for i in range(nv):
            for j in range(nu):
                j2 = (j + 1) % nu
                if i == nv - 1:
                    self.face_c([rows[i][j], rows[i][j2], rows[i + 1][0]], mat, center)
                else:
                    self.face_c([rows[i][j], rows[i][j2], rows[i + 1][j2], rows[i + 1][j]], mat, center)
        if flat_bottom:
            self.face(rows[0], mat, (0, 0, -1))

    def spike(self, base, height, radius, mat):
        """Pirámide de 3 caras (llama mínima para el LOD más bajo)."""
        base = V(base)
        tip = base + V((0, 0, height))
        ring = [base + V((math.cos(a) * radius, math.sin(a) * radius, 0)) for a in (0, 2.094, 4.189)]
        for i in range(3):
            self.face_c([ring[i], ring[(i + 1) % 3], tip], mat, base + V((0, 0, height * 0.3)))

    def flame(self, base, height, radius, n, mat, rnd, lean=V((0, 0, 0))):
        """Llama: huso irregular con punta, dos lenguas cruzadas."""
        base = V(base)
        prof = [(0.0, 0.55), (0.18, 1.0), (0.45, 0.8), (0.75, 0.4), (1.0, 0.0)]
        rings = []
        for h, rr in prof:
            c = base + V((0, 0, h * height)) + lean * (h * h)
            if rr == 0:
                rings.append([c])
                continue
            rings.append([c + V((math.cos(2 * math.pi * k / n + h * 2.0) * radius * rr * rnd.uniform(0.8, 1.2),
                                 math.sin(2 * math.pi * k / n + h * 2.0) * radius * rr * rnd.uniform(0.8, 1.2), 0))
                          for k in range(n)])
        axis = base + V((0, 0, height * 0.4))
        for i in range(len(rings) - 1):
            a, b = rings[i], rings[i + 1]
            for k in range(n):
                k2 = (k + 1) % n
                if len(b) == 1:
                    self.face_c([a[k], a[k2], b[0]], mat, axis)
                else:
                    self.face_c([a[k], a[k2], b[k2], b[k]], mat, axis)
        self.face(rings[0], mat, (0, 0, -1))


# ------------------------------------------------------------------ arcos
def pointed_arch(span, ratio, n_side, extra=0.0):
    """Puntos (u, v) del intradós de un arco apuntado, desde el arranque izquierdo
    hasta el derecho, con radio R = ratio*span (+extra para el trasdós)."""
    hw = span / 2
    R = ratio * span
    cx = -hw + R  # centro del arco izquierdo
    Rr = R + extra
    th_end = math.acos(max(-1.0, min(1.0, (0 - cx) / Rr)))
    pts = []
    for i in range(n_side + 1):
        th = math.pi + (th_end - math.pi) * i / n_side
        pts.append((cx + Rr * math.cos(th), Rr * math.sin(th)))
    right = [(-u, v) for u, v in reversed(pts[:-1])]
    return pts + right


def arch_height(u, span, ratio):
    hw = span / 2
    R = ratio * span
    cx = -hw + R
    if u > 0:
        u = -u
    d = R * R - (u - cx) ** 2
    return math.sqrt(max(d, 0.0))


def rng(seed):
    return random.Random(seed)


def rot_z(angle):
    return Matrix.Rotation(angle, 3, "Z")

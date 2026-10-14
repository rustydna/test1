"""Prueba de circulación del Foso V3 en dos escenarios de Second Life.

A) CONFIGURADO: el script foso_nucleo puso la física de cada pieza
   (estructura = la física subida; muebles = casco convexo; decoración = nada).
B) SIN SCRIPTS: nadie tocó nada y SL dejó TODAS las mallas en «Convex Hull»
   (el caso en el que en la V2 no se podía entrar en las celdas). Se usa el casco
   convexo de la geometría visible de cada pieza, que es el caso más desfavorable.

En ambos, con las puertas abiertas, un avatar (radio 0,25 m, cuerpo de 0,35 a
1,9 m) debe llegar desde la escalinata exterior a todas las salas.

Uso: python foso_mazmorra/scripts/qa_fisica.py   (necesita salida/Foso_V3.blend)
"""

import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import pieces_v3 as P  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "salida")
STEP = 0.2
RADIUS = 0.25
FL = P.FL


def bvh_from(objs, hull=False):
    verts, polys = [], []
    for ob in objs:
        me = ob.data
        mw = ob.matrix_basis  # en colecciones ocultas matrix_world puede estar sin actualizar
        pts = [mw @ v.co for v in me.vertices]
        if hull:
            bm = bmesh.new()
            for p in pts:
                bm.verts.new(p)
            bmesh.ops.convex_hull(bm, input=bm.verts)
            off = len(verts)
            idx = {v: i for i, v in enumerate(bm.verts)}
            verts.extend(v.co.copy() for v in bm.verts)
            polys.extend([off + idx[v] for v in f.verts] for f in bm.faces if f.is_valid)
            bm.free()
        else:
            off = len(verts)
            verts.extend(pts)
            polys.extend([off + i for i in p.vertices] for p in me.polygons)
    return BVHTree.FromPolygons(verts, polys)


def objects(level, kinds):
    coll = bpy.data.collections["FISICA" if level == "PHYS" else "MALLA | HIGH"]
    return [ob for ob in coll.objects if ob.get("sl_kind") in kinds]


def walk(bvh, label):
    x0, x1, y0, y1 = -13.2, 13.2, -19.8, 16.2
    nx, ny = int((x1 - x0) / STEP) + 1, int((y1 - y0) / STEP) + 1
    up, down = Vector((0, 0, 1)), Vector((0, 0, -1))
    grid = {}
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * STEP, y0 + j * STEP
            hit = bvh.ray_cast(Vector((x, y, FL + 1.25)), down, 3.0)
            gz = hit[0].z if hit[0] is not None else None
            blocked = gz is None and -12.4 < x < 12.4 and -18.0 < y < 16.0
            if gz is None:
                gz = 0.0
            if not blocked:
                for h in (0.45, 1.0, 1.6):
                    p = Vector((x, y, gz + h))
                    hit = bvh.find_nearest(p, RADIUS)
                    if hit[0] is not None and hit[0].z > p.z - 0.3:   # lo que queda bajo los pies es suelo/rampa
                        blocked = True
                        break
                    hu = bvh.ray_cast(p, up, 12.0)
                    if hu[0] is not None and hu[1].dot(up) > 0.1:   # dentro de un sólido
                        blocked = True
                        break
            grid[i, j] = (gz, blocked)
    start = (int((0 - x0) / STEP), int((-19.6 - y0) / STEP))
    seen = {start}
    q = deque([start])
    while q:
        i, j = q.popleft()
        gz = grid[i, j][0]
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (i + di, j + dj)
            if n in seen or n not in grid:
                continue
            g2, b = grid[n]
            if b or abs(g2 - gz) > 0.45:
                continue
            seen.add(n)
            q.append(n)

    def reach(x, y):
        return (int(round((x - x0) / STEP)), int(round((y - y0) / STEP))) in seen

    targets = {"Patio": (0, 0), "Vestíbulo oeste": (-8, -13.5), "Vestíbulo este": (8, -12.2),
               "Estrado del trono": (-1.3, 12.9), "Sala del Señor, ala oeste": (-6.0, 12.6),
               "Sala del Señor, ala este": (6.0, 12.6)}
    for (s, k), (tag, room) in P.ROOMS.items():
        targets[f"{tag} {room}"] = (s * 4.6, P.cell_center(k) - 1.6)
    res = {name: reach(*xy) for name, xy in targets.items()}
    try:
        from PIL import Image
        img = Image.new("RGB", (nx, ny))
        for (i, j), (gz, b) in grid.items():
            c = (40, 40, 48) if b else ((235, 225, 200) if (i, j) in seen else (90, 90, 90))
            if (i, j) in seen and gz > FL + 0.2:
                c = (250, 190, 120)
            img.putpixel((i, ny - 1 - j), c)
        img.resize((nx * 4, ny * 4), Image.NEAREST).save(os.path.join(OUT, f"QA_fisica_{label}.png"))
    except ImportError:
        pass
    return res


def run():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "Foso_V3.blend"))
    bpy.context.view_layer.update()
    # A) configurado: física subida de la estructura + casco de los muebles
    bvh_a = BVHTree.FromPolygons(*_merge([bvh_parts(objects("PHYS", ("estructura",)), False),
                                         bvh_parts(objects("PHYS", ("mueble",)), True)]))
    # B) sin scripts: casco convexo de la geometría visible de TODO (menos las hojas, abiertas)
    bvh_b = BVHTree.FromPolygons(*bvh_parts(objects("HIGH", ("estructura", "mueble", "deco", "luz", "agua")), True))
    a = walk(bvh_a, "configurado")
    b = walk(bvh_b, "sin_scripts")
    out = {"configurado": a, "sin_scripts": b,
           "todo_accesible_configurado": all(a.values()),
           "todo_accesible_sin_scripts": all(b.values()),
           "parametros": {"paso_m": STEP, "radio_avatar_m": RADIUS, "puertas": "abiertas"}}
    with open(os.path.join(OUT, "QA_fisica.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


def bvh_parts(objs, hull):
    verts, polys = [], []
    for ob in objs:
        mw = ob.matrix_basis  # en colecciones ocultas matrix_world puede estar sin actualizar
        pts = [mw @ v.co for v in ob.data.vertices]
        if hull:
            bm = bmesh.new()
            for p in pts:
                bm.verts.new(p)
            bmesh.ops.convex_hull(bm, input=bm.verts)
            bm.verts.ensure_lookup_table()
            idx = {v: i for i, v in enumerate(bm.verts)}
            off = len(verts)
            verts.extend(v.co.copy() for v in bm.verts)
            polys.extend([off + idx[v] for v in f.verts] for f in bm.faces if f.is_valid)
            bm.free()
        else:
            off = len(verts)
            verts.extend(pts)
            polys.extend([off + i for i in p.vertices] for p in ob.data.polygons)
    return verts, polys


def _merge(parts):
    verts, polys = [], []
    for v, p in parts:
        off = len(verts)
        verts.extend(v)
        polys.extend([off + i for i in poly] for poly in p)
    return verts, polys


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))

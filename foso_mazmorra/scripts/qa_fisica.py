"""Prueba de circulación sobre la física exportada (PHYS) y comparación con lo visible (HIGH).

Simula un avatar como una columna de radio 0,25 m entre 0,35 y 1,9 m sobre el suelo,
con las puertas abiertas (las hojas tienen su propia física y se mueven con el script).

* Relleno por inundación desde la escalinata exterior: ¿se llega a todas las celdas,
  al vestíbulo, al patio y al estrado?
* Pared invisible: la física bloquea donde no hay piedra visible.
* Atravesable: hay piedra visible donde la física deja pasar.
* Apoyo: en cada punto alcanzable hay suelo físico bajo los pies.

Uso: python foso_mazmorra/scripts/qa_fisica.py   (necesita salida/Foso_V2.blend)
"""

import json
import os
import sys
from collections import deque

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import pieces as P  # noqa: E402

OUT = os.path.join(os.path.dirname(HERE), "salida")
STEP = 0.2
RADIUS = 0.25
Z_LO, Z_HI = 0.35, 1.9
SKIP_KIND = ("puerta",)


def boxes_and_ramps():
    boxes, ramps = [], []
    for pc in P.build_all():
        if pc.kind in SKIP_KIND or pc.kind == "deco":  # en SL la física de lo decorativo va a None
            continue
        for b in pc.phys():
            if b[0] == "RAMPA":
                ramps.append((b[1], b[2]))
            else:
                boxes.append((b[0], b[1], pc.name))
    return boxes, ramps


def ground_at(x, y, boxes, ramps):
    """Cota del suelo físico más alto alcanzable (escalón ≤ 0,5 m) bajo (x, y)."""
    best = None
    for mn, mx, _ in boxes:
        if mn.x <= x <= mx.x and mn.y <= y <= mx.y and mx.z <= P.FL + 1.0:
            best = mx.z if best is None else max(best, mx.z)
    for mn, mx in ramps:
        if mn.x <= x <= mx.x and mn.y <= y <= mx.y:
            z = mn.z + (mx.z - mn.z) * (y - mn.y) / (mx.y - mn.y)
            best = z if best is None else max(best, z)
    return best


def phys_blocked(x, y, gz, boxes):
    lo, hi = gz + Z_LO, gz + Z_HI
    for mn, mx, name in boxes:
        if mx.z <= lo or mn.z >= hi:
            continue
        dx = max(mn.x - x, 0, x - mx.x)
        dy = max(mn.y - y, 0, y - mx.y)
        if dx * dx + dy * dy < RADIUS * RADIUS:
            return name
    return None


def visual_bvh():
    verts, polys = [], []
    for ob in bpy.data.collections["MALLA | HIGH"].objects:
        if ob.get("sl_kind") != "estructura" and not ob.name.endswith("_Reja"):
            continue
        me = ob.data
        mw = ob.matrix_world
        off = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        polys.extend([off + i for i in p.vertices] for p in me.polygons)
    return BVHTree.FromPolygons(verts, polys)


def run():
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "Foso_V2.blend"))
    bpy.context.view_layer.update()
    boxes, ramps = boxes_and_ramps()
    bvh = visual_bvh()
    x0, x1, y0, y1 = -13.2, 13.2, -19.8, 16.2
    nx, ny = int((x1 - x0) / STEP) + 1, int((y1 - y0) / STEP) + 1
    grid = {}
    for i in range(nx):
        for j in range(ny):
            x, y = x0 + i * STEP, y0 + j * STEP
            gz = ground_at(x, y, boxes, ramps)
            if gz is None:
                gz = 0.0  # terreno exterior
            pb = phys_blocked(x, y, gz, boxes)
            # dos tolerancias: "hay piedra cerca" (r + 3 cm) para paredes invisibles,
            # "la piedra se mete ≥ 5 cm en el avatar" (r - 5 cm) para zonas atravesables
            vb = vg = False
            for h in (0.45, 1.0, 1.6):
                p = Vector((x, y, gz + h))
                if not vb and bvh.find_nearest(p, RADIUS + 0.03)[0] is not None:
                    vb = True
                if not vg and bvh.find_nearest(p, RADIUS - 0.05)[0] is not None:
                    vg = True
            grid[i, j] = (gz, pb, vb, vg)
    # inundación desde delante de la escalinata
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
            g2, pb = grid[n][0], grid[n][1]
            if pb or abs(g2 - gz) > 0.5:
                continue
            x, y = x0 + n[0] * STEP, y0 + n[1] * STEP
            inside = -13.0 < x < 13.0 and -18.0 < y < 16.0
            if inside and ground_at(x, y, boxes, ramps) is None:
                continue  # agujero en el suelo físico
            seen.add(n)
            q.append(n)

    def reach(x, y):
        return (int(round((x - x0) / STEP)), int(round((y - y0) / STEP))) in seen

    targets = {"Patio centro": (0, 0), "Vestíbulo oeste": (-8, -13.5), "Vestíbulo este": (8, -13.5),
               "Estrado (brasero)": (1.5, 13.5), "Sala del perrero oeste": (-6.0, 12.6),
               "Sala del perrero este": (6.0, 12.6)}
    for k in range(4):
        yc = (P.YP[k] + P.YP[k + 1]) / 2
        targets[f"Celda C{k + 1:02d}"] = (-7.0, yc)
        targets[f"Celda C{k + 5:02d}"] = (7.0, yc)
    res = {name: reach(*xy) for name, xy in targets.items()}

    def near_walkable(i, j, k=2):
        return any((i + a, j + b) in seen for a in range(-k, k + 1) for b in range(-k, k + 1))

    invisible, ghost, no_floor = [], [], 0
    for (i, j), (gz, pb, vb, vg) in grid.items():
        x, y = x0 + i * STEP, y0 + j * STEP
        inside = -12.4 < x < 12.4 and -18.0 < y < 16.0
        if not inside:
            continue
        # pared invisible: la física frena junto a una zona transitable sin piedra visible
        if pb and not vb and near_walkable(i, j, 1):
            invisible.append((round(x, 1), round(y, 1), pb))
        # atravesable: piedra visible en un punto al que se llega caminando
        if vg and not pb and (i, j) in seen:
            ghost.append((round(x, 1), round(y, 1)))
        if (i, j) in seen and ground_at(x, y, boxes, ramps) is None:
            no_floor += 1

    # mapa
    try:
        from PIL import Image
        img = Image.new("RGB", (nx, ny))
        for (i, j), (gz, pb, vb, vg) in grid.items():
            if pb and vb:
                c = (40, 40, 48)
            elif pb and near_walkable(i, j, 1):
                c = (220, 40, 40)
            elif pb:
                c = (40, 40, 48)
            elif vg and (i, j) in seen:
                c = (40, 90, 230)
            elif (i, j) in seen:
                c = (235, 225, 200) if gz < P.FL + 0.2 else (250, 190, 120)
            else:
                c = (90, 90, 90)
            img.putpixel((i, ny - 1 - j), c)
        img = img.resize((nx * 4, ny * 4), Image.NEAREST)
        img.save(os.path.join(OUT, "QA_fisica_mapa.png"))
    except ImportError:
        pass

    # agrupar paredes invisibles por pieza
    by_piece = {}
    for x, y, name in invisible:
        by_piece[name] = by_piece.get(name, 0) + 1
    out = {
        "accesible": res,
        "todo_accesible": all(res.values()),
        "celdas_pared_invisible": len(invisible),
        "pared_invisible_por_pieza_m2": {k: round(v * STEP * STEP, 2) for k, v in
                                          sorted(by_piece.items(), key=lambda kv: -kv[1])[:12]},
        "celdas_atravesables": len(ghost),
        "atravesables_muestra": ghost[:20],
        "puntos_alcanzables_sin_suelo": no_floor,
        "parametros": {"paso_m": STEP, "radio_avatar_m": RADIUS, "franja_cuerpo_m": [Z_LO, Z_HI],
                       "puertas": "abiertas (sin física de hojas)"},
    }
    with open(os.path.join(OUT, "QA_fisica.json"), "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    return out


if __name__ == "__main__":
    print(json.dumps(run(), ensure_ascii=False, indent=1))

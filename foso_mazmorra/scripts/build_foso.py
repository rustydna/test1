"""Construye el Foso V2 completo: Blender, DAE por nivel, auditoría y estimación de LI.

Uso (desde cualquier carpeta):
    python foso_mazmorra/scripts/build_foso.py            # con el módulo bpy de PyPI
    blender -b --factory-startup --python foso_mazmorra/scripts/build_foso.py

Salida en foso_mazmorra/salida/.
"""

import json
import math
import os
import sys
import time
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402  (antes que bmesh con el módulo de PyPI)
import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import pieces as P  # noqa: E402
from collada_static import write_dae  # noqa: E402
from geo import MATS, SMOOTH_ANGLE, UV_TILE, Geo  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "salida")
LEVELS = ["HIGH", "MEDIUM", "LOW", "LOWEST"]
SUFFIX = {"HIGH": "", "MEDIUM": "_LOD2", "LOW": "_LOD1", "LOWEST": "_LOD0", "PHYS": "_PHYS"}
COLL = {"HIGH": "MALLA | HIGH", "MEDIUM": "LOD | MEDIUM", "LOW": "LOD | LOW", "LOWEST": "LOD | LOWEST",
        "PHYS": "FISICA"}
COLORS = {"Llama": (1.0, 0.45, 0.1), "Piedra": (0.5, 0.48, 0.45), "Suelo": (0.36, 0.32, 0.27),
          "Madera": (0.36, 0.24, 0.14), "Hierro": (0.12, 0.12, 0.13), "Paja": (0.66, 0.55, 0.3),
          "Fisica": (0.2, 0.6, 1.0)}
MARK = 0.004


# ------------------------------------------------------------------ geometría auxiliar
def ensure_bounds(g, mn, mx, mat):
    """Añade dos triángulos diminutos en las esquinas de la caja del HIGH si el nivel no la alcanza.
    SL estira cada LOD y la física hasta la caja del HIGH; así no se deforman."""
    if g.verts:
        # un nivel que sobresale de la caja del HIGH se recorta a ella
        for v in g.verts:
            v.x = min(max(v.x, mn.x), mx.x)
            v.y = min(max(v.y, mn.y), mx.y)
            v.z = min(max(v.z, mn.z), mx.z)
        a, b = g.bounds()
        if (a - mn).length < 1e-5 and (b - mx).length < 1e-5:
            return False
    e = MARK
    g.face([mn, mn + Vector((e, 0, 0)), mn + Vector((0, e, 0))], mat, (0, 0, -1))
    g.face([mx, mx - Vector((e, 0, 0)), mx - Vector((0, e, 0))], mat, (0, 0, 1))
    return True


def _copy(g):
    c = Geo()
    c.verts = [v.copy() for v in g.verts]
    c.faces = list(g.faces)
    c.mats = list(g.mats)
    return c


def phys_geo(boxes):
    g = Geo()
    for b in boxes:
        if b[0] == "RAMPA":
            _, mn, mx = b
            x0, y0, z0 = mn
            x1, y1, z1 = mx
            pts = [Vector(p) for p in ((x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1))]
            g.face(pts, "Fisica", (0, -1, 1))
            g.face([Vector((x0, y1, z0)), Vector((x1, y1, z0)), Vector((x1, y1, z1)), Vector((x0, y1, z1))],
                   "Fisica", (0, 1, 0))
            g.face([Vector((x0, y0, z0)), Vector((x0, y1, z0)), Vector((x0, y1, z1))], "Fisica", (-1, 0, 0))
            g.face([Vector((x1, y0, z0)), Vector((x1, y1, z0)), Vector((x1, y1, z1))], "Fisica", (1, 0, 0))
            g.face([Vector((x0, y0, z0)), Vector((x1, y0, z0)), Vector((x1, y1, z0)), Vector((x0, y1, z0))],
                   "Fisica", (0, 0, -1))
        else:
            g.box(b[0], b[1], "Fisica")
    return g


# ------------------------------------------------------------------ Blender
def material(name):
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        c = COLORS.get(name, (0.5, 0.5, 0.5))
        m.diffuse_color = (*c, 1.0)
        m.use_nodes = True
        bsdf = m.node_tree.nodes.get("Principled BSDF")
        if bsdf:
            bsdf.inputs["Base Color"].default_value = (*c, 1.0)
            bsdf.inputs["Roughness"].default_value = {"Hierro": 0.45, "Llama": 0.6}.get(name, 0.92)
            bsdf.inputs["Metallic"].default_value = 0.85 if name == "Hierro" else 0.0
            if name == "Llama":
                bsdf.inputs["Emission Color"].default_value = (1.0, 0.42, 0.08, 1.0)
                bsdf.inputs["Emission Strength"].default_value = 18.0
            if name == "Fisica":
                bsdf.inputs["Alpha"].default_value = 0.35
    return m


def uv_for(co, n, mat):
    s = UV_TILE.get(mat, 1.0)
    ax = max(range(3), key=lambda i: abs(n[i]))
    if ax == 0:
        u, v = (co.y if n.x > 0 else -co.y), co.z
    elif ax == 1:
        u, v = (-co.x if n.y > 0 else co.x), co.z
    else:
        u, v = co.x, (co.y if n.z > 0 else -co.y)
    return u / s, v / s


def mesh_object(name, g, origin, coll, level, sl_name, kind):
    me = bpy.data.meshes.new(name)
    verts = [v - origin for v in g.verts]
    me.from_pydata([tuple(v) for v in verts], [], g.faces)
    present = [m for m in MATS + ["Fisica"] if m in set(g.mats)]
    for m in present:
        me.materials.append(material(m))
    idx = {m: i for i, m in enumerate(present)}
    for poly, m in zip(me.polygons, g.mats):
        poly.material_index = idx[m]
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1.5e-4)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-6)
    bm.to_mesh(me)
    bm.free()
    # aristas duras por ángulo según material y en cambios de material
    sharp = [False] * len(me.edges)
    edge_faces = {}
    for p in me.polygons:
        for ek in p.edge_keys:
            edge_faces.setdefault(ek, []).append(p.index)
    ek_index = {e.key: e.index for e in me.edges}
    for ek, fl in edge_faces.items():
        i = ek_index[ek]
        if len(fl) != 2:
            sharp[i] = True
            continue
        a, b = me.polygons[fl[0]], me.polygons[fl[1]]
        ma, mb = present[a.material_index], present[b.material_index]
        if ma != mb:
            sharp[i] = True
            continue
        ang = math.degrees(a.normal.angle(b.normal, 0.0))
        sharp[i] = ang > SMOOTH_ANGLE.get(ma, 30)
    attr = me.attributes.get("sharp_edge") or me.attributes.new("sharp_edge", "BOOLEAN", "EDGE")
    attr.data.foreach_set("value", sharp)
    for p in me.polygons:
        p.use_smooth = True
    # UV de caja en coordenadas de mundo (texturas repetibles y continuas entre piezas)
    uvl = me.uv_layers.new(name="UVMap")
    for p in me.polygons:
        m = present[p.material_index]
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co + origin
            uvl.data[li].uv = uv_for(co, p.normal, m)
    me.update()
    ob = bpy.data.objects.new(name, me)
    ob.location = origin
    ob["sl_name"] = sl_name
    ob["sl_level"] = level
    ob["sl_kind"] = kind
    coll.objects.link(ob)
    return ob


def get_coll(name, parent=None):
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
        (parent or bpy.context.scene.collection).children.link(c)
    return c


# ------------------------------------------------------------------ land impact (estimación)
def submesh_stats(ob):
    me = ob.data
    me.calc_loop_triangles()
    cn = me.corner_normals
    uv = me.uv_layers[0].data if me.uv_layers else None
    verts = set()
    tris = 0
    for t in me.loop_triangles:
        tris += 1
        for li in t.loops:
            key = (t.material_index, me.loops[li].vertex_index, tuple(round(c, 3) for c in cn[li].vector),
                   tuple(round(c, 4) for c in uv[li].uv) if uv else ())
            verts.add(key)
    return tris, len(verts), len(me.materials)


def est_bytes(tris, verts, subm):
    # malla SL: posición/normal/UV cuantizadas (16 B por vértice) + índices (6 B por triángulo), zlib ~0.6
    return (verts * 16 + tris * 6) * 0.6 + 40 * subm


def streaming_cost(radius, lod_bytes):
    """Réplica de LLMeshCostData::getRadiusWeightedTris del visor de SL."""
    max_dist, max_area, min_area = 512.0, 102944.0, 1.0
    dlowest = min(radius / 0.03, max_dist)
    dlow = min(radius / 0.06, max_dist)
    dmid = min(radius / 0.24, max_dist)
    high_area = min(math.pi * dmid * dmid, max_area)
    mid_area = min(math.pi * dlow * dlow, max_area)
    low_area = min(math.pi * dlowest * dlowest, max_area)
    lowest_area = max_area
    lowest_area -= low_area
    low_area -= mid_area
    mid_area -= high_area
    high_area = min(max(high_area, min_area), max_area)
    mid_area = min(max(mid_area, min_area), max_area)
    low_area = min(max(low_area, min_area), max_area)
    lowest_area = min(max(lowest_area, min_area), max_area)
    total = high_area + mid_area + low_area + lowest_area
    w = [high_area / total, mid_area / total, low_area / total, lowest_area / total]
    tris = [max(b - 384.0, 16.0) / 16.0 for b in lod_bytes]
    weighted = sum(a * b for a, b in zip(w, tris))
    return weighted / 250000.0 * 15000.0, w


# ------------------------------------------------------------------ principal
def build(save=True, export=True):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Foso V2"
    scene.unit_settings.system = "METRIC"
    colls = {lv: get_coll(COLL[lv]) for lv in LEVELS + ["PHYS"]}
    for lv in ("MEDIUM", "LOW", "LOWEST", "PHYS"):
        colls[lv].hide_render = True
        colls[lv].hide_viewport = True

    pieces = P.build_all()
    report = {"piezas": [], "niveles": {}, "avisos": []}
    objs = {lv: [] for lv in LEVELS + ["PHYS"]}
    li_total = 0.0
    for pc in pieces:
        cache = {}
        for m in pc.lod_map:
            if m not in cache:
                cache[m] = pc.build(m)
        geos = [cache[pc.lod_map[0]]] + [_copy(cache[m]) for m in pc.lod_map[1:]]
        if not geos[0].verts:
            report["avisos"].append(f"{pc.name}: HIGH vacío")
            continue
        mn, mx = geos[0].bounds()
        origin = (mn + mx) / 2
        hmats = [m for m in MATS if m in set(geos[0].mats)]
        markers = {}
        for i in range(1, 4):
            markers[LEVELS[i]] = ensure_bounds(geos[i], mn, mx, hmats[0])
            extra = set(geos[i].mats) - set(hmats)
            if extra:
                report["avisos"].append(f"{pc.name} {LEVELS[i]}: materiales fuera del HIGH {extra}")
        pg = phys_geo(pc.phys())
        markers["PHYS"] = ensure_bounds(pg, mn, mx, "Fisica")
        entry = {"nombre": pc.name, "tipo": pc.kind, "tamano_m": [round(c, 3) for c in (mx - mn)],
                 "centro": [round(c, 3) for c in origin], "triangulos": {}, "marcadores_caja": markers}
        lod_bytes = []
        for i, lv in enumerate(LEVELS):
            ob = mesh_object(pc.name + SUFFIX[lv], geos[i], origin, colls[lv], lv, pc.name, pc.kind)
            objs[lv].append(ob)
            tris, nv, sm = submesh_stats(ob)
            entry["triangulos"][lv] = tris
            lod_bytes.append(est_bytes(tris, nv, sm))
        ob = mesh_object(pc.name + SUFFIX["PHYS"], pg, origin, colls["PHYS"], "PHYS", pc.name, pc.kind)
        objs["PHYS"].append(ob)
        entry["triangulos"]["PHYS"] = len(pg.faces) and sum(len(f) - 2 for f in pg.faces)
        radius = (mx - mn).length / 2
        cost, w = streaming_cost(radius, lod_bytes)
        entry["radio_m"] = round(radius, 2)
        entry["peso_lod"] = [round(x, 4) for x in w]
        entry["li_descarga_est"] = round(cost, 3)
        entry["caras_sl"] = hmats
        li_total += cost
        dims_ok = min(mx - mn) >= 0.5
        if pc.kind == "estructura" and not dims_ok:
            report["avisos"].append(f"{pc.name}: alguna dimensión < 0,5 m; SL usará casco convexo")
        report["piezas"].append(entry)

    for lv in LEVELS + ["PHYS"]:
        report["niveles"][lv] = {"objetos": len(objs[lv]),
                                 "triangulos": sum(p["triangulos"][lv] for p in report["piezas"])}

    n = len(report["piezas"])
    report["li_estimado"] = {
        "descarga_total": round(li_total, 1),
        "servidor_total": n * 0.5,
        "estimacion": round(max(li_total, n * 0.5), 1),
        "nota": "Estimación con la fórmula de streaming cost del visor y un tamaño comprimido aproximado. "
                "La física no se estima: con Prim/None bien asignados no debería dominar. "
                "El valor real es el que muestre el visor al subir (botón Calculate weights & fee).",
    }
    # huella
    allmn = Vector((1e9, 1e9, 1e9))
    allmx = Vector((-1e9, -1e9, -1e9))
    for p in report["piezas"]:
        c, t = Vector(p["centro"]), Vector(p["tamano_m"])
        allmn = Vector(map(min, allmn, c - t / 2))
        allmx = Vector(map(max, allmx, c + t / 2))
    size = allmx - allmn
    report["huella"] = {"x_m": round(size.x, 2), "y_m": round(size.y, 2), "alto_m": round(size.z, 2),
                        "area_m2": round(size.x * size.y, 1), "limite_m2": 1011.5,
                        "porcentaje_parcela": round(100 * size.x * size.y / 2023, 1)}

    if export:
        bpy.context.view_layer.update()
        names = {"HIGH": "Foso_V2_HIGH.dae", "MEDIUM": "Foso_V2_MEDIUM.dae", "LOW": "Foso_V2_LOW.dae",
                 "LOWEST": "Foso_V2_LOWEST.dae", "PHYS": "Foso_V2_PHYS.dae"}
        for lv, fn in names.items():
            write_dae(os.path.join(OUT, fn), objs[lv])
        report["archivos"] = list(names.values())

    report["segundos"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "Informe_V2.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if save:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Foso_V2.blend"), compress=True)
    return report, objs


if __name__ == "__main__":
    rep, _ = build(save="--no-save" not in sys.argv, export="--no-export" not in sys.argv)
    print(json.dumps({k: rep[k] for k in ("niveles", "li_estimado", "huella")}, ensure_ascii=False, indent=1))
    for a in rep["avisos"]:
        print("AVISO:", a)
    top = sorted(rep["piezas"], key=lambda p: -p["li_descarga_est"])[:15]
    for p in top:
        print(f"{p['nombre']:<28} r={p['radio_m']:<6} LI~{p['li_descarga_est']:<6} {p['triangulos']}")

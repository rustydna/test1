"""Construye el Foso V3 completo: Blender, DAE por nivel, auditoría y estimación de LI.

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

import pieces_v3 as P  # noqa: E402
from collada_static import write_dae  # noqa: E402
from geo import FACE_MATS, MATS, SMOOTH_ANGLE, UV_TILE, Geo  # noqa: E402
from mathutils import Matrix  # noqa: E402,F401

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "salida")
LEVELS = ["HIGH", "MEDIUM", "LOW", "LOWEST"]
SUFFIX = {"HIGH": "", "MEDIUM": "_LOD2", "LOW": "_LOD1", "LOWEST": "_LOD0", "PHYS": "_PHYS"}
COLL = {"HIGH": "MALLA | HIGH", "MEDIUM": "LOD | MEDIUM", "LOW": "LOD | LOW", "LOWEST": "LOD | LOWEST",
        "PHYS": "FISICA"}
COLORS = {"Llama": (1.0, 0.45, 0.1), "Piedra": (0.42, 0.40, 0.37), "Suelo": (0.25, 0.22, 0.19),
          "Tela": (0.38, 0.34, 0.28), "Hueso": (0.72, 0.66, 0.55), "Agua": (0.05, 0.09, 0.1),
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


def hull_geo(g, pts):
    bm = bmesh.new()
    for p in pts:
        bm.verts.new(p)
    res = bmesh.ops.convex_hull(bm, input=bm.verts)
    for f in bm.faces:
        if f.is_valid:
            g.face([v.co.copy() for v in f.verts], "Fisica", f.normal.copy())
    bm.free()


def decimate(g, target):
    """Reduce una geometría a ~target triángulos con el Decimate de Blender (para MEDIUM/LOW automáticos)."""
    if g.tri_count() <= target or not g.faces:
        return _copy(g)
    mats = sorted(set(g.mats), key=MATS.index)
    me = bpy.data.meshes.new("_dec")
    me.from_pydata([tuple(v) for v in g.verts], [], g.faces)
    for p, m in zip(me.polygons, g.mats):
        p.material_index = mats.index(m)
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1.5e-4)
    bmesh.ops.triangulate(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new("_dec", me)
    bpy.context.scene.collection.objects.link(ob)
    mod = ob.modifiers.new("d", "DECIMATE")
    mod.ratio = max(0.005, target / max(len(me.polygons), 1))
    mod.use_collapse_triangulate = True
    dg = bpy.context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    m2 = ev.to_mesh()
    out = Geo()
    out.verts = [v.co.copy() for v in m2.vertices]
    out.faces = [tuple(p.vertices) for p in m2.polygons]
    out.mats = [mats[min(p.material_index, len(mats) - 1)] for p in m2.polygons]
    ev.to_mesh_clear()
    bpy.data.objects.remove(ob)
    bpy.data.meshes.remove(me)
    return out


def phys_geo(boxes):
    g = Geo()
    for b in boxes:
        if b[0] == "CASCO":
            hull_geo(g, b[1])
            continue
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
                bsdf.inputs["Emission Strength"].default_value = 7.0
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


def uv_llamas(me, present, uvl):
    """UV 0-1 para el flipbook de fuego (cara 7): mapeado cilíndrico por isla.

    Cada isla conectada de polígonos "Llama" (una llama) recibe
    u = ángulo alrededor de su eje vertical / 2π y v = altura relativa en la
    isla, de modo que el fotograma entero del flipbook cubre la llama.
    """
    if "Llama" not in present:
        return
    im = present.index("Llama")
    polys = [p for p in me.polygons if p.material_index == im]
    padre = {}

    def raiz(a):
        while padre.setdefault(a, a) != a:
            padre[a] = padre[padre[a]]
            a = padre[a]
        return a

    for p in polys:
        vs = list(p.vertices)
        for v in vs[1:]:
            padre[raiz(v)] = raiz(vs[0])
    islas = {}
    for p in polys:
        islas.setdefault(raiz(p.vertices[0]), []).append(p)
    for ps in islas.values():
        vids = {v for p in ps for v in p.vertices}
        cos = [me.vertices[v].co for v in vids]
        cx = (min(c.x for c in cos) + max(c.x for c in cos)) / 2
        cy = (min(c.y for c in cos) + max(c.y for c in cos)) / 2
        z0 = min(c.z for c in cos)
        dz = max(max(c.z for c in cos) - z0, 1e-6)
        rmax = max(max(math.hypot(c.x - cx, c.y - cy) for c in cos), 1e-6)
        for p in ps:
            pc = p.center
            if abs(p.normal.z) > 0.7:      # tapa de la base: planar, dentro de 0-1
                for li in p.loop_indices:
                    co = me.vertices[me.loops[li].vertex_index].co
                    uvl.data[li].uv = (0.5 + 0.45 * (co.x - cx) / rmax, (co.z - z0) / dz)
                continue
            uvs = []
            for li in p.loop_indices:
                co = me.vertices[me.loops[li].vertex_index].co
                dx, dy = co.x - cx, co.y - cy
                if dx * dx + dy * dy < 1e-10:          # vértice sobre el eje: ángulo del polígono
                    dx, dy = pc.x - cx, pc.y - cy
                uvs.append([(math.atan2(dy, dx) / (2 * math.pi)) % 1.0, (co.z - z0) / dz])
            # costura: el polígono que cruza u=0/1 no debe recorrer la textura
            # entera; se pega al borde (margen transparente del fotograma) para
            # no invadir el fotograma vecino del flipbook
            us = [uv[0] for uv in uvs]
            if max(us) - min(us) > 0.5:
                for uv in uvs:
                    uv[0] = 1.0 if uv[0] < 0.5 else uv[0]
            for li, uv in zip(p.loop_indices, uvs):
                uvl.data[li].uv = uv


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
        if m == "Llama":
            continue
        for li in p.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co + origin
            uvl.data[li].uv = uv_for(co, p.normal, m)
    uv_llamas(me, present, uvl)
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


# ------------------------------------------------------------------ tabla para los scripts LSL
KIND_CODE = {"estructura": 0, "puerta": 1, "deco": 2, "luz": 3, "mueble": 4, "agua": 5}
LSL_DIR = os.path.join(ROOT, "lsl")


def _v(v):
    return "<" + ",".join(f"{c:.3f}" for c in v) + ">"


def write_lsl_table(report):
    """Inserta en los scripts LSL la tabla de piezas (nombre, tipo, tamaño, posición respecto al trono).
    Con ella el script reconoce cada primitiva aunque SL haya perdido los nombres al subir."""
    ref = next(p for p in report["piezas"] if p["nombre"] == "N_Trono")
    rc = Vector(ref["centro"])
    rows = []
    for p in report["piezas"]:
        off = Vector(p["centro"]) - rc
        rows.append(f'"{p["nombre"]}", {KIND_CODE[p["tipo"]]}, {_v(p["tamano_m"])}, {_v(off)}')
    table = "list TABLA = [\n    " + ",\n    ".join(rows) + "];"
    silla = next(p for p in report["piezas"] if p["nombre"] == "C04_Silla")
    consts = f"vector PIVOTE_SILLA = {_v(silla['pivote_rel'])};"
    seats = []
    for p in report["piezas"]:
        if "asiento" in p:
            a = p["asiento"]
            seats.append(f'"{p["nombre"]}", {_v(a["offset"])}, {a["giro"]}, "{a["anim"]}", "{a["reserva"]}"')
    consts += "\nlist ASIENTOS = [\n    " + ",\n    ".join(seats) + "];"
    for fn in os.listdir(os.path.join(LSL_DIR, "plantillas")):
        src = open(os.path.join(LSL_DIR, "plantillas", fn), encoding="utf-8").read()
        src = src.replace("//@@TABLA@@", table).replace("//@@CONSTANTES@@", consts)
        with open(os.path.join(LSL_DIR, fn), "w", encoding="utf-8") as f:
            f.write("// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/" + fn + " (no editar a mano)\n" + src)


# ------------------------------------------------------------------ principal
def build(save=True, export=True):
    t0 = time.time()
    os.makedirs(OUT, exist_ok=True)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.name = "Foso V3"
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
        if pc.kind in ("deco", "mueble", "luz"):
            # LOD según el radio: en SL, a radio pequeño pesa el LOWEST; a radio medio, LOW y MEDIUM
            g0 = pc.build(0)
            a0, b0 = g0.bounds()
            rad = (b0 - a0).length / 2
            pc.lod_map = (0, 0, 1, 3) if rad < 1.2 else ((0, 1, 2, 3) if rad < 2.2 else (0, 1, 3, 3))
            cache[0] = g0
        for m in pc.lod_map:
            if m not in cache:
                cache[m] = pc.build(m)
        geos = [cache[pc.lod_map[0]]] + [_copy(cache[m]) for m in pc.lod_map[1:]]
        if pc.kind in ("deco", "mueble", "luz", "puerta") and pc.lod_map == (0, 0, 1, 3):
            geos[1] = decimate(geos[1], 300)
            geos[2] = decimate(geos[2], 40)
        if pc.kind in ("deco", "mueble", "luz") and pc.lod_map != (0, 0, 1, 3):
            # presupuesto de triángulos por radio (los niveles que más pesan en el coste de SL)
            hi = cache[0]
            if pc.lod_map == (0, 1, 2, 3):
                geos[1] = decimate(geos[1], min(800, max(60, hi.tri_count() // 4)))
                geos[2] = decimate(geos[2], min(120, max(16, hi.tri_count() // 20)))
            else:
                geos[1] = decimate(geos[1], 160)
        if not geos[0].verts:
            report["avisos"].append(f"{pc.name}: HIGH vacío")
            continue
        mn, mx = geos[0].bounds()
        if getattr(pc, "fire", False):
            # el centro de la pieza queda en la base de la llama: SL emite luz y partículas desde ahí
            lz = [geos[0].verts[i] for f, m in zip(geos[0].faces, geos[0].mats) if m == "Llama" for i in f]
            c = sum(lz, Vector()) / len(lz)
            c.z = min(v.z for v in lz) + 0.04
            h = Vector([max(mx[i] - c[i], c[i] - mn[i]) for i in range(3)])
            mn, mx = c - h, c + h
            ensure_bounds(geos[0], mn, mx, geos[0].mats[0])
        if "Agua" not in geos[0].mats:
            # caras fijas: cada pieza lleva las 8 caras en el mismo orden (relleno diminuto en la esquina)
            for k, m in enumerate(FACE_MATS):
                if m not in geos[0].mats:
                    e = MARK
                    o = mn + Vector((e * (1 + 3 * k), e, 0))   # cada relleno en su sitio: al soldar no se fusionan
                    geos[0].face([o, o + Vector((e, 0, 0)), o + Vector((0, e, 0))], m, (0, 0, -1))
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
        entry = {"nombre": pc.name, "tipo": pc.kind, "rol": getattr(pc, "role", ""), "fuego": getattr(pc, "fire", False),
                 "tamano_m": [round(c, 3) for c in (mx - mn)],
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
        if pc.name in P.SITS:
            pt, yaw, anim, fb = P.SITS[pc.name]
            entry["asiento"] = {"offset": [round(c, 3) for c in (pt - origin)], "giro": yaw, "anim": anim, "reserva": fb}
        if hasattr(pc, "pivot"):
            entry["pivote_rel"] = [round(c, 3) for c in (pc.pivot - origin)]
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
        names = {"HIGH": "Foso_V3_HIGH.dae", "MEDIUM": "Foso_V3_MEDIUM.dae", "LOW": "Foso_V3_LOW.dae",
                 "LOWEST": "Foso_V3_LOWEST.dae", "PHYS": "Foso_V3_PHYS.dae"}
        for lv, fn in names.items():
            write_dae(os.path.join(OUT, fn), objs[lv])
        report["archivos"] = list(names.values())

    write_lsl_table(report)
    report["segundos"] = round(time.time() - t0, 1)
    with open(os.path.join(OUT, "Informe_V3.json"), "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=1)
    if save:
        bpy.context.preferences.filepaths.save_version = 0
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "Foso_V3.blend"), compress=True)
    return report, objs


if __name__ == "__main__":
    rep, _ = build(save="--no-save" not in sys.argv, export="--no-export" not in sys.argv)
    print(json.dumps({k: rep[k] for k in ("niveles", "li_estimado", "huella")}, ensure_ascii=False, indent=1))
    for a in rep["avisos"]:
        print("AVISO:", a)
    top = sorted(rep["piezas"], key=lambda p: -p["li_descarga_est"])[:15]
    for p in top:
        print(f"{p['nombre']:<28} r={p['radio_m']:<6} LI~{p['li_descarga_est']:<6} {p['triangulos']}")

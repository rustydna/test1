"""Pruebas del Foso V2. Regenera el modelo y comprueba los DAE y la física.

    python foso_mazmorra/tests/test_foso.py
"""

import json
import math
import os
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

import bpy  # noqa: E402,F401

import build_foso  # noqa: E402
import pieces as P  # noqa: E402
import qa_fisica  # noqa: E402

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
OUT = os.path.join(ROOT, "salida")
LEVELS = {"HIGH": "", "MEDIUM": "_LOD2", "LOW": "_LOD1", "LOWEST": "_LOD0", "PHYS": "_PHYS"}
RESULTS = []


def case(fn):
    try:
        fn()
        RESULTS.append((fn.__name__, True, ""))
    except Exception:
        RESULTS.append((fn.__name__, False, traceback.format_exc()))
    return fn


def load(level):
    root = ET.parse(os.path.join(OUT, f"Foso_V2_{level}.dae")).getroot()
    geoms = {}
    for g in root.iterfind(".//c:geometry", NS):
        name = g.get("name")
        pos = list(map(float, g.find(".//c:source[@id='%s-mesh-positions']/c:float_array" % name, NS).text.split()))
        nrm = g.find(".//c:source[@id='%s-mesh-normals']/c:float_array" % name, NS)
        uvs = g.find(".//c:source[@id='%s-mesh-map0']/c:float_array" % name, NS)
        tris = []
        for t in g.iterfind(".//c:triangles", NS):
            idx = list(map(int, t.find("c:p", NS).text.split()))
            assert len(idx) == int(t.get("count")) * 9, name
            tris.append((t.get("material"), idx))
        geoms[name] = dict(pos=pos, nrm=len(nrm.text.split()) // 3,
                           uv=len(uvs.text.split()) // 2 if uvs.text else 0, tris=tris)
    nodes = {}
    for n in root.iterfind(".//c:visual_scene/c:node", NS):
        m = list(map(float, n.find("c:matrix", NS).text.split()))
        nodes[n.get("name")] = (m[3], m[7], m[11])
    return root, geoms, nodes


def bounds(geom, t):
    p = geom["pos"]
    xs, ys, zs = p[0::3], p[1::3], p[2::3]
    return ((min(xs) + t[0], min(ys) + t[1], min(zs) + t[2]), (max(xs) + t[0], max(ys) + t[1], max(zs) + t[2]))


print("Regenerando el modelo...")
REPORT, _ = build_foso.build(save=True, export=True)
DATA = {lv: load(lv) for lv in LEVELS}


@case
def mismos_objetos_en_todos_los_niveles():
    base = set(DATA["HIGH"][1])
    assert len(base) == len(P.PIECES) > 100
    for lv, suf in LEVELS.items():
        names = set(DATA[lv][1])
        assert names == {b + suf for b in base}, lv


@case
def sin_imagenes_ni_texturas():
    for lv in LEVELS:
        root = DATA[lv][0]
        assert root.find(".//c:library_images", NS) is None
        assert root.find(".//c:image", NS) is None
        assert root.find(".//c:texture", NS) is None


@case
def indices_validos():
    for lv in LEVELS:
        for name, g in DATA[lv][1].items():
            nv = len(g["pos"]) // 3
            for _, idx in g["tris"]:
                assert max(idx[0::3]) < nv and max(idx[1::3]) < g["nrm"] and max(idx[2::3]) < g["uv"], (lv, name)


@case
def materiales_de_cada_lod_dentro_del_high():
    for name, g in DATA["HIGH"][1].items():
        hm = [m for m, _ in g["tris"]]
        for lv in ("MEDIUM", "LOW", "LOWEST"):
            lm = [m for m, _ in DATA[lv][1][name + LEVELS[lv]]["tris"]]
            assert set(lm) <= set(hm), (name, lv, lm, hm)
            assert len(hm) <= 8, name


@case
def misma_caja_en_todos_los_niveles():
    """SL estira cada LOD y la física hasta la caja del HIGH: deben coincidir."""
    for name, g in DATA["HIGH"][1].items():
        hb = bounds(g, DATA["HIGH"][2][name])
        for lv, suf in LEVELS.items():
            ob = DATA[lv][1][name + suf]
            b = bounds(ob, DATA[lv][2][name + suf])
            for a, c in zip(hb[0] + hb[1], b[0] + b[1]):
                assert abs(a - c) < 2e-3, (name, lv, hb, b)


@case
def triangulos_no_degenerados():
    for lv in ("HIGH", "MEDIUM", "LOW", "LOWEST"):
        bad = 0
        for name, g in DATA[lv][1].items():
            p = g["pos"]
            for _, idx in g["tris"]:
                for k in range(0, len(idx), 9):
                    a, b, c = (p[3 * idx[k + o]: 3 * idx[k + o] + 3] for o in (0, 3, 6))
                    u = [b[i] - a[i] for i in range(3)]
                    v = [c[i] - a[i] for i in range(3)]
                    cr = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
                    if math.sqrt(sum(x * x for x in cr)) < 1e-9:
                        bad += 1
        assert bad == 0, (lv, bad)


@case
def huella_dentro_de_media_parcela():
    h = REPORT["huella"]
    assert h["area_m2"] <= 1011.5, h


@case
def land_impact_estimado_bajo_objetivo():
    li = REPORT["li_estimado"]["estimacion"]
    assert li <= 130, li  # objetivo 150 con margen para el error de la estimación


@case
def piezas_con_fisica_prim_no_bajan_de_medio_metro():
    for p in REPORT["piezas"]:
        if p["tipo"] == "estructura":
            assert min(p["tamano_m"]) >= 0.5, p["nombre"]


@case
def llamas_en_la_cara_0():
    for p in REPORT["piezas"]:
        if "Llama" in p["caras_sl"]:
            assert p["caras_sl"][0] == "Llama", p["nombre"]


@case
def circulacion_completa():
    r = qa_fisica.run()
    assert r["todo_accesible"], r["accesible"]
    assert r["celdas_atravesables"] == 0, r["atravesables_muestra"]
    assert r["puntos_alcanzables_sin_suelo"] == 0
    assert r["celdas_pared_invisible"] <= 10, r["pared_invisible_por_pieza_m2"]


@case
def nombres_que_usan_los_scripts_lsl():
    names = {p.name for p in P.PIECES}
    lsl = open(os.path.join(ROOT, "lsl", "foso_puertas.lsl"), encoding="utf-8").read()
    assert "G_Hoja_O" in names and "G_Hoja_E" in names and "G_Rastrillo" in names
    assert sum(1 for n in names if n.endswith("_Puerta")) == 8
    assert '"G_Rastrillo"' in lsl and '"G_Hoja_O"' in lsl


fails = [r for r in RESULTS if not r[1]]
for name, ok, err in RESULTS:
    print(("OK   " if ok else "FALLO"), name)
    if err:
        print(err)
print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} pruebas correctas")
with open(os.path.join(OUT, "Pruebas_V2.json"), "w", encoding="utf-8") as f:
    json.dump({n: ok for n, ok, _ in RESULTS}, f, ensure_ascii=False, indent=1)
sys.exit(1 if fails else 0)

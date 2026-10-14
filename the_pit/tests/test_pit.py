"""Tests for The Pit. Rebuilds the model and checks the DAE files and the physics.

    python the_pit/tests/test_pit.py
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

import build_pit  # noqa: E402
import pieces_v3 as P  # noqa: E402
from geo import FACE_MATS  # noqa: E402
import qa_physics  # noqa: E402

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
OUT = os.path.join(ROOT, "output")
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
    root = ET.parse(os.path.join(OUT, "ThePit" + LEVELS[level] + ".dae")).getroot()
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


print("Rebuilding the model...")
REPORT, _ = build_pit.build(save=True, export=True)
DATA = {lv: load(lv) for lv in LEVELS}


@case
def same_objects_in_every_level():
    base = set(DATA["HIGH"][1])
    assert len(base) == len(P.PIECES) > 100
    assert len(base) <= 150, len(base)   # prims when rezzed
    for lv, suf in LEVELS.items():
        names = set(DATA[lv][1])
        assert names == {b + suf for b in base}, lv


@case
def no_images_or_textures():
    for lv in LEVELS:
        root = DATA[lv][0]
        assert root.find(".//c:library_images", NS) is None
        assert root.find(".//c:image", NS) is None
        assert root.find(".//c:texture", NS) is None


@case
def valid_indices():
    for lv in LEVELS:
        for name, g in DATA[lv][1].items():
            nv = len(g["pos"]) // 3
            for _, idx in g["tris"]:
                assert max(idx[0::3]) < nv and max(idx[1::3]) < g["nrm"] and max(idx[2::3]) < g["uv"], (lv, name)


@case
def lod_materials_within_high():
    for name, g in DATA["HIGH"][1].items():
        hm = [m for m, _ in g["tris"]]
        for lv in ("MEDIUM", "LOW", "LOWEST"):
            lm = [m for m, _ in DATA[lv][1][name + LEVELS[lv]]["tris"]]
            assert set(lm) <= set(hm), (name, lv, lm, hm)
            assert len(hm) <= 8, name


@case
def fixed_pbr_faces():
    """Every piece (except the water) has the same 8 materials, so once SL sorts the faces by
    material name (LLModel::sortVolumeFacesByMaterialName) each block lands on the same face in
    every piece, and pit_control / pit_fire use exactly those face numbers."""
    import re
    for name, g in DATA["HIGH"][1].items():
        mats = [m.replace("-material", "") for m, _ in g["tris"]]
        if mats == ["Water"]:
            continue
        assert sorted(mats) == sorted(FACE_MATS), (name, mats)
    sl_order = sorted(FACE_MATS, key=str.lower)                  # face index as SL builds it
    spanish = {"Stone": "Piedra", "Floor": "Suelo", "Wood": "Madera", "Iron": "Hierro", "Cloth": "Tela",
               "Bone": "Hueso", "Straw": "Paja", "Flame": "Llama"}  # material names of the first release
    sl_order_es = [m for _, m in sorted((spanish[m].lower(), m) for m in FACE_MATS)]
    lsl = open(os.path.join(ROOT, "lsl", "pit_control.lsl"), encoding="utf-8").read()
    blocks = re.search(r'list BLOCKS = \[([^\]]*)\]', lsl).group(1).replace('"', "").replace(" ", "").split(",")
    for var, order in (("FACES_EN", sl_order), ("FACES_ES", sl_order_es)):
        faces = [int(x) for x in re.search(r"list " + var + r" = \[([^\]]*)\]", lsl).group(1).split(",")]
        assert faces == [order.index(b) for b in blocks[:7]], (var, faces)
    fire = open(os.path.join(ROOT, "lsl", "pit_fire.lsl"), encoding="utf-8").read()
    assert "integer FLAME = %d;" % sl_order.index("Flame") in fire
    assert sl_order.index("Flame") == sl_order_es.index("Flame")


@case
def same_bbox_every_level():
    """SL stretches every LOD and the physics to the HIGH box: they must match."""
    for name, g in DATA["HIGH"][1].items():
        hb = bounds(g, DATA["HIGH"][2][name])
        for lv, suf in LEVELS.items():
            ob = DATA[lv][1][name + suf]
            b = bounds(ob, DATA[lv][2][name + suf])
            for a, c in zip(hb[0] + hb[1], b[0] + b[1]):
                assert abs(a - c) < 2e-3, (name, lv, hb, b)


@case
def no_degenerate_triangles():
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
def footprint_within_half_parcel():
    h = REPORT["footprint"]
    assert h["area_m2"] <= 1011.5, h


@case
def estimated_land_impact_under_target():
    li = REPORT["li_estimate"]["estimate"]
    assert li <= 135, li  # target 150, with margin for the error of the estimate


@case
def prim_physics_pieces_not_below_half_metre():
    for p in REPORT["pieces"]:
        if p["kind"] == "structure":
            assert min(p["size_m"]) >= 0.5, p["name"]


@case
def fire_pieces_centred_on_flame():
    """SL emits the light and the particles from the piece centre: it must be at the base of the flame."""
    for p in REPORT["pieces"]:
        if p["fire"]:
            name = p["name"]
            g = DATA["HIGH"][1][name]
            t = DATA["HIGH"][2][name]
            pos = g["pos"]
            fl = [i for m, idx in g["tris"] if m == "Flame-material" for i in idx[0::3]]
            zs = [pos[3 * i + 2] + t[2] for i in fl]
            xs = [pos[3 * i] + t[0] for i in fl]
            ys = [pos[3 * i + 1] + t[1] for i in fl]
            c = (sum(xs) / len(xs), sum(ys) / len(ys), min(zs))
            d = math.dist(c, t)
            assert d < 0.25, (name, d)


@case
def circulation_with_and_without_scripts():
    """Every room can be entered both with the physics configured and WITHOUT running any script
    (all meshes as Convex Hull, the V2 failure)."""
    r = qa_physics.run()
    assert r["all_reachable_configured"], r["configured"]
    assert r["all_reachable_no_scripts"], r["no_scripts"]


@case
def lsl_scripts_consistent_with_model():
    import re
    names = {p.name for p in P.PIECES}
    assert sum(1 for n in names if n.endswith("_Door")) == 8
    lsl_dir = os.path.join(ROOT, "lsl")
    core = open(os.path.join(lsl_dir, "pit_core.lsl"), encoding="utf-8").read()
    table = set(re.findall(r'^    "([A-Za-z0-9_]+)", \d,', core, re.M))
    assert table == names, names ^ table
    for fn in os.listdir(lsl_dir):
        if fn.endswith(".lsl"):
            src = open(os.path.join(lsl_dir, fn), encoding="utf-8").read()
            assert "//@@" not in src, fn
            # every piece name quoted in a script must exist in the model (or be a prefix of one)
            for lit in re.findall(r'"([CGNVPTAM]\d?\d?[WE]?_[A-Za-z_0-9]+)"', src):
                if not lit.startswith(("pit_", "sit:", "p:", "opt:")):
                    assert lit in names or any(n.startswith(lit) for n in names), (fn, lit)
            assert src.count("{") == src.count("}"), fn
            assert src.count("(") == src.count(")"), fn



@case
def every_feature_can_be_switched_off():
    import re
    lsl_dir = os.path.join(ROOT, "lsl")
    settings = open(os.path.join(lsl_dir, "pit_control.lsl"), encoding="utf-8").read()
    block = settings[settings.index("list FEATURES"):settings.index("list CATEGORIES")]
    features = re.findall(r'^\s+"([a-z_]+)",\s+\d,', block, re.M)
    assert len(features) == len(set(features)) >= 40, features
    used = set()
    for fn in os.listdir(lsl_dir):
        if fn.endswith(".lsl"):
            src = open(os.path.join(lsl_dir, fn), encoding="utf-8").read()
            used |= set(re.findall(r'\bopt\("([a-z_]+)"\)', src))
            if "string feature(string nm)" in src:      # pit_rooms: one switch per room, looked up by piece
                body = src[src.index("string feature(string nm)"):src.index("integer active(")]
                used |= set(re.findall(r'return "([a-z_]+)";', body))
    assert set(features) - used == set(), ("switches that no script reads", set(features) - used)
    assert used - set(features) == set(), ("switches read but missing from the settings menu", used - set(features))


@case
def lsl_scripts_compile_and_are_english():
    import re
    import shutil
    import subprocess
    lsl_dir = os.path.join(ROOT, "lsl")
    files = sorted(fn for fn in os.listdir(lsl_dir) if fn.endswith(".lsl"))
    for fn in files:
        src = open(os.path.join(lsl_dir, fn), encoding="utf-8").read()
        assert not re.search("[\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00bf\u00a1]", src), fn
    lslint = os.environ.get("LSLINT") or shutil.which("lslint")
    if not lslint:
        print("(lslint not found: set LSLINT=/path/to/lslint to also compile the scripts)")
        return
    for fn in files:
        out = subprocess.run([lslint, "-m", os.path.join(lsl_dir, fn)], capture_output=True, text=True)
        text = out.stdout + out.stderr
        assert "Errors: 0" in text, (fn, text)


@case
def pose_animations_are_looping_sl_anims():
    import struct
    names = {a for p in P.PIECES if p.name in P.SITS for a in [P.SITS[p.name][2]]}
    anim_dir = os.path.join(OUT, "animations")
    for n in names:
        data = open(os.path.join(anim_dir, n + ".anim"), "rb").read()
        version, sub, priority, duration = struct.unpack_from("<HHif", data, 0)
        end = data.index(b"\0", 12)
        loop_in, loop_out, loop, ease_in, ease_out, hand, joints = struct.unpack_from("<ffiffII", data, end + 1)
        assert (version, sub) == (1, 0) and priority == 4 and loop == 1 and joints == 19, (n, version, priority, loop, joints)
        assert 0 < duration and loop_out == duration, n

fails = [r for r in RESULTS if not r[1]]
for name, ok, err in RESULTS:
    print(("OK  " if ok else "FAIL"), name)
    if err:
        print(err)
print(f"\n{len(RESULTS) - len(fails)}/{len(RESULTS)} tests passed")
with open(os.path.join(OUT, "Tests.json"), "w", encoding="utf-8") as f:
    json.dump({n: ok for n, ok, _ in RESULTS}, f, ensure_ascii=False, indent=1)
sys.exit(1 if fails else 0)

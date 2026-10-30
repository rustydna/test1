"""Cave test suite: the built models, the scripts and the package must all pass before delivery.

    python3 cave/scripts/build_cave.py && LSLINT=/path/to/lslint python3 villa/tests/test_villa.py

Reads villa/output/Report.json and villa/output/models/*.dae (written by build_villa.py).
"""

import glob
import json
import os
import re
import subprocess
import sys
import traceback
import xml.etree.ElementTree as ET

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
MODELS = os.path.join(OUT, "models")
LSL = os.path.join(ROOT, "lsl")
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow"]
NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
CASES = []
REPORT = json.load(open(os.path.join(OUT, "Report.json"))) if os.path.exists(os.path.join(OUT, "Report.json")) else None
LI_LIMIT = 400.0
LI_MARGIN = 0.92          # the estimate must stay 8 % under the limit


def case(fn):
    CASES.append(fn)
    return fn


def dae(path):
    root = ET.parse(path).getroot()
    geos = {}
    for g in root.iterfind(".//c:geometry", NS):
        mats, tris, bad = [], 0, 0
        pos = g.find(".//c:source/c:float_array", NS)
        nverts = int(pos.get("count")) // 3
        for t in g.iterfind(".//c:triangles", NS):
            mats.append(t.get("material"))
            count = int(t.get("count"))
            tris += count
            stride = len(t.findall("c:input", NS))
            idx = [int(x) for x in (t.find("c:p", NS).text or "").split()]
            if len(idx) != count * 3 * stride:
                bad += 1
            vi = idx[0::stride]
            if vi and (max(vi) >= nverts or min(vi) < 0):
                bad += 1
        geos[g.get("name")] = {"mats": mats, "tris": tris, "bad": bad}
    return geos


def sets():
    return sorted({os.path.basename(p)[:-4] for p in glob.glob(os.path.join(MODELS, "*.dae"))
                   if not re.search(r"_(LOD[012]|PHYS)\.dae$", p)})


# ------------------------------------------------------------------ models
@case
def report_exists_and_clean():
    assert REPORT, "run cave/scripts/build_cave.py first"
    assert not REPORT["warnings"], REPORT["warnings"][:10]
    assert REPORT["linksets"], "no linkset built"


@case
def five_files_per_linkset_same_objects():
    for s in sets():
        names = None
        for suf in ("", "_LOD2", "_LOD1", "_LOD0", "_PHYS"):
            p = os.path.join(MODELS, s + suf + ".dae")
            assert os.path.exists(p), p
            g = dae(p)
            n = [k[: -len(suf)] if suf and k.endswith(suf) else k for k in g]
            if names is None:
                names = n
            assert n == names, (s, suf, set(n) ^ set(names))


@case
def every_piece_has_the_eight_fixed_faces():
    for s in sets():
        for name, g in dae(os.path.join(MODELS, s + ".dae")).items():
            mats = [m.replace("-material", "") for m in g["mats"]]
            if mats == ["water"]:
                continue
            assert sorted(mats) == SLOTS, (name, mats)


@case
def lods_use_only_high_slots_and_valid_indices():
    for s in sets():
        hi = dae(os.path.join(MODELS, s + ".dae"))
        for suf in ("_LOD2", "_LOD1", "_LOD0"):
            for name, g in dae(os.path.join(MODELS, s + suf + ".dae")).items():
                base = name[: -len(suf)]
                assert set(g["mats"]) <= set(hi[base]["mats"]), (name, g["mats"])
                assert g["bad"] == 0, name
                assert g["tris"] <= hi[base]["tris"] + 4, (name, g["tris"], hi[base]["tris"])


@case
def same_bounding_box_every_level():
    for p in REPORT["pieces"]:
        # the engine marks the HIGH box corners on any level that does not reach them
        assert set(p["markers"]) == {"MEDIUM", "LOW", "LOWEST", "PHYS"}, p["name"]


@case
def linkset_limits():
    for name, ls in REPORT["linksets"].items():
        assert ls["pieces"] <= 256, (name, ls["pieces"])
        x, y, z = ls["size_m"]
        assert x <= 64 and y <= 64 and z <= 40, (name, ls["size_m"])     # any single linkset
        root = ls.get("root")
        assert root and any(p["name"] == root for p in REPORT["pieces"]), (name, root)


@case
def land_impact_per_variant_under_budget():
    roles = REPORT.get("roles") or {}
    site = [n for n, r in roles.items() if r == "site"]
    houses = [n for n, r in roles.items() if r == "house"]
    if not houses:          # no roles declared: every linkset alone must fit
        houses = list(REPORT["linksets"])
    site_li = sum(REPORT["linksets"][n]["li_estimate"] for n in site if n in REPORT["linksets"])
    for h in houses:
        if h not in REPORT["linksets"]:
            continue
        li = site_li + REPORT["linksets"][h]["li_estimate"]
        extra = REPORT.get("variant_extra", {}).get(h, [])
        li += sum(REPORT["linksets"][e]["li_estimate"] for e in extra if e in REPORT["linksets"])
        assert li <= LI_LIMIT * LI_MARGIN, (h, round(li, 1))


@case
def footprint_and_height():
    for name, ls in REPORT["linksets"].items():
        x, y, z = ls["size_m"]
        assert x <= 64 and y <= 64, (name, ls["size_m"])        # one region corner, plenty of room
        assert z <= 45, (name, ls["size_m"])        # masts: 39 m from keel to truck


@case
def no_piece_too_thin_for_prim_physics():
    for p in REPORT["pieces"]:
        if p.get("walkable"):
            assert min(p["size_m"]) >= 0.01, p["name"]


# ------------------------------------------------------------------ scripts
def lsl_files():
    return sorted(glob.glob(os.path.join(LSL, "*.lsl")))


@case
def lsl_scripts_compile():
    lint = os.environ.get("LSLINT")
    files = lsl_files()
    if not files:
        raise AssertionError("no scripts yet in villa/lsl/")
    if not lint:
        raise AssertionError("set LSLINT to the lslint binary")
    for f in files:
        r = subprocess.run([lint, "-m", f], capture_output=True, text=True)
        out = r.stdout + r.stderr
        m = re.search(r"TOTAL::\s*Errors:\s*(\d+)\s*Warnings:\s*(\d+)", out)
        assert m and m.group(1) == "0", (os.path.basename(f), out[-800:])


@case
def lsl_scripts_are_english_ascii_and_small():
    for f in lsl_files():
        src = open(f, encoding="utf-8").read()
        assert all(ord(c) < 128 for c in src), (f, [c for c in src if ord(c) >= 128][:5])
        assert len(src.encode()) < 120000, (f, len(src))      # source size proxy for 64 KB bytecode


@case
def materials_in_scripts_exist():
    cat = os.path.join(ROOT, "docs", "materials.json")
    assert os.path.exists(cat), cat
    names = {v["name"] for vs in json.load(open(cat))["slots"].values() for v in vs}
    glbs = {os.path.basename(p)[:-4] for p in glob.glob(os.path.join(OUT, "pbr_materials", "*.glb"))}
    assert names == glbs, (sorted(names ^ glbs)[:10])
    for f in lsl_files():
        for m in re.findall(r'"(cave_[a-h]_[a-z]+_[a-z0-9_]+|cave_water_[a-z0-9]+)"', open(f).read()):
            assert m in names, (os.path.basename(f), m)


def main():
    ok = 0
    for fn in CASES:
        try:
            fn()
            print("OK  ", fn.__name__)
            ok += 1
        except Exception:  # noqa: BLE001
            print("FAIL", fn.__name__)
            traceback.print_exc(limit=1)
            print()
    print(f"\n{ok}/{len(CASES)} tests passed")
    return 0 if ok == len(CASES) else 1


if __name__ == "__main__":
    sys.exit(main())

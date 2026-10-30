"""Dry-run build that checks the story details: piece bounds unchanged, materials, LI budget.

    python the_pit/scripts/check_story.py            # every piece
    python the_pit/scripts/check_story.py C02_ C03_  # only pieces whose name starts with these

Writes nothing. Prints the estimated land impact (budget: 140) and every piece that grew.
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402,F401

import build_pit  # noqa: E402
from geo import FACE_MATS  # noqa: E402

ROOT = os.path.dirname(HERE)
base = json.load(open(os.path.join(ROOT, "tests", "baseline_bounds.json")))
rep, _ = build_pit.build(save=False, export=False, write=False)
prefixes = tuple(sys.argv[1:])
bad = 0
for p in rep["pieces"]:
    if prefixes and not p["name"].startswith(prefixes):
        continue
    b = base[p["name"]]
    ds = max(abs(x - y) for x, y in zip(p["size_m"], b["size_m"]))
    dc = max(abs(x - y) for x, y in zip(p["center"], b["center"]))
    if ds > 0.002 or dc > 0.002:
        print(f"GREW  {p['name']}: size {b['size_m']} -> {p['size_m']}, centre moved {dc:.3f} m")
        bad += 1
    if p.get("li_download_est", 0) > 6:
        print(f"heavy {p['name']}: LI ~{p['li_download_est']}")
for w in rep["warnings"]:
    print("WARNING", w)
area_now = sum(p.get("li_download_est", 0) for p in rep["pieces"] if not prefixes or p["name"].startswith(prefixes))
area_base = sum(b.get("li", 0) for n, b in base.items() if not prefixes or n.startswith(prefixes))
print(f"land impact of these pieces: {area_now:.1f} (was {area_base:.1f}, +{area_now - area_base:.1f})")
li = rep["li_estimate"]["estimate"]
tris = rep["levels"]["HIGH"]["triangles"]
print(f"\nestimated land impact {li} (budget 140), HIGH triangles {tris}, pieces that grew: {bad}")
sys.exit(1 if bad or li > 140 else 0)

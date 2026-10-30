"""Writes villa/lsl/villa_core.lsl and villa_house.lsl from the templates, filling in the tables
taken from the build report, the material catalogue and the pose data.

    python3 villa/scripts/vlsl.py
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LSL = os.path.join(ROOT, "lsl")
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow", "water"]
SLOT_LABELS = ["Walls", "Floors", "Wood", "Stone", "Fabric", "Metal", "Glass", "Glow", "Water"]
HOUSE_STYLES = {
    "Nautilus": "white,travertine,oak,calacatta,boucle,brass,clear,led,turquoise",
    "Dune": "sand,terrazzo,teak,travertine,linen,bronze,bronze,opal,lagoon",
    "Nocturne": "charcoal,basalt,ebony,nero,velvet,brass,smoked,led,infinity",
}
SCENES = [("Day", (1, 0.92, 0.8), 0.15), ("Golden", (1, 0.78, 0.5), 0.55), ("Evening", (1, 0.8, 0.58), 0.8),
          ("Night", (1, 0.65, 0.4), 0.45), ("Party", (0.75, 0.4, 1), 1.0), ("Off", (1, 1, 1), 0.0)]
LEDS = [("Warm", (1, 0.8, 0.58)), ("Neutral", (1, 0.93, 0.85)), ("Cool", (0.85, 0.92, 1)), ("Amber", (1, 0.62, 0.3)),
        ("Rose", (1, 0.55, 0.65)), ("Violet", (0.7, 0.5, 1)), ("Blue", (0.4, 0.6, 1)), ("Green", (0.5, 1, 0.6)),
        ("Red", (1, 0.25, 0.2))]
TINTS = [("Natural", (1, 1, 1)), ("Ivory", (1, 0.97, 0.9)), ("Sand", (0.93, 0.84, 0.7)), ("Caramel", (0.8, 0.6, 0.42)),
         ("Terracotta", (0.78, 0.45, 0.33)), ("Olive", (0.6, 0.62, 0.42)), ("Sage", (0.66, 0.74, 0.62)),
         ("Ocean", (0.42, 0.62, 0.7)), ("Navy", (0.25, 0.3, 0.45)), ("Plum", (0.5, 0.32, 0.45)),
         ("Blush", (0.95, 0.75, 0.72)), ("Charcoal", (0.3, 0.3, 0.32))]
POOL_LIGHTS = [("Off", (0, 0, 0)), ("Aqua", (0.3, 0.75, 1)), ("White", (0.9, 0.95, 1)), ("Blue", (0.2, 0.4, 1)),
               ("Violet", (0.6, 0.3, 1)), ("Pink", (1, 0.4, 0.7)), ("Green", (0.3, 1, 0.6)), ("Amber", (1, 0.6, 0.25))]
SOUNDS = [("Garden", "villa_garden"), ("Night", "villa_night"), ("Rain", "villa_rain_glass"), ("Surf", "villa_surf"),
          ("Chimes", "villa_chimes"), ("Lounge", "villa_lounge"), ("Pool", "villa_pool_lap"), ("Fire", "villa_fire")]


def v(t):
    return "<" + ", ".join(f"{float(c):.3f}" for c in t) + ">"


def q(s):
    return '"' + s + '"'


def tables():
    rep = json.load(open(os.path.join(ROOT, "output", "Report.json")))
    cat = json.load(open(os.path.join(ROOT, "docs", "materials.json")))
    poses = json.load(open(os.path.join(ROOT, "output", "animations", "poses.json")))
    pieces = {p["name"]: p for p in rep["pieces"]}
    # ---- house script
    seats, kinds = [], []
    for p in rep["pieces"]:
        if "seat" in p:
            s = p["seat"]
            seats.append(f'{q(p["name"])}, {v(s["offset"])}, {s["yaw"]:.1f}, {q(",".join(s["poses"]))}')
        c = 0
        nm = p["name"]
        c |= 1 if p["kind"] == "door" else 0
        c |= 2 if p["kind"] == "light" else 0
        c |= 4 if p["kind"] == "water" else 0
        c |= 8 if p["kind"] == "plant" else 0
        c |= 16 if ("Fireplace" in nm or "Firebowl" in nm) else 0
        c |= 32 if nm in ("Site_Pool", "Site_Spa") else 0
        c |= 64 if nm == "Site_Spa" else 0
        c |= 128 if p.get("phys") == "none" else 0
        c |= 256 if p.get("phys") in ("custom", "floor") else 0
        if c:
            kinds.append(f"{q(nm)}, {c}")
    fit = []
    for name, d in poses.items():
        st = d["sit_target"]
        fit.append(f'{q(name)}, {st["offset_m"][0]:.3f}, {st["offset_m"][2] - st["anchor_height_m"]:.3f}')
    house = ("list SEATS = [\n    " + ",\n    ".join(seats) + "];\n"
             "list KINDS = [\n    " + ",\n    ".join(kinds) + "];\n"
             "list POSE_FIT = [\n    " + ",\n    ".join(fit) + "];")
    # ---- core script
    mats = []
    for si, slot in enumerate(SLOTS):
        for var in cat["slots"].get(slot, []):
            mats.append(f'{si}, {q(var["id"])}, {q(var["label"][:24])}')
    core_c = pieces["Core_Totem"]["center"]
    house_c = next(p["center"] for p in rep["pieces"] if p["name"].endswith("_Floor") and p["linkset"] != "Villa_Core")
    off = [h - c for h, c in zip(house_c, core_c)]
    default = HOUSE_STYLES["Nautilus"].split(",")
    core = "\n".join([
        "list SLOTS = [" + ", ".join(q(s) for s in SLOTS) + "];",
        "list SLOT_LABELS = [" + ", ".join(q(s) for s in SLOT_LABELS) + "];",
        "list DEFAULT_MATS = [" + ", ".join(q(s) for s in default) + "];",
        "list MATS = [\n    " + ",\n    ".join(mats) + "];",
        "list HOUSE_STYLES = [" + ", ".join(f"{q(k)}, {q(s)}" for k, s in HOUSE_STYLES.items()) + "];",
        f"vector HOUSE_OFFSET = {v(off)};      // house root (floor) centre minus Core totem centre",
        "list SCENES = [" + ", ".join(f"{q(n)}, {v(c)}, {lv}" for n, c, lv in SCENES) + "];",
        "list LEDS = [" + ", ".join(f"{q(n)}, {q(v(c))}" for n, c in LEDS) + "];",
        "list TINTS = [" + ", ".join(f"{q(n)}, {q(v(c))}" for n, c in TINTS) + "];",
        "list POOL_LIGHTS = [" + ", ".join(f"{q(n)}, {q(v(c))}" for n, c in POOL_LIGHTS) + "];",
        "list SOUNDS = [" + ", ".join(f"{q(n)}, {q(s)}" for n, s in SOUNDS) + "];",
        'string OPTS_DEFAULT = "chat,sounds,particles,lights";',
    ])
    return house, core


def main():
    house, core = tables()
    for fn, t in (("villa_house.lsl", house), ("villa_core.lsl", core)):
        src = open(os.path.join(LSL, "templates", fn), encoding="utf-8").read().replace("//@@TABLES@@", t)
        with open(os.path.join(LSL, fn), "w", encoding="utf-8") as f:
            f.write(f"// GENERATED by villa/scripts/vlsl.py from lsl/templates/{fn} (edit the template)\n" + src)
        print(os.path.join(LSL, fn), len(src.encode()), "bytes")


if __name__ == "__main__":
    main()

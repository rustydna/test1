"""Writes ship/lsl/bride_main.lsl from its template with the tables from the build report, the
material catalogue and the pose data.   python3 ship/scripts/slsl.py"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow", "water"]
SLOT_LABELS = ["Hull", "Deck", "Wood", "Trim", "Canvas", "Metal", "Glass", "Glow", "Water"]
DEFAULTS = ["tar", "pine", "oak", "gilt", "canvas", "iron", "leaded", "lantern", "sea"]
VILLA_POSES = {"bride_sit_relaxed": "villa_sit_relaxed", "bride_sit_upright": "villa_sit_upright",
               "bride_sit_crossed": "villa_sit_crossed", "bride_sit_curl": "villa_sit_curl", "bride_lounge": "villa_lounge"}
STANDING = ["bride_helm", "bride_kneel", "bride_cage", "bride_dog"]      # anchored on the floor
SEATED_PIT = ["bride_scribe", "bride_guard"]
SCENES = [("Day", 0.0), ("Dusk", 0.6), ("Night", 1.0), ("Dark", 0.15)]
SOUND_SPOTS = [("Bride_Hull_Aft", "bride_sea"), ("Bride_Deck_Quarter", "bride_creak"), ("Bride_Topmast_Main", "bride_wind"),
               ("Bride_Brig", "bride_chains")]
LORE = [
    ("Bride_Figurehead", "The Bride leans into the sea with her veil streaming back. The carver gave her the face of the "
                         "Governor's daughter. Nobody aboard says so aloud."),
    ("Bride_Bell", "STEADFAST, cast into her waist. The Lord had the name filed off. Every sailor can still read it "
                   "with his thumb."),
    ("Bride_Helm", "Two wheels, eight hands in a gale. The spokes are worn pale where Hugh Ormond's hands rest."),
    ("Bride_Cabin_Table", "The chart of the Narrows, the Widow's Tooth circled three times. Dividers, cold wax, a ring of "
                          "wine where the Lord's cup stood."),
    ("Bride_Cabin_Chest", "Iron-bound, triple-locked. Ransom letters, a Crown commission with the name scratched out, "
                          "and a lock of fair hair tied with black ribbon."),
    ("Bride_Capstan", "Twelve men on the bars to raise her anchor. The pawls clack like teeth."),
    ("Bride_Brig", "Below the waterline of every law. The irons are bolted through the hull; the straw is changed when "
                   "someone remembers."),
    ("Bride_Stern", "SECOND BRIDE in new gilt over the old letters. In some lights you can still see STEADFAST beneath."),
]


def v(t):
    return "<" + ", ".join(f"{float(c):.3f}" for c in t) + ">"


def q(s):
    return '"' + s.replace('"', "'") + '"'


def tables():
    rep = json.load(open(os.path.join(ROOT, "output", "Report.json")))
    cat_path = os.path.join(ROOT, "docs", "materials.json")
    cat = json.load(open(cat_path)) if os.path.exists(cat_path) else {"slots": {}}
    vposes = json.load(open(os.path.join(REPO, "villa", "output", "animations", "poses.json")))
    seats, nophys, primphys, lights = [], [], [], []
    root = next(p for p in rep["pieces"] if p["name"] == "Bride_Deck_Main")
    for p in rep["pieces"]:
        if "seat" in p:
            s = p["seat"]
            seats.append(f'{q(p["name"])}, {v(s["offset"])}, {s["yaw"]:.1f}, {q(",".join(s["poses"]))}')
        if p.get("phys") == "none":
            nophys.append(q(p["name"]))
        elif p.get("phys") in ("custom", "floor"):
            primphys.append(q(p["name"]))
        if p["kind"] == "light" or p["name"] in ("Bride_Stern", "Bride_Helm"):
            lights.append(q(p["name"]))
    fit = [f"{q(n)}, 0.0, 0.717" for n in STANDING] + [f"{q(n)}, 0.1, -0.23" for n in SEATED_PIT]
    for bname, vname in VILLA_POSES.items():
        st = vposes[vname]["sit_target"]
        fit.append(f'{q(bname)}, {st["offset_m"][0]:.3f}, {st["offset_m"][2] - st["anchor_height_m"]:.3f}')
    mats = []
    for si, slot in enumerate(SLOTS):
        for var in cat["slots"].get(slot, []):
            mats.append(f'{si}, {q(var["id"])}, {q(var["label"][:24])}')
    defaults = [cat.get("default", {}).get(s, d) for s, d in zip(SLOTS, DEFAULTS)]
    return "\n".join([
        f'string ROOT_NAME = "Bride_Deck_Main";      // the root takes the object\'s name in SL',
        f"float ROOT_Z = {root['center'][2]:.3f};          // root centre above the waterline",
        "list SEATS = [\n    " + ",\n    ".join(seats) + "];",
        "list POSE_FIT = [" + ", ".join(fit) + "];",
        "list NO_PHYS = [" + ", ".join(nophys) + "];",
        "list PRIM_PHYS = [" + ", ".join(primphys) + "];",
        "list LIGHT_PIECES = [" + ", ".join(lights) + "];",
        "list SLOTS = [" + ", ".join(q(s) for s in SLOTS) + "];",
        "list SLOT_LABELS = [" + ", ".join(q(s) for s in SLOT_LABELS) + "];",
        "list DEFAULT_MATS = [" + ", ".join(q(s) for s in defaults) + "];",
        "list MATS = [\n    " + ",\n    ".join(mats) + "];",
        "list SCENES = [" + ", ".join(f"{q(n)}, {lv}" for n, lv in SCENES) + "];",
        "list SOUND_SPOTS = [" + ", ".join(f"{q(a)}, {q(b)}" for a, b in SOUND_SPOTS) + "];",
        "list LORE = [\n    " + ",\n    ".join(f"{q(a)}, {q(b)}" for a, b in LORE) + "];",
        'string OPTS_DEFAULT = "chat,lore,sounds,particles,lights,guns";',
    ])


def main():
    src = open(os.path.join(ROOT, "lsl", "templates", "bride_main.lsl"), encoding="utf-8").read()
    src = src.replace("//@@TABLES@@", tables())
    out = os.path.join(ROOT, "lsl", "bride_main.lsl")
    with open(out, "w", encoding="utf-8") as f:
        f.write("// GENERATED by ship/scripts/slsl.py from lsl/templates/bride_main.lsl (edit the template)\n" + src)
    print(out, len(src.encode()), "bytes")


if __name__ == "__main__":
    main()

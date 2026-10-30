"""Writes cave/lsl/cave_main.lsl from its template with the tables from the build report, the
material catalogue and the pose data.   python3 cave/scripts/clsl.py"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
REPO = os.path.dirname(ROOT)
SLOTS = ["a_plaster", "b_floor", "c_wood", "d_stone", "e_fabric", "f_metal", "g_glass", "h_glow", "water"]
SLOT_LABELS = ["Rock", "Ground", "Wood", "Moss", "Fur", "Metal", "Crystal", "Glow", "Water"]
DEFAULTS = ["limestone", "earth", "timber", "wet", "fur_brown", "iron", "amethyst", "embers", "teal"]
POSES = {"cave_sit_relaxed": "villa_sit_relaxed", "cave_sit_upright": "villa_sit_upright",
         "cave_sit_crossed": "villa_sit_crossed", "cave_sit_curl": "villa_sit_curl", "cave_lounge": "villa_lounge"}
MOODS = [  # name, fire colour, fire level, crystal colour, crystal level, glow-worm colour, glow-worm level
    ("Torchlight", (1, 0.55, 0.22), 1.0, (0.7, 0.4, 1), 0.35, (0.3, 0.75, 1), 0.3),
    ("Bioluminescent", (1, 0.55, 0.22), 0.0, (0.4, 0.7, 1), 1.0, (0.3, 0.85, 1), 1.0),
    ("Crystal", (1, 0.55, 0.22), 0.15, (0.75, 0.35, 1), 1.0, (0.5, 0.4, 1), 0.5),
    ("Daylight", (1, 0.55, 0.22), 0.0, (0.7, 0.4, 1), 0.2, (0.3, 0.75, 1), 0.0),
    ("Darkness", (1, 0.45, 0.18), 0.12, (0.7, 0.4, 1), 0.05, (0.3, 0.75, 1), 0.15),
    ("Ritual", (1, 0.15, 0.08), 1.0, (1, 0.2, 0.2), 0.8, (0.6, 0.1, 0.1), 0.3),
]
TINTS = [("Natural", (1, 1, 1)), ("Snow", (1, 0.98, 0.95)), ("Sand", (0.93, 0.84, 0.7)), ("Russet", (0.75, 0.45, 0.3)),
         ("Black", (0.25, 0.24, 0.24)), ("Grey", (0.6, 0.6, 0.62)), ("Moss", (0.55, 0.62, 0.42)),
         ("Blood", (0.6, 0.18, 0.15)), ("Indigo", (0.3, 0.3, 0.55))]
FIRE_COLOURS = [("Natural", (1, 0.55, 0.22)), ("Blue magic", (0.35, 0.6, 1)), ("Green", (0.4, 1, 0.45)),
                ("Red", (1, 0.15, 0.08)), ("Violet", (0.75, 0.35, 1))]
SOUND_SPOTS = [("Cave_Hearth", "cave_fire"), ("Cave_Waterfall", "cave_waterfall"), ("Cave_Spring_Water", "cave_spring"),
               ("Cave_Crystals_1", "cave_crystal"), ("Cave_Rock_11", "cave_drips"), ("Cave_Curtain", "cave_wind"),
               ("Cave_Lake", "cave_lake")]
LORE = [
    ("Cave_Altar", "An altar older than any song. The stone is worn in two hollows where countless knees have rested, "
                   "and the bowl is never quite cold."),
    ("Cave_Crystals", "The crystals hum when you stand close, a sound felt in the teeth more than heard. Some say "
                      "they remember every word spoken in the cave."),
    ("Cave_Waterfall", "Cold water falls from a crack in the rock, fed by snow far above. Behind the veil the stone is "
                       "smooth, as if someone once lived there."),
    ("Cave_Chest", "A sea chest bound in iron, its lid scratched with a dozen tally marks. The coins spilling out are "
                   "from no kingdom you know."),
    ("Cave_Spring", "Warm water rises through the stones, smelling faintly of iron and sulphur. Aching bones forget "
                    "their age here."),
    ("Cave_Barrels", "Three barrels: one of water, one of salted meat, one marked with a skull that nobody opens."),
    ("Cave_Crates", "Crates of rope, oil, candles and dried herbs, stacked by someone planning to stay a long time."),
    ("Cave_Table", "A flat stone used as a table. Knife marks, wax drips and a map scratched into the surface."),
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
    seats, nophys = [], []
    for p in rep["pieces"]:
        if "seat" in p:
            s = p["seat"]
            seats.append(f'{q(p["name"])}, {v(s["offset"])}, {s["yaw"]:.1f}, {q(",".join(s["poses"]))}')
        if p.get("phys") == "none":
            nophys.append(q(p["name"]))
    fit = [f'{q("cave_kneel")}, 0.0, 0.717']
    for cname, vname in POSES.items():
        st = vposes[vname]["sit_target"]
        fit.append(f'{q(cname)}, {st["offset_m"][0]:.3f}, {st["offset_m"][2] - st["anchor_height_m"]:.3f}')
    mats = []
    for si, slot in enumerate(SLOTS):
        for var in cat["slots"].get(slot, []):
            mats.append(f'{si}, {q(var["id"])}, {q(var["label"][:24])}')
    defaults = [cat.get("default", {}).get(s, d) for s, d in zip(SLOTS, DEFAULTS)]
    return "\n".join([
        "list SEATS = [\n    " + ",\n    ".join(seats) + "];",
        "list POSE_FIT = [" + ", ".join(fit) + "];",
        "list NO_PHYS = [" + ", ".join(nophys) + "];",
        "list SLOTS = [" + ", ".join(q(s) for s in SLOTS) + "];",
        "list SLOT_LABELS = [" + ", ".join(q(s) for s in SLOT_LABELS) + "];",
        "list DEFAULT_MATS = [" + ", ".join(q(s) for s in defaults) + "];",
        "list MATS = [\n    " + ",\n    ".join(mats) + "];",
        "list MOODS = [\n    " + ",\n    ".join(f"{q(n)}, {v(fc)}, {fl}, {v(cc)}, {cl}, {v(wc)}, {wl}"
                                                for n, fc, fl, cc, cl, wc, wl in MOODS) + "];",
        "list TINTS = [" + ", ".join(f"{q(n)}, {q(v(c))}" for n, c in TINTS) + "];",
        "list FIRE_COLOURS = [" + ", ".join(f"{q(n)}, {q(v(c))}" for n, c in FIRE_COLOURS) + "];",
        "list SOUND_SPOTS = [" + ", ".join(f"{q(a)}, {q(b)}" for a, b in SOUND_SPOTS) + "];",
        "list LORE = [\n    " + ",\n    ".join(f"{q(a)}, {q(b)}" for a, b in LORE) + "];",
        'string OPTS_DEFAULT = "chat,lore,sounds,particles,lights";',
    ])


def main():
    src = open(os.path.join(ROOT, "lsl", "templates", "cave_main.lsl"), encoding="utf-8").read()
    src = src.replace("//@@TABLES@@", tables())
    out = os.path.join(ROOT, "lsl", "cave_main.lsl")
    with open(out, "w", encoding="utf-8") as f:
        f.write("// GENERATED by cave/scripts/clsl.py from lsl/templates/cave_main.lsl (edit the template)\n" + src)
    print(out, len(src.encode()), "bytes")


if __name__ == "__main__":
    main()

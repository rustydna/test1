"""Beauty renders of The Cave with its real PBR materials (Cycles CPU).

    python3 cave/scripts/crender.py [--samples 64] [--size 1280x720] [--only 0,3]
-> cave/output/renders/cave_<view>.png

Lighting follows the in-world "Torchlight" mood: every torch, the hearth and the altar bowl
are warm point lights, the crystals glow violet, the glow-worms over the lake glow blue, and
daylight comes in through the mouth and the sky chimney.
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cave  # noqa: E402  (registers the pieces, sets the output folder)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import vrender as R  # noqa: E402

ROOT = os.path.dirname(HERE)
R.TEX = os.path.join(ROOT, "output", "textures")
R.REN = os.path.join(ROOT, "output", "renders")
R.FALLBACK["g_glass"] = ((0.7, 0.55, 0.9), 0.05, 0.0, 0.7, 0.0)
R.FALLBACK["water"] = ((0.1, 0.4, 0.42), 0.02, 0.0, 0.7, 0.0)
DEFAULTS = json.load(open(os.path.join(ROOT, "docs", "materials.json")))["default"]

VIEWS = [   # name, eye, look-at, lens
    ("entrance_hall", (17.0, -1.6, 1.7), (0.0, 1.0, 1.4), 22),
    ("hearth", (8.4, -3.6, 1.6), (4.0, 0.2, 0.4), 28),
    ("lake_grotto", (-3.8, 1.2, 1.9), (-13.0, 11.0, 1.8), 20),
    ("waterfall", (-8.4, 4.2, 1.3), (-12.4, 14.0, 2.6), 26),
    ("hot_spring", (-5.4, -6.2, 1.7), (-10.0, -10.0, 0.4), 24),
    ("crystal_grotto", (9.4, -7.4, 1.7), (15.0, -13.0, 1.0), 22),
    ("den", (9.6, 6.8, 1.7), (14.0, 13.0, 0.6), 22),
    ("exterior", (48.0, -38.0, 24.0), (0.0, 0.0, 1.0), 30),
]


def dress_cave(objects):
    """Default materials, but the glow faces of the rock are glow-worms and of the crystals violet."""
    for ob in objects:
        name = ob.get("sl_name", ob.name)
        for i, mat in enumerate(ob.data.materials):
            slot = mat.name if mat else "a_plaster"
            if slot not in cave.M.ALL:
                continue
            var = DEFAULTS.get(slot)
            if slot == "h_glow" and name.startswith("Cave_Rock_"):
                var = "glowworm"
            elif slot == "h_glow" and name.startswith("Cave_Crystals_"):
                var = "crystal"
            ob.data.materials[i] = R.make_material(slot, var)


def lights(report):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.55, 0.68, 0.9, 1)
    bg.inputs["Strength"].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.data.color = (1.0, 0.93, 0.82)
    sun.rotation_euler = (math.radians(35), 0, math.radians(110))
    scene.collection.objects.link(sun)

    def point(name, loc, energy, colour, radius=0.1):
        L = bpy.data.objects.new(name, bpy.data.lights.new(name, "POINT"))
        L.data.energy = energy
        L.data.color = colour
        L.data.shadow_soft_size = radius
        L.location = loc
        scene.collection.objects.link(L)

    for p in report["pieces"]:
        c = Vector(p["center"])
        n = p["name"]
        if n.startswith("Cave_Torch_"):
            point(n, c + Vector((0, 0, 0.35)), 180, (1.0, 0.55, 0.22), 0.08)
        elif n == "Cave_Hearth":
            point(n, Vector((c.x, c.y, c.z - 0.2)), 900, (1.0, 0.5, 0.2), 0.4)
        elif n == "Cave_Altar":
            point(n, c + Vector((0, 0, 0.7)), 120, (1.0, 0.5, 0.2), 0.1)
        elif n.startswith("Cave_Crystals_"):
            point(n, c + Vector((0, 0, 0.3)), 160, (0.7, 0.4, 1.0), 0.3)
    lx, ly = cave.CHAMBERS["lake"][0][0], cave.CHAMBERS["lake"][0][1]
    for dx, dy in ((-3, -2), (3, 2), (0, 4), (-2, 3)):
        point("worms", (lx + dx, ly + dy, 4.6), 120, (0.3, 0.75, 1.0), 2.0)
    point("fill_hall", (4, 0, 6.0), 250, (1.0, 0.75, 0.55), 3.0)


def main():
    samples = int(R._arg("--samples", 64))
    w, h = (int(x) for x in R._arg("--size", "1280x720").split("x"))
    only = [int(x) for x in R._arg("--only", "").split(",") if x != ""]
    rep = cave.B.build(export=False, verbose=False)
    high = [o for o in bpy.data.objects if o.get("sl_level") == "HIGH"]
    for o in bpy.data.objects:
        if o.get("sl_level") not in (None, "HIGH"):
            o.hide_render = True
    dress_cave(high)
    lights(rep)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.view_settings.view_transform = "AgX"
    scene.view_settings.exposure = 0.3
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    os.makedirs(R.REN, exist_ok=True)
    for k, (name, eye, look, lens) in enumerate(VIEWS):
        if only and k not in only:
            continue
        cam.data.lens = lens
        cam.location = Vector(eye)
        cam.rotation_euler = (Vector(look) - Vector(eye)).to_track_quat("-Z", "Y").to_euler()
        scene.view_settings.exposure = -0.6 if name == "exterior" else 0.3
        scene.render.filepath = os.path.join(R.REN, f"cave_{name}.png")
        bpy.ops.render.render(write_still=True)
        print(scene.render.filepath, flush=True)


if __name__ == "__main__":
    main()

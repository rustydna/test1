"""Beauty renders of the Second Bride (Cycles CPU) with its PBR materials when they exist.

    python3 ship/scripts/srender.py [--samples 64] [--size 1280x720] [--only 0,3] [--night]
-> ship/output/renders/bride_<view>.png
"""

import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import ship  # noqa: E402  (registers the pieces, sets the output folder)
import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import hull as H  # noqa: E402
import vmesh as M  # noqa: E402
import vrender as R  # noqa: E402

ROOT = os.path.dirname(HERE)
R.TEX = os.path.join(ROOT, "output", "textures")
R.REN = os.path.join(ROOT, "output", "renders")
CAT = os.path.join(ROOT, "docs", "materials.json")
DEFAULTS = json.load(open(CAT))["default"] if os.path.exists(CAT) else {}
R.FALLBACK.update({
    "a_plaster": ((0.04, 0.04, 0.045), 0.6, 0.0, 1.0, 0.0), "b_floor": ((0.62, 0.55, 0.42), 0.7, 0.0, 1.0, 0.0),
    "c_wood": ((0.32, 0.2, 0.11), 0.5, 0.0, 1.0, 0.0), "d_stone": ((0.8, 0.6, 0.2), 0.35, 1.0, 1.0, 0.0),
    "e_fabric": ((0.85, 0.8, 0.7), 0.9, 0.0, 1.0, 0.0), "f_metal": ((0.08, 0.08, 0.09), 0.5, 1.0, 1.0, 0.0),
    "g_glass": ((0.5, 0.6, 0.5), 0.05, 0.0, 0.5, 0.0), "h_glow": ((1.0, 0.7, 0.35), 0.5, 0.0, 1.0, 6.0)})

VIEWS = [   # name, eye, look-at, lens
    ("three_quarter", (34.0, -30.0, 9.0), (-1.0, 0.0, 9.0), 30),
    ("stern", (-34.0, -14.0, 5.0), (-17.0, 0.0, 4.0), 40),
    ("bow", (32.0, 12.0, 3.0), (16.0, 0.0, 5.0), 35),
    ("quarterdeck", (-17.0, -2.2, 6.6), (6.0, 1.0, 5.0), 24),
    ("waist", (8.5, 3.4, 4.3), (-4.0, -1.0, 3.6), 22),
    ("great_cabin", (-7.3, -2.4, 3.9), (-16.0, 1.0, 3.2), 20),
    ("brig", (2.0, 0.0, 0.9), (8.5, 2.0, 0.2), 22),
    ("aloft", (8.0, -24.0, 30.0), (0.0, 0.0, 16.0), 30),
]


def dress_ship(objects):
    for ob in objects:
        for i, mat in enumerate(ob.data.materials):
            slot = mat.name if mat else "a_plaster"
            if slot in M.ALL:
                ob.data.materials[i] = R.make_material(slot, DEFAULTS.get(slot))


def lights(report, night):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs["Color"].default_value = (0.05, 0.07, 0.12, 1) if night else (0.55, 0.68, 0.9, 1)
    bg.inputs["Strength"].default_value = 0.3 if night else 1.0
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 0.15 if night else 3.2
    sun.data.color = (0.6, 0.7, 1.0) if night else (1.0, 0.9, 0.75)
    sun.rotation_euler = (math.radians(55 if not night else 30), 0, math.radians(-30))
    scene.collection.objects.link(sun)
    for p in report["pieces"]:
        if p["kind"] != "light" and not p["name"].startswith("Bride_Cabin_Lamp"):
            continue
        L = bpy.data.objects.new(p["name"], bpy.data.lights.new(p["name"], "POINT"))
        L.data.energy = 250 if night else 60
        L.data.color = (1.0, 0.6, 0.3)
        L.data.shadow_soft_size = 0.2
        L.location = Vector(p["center"])
        scene.collection.objects.link(L)
    # the great cabin and the brig need their own light by day too
    for loc, e in (((-12.5, 0.0, 4.4), 400), ((6.0, 0.0, 1.3), 200)):
        L = bpy.data.objects.new("in", bpy.data.lights.new("in", "POINT"))
        L.data.energy = e
        L.data.color = (1.0, 0.75, 0.5)
        L.data.shadow_soft_size = 0.6
        L.location = loc
        scene.collection.objects.link(L)
    # the sea: a big plane at the waterline
    me = bpy.data.meshes.new("sea")
    me.from_pydata([(-400, -400, 0), (400, -400, 0), (400, 400, 0), (-400, 400, 0)], [], [(0, 1, 2, 3)])
    ob = bpy.data.objects.new("sea", me)
    mat = bpy.data.materials.new("sea")
    mat.use_nodes = True
    b = mat.node_tree.nodes["Principled BSDF"]
    b.inputs["Base Color"].default_value = (0.02, 0.07, 0.08, 1)
    b.inputs["Roughness"].default_value = 0.08
    me.materials.append(mat)
    scene.collection.objects.link(ob)


def main():
    samples = int(R._arg("--samples", 64))
    w, h = (int(x) for x in R._arg("--size", "1280x720").split("x"))
    only = [int(x) for x in R._arg("--only", "").split(",") if x != ""]
    night = "--night" in sys.argv
    rep = ship.B.build(export=False, verbose=False)
    high = [o for o in bpy.data.objects if o.get("sl_level") == "HIGH"]
    for o in bpy.data.objects:
        if o.get("sl_level") not in (None, "HIGH"):
            o.hide_render = True
        if o.get("sl_level") == "HIGH" and o.get("sl_name", "").startswith("Bride_Furled_"):
            o.hide_render = True                      # sails set
    dress_ship(high)
    lights(rep, night)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.cycles.max_bounces = 6
    scene.render.resolution_x, scene.render.resolution_y = w, h
    scene.view_settings.view_transform = "AgX"
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
        interior = name in ("great_cabin", "brig")
        scene.view_settings.exposure = (0.8 if interior else -0.4) + (0.6 if night else 0.0)
        scene.render.filepath = os.path.join(R.REN, f"bride_{name}{'_night' if night else ''}.png")
        bpy.ops.render.render(write_still=True)
        print(scene.render.filepath, flush=True)


if __name__ == "__main__":
    main()

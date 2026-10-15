"""Quick look at a few pieces with their story details (small Cycles render, material colours).

    python the_pit/scripts/preview_piece.py C02_Props C02_Wall      ->  the_pit/output/previews/<first>.png
Options: --lod N (0 HIGH, default), --out name.png, --view x,y,z (camera direction, default 1,-1.4,0.9)
Renders the pieces together, framed automatically, from two sides.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import build_pit  # noqa: E402
import pieces_v3 as P  # noqa: E402
from geo import MATS  # noqa: E402

COLOURS = {"Stone": (0.42, 0.4, 0.37), "Floor": (0.25, 0.22, 0.19), "Wood": (0.36, 0.24, 0.14), "Iron": (0.12, 0.12, 0.13),
           "Cloth": (0.5, 0.44, 0.34), "Bone": (0.78, 0.72, 0.6), "Straw": (0.7, 0.58, 0.3), "Flame": (1.0, 0.5, 0.1),
           "Water": (0.05, 0.12, 0.14)}


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    lod = int(sys.argv[sys.argv.index("--lod") + 1]) if "--lod" in sys.argv else 0
    if "--lod" in sys.argv:
        args.remove(str(lod))
    out = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else args[0] + ".png"
    if "--out" in sys.argv:
        args.remove(out)
    view = Vector((1, -1.4, 0.9))
    if "--view" in sys.argv:
        v = sys.argv[sys.argv.index("--view") + 1]
        args.remove(v)
        view = Vector([float(x) for x in v.split(",")])
    bpy.ops.wm.read_factory_settings(use_empty=True)
    pieces = {pc.name: pc for pc in P.build_all()}
    mats = {}
    for m in MATS:
        mat = bpy.data.materials.new(m)
        mat.use_nodes = True
        bsdf = mat.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = COLOURS[m] + (1.0,)
        bsdf.inputs["Roughness"].default_value = 0.8
        if m == "Flame":
            bsdf.inputs["Emission Color"].default_value = COLOURS[m] + (1.0,)
            bsdf.inputs["Emission Strength"].default_value = 3.0
        mats[m] = mat
    lo, hi = Vector((1e9,) * 3), Vector((-1e9,) * 3)
    for name in args:
        g = build_pit.built(pieces[name], lod)
        me = bpy.data.meshes.new(name)
        me.from_pydata([tuple(v) for v in g.verts], [], [tuple(f) for f in g.faces])
        for m in MATS:
            me.materials.append(mats[m])
        me.polygons.foreach_set("material_index", [MATS.index(m) for m in g.mats])
        ob = bpy.data.objects.new(name, me)
        bpy.context.scene.collection.objects.link(ob)
        a, b = g.bounds()
        lo = Vector(map(min, lo, a))
        hi = Vector(map(max, hi, b))
    c = (lo + hi) / 2
    r = (hi - lo).length / 2
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 24
    scene.cycles.use_denoising = False
    scene.render.resolution_x, scene.render.resolution_y = 900, 650
    world = bpy.data.worlds.new("w")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.35, 0.36, 0.4, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.0
    sun.rotation_euler = (0.7, 0.3, 0.9)
    scene.collection.objects.link(sun)
    os.makedirs(os.path.join(HERE, "..", "output", "previews"), exist_ok=True)
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 35
    for k, d in enumerate((view, Vector((-view.x, -view.y, view.z)))):
        cam.location = c + d.normalized() * r * 2.3
        cam.rotation_euler = (c - cam.location).to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(HERE, "..", "output", "previews", out.replace(".png", "") + ("" if k == 0 else "_back") + ".png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        print(os.path.abspath(path))


if __name__ == "__main__":
    main()

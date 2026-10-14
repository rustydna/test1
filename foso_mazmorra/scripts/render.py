"""Renders de presentación del Foso V2 (Cycles). No cambia el modelo exportado.

    python foso_mazmorra/scripts/render.py [--fast] [--only 01,03]
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "salida")

VIEWS = {
    "01_Puerta_exterior": dict(loc=(13.5, -36.0, 6.5), look=(0.0, -16.0, 5.2), lens=30),
    "02_Patio_hacia_brasero": dict(loc=(1.2, -12.6, 1.65), look=(-0.2, 14.0, 2.6), lens=22),
    "03_Celda_cadena": dict(loc=(-4.4, -4.6, 1.75), look=(-8.6, -1.6, 0.6), lens=18, fill=(-5.0, -3.4, 3.4)),
    "04_Reja_y_antorcha": dict(loc=(0.6, -4.9, 1.6), look=(-3.0, -8.2, 2.3), lens=26),
    "05_Vista_aerea": dict(loc=(27.0, -40.0, 30.0), look=(0.0, -1.0, 2.0), lens=30, moon=0.7),
    "06_Planta_sin_bovedas": dict(ortho=38.0, loc=(0.0, -1.6, 60.0), rot=(0.0, 0.0, 1.5708), hide="_Boveda",
                                  moon=1.2, res=(1400, 1000)),
}


def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def setup(fast):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24 if fast else 96
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x = 960 if fast else 1600
    sc.render.resolution_y = 540 if fast else 900
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.6
    w = bpy.data.worlds.new("Noche") if not sc.world else sc.world
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.012, 0.018, 0.035, 1)
    bg.inputs[1].default_value = 1.0
    coll = bpy.data.collections.get("PRESENTACION") or bpy.data.collections.new("PRESENTACION")
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    # luna
    moon = bpy.data.lights.new("Luna", "SUN")
    moon.energy = 0.35
    moon.color = (0.62, 0.72, 1.0)
    moon.angle = math.radians(2)
    mo = bpy.data.objects.new("Luna", moon)
    mo.rotation_euler = (math.radians(52), 0, math.radians(-32))
    coll.objects.link(mo)
    # luces en cada llama
    hi = bpy.data.collections["MALLA | HIGH"]
    for ob in hi.objects:
        me = ob.data
        if "Llama" not in me.materials:
            continue
        mi = list(me.materials.keys()).index("Llama")
        pts = [ob.matrix_world @ me.vertices[v].co for p in me.polygons if p.material_index == mi for v in p.vertices]
        if not pts:
            continue
        c = sum(pts, Vector()) / len(pts)
        name = ob.name
        power = 420.0 if "Brasero" in name else (45.0 if "Farol" in name else 55.0)
        L = bpy.data.lights.new(f"Luz_{name}", "POINT")
        L.energy = power
        L.color = (1.0, 0.52, 0.22)
        L.shadow_soft_size = 0.12 if "Brasero" not in name else 0.4
        lo = bpy.data.objects.new(f"Luz_{name}", L)
        lo.location = c + Vector((0, 0, 0.12))
        coll.objects.link(lo)
    return coll, mo


def render(name, v, coll, moon_ob):
    sc = bpy.context.scene
    cam_data = bpy.data.cameras.new(f"Cam_{name}")
    cam = bpy.data.objects.new(f"Cam_{name}", cam_data)
    coll.objects.link(cam)
    cam.location = Vector(v["loc"])
    if "rot" in v:
        cam.rotation_euler = v["rot"]
    else:
        look_at(cam, v["look"])
    base_res = (sc.render.resolution_x, sc.render.resolution_y)
    if "res" in v:
        k = sc.render.resolution_x / 1600
        sc.render.resolution_x, sc.render.resolution_y = int(v["res"][0] * k), int(v["res"][1] * k)
    if "ortho" in v:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = v["ortho"]
    else:
        cam_data.lens = v.get("lens", 28)
    cam_data.clip_end = 400
    sc.camera = cam
    moon_ob.data.energy = 0.35 * v.get("moon", 1.0)
    fill = None
    if "fill" in v:
        fl = bpy.data.lights.new(f"Relleno_{name}", "POINT")
        fl.energy = 60
        fl.color = (0.85, 0.85, 1.0)
        fill = bpy.data.objects.new(f"Relleno_{name}", fl)
        fill.location = Vector(v["fill"])
        coll.objects.link(fill)
    hidden = []
    if "hide" in v:
        for ob in bpy.data.collections["MALLA | HIGH"].objects:
            if v["hide"] in ob.name:
                ob.hide_render = True
                hidden.append(ob)
    sc.render.filepath = os.path.join(OUT, f"{name}.png")
    bpy.ops.render.render(write_still=True)
    sc.render.resolution_x, sc.render.resolution_y = base_res
    for ob in hidden:
        ob.hide_render = False
    if fill:
        bpy.data.objects.remove(fill)
    print("render", name)


def main():
    fast = "--fast" in sys.argv
    only = None
    if "--only" in sys.argv:
        only = sys.argv[sys.argv.index("--only") + 1].split(",")
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "Foso_V2.blend"))
    coll, moon = setup(fast)
    for name, v in VIEWS.items():
        if only and not any(name.startswith(o) for o in only):
            continue
        render(name, v, coll, moon)
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile(compress=True)


if __name__ == "__main__":
    main()

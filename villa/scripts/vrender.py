"""Beauty renders of the Villa (Cycles CPU) with the real PBR textures when they exist.

    python villa/scripts/vrender.py [LINKSET ...] [--variant a_plaster=white,b_floor=oak]
        [--views N] [--samples 48] [--size 1280x800] [--out name] [--night]

Builds the requested linksets with vbuild (no export), dresses every slot with the textures in
output/textures/<slot>__<variant>_*.png (box-mapped like Second Life will show them, in world
metres), lights the scene with a sun and a sky, and writes output/renders/<name>_<k>.png from
automatic cameras (exterior three-quarter views and, with --interior, eye-level views).
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

import vbuild as B  # noqa: E402
import vmesh as M  # noqa: E402

TEX = os.path.join(B.OUT, "textures")
REN = os.path.join(B.OUT, "renders")
FALLBACK = {   # base colour, roughness, metallic, alpha, emission
    "a_plaster": ((0.86, 0.84, 0.80), 0.7, 0.0, 1.0, 0.0),
    "b_floor": ((0.70, 0.64, 0.55), 0.45, 0.0, 1.0, 0.0),
    "c_wood": ((0.36, 0.22, 0.12), 0.5, 0.0, 1.0, 0.0),
    "d_stone": ((0.88, 0.86, 0.82), 0.15, 0.0, 1.0, 0.0),
    "e_fabric": ((0.78, 0.72, 0.64), 0.85, 0.0, 1.0, 0.0),
    "f_metal": ((0.85, 0.68, 0.42), 0.3, 1.0, 1.0, 0.0),
    "g_glass": ((0.75, 0.82, 0.85), 0.03, 0.0, 0.2, 0.0),
    "h_glow": ((1.0, 0.85, 0.62), 0.5, 0.0, 1.0, 6.0),
    "water": ((0.10, 0.55, 0.62), 0.02, 0.0, 0.7, 0.0),
}


def variants_from_args():
    out = {}
    if "--variant" in sys.argv:
        for kv in sys.argv[sys.argv.index("--variant") + 1].split(","):
            k, v = kv.split("=")
            out[k] = v
    return out


def default_variants():
    path = os.path.join(B.ROOT, "docs", "materials.json")
    if os.path.exists(path):
        import json
        return json.load(open(path)).get("default", {})
    return {}


def _img(path, colour):
    if not os.path.exists(path):
        return None
    im = bpy.data.images.load(path, check_existing=True)
    im.colorspace_settings.name = "sRGB" if colour else "Non-Color"
    return im


def make_material(slot, variant, tint=None):
    name = f"R_{slot}_{variant or 'flat'}"
    m = bpy.data.materials.get(name)
    if m:
        return m
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    base, rough, metal, alpha, emit = FALLBACK.get(slot, FALLBACK["a_plaster"])
    bsdf.inputs["Base Color"].default_value = (*(tint or base), 1.0)
    bsdf.inputs["Roughness"].default_value = rough
    bsdf.inputs["Metallic"].default_value = metal
    stem = os.path.join(TEX, f"{slot}__{variant}") if variant else None
    bc = _img(stem + "_basecolor.png", True) if stem else None
    if bc:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = bc
        if tint:
            mix = nt.nodes.new("ShaderNodeMix")
            mix.data_type = "RGBA"
            mix.blend_type = "MULTIPLY"
            mix.inputs["Factor"].default_value = 1.0
            nt.links.new(t.outputs["Color"], mix.inputs["A"])
            mix.inputs["B"].default_value = (*tint, 1.0)
            nt.links.new(mix.outputs["Result"], bsdf.inputs["Base Color"])
        else:
            nt.links.new(t.outputs["Color"], bsdf.inputs["Base Color"])
    orm = _img(stem + "_orm.png", False) if stem else None
    if orm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = orm
        sep = nt.nodes.new("ShaderNodeSeparateColor")
        nt.links.new(t.outputs["Color"], sep.inputs["Color"])
        nt.links.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
        nt.links.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nrm = _img(stem + "_normal.png", False) if stem else None
    if nrm:
        t = nt.nodes.new("ShaderNodeTexImage")
        t.image = nrm
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nt.links.new(t.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    em = _img(stem + "_emissive.png", True) if stem else None
    if emit > 0 or em:
        if em:
            t = nt.nodes.new("ShaderNodeTexImage")
            t.image = em
            nt.links.new(t.outputs["Color"], bsdf.inputs["Emission Color"])
        else:
            bsdf.inputs["Emission Color"].default_value = (*base, 1.0)
        bsdf.inputs["Emission Strength"].default_value = max(emit, 4.0)
    if alpha < 1.0:
        bsdf.inputs["Alpha"].default_value = alpha
        if slot in ("g_glass", "water"):
            bsdf.inputs["Transmission Weight"].default_value = 0.0
    return m


def dress(objects, variants):
    for ob in objects:
        me = ob.data
        for i, mat in enumerate(me.materials):
            slot = mat.name if mat else "a_plaster"
            if slot not in M.ALL:
                continue
            me.materials[i] = make_material(slot, variants.get(slot))


def light_scene(night=False):
    scene = bpy.context.scene
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    nt = world.node_tree
    bg = nt.nodes["Background"]
    try:
        sky = nt.nodes.new("ShaderNodeTexSky")
        sky.sky_type = "NISHITA" if "NISHITA" in [e.identifier for e in sky.bl_rna.properties["sky_type"].enum_items] \
            else sky.sky_type
        if hasattr(sky, "sun_elevation"):
            sky.sun_elevation = math.radians(4 if night else 28)
            sky.sun_rotation = math.radians(215)
        nt.links.new(sky.outputs["Color"], bg.inputs["Color"])
        bg.inputs["Strength"].default_value = 0.02 if night else 0.35
    except Exception:  # noqa: BLE001  (older/newer sky node: plain colour)
        bg.inputs["Color"].default_value = (0.55, 0.65, 0.8, 1)
        bg.inputs["Strength"].default_value = 0.05 if night else 0.8
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 0.25 if night else 4.0
    sun.data.angle = math.radians(1.5)
    sun.data.color = (0.6, 0.7, 1.0) if night else (1.0, 0.93, 0.82)
    sun.rotation_euler = (math.radians(58), 0, math.radians(215))
    scene.collection.objects.link(sun)


def cameras(lo, hi, n, interior=False):
    c = (lo + hi) / 2
    r = max((hi - lo).length / 2, 1.0)
    out = []
    for k in range(n):
        a = math.radians(-60 + 360 * k / n)
        if interior:
            eye = Vector((c.x + math.cos(a) * r * 0.25, c.y + math.sin(a) * r * 0.25, lo.z + 1.6))
            look = Vector((c.x - math.cos(a) * r * 0.4, c.y - math.sin(a) * r * 0.4, lo.z + 1.2))
        else:
            eye = c + Vector((math.cos(a), math.sin(a), 0.42)).normalized() * r * 1.55
            look = c + Vector((0, 0, -(hi.z - lo.z) * 0.12))
        out.append((eye, look))
    return out


def render(linksets=None, variants=None, views=3, samples=48, size=(1280, 800), name="villa", night=False,
           interior=False, cams=None):
    rep = B.build(only=linksets, export=False, verbose=False)
    high = [o for o in bpy.data.objects if o.get("sl_level") == "HIGH"]
    for o in bpy.data.objects:
        if o.get("sl_level") not in (None, "HIGH"):
            o.hide_render = True
    v = default_variants()
    v.update(variants or {})
    dress(high, v)
    light_scene(night)
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = samples
    scene.cycles.use_denoising = True
    scene.render.resolution_x, scene.render.resolution_y = size
    scene.view_settings.view_transform = "AgX" if "AgX" in [
        e.identifier for e in scene.view_settings.bl_rna.properties["view_transform"].enum_items] else "Filmic"
    scene.view_settings.look = "None"
    scene.view_settings.exposure = -1.6 if not night else 0.0
    lo = Vector((1e9,) * 3)
    hi = Vector((-1e9,) * 3)
    for p in rep["pieces"]:
        c, s = Vector(p["center"]), Vector(p["size_m"])
        lo = Vector(map(min, lo, c - s / 2))
        hi = Vector(map(max, hi, c + s / 2))
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.data.lens = 18 if interior else 30
    os.makedirs(REN, exist_ok=True)
    paths = []
    for k, (eye, look) in enumerate(cams or cameras(lo, hi, views, interior)):
        cam.location = eye
        cam.rotation_euler = (look - eye).to_track_quat("-Z", "Y").to_euler()
        path = os.path.join(REN, f"{name}_{k}.png")
        scene.render.filepath = path
        bpy.ops.render.render(write_still=True)
        paths.append(path)
        print(path, flush=True)
    return paths


def _arg(flag, default):
    return sys.argv[sys.argv.index(flag) + 1] if flag in sys.argv else default


if __name__ == "__main__":
    import villa  # noqa: F401,E402  (registers every piece)
    flags = {"--variant", "--views", "--samples", "--size", "--out"}
    names = []
    skip = False
    for a in sys.argv[1:]:
        if skip:
            skip = False
            continue
        if a in flags:
            skip = True
            continue
        if not a.startswith("--"):
            names.append(a)
    w, h = (int(x) for x in _arg("--size", "1280x800").split("x"))
    render(names or None, variants_from_args(), int(_arg("--views", 3)), int(_arg("--samples", 48)), (w, h),
           _arg("--out", "villa"), "--night" in sys.argv, "--interior" in sys.argv)

"""Presentation renders of The Pit V3 (Cycles). Does not change the exported model.

    python the_pit/scripts/render.py [--fast] [--only 01,03] [--samples 96] [--no-pbr]

After opening the .blend it replaces (in memory only, unless --save) the flat materials with
the PBR textures from output/textures/ and the flame with the first frame of the flipbook from
output/effects/. The DAEs for SL are not touched: they still reference no images.
"""

import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import bpy  # noqa: E402
from mathutils import Vector  # noqa: E402

ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "output")
TEX = os.path.join(OUT, "textures")
EFX = os.path.join(OUT, "effects")
PBR = ["Stone", "Floor", "Wood", "Iron", "Cloth", "Bone", "Straw", "Water"]

VIEWS = {
    "01_Outer_gate": dict(loc=(13.5, -36.0, 6.5), look=(0.0, -16.0, 5.2), lens=30, moon=4.0, exp=1.5,
                          fill=(16.0, -40.0, 12.0), fill_w=6000),
    "02_The_Pit_towards_the_throne": dict(loc=(0.9, -12.4, 1.65), look=(-0.2, 14.0, 2.4), lens=22),
    "03_The_Kennel": dict(loc=(4.2, -10.7, 1.75), look=(10.4, -4.8, 0.55), lens=20, fill=(7.6, -6.8, 3.5), exp=1.5),
    "04_The_Cistern": dict(loc=(-4.3, 6.2, 1.9), look=(-9.4, 9.2, 0.9), lens=20, fill=(-7.0, 8.0, 3.6), exp=1.2),
    "05_The_Cages": dict(loc=(4.2, 5.1, 1.7), look=(8.6, 1.6, 2.2), lens=20, fill=(6.5, 2.5, 3.8), exp=1.2),
    "06_The_Throne": dict(loc=(0.6, 9.2, 1.9), look=(0.0, 14.6, 2.6), lens=24, exp=0.0),
    "07_The_Rack": dict(loc=(-4.2, -4.2, 2.0), look=(-8.6, -2.6, 0.8), lens=20, fill=(-7.0, -3.0, 3.6), exp=1.2),
    "08_Aerial": dict(loc=(27.0, -40.0, 30.0), look=(0.0, -1.0, 2.0), lens=30, moon=0.7, no_fog=True),
    "09_Plan": dict(ortho=38.0, loc=(0.0, -1.6, 60.0), rot=(0.0, 0.0, 1.5708), hide=("_Vault", "_Roof"),
                    moon=1.2, res=(1400, 1000), no_fog=True),
}

def look_at(ob, target):
    d = Vector(target) - ob.location
    ob.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def load_image(path, color):
    """Loads a PNG only once; color=False leaves it as Non-Color."""
    img = bpy.data.images.load(path, check_existing=True)
    img.colorspace_settings.name = "sRGB" if color else "Non-Color"
    return img


def material_pbr(m, name):
    """sRGB basecolor (x occlusion), ORM split into AO/roughness/metallic, and glTF normal."""
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    bsdf = N.new("ShaderNodeBsdfPrincipled")
    uv = N.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    tx = {}
    for k, color in (("basecolor", True), ("orm", False), ("normal", False)):
        t = N.new("ShaderNodeTexImage")
        t.image = load_image(os.path.join(TEX, f"{name}_{k}.png"), color)
        t.interpolation = "Cubic" if k == "normal" else "Linear"
        L.new(uv.outputs["UV"], t.inputs["Vector"])
        tx[k] = t
    sep = N.new("ShaderNodeSeparateColor")
    L.new(tx["orm"].outputs["Color"], sep.inputs["Color"])
    ao = N.new("ShaderNodeMix")
    ao.data_type = "RGBA"
    ao.blend_type = "MULTIPLY"
    ao.inputs["Factor"].default_value = 1.0
    L.new(tx["basecolor"].outputs["Color"], ao.inputs["A"])
    L.new(sep.outputs["Red"], ao.inputs["B"])
    L.new(ao.outputs["Result"], bsdf.inputs["Base Color"])
    L.new(sep.outputs["Green"], bsdf.inputs["Roughness"])
    L.new(sep.outputs["Blue"], bsdf.inputs["Metallic"])
    nm = N.new("ShaderNodeNormalMap")
    nm.uv_map = "UVMap"
    nm.inputs["Strength"].default_value = 1.0
    L.new(tx["normal"].outputs["Color"], nm.inputs["Color"])
    L.new(nm.outputs["Normal"], bsdf.inputs["Normal"])
    L.new(bsdf.outputs["BSDF"], out.inputs["Surface"])


def material_flame(m):
    """Emission using the first frame (top left) of the 4x4 flipbook."""
    path = os.path.join(EFX, "fire_flipbook.png")
    if not os.path.exists(path):
        return  # keep the flat warm emission from the .blend
    nt = m.node_tree
    nt.nodes.clear()
    N, L = nt.nodes, nt.links
    out = N.new("ShaderNodeOutputMaterial")
    uv = N.new("ShaderNodeUVMap")
    uv.uv_map = "UVMap"
    mp = N.new("ShaderNodeMapping")
    mp.vector_type = "POINT"
    mp.inputs["Scale"].default_value = (0.25, 0.25, 1.0)
    mp.inputs["Location"].default_value = (0.0, 0.75, 0.0)
    L.new(uv.outputs["UV"], mp.inputs["Vector"])
    t = N.new("ShaderNodeTexImage")
    t.image = load_image(path, True)
    t.extension = "CLIP"
    L.new(mp.outputs["Vector"], t.inputs["Vector"])
    # fire color from a ramp over the frame's luminance: saturated red turns
    # pink under AgX, so the ramp goes from orange to pale yellow
    bw = N.new("ShaderNodeRGBToBW")
    L.new(t.outputs["Color"], bw.inputs["Color"])
    cr = N.new("ShaderNodeValToRGB")
    els = cr.color_ramp.elements
    els[0].position, els[0].color = 0.0, (0.85, 0.22, 0.02, 1.0)
    els[1].position, els[1].color = 1.0, (1.0, 0.78, 0.38, 1.0)
    e = els.new(0.55)
    e.color = (1.0, 0.45, 0.07, 1.0)
    L.new(bw.outputs["Val"], cr.inputs["Fac"])
    em = N.new("ShaderNodeEmission")
    em.inputs["Strength"].default_value = 4.0
    L.new(cr.outputs["Color"], em.inputs["Color"])
    tr = N.new("ShaderNodeBsdfTransparent")
    mx = N.new("ShaderNodeMixShader")
    L.new(t.outputs["Alpha"], mx.inputs["Fac"])
    L.new(tr.outputs["BSDF"], mx.inputs[1])
    L.new(em.outputs["Emission"], mx.inputs[2])
    L.new(mx.outputs["Shader"], out.inputs["Surface"])


def apply_pbr():
    for name in PBR:
        m = bpy.data.materials.get(name)
        if m and os.path.exists(os.path.join(TEX, f"{name}_basecolor.png")):
            material_pbr(m, name)
    if bpy.data.materials.get("Flame"):
        material_flame(bpy.data.materials["Flame"])


def setup(fast, samples=None):
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples or (24 if fast else 64)
    sc.cycles.volume_step_rate = 4.0
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 6
    sc.render.resolution_x = 960 if fast else 1280
    sc.render.resolution_y = 540 if fast else 720
    sc.render.image_settings.file_format = "PNG"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = "AgX - Medium High Contrast"
    sc.view_settings.exposure = 0.6
    w = bpy.data.worlds.new("Night") if not sc.world else sc.world
    sc.world = w
    w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.006, 0.009, 0.018, 1)
    bg.inputs[1].default_value = 1.0
    # volumetric haze (presentation only): the air of the Pit is thick and salty
    nt = w.node_tree
    vol = nt.nodes.new("ShaderNodeVolumePrincipled")
    vol.inputs["Density"].default_value = 0.012
    vol.inputs["Anisotropy"].default_value = 0.35
    vol.inputs["Color"].default_value = (0.7, 0.72, 0.75, 1)
    nt.links.new(vol.outputs[0], nt.nodes["World Output"].inputs["Volume"])
    sc["_vol"] = vol.name
    coll = bpy.data.collections.get("PRESENTATION") or bpy.data.collections.new("PRESENTATION")
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    # moon
    moon = bpy.data.lights.new("Moon", "SUN")
    moon.energy = 0.35
    moon.color = (0.62, 0.72, 1.0)
    moon.angle = math.radians(2)
    mo = bpy.data.objects.new("Moon", moon)
    mo.rotation_euler = (math.radians(52), 0, math.radians(-32))
    coll.objects.link(mo)
    # a light at every flame
    hi = bpy.data.collections["MESH | HIGH"]
    for ob in hi.objects:
        me = ob.data
        if "Flame" not in me.materials:
            continue
        mi = list(me.materials.keys()).index("Flame")
        pts = [ob.matrix_world @ me.vertices[v].co for p in me.polygons if p.material_index == mi for v in p.vertices]
        if not pts:
            continue
        c = sum(pts, Vector()) / len(pts)
        name = ob.name
        power = 160.0 if "Brazier" in name else (40.0 if "Lantern" in name else 45.0)
        L = bpy.data.lights.new(f"Light_{name}", "POINT")
        L.energy = power
        L.color = (1.0, 0.52, 0.22)
        L.shadow_soft_size = 0.12 if "Brazier" not in name else 0.4
        lo = bpy.data.objects.new(f"Light_{name}", L)
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
        k = sc.render.resolution_x / 1280
        sc.render.resolution_x, sc.render.resolution_y = int(v["res"][0] * k), int(v["res"][1] * k)
    if "ortho" in v:
        cam_data.type = "ORTHO"
        cam_data.ortho_scale = v["ortho"]
    else:
        cam_data.lens = v.get("lens", 28)
    cam_data.clip_end = 400
    sc.camera = cam
    sc.view_settings.exposure = v.get("exp", 0.6)
    moon_ob.data.energy = 0.35 * v.get("moon", 1.0)
    fill = None
    if "fill" in v:
        fl = bpy.data.lights.new(f"Fill_{name}", "POINT")
        fl.energy = v.get("fill_w", 25)
        fl.color = (0.85, 0.85, 1.0)
        fill = bpy.data.objects.new(f"Fill_{name}", fl)
        fill.location = Vector(v["fill"])
        fill.visible_volume_scatter = False  # no halo in the fog
        fill.visible_camera = False
        coll.objects.link(fill)
    hidden = []
    vol = sc.world.node_tree.nodes.get(sc.get("_vol", ""))
    if vol:
        vol.inputs["Density"].default_value = 0.0 if v.get("no_fog") else 0.012
    if "hide" in v:
        for ob in bpy.data.collections["MESH | HIGH"].objects:
            if any(h in ob.name for h in v["hide"]):
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
    bpy.ops.wm.open_mainfile(filepath=os.path.join(OUT, "ThePit.blend"))
    if "--no-pbr" not in sys.argv:
        apply_pbr()
    samples = int(sys.argv[sys.argv.index("--samples") + 1]) if "--samples" in sys.argv else None
    coll, moon = setup(fast, samples)
    for name, v in VIEWS.items():
        if only and not any(name.startswith(o) for o in only):
            continue
        render(name, v, coll, moon)
    if "--save" in sys.argv:
        bpy.ops.wm.save_mainfile(compress=True)


if __name__ == "__main__":
    main()

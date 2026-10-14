"""Pruebas de SL Rigger. Ejecutar con Blender en segundo plano:

    blender -b --factory-startup --python tests/test_addon.py
o con el módulo bpy de PyPI:
    python tests/test_addon.py
"""

import os
import sys
import tempfile
import traceback
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

import bpy  # noqa: E402

import sl_rigger  # noqa: E402
from sl_rigger import (anim_export, anim_library, attachments, hud, pose_engine, presets, previews,  # noqa: E402
                       report, skeleton, weights)

NS = {"c": "http://www.collada.org/2005/11/COLLADASchema"}
OUT = tempfile.mkdtemp(prefix="slr_test_")
RESULTS = []
TESTS = []


def case(fn):
    TESTS.append(fn)
    return fn


def run(fn):
    try:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        fn()
        RESULTS.append((fn.__name__, True, ""))
    except Exception:
        RESULTS.append((fn.__name__, False, traceback.format_exc()))


def ctx():
    return bpy.context


def select(objs, active):
    for o in ctx().view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    ctx().view_layer.objects.active = active


def body_mesh(cuts=12):
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.22, depth=1.75, location=(0, 0, 0.9))
    obj = ctx().active_object
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode="OBJECT")
    return obj


def parse(path):
    return ET.parse(path).getroot()


def skins(root):
    out = []
    for ctrl in root.iterfind(".//c:controller", NS):
        names = ctrl.find(".//c:Name_array", NS).text.split()
        binds = list(map(float, ctrl.find(".//c:source[@id='%s-bind_poses']/c:float_array"
                                          % ctrl.get("id"), NS).text.split()))
        out.append((names, binds))
    return out


@case
def official_skeleton_complete():
    assert len(skeleton.SL_INFO) == 159
    bpy.ops.slr.create_rig(preset="HUMAN")
    arm = ctx().active_object
    assert len(arm.data.bones) == 159, len(arm.data.bones)
    world = skeleton.world_positions_sl(skeleton.bone_table("HUMAN"))
    assert abs(world["mPelvis"].z - 1.067015) < 1e-6
    deform = {b.name for b in arm.data.bones if b.use_deform}
    assert "mHandIndex1Left" in deform and "mTail1" not in deform and "BELLY" not in deform


@case
def presets_grounded_and_valid():
    feet = ("mToeLeft", "mToeRight", "mFootLeft", "mFootRight")
    base = skeleton.world_positions_sl(skeleton.bone_table("HUMAN"))
    base_low = min(base[n].z for n in feet)
    for key in presets.PRESETS:
        world = skeleton.world_positions_sl(skeleton.bone_table(key))
        scale = presets.PRESETS[key].get("scale", 1.0)
        assert abs(min(world[n].z for n in feet) - base_low * scale) < 1e-6, key
        bpy.ops.slr.create_rig(preset=key)
        assert len(ctx().active_object.data.bones) == 159


@case
def icons_exist():
    valid = set(bpy.types.UILayout.bl_rna.functions["label"].parameters["icon"].enum_items.keys())
    import re
    base = os.path.dirname(sl_rigger.__file__)
    src = "".join(open(os.path.join(base, f), encoding="utf-8").read() for f in os.listdir(base) if f.endswith(".py"))
    ui_src = "".join(open(os.path.join(base, f), encoding="utf-8").read() for f in ("ui.py", "ui_ops.py"))
    used = set(re.findall(r'icon="([A-Z_0-9]+)"', src))
    used |= set(re.findall(r'icon="([A-Z_0-9]+)" if', ui_src)) | set(re.findall(r'else "([A-Z_0-9]+)"', ui_src))
    used |= set(re.findall(r'"(?:[A-Z]+)", "[^"]+", "[^"]+", "([A-Z_]+)"', ui_src))
    used |= {f"COLORSET_{t[-2:]}_VEC" for _, _, t in skeleton.DEFORM_GROUPS.values()}
    used |= {t[3] for t in __import__("sl_rigger.ui", fromlist=["TABS"]).TABS}
    missing = used - valid
    assert not missing, missing


@case
def wizard_and_dae_export():
    body = body_mesh()
    select([body], body)
    assert "FINISHED" in bpy.ops.slr.wizard()
    report = ctx().scene.slr_report
    assert "ERROR" not in report, report
    path = os.path.join(OUT, "wizard.dae")
    select([body], body)
    assert "FINISHED" in bpy.ops.slr.export_dae(filepath=path, include_lods=False)
    root = parse(path)
    arm_node = root.find(".//c:visual_scene/c:node", NS)
    skel = root.find(".//c:instance_controller/c:skeleton", NS).text
    assert skel == "#" + arm_node.get("id"), (skel, arm_node.get("id"))
    for names, binds in skins(root):
        assert len(names) <= skeleton.SL_MAX_JOINTS_PER_MESH
        assert len(binds) == 16 * len(names)
        assert all(n in skeleton.SL_INFO for n in names)
        for n in names:  # antecesores incluidos
            p = skeleton.SL_INFO[n]["parent"]
            assert p is None or p in names, (n, p)


@case
def fitted_mesh_volumes():
    bpy.ops.slr.create_rig(preset="HUMAN", deform_volumes=True)
    arm = ctx().active_object
    assert arm.data.bones["BELLY"].use_deform
    body = body_mesh(4)
    select([body, arm], arm)
    bpy.ops.slr.bind(mode="EMPTY")
    n = len(body.data.vertices)
    body.vertex_groups["BELLY"].add(range(n // 2), 1.0, "REPLACE")
    body.vertex_groups["mPelvis"].add(range(n // 2, n), 1.0, "REPLACE")
    path = os.path.join(OUT, "fitted.dae")
    select([body], body)
    bpy.ops.slr.export_dae(filepath=path, include_lods=False)
    root = parse(path)
    names, binds = skins(root)[0]
    i = names.index("BELLY")
    m = binds[16 * i:16 * i + 16]
    sx = (m[0] ** 2 + m[4] ** 2 + m[8] ** 2) ** 0.5
    assert abs(sx - 1.0) > 0.5, "la matriz de BELLY debe incluir su escala"
    node = root.find(".//c:node[@name='BELLY']/c:matrix", NS).text.split()
    assert abs(float(node[0]) - 1.0) > 0.05


@case
def joint_limit_detected():
    bpy.ops.slr.create_rig(preset="HUMAN", **{f"deform_{k.lower()}": True for k in skeleton.DEFORM_GROUPS})
    arm = ctx().active_object
    body = body_mesh(14)
    select([body, arm], arm)
    bpy.ops.slr.bind(mode="EMPTY")
    names = [b.name for b in arm.data.bones]
    for i, v in enumerate(body.data.vertices):
        body.vertex_groups[names[i % len(names)]].add([i], 1.0, "REPLACE")
    res = weights.validate_object(body)
    assert any(lvl == "ERROR" and "articulaciones" in msg for lvl, msg in res), res


@case
def transfer_and_mirror_weights():
    body = body_mesh()
    select([body], body)
    bpy.ops.slr.wizard()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.25, depth=0.6, location=(0, 0, 1.2))
    shirt = ctx().active_object
    select([shirt, body], body)
    assert "FINISHED" in bpy.ops.slr.transfer_weights()
    assert skeleton.find_armature(shirt) is not None
    assert len(shirt.vertex_groups) > 3
    assert all(sum(1 for g in v.groups if g.weight > 0) <= 4 for v in shirt.data.vertices)
    select([shirt], shirt)
    assert "FINISHED" in bpy.ops.slr.mirror_weights()


@case
def rigid_bind_robot():
    bpy.ops.slr.create_rig(preset="HUMAN")
    arm = ctx().active_object
    hand = arm.matrix_world @ arm.data.bones["mWristLeft"].head_local
    bpy.ops.mesh.primitive_cube_add(size=0.05, location=hand)
    piece = ctx().active_object
    select([piece, arm], arm)
    assert "FINISHED" in bpy.ops.slr.rigid_bind()
    assert len(piece.vertex_groups) == 1
    name = piece.vertex_groups[0].name
    assert "Left" in name and ("Wrist" in name or "Hand" in name or "Elbow" in name), name


@case
def gltf_and_materials():
    bpy.ops.mesh.primitive_monkey_add()
    m = ctx().active_object
    m.data.materials.append(bpy.data.materials.new("Metal"))
    select([m], m)
    assert "FINISHED" in bpy.ops.slr.export_gltf(filepath=os.path.join(OUT, "obj.glb"), kind="STATIC")
    assert "FINISHED" in bpy.ops.slr.export_materials(directory=OUT)
    assert os.path.exists(os.path.join(OUT, "Metal.glb"))


@case
def static_lods_physics_mirrored():
    bpy.ops.mesh.primitive_monkey_add()
    m = ctx().active_object
    m.scale = (-1, 1, 1)
    select([m], m)
    bpy.ops.slr.make_lods()
    bpy.ops.slr.make_physics()
    select([m], m)
    path = os.path.join(OUT, "static.dae")
    assert "FINISHED" in bpy.ops.slr.export_dae(filepath=path)
    for lvl in ("MED", "LOW", "LOWEST", "PHYS"):
        assert os.path.exists(path.replace(".dae", f"_{lvl}.dae")), lvl


@case
def mixamo_conversion():
    bpy.ops.mesh.primitive_cube_add()
    cube = ctx().active_object
    for n in ("mixamorig:Hips", "mixamorig:Spine1", "mixamorig:Spine2", "mixamorig:LeftHandIndex1"):
        cube.vertex_groups.new(name=n).add(range(8), 0.25, "REPLACE")
    select([cube], cube)
    bpy.ops.slr.convert_groups()
    assert {vg.name for vg in cube.vertex_groups} == {"mPelvis", "mChest", "mHandIndex1Left"}


@case
def monitor_stats():
    body = body_mesh(2)
    select([body], body)
    bpy.ops.slr.wizard()
    select([body], body)
    data = hud.current(ctx())
    st = data["stats"]
    assert st["rigged"] and st["unweighted"] == 0 and st["joints"] <= 110
    assert data["points"] is not None and len(data["points"][0]) == len(body.data.vertices)



# --------------------------------------------------------------------------- 0.5: animación y más

def rig(preset="HUMAN", **kw):
    bpy.ops.slr.create_rig(preset=preset, **kw)
    return ctx().active_object


def _decode_rot(k):
    x, y, z = ((c / 65535.0) * 2 - 1 for c in k[1:])
    w = max(0.0, 1 - x * x - y * y - z * z) ** 0.5
    from mathutils import Quaternion
    return Quaternion((w, x, y, z))


@case
def anim_generators_export_valid():
    arm = rig("FURRY", **{f"deform_{k.lower()}": True for k in skeleton.DEFORM_GROUPS})
    for key in anim_library.GENERATORS:
        select([arm], arm)
        assert "FINISHED" in bpy.ops.slr.generate_anim(kind=key), key
        path = os.path.join(OUT, f"{key}.anim")
        assert "FINISHED" in bpy.ops.slr.export_anim(filepath=path), key
        a = anim_export.read_anim(path)
        assert a["version"] == (1, 0) and a["consumed"] == a["size"], key
        assert 0 < a["duration"] <= 60 and a["joints"], key
        assert all(n in skeleton.SL_INFO for n in a["joints"]), key
    a = anim_export.read_anim(os.path.join(OUT, "TAIL.anim"))
    assert "mTail6" in a["joints"] and len(a["joints"]["mTail6"][1]) > 10
    a = anim_export.read_anim(os.path.join(OUT, "WALK.anim"))
    assert a["joints"]["mPelvis"][2], "la pelvis debe llevar claves de posición"


@case
def static_pose_roundtrip():
    arm = rig()
    select([arm], arm)
    bpy.ops.slr.body_pose(pose="APOSE")
    path = os.path.join(OUT, "apose.anim")
    assert "FINISHED" in bpy.ops.slr.export_anim(filepath=path, static_pose=True)
    a = anim_export.read_anim(path)
    q = _decode_rot(a["joints"]["mShoulderLeft"][1][0])
    target = pose_engine.sl_euler(-45, 0, 0)
    assert abs(q.dot(target)) > 0.9999, (q, target)
    qr = _decode_rot(a["joints"]["mShoulderRight"][1][0])
    assert abs(qr.dot(pose_engine.sl_euler(45, 0, 0))) > 0.9999


@case
def hand_face_poses_and_mirror():
    arm = rig()
    select([arm], arm)
    for k in anim_library.HAND_POSES:
        assert "FINISHED" in bpy.ops.slr.hand_pose(pose=k)
    for k in anim_library.FACE_POSES:
        assert "FINISHED" in bpy.ops.slr.face_pose(pose=k)
    pose_engine.reset_pose(arm)
    pose_engine.apply_pose(arm, local={"mShoulderLeft": pose_engine.sl_euler(-30, 10, 20)})
    bpy.ops.slr.mirror_pose(direction="L2R")
    ctx().view_layer.update()
    s = pose_engine.sample(arm)
    expect = pose_engine.mirror_quat(pose_engine.sl_euler(-30, 10, 20))
    assert abs(s["mShoulderRight"][0].dot(expect)) > 0.9999


@case
def retarget_mixamo():
    src = rig()
    src.name = "Mixamo"
    names = {"mPelvis": "mixamorig:Hips", "mTorso": "mixamorig:Spine", "mChest": "mixamorig:Spine2",
             "mNeck": "mixamorig:Neck", "mHead": "mixamorig:Head", "mShoulderLeft": "mixamorig:LeftArm",
             "mElbowLeft": "mixamorig:LeftForeArm", "mHipLeft": "mixamorig:LeftUpLeg"}
    for b in src.data.bones:
        if b.name in names:
            b.name = names[b.name]
    src.animation_data_create()
    src.animation_data.action = bpy.data.actions.new("mix")
    pb = src.pose.bones["mixamorig:LeftArm"]
    pb.rotation_mode = "QUATERNION"
    for f, ang in ((1, 0.0), (10, 60.0)):
        pose_engine.apply_pose(src, local={"mixamorig:LeftArm": pose_engine.sl_euler(-ang, 0, 0)})
        pb.keyframe_insert("rotation_quaternion", frame=f)
    tgt = rig()
    select([src, tgt], tgt)
    assert "FINISHED" in bpy.ops.slr.retarget()
    ctx().scene.frame_set(10)
    s = pose_engine.sample(tgt)
    assert abs(s["mShoulderLeft"][2].dot(pose_engine.sl_euler(-60, 0, 0))) > 0.999


@case
def attachment_points_and_offset():
    arm = rig()
    select([arm], arm)
    assert "FINISHED" in bpy.ops.slr.show_attachments()
    coll = bpy.data.collections[f"SL_Anclajes_{arm.name}"]
    assert len(coll.objects) == len(attachments.BODY_POINTS) == 47
    chest = next(o for o in coll.objects if o["sl_attach_id"] == 1)
    bpy.ops.mesh.primitive_cube_add(size=0.05)
    cube = ctx().active_object
    cube.matrix_world = chest.matrix_world.copy()
    ctx().view_layer.update()
    pos, rot = attachments.sl_offset(arm, cube, 1)
    assert pos.length < 1e-4 and all(abs(r) < 0.01 for r in rot), (pos, rot)


@case
def clothing_tools():
    body = body_mesh()
    select([body], body)
    bpy.ops.slr.wizard()
    bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=0.2, depth=0.5, location=(0, 0, 1.2))
    shirt = ctx().active_object
    select([shirt, body], body)
    assert "FINISHED" in bpy.ops.slr.fit_clothing()
    assert shirt.modifiers.get("SL_SinAtravesar") is not None
    select([shirt], shirt)
    assert "FINISHED" in bpy.ops.slr.make_sizes()
    assert len(bpy.data.collections[f"SL_Tallas_{shirt.name}"].objects) == 7
    select([body], body)
    assert "FINISHED" in bpy.ops.slr.alpha_zones()
    assert len(body.material_slots) == 8


@case
def mesh_tools_and_physics():
    bpy.ops.mesh.primitive_cube_add()
    a = ctx().active_object
    bpy.ops.mesh.primitive_cube_add()
    b = ctx().active_object
    select([a, b], a)
    bpy.ops.object.join()
    obj = ctx().active_object
    obj.data.uv_layers.remove(obj.data.uv_layers[0])
    select([obj], obj)
    before = len(obj.data.vertices)
    bpy.ops.slr.optimize()
    assert len(obj.data.vertices) < before
    assert "FINISHED" in bpy.ops.slr.auto_uv()
    assert obj.data.uv_layers
    for shape in ("BOX", "SIMPLE", "HULL"):
        select([obj], obj)
        assert "FINISHED" in bpy.ops.slr.make_physics(shape=shape)
        assert bpy.data.objects.get(f"{obj.name}_PHYS") is not None
    vg = obj.vertex_groups.new(name="custom_bone")
    vg.add(range(len(obj.data.vertices)), 0.5, "REPLACE")
    obj.vertex_groups.active_index = vg.index
    assert "FINISHED" in bpy.ops.slr.merge_group(target="mChest")
    assert obj.vertex_groups.get("mChest") and not obj.vertex_groups.get("custom_bone")
    d = tempfile.mkdtemp(dir=OUT)
    select([obj], obj)
    assert "FINISHED" in bpy.ops.slr.batch_export(directory=d)
    assert os.listdir(d)


@case
def textures_pbr_orm_resize():
    d = tempfile.mkdtemp(dir=OUT)
    for name in ("wood_basecolor", "wood_normal", "wood_roughness", "wood_metallic"):
        img = bpy.data.images.new(name, 600, 300)
        img.filepath_raw = os.path.join(d, name + ".png")
        img.file_format = "PNG"
        img.save()
    bpy.ops.mesh.primitive_cube_add()
    obj = ctx().active_object
    assert "FINISHED" in bpy.ops.slr.pbr_from_folder(directory=d)
    mat = obj.active_material
    linked = {l.to_socket.name for l in mat.node_tree.links}
    assert {"Base Color", "Roughness", "Metallic", "Normal"} <= linked, linked
    assert "FINISHED" in bpy.ops.slr.pack_orm()
    assert any(i.name.endswith("_ORM") for i in bpy.data.images)
    select([obj], obj)
    assert "FINISHED" in bpy.ops.slr.resize_textures(max_size="512")
    sizes = {tuple(n.image.size) for n in mat.node_tree.nodes if n.type == "TEX_IMAGE"}
    assert all(w & (w - 1) == 0 and h & (h - 1) == 0 and w <= 512 for w, h in sizes), sizes


@case
def certificate_and_score():
    body = body_mesh(2)
    select([body], body)
    bpy.ops.slr.wizard()
    st = hud.analyze(body)[0]
    assert st["score"] >= 85, st
    path = os.path.join(OUT, "cert.html")
    select([body], body)
    assert "FINISHED" in bpy.ops.slr.certificate(filepath=path, open_after=False)
    html = open(path, encoding="utf-8").read()
    assert "CERTIFICADO SL READY" in html and body.name in html


@case
def ui_helpers():
    assert len(previews.preset_items(None, ctx())) == len(presets.PRESETS)
    img = previews._render("FURRY_DIGI")
    assert img.shape == (128, 128, 4) and img[:, :, 0].max() > 0.9
    from sl_rigger import ui_ops
    steps = ui_ops.guide_steps(ctx())
    assert len(steps) == 5 and not steps[1][1]
    arm = rig("GIANT")
    select([arm], arm)
    bpy.ops.slr.isolate_group(group="HANDS")
    assert arm.data.bones["mPelvis"].hide and not arm.data.bones["mHandIndex1Left"].hide
    bpy.ops.slr.isolate_group(group="ALL")
    assert not arm.data.bones["mPelvis"].hide
    bpy.ops.slr.scale_to_height(height=2.5)
    assert abs(ui_ops.rig_height(arm) - 2.5) < 1e-3
    ui_ops._preset_dir = lambda: OUT
    bpy.ops.slr.save_preset(name="Prueba gigante")
    assert "Prueba_gigante" in ui_ops.custom_presets()
    bpy.ops.slr.load_preset(preset="Prueba_gigante")
    new = ctx().active_object
    p1 = (arm.matrix_world @ arm.data.bones["mHandIndex1Left"].head_local)
    p2 = (new.matrix_world @ new.data.bones["mHandIndex1Left"].head_local)
    assert (p1 - p2).length < 1e-3, (p1, p2)


class _FakeLayout:
    """Lienzo simulado: acepta cualquier llamada de UILayout y registra los operadores usados."""
    used_ops = set()

    def __getattr__(self, name):
        if name in ("operator", "operator_menu_enum"):
            def op(idname, *args, **kw):
                _FakeLayout.used_ops.add(idname)
                return _FakeProps()
            return op
        if name == "menu_pie" or name in ("row", "column", "box", "grid_flow", "split", "column_flow"):
            return lambda *a, **k: _FakeLayout()
        return lambda *a, **k: None

    def __setattr__(self, name, value):
        pass


class _FakeProps:
    def __setattr__(self, name, value):
        pass


@case
def ui_draw_all_tabs():
    from sl_rigger import ui
    body = body_mesh(2)
    select([body], body)
    bpy.ops.slr.wizard()
    arm = skeleton.find_armature(body)
    panel = ui.SLR_PT_main
    for active in (None, body, arm):
        if active is None:
            for o in ctx().view_layer.objects:
                o.select_set(False)
            ctx().view_layer.objects.active = None
        else:
            select([active], active)
        for tab, *_ in ui.TABS:
            ctx().scene.slr_tab = tab
            methods = {k: v for k, v in panel.__dict__.items() if callable(v)}
            fake = type("P", (), {**methods, "layout": _FakeLayout()})()
            panel.draw(fake, ctx())
            panel.draw_header(fake, ctx())
    for menu in (ui.SLR_MT_pie, ui.SLR_MT_pie_anim):
        menu.draw(type("M", (), {"layout": _FakeLayout()})(), ctx())
    select([body], body)
    ui.statusbar(type("S", (), {"layout": _FakeLayout()})(), ctx())
    ui.header_chip(type("H", (), {"layout": _FakeLayout()})(), ctx())
    from sl_rigger import ui_ops
    for op in (ui_ops.SLR_OT_welcome, ui_ops.SLR_OT_cheatsheet):
        op.draw(type("O", (), {"layout": _FakeLayout()})(), ctx())
    missing = [i for i in _FakeLayout.used_ops if not hasattr(getattr(bpy.ops, i.split(".")[0]), i.split(".")[1])
               or getattr(getattr(bpy.ops, i.split(".")[0]), i.split(".")[1]).get_rna_type() is None]
    assert not missing, missing
    assert len(_FakeLayout.used_ops) >= 45, len(_FakeLayout.used_ops)

if __name__ == "__main__":
    sl_rigger.register()
    for fn in TESTS:
        run(fn)
    sl_rigger.unregister()
    failed = [r for r in RESULTS if not r[1]]
    for name, ok, err in RESULTS:
        print(("PASS " if ok else "FAIL ") + name)
        if err:
            print(err)
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} pruebas correctas")
    sys.exit(1 if failed else 0)

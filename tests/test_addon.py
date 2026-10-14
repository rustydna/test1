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
from sl_rigger import hud, presets, skeleton, weights  # noqa: E402

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
    src = open(os.path.join(os.path.dirname(sl_rigger.__file__), "ui.py"), encoding="utf-8").read()
    used = set(re.findall(r'icon="([A-Z_]+)"', src)) | set(re.findall(r'"([A-Z_]+)" if', src))
    used |= set(re.findall(r'else "([A-Z_]+)"', src))
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

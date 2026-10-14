"""Esqueleto de Second Life y creación del rig en Blender.

Los datos vienen del avatar_skeleton.xml oficial (ver skeleton_data.py): 133 huesos
(26 base + 107 Bento) y 26 volúmenes de colisión para fitted mesh.

Coordenadas SL: X delante, Y izquierda, Z arriba (metros). En Blender el rig mira
hacia -Y (vista frontal); al exportar se rota a ejes SL.
"""

import bpy
from mathutils import Euler, Matrix, Vector

from . import compat
from .skeleton_data import SKELETON

# Información por nombre: dict con parent, pos, end, group, support, kind, rot, scale.
SL_INFO = {
    r[0]: {"parent": r[1], "pos": r[2], "end": r[3], "group": r[4], "support": r[5],
           "kind": r[6], "rot": r[7], "scale": r[8]}
    for r in SKELETON
}
ALL_SL_BONE_NAMES = set(SL_INFO)
SL_BONE_ORDER = [r[0] for r in SKELETON]

# Límite del visor (LL_MAX_JOINTS_PER_MESH_OBJECT en lljoint.h).
SL_MAX_JOINTS_PER_MESH = 110

# Grupos de la interfaz → grupos del XML.
DEFORM_GROUPS = {
    "HANDS": ("Manos Bento", ("Hand",), "THEME09"),
    "FACE": ("Cara Bento", ("Face", "Eyes", "Mouth", "Lips", "Nose"), "THEME06"),
    "EARS": ("Orejas", ("Ears",), "THEME11"),
    "TAIL": ("Cola", ("Tail",), "THEME02"),
    "WINGS": ("Alas", ("Wing",), "THEME07"),
    "HIND": ("Patas traseras", ("Limb",), "THEME08"),
    "GROIN": ("Ingle", ("Groin",), "THEME10"),
    "SPINE": ("Columna Bento", ("Spine",), "THEME04"),
    "VOLUMES": ("Fitted mesh (volúmenes)", ("Collision",), "THEME05"),
}
_BASE_GROUPS = ("Torso", "Arms", "Legs", "Extra")


def group_key(name):
    grp = SL_INFO[name]["group"]
    for key, (_, xml_groups, _) in DEFORM_GROUPS.items():
        if grp in xml_groups:
            return key
    return "BASE"


# Rotación de ejes Blender (frente -Y) -> Second Life (frente +X): +90º en Z.
BLENDER_TO_SL = Matrix.Rotation(1.5707963267948966, 4, "Z")
SL_TO_BLENDER = BLENDER_TO_SL.inverted()


def bone_table(preset=None):
    """[(nombre, padre, pos)] de todo el esqueleto con el preset aplicado."""
    from . import presets
    rows = [(n, i["parent"], i["pos"]) for n, i in ((n, SL_INFO[n]) for n in SL_BONE_ORDER)]
    return presets.apply(rows, preset)


def world_positions_sl(bones):
    pos = {}
    for name, parent, offset in bones:
        base = pos[parent] if parent else Vector((0.0, 0.0, 0.0))
        pos[name] = base + Vector(offset)
    return pos


def cv_local_matrix(name, local_pos):
    """Matriz local de un volumen de colisión: traslación · rotación · escala oficiales."""
    info = SL_INFO[name]
    rot = Euler([v * 0.017453292519943295 for v in info["rot"]], "XYZ").to_matrix().to_4x4()
    sx, sy, sz = info["scale"]
    scale = Matrix.Diagonal((sx, sy, sz, 1.0))
    return Matrix.Translation(local_pos) @ rot @ scale


def create_sl_armature(context, name="SL_Avatar", preset=None, deform=("HANDS",)):
    """Crea el rig completo. `deform`: grupos (claves de DEFORM_GROUPS) que deforman."""
    bones = bone_table(preset)
    pos_sl = world_positions_sl(bones)
    rot3 = SL_TO_BLENDER.to_3x3()
    scale = _preset_scale(preset)

    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    context.collection.objects.link(arm_obj)
    arm_obj.location = context.scene.cursor.location.copy()
    arm_obj["sl_rig"] = True
    arm_obj["sl_preset"] = preset or "HUMAN"
    arm_data.display_type = "STICK"
    arm_obj.show_in_front = True

    for o in context.view_layer.objects:
        o.select_set(False)
    context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    deform = set(deform)
    edit = arm_data.edit_bones
    for n, parent, _ in bones:
        info = SL_INFO[n]
        eb = edit.new(n)
        head = rot3 @ pos_sl[n]
        end = Vector(info["end"]) * scale
        if end.length < 1e-4:
            end = Vector((0.0, 0.0, 0.02))
        eb.head = head
        eb.tail = head + rot3 @ end
        key = group_key(n)
        eb.use_deform = key == "BASE" or key in deform
        eb.use_connect = False
    for n, parent, _ in bones:
        if parent:
            edit[n].parent = edit[parent]
    bpy.ops.object.mode_set(mode="OBJECT")

    groups = {"Cuerpo": ("THEME01", [n for n in SL_BONE_ORDER if group_key(n) == "BASE"], True)}
    for key, (label, _, theme) in DEFORM_GROUPS.items():
        names = [n for n in SL_BONE_ORDER if group_key(n) == key]
        groups[label] = (theme, names, key != "VOLUMES" or key in deform)
    compat.assign_bone_groups(arm_obj, groups)
    return arm_obj


def _preset_scale(preset):
    from . import presets
    return presets.PRESETS.get(preset or "HUMAN", presets.PRESETS["HUMAN"]).get("scale", 1.0)


def set_group_deform(arm_obj, key, enabled):
    for b in arm_obj.data.bones:
        if b.name in SL_INFO and group_key(b.name) == key:
            b.use_deform = enabled


def is_sl_armature(obj):
    return obj is not None and obj.type == "ARMATURE" and "mPelvis" in obj.data.bones


def find_armature(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE" and mod.object is not None:
            return mod.object
    if mesh_obj.parent is not None and mesh_obj.parent.type == "ARMATURE":
        return mesh_obj.parent
    return None


def joints_with_ancestors(armature, names):
    """Huesos SL usados más todos sus antecesores SL, en orden del esqueleto."""
    bones = armature.data.bones
    keep = set()
    for n in names:
        b = bones.get(n)
        while b is not None:
            if b.name in SL_INFO:
                if b.name in keep:
                    break
                keep.add(b.name)
            b = b.parent
    return [n for n in SL_BONE_ORDER if n in keep]

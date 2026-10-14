"""Esqueleto de Second Life (avatar_skeleton.xml) y creación del rig en Blender.

Las posiciones están en coordenadas de Second Life (metros):
    X = hacia delante, Y = izquierda del avatar, Z = arriba.
Cada desplazamiento es relativo al hueso padre.

En Blender el rig se crea mirando hacia -Y (convención habitual de Blender:
vista frontal, la izquierda del personaje en +X). Al exportar se rota a los
ejes de Second Life.
"""

import bpy
from mathutils import Matrix, Vector

# (nombre, padre, desplazamiento respecto al padre en ejes SL)
SL_BASE_BONES = [
    ("mPelvis", None, (0.0, 0.0, 1.067015)),
    ("mTorso", "mPelvis", (0.0, 0.0, 0.084073)),
    ("mChest", "mTorso", (-0.015368, 0.0, 0.204892)),
    ("mNeck", "mChest", (-0.009507, 0.0, 0.251108)),
    ("mHead", "mNeck", (0.0, 0.0, 0.075630)),
    ("mSkull", "mHead", (0.0, 0.0, 0.079000)),
    ("mEyeRight", "mHead", (0.098466, -0.036000, 0.079000)),
    ("mEyeLeft", "mHead", (0.098461, 0.036000, 0.079000)),
    ("mCollarLeft", "mChest", (-0.020927, 0.084665, 0.165396)),
    ("mShoulderLeft", "mCollarLeft", (0.0, 0.079000, 0.0)),
    ("mElbowLeft", "mShoulderLeft", (0.0, 0.248000, 0.0)),
    ("mWristLeft", "mElbowLeft", (0.0, 0.205000, 0.0)),
    ("mCollarRight", "mChest", (-0.020927, -0.085000, 0.165396)),
    ("mShoulderRight", "mCollarRight", (0.0, -0.079418, 0.0)),
    ("mElbowRight", "mShoulderRight", (0.0, -0.248000, 0.0)),
    ("mWristRight", "mElbowRight", (0.0, -0.205000, 0.0)),
    ("mHipRight", "mPelvis", (0.033620, -0.128806, -0.041086)),
    ("mKneeRight", "mHipRight", (-0.000780, 0.048635, -0.491810)),
    ("mAnkleRight", "mKneeRight", (-0.029148, 0.001049, -0.468894)),
    ("mFootRight", "mAnkleRight", (0.111956, 0.0, -0.061632)),
    ("mToeRight", "mFootRight", (0.105043, -0.010000, 0.0)),
    ("mHipLeft", "mPelvis", (0.033757, 0.126765, -0.041086)),
    ("mKneeLeft", "mHipLeft", (-0.000887, -0.045568, -0.491053)),
    ("mAnkleLeft", "mKneeLeft", (-0.029156, -0.001918, -0.468899)),
    ("mFootLeft", "mAnkleLeft", (0.111956, 0.0, -0.061632)),
    ("mToeLeft", "mFootLeft", (0.105137, 0.010000, 0.0)),
]

# Dedos Bento (mano izquierda; la derecha se obtiene reflejando Y).
_BENTO_LEFT_HAND = [
    ("mHandThumb1Left", "mWristLeft", (0.031, 0.026, 0.004)),
    ("mHandThumb2Left", "mHandThumb1Left", (0.028, 0.032, -0.001)),
    ("mHandThumb3Left", "mHandThumb2Left", (0.023, 0.031, -0.001)),
    ("mHandIndex1Left", "mWristLeft", (0.038, 0.097, 0.015)),
    ("mHandIndex2Left", "mHandIndex1Left", (0.017, 0.036, -0.006)),
    ("mHandIndex3Left", "mHandIndex2Left", (0.014, 0.032, -0.006)),
    ("mHandMiddle1Left", "mWristLeft", (0.013, 0.101, 0.015)),
    ("mHandMiddle2Left", "mHandMiddle1Left", (-0.001, 0.040, -0.006)),
    ("mHandMiddle3Left", "mHandMiddle2Left", (-0.001, 0.049, -0.008)),
    ("mHandRing1Left", "mWristLeft", (-0.010, 0.099, 0.009)),
    ("mHandRing2Left", "mHandRing1Left", (-0.013, 0.038, -0.008)),
    ("mHandRing3Left", "mHandRing2Left", (-0.013, 0.040, -0.009)),
    ("mHandPinky1Left", "mWristLeft", (-0.031, 0.095, 0.003)),
    ("mHandPinky2Left", "mHandPinky1Left", (-0.024, 0.025, -0.006)),
    ("mHandPinky3Left", "mHandPinky2Left", (-0.015, 0.018, -0.004)),
]


def _mirror(entries):
    out = []
    for name, parent, (x, y, z) in entries:
        out.append((name.replace("Left", "Right"), parent.replace("Left", "Right"), (x, -y, z)))
    return out


SL_BENTO_HAND_BONES = _BENTO_LEFT_HAND + _mirror(_BENTO_LEFT_HAND)

# Hueso hacia el que apunta la cola de cada hueso (si no, se prolonga la dirección del padre).
_TAIL_TARGET = {
    "mPelvis": "mTorso",
    "mTorso": "mChest",
    "mChest": "mNeck",
    "mNeck": "mHead",
    "mHead": "mSkull",
}

# Todos los nombres de hueso conocidos (para validar grupos de vértices).
ALL_SL_BONE_NAMES = {b[0] for b in SL_BASE_BONES} | {b[0] for b in SL_BENTO_HAND_BONES}

# Rotación de ejes Blender (frente -Y) -> Second Life (frente +X): +90º en Z.
BLENDER_TO_SL = Matrix.Rotation(1.5707963267948966, 4, "Z")
SL_TO_BLENDER = BLENDER_TO_SL.inverted()


def bone_table(include_bento_hands=True):
    bones = list(SL_BASE_BONES)
    if include_bento_hands:
        bones += SL_BENTO_HAND_BONES
    return bones


def world_positions_sl(bones):
    """Posición absoluta (ejes SL) de cada hueso."""
    pos = {}
    for name, parent, offset in bones:
        base = pos[parent] if parent else Vector((0.0, 0.0, 0.0))
        pos[name] = base + Vector(offset)
    return pos


def create_sl_armature(context, name="SL_Avatar", include_bento_hands=True):
    bones = bone_table(include_bento_hands)
    pos_sl = world_positions_sl(bones)
    pos = {n: (SL_TO_BLENDER.to_3x3() @ p) for n, p in pos_sl.items()}
    children = {}
    for n, parent, _ in bones:
        children.setdefault(parent, []).append(n)

    arm_data = bpy.data.armatures.new(name)
    arm_obj = bpy.data.objects.new(name, arm_data)
    context.collection.objects.link(arm_obj)
    arm_obj.location = context.scene.cursor.location.copy()
    arm_obj["sl_rig"] = True
    arm_data.display_type = "STICK"
    arm_obj.show_in_front = True

    for o in context.view_layer.objects:
        o.select_set(False)
    context.view_layer.objects.active = arm_obj
    arm_obj.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")

    edit = arm_data.edit_bones
    for n, parent, _ in bones:
        eb = edit.new(n)
        head = pos[n]
        target = _TAIL_TARGET.get(n)
        kids = children.get(n, [])
        if target is None and len(kids) == 1:
            target = kids[0]
        if target is None and n.startswith("mWrist") and ("mHandMiddle1" + n[6:]) in pos:
            target = "mHandMiddle1" + n[6:]
        if target is not None and (pos[target] - head).length > 1e-4:
            tail = pos[target].copy()
        else:
            direction = head - pos[parent] if parent else Vector((0, 0, 1))
            if direction.length < 1e-4:
                direction = Vector((0, 0, 1))
            length = 0.02 if "Hand" in n or "Eye" in n else 0.06
            tail = head + direction.normalized() * length
        eb.head = head
        eb.tail = tail
        eb.use_deform = True
        eb.use_connect = False
    for n, parent, _ in bones:
        if parent:
            edit[n].parent = edit[parent]

    bpy.ops.object.mode_set(mode="OBJECT")
    return arm_obj


def is_sl_armature(obj):
    return obj is not None and obj.type == "ARMATURE" and "mPelvis" in obj.data.bones


def find_armature(mesh_obj):
    for mod in mesh_obj.modifiers:
        if mod.type == "ARMATURE" and mod.object is not None:
            return mod.object
    if mesh_obj.parent is not None and mesh_obj.parent.type == "ARMATURE":
        return mesh_obj.parent
    return None

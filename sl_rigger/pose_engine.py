"""Motor de poses en ejes de Second Life.

En SL todas las articulaciones tienen rotación identidad en reposo y sus ejes son los
del avatar (X delante, Y izquierda, Z arriba). Por eso una pose se describe con
rotaciones *locales* de cada articulación respecto a su padre, en esos ejes.

Este módulo convierte entre:
  * rotaciones locales SL (cuaterniones) ↔ pose de los huesos de Blender
  * y muestrea la pose evaluada de Blender para exportar .anim.
"""

import math

from mathutils import Euler, Matrix, Quaternion, Vector

from .skeleton import BLENDER_TO_SL, SL_INFO

_C = BLENDER_TO_SL.to_3x3()
_CI = _C.inverted()


def sl_euler(x=0.0, y=0.0, z=0.0):
    """Cuaternión SL a partir de ángulos en grados (X: alabeo, Y: cabeceo, Z: giro)."""
    return Euler((math.radians(x), math.radians(y), math.radians(z)), "XYZ").to_quaternion()


def mirror_name(name):
    if "Left" in name:
        return name.replace("Left", "Right")
    if "Right" in name:
        return name.replace("Right", "Left")
    return name


def mirror_quat(q):
    """Refleja una rotación SL izquierda ↔ derecha (plano XZ): invierte los ejes X y Z."""
    return Quaternion((q.w, -q.x, q.y, -q.z))


def mirror_vec(v):
    return Vector((v.x, -v.y, v.z))


def _hierarchy(arm):
    """Huesos del armature ordenados de padres a hijos."""
    order, seen = [], set()

    def visit(b):
        if b.name in seen:
            return
        if b.parent is not None:
            visit(b.parent)
        seen.add(b.name)
        order.append(b)

    for b in arm.data.bones:
        visit(b)
    return order


def _rot_world_sl(arm, pose_rot3, rest_rot3):
    """Rotación de mundo (delta respecto al reposo) en ejes SL."""
    aw = arm.matrix_world.to_3x3().normalized()
    d = aw @ pose_rot3 @ rest_rot3.inverted() @ aw.inverted()
    return (_C @ d @ _CI).to_quaternion()


def apply_pose(arm, local=None, world=None, offsets=None, keep_others=True):
    """Pone el armature en una pose.

    local:   {hueso: Quaternion}  rotación local SL respecto al padre
    world:   {hueso: Quaternion}  rotación de mundo SL (delta respecto al reposo)
    offsets: {hueso: Vector}      desplazamiento en ejes SL (metros) respecto al reposo
    keep_others: los huesos no indicados conservan su pose actual (si no, reposo).
    """
    local = local or {}
    world = world or {}
    offsets = offsets or {}
    aw = arm.matrix_world.to_3x3().normalized()
    aw_inv = aw.inverted()
    pose_m = {}
    world_sl = {}
    for bone in _hierarchy(arm):
        pb = arm.pose.bones[bone.name]
        rest = bone.matrix_local
        parent = bone.parent
        if parent is not None:
            base = pose_m[parent.name] @ parent.matrix_local.inverted() @ rest
        else:
            base = rest.copy()
        name = bone.name
        if name in local or name in world or name in offsets:
            if name in world:
                w = world[name]
            else:
                pw = world_sl.get(parent.name, Quaternion()) if parent is not None else Quaternion()
                w = pw @ local.get(name, Quaternion())
            d = aw_inv @ (_CI @ w.to_matrix() @ _C) @ aw
            rot = d @ rest.to_3x3()
            loc = base.to_translation()
            if name in offsets:
                loc = loc + aw_inv @ (_CI @ Vector(offsets[name]))
            m = Matrix.Translation(loc) @ rot.to_4x4()
            basis = base.inverted() @ m
            pb.rotation_mode = "QUATERNION"
            pb.location = basis.to_translation()
            pb.rotation_quaternion = basis.to_quaternion()
        elif not keep_others:
            pb.location = (0.0, 0.0, 0.0)
            pb.rotation_mode = "QUATERNION"
            pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
            pb.scale = (1.0, 1.0, 1.0)
        basis = pb.matrix_basis
        m = base @ basis
        pose_m[name] = m
        world_sl[name] = _rot_world_sl(arm, m.to_3x3(), rest.to_3x3())
    return pose_m


def key_pose(arm, frame, names):
    for n in names:
        pb = arm.pose.bones.get(n)
        if pb is None:
            continue
        pb.keyframe_insert("rotation_quaternion", frame=frame)
        pb.keyframe_insert("location", frame=frame)


def reset_pose(arm):
    for pb in arm.pose.bones:
        pb.location = (0.0, 0.0, 0.0)
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = (1.0, 0.0, 0.0, 0.0)
        pb.scale = (1.0, 1.0, 1.0)


def sample(arm):
    """Pose evaluada actual → {hueso SL: (rot local SL, pos mundo SL, rot mundo SL)}."""
    aw = arm.matrix_world
    out = {}
    world_rot = {}
    world_pos = {}
    for bone in _hierarchy(arm):
        if bone.name not in SL_INFO or SL_INFO[bone.name]["kind"] != "bone":
            continue
        pb = arm.pose.bones[bone.name]
        wr = _rot_world_sl(arm, pb.matrix.to_3x3().normalized(), bone.matrix_local.to_3x3().normalized())
        wp = _C @ (aw @ pb.matrix.to_translation())
        parent = bone.parent
        while parent is not None and parent.name not in world_rot:
            parent = parent.parent
        lr = (world_rot[parent.name].inverted() @ wr) if parent is not None else wr
        world_rot[bone.name] = wr
        world_pos[bone.name] = wp
        out[bone.name] = (lr, wp, wr, parent.name if parent is not None else None)
    return out


def rest_positions_sl(arm):
    """Posición de mundo SL de cada hueso en reposo."""
    aw = arm.matrix_world
    return {b.name: _C @ (aw @ b.head_local) for b in arm.data.bones if b.name in SL_INFO}

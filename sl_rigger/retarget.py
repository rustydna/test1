"""Retarget de animaciones (Mixamo, Unreal, Rigify) al esqueleto SL.

Para cada hueso emparejado se copia su rotación de mundo *respecto a su reposo*
(delta), así funciona aunque los huesos tengan ejes distintos. La pelvis copia
además el desplazamiento de la cadera, escalado por la diferencia de altura.
"""

import bpy
from mathutils import Vector

from . import mappings
from . import pose_engine as pe
from .skeleton import BLENDER_TO_SL, is_sl_armature

_C = BLENDER_TO_SL.to_3x3()
_CI = _C.inverted()

# Para cada hueso SL, el hueso de origen preferido (el más profundo cuando varios coinciden).
_PREFER_DEEPEST = {"mChest": ("Spine2", "spine_03", "spine.003", "Spine1", "spine_02")}


def build_map(source_arm):
    names = [b.name for b in source_arm.data.bones]
    preset = mappings.detect_preset(names)
    if preset is None:
        return None, {}
    table = mappings.PRESETS[preset][1]
    by_target = {}
    for n in names:
        tgt = table.get(mappings.normalize_name(n))
        if tgt:
            by_target.setdefault(tgt, []).append(n)
    result = {}
    for tgt, srcs in by_target.items():
        if len(srcs) > 1:
            order = _PREFER_DEEPEST.get(tgt, ())
            srcs.sort(key=lambda s: (order.index(mappings.normalize_name(s))
                                     if mappings.normalize_name(s) in order else 99,
                                     -len(source_arm.data.bones[s].parent_recursive)))
        result[tgt] = srcs[0]
    return preset, result


def _world_delta(arm, pb):
    aw = arm.matrix_world.to_3x3().normalized()
    rest = aw @ pb.bone.matrix_local.to_3x3().normalized()
    pose = aw @ pb.matrix.to_3x3().normalized()
    return (_C @ (pose @ rest.inverted()) @ _CI).to_quaternion()


def retarget(context, source, target, frame_start, frame_end, flip=False):
    preset, bone_map = build_map(source)
    if not bone_map:
        raise ValueError("No reconozco los huesos del esqueleto de origen (Mixamo, Unreal o Rigify)")
    hips_src = bone_map.get("mPelvis")
    scene = context.scene
    target.animation_data_create()
    action = bpy.data.actions.new(f"SL_retarget_{source.name}")
    target.animation_data.action = action
    pe.reset_pose(target)

    src_hips_rest = None
    scale = 1.0
    if hips_src:
        hb = source.data.bones[hips_src]
        src_hips_rest = source.matrix_world @ hb.head_local
        tgt_hips = target.matrix_world @ target.data.bones["mPelvis"].head_local
        if src_hips_rest.z > 1e-4:
            scale = tgt_hips.z / src_hips_rest.z
    flip_q = pe.sl_euler(0, 0, 180) if flip else None

    wm = context.window_manager
    wm.progress_begin(frame_start, frame_end)
    old = scene.frame_current
    keyed = set()
    try:
        for f in range(frame_start, frame_end + 1):
            scene.frame_set(f)
            world = {}
            for tgt, src in bone_map.items():
                if tgt not in target.data.bones:
                    continue
                q = _world_delta(source, source.pose.bones[src])
                if flip_q is not None:
                    q = flip_q @ q @ flip_q.inverted()
                world[tgt] = q
            offsets = {}
            if hips_src:
                cur = source.matrix_world @ source.pose.bones[hips_src].head
                d = _C @ ((cur - src_hips_rest) * scale)
                if flip:
                    d = Vector((-d.x, -d.y, d.z))
                offsets["mPelvis"] = d
            pe.apply_pose(target, world=world, offsets=offsets, keep_others=False)
            keyed |= set(world) | set(offsets)
            pe.key_pose(target, f, keyed)
            wm.progress_update(f)
    finally:
        wm.progress_end()
        scene.frame_set(old)
    return preset, len(bone_map)


class SLR_OT_retarget(bpy.types.Operator):
    """Copia la animación de un esqueleto Mixamo/Unreal/Rigify (seleccionado) al esqueleto SL (activo)"""
    bl_idname = "slr.retarget"
    bl_label = "Retarget a SL"
    bl_options = {"REGISTER", "UNDO"}

    flip: bpy.props.BoolProperty(name="Girar 180°", default=False,
                                 description="Si el personaje de origen mira hacia +Y en lugar de −Y")
    use_scene_range: bpy.props.BoolProperty(name="Rango de la escena", default=False,
                                            description="Si no, usa el rango de la acción de origen")

    @classmethod
    def poll(cls, context):
        tgt = context.active_object
        srcs = [o for o in context.selected_objects if o.type == "ARMATURE" and o != tgt]
        if not is_sl_armature(tgt) or not srcs:
            cls.poll_message_set("Selecciona el esqueleto animado y, por último, el esqueleto SL (activo)")
            return False
        return True

    def execute(self, context):
        from . import hud
        target = context.active_object
        source = next(o for o in context.selected_objects if o.type == "ARMATURE" and o != target)
        fs, fe = context.scene.frame_start, context.scene.frame_end
        ad = source.animation_data
        if not self.use_scene_range and ad is not None and ad.action is not None:
            fs, fe = (int(round(v)) for v in ad.action.frame_range)
            context.scene.frame_start, context.scene.frame_end = fs, fe
        try:
            preset, n = retarget(context, source, target, fs, fe, self.flip)
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        msg = f"Retarget {mappings.PRESETS[preset][0]} → SL: {n} huesos, fotogramas {fs}–{fe}"
        hud.toast(msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


classes = (SLR_OT_retarget,)

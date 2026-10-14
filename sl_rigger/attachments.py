"""Puntos de anclaje de SL: verlos en el visor y calcular la posición de un accesorio.

Un accesorio estático (pelo, zapatos, gafas…) se sube como objeto y se coloca en SL
con la posición y rotación del menú Editar. Este módulo calcula esos números a partir
de dónde está el objeto respecto al esqueleto en Blender.
"""

import math

import bpy
from mathutils import Euler, Matrix, Vector

from .attachment_data import ATTACHMENTS
from .skeleton import BLENDER_TO_SL, find_armature, is_sl_armature

_C = BLENDER_TO_SL.to_3x3()
_CI = _C.inverted()
BODY_POINTS = [a for a in ATTACHMENTS if not a[5]]
_BY_ID = {a[0]: a for a in ATTACHMENTS}


def point_items(self=None, context=None):
    return [(str(a[0]), a[1], f"Hueso {a[2]}") for a in BODY_POINTS]


def point_frame_sl(arm, point_id):
    """Matriz 4x4 del punto de anclaje en coordenadas SL del armature."""
    pid, name, joint, pos, rot, _ = _BY_ID[point_id]
    if joint == "mRoot":  # raíz del avatar: el origen del esqueleto
        joint_sl = _C @ arm.matrix_world.to_translation()
    else:
        bone = arm.data.bones.get(joint)
        if bone is None:
            raise ValueError(f"El esqueleto no tiene el hueso {joint}")
        joint_sl = _C @ (arm.matrix_world @ bone.head_local)
    r = Euler([math.radians(v) for v in rot], "XYZ").to_matrix().to_4x4()
    return Matrix.Translation(joint_sl + Vector(pos)) @ r


def sl_offset(arm, obj, point_id):
    """(posición, rotación en grados) del objeto respecto al punto, como en el editor de SL."""
    frame = point_frame_sl(arm, point_id)
    # El subidor de SL no gira los objetos estáticos: sus ejes locales son los de Blender.
    obj_sl = Matrix.Translation(_C @ obj.matrix_world.to_translation()) @ \
        (_C @ obj.matrix_world.to_3x3().normalized()).to_4x4()
    rel = frame.inverted() @ obj_sl
    pos = rel.to_translation()
    rot = rel.to_euler("XYZ")
    return pos, tuple(math.degrees(v) for v in rot)


class SLR_OT_show_attachments(bpy.types.Operator):
    """Muestra (o quita) los 47 puntos de anclaje del cuerpo de SL en el esqueleto activo"""
    bl_idname = "slr.show_attachments"
    bl_label = "Puntos de anclaje"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not is_sl_armature(context.active_object):
            cls.poll_message_set("Selecciona un esqueleto SL")
            return False
        return True

    def execute(self, context):
        arm = context.active_object
        cname = f"SL_Anclajes_{arm.name}"
        coll = bpy.data.collections.get(cname)
        if coll is not None:
            for o in list(coll.objects):
                bpy.data.objects.remove(o)
            bpy.data.collections.remove(coll)
            self.report({"INFO"}, "Puntos de anclaje ocultos")
            return {"FINISHED"}
        coll = bpy.data.collections.new(cname)
        context.scene.collection.children.link(coll)
        for a in BODY_POINTS:
            frame_sl = point_frame_sl(arm, a[0])
            m = Matrix.Translation(_CI @ frame_sl.to_translation()) @ (_CI @ frame_sl.to_3x3()).to_4x4()
            empty = bpy.data.objects.new(f"⚓ {a[1]}", None)
            empty.empty_display_type = "ARROWS"
            empty.empty_display_size = 0.04
            empty.matrix_world = m
            empty["sl_attach_id"] = a[0]
            coll.objects.link(empty)
            empty.parent = arm
            empty.matrix_parent_inverse = arm.matrix_world.inverted()
        self.report({"INFO"}, f"{len(BODY_POINTS)} puntos de anclaje en '{cname}'")
        return {"FINISHED"}


class SLR_OT_attachment_offset(bpy.types.Operator):
    """Calcula la posición y rotación que hay que escribir en SL para que el accesorio quede como en Blender"""
    bl_idname = "slr.attachment_offset"
    bl_label = "Posición para SL"
    bl_options = {"REGISTER"}

    point: bpy.props.EnumProperty(name="Punto de anclaje", items=point_items)

    @classmethod
    def poll(cls, context):
        objs = [o for o in context.selected_objects if o.type == "MESH"]
        arms = [o for o in context.selected_objects if is_sl_armature(o)]
        if not objs or (not arms and not any(find_armature(o) for o in objs)):
            cls.poll_message_set("Selecciona el accesorio y el esqueleto SL")
            return False
        return True

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        obj = next(o for o in context.selected_objects if o.type == "MESH")
        arm = next((o for o in context.selected_objects if is_sl_armature(o)), None) or find_armature(obj)
        pos, rot = sl_offset(arm, obj, int(self.point))
        name = _BY_ID[int(self.point)][1]
        text = (f"{obj.name} en '{name}':  Posición <{pos.x:.3f}, {pos.y:.3f}, {pos.z:.3f}>  "
                f"Rotación <{rot[0]:.1f}, {rot[1]:.1f}, {rot[2]:.1f}>")
        obj["sl_attach_point"] = name
        obj["sl_attach_pos"] = tuple(round(v, 4) for v in pos)
        obj["sl_attach_rot"] = tuple(round(v, 2) for v in rot)
        context.window_manager.clipboard = text
        self.report({"INFO"}, text + "  (copiado al portapapeles)")
        return {"FINISHED"}


classes = (SLR_OT_show_attachments, SLR_OT_attachment_offset)

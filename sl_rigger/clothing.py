"""Ropa: ajuste sin atravesar el cuerpo, tallas y zonas de alfa."""

import bpy

from . import compat
from .skeleton import SL_INFO, find_armature

SIZES = [("XXS", -0.006), ("XS", -0.003), ("S", 0.0), ("M", 0.003), ("L", 0.006), ("XL", 0.010), ("XXL", 0.014)]

# Zonas de alfa: cada una será un material (= una cara en SL, máximo 8).
ALPHA_ZONES = [
    ("Cabeza", ("mHead", "mNeck", "mSkull", "mFace", "mEye", "NECK", "HEAD")),
    ("Pecho", ("mChest", "mSpine3", "mSpine4", "mCollar", "CHEST", "PEC", "UPPER_BACK")),
    ("Vientre", ("mTorso", "mSpine1", "mSpine2", "mPelvis", "mGroin", "BELLY", "PELVIS", "BUTT",
                 "HANDLE", "LOWER_BACK", "mTail")),
    ("Brazo izq.", ("Left", "L_UPPER_ARM", "L_LOWER_ARM", "L_HAND")),
    ("Brazo der.", ("Right", "R_UPPER_ARM", "R_LOWER_ARM", "R_HAND")),
    ("Pierna izq.", ("mHipLeft", "mKneeLeft", "L_UPPER_LEG", "L_LOWER_LEG", "mHindLimb1Left", "mHindLimb2Left")),
    ("Pierna der.", ("mHipRight", "mKneeRight", "R_UPPER_LEG", "R_LOWER_LEG", "mHindLimb1Right", "mHindLimb2Right")),
    ("Pies", ("mAnkle", "mFoot", "mToe", "L_FOOT", "R_FOOT", "mHindLimb3", "mHindLimb4")),
]


def zone_of(bone_name):
    # Las piernas y los pies se comprueban antes que "Left/Right" (brazos).
    for idx in (7, 5, 6, 0, 1, 2, 3, 4):
        name, keys = ALPHA_ZONES[idx]
        if any(k in bone_name for k in keys):
            return idx
    return 2


def _meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


class SLR_OT_fit_clothing(bpy.types.Operator):
    """Empuja hacia fuera las partes de la ropa que atraviesan el cuerpo (no destructivo)"""
    bl_idname = "slr.fit_clothing"
    bl_label = "Ajustar sin atravesar"
    bl_options = {"REGISTER", "UNDO"}

    offset: bpy.props.FloatProperty(name="Separación", default=0.002, min=0.0, max=0.05, unit="LENGTH",
                                    description="Distancia mínima entre ropa y cuerpo")
    apply: bpy.props.BoolProperty(name="Aplicar ya", default=False)

    @classmethod
    def poll(cls, context):
        body = context.active_object
        if body is None or body.type != "MESH" or len(_meshes(context)) < 2:
            cls.poll_message_set("Selecciona la ropa y, por último, el cuerpo (activo)")
            return False
        return True

    def execute(self, context):
        body = context.active_object
        clothes = [o for o in _meshes(context) if o != body]
        arm = find_armature(body)
        old_pose = arm.data.pose_position if arm is not None else None
        if arm is not None:
            arm.data.pose_position = "REST"
        try:
            for c in clothes:
                mod = c.modifiers.get("SL_SinAtravesar") or c.modifiers.new("SL_SinAtravesar", "SHRINKWRAP")
                mod.target = body
                mod.wrap_method = "NEAREST_SURFACEPOINT"
                mod.wrap_mode = "OUTSIDE"
                mod.offset = self.offset
                compat.move_modifier_first(context, c, mod.name)
                if self.apply:
                    with context.temp_override(object=c, active_object=c):
                        bpy.ops.object.modifier_apply(modifier=mod.name)
        finally:
            if arm is not None:
                arm.data.pose_position = old_pose
        self.report({"INFO"}, f"{len(clothes)} prenda(s) ajustadas" + ("" if self.apply else
                    " (modificador SL_SinAtravesar; ajusta la separación cuando quieras)"))
        return {"FINISHED"}


class SLR_OT_make_sizes(bpy.types.Operator):
    """Genera tallas XXS–XXL de la prenda (copias con más o menos holgura)"""
    bl_idname = "slr.make_sizes"
    bl_label = "Generar tallas"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        if not _meshes(context):
            cls.poll_message_set("Selecciona la prenda")
            return False
        return True

    def execute(self, context):
        total = 0
        for obj in _meshes(context):
            cname = f"SL_Tallas_{obj.name}"
            coll = bpy.data.collections.get(cname) or bpy.data.collections.new(cname)
            if coll.name not in context.scene.collection.children:
                context.scene.collection.children.link(coll)
            for o in list(coll.objects):
                bpy.data.objects.remove(o)
            for label, push in SIZES:
                copy = obj.copy()
                copy.data = obj.data.copy()
                copy.name = f"{obj.name}_{label}"
                coll.objects.link(copy)
                if push:
                    disp = copy.modifiers.new("SL_Talla", "DISPLACE")
                    disp.strength = push
                    disp.mid_level = 0.0
                    disp.direction = "NORMAL"
                    compat.move_modifier_first(context, copy, disp.name)
                copy["sl_size"] = label
                copy.hide_set(label != "S")
                total += 1
        self.report({"INFO"}, f"{total} tallas creadas en colecciones SL_Tallas_*")
        return {"FINISHED"}


class SLR_OT_alpha_zones(bpy.types.Operator):
    """Divide la malla en 8 caras (materiales) por zonas del cuerpo, para ocultarlas con un HUD de alfas"""
    bl_idname = "slr.alpha_zones"
    bl_label = "Zonas de alfa"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH" or find_armature(obj) is None:
            cls.poll_message_set("Selecciona una malla rigged (con pesos)")
            return False
        return True

    def execute(self, context):
        obj = context.active_object
        me = obj.data
        names = {vg.index: vg.name for vg in obj.vertex_groups}
        vzone = []
        for v in me.vertices:
            best = max(((g.weight, names.get(g.group, "")) for g in v.groups
                        if names.get(g.group, "") in SL_INFO), default=(0.0, "mTorso"))
            vzone.append(zone_of(best[1]))
        mats = []
        for label, _ in ALPHA_ZONES:
            mname = f"SL_Alfa_{label}"
            mat = bpy.data.materials.get(mname) or bpy.data.materials.new(mname)
            mats.append(mat)
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
        used = set()
        for p in me.polygons:
            counts = {}
            for vi in p.vertices:
                counts[vzone[vi]] = counts.get(vzone[vi], 0) + 1
            z = max(counts, key=counts.get)
            p.material_index = z
            used.add(z)
        self.report({"INFO"}, f"{len(used)} zonas de alfa (caras SL): "
                    + ", ".join(ALPHA_ZONES[i][0] for i in sorted(used)))
        return {"FINISHED"}


classes = (SLR_OT_fit_clothing, SLR_OT_make_sizes, SLR_OT_alpha_zones)

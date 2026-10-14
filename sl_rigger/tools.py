"""Herramientas avanzadas: asistente de auto-rig, transferencia y simetría de pesos, rig rígido."""

import bpy
from bpy.props import BoolProperty, EnumProperty
from mathutils import Vector

from . import presets, skeleton, weights


def _meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


def _object_mode(context):
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")


def _select_only(context, objs, active):
    for o in context.view_layer.objects:
        o.select_set(False)
    for o in objs:
        o.select_set(True)
    context.view_layer.objects.active = active


class SLR_OT_wizard(bpy.types.Operator):
    """Un clic: crea el esqueleto con el preset elegido, lo ajusta a la malla, vincula con pesos automáticos, limpia y valida"""
    bl_idname = "slr.wizard"
    bl_label = "Auto-rig en un clic"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        meshes = _meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona la malla (o mallas) del avatar o la prenda")
            return {"CANCELLED"}
        _object_mode(context)
        preset = context.scene.slr_preset
        bpy.ops.slr.create_rig("EXEC_DEFAULT", preset=preset,
                               **{f"deform_{k.lower()}": True for k in presets.default_deform(preset)})
        arm = context.active_object
        _select_only(context, meshes + [arm], arm)
        bpy.ops.slr.fit_rig()
        _select_only(context, [arm], arm)
        bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
        _select_only(context, meshes + [arm], arm)
        result = bpy.ops.slr.bind(mode="AUTO")
        if "FINISHED" not in result:
            self.report({"ERROR"}, "No se pudieron calcular los pesos automáticos (revisa que la malla sea cerrada)")
            return {"CANCELLED"}
        _select_only(context, meshes, meshes[0])
        bpy.ops.slr.validate()
        self.report({"INFO"}, f"Auto-rig listo: '{arm.name}' + {len(meshes)} malla(s). Revisa el informe")
        return {"FINISHED"}


class SLR_OT_transfer_weights(bpy.types.Operator):
    """Copia los pesos del cuerpo (activo) a la ropa seleccionada y la vincula a su esqueleto"""
    bl_idname = "slr.transfer_weights"
    bl_label = "Transferir pesos del cuerpo"
    bl_options = {"REGISTER", "UNDO"}

    method: EnumProperty(
        name="Método",
        items=[
            ("POLYINTERP_NEAREST", "Superficie interpolada", "El más suave; recomendado para ropa"),
            ("NEAREST", "Vértice más cercano", "Rápido; bueno si la ropa sigue la topología del cuerpo"),
        ],
        default="POLYINTERP_NEAREST",
    )

    def execute(self, context):
        body = context.active_object
        targets = [o for o in _meshes(context) if o != body]
        if body is None or body.type != "MESH" or not targets:
            self.report({"ERROR"}, "Selecciona la ropa y, por último, el cuerpo con pesos (activo)")
            return {"CANCELLED"}
        arm = skeleton.find_armature(body)
        if not skeleton.is_sl_armature(arm):
            self.report({"ERROR"}, "El cuerpo activo no está vinculado a un esqueleto SL")
            return {"CANCELLED"}
        _object_mode(context)
        old_pose = arm.data.pose_position
        arm.data.pose_position = "REST"  # transferir siempre en pose de reposo
        try:
            self._transfer(context, body, arm, targets)
        finally:
            arm.data.pose_position = old_pose
        _select_only(context, targets, targets[0])
        self.report({"INFO"}, f"Pesos transferidos a {len(targets)} prenda(s) y vinculadas a '{arm.name}'")
        return {"FINISHED"}

    def _transfer(self, context, body, arm, targets):
        for t in targets:
            for vg in list(t.vertex_groups):
                t.vertex_groups.remove(vg)
            mod = t.modifiers.new("SL_WeightTransfer", "DATA_TRANSFER")
            mod.object = body
            mod.use_vert_data = True
            mod.data_types_verts = {"VGROUP_WEIGHTS"}
            mod.vert_mapping = self.method
            mod.layers_vgroup_select_src = "ALL"
            mod.layers_vgroup_select_dst = "NAME"
            _select_only(context, [t], t)
            bpy.ops.object.datalayout_transfer(modifier=mod.name)
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=0)
            bpy.ops.object.modifier_apply(modifier=mod.name)
            weights.clean_weights(t)
            mw = t.matrix_world.copy()
            t.parent = arm
            t.matrix_world = mw
            if not any(m.type == "ARMATURE" for m in t.modifiers):
                t.modifiers.new("SL_Armature", "ARMATURE").object = arm


class SLR_OT_mirror_weights(bpy.types.Operator):
    """Copia los pesos de un lado al otro (Left ↔ Right) en las mallas seleccionadas"""
    bl_idname = "slr.mirror_weights"
    bl_label = "Simetrizar pesos"
    bl_options = {"REGISTER", "UNDO"}

    use_topology: BoolProperty(name="Por topología", default=False,
                               description="Para mallas simétricas en topología pero no en posición")

    def execute(self, context):
        meshes = _meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona al menos una malla")
            return {"CANCELLED"}
        _object_mode(context)
        for obj in meshes:
            _select_only(context, [obj], obj)
            bpy.ops.object.vertex_group_mirror(mirror_weights=True, flip_group_names=True,
                                               all_groups=True, use_topology=self.use_topology)
            weights.clean_weights(obj)
        _select_only(context, meshes, meshes[0])
        self.report({"INFO"}, "Pesos simetrizados")
        return {"FINISHED"}


class SLR_OT_rigid_bind(bpy.types.Operator):
    """Robots, mechas y armaduras: cada pieza seleccionada sigue al 100 % al hueso más cercano"""
    bl_idname = "slr.rigid_bind"
    bl_label = "Rig rígido (robots)"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        arm = context.active_object
        meshes = _meshes(context)
        if not skeleton.is_sl_armature(arm) or not meshes:
            self.report({"ERROR"}, "Selecciona las piezas y, por último, el esqueleto SL (activo)")
            return {"CANCELLED"}
        _object_mode(context)
        deform = [b for b in arm.data.bones if b.use_deform and b.name in skeleton.ALL_SL_BONE_NAMES]
        mw = arm.matrix_world
        for obj in meshes:
            center = obj.matrix_world @ (sum((Vector(c) for c in obj.bound_box), Vector()) / 8.0)

            def dist(b):
                a, t = mw @ b.head_local, mw @ b.tail_local
                ab = t - a
                f = max(0.0, min(1.0, (center - a).dot(ab) / max(ab.length_squared, 1e-12)))
                return (a + ab * f - center).length

            bone = min(deform, key=dist)
            for vg in list(obj.vertex_groups):
                obj.vertex_groups.remove(vg)
            obj.vertex_groups.new(name=bone.name).add(range(len(obj.data.vertices)), 1.0, "REPLACE")
            m = obj.matrix_world.copy()
            obj.parent = arm
            obj.matrix_world = m
            if not any(md.type == "ARMATURE" for md in obj.modifiers):
                obj.modifiers.new("SL_Armature", "ARMATURE").object = arm
        self.report({"INFO"}, f"{len(meshes)} pieza(s) unidas rígidamente")
        return {"FINISHED"}


classes = (SLR_OT_wizard, SLR_OT_transfer_weights, SLR_OT_mirror_weights, SLR_OT_rigid_bind)

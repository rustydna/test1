"""Herramientas de malla: optimizar, UV automático, exportación por lotes y fusión de grupos."""

import os

import bmesh
import bpy

from .skeleton import SL_BONE_ORDER


def _meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


class _MeshOp:
    @classmethod
    def poll(cls, context):
        if not any(o.type == "MESH" for o in context.selected_objects):
            cls.poll_message_set("Selecciona al menos una malla")
            return False
        return True


def optimize_mesh(me, merge_dist=0.0001):
    bm = bmesh.new()
    bm.from_mesh(me)
    v0, f0 = len(bm.verts), len(bm.faces)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=merge_dist)
    bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=merge_dist)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context="VERTS")
    loose_e = [e for e in bm.edges if not e.link_faces]
    bmesh.ops.delete(bm, geom=loose_e, context="EDGES")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    v1, f1 = len(bm.verts), len(bm.faces)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return v0 - v1, f0 - f1


class SLR_OT_optimize(_MeshOp, bpy.types.Operator):
    """Une vértices duplicados, borra geometría suelta y degenerada y corrige normales"""
    bl_idname = "slr.optimize"
    bl_label = "Optimizar para SL"
    bl_options = {"REGISTER", "UNDO"}

    merge_dist: bpy.props.FloatProperty(name="Distancia de unión", default=0.0001, min=0.0, max=0.01,
                                        unit="LENGTH", precision=5)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        tv = tf = 0
        for obj in _meshes(context):
            if obj.data.users > 1:
                obj.data = obj.data.copy()
            dv, df = optimize_mesh(obj.data, self.merge_dist)
            tv += dv
            tf += df
        self.report({"INFO"}, f"Optimizado: −{tv} vértices, −{tf} caras")
        return {"FINISHED"}


class SLR_OT_auto_uv(_MeshOp, bpy.types.Operator):
    """Crea un mapa UV automático (Smart UV) en las mallas que no tienen"""
    bl_idname = "slr.auto_uv"
    bl_label = "UV automático"
    bl_options = {"REGISTER", "UNDO"}

    only_missing: bpy.props.BoolProperty(name="Solo si falta", default=True)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        done = 0
        for obj in _meshes(context):
            if self.only_missing and obj.data.uv_layers:
                continue
            if not obj.data.uv_layers:
                obj.data.uv_layers.new(name="UVMap")
            for o in context.view_layer.objects:
                o.select_set(o == obj)
            context.view_layer.objects.active = obj
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.uv.smart_project(island_margin=0.02)
            bpy.ops.object.mode_set(mode="OBJECT")
            done += 1
        self.report({"INFO"}, f"UV creado en {done} malla(s)")
        return {"FINISHED"}


class SLR_OT_batch_export(_MeshOp, bpy.types.Operator):
    """Exporta cada malla seleccionada a su propio archivo (con sus LODs y física)"""
    bl_idname = "slr.batch_export"
    bl_label = "Exportar por lotes"

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})
    file_format: bpy.props.EnumProperty(name="Formato", items=[("DAE", "Collada (.dae)", ""),
                                                              ("GLB", "glTF binario (.glb)", "")])

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        objs = [o for o in _meshes(context) if "sl_lod_of" not in o]
        if not os.path.isdir(self.directory):
            self.report({"ERROR"}, "Elige una carpeta")
            return {"CANCELLED"}
        done = []
        wm = context.window_manager
        wm.progress_begin(0, len(objs))
        try:
            for i, obj in enumerate(objs):
                for o in context.view_layer.objects:
                    o.select_set(o == obj)
                context.view_layer.objects.active = obj
                safe = bpy.path.clean_name(obj.name)
                if self.file_format == "DAE":
                    path = os.path.join(self.directory, safe + ".dae")
                    bpy.ops.slr.export_dae(filepath=path)
                else:
                    path = os.path.join(self.directory, safe + ".glb")
                    bpy.ops.slr.export_gltf(filepath=path, kind="AUTO")
                done.append(os.path.basename(path))
                wm.progress_update(i)
        finally:
            wm.progress_end()
            for o in objs:
                o.select_set(True)
        self.report({"INFO"}, f"{len(done)} archivos: " + ", ".join(done))
        return {"FINISHED"}


_SL_BONE_ITEMS = [(n, n, "") for n in SL_BONE_ORDER]


def _sl_bone_items(self, context):
    return _SL_BONE_ITEMS


class SLR_OT_merge_group(bpy.types.Operator):
    """Suma los pesos del grupo de vértices activo a un hueso SL y borra el grupo original"""
    bl_idname = "slr.merge_group"
    bl_label = "Fusionar grupo en hueso SL"
    bl_options = {"REGISTER", "UNDO"}
    bl_property = "target"

    target: bpy.props.EnumProperty(name="Hueso SL", items=_sl_bone_items)

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH" or obj.vertex_groups.active is None:
            cls.poll_message_set("Selecciona una malla con un grupo de vértices activo")
            return False
        return True

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        obj = context.active_object
        src = obj.vertex_groups.active
        if src.name == self.target:
            return {"CANCELLED"}
        dst = obj.vertex_groups.get(self.target) or obj.vertex_groups.new(name=self.target)
        n = 0
        for v in obj.data.vertices:
            for g in v.groups:
                if g.group == src.index and g.weight > 0.0:
                    dst.add([v.index], g.weight, "ADD")
                    n += 1
        name = src.name
        obj.vertex_groups.remove(src)
        self.report({"INFO"}, f"'{name}' fusionado en {self.target} ({n} vértices)")
        return {"FINISHED"}


classes = (SLR_OT_optimize, SLR_OT_auto_uv, SLR_OT_batch_export, SLR_OT_merge_group)

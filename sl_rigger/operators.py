import os

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty
from bpy_extras.io_utils import ExportHelper
from mathutils import Vector

from . import collada, gltf, mappings, skeleton, weights


def _selected_meshes(context):
    return [o for o in context.selected_objects if o.type == "MESH"]


def _sl_rig_in_selection(context):
    for o in context.selected_objects:
        if skeleton.is_sl_armature(o):
            return o
    act = context.active_object
    return act if skeleton.is_sl_armature(act) else None


def _world_bbox(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return lo, hi


# --------------------------------------------------------------------------- esqueleto

class SLR_OT_create_rig(bpy.types.Operator):
    """Crea un esqueleto con los huesos y posiciones de Second Life"""
    bl_idname = "slr.create_rig"
    bl_label = "Crear esqueleto SL"
    bl_options = {"REGISTER", "UNDO"}

    bento_hands: BoolProperty(name="Dedos Bento", default=True)

    def execute(self, context):
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        arm = skeleton.create_sl_armature(context, include_bento_hands=self.bento_hands)
        self.report({"INFO"}, f"Creado '{arm.name}' con {len(arm.data.bones)} huesos")
        return {"FINISHED"}


class SLR_OT_fit_rig(bpy.types.Operator):
    """Escala y centra el esqueleto SL para que encaje con la altura de las mallas seleccionadas"""
    bl_idname = "slr.fit_rig"
    bl_label = "Ajustar esqueleto a la malla"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        arm = _sl_rig_in_selection(context)
        meshes = _selected_meshes(context)
        if arm is None or not meshes:
            self.report({"ERROR"}, "Selecciona las mallas y el esqueleto SL (activo)")
            return {"CANCELLED"}
        lo, hi = _world_bbox(meshes)
        height = hi.z - lo.z
        if height <= 1e-4:
            self.report({"ERROR"}, "La malla no tiene altura")
            return {"CANCELLED"}
        # Altura de referencia del esqueleto SL: de los pies a la parte superior del cráneo (+ cráneo).
        bones = arm.data.bones
        rig_bottom = min(b.head_local.z for b in bones)
        rig_top = bones["mSkull"].head_local.z + 0.10 if "mSkull" in bones else max(b.tail_local.z for b in bones)
        factor = height / (rig_top - rig_bottom)
        arm.scale = (factor, factor, factor)
        center = (lo + hi) / 2
        arm.location = Vector((center.x, center.y, lo.z - rig_bottom * factor))
        context.view_layer.update()
        self.report({"INFO"}, f"Esqueleto escalado ×{factor:.3f}. Aplica la escala (Ctrl+A) antes de vincular; "
                              "sube el modelo con 'Incluir posiciones de articulaciones'")
        return {"FINISHED"}


# --------------------------------------------------------------------------- malla → avatar

class SLR_OT_convert_groups(bpy.types.Operator):
    """Renombra/fusiona grupos de vértices de Mixamo, Unreal o Rigify a huesos de Second Life"""
    bl_idname = "slr.convert_groups"
    bl_label = "Convertir grupos a nombres SL"
    bl_options = {"REGISTER", "UNDO"}

    preset: EnumProperty(
        name="Origen",
        items=[("AUTO", "Detectar", "Detectar automáticamente")]
        + [(k, v[0], "") for k, v in mappings.PRESETS.items()],
        default="AUTO",
    )

    def execute(self, context):
        meshes = _selected_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona al menos una malla")
            return {"CANCELLED"}
        msgs = []
        for obj in meshes:
            used, n = weights.convert_vertex_groups(obj, self.preset)
            label = mappings.PRESETS[used][0] if used else "desconocido"
            msgs.append(f"{obj.name}: {n} grupos ({label})")
        self.report({"INFO"}, "; ".join(msgs))
        return {"FINISHED"}


class SLR_OT_bind(bpy.types.Operator):
    """Vincula las mallas seleccionadas al esqueleto SL activo"""
    bl_idname = "slr.bind"
    bl_label = "Vincular al esqueleto"
    bl_options = {"REGISTER", "UNDO"}

    mode: EnumProperty(
        name="Pesos",
        items=[
            ("AUTO", "Automáticos", "Calcula pesos por proximidad a los huesos"),
            ("KEEP", "Conservar grupos", "Usa los grupos de vértices existentes (p. ej. tras convertir Mixamo)"),
            ("EMPTY", "Grupos vacíos", "Crea un grupo vacío por hueso para pintar a mano"),
        ],
        default="AUTO",
    )

    def execute(self, context):
        arm = _sl_rig_in_selection(context)
        meshes = _selected_meshes(context)
        if arm is None or not meshes:
            self.report({"ERROR"}, "Selecciona las mallas y luego el esqueleto SL (activo)")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        if self.mode == "KEEP":
            for obj in meshes:
                mw = obj.matrix_world.copy()
                obj.parent = arm
                obj.matrix_world = mw
                mod = next((m for m in obj.modifiers if m.type == "ARMATURE"), None)
                if mod is None:
                    mod = obj.modifiers.new("SL_Armature", "ARMATURE")
                mod.object = arm
        else:
            for o in context.selected_objects:
                o.select_set(o in meshes or o == arm)
            context.view_layer.objects.active = arm
            for obj in meshes:
                for mod in [m for m in obj.modifiers if m.type == "ARMATURE"]:
                    obj.modifiers.remove(mod)
            kind = "ARMATURE_AUTO" if self.mode == "AUTO" else "ARMATURE_NAME"
            bpy.ops.object.parent_set(type=kind)
            if self.mode == "AUTO":
                for obj in meshes:
                    weights.clean_weights(obj)
        self.report({"INFO"}, f"{len(meshes)} malla(s) vinculada(s) a '{arm.name}'")
        return {"FINISHED"}


class SLR_OT_clean_weights(bpy.types.Operator):
    """Máx. 4 huesos por vértice, elimina pesos ínfimos y normaliza"""
    bl_idname = "slr.clean_weights"
    bl_label = "Limpiar pesos para SL"
    bl_options = {"REGISTER", "UNDO"}

    threshold: FloatProperty(name="Umbral", default=0.01, min=0.0, max=0.5)
    remove_non_sl: BoolProperty(name="Borrar grupos no SL", default=False)

    def execute(self, context):
        meshes = _selected_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona al menos una malla")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        total = 0
        for obj in meshes:
            total += weights.clean_weights(obj, threshold=self.threshold, remove_non_sl=self.remove_non_sl)
        level = {"WARNING"} if total else {"INFO"}
        self.report(level, f"Pesos limpios. Vértices sin peso: {total}")
        return {"FINISHED"}


# --------------------------------------------------------------------------- objetos estáticos

class SLR_OT_prepare_static(bpy.types.Operator):
    """Aplica rotación y escala y centra el origen (recomendado para objetos de SL)"""
    bl_idname = "slr.prepare_static"
    bl_label = "Preparar objeto"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        meshes = _selected_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona al menos una malla")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in context.selected_objects:
            o.select_set(o in meshes)
        context.view_layer.objects.active = meshes[0]
        bpy.ops.object.transform_apply(location=False, rotation=True, scale=True)
        bpy.ops.object.origin_set(type="ORIGIN_GEOMETRY", center="BOUNDS")
        self.report({"INFO"}, f"{len(meshes)} objeto(s) preparados")
        return {"FINISHED"}


LOD_LEVELS = (("MED", "Medio"), ("LOW", "Bajo"), ("LOWEST", "Mínimo"))


class SLR_OT_make_lods(bpy.types.Operator):
    """Crea copias simplificadas (LOD) para reducir el coste de terreno (Land Impact)"""
    bl_idname = "slr.make_lods"
    bl_label = "Generar LODs"
    bl_options = {"REGISTER", "UNDO"}

    med: FloatProperty(name="Medio", default=0.5, min=0.01, max=1.0)
    low: FloatProperty(name="Bajo", default=0.25, min=0.01, max=1.0)
    lowest: FloatProperty(name="Mínimo", default=0.1, min=0.01, max=1.0)

    def execute(self, context):
        meshes = [o for o in _selected_meshes(context) if "sl_lod_of" not in o]
        if not meshes:
            self.report({"ERROR"}, "Selecciona las mallas originales")
            return {"CANCELLED"}
        ratios = {"MED": self.med, "LOW": self.low, "LOWEST": self.lowest}
        for obj in meshes:
            coll = bpy.data.collections.get(f"SL_LOD_{obj.name}") or bpy.data.collections.new(f"SL_LOD_{obj.name}")
            if coll.name not in context.scene.collection.children:
                context.scene.collection.children.link(coll)
            for o in list(coll.objects):
                if o.get("sl_lod_of") == obj.name and o.get("sl_lod_level") in ratios:
                    bpy.data.objects.remove(o)
            for level, ratio in ratios.items():
                copy = obj.copy()
                copy.data = obj.data.copy()
                copy.name = f"{obj.name}_{level}"
                copy["sl_lod_of"] = obj.name
                copy["sl_lod_level"] = level
                dec = copy.modifiers.new("SL_Decimate", "DECIMATE")
                dec.ratio = ratio
                # El decimado debe ir antes del armature.
                copy.modifiers.move(copy.modifiers.find(dec.name), 0)
                coll.objects.link(copy)
                copy.hide_set(True)
        self.report({"INFO"}, "LODs creados (ocultos) en colecciones SL_LOD_*")
        return {"FINISHED"}


class SLR_OT_make_physics(bpy.types.Operator):
    """Crea una malla de física simple (envolvente convexa) para objetos estáticos"""
    bl_idname = "slr.make_physics"
    bl_label = "Generar física"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        meshes = [o for o in _selected_meshes(context) if "sl_lod_of" not in o]
        if not meshes:
            self.report({"ERROR"}, "Selecciona las mallas originales")
            return {"CANCELLED"}
        depsgraph = context.evaluated_depsgraph_get()
        for obj in meshes:
            ev = obj.evaluated_get(depsgraph)
            bm = bmesh.new()
            bm.from_mesh(ev.to_mesh())
            ev.to_mesh_clear()
            res = bmesh.ops.convex_hull(bm, input=bm.verts)
            bmesh.ops.delete(bm, geom=[g for g in res["geom_interior"] + res["geom_unused"]
                                       if isinstance(g, bmesh.types.BMVert)], context="VERTS")
            name = f"{obj.name}_PHYS"
            old = bpy.data.objects.get(name)
            if old is not None:
                bpy.data.objects.remove(old)
            me = bpy.data.meshes.new(name)
            bm.to_mesh(me)
            bm.free()
            phys = bpy.data.objects.new(name, me)
            phys.matrix_world = obj.matrix_world.copy()
            phys["sl_lod_of"] = obj.name
            phys["sl_lod_level"] = "PHYS"
            phys.display_type = "WIRE"
            coll = bpy.data.collections.get(f"SL_LOD_{obj.name}") or bpy.data.collections.new(f"SL_LOD_{obj.name}")
            if coll.name not in context.scene.collection.children:
                context.scene.collection.children.link(coll)
            coll.objects.link(phys)
        self.report({"INFO"}, "Mallas de física creadas (*_PHYS)")
        return {"FINISHED"}


# --------------------------------------------------------------------------- validación / exportación

class SLR_OT_validate(bpy.types.Operator):
    """Comprueba que las mallas seleccionadas cumplen los límites de Second Life"""
    bl_idname = "slr.validate"
    bl_label = "Validar para SL"

    def execute(self, context):
        meshes = _selected_meshes(context)
        if not meshes:
            self.report({"ERROR"}, "Selecciona al menos una malla")
            return {"CANCELLED"}
        results = []
        seen = set()
        for obj in meshes:
            results += weights.validate_object(obj)
            for slot in obj.material_slots:
                if slot.material is not None and slot.material.name not in seen:
                    seen.add(slot.material.name)
                    results += gltf.validate_material_textures(slot.material)
        context.scene.slr_report = "\n".join(f"{lvl}|{msg}" for lvl, msg in results)
        errors = sum(1 for lvl, _ in results if lvl == "ERROR")
        warns = sum(1 for lvl, _ in results if lvl == "WARNING")
        for lvl, msg in results:
            print(f"[SL Rigger] {lvl}: {msg}")
        self.report({"ERROR"} if errors else {"WARNING"} if warns else {"INFO"},
                    f"Validación: {errors} errores, {warns} avisos (detalles en el panel)")
        return {"FINISHED"}


_KIND_ITEMS = [
    ("AUTO", "Automático", "Rigged si las mallas usan un esqueleto SL"),
    ("RIGGED", "Avatar / ropa rigged", ""),
    ("STATIC", "Objeto estático", ""),
]


def _export_with_lods(op, context, filepath, writer):
    """Exporta las mallas seleccionadas y, si se pide, sus LODs y física a archivos hermanos."""
    meshes = [o for o in _selected_meshes(context) if "sl_lod_of" not in o]
    if not meshes:
        op.report({"ERROR"}, "Selecciona al menos una malla")
        return {"CANCELLED"}
    if context.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")
    rigged = {"AUTO": None, "RIGGED": True, "STATIC": False}[op.kind]
    written, warnings_all = [], []
    try:
        warnings_all += writer(filepath, meshes, rigged)
        written.append(filepath)
        if op.include_lods:
            base, ext = os.path.splitext(filepath)
            names = {o.name for o in meshes}
            for level in [lv for lv, _ in LOD_LEVELS] + ["PHYS"]:
                objs = [o for o in context.scene.objects
                        if o.get("sl_lod_of") in names and o.get("sl_lod_level") == level]
                if not objs:
                    continue
                path = f"{base}_{level}{ext}"
                warnings_all += writer(path, objs, False if level == "PHYS" else rigged)
                written.append(path)
    except ValueError as e:
        op.report({"ERROR"}, str(e))
        return {"CANCELLED"}
    for msg in dict.fromkeys(warnings_all):
        op.report({"WARNING"}, msg)
    op.report({"INFO"}, "Exportado: " + ", ".join(os.path.basename(p) for p in written))
    return {"FINISHED"}


class SLR_OT_export(bpy.types.Operator, ExportHelper):
    """Exporta las mallas seleccionadas a Collada (.dae) para el subidor de Second Life"""
    bl_idname = "slr.export_dae"
    bl_label = "Exportar .dae para SL"
    filename_ext = ".dae"
    filter_glob: StringProperty(default="*.dae", options={"HIDDEN"})

    kind: EnumProperty(name="Tipo", items=_KIND_ITEMS, default="AUTO")
    apply_modifiers: BoolProperty(name="Aplicar modificadores", default=True)
    include_lods: BoolProperty(name="Exportar LODs y física", default=True,
                               description="Crea archivos _MED, _LOW, _LOWEST y _PHYS si existen")

    def execute(self, context):
        depsgraph = context.evaluated_depsgraph_get()

        def writer(path, objs, rigged):
            return collada.export(path, objs, depsgraph, self.apply_modifiers, rigged)

        return _export_with_lods(self, context, self.filepath, writer)


class SLR_OT_export_gltf(bpy.types.Operator, ExportHelper):
    """Exporta las mallas seleccionadas a glTF (.glb/.gltf) para el subidor de Second Life"""
    bl_idname = "slr.export_gltf"
    bl_label = "Exportar glTF para SL"
    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb;*.gltf", options={"HIDDEN"})

    export_format: EnumProperty(
        name="Formato",
        items=[
            ("GLB", "glTF binario (.glb)", "Un solo archivo con texturas incluidas"),
            ("GLTF_SEPARATE", "glTF separado (.gltf + .bin + texturas)", ""),
        ],
        default="GLB",
    )
    kind: EnumProperty(name="Tipo", items=_KIND_ITEMS, default="STATIC")
    apply_modifiers: BoolProperty(name="Aplicar modificadores", default=True)
    include_lods: BoolProperty(name="Exportar LODs y física", default=True,
                               description="Crea archivos _MED, _LOW, _LOWEST y _PHYS si existen")

    def _ext(self):
        return ".glb" if self.export_format == "GLB" else ".gltf"

    def check(self, context):
        old = self.filepath
        base, ext = os.path.splitext(old)
        if ext.lower() in (".glb", ".gltf"):
            old_base = base
        else:
            old_base = old
        self.filepath = old_base + self._ext()
        return self.filepath != old

    def execute(self, context):
        self.check(context)

        def writer(path, objs, rigged):
            return gltf.export_model(context, path, objs, self.export_format, self.apply_modifiers, rigged)

        return _export_with_lods(self, context, self.filepath, writer)


class SLR_OT_export_materials(bpy.types.Operator):
    """Exporta los materiales PBR de las mallas seleccionadas, un .glb por material (Build → Upload → Material)"""
    bl_idname = "slr.export_materials"
    bl_label = "Exportar materiales PBR"

    directory: StringProperty(subtype="DIR_PATH")
    filter_folder: BoolProperty(default=True, options={"HIDDEN"})

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        mats = []
        for obj in _selected_meshes(context):
            for slot in obj.material_slots:
                if slot.material is not None and slot.material not in mats:
                    mats.append(slot.material)
        if not mats:
            self.report({"ERROR"}, "Las mallas seleccionadas no tienen materiales")
            return {"CANCELLED"}
        if not self.directory or not os.path.isdir(self.directory):
            self.report({"ERROR"}, "Elige una carpeta de destino")
            return {"CANCELLED"}
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        try:
            written = gltf.export_materials(context, self.directory, mats)
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        self.report({"INFO"}, "Materiales: " + ", ".join(os.path.basename(p) for p in written))
        return {"FINISHED"}


classes = (
    SLR_OT_create_rig,
    SLR_OT_fit_rig,
    SLR_OT_convert_groups,
    SLR_OT_bind,
    SLR_OT_clean_weights,
    SLR_OT_prepare_static,
    SLR_OT_make_lods,
    SLR_OT_make_physics,
    SLR_OT_validate,
    SLR_OT_export,
    SLR_OT_export_gltf,
    SLR_OT_export_materials,
)

"""Exportación glTF 2.0 (.glb / .gltf) adaptada al subidor de Second Life.

Usa el exportador glTF que trae Blender, con los ajustes que pide SL:
  * Malla: Build → Upload → Model (.gltf/.glb). Mismos límites que Collada.
    SL de momento solo toma el color base del modelo.
  * Materiales PBR: Build → Upload → Material, con un .glb por material.
    Color base, normal, metal/rugosidad (empaquetados en un PNG) y emisivo.
"""

import os
import re

import addon_utils
import bpy

from .skeleton import find_armature
from .weights import SL_MAX_INFLUENCES


def _ensure_gltf_addon():
    if not hasattr(bpy.ops.export_scene, "gltf"):
        addon_utils.enable("io_scene_gltf2", default_set=True)
    if not hasattr(bpy.ops.export_scene, "gltf"):
        raise ValueError("El exportador glTF de Blender (io_scene_gltf2) no está disponible")


def _call_exporter(filepath, export_format, **opts):
    """Llama al exportador filtrando opciones que no existan en esta versión de Blender."""
    _ensure_gltf_addon()
    valid = set(bpy.ops.export_scene.gltf.get_rna_type().properties.keys())
    kwargs = {k: v for k, v in opts.items() if k in valid}
    result = bpy.ops.export_scene.gltf(filepath=filepath, export_format=export_format, **kwargs)
    if "FINISHED" not in result:
        raise ValueError(f"El exportador glTF falló al escribir {os.path.basename(filepath)}")


class _Selection:
    """Selecciona solo `objs` mientras dura el bloque y restaura la selección después."""

    def __init__(self, context, objs):
        self.context = context
        self.objs = objs

    def __enter__(self):
        vl = self.context.view_layer
        self.prev_sel = [o for o in vl.objects if o.select_get()]
        self.prev_active = vl.objects.active
        self.prev_hidden = []
        for o in vl.objects:
            o.select_set(False)
        for o in self.objs:
            if o.hide_get():
                self.prev_hidden.append(o)
                o.hide_set(False)
            o.select_set(True)
        vl.objects.active = self.objs[0]

    def __exit__(self, *exc):
        vl = self.context.view_layer
        for o in vl.objects:
            o.select_set(False)
        for o in self.prev_hidden:
            o.hide_set(True)
        for o in self.prev_sel:
            if o.name in vl.objects:
                o.select_set(True)
        vl.objects.active = self.prev_active
        return False


def export_model(context, filepath, objects, export_format="GLB", apply_modifiers=True, rigged=None):
    """Exporta mallas (y su esqueleto SL si son rigged) a glTF. Devuelve lista de avisos."""
    warnings = []
    objects = [o for o in objects if o.type == "MESH"]
    if not objects:
        raise ValueError("No hay mallas para exportar")
    armatures = {find_armature(o) for o in objects}
    armature = next(iter(armatures)) if len(armatures) == 1 else None
    if armature is not None and "mPelvis" not in armature.data.bones:
        armature = None
    if rigged is None:
        rigged = armature is not None
    if rigged and armature is None:
        raise ValueError("Para exportar rigged todas las mallas deben usar el mismo armature de Second Life")
    if rigged:
        warnings.append("glTF rigged es experimental en SL; si el subidor falla usa .dae")

    to_select = objects + ([armature] if rigged else [])
    with _Selection(context, to_select):
        _call_exporter(
            filepath,
            export_format,
            use_selection=True,
            export_apply=apply_modifiers,
            export_yup=True,
            export_materials="EXPORT",
            export_image_format="AUTO",
            export_image_add_webp=False,
            export_draco_mesh_compression_enable=False,
            export_tangents=False,
            export_extras=False,
            export_animations=False,
            export_morph=False,
            export_skins=rigged,
            export_def_bones=True,
            export_leaf_bone=False,
            export_rest_position_armature=True,
            export_influence_nb=SL_MAX_INFLUENCES,
            export_all_influences=False,
        )
    return warnings


def _safe_filename(name):
    return re.sub(r'[\\/:*?"<>|]+', "_", name).strip() or "material"


def export_materials(context, directory, materials):
    """Escribe un .glb por material (para Build → Upload → Material). Devuelve rutas."""
    written = []
    mesh = bpy.data.meshes.new("SLR_material_carrier")
    mesh.from_pydata([(-0.5, -0.5, 0), (0.5, -0.5, 0), (0.5, 0.5, 0), (-0.5, 0.5, 0)], [], [(0, 1, 2, 3)])
    uv = mesh.uv_layers.new(name="UVMap")
    for i, co in enumerate(((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[i].uv = co
    carrier = bpy.data.objects.new("SLR_material_carrier", mesh)
    context.scene.collection.objects.link(carrier)
    try:
        for mat in materials:
            mesh.materials.clear()
            mesh.materials.append(mat)
            # El nombre del objeto/malla aparece en el subidor: usar el del material.
            carrier.name = mat.name
            path = os.path.join(directory, _safe_filename(mat.name) + ".glb")
            with _Selection(context, [carrier]):
                _call_exporter(
                    path,
                    "GLB",
                    use_selection=True,
                    export_apply=False,
                    export_yup=True,
                    export_materials="EXPORT",
                    export_image_format="AUTO",
                    export_image_add_webp=False,
            export_draco_mesh_compression_enable=False,
                    export_tangents=False,
                    export_animations=False,
                    export_skins=False,
                    export_morph=False,
                )
            written.append(path)
    finally:
        bpy.data.objects.remove(carrier)
        bpy.data.meshes.remove(mesh)
    return written


SL_MAX_TEXTURE = 2048


def validate_material_textures(mat):
    """Avisos sobre las texturas de un material (tamaño y potencia de dos)."""
    out = []
    if not mat.use_nodes or mat.node_tree is None:
        return out
    for node in mat.node_tree.nodes:
        if node.type != "TEX_IMAGE" or node.image is None:
            continue
        w, h = node.image.size
        name = node.image.name
        if w == 0 or h == 0:
            out.append(("WARNING", f"Material {mat.name}: la imagen '{name}' no se encuentra"))
            continue
        if w > SL_MAX_TEXTURE or h > SL_MAX_TEXTURE:
            out.append(("WARNING", f"Material {mat.name}: '{name}' es {w}×{h}; SL la reduce a {SL_MAX_TEXTURE} máx."))
        if w & (w - 1) or h & (h - 1):
            out.append(("INFO", f"Material {mat.name}: '{name}' ({w}×{h}) no es potencia de 2; SL la reescala"))
    return out

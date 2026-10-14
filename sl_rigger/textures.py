"""Texturas y materiales PBR para Second Life."""

import os
import re

import bpy

IMAGE_EXT = (".png", ".jpg", ".jpeg", ".tga", ".bmp", ".tif", ".tiff", ".webp")

# Palabras clave en el nombre del archivo → canal.
CHANNELS = [
    ("ORM", r"(^|[_\-. ])(orm|arm|occlusionroughnessmetal(lic)?)([_\-. ]|$)"),
    ("NORMAL", r"(normal|nrm|nor)([_\-. ]|gl|$)"),
    ("ROUGH", r"(rough|roughness|rgh)"),
    ("METAL", r"(metal|metallic|metalness|mtl)"),
    ("AO", r"(^|[_\-. ])(ao|occlusion|ambientocclusion)([_\-. ]|$)"),
    ("EMIT", r"(emissive|emission|emit|glow)"),
    ("BASE", r"(base|albedo|diffuse|diff|color|colour|basecolor|col)"),
]


def classify(filename):
    stem = os.path.splitext(os.path.basename(filename))[0].lower()
    for chan, pat in CHANNELS:
        if re.search(pat, stem):
            return chan
    return None


def _input(node, *names):
    for n in names:
        if n in node.inputs:
            return node.inputs[n]
    return None


def build_pbr_material(name, files):
    """files: {canal: ruta}. Crea un material Principled conectado."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = next(n for n in nt.nodes if n.type == "BSDF_PRINCIPLED")
    x = -700

    def tex(chan, non_color):
        nonlocal x
        img = bpy.data.images.load(files[chan], check_existing=True)
        if non_color:
            img.colorspace_settings.name = "Non-Color"
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.label = chan
        node.location = (x, 300 - 280 * len([n for n in nt.nodes if n.type == "TEX_IMAGE"]))
        return node

    links = nt.links
    if "BASE" in files:
        n = tex("BASE", False)
        links.new(n.outputs["Color"], _input(bsdf, "Base Color"))
        links.new(n.outputs["Alpha"], _input(bsdf, "Alpha"))
    if "ORM" in files:
        n = tex("ORM", True)
        sep = nt.nodes.new("ShaderNodeSeparateColor" if hasattr(bpy.types, "ShaderNodeSeparateColor")
                           else "ShaderNodeSeparateRGB")
        sep.location = (x + 300, n.location.y)
        links.new(n.outputs["Color"], sep.inputs[0])
        links.new(sep.outputs[1], _input(bsdf, "Roughness"))
        links.new(sep.outputs[2], _input(bsdf, "Metallic"))
    else:
        if "ROUGH" in files:
            n = tex("ROUGH", True)
            links.new(n.outputs["Color"], _input(bsdf, "Roughness"))
        if "METAL" in files:
            n = tex("METAL", True)
            links.new(n.outputs["Color"], _input(bsdf, "Metallic"))
    if "NORMAL" in files:
        n = tex("NORMAL", True)
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.location = (x + 300, n.location.y)
        links.new(n.outputs["Color"], nm.inputs["Color"])
        links.new(nm.outputs["Normal"], _input(bsdf, "Normal"))
    if "EMIT" in files:
        n = tex("EMIT", False)
        links.new(n.outputs["Color"], _input(bsdf, "Emission Color", "Emission"))
        strength = _input(bsdf, "Emission Strength")
        if strength is not None:
            strength.default_value = 1.0
    return mat


def pack_orm(images, size, name):
    """Empaqueta (AO, rugosidad, metal) en una imagen ORM: R=AO, G=rugosidad, B=metal."""
    import numpy as np

    w, h = size
    out = np.ones((h, w, 4), dtype=np.float32)
    for channel, img in zip((0, 1, 2), images):
        if img is None:
            continue
        src = img.copy()
        if tuple(src.size) != (w, h):
            src.scale(w, h)
        buf = np.empty(w * h * 4, dtype=np.float32)
        src.pixels.foreach_get(buf)
        out[:, :, channel] = buf.reshape(h, w, 4)[:, :, 0]
        bpy.data.images.remove(src)
    orm = bpy.data.images.new(name, w, h, alpha=False, float_buffer=False)
    orm.colorspace_settings.name = "Non-Color"
    orm.pixels.foreach_set(out.ravel())
    orm.pack()
    return orm


def _pow2_floor(v, cap):
    p = 1
    while p * 2 <= min(v, cap):
        p *= 2
    return max(p, 1)


def _material_images(objs):
    seen = []
    for o in objs:
        for slot in o.material_slots:
            m = slot.material
            if m is None or not m.use_nodes:
                continue
            for n in m.node_tree.nodes:
                if n.type == "TEX_IMAGE" and n.image is not None and n.image not in seen:
                    seen.append(n.image)
    return seen


class SLR_OT_pbr_from_folder(bpy.types.Operator):
    """Crea un material PBR completo a partir de una carpeta de texturas (detecta cada mapa por su nombre)"""
    bl_idname = "slr.pbr_from_folder"
    bl_label = "PBR en un clic"
    bl_options = {"REGISTER", "UNDO"}

    directory: bpy.props.StringProperty(subtype="DIR_PATH")
    filter_folder: bpy.props.BoolProperty(default=True, options={"HIDDEN"})
    filter_image: bpy.props.BoolProperty(default=True, options={"HIDDEN"})

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH":
            cls.poll_message_set("Selecciona la malla que recibirá el material")
            return False
        return True

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not os.path.isdir(self.directory):
            self.report({"ERROR"}, "Elige una carpeta de texturas")
            return {"CANCELLED"}
        files = {}
        for f in sorted(os.listdir(self.directory)):
            if f.lower().endswith(IMAGE_EXT):
                chan = classify(f)
                if chan and chan not in files:
                    files[chan] = os.path.join(self.directory, f)
        if not files:
            self.report({"ERROR"}, "No encontré texturas reconocibles (basecolor, normal, roughness, metallic…)")
            return {"CANCELLED"}
        name = os.path.basename(os.path.normpath(self.directory)) or "SL_PBR"
        mat = build_pbr_material(name, files)
        obj = context.active_object
        if obj.material_slots and obj.active_material_index < len(obj.material_slots):
            obj.material_slots[obj.active_material_index].material = mat
        else:
            obj.data.materials.append(mat)
        self.report({"INFO"}, f"Material '{name}': " + ", ".join(sorted(files)))
        return {"FINISHED"}


class SLR_OT_pack_orm(bpy.types.Operator):
    """Junta oclusión, rugosidad y metal del material activo en una sola textura ORM (como pide glTF/SL)"""
    bl_idname = "slr.pack_orm"
    bl_label = "Empaquetar ORM"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.active_material is None or not obj.active_material.use_nodes:
            cls.poll_message_set("Selecciona una malla con un material de nodos")
            return False
        return True

    def execute(self, context):
        mat = context.active_object.active_material
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if bsdf is None:
            self.report({"ERROR"}, "El material no tiene Principled BSDF")
            return {"CANCELLED"}

        def linked_image(inp):
            if inp is None or not inp.is_linked:
                return None
            node = inp.links[0].from_node
            return node.image if node.type == "TEX_IMAGE" else None

        rough = linked_image(_input(bsdf, "Roughness"))
        metal = linked_image(_input(bsdf, "Metallic"))
        ao = next((n.image for n in nt.nodes if n.type == "TEX_IMAGE" and n.image is not None
                   and classify(n.image.name) == "AO"), None)
        if rough is None and metal is None:
            self.report({"ERROR"}, "Conecta texturas a Roughness y/o Metallic")
            return {"CANCELLED"}
        size = max(((i.size[0], i.size[1]) for i in (rough, metal, ao) if i is not None), key=lambda s: s[0] * s[1])
        orm = pack_orm((ao, rough, metal), size, f"{mat.name}_ORM")
        node = nt.nodes.new("ShaderNodeTexImage")
        node.image = orm
        node.label = "ORM"
        node.location = (bsdf.location.x - 700, bsdf.location.y - 300)
        sep = nt.nodes.new("ShaderNodeSeparateColor" if hasattr(bpy.types, "ShaderNodeSeparateColor")
                           else "ShaderNodeSeparateRGB")
        sep.location = (bsdf.location.x - 400, bsdf.location.y - 300)
        nt.links.new(node.outputs["Color"], sep.inputs[0])
        nt.links.new(sep.outputs[1], _input(bsdf, "Roughness"))
        nt.links.new(sep.outputs[2], _input(bsdf, "Metallic"))
        self.report({"INFO"}, f"ORM '{orm.name}' {size[0]}×{size[1]} creado y conectado")
        return {"FINISHED"}


class SLR_OT_resize_textures(bpy.types.Operator):
    """Reduce las texturas de las mallas seleccionadas a potencias de 2 dentro del máximo elegido"""
    bl_idname = "slr.resize_textures"
    bl_label = "Texturas a tamaño SL"
    bl_options = {"REGISTER", "UNDO"}

    max_size: bpy.props.EnumProperty(name="Máximo", items=[("512", "512", ""), ("1024", "1024", ""),
                                                           ("2048", "2048", "")], default="1024")

    @classmethod
    def poll(cls, context):
        if not any(o.type == "MESH" for o in context.selected_objects):
            cls.poll_message_set("Selecciona mallas con materiales")
            return False
        return True

    def execute(self, context):
        cap = int(self.max_size)
        changed = []
        for img in _material_images([o for o in context.selected_objects if o.type == "MESH"]):
            w, h = img.size
            if w == 0 or h == 0:
                continue
            nw, nh = _pow2_floor(w, cap), _pow2_floor(h, cap)
            if (nw, nh) != (w, h):
                img.scale(nw, nh)
                changed.append(f"{img.name} {w}×{h}→{nw}×{nh}")
        self.report({"INFO"}, (f"{len(changed)} textura(s): " + "; ".join(changed[:4])) if changed
                    else "Todas las texturas ya tienen tamaño SL")
        return {"FINISHED"}


classes = (SLR_OT_pbr_from_folder, SLR_OT_pack_orm, SLR_OT_resize_textures)

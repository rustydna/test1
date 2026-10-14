import bpy

from . import anim_library, edition, hud, prefs, skeleton, ui_ops
from .report import grade, text_bar
from .weights import SL_MAX_MATERIALS

ICON_LEVEL = {"ERROR": "CANCEL", "WARNING": "ERROR", "INFO": "CHECKMARK"}

TABS = [
    ("RIG", "Esqueleto", "Esqueleto Bento, presets y proporciones", "ARMATURE_DATA", 0),
    ("WEIGHTS", "Pesos", "Vincular la malla y trabajar los pesos", "MOD_VERTEX_WEIGHT", 1),
    ("ANIM", "Animación", "Poses, expresiones y animaciones .anim", "ACTION", 2),
    ("CLOTH", "Ropa", "Ajuste, tallas y zonas de alfa", "MOD_CLOTH", 3),
    ("OBJECT", "Objetos", "Objetos estáticos, accesorios, LODs y física", "MESH_CUBE", 4),
    ("MATERIAL", "Materiales", "PBR y texturas", "MATERIAL", 5),
    ("EXPORT", "Exportar", "Validar, certificar y exportar", "EXPORT", 6),
]

TIPS = {
    "RIG": "Los presets de furro activan cola y orejas. Cualquier preset distinto del humano se sube "
           "con «Include joint positions».",
    "WEIGHTS": "Rojo en el mapa de pesos = SL rechazará la subida. Para ropa, transfiere los pesos del cuerpo.",
    "ANIM": "Genera, pulsa Espacio para verla y exporta a .anim. La prioridad 4 gana a casi todas las AO.",
    "CLOTH": "Ajusta sin atravesar con el cuerpo en reposo; luego genera las tallas.",
    "OBJECT": "La física en caja es la que menos Land Impact suma para muebles y paredes.",
    "MATERIAL": "SL toma el color base del modelo; sube el material PBR aparte (Build → Upload → Material).",
    "EXPORT": "Sube primero en Aditi (gratis). Avatares: Include skin weight (+ joint positions si cambiaste huesos).",
}


def _big(layout, scale=1.35):
    col = layout.column(align=True)
    col.scale_y = scale
    return col


def _progress(layout, value, text):
    if hasattr(layout, "progress"):
        layout.progress(factor=value / 100.0, type="BAR", text=text)
    else:
        layout.label(text=f"{text}  {text_bar(value, 16)}")


def _rig_of(context):
    obj = context.active_object
    if skeleton.is_sl_armature(obj):
        return obj
    if obj is not None and obj.type == "MESH":
        arm = skeleton.find_armature(obj)
        if skeleton.is_sl_armature(arm):
            return arm
    return None


def _wrap(text, width):
    words, lines, cur = text.split(), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width:
            lines.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    if cur:
        lines.append(cur)
    return lines


class SLR_PT_main(bpy.types.Panel):
    bl_label = "SL Rigger"
    bl_idname = "SLR_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SL Rigger"

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_ARMATURE")

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        p = prefs.get(context)

        head = layout.box()
        row = head.row()
        row.alignment = "CENTER"
        row.label(text=edition.EDITION_LABEL, icon="SOLO_ON" if edition.EDITION == "FOUNDER" else "FUND")
        self._dashboard(context, head)
        _big(head, 1.6).operator("slr.wizard", icon="PLAY")
        row = head.row(align=True)
        row.operator("slr.toggle_hud", text="HUD", icon="HIDE_OFF" if hud.is_enabled() else "HIDE_ON",
                     depress=hud.is_enabled())
        row.prop(scene, "slr_heatmap", text="Pesos", toggle=True, icon="MOD_VERTEX_WEIGHT")
        row.operator("slr.cheatsheet", text="", icon="QUESTION")
        row.operator("slr.welcome", text="", icon="INFO")

        self._guide(context, layout)

        tabs = layout.row(align=True)
        tabs.scale_y = 1.3
        tabs.prop(scene, "slr_tab", expand=True, icon_only=True)
        current = next(t for t in TABS if t[0] == scene.slr_tab)
        layout.label(text=current[1].upper(), icon=current[3])
        body = layout.column()
        getattr(self, "_tab_" + scene.slr_tab.lower())(context, body)
        if p.show_tips:
            tip = layout.box()
            tip.scale_y = 0.8
            for i, chunk in enumerate(_wrap(TIPS[scene.slr_tab], 46)):
                tip.label(text=chunk, icon="LIGHT" if i == 0 else "BLANK1")

    # -- tablero ------------------------------------------------------------------------------
    def _dashboard(self, context, layout):
        obj = context.active_object
        box = layout.box()
        if obj is None or obj.type not in {"MESH", "ARMATURE"}:
            box.label(text="Selecciona una malla o un esqueleto", icon="RESTRICT_SELECT_OFF")
            return
        if obj.type == "ARMATURE":
            box.label(text=obj.name, icon="ARMATURE_DATA")
            if skeleton.is_sl_armature(obj):
                box.label(text=f"{len(obj.data.bones)} huesos · {ui_ops.rig_height(obj):.2f} m · "
                               f"{obj.get('sl_preset', '—')}", icon="CHECKMARK")
            else:
                box.label(text="No es un esqueleto SL", icon="ERROR")
            return
        data = hud.current(context)
        if not data:
            box.label(text="Sal del modo edición para analizar", icon="EDITMODE_HLT")
            return
        st = data["stats"]
        letter, label = grade(st["score"])
        row = box.row()
        row.label(text=st["name"], icon="OUTLINER_OB_MESH")
        row.label(text=f"{letter} · {label}")
        _progress(box, st["score"], f"SL Ready {st['score']}/100")
        grid = box.grid_flow(columns=2, even_columns=True, align=True)
        grid.label(text=f"{st['tris']:,} tris".replace(",", "."), icon="MESH_DATA")
        grid.label(text=f"{st['materials']}/{SL_MAX_MATERIALS} caras",
                   icon="CHECKMARK" if st["materials"] <= SL_MAX_MATERIALS else "CANCEL")
        if st["rigged"]:
            grid.label(text=f"{st['joints']}/{skeleton.SL_MAX_JOINTS_PER_MESH} huesos",
                       icon="CHECKMARK" if st["joints"] <= skeleton.SL_MAX_JOINTS_PER_MESH else "CANCEL")
            grid.label(text=f"{st['unweighted']} sin peso", icon="CHECKMARK" if not st["unweighted"] else "CANCEL")
        else:
            grid.label(text="UV" if st["uv"] else "Sin UV", icon="CHECKMARK" if st["uv"] else "ERROR")
            grid.label(text="Estático", icon="MESH_CUBE")
        for pen, why in st["penalties"][:2]:
            r = box.row()
            r.alert = pen >= 25
            r.label(text=f"−{pen}  {why}", icon="ERROR")

    def _guide(self, context, layout):
        scene = context.scene
        steps = ui_ops.guide_steps(context)
        done = sum(1 for _, d, _ in steps if d)
        box = layout.box()
        row = box.row()
        row.prop(scene, "slr_show_guide", text="", emboss=False,
                 icon="DISCLOSURE_TRI_DOWN" if scene.slr_show_guide else "DISCLOSURE_TRI_RIGHT")
        row.label(text=f"Guía  {done}/{len(steps)}", icon="CHECKBOX_HLT" if done == len(steps) else "SEQUENCE")
        row.operator("slr.next_step", text="Siguiente", icon="FORWARD")
        if scene.slr_show_guide:
            col = box.column(align=True)
            for text, ok, _ in steps:
                col.label(text=text, icon="CHECKBOX_HLT" if ok else "CHECKBOX_DEHLT")

    # -- pestañas -----------------------------------------------------------------------------
    def _tab_rig(self, context, layout):
        scene = context.scene
        layout.template_icon_view(scene, "slr_preset", show_labels=True, scale=7.0, scale_popup=5.0)
        _big(layout).operator("slr.create_rig", icon="ADD")
        row = layout.row(align=True)
        row.operator("slr.fit_rig", text="Ajustar a malla", icon="FULLSCREEN_ENTER")
        row.operator("slr.scale_to_height", text="Altura exacta", icon="EMPTY_SINGLE_ARROW")
        row = layout.row(align=True)
        row.operator("slr.save_preset", text="Guardar preset", icon="FILE_TICK")
        row.operator("slr.load_preset", text="Cargar preset", icon="FILE_FOLDER")
        arm = _rig_of(context)
        if arm is None:
            return
        box = layout.box()
        box.label(text="Grupos Bento (clic = deforma / no deforma)", icon="BONE_DATA")
        grid = box.grid_flow(columns=2, even_columns=True, align=True)
        for key, (label, _, theme) in skeleton.DEFORM_GROUPS.items():
            on = any(b.use_deform for b in arm.data.bones
                     if b.name in skeleton.SL_INFO and skeleton.group_key(b.name) == key)
            op = grid.operator("slr.set_deform", text=label, depress=on, icon=f"COLORSET_{theme[-2:]}_VEC")
            op.group, op.enable = key, not on
        row = box.row(align=True)
        row.operator_menu_enum("slr.isolate_group", "group", text="Aislar grupo", icon="HIDE_OFF")
        row.operator("slr.isolate_group", text="Mostrar todo", icon="RESTRICT_VIEW_OFF").group = "ALL"
        layout.operator("slr.show_attachments", icon="EMPTY_ARROWS")

    def _tab_weights(self, context, layout):
        layout.operator("slr.convert_groups", icon="SORTALPHA")
        row = _big(layout, 1.2).row(align=True)
        row.operator("slr.bind", text="Pesos auto", icon="AUTO").mode = "AUTO"
        row.operator("slr.bind", text="Conservar").mode = "KEEP"
        row.operator("slr.bind", text="Vacíos").mode = "EMPTY"
        col = layout.column(align=True)
        col.operator("slr.transfer_weights", icon="MOD_DATA_TRANSFER")
        col.operator("slr.mirror_weights", icon="MOD_MIRROR")
        col.operator("slr.rigid_bind", icon="MOD_BUILD")
        col.operator("slr.merge_group", icon="AUTOMERGE_ON")
        col.operator("slr.clean_weights", icon="BRUSH_DATA")
        _big(layout, 1.2).operator("slr.weight_paint", icon="WPAINT_HLT")

    def _tab_anim(self, context, layout):
        box = layout.box()
        box.label(text="Poses", icon="POSE_HLT")
        row = box.row(align=True)
        row.operator_menu_enum("slr.body_pose", "pose", text="Cuerpo", icon="ARMATURE_DATA")
        row.operator_menu_enum("slr.hand_pose", "pose", text="Manos", icon="VIEW_PAN")
        row.operator_menu_enum("slr.face_pose", "pose", text="Cara", icon="USER")
        row = box.row(align=True)
        row.operator("slr.mirror_pose", text="Simetrizar", icon="MOD_MIRROR")
        row.operator("slr.reset_pose", text="Reposo", icon="LOOP_BACK")
        box = layout.box()
        box.label(text="Animaciones generadas", icon="ACTION")
        grid = box.grid_flow(columns=2, even_columns=True, align=True)
        icons = {"TAIL": "FORCE_CURVE", "EARS": "SOUND", "WINGS": "MOD_WAVE", "BREATHE": "FORCE_HARMONIC",
                 "BLINK": "HIDE_ON", "WALK": "ANIM", "WAVE": "VIEW_PAN", "DANCE": "SEQUENCE",
                 "STRESS": "MOD_SIMPLEDEFORM"}
        for key, (label, *_rest) in anim_library.GENERATORS.items():
            grid.operator("slr.generate_anim", text=label, icon=icons.get(key, "ACTION")).kind = key
        box.operator("slr.retarget", icon="ARMATURE_DATA")
        col = _big(layout, 1.3)
        col.operator("slr.export_anim", text="Exportar animación .anim", icon="RENDER_ANIMATION")
        col.operator("slr.export_anim", text="Exportar pose actual .anim", icon="POSE_HLT").static_pose = True

    def _tab_cloth(self, context, layout):
        col = layout.column(align=True)
        col.scale_y = 1.2
        col.operator("slr.transfer_weights", icon="MOD_DATA_TRANSFER")
        col.operator("slr.fit_clothing", icon="MOD_SHRINKWRAP")
        col.operator("slr.make_sizes", icon="FULLSCREEN_ENTER")
        col.operator("slr.alpha_zones", icon="MOD_MASK")

    def _tab_object(self, context, layout):
        col = layout.column(align=True)
        col.operator("slr.optimize", icon="MOD_REMESH")
        col.operator("slr.auto_uv", icon="UV")
        col.operator("slr.prepare_static", icon="OBJECT_ORIGIN")
        row = layout.row(align=True)
        row.operator("slr.make_lods", icon="MOD_DECIM")
        row.operator_menu_enum("slr.make_physics", "shape", text="Física", icon="PHYSICS")
        box = layout.box()
        box.label(text="Accesorios (pelo, zapatos, gafas…)", icon="EMPTY_ARROWS")
        box.operator("slr.show_attachments", icon="EMPTY_ARROWS")
        box.operator("slr.attachment_offset", icon="ORIENTATION_LOCAL")

    def _tab_material(self, context, layout):
        _big(layout, 1.3).operator("slr.pbr_from_folder", icon="NODE_MATERIAL")
        col = layout.column(align=True)
        col.operator("slr.pack_orm", icon="IMAGE_RGB")
        col.operator_menu_enum("slr.resize_textures", "max_size", text="Texturas a tamaño SL", icon="IMAGE_DATA")
        layout.operator("slr.export_materials", icon="MATERIAL")

    def _tab_export(self, context, layout):
        _big(layout, 1.2).operator("slr.validate", icon="VIEWZOOM")
        report = context.scene.slr_report
        if report:
            box = layout.box()
            col = box.column(align=True)
            for line in report.splitlines():
                lvl, _, msg = line.partition("|")
                r = col.row()
                r.alert = lvl == "ERROR"
                r.label(text=msg, icon=ICON_LEVEL.get(lvl, "DOT"))
        col = _big(layout, 1.3)
        col.operator("slr.export_dae", icon="FILE_3D")
        col.operator("slr.export_gltf", icon="FILE_3D")
        row = layout.row(align=True)
        row.operator("slr.batch_export", icon="DOCUMENTS")
        row.operator("slr.certificate", icon="FILE_TEXT")


class SLR_MT_pie(bpy.types.Menu):
    bl_label = "SL Rigger"
    bl_idname = "SLR_MT_pie"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator("slr.create_rig", icon="ARMATURE_DATA")
        pie.operator("slr.export_dae", icon="FILE_3D")
        pie.operator("slr.validate", icon="VIEWZOOM")
        pie.operator("slr.wizard", icon="PLAY")
        pie.operator("slr.bind", text="Pesos auto", icon="AUTO").mode = "AUTO"
        pie.operator("slr.toggle_hud", icon="HIDE_OFF")
        pie.operator("slr.transfer_weights", icon="MOD_DATA_TRANSFER")
        pie.operator("slr.weight_paint", icon="WPAINT_HLT")


class SLR_MT_pie_anim(bpy.types.Menu):
    bl_label = "SL Rigger · Animación"
    bl_idname = "SLR_MT_pie_anim"

    def draw(self, context):
        pie = self.layout.menu_pie()
        pie.operator_menu_enum("slr.hand_pose", "pose", text="Manos", icon="VIEW_PAN")
        pie.operator("slr.export_anim", text="Exportar .anim", icon="RENDER_ANIMATION")
        pie.operator_menu_enum("slr.face_pose", "pose", text="Cara", icon="USER")
        pie.operator_menu_enum("slr.generate_anim", "kind", text="Generar animación", icon="ACTION")
        pie.operator_menu_enum("slr.body_pose", "pose", text="Cuerpo", icon="ARMATURE_DATA")
        pie.operator("slr.reset_pose", icon="LOOP_BACK")
        pie.operator("slr.mirror_pose", icon="MOD_MIRROR")
        pie.operator("slr.export_anim", text="Pose → .anim", icon="POSE_HLT").static_pose = True


def menu_export(self, context):
    self.layout.operator("slr.export_dae", text="Second Life Collada (.dae)")
    self.layout.operator("slr.export_gltf", text="Second Life glTF (.glb/.gltf)")
    self.layout.operator("slr.export_anim", text="Second Life animación (.anim)")


def statusbar(self, context):
    if not prefs.get(context).show_statusbar:
        return
    data = hud.current(context)
    if not data:
        return
    sc = data["stats"]["score"]
    self.layout.label(text=f"SL {sc}/100", icon="CHECKMARK" if sc >= 85 else "ERROR")


def header_chip(self, context):
    if not prefs.get(context).show_header:
        return
    data = hud.current(context)
    if not data:
        return
    sc = data["stats"]["score"]
    self.layout.operator("slr.toggle_hud", text=f"SL {sc}", icon="CHECKMARK" if sc >= 85 else "ERROR",
                         depress=hud.is_enabled())


classes = (SLR_PT_main, SLR_MT_pie, SLR_MT_pie_anim)

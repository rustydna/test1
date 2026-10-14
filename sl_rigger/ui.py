import bpy

from . import edition, hud, skeleton
from .weights import SL_MAX_MATERIALS

ICON_LEVEL = {"ERROR": "CANCEL", "WARNING": "ERROR", "INFO": "CHECKMARK"}


def _big(layout, scale=1.35):
    col = layout.column(align=True)
    col.scale_y = scale
    return col


class _Base:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SL Rigger"


class SLR_PT_main(_Base, bpy.types.Panel):
    bl_label = "SL Rigger"
    bl_idname = "SLR_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon="OUTLINER_OB_ARMATURE")

    def draw(self, context):
        layout = self.layout
        head = layout.box()
        row = head.row()
        row.alignment = "CENTER"
        row.label(text=edition.EDITION_LABEL, icon="SOLO_ON" if edition.EDITION == "FOUNDER" else "FUND")
        col = _big(head, 1.6)
        col.operator("slr.wizard", icon="PLAY")
        row = head.row(align=True)
        row.operator("slr.toggle_hud", text="Monitor HUD", icon="HIDE_OFF" if hud.is_enabled() else "HIDE_ON",
                     depress=hud.is_enabled())
        row.prop(context.scene, "slr_heatmap", text="Mapa de pesos", toggle=True, icon="MOD_VERTEX_WEIGHT")

        obj = context.active_object
        dash = layout.box()
        if obj is None or obj.type not in {"MESH", "ARMATURE"}:
            dash.label(text="Selecciona una malla o un esqueleto", icon="INFO")
            return
        if obj.type == "ARMATURE":
            ok = skeleton.is_sl_armature(obj)
            dash.label(text=obj.name, icon="ARMATURE_DATA")
            dash.label(text=f"{len(obj.data.bones)} huesos · preset {obj.get('sl_preset', '—')}" if ok
                       else "No es un esqueleto SL", icon="CHECKMARK" if ok else "ERROR")
            return
        if obj.mode == "EDIT":
            dash.label(text="Sal del modo edición para analizar", icon="EDITMODE_HLT")
            return
        st = hud.current(context)["stats"]
        dash.label(text=st["name"], icon="OUTLINER_OB_MESH")
        grid = dash.grid_flow(columns=2, even_columns=True, align=True)
        grid.label(text=f"{st['tris']:,} tris".replace(",", "."), icon="MESH_DATA")
        grid.label(text=f"{st['materials']}/{SL_MAX_MATERIALS} mat.",
                   icon="CHECKMARK" if st["materials"] <= SL_MAX_MATERIALS else "CANCEL")
        grid.label(text="UV" if st["uv"] else "Sin UV", icon="CHECKMARK" if st["uv"] else "ERROR")
        grid.label(text="Escala OK" if st["scale_ok"] else "Escala", icon="CHECKMARK" if st["scale_ok"] else "ERROR")
        if st["rigged"]:
            grid.label(text=f"{st['joints']}/{skeleton.SL_MAX_JOINTS_PER_MESH} huesos",
                       icon="CHECKMARK" if st["joints"] <= skeleton.SL_MAX_JOINTS_PER_MESH else "CANCEL")
            grid.label(text=f"{st['unweighted']} sin peso", icon="CHECKMARK" if not st["unweighted"] else "CANCEL")
        else:
            grid.label(text="Estático", icon="MESH_CUBE")


class SLR_PT_rig(_Base, bpy.types.Panel):
    bl_label = "Esqueleto Bento"
    bl_parent_id = "SLR_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon="ARMATURE_DATA")

    def draw(self, context):
        layout = self.layout
        layout.prop(context.scene, "slr_preset", text="")
        col = _big(layout)
        col.operator("slr.create_rig", icon="ADD")
        layout.operator("slr.fit_rig", icon="FULLSCREEN_ENTER")
        arm = context.active_object
        if arm is not None and arm.type == "MESH":
            arm = skeleton.find_armature(arm)
        if skeleton.is_sl_armature(arm):
            box = layout.box()
            box.label(text="Grupos que deforman", icon="BONE_DATA")
            grid = box.grid_flow(columns=2, even_columns=True, align=True)
            for key, (label, _, _) in skeleton.DEFORM_GROUPS.items():
                on = any(b.use_deform for b in arm.data.bones
                         if b.name in skeleton.SL_INFO and skeleton.group_key(b.name) == key)
                op = grid.operator("slr.set_deform", text=label, depress=on,
                                   icon="CHECKBOX_HLT" if on else "CHECKBOX_DEHLT")
                op.group, op.enable = key, not on


class SLR_PT_weights(_Base, bpy.types.Panel):
    bl_label = "Malla → Avatar / ropa"
    bl_parent_id = "SLR_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon="MOD_VERTEX_WEIGHT")

    def draw(self, context):
        layout = self.layout
        layout.operator("slr.convert_groups", icon="SORTALPHA")
        row = _big(layout, 1.2).row(align=True)
        row.operator("slr.bind", text="Pesos auto", icon="AUTO").mode = "AUTO"
        row.operator("slr.bind", text="Conservar").mode = "KEEP"
        row.operator("slr.bind", text="Vacíos").mode = "EMPTY"
        col = layout.column(align=True)
        col.operator("slr.transfer_weights", icon="MOD_DATA_TRANSFER")
        col.operator("slr.mirror_weights", icon="MOD_MIRROR")
        col.operator("slr.rigid_bind", icon="MOD_BUILD")
        col.operator("slr.clean_weights", icon="BRUSH_DATA")


class SLR_PT_static(_Base, bpy.types.Panel):
    bl_label = "Objeto estático"
    bl_parent_id = "SLR_PT_main"
    bl_options = {"DEFAULT_CLOSED"}

    def draw_header(self, context):
        self.layout.label(text="", icon="MESH_CUBE")

    def draw(self, context):
        layout = self.layout
        layout.operator("slr.prepare_static", icon="OBJECT_ORIGIN")
        row = layout.row(align=True)
        row.operator("slr.make_lods", icon="MOD_DECIM")
        row.operator("slr.make_physics", icon="PHYSICS")


class SLR_PT_export(_Base, bpy.types.Panel):
    bl_label = "Validar y exportar"
    bl_parent_id = "SLR_PT_main"

    def draw_header(self, context):
        self.layout.label(text="", icon="EXPORT")

    def draw(self, context):
        layout = self.layout
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
        layout.operator("slr.export_materials", icon="MATERIAL")


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
        pie.operator("slr.clean_weights", icon="BRUSH_DATA")


def menu_export(self, context):
    self.layout.operator("slr.export_dae", text="Second Life Collada (.dae)")
    self.layout.operator("slr.export_gltf", text="Second Life glTF (.glb/.gltf)")


classes = (SLR_PT_main, SLR_PT_rig, SLR_PT_weights, SLR_PT_static, SLR_PT_export, SLR_MT_pie)

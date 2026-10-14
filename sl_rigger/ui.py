import bpy


class SLR_PT_main(bpy.types.Panel):
    bl_label = "SL Rigger"
    bl_idname = "SLR_PT_main"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "SL Rigger"

    def draw(self, context):
        layout = self.layout

        box = layout.box()
        box.label(text="1. Esqueleto", icon="ARMATURE_DATA")
        box.prop(context.scene, "slr_preset", text="")
        box.operator("slr.create_rig", icon="ADD")
        box.operator("slr.fit_rig", icon="FULLSCREEN_ENTER")

        box = layout.box()
        box.label(text="2. Malla → Avatar / ropa", icon="OUTLINER_OB_MESH")
        box.operator("slr.convert_groups", icon="SORTALPHA")
        row = box.row(align=True)
        row.operator("slr.bind", text="Pesos auto").mode = "AUTO"
        row.operator("slr.bind", text="Conservar").mode = "KEEP"
        row.operator("slr.bind", text="Vacíos").mode = "EMPTY"
        box.operator("slr.clean_weights", icon="BRUSH_DATA")

        box = layout.box()
        box.label(text="3. Objeto estático", icon="MESH_CUBE")
        box.operator("slr.prepare_static", icon="OBJECT_ORIGIN")
        row = box.row(align=True)
        row.operator("slr.make_lods", icon="MOD_DECIM")
        row.operator("slr.make_physics", icon="PHYSICS")

        box = layout.box()
        box.label(text="4. Validar y exportar", icon="EXPORT")
        box.operator("slr.validate", icon="CHECKMARK")
        report = context.scene.slr_report
        if report:
            col = box.column(align=True)
            icons = {"ERROR": "ERROR", "WARNING": "INFO", "INFO": "CHECKMARK"}
            for line in report.splitlines():
                lvl, _, msg = line.partition("|")
                col.label(text=msg, icon=icons.get(lvl, "DOT"))
        col = box.column(align=True)
        col.operator("slr.export_dae", icon="FILE_3D")
        col.operator("slr.export_gltf", icon="FILE_3D")
        col.operator("slr.export_materials", icon="MATERIAL")


def menu_export(self, context):
    self.layout.operator("slr.export_dae", text="Second Life Collada (.dae)")
    self.layout.operator("slr.export_gltf", text="Second Life glTF (.glb/.gltf)")


classes = (SLR_PT_main,)

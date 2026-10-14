bl_info = {
    "name": "SL Rigger",
    "author": "SL Rigger contributors",
    "version": (0, 5, 0),
    "blender": (3, 5, 0),
    "location": "Vista 3D > Barra lateral (N) > SL Rigger  ·  Menús radiales: Mayús+Alt+Q / Mayús+Alt+W",
    "description": "Avatares Bento, ropa, animaciones .anim y objetos para Second Life",
    "category": "Import-Export",
}

import bpy

from . import (anim_export, anim_library, attachments, clothing, hud, meshtools, operators, prefs, presets,
               previews, report, retarget, textures, tools, ui, ui_ops)

_classes = (prefs.classes + operators.classes + tools.classes + hud.classes + anim_export.classes
            + anim_library.classes + retarget.classes + attachments.classes + clothing.classes
            + meshtools.classes + textures.classes + report.classes + ui_ops.classes + ui.classes)
_keymaps = []


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    S = bpy.types.Scene
    S.slr_report = bpy.props.StringProperty(default="")
    S.slr_preset = bpy.props.EnumProperty(name="Preset de avatar", items=previews.preset_items)
    S.slr_heatmap = bpy.props.BoolProperty(
        name="Mapa de pesos", default=True,
        description="Colorea los vértices según sus huesos: rojo sin peso, verde correcto, magenta más de 4")
    S.slr_tab = bpy.props.EnumProperty(name="Sección", items=[t for t in ui.TABS], default="RIG")
    S.slr_show_guide = bpy.props.BoolProperty(name="Mostrar guía", default=True)
    bpy.types.TOPBAR_MT_file_export.append(ui.menu_export)
    bpy.types.STATUSBAR_HT_header.append(ui.statusbar)
    bpy.types.VIEW3D_HT_header.append(ui.header_chip)
    hud.register_handlers()
    kc = bpy.context.window_manager.keyconfigs.addon if bpy.context.window_manager else None
    if kc is not None:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        for key, menu in (("Q", "SLR_MT_pie"), ("W", "SLR_MT_pie_anim")):
            kmi = km.keymap_items.new("wm.call_menu_pie", key, "PRESS", shift=True, alt=True)
            kmi.properties.name = menu
            _keymaps.append((km, kmi))
    ui_ops.schedule_welcome()


def unregister():
    hud.unregister_handlers()
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    bpy.types.TOPBAR_MT_file_export.remove(ui.menu_export)
    bpy.types.STATUSBAR_HT_header.remove(ui.statusbar)
    bpy.types.VIEW3D_HT_header.remove(ui.header_chip)
    S = bpy.types.Scene
    for prop in ("slr_report", "slr_preset", "slr_heatmap", "slr_tab", "slr_show_guide"):
        delattr(S, prop)
    previews.unregister()
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

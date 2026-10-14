bl_info = {
    "name": "SL Rigger",
    "author": "SL Rigger contributors",
    "version": (0, 4, 0),
    "blender": (3, 5, 0),
    "location": "Vista 3D > Barra lateral (N) > SL Rigger  ·  Menú radial: Mayús+Alt+Q",
    "description": "Avatares Bento, ropa rigged y objetos para Second Life",
    "category": "Import-Export",
}

import bpy

from . import hud, operators, presets, tools, ui

_classes = operators.classes + tools.classes + hud.classes + ui.classes
_keymaps = []


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.slr_report = bpy.props.StringProperty(default="")
    bpy.types.Scene.slr_preset = bpy.props.EnumProperty(
        name="Preset de avatar", items=presets.enum_items(), default="HUMAN")
    bpy.types.Scene.slr_heatmap = bpy.props.BoolProperty(
        name="Mapa de pesos", default=True,
        description="Colorea los vértices según sus huesos: rojo sin peso, verde correcto, magenta más de 4")
    bpy.types.TOPBAR_MT_file_export.append(ui.menu_export)
    hud.register_handlers()
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is not None:
        km = kc.keymaps.new(name="3D View", space_type="VIEW_3D")
        kmi = km.keymap_items.new("wm.call_menu_pie", "Q", "PRESS", shift=True, alt=True)
        kmi.properties.name = "SLR_MT_pie"
        _keymaps.append((km, kmi))


def unregister():
    hud.unregister_handlers()
    for km, kmi in _keymaps:
        km.keymap_items.remove(kmi)
    _keymaps.clear()
    bpy.types.TOPBAR_MT_file_export.remove(ui.menu_export)
    del bpy.types.Scene.slr_report
    del bpy.types.Scene.slr_preset
    del bpy.types.Scene.slr_heatmap
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

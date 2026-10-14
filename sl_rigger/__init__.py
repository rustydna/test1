bl_info = {
    "name": "SL Rigger",
    "author": "SL Rigger contributors",
    "version": (0, 2, 0),
    "blender": (3, 6, 0),
    "location": "Vista 3D > Barra lateral (N) > SL Rigger",
    "description": "Convierte mallas en avatares, ropa rigged y objetos para Second Life",
    "category": "Import-Export",
}

import bpy

from . import operators, ui

_classes = operators.classes + ui.classes


def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    bpy.types.Scene.slr_report = bpy.props.StringProperty(default="")
    bpy.types.TOPBAR_MT_file_export.append(ui.menu_export)


def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(ui.menu_export)
    del bpy.types.Scene.slr_report
    for cls in reversed(_classes):
        bpy.utils.unregister_class(cls)

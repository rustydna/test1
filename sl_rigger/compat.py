"""Compatibilidad entre versiones de Blender (3.5 en adelante)."""

import bpy


def move_modifier_first(context, obj, name):
    """Pone el modificador `name` el primero de la pila.

    ObjectModifiers.move() no existe en todas las versiones; si falta se usa el
    operador modifier_move_to_index con un contexto sobrescrito.
    """
    mods = obj.modifiers
    index = mods.find(name)
    if index <= 0:
        return
    if hasattr(mods, "move"):
        mods.move(index, 0)
        return
    with context.temp_override(object=obj, active_object=obj):
        bpy.ops.object.modifier_move_to_index(modifier=name, index=0)

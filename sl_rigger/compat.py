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


def assign_bone_groups(arm_obj, groups):
    """Crea colecciones/grupos de huesos con color.

    groups: {nombre: (tema de color, [huesos], visible)}.
    Blender 4.0+ usa colecciones de huesos; 3.x usa grupos de huesos del pose.
    """
    data = arm_obj.data
    if hasattr(data, "collections"):
        for cname, (theme, names, visible) in groups.items():
            coll = data.collections.new(cname)
            for n in names:
                b = data.bones.get(n)
                if b is not None:
                    coll.assign(b)
                    b.color.palette = theme
            coll.is_visible = visible
        return
    pose = arm_obj.pose
    for cname, (theme, names, visible) in groups.items():
        grp = pose.bone_groups.new(name=cname)
        grp.color_set = theme
        for n in names:
            pb = pose.bones.get(n)
            if pb is not None:
                pb.bone_group = grp
                if not visible:
                    data.bones[n].hide = True


def gpu_shader(kind):
    """Nombre del shader integrado según versión ('UNIFORM_COLOR' o 'FLAT_COLOR')."""
    import gpu
    try:
        return gpu.shader.from_builtin(kind)
    except (ValueError, SystemError):
        return gpu.shader.from_builtin("3D_" + kind)

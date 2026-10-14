"""Monitor HUD en el visor 3D: estado de la malla activa y mapa de calor de pesos.

Mapa de calor por vértice:
  rojo     sin peso (SL rechaza la subida)
  verde    1–4 huesos (correcto; más claro con más huesos)
  magenta  más de 4 huesos (se recortará al exportar)
"""

import bpy

from . import compat
from .skeleton import ALL_SL_BONE_NAMES, SL_MAX_JOINTS_PER_MESH, find_armature, joints_with_ancestors
from .weights import SL_MAX_INFLUENCES, SL_MAX_MATERIALS

_handlers = {}
_cache = {"key": None, "stats": None, "points": None}

CYAN = (0.0, 0.9, 1.0, 1.0)
OK = (0.25, 1.0, 0.55, 1.0)
WARN = (1.0, 0.75, 0.1, 1.0)
BAD = (1.0, 0.25, 0.3, 1.0)
DIM = (0.65, 0.75, 0.85, 1.0)


def analyze(obj):
    """Estadísticas de la malla para el monitor (también usado por el panel)."""
    me = obj.data
    me.calc_loop_triangles()
    stats = {
        "name": obj.name,
        "tris": len(me.loop_triangles),
        "verts": len(me.vertices),
        "materials": len(obj.material_slots),
        "uv": bool(me.uv_layers),
        "scale_ok": all(abs(s - 1.0) < 1e-4 for s in obj.scale),
        "rigged": False,
    }
    counts = None
    arm = find_armature(obj)
    if arm is not None and "mPelvis" in arm.data.bones:
        sl_idx = {vg.index for vg in obj.vertex_groups if vg.name in ALL_SL_BONE_NAMES}
        counts = [sum(1 for g in v.groups if g.group in sl_idx and g.weight > 0.0) for v in me.vertices]
        used = {obj.vertex_groups[g.group].name for v in me.vertices for g in v.groups
                if g.group in sl_idx and g.weight > 0.0}
        stats.update({
            "rigged": True,
            "rig": arm.name,
            "unweighted": sum(1 for c in counts if c == 0),
            "over": sum(1 for c in counts if c > SL_MAX_INFLUENCES),
            "joints": len(joints_with_ancestors(arm, used)),
        })
    return stats, counts


def _status_lines(st):
    lines = [("SL RIGGER  //  MONITOR", CYAN), (st["name"], DIM)]
    lines.append((f"Triángulos {st['tris']:,}   Vértices {st['verts']:,}".replace(",", "."), DIM))
    mat_col = BAD if st["materials"] > SL_MAX_MATERIALS else OK
    lines.append((f"Materiales {st['materials']}/{SL_MAX_MATERIALS}", mat_col))
    lines.append(("UV  OK" if st["uv"] else "UV  FALTA", OK if st["uv"] else WARN))
    lines.append(("Escala  aplicada" if st["scale_ok"] else "Escala  SIN APLICAR", OK if st["scale_ok"] else WARN))
    if st["rigged"]:
        j_col = BAD if st["joints"] > SL_MAX_JOINTS_PER_MESH else OK
        lines.append((f"Rig  {st['rig']}", DIM))
        lines.append((f"Articulaciones {st['joints']}/{SL_MAX_JOINTS_PER_MESH}", j_col))
        lines.append((f"Sin peso {st['unweighted']}", BAD if st["unweighted"] else OK))
        lines.append((f">4 huesos {st['over']}", WARN if st["over"] else OK))
    else:
        lines.append(("Estático (sin rig)", DIM))
    ready = (st["materials"] <= SL_MAX_MATERIALS and (not st["rigged"] or
             (st["unweighted"] == 0 and st["joints"] <= SL_MAX_JOINTS_PER_MESH)))
    lines.append(("● LISTO PARA SL" if ready else "● REVISAR ANTES DE SUBIR", OK if ready else BAD))
    return lines


def current(context):
    obj = context.active_object
    if obj is None or obj.type != "MESH" or obj.mode == "EDIT":
        return None
    key = (obj.name, obj.data.name, len(obj.data.vertices), _cache.get("tick", 0),
           context.scene.slr_heatmap)
    if _cache["key"] != key:
        stats, counts = analyze(obj)
        points = None
        if counts is not None and context.scene.slr_heatmap and len(counts) <= 300000:
            cols = []
            for c in counts:
                if c == 0:
                    cols.append(BAD)
                elif c > SL_MAX_INFLUENCES:
                    cols.append((1.0, 0.2, 1.0, 1.0))
                else:
                    g = 0.55 + 0.45 * (c / SL_MAX_INFLUENCES)
                    cols.append((0.1, g, 0.45, 1.0))
            points = ([v.co.copy() for v in obj.data.vertices], cols)
        _cache.update(key=key, stats=stats, points=points)
    return _cache


def _draw_points():
    try:
        context = bpy.context
        if not context.scene.slr_heatmap:
            return
        data = current(context)
        if not data or not data["points"]:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        coords, cols = data["points"]
        shader = compat.gpu_shader("FLAT_COLOR")
        batch = batch_for_shader(shader, "POINTS", {"pos": coords, "color": cols})
        gpu.state.point_size_set(5.0)
        gpu.state.depth_test_set("LESS_EQUAL")
        with gpu.matrix.push_pop():
            gpu.matrix.multiply_matrix(context.active_object.matrix_world)
            batch.draw(shader)
        gpu.state.depth_test_set("NONE")
        gpu.state.point_size_set(1.0)
    except Exception as exc:  # nunca romper el dibujo del visor
        print("[SL Rigger] HUD:", exc)


def _draw_panel():
    try:
        context = bpy.context
        data = current(context)
        if not data:
            return
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        lines = _status_lines(data["stats"])
        ui = context.preferences.system.ui_scale
        size, pad, lh = int(12 * ui), int(10 * ui), int(17 * ui)
        width = int(270 * ui)
        height = pad * 2 + lh * len(lines)
        x = int(20 * ui)
        y = context.region.height - height - int(60 * ui)
        shader = compat.gpu_shader("UNIFORM_COLOR")
        gpu.state.blend_set("ALPHA")
        rect = [(x, y), (x + width, y), (x + width, y + height), (x, y + height)]
        batch = batch_for_shader(shader, "TRI_FAN", {"pos": rect})
        shader.bind()
        shader.uniform_float("color", (0.02, 0.04, 0.08, 0.78))
        batch.draw(shader)
        edge = batch_for_shader(shader, "LINE_LOOP", {"pos": rect})
        shader.uniform_float("color", (0.0, 0.9, 1.0, 0.9))
        edge.draw(shader)
        bar = batch_for_shader(shader, "TRI_FAN", {"pos": [(x, y + height - 3), (x + width, y + height - 3),
                                                            (x + width, y + height), (x, y + height)]})
        bar.draw(shader)
        gpu.state.blend_set("NONE")
        font = 0
        try:
            blf.size(font, size)
        except TypeError:
            blf.size(font, size, 72)
        ty = y + height - pad - lh + 4
        for text, col in lines:
            blf.color(font, *col)
            blf.position(font, x + pad, ty, 0)
            blf.draw(font, text)
            ty -= lh
    except Exception as exc:
        print("[SL Rigger] HUD:", exc)


def _on_depsgraph(scene, depsgraph):
    if depsgraph.id_type_updated("MESH"):
        _cache["tick"] = _cache.get("tick", 0) + 1


def invalidate():
    _cache["tick"] = _cache.get("tick", 0) + 1


def register_handlers():
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister_handlers():
    disable()
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)


def enable():
    if _handlers:
        return
    space = bpy.types.SpaceView3D
    _handlers["points"] = space.draw_handler_add(_draw_points, (), "WINDOW", "POST_VIEW")
    _handlers["panel"] = space.draw_handler_add(_draw_panel, (), "WINDOW", "POST_PIXEL")


def disable():
    space = bpy.types.SpaceView3D
    for h in list(_handlers.values()):
        space.draw_handler_remove(h, "WINDOW")
    _handlers.clear()
    _cache.update(key=None, stats=None, points=None)


def is_enabled():
    return bool(_handlers)


def _redraw():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class SLR_OT_toggle_hud(bpy.types.Operator):
    """Muestra u oculta el monitor HUD en el visor 3D"""
    bl_idname = "slr.toggle_hud"
    bl_label = "Monitor HUD"

    def execute(self, context):
        disable() if is_enabled() else enable()
        _redraw()
        return {"FINISHED"}


classes = (SLR_OT_toggle_hud,)

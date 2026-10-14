"""Monitor HUD en el visor 3D.

* Panel de estado con puntuación SL Ready, tema de color y posición configurables.
* Mapa de calor de pesos: rojo sin peso, verde 1–4 huesos, magenta más de 4.
* Etiquetas flotantes de los grupos Bento sobre el esqueleto.
* Notificaciones (toasts) que se desvanecen.
"""

import time

import bpy

from . import compat, prefs
from .skeleton import ALL_SL_BONE_NAMES, SL_MAX_JOINTS_PER_MESH, find_armature, is_sl_armature, \
    joints_with_ancestors
from .weights import SL_MAX_INFLUENCES, SL_MAX_MATERIALS

_handlers = {}
_cache = {"key": None, "stats": None, "points": None, "tick": 0}
_toast = {"text": "", "until": 0.0}

OK = (0.35, 1.0, 0.55, 1.0)
WARN = (1.0, 0.75, 0.1, 1.0)
BAD = (1.0, 0.3, 0.38, 1.0)
DIM = (0.7, 0.78, 0.88, 1.0)

# Etiquetas: hueso ancla → texto.
LABELS = {"mHead": "CABEZA", "mFaceRoot": "CARA", "mChest": "TORSO", "mWristLeft": "MANO IZQ.",
          "mWristRight": "MANO DER.", "mTail3": "COLA", "mWingsRoot": "ALAS", "mHindLimbsRoot": "PATAS",
          "mGroin": "INGLE", "mPelvis": "PELVIS", "mFaceEar2Left": "OREJA", "mFaceEar2Right": "OREJA"}


def analyze(obj):
    me = obj.data
    me.calc_loop_triangles()
    stats = {
        "name": obj.name, "tris": len(me.loop_triangles), "verts": len(me.vertices),
        "materials": len(obj.material_slots), "uv": bool(me.uv_layers),
        "scale_ok": all(abs(s - 1.0) < 1e-4 for s in obj.scale), "rigged": False,
    }
    counts = None
    arm = find_armature(obj)
    if arm is not None and "mPelvis" in arm.data.bones:
        sl_idx = {vg.index for vg in obj.vertex_groups if vg.name in ALL_SL_BONE_NAMES}
        counts = [sum(1 for g in v.groups if g.group in sl_idx and g.weight > 0.0) for v in me.vertices]
        used = {obj.vertex_groups[g.group].name for v in me.vertices for g in v.groups
                if g.group in sl_idx and g.weight > 0.0}
        stats.update(rigged=True, rig=arm.name, unweighted=sum(1 for c in counts if c == 0),
                     over=sum(1 for c in counts if c > SL_MAX_INFLUENCES),
                     joints=len(joints_with_ancestors(arm, used)))
    from .report import score
    stats["score"], stats["penalties"] = score(stats)
    return stats, counts


def current(context):
    obj = context.active_object
    if obj is None or obj.type != "MESH" or obj.mode == "EDIT":
        return None
    key = (obj.name, obj.data.name, len(obj.data.vertices), _cache["tick"], context.scene.slr_heatmap)
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


def invalidate():
    _cache["tick"] += 1


def toast(text, seconds=3.5):
    _toast["text"] = text
    _toast["until"] = time.time() + seconds
    if not bpy.app.background and _handlers:
        _redraw()
        if not bpy.app.timers.is_registered(_toast_tick):
            bpy.app.timers.register(_toast_tick, first_interval=0.1)


def _toast_tick():
    _redraw()
    return 0.1 if time.time() < _toast["until"] + 0.2 else None


# --------------------------------------------------------------------------- dibujo

def _font_size(size):
    import blf
    try:
        blf.size(0, size)
    except TypeError:
        blf.size(0, size, 72)


def _rect(shader, batch_for_shader, x0, y0, x1, y1, color, kind="TRI_FAN"):
    batch = batch_for_shader(shader, kind, {"pos": [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]})
    shader.bind()
    shader.uniform_float("color", color)
    batch.draw(shader)


def _status_lines(st):
    lines = [(st["name"], DIM)]
    lines.append((f"Triángulos {st['tris']:,}   Vértices {st['verts']:,}".replace(",", "."), DIM))
    lines.append((f"Materiales {st['materials']}/{SL_MAX_MATERIALS}",
                  BAD if st["materials"] > SL_MAX_MATERIALS else OK))
    lines.append(("UV  OK" if st["uv"] else "UV  FALTA", OK if st["uv"] else WARN))
    lines.append(("Escala  aplicada" if st["scale_ok"] else "Escala  SIN APLICAR", OK if st["scale_ok"] else WARN))
    if st["rigged"]:
        lines.append((f"Rig  {st['rig']}", DIM))
        lines.append((f"Articulaciones {st['joints']}/{SL_MAX_JOINTS_PER_MESH}",
                      BAD if st["joints"] > SL_MAX_JOINTS_PER_MESH else OK))
        lines.append((f"Sin peso {st['unweighted']}", BAD if st["unweighted"] else OK))
        lines.append((f">4 huesos {st['over']}", WARN if st["over"] else OK))
    else:
        lines.append(("Estático (sin rig)", DIM))
    return lines


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
        import blf
        import gpu
        from gpu_extras.batch import batch_for_shader
        p = prefs.get(context)
        _, accent, bg = prefs.theme(context)
        accent4 = (*accent, 1.0)
        ui = context.preferences.system.ui_scale * p.hud_scale
        shader = compat.gpu_shader("UNIFORM_COLOR")
        region = context.region
        data = current(context)
        gpu.state.blend_set("ALPHA")
        if data:
            st = data["stats"]
            lines = _status_lines(st)
            size, pad, lh = int(12 * ui), int(10 * ui), int(17 * ui)
            width = int(280 * ui)
            height = pad * 2 + lh * (len(lines) + 3)
            left = p.hud_corner in ("TL", "BL")
            top = p.hud_corner in ("TL", "TR")
            x = int(20 * ui) if left else region.width - width - int(60 * ui)
            y = region.height - height - int(60 * ui) if top else int(40 * ui)
            _rect(shader, batch_for_shader, x, y, x + width, y + height, (*bg, p.hud_opacity))
            _rect(shader, batch_for_shader, x, y, x + width, y + height, (*accent, 0.9), "LINE_LOOP")
            _rect(shader, batch_for_shader, x, y + height - int(3 * ui), x + width, y + height, accent4)
            sc = st["score"]
            col = OK if sc >= 85 else WARN if sc >= 60 else BAD
            bx0, by0 = x + pad, y + height - pad - lh * 2 - int(4 * ui)
            bx1 = x + width - pad
            _rect(shader, batch_for_shader, bx0, by0, bx1, by0 + int(6 * ui), (1, 1, 1, 0.08))
            _rect(shader, batch_for_shader, bx0, by0, bx0 + (bx1 - bx0) * sc / 100.0, by0 + int(6 * ui), col)
            _font_size(int(13 * ui))
            blf.color(0, *accent4)
            blf.position(0, x + pad, y + height - pad - lh + 2, 0)
            blf.draw(0, "SL RIGGER  //  MONITOR")
            blf.color(0, *col)
            blf.position(0, x + width - pad - int(70 * ui), y + height - pad - lh + 2, 0)
            blf.draw(0, f"{sc}/100")
            _font_size(size)
            ty = by0 - lh
            for text, c in lines:
                blf.color(0, *c)
                blf.position(0, x + pad, ty, 0)
                blf.draw(0, text)
                ty -= lh
            ready = sc >= 85
            blf.color(0, *(OK if ready else BAD))
            blf.position(0, x + pad, ty, 0)
            blf.draw(0, "● LISTO PARA SL" if ready else "● REVISAR ANTES DE SUBIR")
        _draw_labels(context, p, accent4)
        _draw_toast(context, shader, batch_for_shader, ui, accent, bg)
        gpu.state.blend_set("NONE")
    except Exception as exc:
        print("[SL Rigger] HUD:", exc)


def _draw_labels(context, p, accent4):
    if not p.show_labels:
        return
    obj = context.active_object
    arm = obj if is_sl_armature(obj) else (find_armature(obj) if obj is not None and obj.type == "MESH" else None)
    if not is_sl_armature(arm):
        return
    import blf
    from bpy_extras.view3d_utils import location_3d_to_region_2d
    region, rv3d = context.region, context.region_data
    _font_size(int(11 * context.preferences.system.ui_scale))
    for bone_name, text in LABELS.items():
        pb = arm.pose.bones.get(bone_name)
        if pb is None or pb.bone.hide:
            continue
        co = location_3d_to_region_2d(region, rv3d, arm.matrix_world @ pb.head)
        if co is None:
            continue
        deform = pb.bone.use_deform
        blf.color(0, *(accent4 if deform else (0.6, 0.65, 0.7, 0.55)))
        blf.position(0, co.x + 8, co.y + 4, 0)
        blf.draw(0, ("◆ " if deform else "◇ ") + text)


def _draw_toast(context, shader, batch_for_shader, ui, accent, bg):
    remaining = _toast["until"] - time.time()
    if remaining <= 0 or not _toast["text"]:
        return
    import blf
    alpha = min(1.0, remaining / 0.6)
    _font_size(int(14 * ui))
    w, h = blf.dimensions(0, _toast["text"])
    region = context.region
    pad = int(14 * ui)
    x = (region.width - w) / 2 - pad
    y = int(70 * ui)
    _rect(shader, batch_for_shader, x, y, x + w + pad * 2, y + h + pad * 2, (*bg, 0.85 * alpha))
    _rect(shader, batch_for_shader, x, y, x + w + pad * 2, y + h + pad * 2, (*accent, alpha), "LINE_LOOP")
    blf.color(0, 1.0, 1.0, 1.0, alpha)
    blf.position(0, x + pad, y + pad, 0)
    blf.draw(0, _toast["text"])


def _on_depsgraph(scene, depsgraph):
    if depsgraph.id_type_updated("MESH"):
        _cache["tick"] += 1


def register_handlers():
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)


def unregister_handlers():
    disable()
    if _on_depsgraph in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_on_depsgraph)
    if bpy.app.timers.is_registered(_toast_tick):
        bpy.app.timers.unregister(_toast_tick)


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
    wm = bpy.context.window_manager
    if wm is None:
        return
    for window in wm.windows:
        for area in window.screen.areas:
            if area.type == "VIEW_3D":
                area.tag_redraw()


class SLR_OT_toggle_hud(bpy.types.Operator):
    """Muestra u oculta el monitor HUD en el visor 3D"""
    bl_idname = "slr.toggle_hud"
    bl_label = "Monitor HUD"

    def execute(self, context):
        if is_enabled():
            disable()
        else:
            enable()
            toast("Monitor HUD activado")
        _redraw()
        return {"FINISHED"}


classes = (SLR_OT_toggle_hud,)

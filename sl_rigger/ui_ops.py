"""Operadores de interfaz: bienvenida, guía, atajos, aislar grupos, pintura de pesos, presets propios."""

import json
import os

import bpy

from . import edition, hud, prefs, skeleton

_session = {"welcomed": False}


# --------------------------------------------------------------------------- guía

def guide_steps(context):
    """[(texto, hecho, operador sugerido)] del flujo principal."""
    scene = context.scene
    meshes = [o for o in scene.objects if o.type == "MESH" and "sl_lod_of" not in o]
    rigs = [o for o in scene.objects if skeleton.is_sl_armature(o)]
    bound = [o for o in meshes if skeleton.is_sl_armature(skeleton.find_armature(o))]
    report = scene.slr_report
    validated = bool(report) and "ERROR|" not in report
    exported = bool(scene.get("slr_last_export"))
    return [
        ("Importa o modela tu malla", bool(meshes), None),
        ("Crea el esqueleto SL", bool(rigs), "slr.create_rig"),
        ("Vincula la malla (pesos)", bool(bound), "slr.wizard"),
        ("Valida sin errores", validated, "slr.validate"),
        ("Exporta y sube a SL", exported, "slr.export_dae"),
    ]


class SLR_OT_next_step(bpy.types.Operator):
    """Ejecuta el siguiente paso pendiente de la guía"""
    bl_idname = "slr.next_step"
    bl_label = "Siguiente paso"

    def execute(self, context):
        for text, done, op in guide_steps(context):
            if not done:
                if op is None:
                    self.report({"INFO"}, "Primero importa tu modelo: Archivo → Importar")
                    return {"CANCELLED"}
                mod, name = op.split(".")
                fn = getattr(getattr(bpy.ops, mod), name)
                if not fn.poll():
                    self.report({"WARNING"}, f"{text}: selecciona primero lo necesario")
                    return {"CANCELLED"}
                return fn("INVOKE_DEFAULT")
        hud.toast("¡Todo listo! Sube tu modelo a Second Life")
        self.report({"INFO"}, "Todos los pasos completados")
        return {"FINISHED"}


# --------------------------------------------------------------------------- bienvenida y atajos

class SLR_OT_welcome(bpy.types.Operator):
    """Bienvenida y guía rápida"""
    bl_idname = "slr.welcome"
    bl_label = "Bienvenido a SL Rigger"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=440)

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        row = box.row()
        row.alignment = "CENTER"
        row.label(text=f"SL RIGGER · {edition.EDITION_LABEL}", icon="OUTLINER_OB_ARMATURE")
        col = layout.column(align=True)
        for i, line in enumerate((
            "Selecciona tu malla y pulsa  ▶ Auto-rig en un clic",
            "Activa el Monitor HUD: verás la puntuación SL en vivo",
            "Pestaña Animación: poses, expresiones, cola, alas, caminar…",
            "Exporta .dae / .glb / .anim y súbelo a Second Life",
        ), 1):
            col.label(text=f"{i}.  {line}")
        layout.separator()
        row = layout.row(align=True)
        row.scale_y = 1.4
        row.operator("slr.wizard", icon="PLAY")
        row.operator("slr.cheatsheet", icon="EVENT_SHIFT")
        p = prefs.get(context)
        if hasattr(p, "bl_rna"):
            layout.prop(p, "show_welcome", text="Mostrar al iniciar Blender")

    def execute(self, context):
        return {"FINISHED"}


class SLR_OT_cheatsheet(bpy.types.Operator):
    """Atajos y trucos de SL Rigger"""
    bl_idname = "slr.cheatsheet"
    bl_label = "Atajos y trucos"

    def invoke(self, context, event):
        return context.window_manager.invoke_popup(self, width=460)

    def draw(self, context):
        col = self.layout.column(align=True)
        for keys, what in (
            ("Mayús+Alt+Q", "Menú radial principal"),
            ("Mayús+Alt+W", "Menú radial de animación"),
            ("Espacio", "Reproducir la animación generada"),
            ("F3 → «SL»", "Buscar cualquier herramienta de SL Rigger"),
            ("Ctrl+Z", "Deshacer cualquier operación"),
            ("Barra de estado", "Puntuación SL de la malla activa"),
        ):
            row = col.row()
            row.label(text=keys, icon="EVENT_SHIFT" if "Mayús" in keys else "DOT")
            row.label(text=what)
        col.separator()
        col.label(text="Truco: el mapa de pesos marca en rojo lo que SL rechazaría.", icon="INFO")

    def execute(self, context):
        return {"FINISHED"}


def schedule_welcome():
    if bpy.app.background or _session["welcomed"]:
        return

    def show():
        _session["welcomed"] = True
        try:
            if not prefs.get().show_welcome:
                return None
            wm = bpy.context.window_manager
            win = wm.windows[0] if wm and wm.windows else None
            if win is None:
                return None
            area = next((a for a in win.screen.areas if a.type == "VIEW_3D"), None)
            with bpy.context.temp_override(window=win, area=area):
                bpy.ops.slr.welcome("INVOKE_DEFAULT")
        except Exception as exc:
            print("[SL Rigger] bienvenida:", exc)
        return None

    bpy.app.timers.register(show, first_interval=1.5)


# --------------------------------------------------------------------------- esqueleto

def _active_rig(context):
    obj = context.active_object
    if skeleton.is_sl_armature(obj):
        return obj
    if obj is not None and obj.type == "MESH":
        arm = skeleton.find_armature(obj)
        if skeleton.is_sl_armature(arm):
            return arm
    return None


class _RigPoll:
    @classmethod
    def poll(cls, context):
        if _active_rig(context) is None:
            cls.poll_message_set("Selecciona un esqueleto SL o una malla vinculada")
            return False
        return True


class SLR_OT_isolate_group(_RigPoll, bpy.types.Operator):
    """Muestra solo los huesos de un grupo Bento (vuelve a pulsar «Mostrar todo» para restaurar)"""
    bl_idname = "slr.isolate_group"
    bl_label = "Aislar grupo"
    bl_options = {"REGISTER", "UNDO"}

    group: bpy.props.EnumProperty(items=[("BASE", "Cuerpo", "")] +
                                  [(k, v[0], "") for k, v in skeleton.DEFORM_GROUPS.items()] +
                                  [("ALL", "Mostrar todo", "")])

    def execute(self, context):
        arm = _active_rig(context)
        for b in arm.data.bones:
            if self.group == "ALL" or b.name not in skeleton.SL_INFO:
                b.hide = False
            else:
                b.hide = skeleton.group_key(b.name) != self.group
        return {"FINISHED"}


class SLR_OT_weight_paint(bpy.types.Operator):
    """Entra en Pintura de pesos con los ajustes recomendados para SL (auto-normalizar, ver ceros)"""
    bl_idname = "slr.weight_paint"
    bl_label = "Pintar pesos (modo SL)"
    bl_options = {"REGISTER", "UNDO"}

    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if obj is None or obj.type != "MESH" or not skeleton.is_sl_armature(skeleton.find_armature(obj)):
            cls.poll_message_set("Selecciona una malla vinculada a un esqueleto SL")
            return False
        return True

    def execute(self, context):
        obj = context.active_object
        arm = skeleton.find_armature(obj)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        for o in context.view_layer.objects:
            o.select_set(o in (obj, arm))
        context.view_layer.objects.active = obj
        bpy.ops.object.mode_set(mode="WEIGHT_PAINT")
        ts = context.scene.tool_settings
        ts.use_auto_normalize = True
        ts.vertex_group_user = "ACTIVE"
        if hasattr(ts, "use_multipaint"):
            ts.use_multipaint = False
        hud.toast("Pintura de pesos: Ctrl+clic en un hueso para elegirlo")
        return {"FINISHED"}


def _preset_dir():
    try:
        path = bpy.utils.extension_path_user(__package__, path="presets", create=True)
    except (AttributeError, ValueError):
        path = bpy.utils.user_resource("SCRIPTS", path=os.path.join("presets", "sl_rigger"), create=True)
    return path


def custom_presets():
    d = _preset_dir()
    return sorted(f[:-5] for f in os.listdir(d) if f.endswith(".json")) if os.path.isdir(d) else []


class SLR_OT_save_preset(_RigPoll, bpy.types.Operator):
    """Guarda las proporciones del esqueleto activo como preset propio (JSON, para reutilizar o compartir)"""
    bl_idname = "slr.save_preset"
    bl_label = "Guardar preset propio"

    name: bpy.props.StringProperty(name="Nombre", default="Mi avatar")

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        arm = _active_rig(context)
        rest = {b.name: skeleton.BLENDER_TO_SL.to_3x3() @ (arm.matrix_world @ b.head_local)
                for b in arm.data.bones if b.name in skeleton.SL_INFO}
        bones = {}
        for name, pos in rest.items():
            parent = skeleton.SL_INFO[name]["parent"]
            local = pos - rest[parent] if parent in rest else pos
            bones[name] = [round(v, 6) for v in local]
        deform = [k for k in skeleton.DEFORM_GROUPS
                  if any(b.use_deform for b in arm.data.bones
                         if b.name in skeleton.SL_INFO and skeleton.group_key(b.name) == k)]
        data = {"name": self.name, "format": "sl_rigger_preset/1", "bones": bones, "deform": deform}
        path = os.path.join(_preset_dir(), bpy.path.clean_name(self.name) + ".json")
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=1, ensure_ascii=False)
        hud.toast(f"Preset '{self.name}' guardado")
        self.report({"INFO"}, f"Preset guardado: {path}")
        return {"FINISHED"}


def _custom_items(self, context):
    items = [(n, n.replace("_", " "), "") for n in custom_presets()]
    _custom_items.cache = items or [("", "(no hay presets propios)", "")]
    return _custom_items.cache


class SLR_OT_load_preset(bpy.types.Operator):
    """Crea un esqueleto SL a partir de un preset propio guardado"""
    bl_idname = "slr.load_preset"
    bl_label = "Cargar preset propio"
    bl_property = "preset"

    preset: bpy.props.EnumProperty(name="Preset", items=_custom_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        if not self.preset:
            self.report({"ERROR"}, "Todavía no has guardado ningún preset propio")
            return {"CANCELLED"}
        path = os.path.join(_preset_dir(), self.preset + ".json")
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")
        arm = skeleton.create_sl_armature(context, name=f"SL_{data.get('name', self.preset)}",
                                          deform=data.get("deform", ["HANDS"]),
                                          custom_offsets={k: tuple(v) for k, v in data["bones"].items()})
        arm["sl_preset"] = data.get("name", self.preset)
        self.report({"INFO"}, f"Esqueleto creado desde '{self.preset}'")
        return {"FINISHED"}


class SLR_OT_scale_to_height(_RigPoll, bpy.types.Operator):
    """Escala el esqueleto para que el avatar mida exactamente la altura indicada"""
    bl_idname = "slr.scale_to_height"
    bl_label = "Escalar a altura"
    bl_options = {"REGISTER", "UNDO"}

    height: bpy.props.FloatProperty(name="Altura", default=1.80, min=0.2, max=20.0, unit="LENGTH")

    def execute(self, context):
        arm = _active_rig(context)
        h = rig_height(arm)
        if h <= 1e-4:
            return {"CANCELLED"}
        f = self.height / h
        arm.scale = tuple(s * f for s in arm.scale)
        context.view_layer.update()
        self.report({"INFO"}, f"Altura {rig_height(arm):.2f} m. Sube con 'Include joint positions'")
        return {"FINISHED"}


def rig_height(arm):
    bones = arm.data.bones
    mw = arm.matrix_world
    if "mSkull" not in bones:
        return 0.0
    low = min((mw @ b.head_local).z for b in bones if b.name in skeleton.SL_INFO
              and skeleton.SL_INFO[b.name]["kind"] == "bone")
    skull = (mw @ bones["mSkull"].head_local).z
    head_len = ((mw @ bones["mSkull"].head_local) - (mw @ bones["mHead"].head_local)).length
    return skull + head_len * 1.27 - low


classes = (SLR_OT_next_step, SLR_OT_welcome, SLR_OT_cheatsheet, SLR_OT_isolate_group, SLR_OT_weight_paint,
           SLR_OT_save_preset, SLR_OT_load_preset, SLR_OT_scale_to_height)

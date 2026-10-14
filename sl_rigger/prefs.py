"""Preferencias del add-on."""

import bpy

PACKAGE = __package__

THEMES = {
    "NEON": ("Neón cian", (0.0, 0.9, 1.0), (0.02, 0.04, 0.08)),
    "GOLD": ("Oro Founder", (1.0, 0.78, 0.25), (0.08, 0.06, 0.02)),
    "SYNTH": ("Synthwave", (1.0, 0.25, 0.85), (0.07, 0.02, 0.09)),
    "MATRIX": ("Matrix", (0.2, 1.0, 0.4), (0.01, 0.05, 0.02)),
}


class SLR_Preferences(bpy.types.AddonPreferences):
    bl_idname = PACKAGE

    hud_theme: bpy.props.EnumProperty(name="Tema del HUD", items=[(k, v[0], "") for k, v in THEMES.items()],
                                      default="NEON")
    hud_corner: bpy.props.EnumProperty(name="Posición del HUD", items=[
        ("TL", "Arriba izquierda", ""), ("TR", "Arriba derecha", ""),
        ("BL", "Abajo izquierda", ""), ("BR", "Abajo derecha", "")], default="TL")
    hud_scale: bpy.props.FloatProperty(name="Tamaño del HUD", default=1.0, min=0.6, max=2.0)
    hud_opacity: bpy.props.FloatProperty(name="Opacidad del fondo", default=0.78, min=0.2, max=1.0)
    show_labels: bpy.props.BoolProperty(name="Etiquetas de grupos Bento en el visor", default=True)
    show_statusbar: bpy.props.BoolProperty(name="Indicador en la barra de estado", default=True)
    show_header: bpy.props.BoolProperty(name="Chip SL en la cabecera del visor 3D", default=True)
    show_welcome: bpy.props.BoolProperty(name="Mostrar bienvenida al iniciar", default=True)
    show_tips: bpy.props.BoolProperty(name="Mostrar consejos en el panel", default=True)

    def draw(self, context):
        layout = self.layout
        col = layout.column(heading="HUD")
        col.prop(self, "hud_theme")
        col.prop(self, "hud_corner")
        col.prop(self, "hud_scale", slider=True)
        col.prop(self, "hud_opacity", slider=True)
        col.prop(self, "show_labels")
        col = layout.column(heading="Interfaz")
        col.prop(self, "show_statusbar")
        col.prop(self, "show_header")
        col.prop(self, "show_tips")
        col.prop(self, "show_welcome")
        layout.label(text="Atajos: Mayús+Alt+Q (menú principal) · Mayús+Alt+W (animación)", icon="EVENT_SHIFT")


class _Defaults:
    hud_theme = "NEON"
    hud_corner = "TL"
    hud_scale = 1.0
    hud_opacity = 0.78
    show_labels = True
    show_statusbar = True
    show_header = True
    show_welcome = True
    show_tips = True


def get(context=None):
    context = context or bpy.context
    addon = context.preferences.addons.get(PACKAGE)
    return addon.preferences if addon is not None and addon.preferences is not None else _Defaults()


def theme(context=None):
    return THEMES.get(get(context).hud_theme, THEMES["NEON"])


classes = (SLR_Preferences,)

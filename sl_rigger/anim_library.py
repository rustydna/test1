"""Biblioteca de poses y animaciones generadas para el esqueleto SL.

Todo se define con rotaciones locales en ejes SL (grados: X alabeo, Y cabeceo, Z giro)
para el lado izquierdo; el lado derecho se obtiene por simetría.
Los valores son puntos de partida pensados para verse bien y retocarse.
"""

import math

import bpy

from . import pose_engine as pe
from .skeleton import is_sl_armature, find_armature

FINGERS = ("Index", "Middle", "Ring", "Pinky")


def _hand(curl, spread=(0, 0, 0, 0), thumb=(0, 0, 0), straight=()):
    """Pose de mano izquierda: curl = (falange1, 2, 3) en grados hacia la palma."""
    out = {}
    for i, f in enumerate(FINGERS):
        c = (0, 0, 0) if f in straight else curl
        for j in (1, 2, 3):
            out[f"mHand{f}{j}Left"] = (-c[j - 1], 0.0, spread[i] if j == 1 else 0.0)
    tz, tx2, tx3 = thumb
    out["mHandThumb1Left"] = (-10.0, 0.0, -tz)
    out["mHandThumb2Left"] = (-tx2, 0.0, 0.0)
    out["mHandThumb3Left"] = (-tx3, 0.0, 0.0)
    return out


FIST = (85, 95, 60)
HAND_POSES = {
    "RELAX": ("Relajada", _hand((15, 20, 10), (-4, 0, 3, 6), (10, 10, 10))),
    "FIST": ("Puño", _hand(FIST, thumb=(35, 40, 40))),
    "POINT": ("Señalar", _hand(FIST, thumb=(35, 40, 40), straight=("Index",))),
    "PEACE": ("Paz / victoria", {**_hand(FIST, thumb=(35, 40, 40), straight=("Index", "Middle")),
                                 "mHandIndex1Left": (0, 0, -10), "mHandMiddle1Left": (0, 0, 8)}),
    "OK": ("OK", {**_hand((5, 5, 5), (-4, 0, 6, 12)), "mHandIndex1Left": (-40, 0, 0),
                  "mHandIndex2Left": (-50, 0, 0), "mHandIndex3Left": (-35, 0, 0),
                  "mHandThumb1Left": (-15, 0, -30), "mHandThumb2Left": (-20, 0, 0)}),
    "SPREAD": ("Abierta", _hand((0, 0, 0), (-12, 0, 8, 16))),
    "CLAW": ("Garra", _hand((30, 60, 50), (-10, 0, 8, 14), (20, 30, 30))),
    "THUMBS": ("Pulgar arriba", {**_hand(FIST), "mHandThumb1Left": (40, 0, 0),
                                 "mHandThumb2Left": (0, 0, 0), "mHandThumb3Left": (0, 0, 0)}),
}

# Expresiones: (rotaciones, desplazamientos en metros) del lado izquierdo + centro.
FACE_POSES = {
    "SMILE": ("Sonrisa", {}, {"mFaceLipCornerLeft": (0, 0.003, 0.004), "mFaceCheekUpperLeft": (0, 0, 0.002),
                             "mFaceLipLowerCenter": (0, 0, 0.001)}),
    "SURPRISE": ("Sorpresa", {"mFaceJaw": (0, 16, 0), "mFaceEyeLidUpperLeft": (0, -6, 0)},
                 {"mFaceEyebrowCenterLeft": (0, 0, 0.006), "mFaceEyebrowOuterLeft": (0, 0, 0.005),
                  "mFaceEyebrowInnerLeft": (0, 0, 0.005)}),
    "ANGRY": ("Enfado", {"mFaceEyeLidUpperLeft": (0, 8, 0)},
              {"mFaceEyebrowInnerLeft": (0, -0.003, -0.004), "mFaceEyebrowCenterLeft": (0, 0, -0.002),
               "mFaceLipCornerLeft": (0, 0, -0.003)}),
    "WINK": ("Guiño", {"mFaceEyeLidUpperLeft": (0, 35, 0), "mFaceEyeLidLowerLeft": (0, -10, 0)},
             {"mFaceLipCornerLeft": (0, 0.002, 0.003), "mFaceCheekUpperLeft": (0, 0, 0.003)}),
    "KISS": ("Beso", {}, {"mFaceLipUpperCenter": (0.004, 0, 0), "mFaceLipLowerCenter": (0.004, 0, 0),
                          "mFaceLipCornerLeft": (0.002, -0.004, 0)}),
    "SLEEP": ("Ojos cerrados", {"mFaceEyeLidUpperLeft": (0, 38, 0), "mFaceEyeLidLowerLeft": (0, -8, 0)}, {}),
    "OPEN": ("Boca abierta", {"mFaceJaw": (0, 14, 0)}, {}),
}
_CENTER_ONLY_WINK = {"WINK"}

BODY_POSES = {
    "TPOSE": ("T-pose", {}),
    "APOSE": ("A-pose", {"mShoulderLeft": (-45, 0, 0)}),
    "STAND": ("De pie relajado", {"mShoulderLeft": (-75, 0, 5), "mElbowLeft": (0, 0, -15),
                                  "mWristLeft": (-10, 0, 0), "mHipLeft": (3, 0, 0)}),
    "SIT": ("Sentado", {"mHipLeft": (0, -90, 0), "mKneeLeft": (0, 90, 0), "mShoulderLeft": (-70, 0, -15),
                        "mElbowLeft": (0, 0, -40), "mTorso": (0, 3, 0)}),
    "HERO": ("Héroe", {"mShoulderLeft": (-70, 0, 0), "mElbowLeft": (0, 0, -10), "mHipLeft": (8, 0, 0),
                       "mChest": (0, -5, 0), "mHead": (0, -4, 0)}),
    "WAVE": ("Saludo", {"mShoulderRight": (-60, 0, 0), "mElbowRight": (-80, 0, 0),
                        "mShoulderLeft": (-75, 0, 5), "mElbowLeft": (0, 0, -15)}),
}


def _rot_table(table, symmetric=True):
    rots = {}
    for name, (x, y, z) in table.items():
        rots[name] = pe.sl_euler(x, y, z)
        if symmetric and "Left" in name and pe.mirror_name(name) not in table:
            rots[pe.mirror_name(name)] = pe.sl_euler(-x, y, -z)
    return rots


def _off_table(table, symmetric=True):
    offs = {}
    for name, (x, y, z) in table.items():
        offs[name] = (x, y, z)
        if symmetric and "Left" in name and pe.mirror_name(name) not in table:
            offs[pe.mirror_name(name)] = (x, -y, z)
    return offs


def hand_pose(key, side="BOTH"):
    rots = _rot_table(HAND_POSES[key][1], symmetric=True)
    if side == "LEFT":
        rots = {k: v for k, v in rots.items() if "Left" in k}
    elif side == "RIGHT":
        rots = {k: v for k, v in rots.items() if "Right" in k}
    return rots


def face_pose(key):
    _, rots, offs = FACE_POSES[key]
    sym = key not in _CENTER_ONLY_WINK
    return _rot_table(rots, sym), _off_table(offs, sym)


def body_pose(key):
    return _rot_table(BODY_POSES[key][1], symmetric=key != "WAVE")


# --------------------------------------------------------------------------- animaciones generadas

def _wave(t, f, phase=0.0):
    return math.sin(2 * math.pi * (f * t) - phase)


def gen_tail(t):
    return {f"mTail{i}": (0, 4 * _wave(t, 0.5, i * 0.6), 9 * i * _wave(t, 1.0, i * 0.5)) for i in range(1, 7)}, {}


def gen_ears(t):
    c = t % 3.0
    twitch = math.sin(math.pi * min(c / 0.25, 1.0)) if c < 0.25 else 0.0
    rots = {"mFaceEar1Left": (-25 * twitch, 0, 6 * _wave(t, 1 / 3.0)), "mFaceEar2Left": (-15 * twitch, 0, 0)}
    return rots, {}


def gen_wings(t):
    s = _wave(t, 1.0)
    rots = {"mWing1Left": (35 * s, 0, 0), "mWing2Left": (20 * _wave(t, 1.0, 0.5), 0, 0),
            "mWing3Left": (15 * _wave(t, 1.0, 1.0), 0, 0), "mWing4Left": (10 * _wave(t, 1.0, 1.4), 0, 0)}
    return rots, {"mPelvis": (0, 0, 0.02 * s)}


def gen_breathe(t):
    s = _wave(t, 0.25)
    return {"mChest": (0, -2.0 * s, 0), "mNeck": (0, 1.5 * s, 0), "mCollarLeft": (2 * s, 0, 0),
            "mShoulderLeft": (-75, 0, 5), "mElbowLeft": (0, 0, -15)}, {}


def gen_blink(t):
    c = t % 4.0
    k = math.sin(math.pi * (c - 0.1) / 0.18) if 0.1 <= c <= 0.28 else 0.0
    return {"mFaceEyeLidUpperLeft": (0, 38 * k, 0), "mFaceEyeLidLowerLeft": (0, -8 * k, 0)}, {}


def gen_walk(t):
    s = _wave(t, 1.0)
    c = math.cos(2 * math.pi * t)
    lift_l = max(0.0, -c)
    lift_r = max(0.0, c)
    rots = {
        "mHipLeft": (0, -25 * s, 0), "mHipRight": (0, 25 * s, 0),
        "mKneeLeft": (0, 50 * lift_l, 0), "mKneeRight": (0, 50 * lift_r, 0),
        "mAnkleLeft": (0, -10 * lift_l, 0), "mAnkleRight": (0, -10 * lift_r, 0),
        "mShoulderLeft": (-75, 20 * s, 5), "mShoulderRight": (75, -20 * s, -5),
        "mElbowLeft": (0, 0, -20), "mElbowRight": (0, 0, 20),
        "mTorso": (0, 0, 4 * s), "mChest": (0, 0, -6 * s), "mPelvis": (0, 0, -4 * s),
    }
    return rots, {"mPelvis": (0, 0, 0.02 * abs(math.cos(2 * math.pi * t)) - 0.02)}


def gen_wave(t):
    rots = dict(BODY_POSES["WAVE"][1])
    rots["mElbowRight"] = (-80, 0, 25 * _wave(t, 1.5))
    rots["mWristRight"] = (0, 0, 10 * _wave(t, 1.5, 0.4))
    return rots, {}


def gen_dance(t):
    s = _wave(t, 1.0)
    up = 0.5 + 0.5 * _wave(t, 2.0)
    rots = {"mPelvis": (0, 0, 10 * s), "mTorso": (6 * s, 0, -6 * s), "mChest": (-4 * s, 0, -4 * s),
            "mShoulderLeft": (-20 - 50 * up, 0, 0), "mShoulderRight": (20 + 50 * (1 - up), 0, 0),
            "mElbowLeft": (0, 0, -60), "mElbowRight": (0, 0, 60), "mHead": (0, 5 * _wave(t, 2.0), 0),
            "mKneeLeft": (0, 15 * up, 0), "mKneeRight": (0, 15 * (1 - up), 0)}
    return rots, {"mPelvis": (0, 0.03 * s, -0.03 * up)}


def gen_stress(t):
    """Prueba de deformación: recorre posturas extremas (4 s)."""
    k = (t % 4.0) / 4.0
    seq = [
        {},
        {"mShoulderLeft": (80, 0, 0), "mElbowLeft": (0, 0, -60)},
        {"mShoulderLeft": (0, 0, -80), "mElbowLeft": (0, 0, -110)},
        {"mHipLeft": (0, -100, 0), "mKneeLeft": (0, 120, 0), "mTorso": (0, 25, 0)},
        {"mTorso": (0, 0, 35), "mChest": (0, 0, 25), "mNeck": (0, 0, 30), "mHead": (0, 20, 0)},
        {},
    ]
    i = min(int(k * (len(seq) - 1)), len(seq) - 2)
    u = k * (len(seq) - 1) - i
    u = u * u * (3 - 2 * u)
    a, b = seq[i], seq[i + 1]
    rots = {}
    for name in set(a) | set(b):
        va, vb = a.get(name, (0, 0, 0)), b.get(name, (0, 0, 0))
        rots[name] = tuple(x + (y - x) * u for x, y in zip(va, vb))
    return rots, {}


GENERATORS = {
    "TAIL": ("Cola que se menea", gen_tail, 2.0, True),
    "EARS": ("Orejas que se mueven", gen_ears, 3.0, True),
    "WINGS": ("Alas aleteando", gen_wings, 1.0, True),
    "BREATHE": ("Respiración (idle)", gen_breathe, 4.0, False),
    "BLINK": ("Parpadeo", gen_blink, 4.0, True),
    "WALK": ("Caminar (básico)", gen_walk, 1.0, False),
    "WAVE": ("Saludar", gen_wave, 2.0, False),
    "DANCE": ("Bailecito", gen_dance, 2.0, False),
    "STRESS": ("Prueba de deformación", gen_stress, 4.0, False),
}
_ASYMMETRIC = {"WALK", "WAVE", "DANCE", "STRESS"}


def bake_generator(context, arm, key, fps=None):
    label, fn, duration, _ = GENERATORS[key]
    scene = context.scene
    fps = fps or scene.render.fps / scene.render.fps_base
    frames = int(round(duration * fps))
    arm.animation_data_create()
    action = bpy.data.actions.new(f"SL_{label}")
    arm.animation_data.action = action
    pe.reset_pose(arm)
    names = set()
    sym = key not in _ASYMMETRIC
    for f in range(frames + 1):
        t = f / fps
        rots, offs = fn(t)
        r = _rot_table(rots, symmetric=True) if sym else {k: pe.sl_euler(*v) for k, v in rots.items()}
        o = _off_table(offs, symmetric=sym) if offs else {}
        r = {k: v for k, v in r.items() if k in arm.data.bones}
        o = {k: v for k, v in o.items() if k in arm.data.bones}
        pe.apply_pose(arm, local=r, offsets=o, keep_others=False)
        names |= set(r) | set(o)
        pe.key_pose(arm, scene.frame_start + f, names)
    scene.frame_end = scene.frame_start + frames
    return label, frames, sorted(names)


# --------------------------------------------------------------------------- operadores

def _target_rig(context):
    obj = context.active_object
    if is_sl_armature(obj):
        return obj
    if obj is not None and obj.type == "MESH":
        arm = find_armature(obj)
        if is_sl_armature(arm):
            return arm
    return None


class _RigOp:
    @classmethod
    def poll(cls, context):
        if _target_rig(context) is None:
            cls.poll_message_set("Selecciona un esqueleto SL o una malla vinculada a él")
            return False
        return True


def _items(table):
    return [(k, v[0], "") for k, v in table.items()]


class SLR_OT_hand_pose(_RigOp, bpy.types.Operator):
    """Aplica una pose de mano Bento (los dedos de la malla deben tener pesos en las manos Bento)"""
    bl_idname = "slr.hand_pose"
    bl_label = "Pose de mano"
    bl_options = {"REGISTER", "UNDO"}

    pose: bpy.props.EnumProperty(name="Pose", items=_items(HAND_POSES))
    side: bpy.props.EnumProperty(name="Mano", items=[("BOTH", "Ambas", ""), ("LEFT", "Izquierda", ""),
                                                     ("RIGHT", "Derecha", "")])
    key: bpy.props.BoolProperty(name="Insertar fotograma clave", default=True)

    def execute(self, context):
        arm = _target_rig(context)
        rots = {k: v for k, v in hand_pose(self.pose, self.side).items() if k in arm.data.bones}
        pe.apply_pose(arm, local=rots)
        if self.key:
            pe.key_pose(arm, context.scene.frame_current, rots)
        return {"FINISHED"}


class SLR_OT_face_pose(_RigOp, bpy.types.Operator):
    """Aplica una expresión facial Bento"""
    bl_idname = "slr.face_pose"
    bl_label = "Expresión facial"
    bl_options = {"REGISTER", "UNDO"}

    pose: bpy.props.EnumProperty(name="Expresión", items=_items(FACE_POSES))
    key: bpy.props.BoolProperty(name="Insertar fotograma clave", default=True)

    def execute(self, context):
        arm = _target_rig(context)
        rots, offs = face_pose(self.pose)
        rots = {k: v for k, v in rots.items() if k in arm.data.bones}
        offs = {k: v for k, v in offs.items() if k in arm.data.bones}
        pe.apply_pose(arm, local=rots, offsets=offs)
        if self.key:
            pe.key_pose(arm, context.scene.frame_current, set(rots) | set(offs))
        return {"FINISHED"}


class SLR_OT_body_pose(_RigOp, bpy.types.Operator):
    """Aplica una pose de cuerpo de partida"""
    bl_idname = "slr.body_pose"
    bl_label = "Pose de cuerpo"
    bl_options = {"REGISTER", "UNDO"}

    pose: bpy.props.EnumProperty(name="Pose", items=_items(BODY_POSES))
    key: bpy.props.BoolProperty(name="Insertar fotograma clave", default=True)

    def execute(self, context):
        arm = _target_rig(context)
        rots = body_pose(self.pose)
        pe.reset_pose(arm)
        pe.apply_pose(arm, local=rots)
        if self.key:
            pe.key_pose(arm, context.scene.frame_current, [b.name for b in arm.data.bones])
        return {"FINISHED"}


class SLR_OT_generate_anim(_RigOp, bpy.types.Operator):
    """Genera una animación lista para exportar a .anim"""
    bl_idname = "slr.generate_anim"
    bl_label = "Generar animación"
    bl_options = {"REGISTER", "UNDO"}

    kind: bpy.props.EnumProperty(name="Animación", items=[(k, v[0], "") for k, v in GENERATORS.items()])

    def execute(self, context):
        from . import hud
        arm = _target_rig(context)
        label, frames, names = bake_generator(context, arm, self.kind)
        missing = [n for n in names if n not in arm.data.bones]
        msg = f"'{label}': {frames} fotogramas, {len(names)} huesos. Reprodúcela con Espacio"
        hud.toast(msg)
        self.report({"INFO"}, msg + (f" (faltan {len(missing)} huesos)" if missing else ""))
        return {"FINISHED"}


class SLR_OT_mirror_pose(_RigOp, bpy.types.Operator):
    """Copia la pose de un lado al otro (izquierda → derecha o al revés)"""
    bl_idname = "slr.mirror_pose"
    bl_label = "Simetrizar pose"
    bl_options = {"REGISTER", "UNDO"}

    direction: bpy.props.EnumProperty(name="Dirección", items=[("L2R", "Izquierda → derecha", ""),
                                                               ("R2L", "Derecha → izquierda", "")])

    def execute(self, context):
        arm = _target_rig(context)
        src = "Left" if self.direction == "L2R" else "Right"
        sample = pe.sample(arm)
        rots = {}
        for name, (lrot, _, _, _) in sample.items():
            if src in name and pe.mirror_name(name) in arm.data.bones:
                rots[pe.mirror_name(name)] = pe.mirror_quat(lrot)
        pe.apply_pose(arm, local=rots)
        pe.key_pose(arm, context.scene.frame_current, rots)
        return {"FINISHED"}


class SLR_OT_reset_pose(_RigOp, bpy.types.Operator):
    """Vuelve a la pose de reposo de SL (T-pose)"""
    bl_idname = "slr.reset_pose"
    bl_label = "Pose de reposo"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        pe.reset_pose(_target_rig(context))
        return {"FINISHED"}


classes = (SLR_OT_hand_pose, SLR_OT_face_pose, SLR_OT_body_pose, SLR_OT_generate_anim,
           SLR_OT_mirror_pose, SLR_OT_reset_pose)

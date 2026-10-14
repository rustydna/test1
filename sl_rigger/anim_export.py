"""Exportador de animaciones .anim (formato nativo de Second Life, versión 1.0).

Formato verificado con LLKeyframeMotion::serialize del visor:
  U16 versión=1, U16 subversión=0, S32 prioridad, F32 duración, string emote,
  F32 loop_in, F32 loop_out, S32 loop, F32 ease_in, F32 ease_out, U32 hand_pose,
  U32 num_joints y, por articulación: string nombre, S32 prioridad,
  S32 n_rot + (U16 t, U16 x, U16 y, U16 z)…, S32 n_pos + (U16 t, U16 x, U16 y, U16 z)…;
  al final S32 num_constraints. Todo en little-endian.

Rotaciones: cuaternión local respecto al padre en ejes SL, w ≥ 0, xyz en [-1, 1].
Posiciones: mPelvis como desplazamiento respecto al reposo; el resto de huesos
(traslaciones Bento) como posición local absoluta = reposo oficial + desplazamiento.
"""

import struct

import bpy
from mathutils import Quaternion, Vector

from . import pose_engine
from .skeleton import SL_INFO

MAX_DURATION = 60.0
MAX_OFFSET = 5.0  # LL_MAX_PELVIS_OFFSET
U16MAX = 65535

HAND_POSES = [
    ("0", "Abierta (spread)", ""), ("1", "Relajada", ""), ("2", "Señalar", ""), ("3", "Puño", ""),
    ("4", "Relajada izq.", ""), ("5", "Señalar izq.", ""), ("6", "Puño izq.", ""),
    ("7", "Relajada der.", ""), ("8", "Señalar der.", ""), ("9", "Puño der.", ""),
    ("10", "Saludo militar der.", ""), ("11", "Escribiendo", ""), ("12", "Paz der.", ""), ("13", "Palma der.", ""),
]


def _u16(value, lower, upper):
    value = min(max(value, lower), upper)
    return int((value - lower) / (upper - lower) * U16MAX + 0.5)


def _q_vec(q):
    q = q.normalized()
    if q.w < 0:
        q = -q
    return q.x, q.y, q.z


def _pack_string(s):
    return s.encode("utf-8") + b"\x00"


def write_anim(path, joints, duration, priority=4, loop=False, loop_in=0.0, loop_out=None,
               ease_in=0.3, ease_out=0.3, hand_pose=0, emote=""):
    """joints: [(nombre, prioridad, [(t, Quaternion)], [(t, Vector)])]."""
    if duration <= 0.0:
        duration = 1.0 / 30.0
    loop_out = duration if loop_out is None else loop_out
    out = bytearray()
    out += struct.pack("<HHif", 1, 0, int(priority), float(duration))
    out += _pack_string(emote)
    out += struct.pack("<ffiffII", float(loop_in), float(loop_out), 1 if loop else 0,
                       float(ease_in), float(ease_out), int(hand_pose), len(joints))
    for name, prio, rots, poss in joints:
        out += _pack_string(name)
        out += struct.pack("<ii", int(prio), len(rots))
        for t, q in rots:
            x, y, z = _q_vec(q)
            out += struct.pack("<HHHH", _u16(t, 0.0, duration),
                               _u16(x, -1.0, 1.0), _u16(y, -1.0, 1.0), _u16(z, -1.0, 1.0))
        out += struct.pack("<i", len(poss))
        for t, p in poss:
            out += struct.pack("<HHHH", _u16(t, 0.0, duration), _u16(p.x, -MAX_OFFSET, MAX_OFFSET),
                               _u16(p.y, -MAX_OFFSET, MAX_OFFSET), _u16(p.z, -MAX_OFFSET, MAX_OFFSET))
    out += struct.pack("<i", 0)  # sin restricciones
    with open(path, "wb") as fh:
        fh.write(out)
    return len(out)


def read_anim(path):
    """Lee un .anim (para verificación y pruebas)."""
    data = open(path, "rb").read()
    o = 0

    def take(fmt):
        nonlocal o
        vals = struct.unpack_from(fmt, data, o)
        o += struct.calcsize(fmt)
        return vals

    def string():
        nonlocal o
        end = data.index(b"\x00", o)
        s = data[o:end].decode("utf-8")
        o = end + 1
        return s

    ver, sub, prio, dur = take("<HHif")
    emote = string()
    loop_in, loop_out, loop, ease_in, ease_out, hand, nj = take("<ffiffII")
    joints = {}
    for _ in range(nj):
        name = string()
        jprio, nrot = take("<ii")
        rots = [take("<HHHH") for _ in range(nrot)]
        (npos,) = take("<i")
        poss = [take("<HHHH") for _ in range(npos)]
        joints[name] = (jprio, rots, poss)
    (ncons,) = take("<i")
    return {"version": (ver, sub), "priority": prio, "duration": dur, "emote": emote, "loop": bool(loop),
            "loop_in": loop_in, "loop_out": loop_out, "ease": (ease_in, ease_out), "hand_pose": hand,
            "joints": joints, "constraints": ncons, "size": len(data), "consumed": o}


def _rot_close(a, b, tol=1e-4):
    return abs(a.dot(b)) > 1.0 - tol


def collect(context, arm, frame_start, frame_end, all_joints=False, translations=True, step=1):
    """Muestrea la animación del armature. Devuelve (joints, duración, avisos)."""
    scene = context.scene
    fps = scene.render.fps / scene.render.fps_base
    frames = list(range(frame_start, frame_end + 1, max(1, step)))
    if frames[-1] != frame_end:
        frames.append(frame_end)
    duration = max((frame_end - frame_start) / fps, 1.0 / fps)
    rest = pose_engine.rest_positions_sl(arm)
    old_frame = scene.frame_current
    tracks = {}
    wm = context.window_manager
    wm.progress_begin(0, len(frames))
    try:
        for i, f in enumerate(frames):
            scene.frame_set(f)
            t = (f - frame_start) / fps if len(frames) > 1 else 0.0
            for name, (lrot, wpos, _wrot, parent) in pose_engine.sample(arm).items():
                tr = tracks.setdefault(name, {"rot": [], "pos": [], "parent": parent})
                tr["rot"].append((t, lrot))
                if parent is None:
                    tr["pos"].append((t, wpos - rest[name]))
                else:
                    tr["pos"].append((t, wpos, parent))
            wm.progress_update(i)
    finally:
        wm.progress_end()
        scene.frame_set(old_frame)

    # Posiciones locales (para traslaciones Bento): necesitan la rotación de mundo del padre.
    warnings = []
    joints = []
    for name in [n for n in pose_engine_order(arm) if n in tracks]:
        tr = tracks[name]
        rots = tr["rot"]
        ident = all(_rot_close(q, Quaternion()) for _, q in rots)
        moving_rot = not all(_rot_close(q, rots[0][1]) for _, q in rots)
        pos_keys = []
        if translations:
            if tr["parent"] is None:
                deltas = [(t, d) for t, d in tr["pos"]]
                if any(d.length > 1e-4 for _, d in deltas):
                    pos_keys = deltas
            else:
                rest_local = Vector(SL_INFO[name]["pos"])
                rest_delta = rest[name] - rest[tr["parent"]]
                ptr = tracks[tr["parent"]]
                local_keys = []
                for k, (t, wpos, _parent) in enumerate(tr["pos"]):
                    p_wpos = ptr["pos"][k][1] if ptr["parent"] is not None else (rest[tr["parent"]] + ptr["pos"][k][1])
                    p_wrot = _world_rot_at(tracks, tr["parent"], k)
                    local = p_wrot.inverted() @ (wpos - p_wpos)
                    local_keys.append((t, local))
                if any((lp - rest_delta).length > 1e-4 for _, lp in local_keys):
                    pos_keys = [(t, rest_local + (lp - rest_delta)) for t, lp in local_keys]
        if not all_joints and ident and not pos_keys:
            continue
        if not moving_rot:
            rots = [rots[0]] if len(rots) == 1 else [rots[0], (rots[-1][0], rots[0][1])]
        joints.append((name, 4, rots, pos_keys))
        if any(abs(c) > MAX_OFFSET for _, p in pos_keys for c in p):
            warnings.append(f"{name}: desplazamiento mayor de {MAX_OFFSET} m (se recorta)")
    if duration > MAX_DURATION:
        warnings.append(f"Duración {duration:.1f} s: SL admite como máximo {MAX_DURATION:.0f} s")
    return joints, duration, warnings


def _world_rot_at(tracks, name, k):
    q = Quaternion()
    chain = []
    while name is not None:
        chain.append(name)
        name = tracks[name]["parent"]
    for n in reversed(chain):
        q = q @ tracks[n]["rot"][k][1]
    return q


def pose_engine_order(arm):
    return [b.name for b in pose_engine._hierarchy(arm)]


def export(context, arm, path, frame_start=None, frame_end=None, priority=4, loop=True,
           ease_in=0.3, ease_out=0.3, hand_pose=0, all_joints=False, translations=True, emote=""):
    scene = context.scene
    fs = scene.frame_start if frame_start is None else frame_start
    fe = scene.frame_end if frame_end is None else frame_end
    joints, duration, warnings = collect(context, arm, fs, fe, all_joints, translations)
    if not joints:
        raise ValueError("La animación no mueve ningún hueso SL")
    joints = [(n, priority, r, p) for n, _, r, p in joints]
    size = write_anim(path, joints, duration, priority=priority, loop=loop, loop_in=0.0, loop_out=duration,
                      ease_in=ease_in, ease_out=ease_out, hand_pose=hand_pose, emote=emote)
    return len(joints), duration, warnings


class SLR_OT_export_anim(bpy.types.Operator):
    """Exporta la animación (o la pose actual) del esqueleto SL a .anim, el formato nativo de Second Life"""
    bl_idname = "slr.export_anim"
    bl_label = "Exportar .anim"

    filepath: bpy.props.StringProperty(subtype="FILE_PATH")
    filter_glob: bpy.props.StringProperty(default="*.anim", options={"HIDDEN"})
    static_pose: bpy.props.BoolProperty(name="Pose estática", default=False,
                                        description="Solo el fotograma actual (para poses de sentarse, posar…)")
    priority: bpy.props.IntProperty(name="Prioridad", default=4, min=0, max=6,
                                    description="0–4 como el subidor de SL; 5–6 solo con .anim (Bento)")
    loop: bpy.props.BoolProperty(name="Bucle", default=True)
    ease_in: bpy.props.FloatProperty(name="Ease in (s)", default=0.3, min=0.0, max=10.0)
    ease_out: bpy.props.FloatProperty(name="Ease out (s)", default=0.3, min=0.0, max=10.0)
    hand_pose: bpy.props.EnumProperty(name="Mano (sistema)", items=HAND_POSES, default="0")
    all_joints: bpy.props.BoolProperty(name="Todas las articulaciones", default=False,
                                       description="Incluye también los huesos sin movimiento (anula otras animaciones)")
    translations: bpy.props.BoolProperty(name="Traslaciones", default=True,
                                         description="Exporta desplazamientos de pelvis y huesos Bento")

    @classmethod
    def poll(cls, context):
        from .skeleton import find_armature, is_sl_armature
        obj = context.active_object
        arm = obj if is_sl_armature(obj) else (find_armature(obj) if obj is not None and obj.type == "MESH" else None)
        if not is_sl_armature(arm):
            cls.poll_message_set("Selecciona el esqueleto SL (o una malla vinculada a él)")
            return False
        return True

    def invoke(self, context, event):
        if not self.filepath:
            name = "pose" if self.static_pose else "animacion"
            self.filepath = bpy.path.ensure_ext(bpy.path.abspath("//") + name, ".anim")
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        from . import hud
        from .skeleton import find_armature, is_sl_armature
        obj = context.active_object
        arm = obj if is_sl_armature(obj) else find_armature(obj)
        path = bpy.path.ensure_ext(self.filepath, ".anim")
        f = context.scene.frame_current
        fs, fe = (f, f) if self.static_pose else (None, None)
        try:
            n, dur, warns = export(context, arm, path, fs, fe, self.priority, self.loop, self.ease_in,
                                   self.ease_out, int(self.hand_pose), self.all_joints, self.translations)
        except ValueError as e:
            self.report({"ERROR"}, str(e))
            return {"CANCELLED"}
        for w in warns:
            self.report({"WARNING"}, w)
        context.scene["slr_last_export"] = path
        msg = f".anim listo: {n} articulaciones, {dur:.2f} s"
        hud.toast(msg)
        self.report({"INFO"}, msg)
        return {"FINISHED"}


classes = (SLR_OT_export_anim,)

"""Miniaturas de los presets: siluetas del esqueleto dibujadas al vuelo (sin archivos)."""

import bpy

from . import presets, skeleton

SIZE = 128
_pcoll = None
_items = []


def _render(preset_key, color=(0.0, 0.9, 1.0)):
    import numpy as np

    rows = skeleton.bone_table(preset_key)
    pos = skeleton.world_positions_sl(rows)
    kinds = skeleton.SL_INFO
    pts = {}
    for name, parent, _ in rows:
        if kinds[name]["kind"] != "bone":
            continue
        p = pos[name]
        pts[name] = (p.y * 0.92 - p.x * 0.38, p.z + p.x * 0.08)
    xs = [v[0] for v in pts.values()]
    ys = [v[1] for v in pts.values()]
    span = max(max(xs) - min(xs), max(ys) - min(ys) + 0.15, 1e-3)
    margin = 10
    scale = (SIZE - 2 * margin) / span
    cx = (max(xs) + min(xs)) / 2
    y0 = min(ys)

    def to_px(v):
        return (SIZE / 2 + (v[0] - cx) * scale, margin + (v[1] - y0) * scale)

    img = np.zeros((SIZE, SIZE, 4), dtype=np.float32)
    for r in range(SIZE):  # fondo degradado
        t = r / SIZE
        img[r, :, :3] = (0.02 + 0.03 * t, 0.04 + 0.04 * t, 0.08 + 0.08 * t)
        img[r, :, 3] = 1.0

    px, py, cols, rads = [], [], [], []

    def plot(x, y, c, rad=1.0):
        px.append(x)
        py.append(y)
        cols.append(c)
        rads.append(rad)

    for name, parent, _ in rows:
        if parent is None or name not in pts or parent not in pts:
            continue
        group = skeleton.group_key(name)
        c = color if group == "BASE" else (0.45, 0.55, 0.65) if group not in ("TAIL", "EARS", "WINGS") \
            else (1.0, 0.45, 0.85)
        (ax, ay), (bx, by) = to_px(pts[parent]), to_px(pts[name])
        steps = int(max(abs(bx - ax), abs(by - ay))) + 1
        for i in range(steps + 1):
            t = i / max(steps, 1)
            plot(ax + (bx - ax) * t, ay + (by - ay) * t, c, 1.0 if group == "BASE" else 0.5)
    for name in ("mHead", "mWristLeft", "mWristRight", "mAnkleLeft", "mAnkleRight", "mPelvis", "mChest"):
        if name in pts:
            x, y = to_px(pts[name])
            plot(x, y, (1.0, 1.0, 1.0), 2.0)
    px, py = np.array(px), np.array(py)
    cols, rads = np.array(cols, dtype=np.float32), np.array(rads)
    for dy in (-2, -1, 0, 1, 2):
        for dx in (-2, -1, 0, 1, 2):
            sel = (dx * dx + dy * dy) <= (rads * rads + 0.3)
            xi = np.round(px[sel] + dx).astype(int)
            yi = np.round(py[sel] + dy).astype(int)
            ok = (xi >= 0) & (xi < SIZE) & (yi >= 0) & (yi < SIZE)
            img[yi[ok], xi[ok], :3] = cols[sel][ok]
    return img


def _build():
    global _pcoll, _items
    import bpy.utils.previews
    if _pcoll is None:
        _pcoll = bpy.utils.previews.new()
    _items = []
    for i, (key, data) in enumerate(presets.PRESETS.items()):
        if key not in _pcoll:
            prev = _pcoll.new(key)
            pix = _render(key).ravel().tolist()
            prev.image_size = (SIZE, SIZE)
            prev.image_pixels_float = pix
            prev.icon_size = (SIZE, SIZE)
            prev.icon_pixels_float = pix
        h = _height(key)
        _items.append((key, f"{data['label']} · {h:.1f} m", data["description"], _pcoll[key].icon_id, i))


def _height(key):
    pos = skeleton.world_positions_sl(skeleton.bone_table(key))
    s = presets.PRESETS[key].get("scale", 1.0)
    return pos["mSkull"].z + 0.10 * s


def preset_items(self, context):
    if not _items:
        try:
            _build()
        except Exception as exc:  # sin miniaturas, pero el desplegable sigue funcionando
            print("[SL Rigger] miniaturas:", exc)
            return [(k, v["label"], v["description"], "ARMATURE_DATA", i)
                    for i, (k, v) in enumerate(presets.PRESETS.items())]
    return _items


def unregister():
    global _pcoll, _items
    if _pcoll is not None:
        bpy.utils.previews.remove(_pcoll)
    _pcoll = None
    _items = []

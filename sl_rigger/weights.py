"""Grupos de vértices: conversión de nombres, limpieza de pesos y validación."""

from . import mappings
from .skeleton import ALL_SL_BONE_NAMES, find_armature

SL_MAX_INFLUENCES = 4
SL_MAX_MATERIALS = 8
SL_MAX_TRIS_PER_MATERIAL = 21844
SL_MAX_VERTS_PER_MATERIAL = 65534
SL_MAX_DIMENSION = 64.0


def convert_vertex_groups(obj, preset_key=None):
    """Renombra/fusiona los grupos de vértices según el preset. Devuelve (preset, convertidos)."""
    names = [vg.name for vg in obj.vertex_groups]
    if preset_key in (None, "AUTO"):
        preset_key = mappings.detect_preset(names)
    if preset_key is None:
        return None, 0
    table = mappings.PRESETS[preset_key][1]

    # Acumular pesos por grupo SL de destino.
    targets = {}
    src_groups = []
    for vg in obj.vertex_groups:
        dst = table.get(mappings.normalize_name(vg.name))
        if dst and dst != vg.name:
            targets.setdefault(dst, {})
            src_groups.append((vg.index, dst))
    if not src_groups:
        return preset_key, 0

    src_index = dict(src_groups)
    for v in obj.data.vertices:
        for g in v.groups:
            dst = src_index.get(g.group)
            if dst and g.weight > 0.0:
                acc = targets[dst]
                acc[v.index] = acc.get(v.index, 0.0) + g.weight

    for idx in sorted(src_index, reverse=True):
        obj.vertex_groups.remove(obj.vertex_groups[idx])

    for dst, weights in targets.items():
        vg = obj.vertex_groups.get(dst) or obj.vertex_groups.new(name=dst)
        for vi, w in weights.items():
            vg.add([vi], min(w, 1.0), "ADD")
    return preset_key, len(src_index)


def clean_weights(obj, limit=SL_MAX_INFLUENCES, threshold=0.001, remove_non_sl=False):
    """Limita influencias por vértice, quita pesos ínfimos y normaliza. Devuelve vértices sin peso."""
    sl_idx = {vg.index for vg in obj.vertex_groups if vg.name in ALL_SL_BONE_NAMES}
    groups = obj.vertex_groups
    unweighted = 0
    for v in obj.data.vertices:
        infl = [(g.group, g.weight) for g in v.groups if g.group in sl_idx]
        keep = sorted((x for x in infl if x[1] > threshold), key=lambda x: -x[1])[:limit]
        total = sum(w for _, w in keep)
        keep_idx = {gi for gi, _ in keep}
        for gi, _ in infl:
            if gi not in keep_idx:
                groups[gi].remove([v.index])
        if total <= 0.0:
            unweighted += 1
            continue
        for gi, w in keep:
            groups[gi].add([v.index], w / total, "REPLACE")

    if remove_non_sl:
        for vg in reversed(list(obj.vertex_groups)):
            if vg.name not in ALL_SL_BONE_NAMES:
                obj.vertex_groups.remove(vg)
    return unweighted


def validate_object(obj):
    """Devuelve lista de (nivel, mensaje). Nivel: 'ERROR', 'WARNING' o 'INFO'."""
    out = []
    me = obj.data
    name = obj.name

    if len(obj.material_slots) > SL_MAX_MATERIALS:
        out.append(("ERROR", f"{name}: {len(obj.material_slots)} materiales (máximo {SL_MAX_MATERIALS})"))

    me.calc_loop_triangles()
    per_mat = {}
    for t in me.loop_triangles:
        per_mat[t.material_index] = per_mat.get(t.material_index, 0) + 1
    for mi, count in per_mat.items():
        if count > SL_MAX_TRIS_PER_MATERIAL:
            out.append(("WARNING", f"{name}: material {mi} tiene {count} triángulos "
                                   f"(SL lo divide a partir de {SL_MAX_TRIS_PER_MATERIAL})"))
    verts_per_mat = {}
    for p in me.polygons:
        verts_per_mat.setdefault(p.material_index, set()).update(p.vertices)
    for mi, vs in verts_per_mat.items():
        if len(vs) > SL_MAX_VERTS_PER_MATERIAL:
            out.append(("WARNING", f"{name}: material {mi} tiene {len(vs)} vértices "
                                   f"(SL lo divide a partir de {SL_MAX_VERTS_PER_MATERIAL})"))
    used = set(per_mat)
    for mi in range(len(obj.material_slots)):
        if mi not in used:
            out.append(("WARNING", f"{name}: el material {mi} no tiene caras asignadas"))

    if not me.uv_layers:
        out.append(("WARNING", f"{name}: no tiene mapa UV (no se podrán aplicar texturas)"))

    dims = obj.dimensions
    if max(dims) > SL_MAX_DIMENSION:
        out.append(("ERROR", f"{name}: mide {max(dims):.2f} m (máximo {SL_MAX_DIMENSION:.0f} m por eje)"))
    if any(abs(s - 1.0) > 1e-4 for s in obj.scale):
        out.append(("INFO", f"{name}: escala sin aplicar ({tuple(round(s, 3) for s in obj.scale)})"))

    arm = find_armature(obj)
    if arm is None:
        out.append(("INFO", f"{name}: sin armature → se exportará como objeto estático"))
        return out

    if "mPelvis" not in arm.data.bones:
        out.append(("ERROR", f"{name}: el armature '{arm.name}' no es un esqueleto de Second Life"))
    groups = obj.vertex_groups
    non_sl = [vg.name for vg in groups if vg.name not in ALL_SL_BONE_NAMES]
    if non_sl:
        out.append(("WARNING", f"{name}: grupos que no son huesos SL (se ignoran): {', '.join(non_sl[:8])}"
                               + (" …" if len(non_sl) > 8 else "")))
    missing = [vg.name for vg in groups if vg.name in ALL_SL_BONE_NAMES and vg.name not in arm.data.bones]
    if missing:
        out.append(("ERROR", f"{name}: el rig no tiene los huesos {', '.join(missing[:8])}"))

    sl_idx = {vg.index for vg in groups if vg.name in ALL_SL_BONE_NAMES}
    unweighted = too_many = 0
    for v in me.vertices:
        n = sum(1 for g in v.groups if g.group in sl_idx and g.weight > 0.0)
        if n == 0:
            unweighted += 1
        elif n > SL_MAX_INFLUENCES:
            too_many += 1
    if unweighted:
        out.append(("ERROR", f"{name}: {unweighted} vértices sin peso (SL rechaza la subida)"))
    if too_many:
        out.append(("WARNING", f"{name}: {too_many} vértices con más de {SL_MAX_INFLUENCES} huesos "
                               "(al exportar se conservan los 4 mayores)"))
    if not out or all(lvl == "INFO" for lvl, _ in out):
        out.append(("INFO", f"{name}: rigged OK ({len(me.vertices)} vértices)"))
    return out

"""Exportador Collada (.dae) propio, pensado para el subidor de mallas de Second Life.

No depende del exportador Collada de Blender (eliminado en versiones recientes).

Mallas rigged:
  * Vértices en coordenadas de mundo convertidas a ejes SL (frente +X).
  * bind_shape_matrix = identidad.
  * Las articulaciones solo llevan traslación (los huesos de SL no tienen
    rotación en la pose de reposo), y la matriz inversa de bind es la
    traslación inversa de cada articulación.
  * Máximo 4 influencias por vértice, normalizadas.
"""

import datetime
import re
from xml.sax.saxutils import quoteattr

from mathutils import Matrix, Vector

from .skeleton import ALL_SL_BONE_NAMES, BLENDER_TO_SL, find_armature
from .weights import SL_MAX_INFLUENCES


def _f(x):
    s = f"{x:.6f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def _floats(values):
    return " ".join(_f(v) for v in values)


def _matrix(m):
    return " ".join(_f(m[r][c]) for r in range(4) for c in range(4))


_ID_BAD = re.compile(r"[^A-Za-z0-9_.-]")


class _Ids:
    def __init__(self):
        self.used = set()

    def make(self, base):
        s = _ID_BAD.sub("_", base) or "id"
        if not s[0].isalpha() and s[0] != "_":
            s = "_" + s
        candidate, i = s, 1
        while candidate in self.used:
            i += 1
            candidate = f"{s}_{i}"
        self.used.add(candidate)
        return candidate


def _corner_normals(me):
    if hasattr(me, "corner_normals"):  # Blender 4.1+
        return [cn.vector for cn in me.corner_normals]
    me.calc_normals_split()
    return [loop.normal for loop in me.loops]


def _extract_mesh(obj, depsgraph, apply_modifiers, vert_matrix, joint_index):
    """Lee geometría (y pesos si joint_index no es None) de un objeto."""
    if apply_modifiers:
        src = obj.evaluated_get(depsgraph)
        me = src.to_mesh()
    else:
        src = obj
        me = obj.to_mesh()
    try:
        me.calc_loop_triangles()
        n_mat = vert_matrix.to_3x3().inverted_safe().transposed()

        positions = [vert_matrix @ v.co for v in me.vertices]

        normals, normal_idx, loop_n = [], {}, []
        for n in _corner_normals(me):
            nn = (n_mat @ n).normalized()
            key = (round(nn.x, 5), round(nn.y, 5), round(nn.z, 5))
            idx = normal_idx.get(key)
            if idx is None:
                idx = normal_idx[key] = len(normals)
                normals.append(key)
            loop_n.append(idx)

        uvs, uv_idx, loop_uv = [], {}, None
        uv_layer = me.uv_layers.active
        if uv_layer is not None:
            loop_uv = []
            for d in uv_layer.data:
                key = (round(d.uv.x, 6), round(d.uv.y, 6))
                idx = uv_idx.get(key)
                if idx is None:
                    idx = uv_idx[key] = len(uvs)
                    uvs.append(key)
                loop_uv.append(idx)

        tris = {}
        for t in me.loop_triangles:
            bucket = tris.setdefault(t.material_index, [])
            for li in t.loops:
                vi = me.loops[li].vertex_index
                bucket.append((vi, loop_n[li], loop_uv[li] if loop_uv is not None else None))

        weights = None
        unweighted = 0
        if joint_index is not None:
            group_to_joint = {}
            for vg in obj.vertex_groups:
                if vg.name in joint_index:
                    group_to_joint[vg.index] = joint_index[vg.name]
            weights = []
            pelvis = joint_index.get("mPelvis", 0)
            for v in me.vertices:
                acc = {}
                for g in v.groups:
                    j = group_to_joint.get(g.group)
                    if j is not None and g.weight > 0.0:
                        acc[j] = acc.get(j, 0.0) + g.weight
                top = sorted(acc.items(), key=lambda x: -x[1])[:SL_MAX_INFLUENCES]
                total = sum(w for _, w in top)
                if total <= 0.0:
                    unweighted += 1
                    top, total = [(pelvis, 1.0)], 1.0
                weights.append([(j, w / total) for j, w in top])

        return {
            "positions": positions,
            "normals": normals,
            "uvs": uvs,
            "has_uv": loop_uv is not None,
            "tris": tris,
            "weights": weights,
            "unweighted": unweighted,
        }
    finally:
        src.to_mesh_clear()


def _material_name(obj, index):
    if index < len(obj.material_slots) and obj.material_slots[index].material is not None:
        return obj.material_slots[index].material.name
    return f"{obj.name}_material_{index}"


def _material_color(obj, index):
    if index < len(obj.material_slots) and obj.material_slots[index].material is not None:
        c = obj.material_slots[index].material.diffuse_color
        return (c[0], c[1], c[2], c[3])
    return (0.8, 0.8, 0.8, 1.0)


def export(filepath, objects, depsgraph, apply_modifiers=True, rigged=None):
    """Exporta `objects` (mallas) a un .dae. Devuelve lista de avisos.

    rigged=None decide automáticamente: rigged si todas las mallas usan el mismo
    armature de Second Life.
    """
    warnings = []
    objects = [o for o in objects if o.type == "MESH"]
    if not objects:
        raise ValueError("No hay mallas para exportar")

    armatures = {find_armature(o) for o in objects}
    armature = next(iter(armatures)) if len(armatures) == 1 else None
    if armature is not None and "mPelvis" not in armature.data.bones:
        armature = None
    if rigged is None:
        rigged = armature is not None
    if rigged and armature is None:
        raise ValueError("Para exportar rigged todas las mallas deben usar el mismo armature de Second Life")

    ids = _Ids()
    joints, joint_index, joint_world, joint_parent = [], {}, {}, {}
    old_pose = None
    if rigged:
        bones = [b for b in armature.data.bones if b.name in ALL_SL_BONE_NAMES]
        for b in bones:
            joint_index[b.name] = len(joints)
            joints.append(b.name)
            joint_world[b.name] = BLENDER_TO_SL @ (armature.matrix_world @ b.head_local)
            p = b.parent
            while p is not None and p.name not in ALL_SL_BONE_NAMES:
                p = p.parent
            joint_parent[b.name] = p.name if p is not None else None
        for name in joints:
            ids.used.add(name)
        # La geometría debe leerse en la pose de reposo.
        old_pose = armature.data.pose_position
        armature.data.pose_position = "REST"
        depsgraph.update()

    try:
        meshes = []
        for obj in objects:
            if rigged:
                vm = BLENDER_TO_SL @ obj.matrix_world
                node_matrix = Matrix.Identity(4)
            else:
                vm = Matrix.Identity(4)
                node_matrix = obj.matrix_world.copy()
            data = _extract_mesh(obj, depsgraph, apply_modifiers, vm, joint_index if rigged else None)
            if data["unweighted"]:
                warnings.append(f"{obj.name}: {data['unweighted']} vértices sin peso asignados a mPelvis")
            if not data["tris"]:
                warnings.append(f"{obj.name}: no tiene caras, se omite")
                continue
            data["obj"] = obj
            data["node_matrix"] = node_matrix
            data["geom_id"] = ids.make(obj.name + "-mesh")
            data["node_id"] = ids.make(obj.name)
            data["skin_id"] = ids.make(obj.name + "-skin") if rigged else None
            meshes.append(data)
    finally:
        if old_pose is not None:
            armature.data.pose_position = old_pose
            depsgraph.update()

    if not meshes:
        raise ValueError("Ninguna malla tiene caras")

    # Materiales (compartidos por nombre).
    materials = {}
    for m in meshes:
        m["mat_ids"] = {}
        for mi in m["tris"]:
            name = _material_name(m["obj"], mi)
            if name not in materials:
                materials[name] = (ids.make(name + "-material"), ids.make(name + "-effect"),
                                   _material_color(m["obj"], mi))
            m["mat_ids"][mi] = (name, materials[name][0])

    x = []
    w = x.append
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    w('<?xml version="1.0" encoding="utf-8"?>')
    w('<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">')
    w("  <asset>")
    w("    <contributor><authoring_tool>SL Rigger for Blender</authoring_tool></contributor>")
    w(f"    <created>{now}</created><modified>{now}</modified>")
    w('    <unit name="meter" meter="1"/>')
    w("    <up_axis>Z_UP</up_axis>")
    w("  </asset>")

    w("  <library_effects>")
    for name, (mat_id, eff_id, col) in materials.items():
        w(f'    <effect id="{eff_id}"><profile_COMMON><technique sid="common"><phong>')
        w(f'      <diffuse><color sid="diffuse">{_floats(col)}</color></diffuse>')
        w("    </phong></technique></profile_COMMON></effect>")
    w("  </library_effects>")
    w("  <library_materials>")
    for name, (mat_id, eff_id, _) in materials.items():
        w(f'    <material id="{mat_id}" name={quoteattr(name)}><instance_effect url="#{eff_id}"/></material>')
    w("  </library_materials>")

    w("  <library_geometries>")
    for m in meshes:
        gid = m["geom_id"]
        pos = m["positions"]
        w(f'    <geometry id="{gid}" name={quoteattr(m["obj"].name)}><mesh>')
        w(f'      <source id="{gid}-positions"><float_array id="{gid}-positions-array" count="{len(pos) * 3}">'
          + _floats(c for p in pos for c in p) + "</float_array>")
        w(f'        <technique_common><accessor source="#{gid}-positions-array" count="{len(pos)}" stride="3">'
          '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
          "</accessor></technique_common></source>")
        nrm = m["normals"]
        w(f'      <source id="{gid}-normals"><float_array id="{gid}-normals-array" count="{len(nrm) * 3}">'
          + _floats(c for n in nrm for c in n) + "</float_array>")
        w(f'        <technique_common><accessor source="#{gid}-normals-array" count="{len(nrm)}" stride="3">'
          '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
          "</accessor></technique_common></source>")
        if m["has_uv"]:
            uv = m["uvs"]
            w(f'      <source id="{gid}-map"><float_array id="{gid}-map-array" count="{len(uv) * 2}">'
              + _floats(c for t in uv for c in t) + "</float_array>")
            w(f'        <technique_common><accessor source="#{gid}-map-array" count="{len(uv)}" stride="2">'
              '<param name="S" type="float"/><param name="T" type="float"/>'
              "</accessor></technique_common></source>")
        w(f'      <vertices id="{gid}-vertices"><input semantic="POSITION" source="#{gid}-positions"/></vertices>')
        for mi in sorted(m["tris"]):
            corners = m["tris"][mi]
            symbol = m["mat_ids"][mi][1]
            w(f'      <triangles material="{symbol}" count="{len(corners) // 3}">')
            w(f'        <input semantic="VERTEX" source="#{gid}-vertices" offset="0"/>')
            w(f'        <input semantic="NORMAL" source="#{gid}-normals" offset="1"/>')
            if m["has_uv"]:
                w(f'        <input semantic="TEXCOORD" source="#{gid}-map" offset="2" set="0"/>')
                p = " ".join(f"{a} {b} {c}" for a, b, c in corners)
            else:
                p = " ".join(f"{a} {b}" for a, b, _ in corners)
            w(f"        <p>{p}</p>")
            w("      </triangles>")
        w("    </mesh></geometry>")
    w("  </library_geometries>")

    if rigged:
        identity = _matrix(Matrix.Identity(4))
        names = " ".join(joints)
        inv_binds = " ".join(_matrix(Matrix.Translation(-joint_world[j])) for j in joints)
        w("  <library_controllers>")
        for m in meshes:
            sid = m["skin_id"]
            flat_w, vcount, v = [], [], []
            for infl in m["weights"]:
                vcount.append(str(len(infl)))
                for j, wt in infl:
                    v.append(f"{j} {len(flat_w)}")
                    flat_w.append(wt)
            w(f'    <controller id="{sid}" name={quoteattr(m["obj"].name)}><skin source="#{m["geom_id"]}">')
            w(f"      <bind_shape_matrix>{identity}</bind_shape_matrix>")
            w(f'      <source id="{sid}-joints"><Name_array id="{sid}-joints-array" count="{len(joints)}">'
              f"{names}</Name_array>")
            w(f'        <technique_common><accessor source="#{sid}-joints-array" count="{len(joints)}" stride="1">'
              '<param name="JOINT" type="name"/></accessor></technique_common></source>')
            w(f'      <source id="{sid}-bind_poses"><float_array id="{sid}-bind_poses-array" '
              f'count="{len(joints) * 16}">{inv_binds}</float_array>')
            w(f'        <technique_common><accessor source="#{sid}-bind_poses-array" count="{len(joints)}" '
              'stride="16"><param name="TRANSFORM" type="float4x4"/></accessor></technique_common></source>')
            w(f'      <source id="{sid}-weights"><float_array id="{sid}-weights-array" count="{len(flat_w)}">'
              + _floats(flat_w) + "</float_array>")
            w(f'        <technique_common><accessor source="#{sid}-weights-array" count="{len(flat_w)}" '
              'stride="1"><param name="WEIGHT" type="float"/></accessor></technique_common></source>')
            w(f'      <joints><input semantic="JOINT" source="#{sid}-joints"/>'
              f'<input semantic="INV_BIND_MATRIX" source="#{sid}-bind_poses"/></joints>')
            w(f'      <vertex_weights count="{len(m["weights"])}">')
            w(f'        <input semantic="JOINT" source="#{sid}-joints" offset="0"/>')
            w(f'        <input semantic="WEIGHT" source="#{sid}-weights" offset="1"/>')
            w(f"        <vcount>{' '.join(vcount)}</vcount>")
            w(f"        <v>{' '.join(v)}</v>")
            w("      </vertex_weights>")
            w("    </skin></controller>")
        w("  </library_controllers>")

    w('  <library_visual_scenes><visual_scene id="Scene" name="Scene">')

    def bind_material(m, indent):
        w(f"{indent}<bind_material><technique_common>")
        for mi in sorted(m["tris"]):
            name, mat_id = m["mat_ids"][mi]
            w(f'{indent}  <instance_material symbol="{mat_id}" target="#{mat_id}">'
              '<bind_vertex_input semantic="UVMap" input_semantic="TEXCOORD" input_set="0"/>'
              "</instance_material>")
        w(f"{indent}</technique_common></bind_material>")

    if rigged:
        children = {}
        for j in joints:
            children.setdefault(joint_parent[j], []).append(j)
        arm_id = ids.make(armature.name)

        def write_joint(j, indent):
            parent = joint_parent[j]
            local = joint_world[j] - (joint_world[parent] if parent else Vector((0.0, 0.0, 0.0)))
            w(f'{indent}<node id="{j}" name="{j}" sid="{j}" type="JOINT">')
            w(f'{indent}  <matrix sid="transform">{_matrix(Matrix.Translation(local))}</matrix>')
            for c in children.get(j, []):
                write_joint(c, indent + "  ")
            w(f"{indent}</node>")

        w(f'    <node id="{arm_id}" name={quoteattr(armature.name)} type="NODE">')
        w(f'      <matrix sid="transform">{identity}</matrix>')
        for root in children.get(None, []):
            write_joint(root, "      ")
        w("    </node>")
        roots = children.get(None, [])
        for m in meshes:
            w(f'    <node id="{m["node_id"]}" name={quoteattr(m["obj"].name)} type="NODE">')
            w(f'      <matrix sid="transform">{identity}</matrix>')
            w(f'      <instance_controller url="#{m["skin_id"]}">')
            for r in roots:
                w(f"        <skeleton>#{r}</skeleton>")
            bind_material(m, "        ")
            w("      </instance_controller>")
            w("    </node>")
    else:
        for m in meshes:
            w(f'    <node id="{m["node_id"]}" name={quoteattr(m["obj"].name)} type="NODE">')
            w(f'      <matrix sid="transform">{_matrix(m["node_matrix"])}</matrix>')
            w(f'      <instance_geometry url="#{m["geom_id"]}" name={quoteattr(m["obj"].name)}>')
            bind_material(m, "        ")
            w("      </instance_geometry>")
            w("    </node>")

    w("  </visual_scene></library_visual_scenes>")
    w('  <scene><instance_visual_scene url="#Scene"/></scene>')
    w("</COLLADA>")

    with open(filepath, "w", encoding="utf-8") as fh:
        fh.write("\n".join(x))
        fh.write("\n")
    return warnings

"""Exportador COLLADA 1.4.1 para mallas estáticas de Second Life.

* Metros, Z arriba.
* Cada objeto es un <node> con su traslación; los vértices van en espacio local.
* Normales por esquina (aristas duras respetadas) y UV por esquina.
* Un <triangles> por material, en el orden de los huecos de material del objeto,
  que en SL se convierte en el número de cara.
* Materiales Lambert de color plano, sin imágenes.
"""

import datetime
from xml.sax.saxutils import escape


def _f(x):
    s = f"{x:.5f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "", "-") else s


def _fl(values):
    return " ".join(_f(v) for v in values)


def _mesh_data(ob):
    me = ob.data
    me.calc_loop_triangles()
    cn = me.corner_normals
    uv = me.uv_layers[0].data if me.uv_layers else None
    pos = [tuple(v.co) for v in me.vertices]
    nidx, nlist = {}, []
    tidx, tlist = {}, []
    per_mat = {}
    for t in me.loop_triangles:
        tri = []
        for li in t.loops:
            n = tuple(round(c, 4) for c in cn[li].vector)
            if n not in nidx:
                nidx[n] = len(nlist)
                nlist.append(n)
            u = tuple(round(c, 5) for c in uv[li].uv) if uv else (0.0, 0.0)
            if u not in tidx:
                tidx[u] = len(tlist)
                tlist.append(u)
            tri.extend((me.loops[li].vertex_index, nidx[n], tidx[u]))
        per_mat.setdefault(t.material_index, []).append(tri)
    return pos, nlist, tlist, per_mat


def write_dae(path, objects):
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    mats = []
    for ob in objects:
        for m in ob.data.materials:
            if m and m.name not in mats:
                mats.append(m.name)
    out = ['<?xml version="1.0" encoding="utf-8"?>',
           '<COLLADA xmlns="http://www.collada.org/2005/11/COLLADASchema" version="1.4.1">',
           "<asset><contributor><authoring_tool>Foso V2 (Blender)</authoring_tool></contributor>",
           f"<created>{now}</created><modified>{now}</modified>",
           '<unit name="meter" meter="1"/><up_axis>Z_UP</up_axis></asset>',
           "<library_effects>"]
    for m in mats:
        mat = next(mm for ob in objects for mm in ob.data.materials if mm and mm.name == m)
        r, g, b, _ = mat.diffuse_color
        out.append(f'<effect id="{m}-effect"><profile_COMMON><technique sid="common"><lambert>'
                   f"<diffuse><color>{_fl((r, g, b, 1.0))}</color></diffuse></lambert></technique>"
                   f"</profile_COMMON></effect>")
    out.append("</library_effects><library_materials>")
    for m in mats:
        out.append(f'<material id="{m}-material" name="{m}"><instance_effect url="#{m}-effect"/></material>')
    out.append("</library_materials><library_geometries>")
    nodes = []
    for ob in objects:
        gid = f"{ob.name}-mesh"
        pos, nrm, tex, per_mat = _mesh_data(ob)
        out.append(f'<geometry id="{gid}" name="{escape(ob.name)}"><mesh>')
        out.append(f'<source id="{gid}-positions"><float_array id="{gid}-positions-array" count="{len(pos) * 3}">'
                   f"{_fl(c for p in pos for c in p)}</float_array><technique_common>"
                   f'<accessor source="#{gid}-positions-array" count="{len(pos)}" stride="3">'
                   '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
                   "</accessor></technique_common></source>")
        out.append(f'<source id="{gid}-normals"><float_array id="{gid}-normals-array" count="{len(nrm) * 3}">'
                   f"{_fl(c for p in nrm for c in p)}</float_array><technique_common>"
                   f'<accessor source="#{gid}-normals-array" count="{len(nrm)}" stride="3">'
                   '<param name="X" type="float"/><param name="Y" type="float"/><param name="Z" type="float"/>'
                   "</accessor></technique_common></source>")
        out.append(f'<source id="{gid}-map0"><float_array id="{gid}-map0-array" count="{len(tex) * 2}">'
                   f"{_fl(c for p in tex for c in p)}</float_array><technique_common>"
                   f'<accessor source="#{gid}-map0-array" count="{len(tex)}" stride="2">'
                   '<param name="S" type="float"/><param name="T" type="float"/>'
                   "</accessor></technique_common></source>")
        out.append(f'<vertices id="{gid}-vertices"><input semantic="POSITION" source="#{gid}-positions"/></vertices>')
        used = []
        for mi in sorted(per_mat):
            m = ob.data.materials[mi].name
            used.append(m)
            tris = per_mat[mi]
            out.append(f'<triangles material="{m}-material" count="{len(tris)}">'
                       f'<input semantic="VERTEX" source="#{gid}-vertices" offset="0"/>'
                       f'<input semantic="NORMAL" source="#{gid}-normals" offset="1"/>'
                       f'<input semantic="TEXCOORD" source="#{gid}-map0" offset="2" set="0"/>'
                       f"<p>{' '.join(str(i) for t in tris for i in t)}</p></triangles>")
        out.append("</mesh></geometry>")
        x, y, z = ob.matrix_basis.translation if ob.parent is None else ob.matrix_world.translation
        binds = "".join(f'<instance_material symbol="{m}-material" target="#{m}-material"/>' for m in used)
        nodes.append(f'<node id="{escape(ob.name)}" name="{escape(ob.name)}" type="NODE">'
                     f'<matrix sid="transform">1 0 0 {_f(x)} 0 1 0 {_f(y)} 0 0 1 {_f(z)} 0 0 0 1</matrix>'
                     f'<instance_geometry url="#{gid}" name="{escape(ob.name)}"><bind_material><technique_common>'
                     f"{binds}</technique_common></bind_material></instance_geometry></node>")
    out.append("</library_geometries>")
    out.append('<library_visual_scenes><visual_scene id="Scene" name="Scene">')
    out.extend(nodes)
    out.append('</visual_scene></library_visual_scenes><scene><instance_visual_scene url="#Scene"/></scene>')
    out.append("</COLLADA>")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out))

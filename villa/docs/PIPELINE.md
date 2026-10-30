# Villa — build pipeline (read before modelling anything)

Everything is generated in Python with Blender's `bpy` module (PyPI build, Blender 5.2, run with
plain `python3`). Nothing is modelled by hand, nothing uses Second Life prims.

## Files
| File | What it is |
|---|---|
| `villa/scripts/vmesh.py` | Organic mesh toolkit: `Shape` (a bmesh whose faces carry a material slot) and constructors. |
| `villa/scripts/vbuild.py` | Build engine: `@piece(...)` registry, LODs, physics, fixed 8 faces, DAE export per linkset, land impact (LI) estimate, report. |
| `villa/scripts/vrender.py` | Cycles beauty renders with the real PBR textures (`render(linksets, variants, views, ...)`). |
| `villa/scripts/furniture/reference.py` | Reference furniture piece (curved "Orbit" sofa): the quality bar. |
| `villa/scripts/vtextures.py` | PBR material library (textures + `.glb` materials + `docs/materials.json`). |
| `the_pit/scripts/collada_static.py` | Shared COLLADA writer (SL static mesh). |

## Material slots (fixed face numbers: SL sorts faces by material name)
`0 a_plaster · 1 b_floor · 2 c_wood · 3 d_stone · 4 e_fabric · 5 f_metal · 6 g_glass · 7 h_glow`;
the pool water piece has the single material `water`. The engine adds a tiny filler triangle for
every slot a piece lacks, so in Second Life **face N is slot N on every piece** (scripts can set a
material on `LINK_SET` face N in one call). Texture scale is world metres (box-mapped UVs):
`UV_TILE = a_plaster 2.0, b_floor 1.6, c_wood 1.2, d_stone 1.6, e_fabric 0.5, f_metal 1.0,
g_glass 2.0, h_glow 1.0, water 3.0` metres per repeat.

## vmesh toolkit (all units metres, Z up, 2D outlines CCW)
* 2D: `superellipse(cx,cy,a,b,n,e,rot)` (e 2.5–4 = soft "squircle"), `rounded_rect`, `arc`,
  `arc_poly(cx,cy,r0,r1,a0,a1,n,round_ends)` (annular sector), `catmull(points,n,closed)` (smooth
  spline through control points), `resample`, `offset2d`, `grow(poly,d)`, `soften(poly,r)`.
* Solids: `slab(poly,z0,z1,slot,r,seg,top_slot,side_slot)` (plate with rounded edges),
  `extrude`, `loft(rings,slot,...)`, `lathe(profile[(r,z)],slot,n)`, `sweep(path,radius,slot,n,
  closed,profile)` (tubes, handrails, piping, any closed profile along a 3D path),
  `wall_band(line,thickness,z0,z1,slot,closed)` (curved walls), `shell(outline,z0,height,slot,
  rings,power,thickness,inner_slot,open_top)` (domes/canopies/oculus), `blob` (superellipsoid),
  `rounded_box`, `box_cage` (cage only), `cushion`, `pillow(poly,z0,z1,slot,r,crown)` (tailored
  cushion from any outline), `piping`, `seam_line`, `tuft`, `panel`, `vpanel`, `curtain`.
* Shape ops: `join`, `move/rotate/scale/mirror/deform(fn)`, `smooth(levels)` (Catmull-Clark with
  creases: `crease(edges)`/`crease_sharp(angle)`), `solidify`, `boolean(cutter, op)` (EXACT),
  `weld`, `decimate(target)`, `slot_where(slot, test(center, normal))`, `bounds`, `tri_count`.

## Registering pieces
```python
import vbuild as B, vmesh as M
B.linkset("Dune", root="Dune_Floor", label="Dune House")
@B.piece("Dune", "Dune_Floor", kind="structure", phys="floor", li=6)
def dune_floor(lod):           # lod 0 = HIGH; return None for 1-3 to let the engine decimate
    if lod: return None
    return M.slab(outline, -0.3, 0.0, "d_stone", r=0.04, top_slot="b_floor")
```
`kind` ∈ structure, glass, door, furniture, light, deco, water, plant, core. `phys` ∈ `hull`
(convex hull of the LOWEST), `none` (walk through), `box`, `floor` (thin box at the top of the
bounding box: walkable floors), or a function returning `('box',mn,mx)` / `('hull',pts)` /
`('slab',poly,z0,z1)` items (e.g. stairs, curved walls as a few boxes). Extra keyword
arguments (`li=`, `seat=`, anything JSON-able) are stored in the report for the scripts.
One linkset = one DAE set `<Linkset>.dae` + `_LOD2/_LOD1/_LOD0/_PHYS.dae`; the root piece is
written first (SL makes the first object the root). Max 256 pieces per linkset.

## Land impact: how Second Life charges (use this when budgeting)
The engine reproduces the viewer's streaming cost. Each LOD is charged by the share of the
view it is shown in, which depends only on the piece's bounding-sphere radius r:

| radius | HIGH | MEDIUM | LOW | LOWEST | consequence |
|---|---|---|---|---|---|
| 0.5 m | 0.0001 | 0.002 | 0.006 | **0.99** | small furniture: HIGH is almost free, LOWEST must be tiny |
| 1.2 m | 0.0008 | 0.01 | 0.04 | **0.95** | same |
| 2.5 m | 0.003 | 0.05 | 0.16 | **0.79** | big sofas/beds: LOW and LOWEST matter |
| 10 m | 0.05 | **0.79** | 0.16 | ~0 | big shells/roofs: MEDIUM is what you pay |
| 20 m | 0.21 | **0.79** | ~0 | ~0 | huge pieces: HIGH and MEDIUM |

One triangle at full weight ≈ 0.04 LI. So: furniture and decor can have rich HIGH meshes
(5–15k triangles) for ~1 LI each; big structural pieces must keep MEDIUM lean (a few hundred
triangles) and should not be bigger than needed. `auto_lods` picks LOD targets per piece from
its `li=` target (defaults per kind) and replaces a LOWEST that will not decimate with a 14-point
convex impostor. Server cost is 0.5 LI per piece, so 256 pieces = 128 LI minimum: prefer fewer,
richer pieces (merge small decor into the furniture piece it sits on).

## Viewer LOD reality
At the default LOD factor a piece of radius r shows HIGH up to ~r/0.24 × factor metres
(r = 1 m → ~4–8 m). Furniture MEDIUM is therefore seen across a room: keep MEDIUM at
25–40 % of HIGH for furniture (the engine does), silhouettes intact.

## Running
```
python3 villa/scripts/build_villa.py            # every linkset: DAE + report (once it exists)
python3 villa/scripts/vrender.py Dune --views 4 # beauty renders in villa/output/renders/
```

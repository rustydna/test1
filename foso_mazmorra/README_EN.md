# The Pit (El Foso) — dungeon-kennel for Second Life (V2, new concept)

A dark medieval fantasy building for roleplay in Second Life, built **from scratch** from the brief
in the handoff (`docs/HANDOFF_EN.md`; Spanish original in `docs/HANDOFF_ES.md`). It does not reuse
V1 geometry. It is a new concept that keeps the requirements: eight large cells, bars, gates, chains
and ironwork modelled in 3D, no textures, and UVs ready for the owner's own textures.
Spanish user guide: `LEEME.md`.

## Concept

A **pit**: a long, narrow courtyard boxed in by 7.6 m walls, with the cells opening onto it like the
beast niches of an arena. You enter through a **fortified gatehouse** with two towers, a portcullis
and studded timber gates. At the far end, on a **dais**, the kennel master's great **brazier** burns
in front of a pointed niche. All light comes from fire: torches on every pier, cage lanterns hanging
from the beams, and the brazier. The cells stay in half-darkness.

* **Footprint:** 26.0 × 35.3 m = **918 m²** (45 % of the 2,023 m² parcel; limit 1,011.5 m²).
  Walls 7.6 m high, towers 10.6 m. The base goes 0.4 m below grade to hide uneven terrain.
* **8 cells**, 5.15 × 7.8 m clear (≈ 40 m²), four per wing. Each has a barrel vault with two
  transverse ribs (removable), a splayed arrow slit, a stone sleeping bench with a timber kerb, a
  straw heap, a stone trough, a stave bucket, gnawed bones, and a **chain of real interlocked links**
  hanging from a ring and ending in a collar on the floor.
* **Cell front:** a 3.8 m pointed arch with voussoirs, keystone, hood mould, imposts and alternating
  jamb quoins. A grille of round bars set into the stone, with an **openable door** of 1.4 × 2.6 m:
  braces, hinge knuckles on pintles, lock box and pull rings.
* **Courtyard:** 6 m wide, coursed irregular paving, a central drain with grates, five timber beams
  on stone corbels, three cage lanterns and ten torches.
* **Gatehouse:** battered towers with cross arrow loops, corbel table and a solid parapet (no toy
  battlements), a plain shield over the arch for the owner's emblem, a portcullis that rises inside
  the wall, and two studded timber leaves with ironwork on both faces.
* **Kennel master's hall:** a 0.9 m dais with a stair (side passages kept clear), a pointed niche
  with a smoke hood, a tripod brazier, wall rings with collars, hay bales and barrels.

## Files (`salida/`)

| File | Purpose |
|---|---|
| `Foso_V2.blend` | Editable source. Collections `MALLA \| HIGH`, `LOD \| MEDIUM/LOW/LOWEST`, `FISICA` |
| `Foso_V2_HIGH.dae` | Main model to upload |
| `Foso_V2_MEDIUM/LOW/LOWEST.dae` | LODs (object names `_LOD2`, `_LOD1`, `_LOD0`) |
| `Foso_V2_PHYS.dae` | Physics (boxes plus one ramp; names `_PHYS`) |
| `Informe_V2.json` | Per piece: size, triangles per level, radius, LOD weights, estimated LI |
| `QA_fisica.json`, `QA_fisica_mapa.png` | Walkability test |
| `Pruebas_V2.json` | Results of the 12 automated tests |
| `01…06_*.png` | Presentation renders |

## Uploading to Second Life

1. **Build → Upload → Model…** → `Foso_V2_HIGH.dae`.
2. **Level of Detail** tab: Medium, Low and Lowest → **Load from file** →
   `Foso_V2_MEDIUM.dae`, `Foso_V2_LOW.dae` and `Foso_V2_LOWEST.dae`. Do *not* use Generate.
3. **Physics** tab: Step 1 → **From file** → `Foso_V2_PHYS.dae`. **Do not click Analyze** or
   Simplify. The boxes are meant to stay a triangle mesh.
4. Upload options: scale 1.0, no textures.
5. **Calculate weights & fee** shows the real land impact. Write it down.
6. Rez it and drop **`lsl/foso_configurar.lsl`** into the root prim. It assigns the right physics
   shape type to all 126 pieces and lights the fires, then deletes itself.
7. Drop **`lsl/foso_puertas.lsl`** into the root. Touching a cell door, a gate leaf or the portcullis
   opens or closes it. The hinge comes from each piece's size, because SL re-centres meshes on their
   bounding box.
8. Optional: **`lsl/foso_fuego.lsl`** makes the lights flicker.
9. Check the physics with **Develop → Render Metadata → Physics Shapes**.

| Pieces | Physics shape | Why |
|---|---|---|
| walls, fronts, floors, vaults, towers, arches, dais, steps | **Prim** | Uses the uploaded physics, with its openings |
| `_Puerta`, `G_Hoja_O/E`, `G_Rastrillo` | **Convex Hull** | Moving slabs |
| grilles, chains, straw, troughs, beams, lanterns, torches, brazier, props | **None** | Decoration; the grille's collision lives in the `_Frente` piece |

A convex hull over a piece with an opening (an arched front, a cell) **closes the opening**. That is
the most likely cause of the V1 "can't enter the cells" problem, so structural pieces must be Prim.

## Physics checks

`scripts/qa_fisica.py` walks a 0.2 m grid with a 0.25 m-radius avatar (body from 0.35 to 1.9 m)
against exactly the exported physics boxes:

* Reachable from the outside stair: courtyard, both sides of the vestibule, all 8 cells, the dais
  and both wings of the hall → **all yes**.
* Places where visible stone can be walked through by ≥ 5 cm: **0**. Reachable points with no
  physical floor: **0**. Invisible walls next to walkable areas: 0.04 m² per tower (battered corner).

The test found these bugs during development, and all of them are fixed:

* Missing floor under the cell-door threshold. The avatar fell or tripped when entering, which
  matches the V1 report.
* The gate passage was narrowed by 30 cm per side.
* The hall wings could only be reached by jumping off the dais.
* The stair cheeks and tower batter had no physics.

**Not tested here:** there is no SL viewer in this environment. Confirm in-world with step 9.

## Land impact

**Estimate: ≈ 112 LI** (target 150). This comes from the viewer's streaming-cost formula with an
approximate compressed size, plus a server weight of 126 × 0.5 = 63. **It is an estimate, not a
measurement.** In SL, each LOD is weighted by the area over which it is visible, and that area
depends on the piece's radius: in large pieces LOW dominates (≈ 60 %), in small pieces LOWEST does
(≈ 90 %). So large pieces get rich HIGHs and minimal LOW/LOWEST levels, small pieces get a MEDIUM
close to their HIGH, and the expensive detail (grilles, chains, portcullis) sits in separate
small-radius pieces.

| Level | Objects | Triangles |
|---|---:|---:|
| HIGH | 126 | 100,365 |
| MEDIUM | 126 | 25,765 |
| LOW | 126 | 6,251 |
| LOWEST | 126 | 1,061 |
| PHYS | 126 | 2,818 |

## Textures and UVs

No textures or images. Named flat materials: `Llama` (flame, always **SL face 0** on fire pieces),
`Piedra` (stone), `Suelo` (floor/earth), `Madera` (wood), `Hierro` (iron), `Paja` (straw).
The UVs are world-space box mapping and repeat: 1 UV unit = 2 m for stone and floor, 1 m for wood
and straw, 0.5 m for iron. Tileable textures therefore line up across neighbouring pieces with the
same texel density everywhere. Adjust the scale in SL with repeats.

## Rebuild and test

```
pip install bpy   # or Blender 4.2+/5.x: blender -b --python ...
python foso_mazmorra/scripts/build_foso.py
python foso_mazmorra/tests/test_foso.py     # 12 tests, including walkability
python foso_mazmorra/scripts/render.py      # --fast for drafts
```

The whole design lives in `scripts/pieces.py`, with the key dimensions at the top. Random variation
(chain paths, straw, bones) uses fixed seeds and is identical across LODs.

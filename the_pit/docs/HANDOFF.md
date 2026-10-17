# HANDOFF — Pit of the Outcasts / dungeon-kennel for Second Life

**Date:** 14 October 2026.
**Status of this delivery:** visual version V1 approved by the user; collision and contact fixes pending.
**Purpose:** let another AI continue the project, reproduce the work and compare it with alternative proposals without losing the requirements.

> Translated from the Spanish original (`HANDOFF_ES.md`). Object names inside the Blender file are partly in French; they are kept verbatim.

## 1. What the user wants now

A dark medieval fantasy building, inspired by the atmosphere of Game of Thrones: a dungeon/kennel with large cells, convincing architecture, bars, heavy gates, chains and ironwork that are actually modelled. It is a consensual roleplay environment among friends in **Second Life**.

The user likes the current version: they said "I love it, it looks great". **Do not redesign it from scratch or change its architectural language without a reason.** They want to fix physics problems when walking or entering the cells, and some rings and pieces that appear to float.

Their immediate request is this detailed handoff, to compare the work of other AIs. After that they authorise continuing the fixes.

### Current constraints, in order of importance

1. **No textures.** The user wants to apply their own. Deliver geometry and usable UVs; neutral grey materials are fine.
2. **Bars, chains, rings and ironwork as 3D geometry.** Do not replace them with images with transparency.
3. Sober dungeon/kennel aesthetic; avoid a toy look, uniform blocks, children's-castle decoration or out-of-scale furniture.
4. **Target budget: 150 land impact (LI) in Second Life.** It was about 100 at first, but the user raised it to 150. The exact LI has not yet been verified by the assistant in a viewer.
5. Total land: **2,023 m²**. The build may occupy **at most half: 1,011.5 m²**.
6. Keep the eight-cell layout the user approved visually, unless an optimisation need justifies changing it.
7. Garments, if added, must be **exclusively male**. This requirement comes from an earlier phase and still applies to any new textile props.

## 2. How the brief evolved

- Initial request: a kennel for giant dogs, mastiff/fantasy-dinosaur type, with several cells, Game of Thrones aesthetic and textures.
- The use was asked about; at first the user selected real-world construction. Later they clarified the roleplay context and finally named the platform: **Second Life**. The current operational scope is the digital asset for SL.
- They wanted austerity, straw, apparent mud, neglect and discarded male garments.
- A first textured mock-up was produced, with eight 4 × 7 m pens. It is not the approved version to continue from.
- When the 100 LI limit appeared, a 96-native-prim variant was tried, with detail moved to textures and an LSL builder. **That approach was discarded.** Do not use its scripts or textures as a basis for the current work.
- The user rejected the previous look, calling it Playmobil. They explicitly ordered: **remove textures, deliver UVs and remake the mesh with a more serious look**.
- They raised the budget to 150 LI and gave the 2,023 m² of land and the maximum of half the parcel.
- The whole was rebuilt as arcade-and-vault architecture, with 3D bars and chains, and presented at human scale. This is the version they approved.

**Do not bring back the decisions of the 96-prim variant.** The current 65 mesh pieces are not equivalent to 65 LI either.

## 3. Approved delivery and main files

The current working folder is **`outputs/Foso_Mazmorra_UV_150/`**.

| File | Use |
|---|---|
| `Foso_Mazmorra_UV_150.blend` | Editable source, with HIGH, LODs, physics, cameras and lights |
| `Foso_HIGH.dae` | Main visual model to import |
| `Foso_MEDIUM.dae` | Medium level |
| `Foso_LOW.dae` | Low level |
| `Foso_LOWEST.dae` | Lowest level |
| `Foso_PHYS.dae` | Collision proxies |
| `UV_layouts/*.svg` | 65 UV templates of the HIGH |
| `01_Patio_sin_texturas.png` | Approved main perspective |
| `02_Detalle_cadenas.png` | Detail with fill light to read links and ironwork |
| `03_Vista_distribucion.png` | Overall view with vaults removed |
| `04_Planta_medidas.png` | Site plan |
| `LEEME.md` | User guide |
| `Verificacion.json` | Counts and constraints verified locally |
| `QA_exportacion.json` | Export report per piece and level |

The file `Foso_Mazmorra_UV_150.zip` contains the approved delivery. The handoff package includes a copy of that delivery and the scripts needed to study it.

The original folder may contain old renders with similar names, such as `03_Distribucion.png`, `04_Planta_672m2.png` or `02_Barrotes_y_cadenas.png`. **The names in the table identify the final views.**

## 4. Dimensions and organisation

- Blender and COLLADA units: **metres, 1:1 scale, Z up**.
- Outer footprint of the base: **24 × 28 m = 672 m²**.
- That is about **33.22 %** of the 2,023 m² parcel and stays below the 1,011.5 m² limit.
- The parcel is only known by its area; the shape of its boundaries is not available. The user must be able to orient or place the 24 × 28 m rectangle on their parcel.
- Eight cells, in two wings of four.
- Nominal size of each cell: **5 × 8 m**, 40 m² before subtracting interior details.
- Nominal clear central corridor: **4.8 m**.
- Longitudinal pitch between cell axes: **5.3 m**.
- Each front has a pointed arcade with a total opening about 3.6 m wide; the central operable leaf is about **1.4 × 2.6 m**, with fixed grilles at the sides and above.
- Individual removable vaults, for working on or viewing the interiors.
- Monumental entrance with two independent iron leaves and a pediment, without toy battlements.
- Top of the pediment: about **6.85 m** above zero. The foundation/base goes 0.38 m below zero; total vertical envelope about 7.23 m.

## 5. What is and is not modelled

### Modelled

- Continuous solid walls, partitions and low platforms at the back of the cells.
- Pointed arcades with jambs, two orders of mouldings/reveals and geometric voussoir pieces.
- Eight fixed-grille sets and eight independent cell leaves.
- Two entrance-gate leaves and two forecourt grilles.
- Volumetric bars, rails, simple bolts, hinges and pulls/rings.
- Eight hanging chains, with links alternating in perpendicular planes, a ring and an anchor plate.
- Vaults, central paving with geometric slabs and scattered planks.

### Not included in this version

- Textures, images, PBR maps, procedural materials or alpha grilles.
- Finished dogs/characters, rigging or animations.
- Working door scripts in SL.
- Dynamic simulation of chains, garments or bodies.
- Male garments or detailed straw as mesh in this UV revision. The earlier preference is kept as context if the props are expanded, but do not claim it is already implemented.
- A physical construction project, structural calculations or services.

## 6. Organisation of the Blender file

Main collections:

- **`MESH | HIGH – edit and texture`**: main model.
- **`LOD | MEDIUM`**, **`LOD | LOW`**, **`LOD | LOWEST`**: lower-detail versions, hidden in the main view.
- **`PHYSICS | simplified`**: proxies, also hidden.
- **PRESENTATION** collections: cameras, lights and labels. Do not export them as part of the asset.
- Inside HIGH there are sub-collections for vaults and near walls to make sections and working views easier.

Scenes:

1. `01 | Patio - arcadas y cadenas` (courtyard – arcades and chains): human-scale perspective, main view.
2. `02 | Coupe - distribution`: layout without vaults.
3. `03 | Fer et chaines`: iron/chain detail, with its own fill light.
4. `04 | Implantation 24 x 28 m`: labelled site plan.

Some internal names are in French because of decisions made by the generator; they do not imply new requirements.

Pieces carry an **`sl_name`** property that identifies their correspondence between HIGH, LODs and PHYS. Do not break it or reorder objects arbitrarily when exporting.

Piece convention:

- `A00_Fondation`: base.
- `A01_Dallage_central`: central paving.
- `A02_Arcade_fond`: back arcade.
- `A03_Portail_entree`, `A04_Fronton_entree`: entrance.
- For each cell `C01`–`C08`: `Murs_et_banquette` (walls and bench), `Arcade_pierre` (stone arcade), `Grille_fixe` (fixed grille), `Porte_pivot` (pivot door), `Chaine_et_ancrage` (chain and anchor), `Voute_amovible` (removable vault), `Planches_au_sol` (floor planks).
- `E1/E2_Porte_entree` (entrance door), `E3/E4_Grille_avant` (front grille): entrance/forecourt.

## 7. Materials and UVs

Piece materials are neutral categories: **stone, floor, iron and wood**. There is also a light material used by the presentation labels.

- There are no texture images in the Blender file and no image file references in the DAEs.
- Each HIGH piece has its own **UVMap 0–1** unwrap.
- The HIGH was unwrapped with Smart Project, 66° angle limit, island margin 0.018 and area weight 0.5.
- The 65 SVG templates describe the outlines of those UVs, one per piece. **They are not a global atlas of the whole building.**
- The final LODs are obtained by copying HIGH and simplifying its geometry with Decimate, keeping its UV data.
- Zero triangles with collapsed UVs and zero coordinates outside 0–1 were verified in all four visual levels.
- If ironwork contacts change, prefer moving existing components without repacking their UVs. If geometry is added, give it coherent UVs and document the change.

## 8. Final V1 counts

| Level | Mesh objects | Triangles |
|---|---:|---:|
| HIGH | 65 | 44,704 |
| MEDIUM | 65 | 9,874 |
| LOW | 65 | 4,980 |
| LOWEST | 65 | 4,288 |
| PHYS | 65 | 1,664 |

These are geometry figures, **not land impact results**. The silhouette of each visual LOD was fitted to the same bounding box as the HIGH, avoiding offsets or scale changes caused by Decimate.

## 9. COLLADA export and pitfalls already solved

Installed Blender: **5.2.1 LTS**, with Cycles and an NVIDIA RTX 5090 available. COLLADA export was solved with a custom Python exporter because this installation does not ship the old DAE exporter.

`work/export_collada_sl.py` provides:

`export_collada(objects, filepath, mode='HIGH')`

- COLLADA **1.4.1**, metre unit, `Z_UP`.
- Per-vertex positions; split normals and per-loop/corner UVs, preserving seams and hard edges.
- Separate `VERTEX`, `NORMAL`, `TEXCOORD` indices per triangle.
- Grey Lambert materials, no images.
- Modifiers must be applied before exporting.
- Matching by `sl_name`; adds the suffixes `_LOD2`, `_LOD1`, `_LOD0` and `_PHYS` on the corresponding levels.
- COLLADA matrices are serialised row by row. Do not transpose them by confusing this with the mathematical column-vector convention.
- **Real problem fixed:** PHYS objects in excluded collections could have a stale `matrix_world`, being exported 8–21 m off. For objects without parent or constraints, the exporter uses a copy of **`matrix_basis`**, which keeps the correct local transform. With parents/constraints it uses `matrix_world`.
- The depsgraph is also updated before levels are excluded.

The exporter passed **12 local tests**, including non-identity matrices, hierarchies/constraints, UV seams, hard normals, materials, LOD names and hidden-physics cache.

## 10. Validation performed and its limits

Checked locally on the files:

- The five DAEs are valid XML and have valid indices.
- 65 objects per level, with matching names and materials.
- Zero referenced images or textures.
- Zero geometrically degenerate triangles in the visual levels.
- Visual UVs within 0–1 and without collapses.
- Visual AABBs exactly matching HIGH.
- PHYS correctly placed after fixing the matrices.
- Actual outer footprint of 24 × 28 m.
- The final ZIP was opened and passed the integrity check.

**This does not prove correct collisions inside Second Life.** The user has already reported problems there when walking or entering the cells. The exact details of their import settings, Physics Shape Type, use of Analyze or applied scale are not yet available.

No real LI value from their viewer has been recorded either. Do not present "150 LI" as a guarantee nor "65 pieces" as land cost.

## 11. Pending problems, known and prioritised

### A. Collisions in Second Life — user report

Confirmed by the user: the problems appear **in Second Life when walking or entering the cells**. Audit the PHYS, its correspondence with each mesh, real openings, floor, platforms and the geometry of the leaves. Also review the importer options and the Physics Shape Type. Do not assume all problems are configuration, and do not claim they are fixed just because the XML is valid.

The current physics is simplified. Chains and planks are decorative and can be left with physics None once the build is assembled; frames and walls must allow passage through the openings. Do not wrap the whole building in a single convex hull that closes the interiors.

Closed leaves block passage by design; since there are no opening scripts, check whether the user is trying to walk through a door that is still closed. Ask precisely if needed, without dismissing other faults.

### B. Ironwork and floating details — report and preliminary findings

The user notices some rings and other pieces with no apparent support. Initial static audit of the generator:

- The chain plates are centred at `y=ystart+0.28`, thickness 0.08 m: their back sits at +0.24, while the partition wall reaches +0.15. **There is a gap of about 9 cm.**
- The rings of the two entrance gates lack a staple/plate visibly connecting them to the bars; gap about 4.9 cm.
- The first joint between the anchor ring and a link shows a minimum separation of about 2.3 cm in one direction: check the 3D intersection, not only the front projection.
- The mouldings of the side arcades are about 1 cm away from the stone: check the X centre and the depth of the profile.

These are concrete candidates for V2. Confirm them against the final Blender file before modifying; do not move a whole object if only a sub-component must move.

### C. Other points to keep/review

- Doors have a hinge origin in Blender, but SL may re-centre the mesh on its bounding box. **Do not promise a rotation script will work without adapting pivots.**
- The roof proxies are simplified boxes: their difference from the visual vault is deliberate, but check that they do not intrude into avatar space.
- Avoid needlessly increasing geometry/LI to fix a joint that can be solved by moving a plate or adding a small staple.

## 12. Sources and reproduction

Relevant scripts, included in the handoff package if available:

| Script | Function |
|---|---|
| `work/build_dungeon_uv.py` | Generates architecture, HIGH/LODs/PHYS, UVs, scenes, renders and DAE |
| `work/export_collada_sl.py` | Custom COLLADA exporter |
| `work/fix_lod_bounds.py` | Matches visual bounds and re-exports/saves the final revision |
| `work/finish_dungeon.py` | Adds detail light, renders final views and saves |
| `work/audit_dungeon.py` | Triangle and UV audit from the Blender file |
| `work/qa_collada_sl.py` | DAE audit of matching, UVs, indices, bounds and transforms |

The scripts compute `outputs/` from the parent directory of `work/`. To reproduce on another machine, keep that structure and adapt the path to the Blender executable. The delivered model already includes the later steps: there is no need to regenerate it to start fixing.

Recommended rebuild order:

1. Run `build_dungeon_uv.py` with Blender in the background; `-- --no-render` avoids repeating images.
2. Run `finish_dungeon.py` on the generated Blender file if the final views are needed. Wait for it to finish: it saves the file at the end.
3. **Then** run `fix_lod_bounds.py` on that file to save/export the final aligned LODs.
4. Audit UVs, matrices, matching and collisions before packaging.

Do not run two processes that save the same `.blend` at the same time: a race was detected and fixed where the render process could overwrite later LOD adjustments.

Primary technical sources consulted:

- [Mesh upload in Second Life](https://community.secondlife.com/knowledgebase/english/uploading-a-mesh-model-r274/).
- [Calculating land impact](https://community.secondlife.com/knowledgebase/english/calculating-land-impact-r273/).
- [Importer name-based matching](https://wiki.secondlife.com/wiki/Mesh_Import_test#Name_based_matching).
- [COLLADA 1.4.1 specification](https://www.khronos.org/files/collada_spec_1_4.pdf).

## 13. Brief ready to copy to another AI

> Continue the attached project of a medieval dungeon/kennel for Second Life. The architecture of the UV version is already approved by the user: keep its eight cells, arcades, bars, gates and chains. It must remain without textures, with usable UVs. The total land is 2,023 m² and the build may not occupy more than 1,011.5 m²; the current base measures 24 × 28 m = 672 m². The target budget is 150 LI, still without a real value documented from the viewer. The user has found physics problems when walking/entering cells in Second Life and some rings or details that visually float. Audit and fix those problems on a V2 copy without redesigning the approved architecture. Start with chain plates about 9 cm off the walls, the joint between ring and first link, gate rings without a staple, and mouldings detached from the stone. Review the PHYS and SL import options, without attributing the fault to a single cause in advance. Deliver Blender, coherent HIGH/MEDIUM/LOW/LOWEST/PHYS DAEs, UVs and a concrete comparison of changes and tests. Distinguish local checks from real tests in Second Life. Read the whole handoff before acting and keep V1 intact as a reference.

## 14. How to compare results between AIs

Compare on the same V1 and the same budget:

1. Architectural quality and proportion, keeping the style that was liked.
2. Real contacts of plates, rings, chains and ironwork, with close-ups.
3. Entry and circulation in SL with the physics used and documented settings.
4. LI **measured in the viewer**, at 1:1 scale, against the 150 target.
5. Useful UVs, without collapses, and coherent LODs.
6. Reproducible export, editable files and no texture dependencies.
7. Evidence of what was checked, what was not, and what visual or performance cost each fix had.

This document describes the **approved V1 before the new fixes**. Any later fix must be labelled V2 and come with its own change log.

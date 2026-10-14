# The Pit of the Levy (El Foso de la Leva): roleplay dungeon for Second Life (V3)

The prison beneath a pirate lord's fortress, where captives are broken and recruited as crew.
It has a moat-courtyard with a tidal seawater channel under drifting fog, seven punishment rooms,
and a single kennel cell where prisoners live as "dogs" among the soldiers' discarded underwear.
At the far end, on a dais, stands the throne from which the Lord of the Pit sees every cell.
All roleplay is consensual and between adults. Full Spanish guide: `LEEME.md`.

## Numbers

* **143 prims at rez** (limit 150). **Estimated land impact ≈ 119** (target 150; the viewer shows the real value).
* Footprint: 26 × 35.3 m = 917 m² (45 % of the 2,023 m² parcel).
* Triangles: HIGH 113,439 · MEDIUM 19,272 · LOW 3,814 · LOWEST 1,376 · PHYS 2,590. 13/13 automated tests pass.

## The V2 door problem, fixed by design

SL leaves mesh pieces with "Convex Hull" physics. The convex hull of an arched piece seals its
opening. In V2, walkability depended on a script switching every piece to "Prim", so if that
script did not run, the doors were sealed. In V3 **no piece's convex hull covers a passage**:
fronts are split into piers, arch heads and leaves, and props cluster against the walls.
`scripts/qa_fisica.py` verifies that every room, the dais and both hall wings are reachable **with
and without any script** (everything left in Convex Hull). `foso_nucleo` also recognises each piece
by size and position even if SL drops the names, sets fine physics, and ray-casts through every
door to report blockages in chat.

## Highlights

* **Living fire** (24 sources): layered particle flames centred on each flame base, plus breathing
  lights, crackles with sparks, gutters, and draughts that bend nearby flames when a door opens.
  The Lord picks one of four moods from the throne: Vigil, Gloom, Judgement and Darkness.
* **Fog** rising from the tidal channel, low mist in the kennel, steam over the cistern, and drips
  from the vaults. The **tide** moves the channel water up and down.
* **RP locks** on every door: open/close; lock (**only the avatar who locked it can unlock it**, plus
  the owner and the Lord on the throne); give a key; timed sentences; pick the lock on a d20; plead
  for mercy; rattle the bars. A floating **sentence board** lists who holds each key.
* **Rooms:**
  * **The Levy:** recruitment ledger with persistent numbering, and a branding brazier that counts marks.
  * **The Rack:** five tension levels.
  * **The Stocks:** pillory, foot stocks and a breaking wheel.
  * **The Cistern:** a ducking chair that actually lowers the seated avatar into salt water and
    times how long they stay under.
  * **The Kennel:** three named dog crates, leash rail, chains, collars and bowls, and piles of
    male underwear. The guards' laundry basket can dump them through a ceiling trapdoor.
  * **The Cages:** two gibbet cages that hoist the prisoner up and down; one holds an old skeleton.
  * **The Mast:** a whipping post with a lash counter and a salt barrel.
* **Other areas:**
  * **Guard room:** dice, mugs, a dagger in the table, a ship's anchor, and a key board.
  * **Gate:** portcullis winch with the levy bell.
  * **Lord's hall:** the throne (spiked crown, skull finials, ship's wheel), a kneeling stone, and
    "voices in the dark" ambient events.
* **Skeletons and skulls** throughout: hanged man in the courtyard, chained corpse, cage inhabitant,
  skulls on spikes and over the gate.

## PBR by blocks

Every piece has the same 8 faces in the same order: 0 Stone, 1 Floor, 2 Wood, 3 Iron,
4 Cloth/leather, 5 Bone, 6 Straw, 7 Flame. Water is in its own pieces. `lsl/foso_materiales.lsl`
reads a "materiales" notecard and applies each PBR material to all its faces across the build in one
touch. UVs are world-space box mapping, so tileable textures line up between pieces.

## Install

Upload `Foso_V3_HIGH.dae` with the MEDIUM, LOW and LOWEST files as LODs and `Foso_V3_PHYS.dae` as
physics (no Analyze), at scale 1.0. Then add the scripts from `lsl/` to the root in this order:

1. `foso_nucleo`
2. `foso_puertas`, `foso_fuego`, `foso_asientos`, `foso_salas`, `foso_trono`
3. 6–8 copies of `foso_pose`
4. optionally `foso_ambiente` and `foso_materiales`

Optional animations go in the root as `foso_<role>` (names listed in LEEME.md); built-in fallbacks
are used otherwise.

**Not verified here:** there is no SL viewer in this environment. The LSL scripts have not been
compiled in-world, and the land impact is an estimate.

# The Pit V4 — shared brief for everyone working on it

## What it is
"The Pit": a Second Life mesh build (143 prims, ~119 land impact, limit 150 LI / 150 prims) — the
prison under a pirate lord's sea fortress, for ADULT roleplay between consenting adults (dark
medieval/pirate theme; prisoners and garments are male). Prisoners spend a very long time in the
cells, so every surface must reward a close look. Read `the_pit/README.md` first.

Owner's brief for V4 (translated): *"Majestic but filthy, dark but full of information — those
contrasts. Every millimetre should tell a story with some detail. Refined, incredible, coherent
and creative. Make it usable and enjoyable in SL, as automated as possible, with the fewest
install steps."*

## Hard constraints
* Everything in English (names, text, comments).
* 143 prims; estimated land impact ≤ 140 (`python the_pit/scripts/check_story.py` prints it).
* Every piece keeps its EXACT bounding box (size and centre): details go INSIDE pieces. This keeps
  the LSL piece table valid and lets the owner's already-uploaded build use the new scripts.
* Materials: only the 8 block materials Stone, Floor, Wood, Iron, Cloth, Bone, Straw, Flame
  (and Water on the two water pieces). SL sorts faces by material name: in the English upload the
  faces are 0 Bone, 1 Cloth, 2 Flame, 3 Floor, 4 Iron, 5 Stone, 6 Straw, 7 Wood.
* Nothing may block a walkway or doorway (tests check walkability with and without scripts).
* Every feature must have an on/off switch (see `lsl/pit_control.lsl` FEATURES and `opt("name")`).
* LSL: Mono, 64 KB per script; every script must compile with lslint:
  `/tmp/claude-0/-home-user-test1/28d8f6b4-e75c-5d70-9e06-be15132804ef/scratchpad/lslint/lslint -m file.lsl`.
  Scripts sit in the ROOT prim; touches arrive with llDetectedLinkNumber; use the helper
  `piece(link)` for names (the root prim's piece name is in linkset data "root_piece").
* Don't commit; don't edit files you don't own (listed in your task). Several people work at once.

## Areas (piece name → area)
C01 The Press-Gang (recruitment office, scribe, branding) · C02 The Rack · C03 The Stocks ·
C04 The Cistern (ducking chair, salt water) · C05+C06 The Kennel (the only living cell: prisoners
live like dogs, three kennels, bowls, piles of dirty male underwear thrown in by guards) ·
C07 The Cages (two gibbet cages, one with an old skeleton) · C08 The Mast (whipping post from a
captured ship's mainmast) · YARD = P*, T*, A*, M* pieces (moat-yard with a sea-water channel,
tide, fog, a hanged man on a beam) · GATE = G_* (fortified gate, portcullis, winch, bell) ·
HALL = V_* (guardroom: dice table, key board / sentence board, laundry basket) ·
THRONE = N_* (the Lord's hall on a dais: throne, braziers, kneeling stone, banners, loot).

## Lore notecard format (`lsl/pit_lore.txt`, pasted in-world as notecard "pit_lore")
One record per line, fields separated by `|`, ASCII only, at most 250 bytes per line,
lines starting with `#` are comments. `{who}` = the acting avatar, `{target}` = the other one,
`{cell}` = the cell name.
```
EXAMINE|<area>|<block>|<text>          area: C01..C08, YARD, GATE, HALL, THRONE or ANY
                                       block: Stone, Floor, Wood, Iron, Cloth, Bone, Straw, Flame, Water or ANY
CARVING|<area>|<signed by>|<text>      graffiti left by past prisoners (players can add their own in-world)
NOTE|<piece name>|<title>|<text>       a document read by touching that exact piece (several lines = pages)
VOICE|<text>                           whispers in the dark (ambient, local chat)
BELL|<event>|<text>                    event: DAWN, RATIONS, ROLLCALL, LIGHTSOUT, HIGHTIDE
CHORE|<button>|<text>                  something a prisoner does in a cell (button ≤ 20 chars)
GUARD|<button>|<text>                  something a guard does to a cell or prisoner (button ≤ 20 chars)
```

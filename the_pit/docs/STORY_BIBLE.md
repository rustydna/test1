# The Pit: story bible (V4)

This is the canon for everyone working on The Pit: the 3D team placing story props
(`docs/story_props.json`), the writers of the in-world notecard (`lsl/pit_lore.txt`) and the script
writers. If a line of lore, a carving or a prop contradicts this file, this file wins. Change this
file first, then the others.

The Pit is a stage for **roleplay between consenting adults**. Every character in it, living or
dead, is an adult man. Everything below is fiction. See section 14.

---

## 1. The world in one paragraph

Three leagues off the harbour town of **Gullhaven**, across a strait of fog and fast water called the
**Narrows**, a black basalt stack rises out of the sea: the **Widow's Tooth**. On it the Crown built
**Fort Clemency**, a toll-fort and prison named for Saint Clement, patron of sailors, who was
drowned bound to an anchor. Under the fort, in the old quarry that gave it its stone, lies the
dungeon every sailor on the coast calls **the Pit**. Eleven years ago a pirate named **Lucan Drave**,
who had once been a prisoner in that same Pit, came back on the lowest tide of the year and took the
fort. He hanged the Governor from a beam in the yard, sat down on the bench where the Crown's judges
had sat, and made the Pit into what had been done to him: a **press-gang** fortress. Men are brought
up the Water Stair, written into the Book, broken in the punishment rooms and, in the end, branded
with the Lord's **Hook** and sent to sea. The few who will not choose live in the Kennel, like dogs.

The motto cut over the gate: **WHAT THE SEA GIVES, THE PIT KEEPS.**
The oath sworn on the Muster Book: **"My back to the lash, my blood to the sea, my life to the Lord of the Pit."**

---

## 2. Geography and the real geometry

The build is laid out along the Y axis (metres, from `output/Report.json`):

| World position | What it is in the story |
|---|---|
| y < -17 (G_Stairs) | **The Water Stair**: steps down to the sea landing. The Crown's Water Gate at its foot was smashed on the Night of the Ebb and never rebuilt. |
| y -18.3 .. -14.3, x -2 .. 2 (G_Arch, G_Tower_W/E, G_Portcullis, G_Leaf_W/E) | **The gate**: twin towers, the portcullis, the arms with the Ashby skulls. |
| y -15.2 .. -11.5 (V_*, G_Winch, G_Wall_W/E inner faces) | **The guardroom ("the Hall")**: the Watch, the key board, the Sentence Board, the dice table, the anchor, the laundry basket, the portcullis winch and the press-gang bell. |
| y -11.5 .. 11.5, x -3 .. 3 (P*, T*, A*, M*) | **The yard**: the Crown's drill yard, dug over the quarry, with the sea-water channel down its middle, five oak beams, the hanged Governor on the second beam (T1, y -5.75). |
| x < -3 (west row) | C01 **The Press-Gang** (y -8.6), C02 **The Rack** (y -2.9), C03 **The Stocks** (y 2.9), C04 **The Cistern** (y 8.6). |
| x > 3 (east row) | C05+C06 **The Kennel** (y -11.2 .. -0.3, one double room, two grilles), C07 **The Cages** (y 2.9), C08 **The Mast** (y 8.6). |
| y 11.5 .. 16 (N_*) | **The throne hall**: the Crown's old court hall. The dais, the throne, the kneeling stone, the braziers, banners and loot. The throne (N_Throne, y 14.4) faces down the whole yard to the gate: from it the Lord sees every grille. |

Each cell is 7.8 m deep (x 3.8 .. 11.6) and 5.15 m wide, under a stone barrel vault (a beamed roof
over the Kennel), lit by one barred arrow slit in the outer wall (z 2.3 .. 4.0) and one torch.
The outer wall faces the open sea; the slits show a strip of grey water and the gulls.

**Light wells.** Every vaulted cell (C01-C04, C07, C08) has a barred iron grate in the crown of its
vault, centred on the room: the top of a shaft the Crown cut up through the rock to the fort's
courtyard for air. At night the only white light in the Pit comes down these shafts as a column of
moonlight onto the middle of each cell floor (the build projects it from the vault centre). Prisoners
tell the time by where the moon square lies; the Mute reads the tide by its angle in the Cistern; in
the old chapel (C03) the Crown called the beam "the saint's finger"; Crake likes the moon on the bound
man's back at the Mast. Guards on the courtyard above sometimes spit, or drop crusts, down the wells.
The Kennel has no well: its light is the lantern and, on rest-days, the rag hatch.

The Widow's Tooth: black, wet, salt-sweating basalt. At the great spring ebbs a causeway of weed-slick
rocks shows for an hour on the seaward side, below the Cistern's culvert. Nobody uses it. One man did,
twice.

---

## 3. Fort Clemency under the Crown (before the Ebb)

* Built in the reign of **King Aldred** (whose name is still cast on the gate bell) by the Admiralty,
  as a toll-fort over the Narrows and a prison for mutineers, deserters, smugglers and pressed men
  waiting for a ship. The Crown pressed men too: the Pit was always a press-gang prison. The Lord only
  changed whose ships they were pressed for.
* The Crown's sign is the **red gull**: on its banners, its arms over the gate, the marines' buttons,
  even the candles. The Crown's property mark, cut into stores and burnt into deserters, is the
  **King's Arrow**.
* The last Governor, **Aldous Prynne**, was pious, punctual and cruel. He kept a pack of mastiffs
  (**Grip, Holdfast and Sorrow**) to hunt escapers across the rocks at low water. He sat as judge in the
  court hall at the head of the yard, on the dais where the throne now stands. Prisoners knelt on the
  **dock stone** (now the kneeling stone).
* The rooms under the Crown:

| Room | Under the Crown | Under the Lord |
|---|---|---|
| Gate | The Water Gate and the Water Stair, kept by the **Ashby brothers** for twenty years between them. | The only way in. The press-gang bell rings three strokes for fresh meat. |
| Guardroom | The Crown's guardroom. | The Watch's room: keys, the Sentence Board, dice, rum, debts. |
| Yard | The drill yard over the quarry; the Crown cut the channel ("the Flushing Cut") so the tide would scour the filth. | Same, plus the Governor on his beam. |
| C01 | **The Registry**: the Crown's clerk entered every prisoner. | **The Press-Gang**: the same clerk enters every recruit. |
| C02 | **The Question Room**: the Governor's questioner and his rack. | **The Rack**: for liars and the stubborn. |
| C03 | **The Chapel of Saint Clement**: altar, painted saint, starry vault, bell. | **The Stocks**: pillory over the altar, foot stocks, the wheel. |
| C04 | **The Cistern**: the fort's tank and the condemned cell; Crown prisoners waited for the rope standing knee-deep in salt water. The sea culvert opens into it. | **The Cistern**: salt water and the ducking chair. |
| C05+C06 | **The Governor's Kennel**: three kennels for the mastiffs, a hatch in the roof for their meat. | **The Kennel**: the only cell where men live. |
| C07 | **The Gibbet Store**: spare cages for Gallows Point, the headland where the Crown hung dead pirates for the gulls. | **The Cages**: the cages brought indoors, men inside. |
| C08 | **The Armoury and sail loft**. | **The Mast**: the Steadfast's mainmast as a whipping post. |
| Throne hall | **The Court Hall** (the Assize): the Governor's bench on the dais, the King's arms in the niche. | **The Lord's hall**: the throne on the bench, the ship's wheel in the niche where the arms were. |

---

## 4. The Lord of the Pit: Lucan Drave

**Who.** About forty-four. Lean, quiet, literate, grey at the temples, a sailor's hands. Dresses in black,
wears the dead Governor's gilt chain only on court nights, otherwise nothing that shines. Never raises
his voice: he speaks through the bell, the Book and the braziers. Keeps accounts. Forgets no number.
"A man is what is written of him."

**Names.** The Lord, the Lord of the Pit. Behind his back on the mainland: **the Drowned Man**. Inside
the Pit the word *drowned* is not said (Standing Order VI).

**Life.**

1. Born in Gullhaven. His father twisted hemp on **Absalom Reed's ropewalk**; Reed taught the boy his knots.
2. At nineteen he was taken by the Crown's press-gang in a Gullhaven tavern and put aboard the Crown
   frigate **Steadfast**. Flogged at her mainmast (forty lashes, for striking a midshipman). Deserted,
   was caught, branded with the **King's Arrow** on the left shoulder and sent to Fort Clemency to wait
   for the rope as **Crown prisoner No. 77**. The clerk who entered him was Tobias Wren.
3. He spent **forty-one days** standing in the Cistern's salt water. He scratched forty-one strokes, his
   initials and *I WILL COME BACK FOR THE KEY* on the outer wall above the tank (C04_Wall). On the
   forty-second night, the lowest ebb of the year, the culvert grate showed dry; he bent two bars and
   squeezed out to the rocks and swam the Narrows. The Wren wrote in the Crown register:
   *No. 77, L. Drave, drowned in the culvert, body not found.*
4. Twelve years of piracy. He took a Gullhaven salt-trader and renamed her the **Gallows Bride** ("the
   only bride a hanged man gets"). The Crown's posters rose from 200 to 500 crowns.
5. **The Night of the Ebb** (Year I, Day 1). On the lowest tide of the year he came back:
   * The **Gallows Bride**, fire-barrels in her hold, was run onto the Water Gate as the flood turned. The
     gate burned, the Bride broke her back on the rocks; he saved only her **wheel** (now in the throne
     niche, N_Back_C).
   * While the garrison ran to the fire, Drave and twenty men walked the exposed rocks to the culvert he
     had escaped through, came up in the Cistern and opened the Pit from inside.
   * **Ned and Will Ashby**, the Crown's gatekeepers, bribed with gold, raised the portcullis.
   * Three Crown marines held the chapel door and died there: **the Saint's Three** (their skulls lie
     at the foot of the wheel in C03).
   * **Governor Prynne** was taken at his own table in the court hall and hanged at dawn from the
     second beam of the yard. He still hangs there (P_Gibbet). The Watch greets him every morning.
   * The garrison of sixty was offered *the hook or the beam*. Forty-three took the hook. Sergeant
     Rook was the first marine to take it; his private, Bartholomew Crane, refused (see Old Fetch).
   * The Crown's hangman, **Hob Lacey**, was put in his own gibbet cage and hoisted in the Gibbet Store.
   * A week later the Ashbys came for double pay. The Lord paid them in full: a Crown coin in each mouth
     and a nail through each skull. Their skulls are on the gate arms.
   * Drave sat down on the Governor's bench. That night is **Year I, Day 1 of the Keeping**. It is now
     **Year XI**.
6. **The Hungry Winter** (Year I): a Crown squadron blockaded the Tooth for four months. The garrison ate
   the Governor's mastiffs. The kennelman asked for new dogs. The Lord gave him men.
7. **Year III**: the Steadfast, sent to retake the Tooth, was taken in fog in the Narrows. Her
   mainmast, the mast Drave had been flogged at, was cut down and stepped in the old armoury: the
   Mast. Her hull was re-masted and renamed the **Second Bride**: the Lord's flagship.
8. Since then: thirty-one prizes, the Crown's price at 1,000 crowns, a new Governor named by the Crown
   who has never dared take up his post (the noose on the middle beam is "kept for him").

**His marks.** On his own left shoulder the King's Arrow, with the Hook burnt over it by his own hand.
The number 77 is scratched under the throne's plinth: he sits on it. When any Book reaches number 77 the
Wren writes that man in red ink and the Lord comes down to see him.

**His sign.** A white **hook through a broken gilt crown**, on black. Banners in the throne hall, the
pennant on the last yard beam, the carving on the throne's back, the brand.

**His habits.** Holds court at **high tide** ("what is decided at the flood is not undone at the ebb").
Watches every grille through a spyglass from the throne. Never enters the Cistern, except on Ebb Night,
alone, without a torch. Orders the **Lord's weather**: WATCH, GLOOM, JUDGEMENT, DARKNESS (the moods of
the build).

---

## 5. Ships

| Ship | Story | Where in the Pit |
|---|---|---|
| **Gallows Bride** | The Lord's first ship, wrecked on the Water Gate on the Night of the Ebb. | Her wheel in the throne niche. |
| **Steadfast**, later **Second Bride** | Crown frigate, 32 guns. Drave was flogged at her mast as a young sailor. Taken in fog in Year III, re-masted, now the Lord's flagship, sailed by Hugh Ormond. | Her mainmast (C08), her block (C08 vault), her gilt stern letters upside down behind the throne, her men's initials on the fourth beam (T3), Ormond's carvings (C07, C08). |
| **Saint's Finger** | A Crown pearl-ship with a crew of divers, taken in Year IV. | Her pearls in the loot chest; one in Jory's hand (C04). |
| **Good Intent** | A Crown supply hulk, taken in Year V. | Her anchor in the guardroom; Oswin Tull was her purser's mate. |

Thirty-one prizes in all: five kept, nine burned, seventeen sold under false colours in Gullhaven.

---

## 6. The officers

| Name | Post | Nickname | Notes |
|---|---|---|---|
| **Tobias Wren** | Scribe, keeper of the Muster Book | the Wren | Crown Register Clerk for twenty years before the Ebb. Wrote "No. 77 drowned". The Lord spared him: *"You were wrong once. Never be wrong again."* Cracked spectacles, ink-black fingers, a round fine hand, never looks up. Wrote the Rules of the Book and the Standing Orders. His under-clerk is Matthias Kemble. |
| **Abel Kettering** | Quartermaster | the Purse | One eye. Former purser of the Steadfast (took the hook in Year III). Weighs bread, counts spoons, bowls, rum, coins and men. Keeps the loot chest. "A dog eats from the bowl, a man from the spoon." |
| **Gideon Hask** | Jailer, keeper of the eight keys | Old Keys | The Crown's turnkey; the first man of the garrison to take the hook ("I keep the keys, whoever keeps me"). Chalks the Sentence Board. Counts prisoners' tallies against it. Whistles *The Widow's Tooth*. Apprentice: Garrett Vole. |
| **Merrick Sallow** | Branding Master | the Smith | A Gullhaven farrier who came over of his own will in Year II. Brands men "like horses, neat and quick", hums hymns, tests each iron on his apron, quenches every brand in brine. |
| **Silas Crake** | Bosun, Master of the Mast | | Bosun's mate of the Steadfast. Three cats: **Mercy** (first dozen), **Margery** (second), **the Widow** (the rest). Salts every back: "an old ship's custom, and a kindness". Keeps the lash book. |
| **Fenwick Dunne** | Kennelman | | Kept the Governor's mastiffs for fifteen years. After the Hungry Winter he was given men instead. Names his dogs, collars them, talks to them gently, never strikes. Two-note whistle. |
| **Ambrose** | Tidewarden, Master of the Cistern | the Mute | The Governor had his tongue cut out for laughing in chapel. Reads the tides better than any almanac, chalks them on the tide slate, counts time under water with knots on a cord. Raises his hand to raise the chair. |
| **Edwin Rook** | Sergeant, Captain of the Watch | | The Crown's marine sergeant who took the hook first. Dice champion and a bad loser; lost his sword at the table. Old Fetch never spoke to him again. |
| **Hugh Ormond** | Sailing Master of the Second Bride | the Lieutenant | Former prisoner (see 9). |

**The Watch** (guards): Dace (young, laughs too much), Mull (fat, sleepy, not unkind), Pell Hollis,
Bram Tolley, Little Orrin (the biggest man in the Pit), Jem Ketch, and the newest, Kit Fennick.

---

## 7. The Watch: habits and customs

* **Greet the Governor.** Every guard touches his cap to the hanged man when he passes under him at
  dawn: "Morning, Governor." It is Standing Order III.
* **Touch the anchor.** Before going on watch every guard touches the shank of the Good Intent's anchor
  in the guardroom; it is worn bright at hand height.
* **Keys before dice.** The eight keys go back on their hooks before the dice come out.
* **The Lord's Due.** A dagger is stuck in the guard table. Whoever loses the last throw of the night puts
  his stake under it. Nobody touches the Due; on Ebb Night it goes to the loot chest.
* **Hazard.** Two bone dice. Seven or eleven takes the pot. On Ebb Night a double six frees one
  prisoner, if the Lord allows it.
* **Never sit on the dais steps**, drunk or sober. Never say *drowned*.
* **Count the tallies.** Prisoners' strokes on the walls are checked against the Sentence Board at roll
  call. "A stroke too many is a lie; a stroke too few is a dream."
* **Rest-day rags.** On rest-days the laundry basket (the Watch's own dirty breeches, shirts and
  loincloths, plus the clothes stripped from new men) is emptied through the hatch in the Kennel roof.
* **Bets on the Cistern.** The wager slate in the guardroom asks HOW LONG UNDER?
* **Toast**: "To the Lord of the Pit, and to fresh meat!"
* They spit in the channel for luck, and they never carve the walls: only the table.

---

## 8. The press-gang system and the life of a prisoner

All unbranded prisoners **live in the Kennel**. The other rooms are where they are taken to be broken,
by sentence, and from which they are brought back. That is why the Kennel is the only living cell.

1. **Taken.** Men come from captured ships, Crown patrols, Gullhaven taverns (the tavern-keepers are
   paid a crown a head, two for a seaman, nothing for a drunk who cannot stand), debtors sold by their
   creditors, and the odd fool who walks up the Water Stair to volunteer.
2. **The Water Stair.** Hooded, roped together, landed at slack tide. **Three strokes of the bell**: fresh
   meat. Thirty-seven turns of the winch raise the portcullis. In the passage they are made to look up
   at the Ashby skulls.
3. **The guardroom.** Stripped on the square cut in the floor (STRIP HERE). Their clothes go into the
   laundry basket, and from there, in time, to the dogs. Searched. Possessions to the Quartermaster.
4. **Under the Governor.** Walked up the yard under the hanged man. The wise ones bow.
5. **The Press-Gang (C01).** Measured against the wall in hands. The Wren enters each man in the
   **Muster Book**: number, name (or NAMELESS), height, marks and scars, trade, ship, how taken. Given a
   canvas shirt and breeches from the chest. Offered **the Choice**: **H** (the Hook) or **P** (the Pit).
6. **Presented.** At the next high tide he is tied to the waiting ring on the last pier, then made to
   kneel on the kneeling stone before the throne. The Lord assigns his breaking "by what a man is":
   * liars and the stubborn to **the Rack** (C02);
   * the proud to **the Stocks** (C03);
   * the loud and the swimmers to **the Cistern** (C04);
   * climbers and runners to **the Cages** (C07);
   * sailors and mutineers to **the Mast** (C08);
   * and every man who will not yet choose to **the Kennel** (C05/C06), as a dog, with a collar and a
     name the kennelman gives him.
7. **The days.** Sentences are entered in days on the Sentence Board in the guardroom and struck off at
   roll call by the jailer. Prisoners scratch their own tallies. Two messes a day. The jailer and the
   Watch come and go (the GUARD actions).
8. **The end.** Three ways out:
   * **The Hook.** He swears the oath with his hand on the Book, the Smith brands the Hook on his left
     shoulder blade, the Wren draws a hook in the margin, and he gets rum, a cutlass and a berth.
     A man who tried to escape gets a **Bar** burnt under the hook for each attempt.
   * **Redemption.** A ransom is paid; he is branded with the **Ring** (so no press-gang takes him again),
     a circle is drawn round his name, and a boat takes him to Gullhaven. Rare.
   * **The beam.** Dead or hanged: one line through the name. The number is never given again in that Book.
9. **Long stays.** Some men stay years. Old Fetch stayed eight winters and refused release twice.

**The Muster Book.** Book the First (Years I-III) and Book the Second (Years III-XI, closed at No. 412)
lie on the shelf under the desk with the Crown register beneath them. **Book the Third** is the one
open on the desk: the in-world Muster Book that numbers new players from 1. Past prisoners are quoted as
"Book II, No. 88".

**Brands.** The Hook (crew), the Bar (one per escape, under the hook), the Ring (redeemed). The King's
Arrow is the Crown's old brand for deserters: the Lord wears one under his hook.

**Ebb Night** (each anniversary of the Taking, on the Dead Ebb): rum for the Watch, the Lord's Due goes
to the chest, one prisoner's freedom is diced at the guard table, Crake reties the knots of his cats, the
Lord reads the year's tally aloud from the Book and goes down alone, without a torch, to touch his own
carving in the Cistern.

---

## 9. The named dead and the named survivors (threads across rooms)

These are the people whose carvings, objects and papers the visitor finds in several rooms. Each
thread should be discoverable piece by piece.

**L.D. (Lucan Drave, Crown No. 77).** C01: *77* scratched by the shackles, with a later hook. C04: the
forty-one strokes, *I WILL COME BACK FOR THE KEY*, the culvert grate with two bars bent outward. C08: a
single *L* at the height of bound hands on the Steadfast's mast, the oldest mark on it. Throne: *77*
under the plinth, the Bride's wheel. Under the desk: the Crown register entry "drowned".

**Absalom Reed, "Long Absalom"** (Book I, No. 9). Gullhaven ropemaker who taught the young Lucan his
knots. Pressed in the first press of Year I; refused three times (the Book reads REFUSED, REFUSED,
REFUSED). Preached from the Stocks to the guards. Racked to the fifth notch with ropes made on his own
walk; died on the rack that winter and came off it, they say, a hand taller. C01: refusal carving.
C02: his skeleton along the north wall, the knot board, the loose stone with his prayer book ("For
Lucan..."), *THE SEA GIVES BACK WHAT THE ROPE TAKES*, the fifth notch signed A.R. C03: his prayer to
the saint. Throne: the chart rolls tied with his knots.

**Bartholomew Crane, "Old Fetch"** (Book I, No. 31). Crown marine of the garrison; refused the hook
because the Saint's Three, his messmates, had died at the chapel door. A dog in the Kennel from
Year I until he died in the straw in the winter of Year IX: eight winters. Refused release twice on Ebb
Night. The kennelman will not let his bones be moved: "he is on watch". Kennel: the skeleton with the
collar FETCH, his helmet as the chamber pot, the rules (*EAT LAST. SLEEP FIRST. NEVER LOOK AT THE
THRONE.*), the stone grey with 2,900-odd strokes, the strokes on Kennel 1's post, the bowl FETCH.
Yard: *DO NOT LOOK AT THE THRONE* cut low on the pier beside the Kennel grilles on his first night.

**Hugh Ormond, "the Lieutenant"** (Book II, No. 14). First lieutenant of the Steadfast. Held out for
three years: a season in Cage 1, two winters in the Kennel. Took the hook in Year VI after 1,061 days;
now sailing master of the Second Bride, sailing his own ship under the Lord's flag. C07: the ship
scratched on Cage 1's floor, reef-knotted rags on its bars, the full carving of the Steadfast, the
loose stone with his secret log. Kennel: the compass rose with a line through north, the bowl
LIEUTENANT. C08: the dismasted frigate, *HER MAST IS HERE*. Throne: his letter to the Lord.

**Tam Wicken, "the Shantyman"** (Book II, No. 15). Shantyman of the Steadfast. Sixty lashes at the
Mast for singing a Crown song after lights out; sang straight through them. Sang the whole song from
the Stocks. Took the hook in Year IV; shantyman of the Second Bride. His song, *The Widow's Tooth*, is
carved in pieces in different rooms (C03, C08, C01) and is what the Pit hums at lights out:

> Oh, the Tooth bites deep and the Tooth bites slow,
> and the tide comes in where the drowned men go.
> *Haul away for the Widow, boys, haul away for the Tooth;*
> *the Lord keeps all the keys, and the sea keeps all the truth.*
> I was pressed in a tavern with ale in my hand,
> and I'll never more walk on the King's dry land.
> They wrote down my number, they burnt me a hook,
> and my name's at the bottom of the Wren's black book.

**Jory Penhallow, "the Seal"** (Book II, No. 88). Pearl diver of the Saint's Finger, Year IV. Held his
breath under the ducking chair for a count of three hundred: the record. A season in the Kennel (tag
SEAL). Heard the legend of the culvert and tried it three times: forty lashes after the first and after
the second (C08: *J.P. 40* and a seal; Crake's book). After the third the Lord had him chained beside the
tank, the chain just short enough that he could always see the grate: "This man tried the way out three
times. Let him look at it." He died of thirst in nine days, in a room full of water, in Year VI. C04:
the skeleton, the slate on his knees, the one grey pearl in his hand, the breath tallies with *300*
ringed, the knot cord, *J.P. 300* on the chair. Kennel: tag SEAL, bowl SEAL, a seal carving.
Throne: sixty pearls in the chest "and a gap where one is missing".

**Kit Fennick, "the Dicer"** (Book II, No. 203). Gullhaven cardsharp sold to the press by a tavern-keeper
he owed, Year VII. In the Kennel he carved a deck of cards from soup bones, four suits: **Hooks, Keys,
Bones, Crowns**. Played the Watch through the bars. Won his release on Ebb Night of Year VIII at the
guard table with a double six (loaded dice), and stayed on as a guard. His cards are everywhere: the
Ace of Hooks behind the loose stone in the Kennel wall, the Three of Keys and Queen of Crowns on the
Kennel floor, the Four of Bones under the stocks' bench (C03), the Jack of Keys in Cage 1 (C07), the
Two of Bones on the guard table. His loaded die, cracked to show the lead, is on the table. His name
is the newest on the Watch's wall. C04: *KIT 61 (CHEATED)*.

**Garrett Vole, "the Rat"** (Book II, No. 161). Gullhaven pickpocket, Year VI. Picked the lock of the
Stocks (a bent nail in the C03 mortar), Cage 1's padlock while hoisted (and fell; a second nail in the
C07 mortar), and the Kennel's second grille (*lift and turn* scratched round the C06 lock). Caught in
the yard each time, because the Water Stair is the only way out. Finally caught with his arm in the
Lord's loot chest (Year VII). The Lord made him the jailer's apprentice. He stole the hook from the
Rack's tool board to make picks (its rust shadow is still there) and named the Pit's rats after the
officers: the rat hole in C02 is "Hask's".

**Matthias Kemble, "the Merchant's Son"** (Book II, No. 90). Taken off his father's pepper ship in Year
IV for ransom. Put in the Stocks for asking for a chair. Hid a sliver of mirror in the chapel wall to
check his face: *STILL MATTHIAS. DAY 200.* Ransom letters: "his weight in pepper, rising a finger each
month"; the father offered half; the Lord: "Then I keep half." Paid in full in Year V; branded with the
Ring; went home; was called "half a son" and disowned; came back up the Water Stair in Year IX and asked
for the hook. Now the Wren's under-clerk. C02: *My father owns nine ships and cannot buy one inch of
this rope.* C03: the mirror. Throne: the ransom letters.

**Hob Lacey, "the Tenant"**. The Crown's hangman on Gallows Point for thirty years, 211 men by warrant.
Put in his own cage on the Night of the Ebb; lasted nine days. C07: his skeleton in Cage 2, his black
hood at its feet, 211 fine notches on the bottom hoop and 9 deep ones on the middle hoop.

**Governor Aldous Prynne, "the Governor"**. Hanged at dawn on Day 1 from the second beam (T1). The
placard on his chest: *THE CROWN KEEPS THE YARD*. His gilt buttons were melted into the circlets on the
throne's skulls; his coronet of office is beaten into the rim of the west brazier; his chain of office
hangs round the east one. Twenty-three notches under his beam: the men hanged from it since.

**Ned and Will Ashby**. The gatekeepers who sold the gate. Skulls on the gate arms with a Crown coin in
each jaw. *W.A. KEPT THIS GATE NINE YEARS* in the passage.

**Minor names** for carvings and counts: **Oswin Tull** (purser's mate of the Good Intent, racked for
stealing rum: *I TOLD THE TRUTH* / *THE FIFTH TIME*), **Rafe Corbin** (smuggler, the Cages), **Hal
Stubbs** (140 in the Cistern), **Ned Platt** (90), **Bran** (a Kennel name). **The Saint's Three**: the
three marines who held the chapel door.

---

## 10. Timeline (Years of the Keeping)

| When | What |
|---|---|
| reign of King Aldred | Fort Clemency built; the chapel bell cast. |
| 23 years before the Ebb | Lucan Drave pressed in Gullhaven, aboard the Steadfast. |
| 12 years before | Drave, Crown No. 77, escapes through the culvert. "Drowned". |
| Year I, Day 1 | **The Night of the Ebb.** Gallows Bride burned on the Water Gate. Governor hanged. Hob Lacey caged. The Saint's Three die. Old Fetch enters the Kennel. Book the First opened. |
| Year I | The Ashbys nailed. Absalom Reed refuses three times and dies on the Rack. The Hungry Winter: the mastiffs eaten; Fenwick Dunne given men. |
| Year II | Merrick Sallow comes over from Gullhaven. |
| Year III | The Steadfast taken in fog. Ormond, Wicken, Kettering, Crake arrive. The mast stepped in C08. Book the Second opened. |
| Year IV | The Saint's Finger taken: Jory Penhallow. Matthias Kemble taken for ransom. Tam Wicken takes the hook. |
| Year V | The Good Intent taken: the anchor, Oswin Tull. Kemble ransomed. Jory's first two culvert attempts. |
| Year VI | Jory's third attempt; he dies chained in the Cistern. Ormond takes the hook. Garrett Vole arrives. |
| Year VII | The Great Flood: the sea comes through the gate knee-high, to the second step of the dais. Vole caught in the loot chest. Kit Fennick sold to the press. |
| Year VIII | Ebb Night: Fennick throws a double six. |
| Year IX | Old Fetch dies in the straw. Kemble returns. The Crown's price reaches 1,000 crowns. |
| Year XI (now) | Book the Second closed at No. 412. **Book the Third** opened: the players. |

---

## 11. The daily round (the BELL events)

The gate bell (Saint Clement's) is the clock of the Pit. **Strokes**: one, the watch changes; two,
messes; three, fresh meat at the Water Stair; five, fire; seven, the Lord comes down; without end, a
man is loose.

* **DAWN** - one stroke. Grey light down the slits. The watch changes and greets the Governor. Night
  buckets go into the channel. Gulls.
* **RATIONS** - two strokes, twice a day: the **first mess** at the forenoon (ship's biscuit, salt
  fish, a dipper of water) and the **second mess** at dusk (pease boiled grey, a heel of bread; rum for
  hooked men). The Kennel gets slop in the bowls and the trough. The Purse weighs everything.
- **ROLLCALL** - after each mess. Hask reads the Sentence Board; every man answers with his number, the
  dogs bark once. Tallies are counted against the chalk.
* **LIGHTSOUT** - one long stroke. "Darken the Pit": cell torches are banked low, the yard lanterns
  and the Lord's braziers burn on. The song goes round the cells until a guard bangs the bars.
* **HIGHTIDE** - twice a day. The sea shoulders up the channel and through the culvert; the Cistern
  rises; drains breathe out; spray comes through the slits. The Lord holds court at the flood.

---

## 12. Sounds and smells

| Where | Sounds | Smells |
|---|---|---|
| Gate | the sea on the stair, gulls, the winch's thirty-seven clacks, the bell | weed, wet rope, salt |
| Guardroom | dice, laughter, the scrape of the dagger, keys | rum, wet wool, tallow, unwashed linen from the basket |
| Yard | the channel sucking at the tide, the Governor's chain, lanterns creaking, dripping | salt, rot at the ebb, the open sea at the flood |
| Press-Gang | the quill, sand being shaken, the hiss of a brand in brine, the bellows | ink, sealing wax, burnt hair |
| Rack | the ratchet of the wheel, the rope's creak | tar, sweat, brine |
| Stocks | mockery, crusts hitting wood, the saint's silence | old wax, rotten eggs, smoke |
| Cistern | the culvert booming at high tide, drips, the chair's squeal | green brine, wet stone, salt crust |
| Kennel | chains on stone, straw, the kennelman's two-note whistle, men barking because they are told to | straw, sweat, other men's dirty linen, wet rope, and faintly the Governor's dogs |
| Cages | the cage chains' squeal, the swing, the gulls in the vault | old bone, smoke, bird droppings |
| Mast | the cats on their pegs, the count in Crake's sing-song, rope creak | salt, tar, blood |
| Throne hall | the braziers' roar, the banners, silence | woodsmoke, hay, rum, gilt warm from the fire |

---

## 13. Visual language: majestic but filthy, dark but full of information

The owner's brief is a set of contrasts. Every room should show both halves of at least one.

* **Gilded vs rusted.** **Gilt exists only in the throne hall**: the circlets on the throne's skulls
  (the Governor's buttons), the studs on the arms, the hook-and-crown on the back, the nail line on the
  top step, the coronet on the west brazier, the chain on the east one, the STEADFAST letters, the
  prize board, the chart's frame, the officers' sword hilts, the reliquary. Everywhere else metal is
  rust, the colour of old blood. The yard's Governor wears torn buttonholes where his gilt was.
* **Banners vs rags.** The same cloth at two ends of the Pit: the Lord's banners and the upside-down
  Crown banner in the throne hall; the rest of that Crown banner cut into rags for the Kennel (a strip
  with a tarnished gold thread lies on the rag pile).
* **Ledgers vs scratched walls.** The officers write: the Muster Book, the Sentence Board, Crake's lash
  book, the Mute's tide slate, the wager slate, the prize board, the Lord's charts, the Standing Orders.
  The prisoners scratch: tallies in fives, names begun and abandoned, songs, ships, rules, a compass.
  The two keep count of the same days and never agree.
* **Numbers everywhere.** 77, 41, 300, 211, 23, 31, 37, 412. Everyone in the Pit is a number first.
* **Light.** Every fire in the Pit is lit from the throne braziers by a carried spill: the Lord's fire is
  in every room. In DARKNESS only the braziers burn.
* **The sea gets in.** Salt rime, weed, crab shells, high-water lines, salted vaults, gulls' nests.

### Conventions for the 3D team (story_props.json)

* **Materials** (only the 8 block materials): **gilt = Bone** (warm ivory reads as old gold in
  firelight; keep gilt faces clean and facing the braziers); **soot, char, ink, black paint = Iron**
  (darkest); **salt, chalk, lime-wash, tallow, wax = Bone**; **mud, stains, spills = Floor**;
  **rope, twine, wicker, nests, weed = Straw**; **paper, parchment, leather, cloth = Cloth**. No new
  geometry uses Flame (the fire script owns face 2).
* **Fit.** Every item lies inside its piece's bounding box (checked against `Report.json`; each item
  gives `center_m` and `size_m` in world metres). Slack available for raised details: outer cell walls
  (C0x_Wall, C05/C07/C08_Wall) 4 cm; end partitions with copings (C04_Partition, C08_Partition,
  V_Partition_W/E) 5 cm; pier and arch-head yard faces 11 cm; N_Back_* 12-19 cm. **No slack** on
  C01/C02/C03/C05/C07_Partition, V_Wall_*, N_Wall_*, V_Floor_*, N_Floor_*, G_Stairs, the dais top:
  details there are **incised** (cut into the surface). Several partitions carry items on their *other*
  face (e.g. C01_Partition's north face is the Rack's south wall): the `where` text says which face.
* **Walkways.** Nothing raised in a cell's door corridor (x 3.0-6.2 from the front, door +/- 1 m), the
  middle of a cell floor, the yard walkway (|x| < 2.6), the gate passage, the guardroom crossing
  (|x| < 3) or the throne approach. Only flat stains and incised marks touch those zones.
* **Text.** The mesh only has to *suggest* writing (a recessed or raised panel with a few strokes); the
  words themselves reach the player through the lore notecard (EXAMINE and CARVING lines). The notecard
  is the canon for every inscription.
* **Budget.** All story items are HIGH-LOD only. Rough triangle targets: carving or stain panel 2-24;
  small object (coin, card, die, tag) 6-20; medium object (bucket, pot, helmet, book) 40-120; nest,
  rag, hat row 60-150. Keep extra detail on large-radius pieces (walls, vaults, floors, partitions),
  where HIGH triangles cost almost nothing; be stingiest on small furniture (desk, table, kennels,
  throne, kneeling stone).

---

## 14. Tone, consent and limits

* Adult, dark, and humiliating by design (the Kennel, the rags, the brands), but every scene in-world is
  **roleplay between consenting adults**. The lore describes the fiction of the place; it never presents
  non-consensual acts as real, and the CHORE and GUARD lines are offered actions that players choose.
* **No minors, ever.** In-world this is canon too: Rule I of the Book: *"The Book takes men grown, and
  no other. A beardless face goes back over the water."* No cabin boys, no youths, no "lads".
* No sexual violence in the lore. Cruelty is shown through objects, counts and consequences, not
  described on bodies at length.
* Garments in the build are male: breeches, shirts, loincloths.

## 15. Style guide for lore lines

* Second person, present tense for EXAMINE ("You..." or a plain description of what is in front of you).
  Each line is a micro-story or a pointer to another room or person in this bible.
* Concrete before abstract: a number, an object, a name, then (maybe) a feeling.
* No modern words (no "okay", "minutes" in speech, no technical vocabulary). Period words: crowns,
  shillings, leagues, hands (height), glass (time), mess, watch, tot, spill, tallow, slop.
* ASCII only, no `|` inside a field, at most 250 bytes a line (Second Life notecard limits). The whole
  notecard stays under 64 KB.
* `{who}` the actor, `{target}` the other avatar (in CHORE lines: the cell's other inmates), `{cell}`
  the cell name as shown in-world (e.g. THE KENNEL): only in CHORE and GUARD lines.
* CHORE and GUARD: at most 9 of each, buttons of 20 characters or fewer, never named Examine, Carve or
  Close. The script picks the effect by keyword in the button: tally/scratch/mark, wash/scrub/bucket/douse,
  knock, hide/stash, feed/ration/slop/bread, search, record; anything else only narrates.
* All NOTE pages of one piece sit on consecutive lines.
* Never contradict a placed prop. If a line mentions a thing, it is either modelled (see
  story_props.json and the existing pieces) or small enough to live in a texture (a stain, a scratch, a
  crumb, a smell).

### Glossary and slang

* **fresh meat**: new arrivals. **hooked / a hook**: a branded crew man. **take the hook / take the Pit**:
  the Choice. **a dog**: a Kennel prisoner. **the Due**: the stake under the dagger.
* **go under** (Cistern), **go up** (Cages), **grow an inch** (Rack), **wear the wood** (Stocks),
  **kiss the mast** (Mast), **sleep in the straw** (Kennel).
* **the Governor**: the hanged man. **the Tenant**: the skeleton in Cage 2. **the Saint's Three**: the
  skulls in the Stocks. **Old Keys**: Hask. **the Wren**, **the Purse**, **the Smith**, **the Mute**.
* **the Ebb**: the Night of the Ebb. **Ebb Night**: its anniversary. **the Dead Ebb**: the year's lowest tide.
* **the Lord's weather**: WATCH, GLOOM, JUDGEMENT, DARKNESS.

---

## 16. Cross-reference index (thread -> where to find it)

| Thread | C01 | C02 | C03 | C04 | Kennel | C07 | C08 | Yard | Gate | Hall | Throne |
|---|---|---|---|---|---|---|---|---|---|---|---|
| L.D. / No. 77 | 77 by the shackles, Crown register | Reed's book prays for "Lucan" | | 41 strokes, KEY, grate | | | the L on the mast | | | wanted posters | 77 under the plinth, wheel, letters |
| Absalom Reed | REFUSED carving | skeleton, knot board, book, A.R. notch, carving | prayer to the saint | | | | | | | | knots on the chart rolls |
| Old Fetch | | | (the Saint's Three, his messmates) | | skeleton, collar, rules, tally stone, post, helmet, bowl | | | DO NOT LOOK AT THE THRONE | | Rook | |
| Hugh Ormond | | | | | compass rose, bowl | cage ship, rags, Steadfast carving, log | HER MAST IS HERE, men's lashes | T3 initials | | | letter, STEADFAST letters |
| Tam Wicken | song verse | | verse on bench and wall | | | | chorus | | | | |
| Jory the Seal | | | | skeleton, pearl, slate, 300, cord, chair | tag, bowl, seal | | J.P. 40, seal | | | | pearls |
| Kit Fennick | | | Four of Bones | KIT 61 | Ace of Hooks, cards, bowl | Jack of Keys | | | | dice, Two of Bones, Watch wall | |
| Garrett Vole | | rust shadow of the hook, Hask's rat hole | nail in mortar | | C06 lock | nail in mortar, padlock | | | | Hask's note | loot chest |
| Matthias Kemble | | carving | mirror shard | | | | | | | | ransom letters |
| Hob Lacey | | | | | | skeleton, hood, 211 notches, Crown plate | | | | | |
| Governor Prynne | | Crown orders | | | old Crown plates GRIP etc. | | | hanged, placard, coat, 23 notches | | Crown arms defaced | buttons, coronet, chain |
| Saint Clement | | | fresco, altar, stars, stoup, bell hole | | | | | | the bell | | reliquary (a fishbone) |
| The sea gets in | | | | grate, salt, high-water lines | | gulls' nest | salt barrel | channel, rime | stair weed, tide lines | | flood line |

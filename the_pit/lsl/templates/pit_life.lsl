// =====================================================================
//  THE PIT - PRISON LIFE: INMATES, CELL SIGNS, CELL LIFE, ROUTINES (root)
//
//  INMATES. Every minute while anyone is on the parcel, whoever stands in
//  a LOCKED cell (over its floor, under 2.8 m, behind the door) is booked
//  as an inmate: a number chalked on the door and a record kept in the
//  build - name, cell, first day, time served, last meal, last wash and
//  tally marks. Hunger and filth only grow while he is locked in, so
//  logging off starves nobody. Records unseen for 60 days are pruned,
//  and 80 are kept at most.
//  CELL SIGNS. Floating text over the door of every occupied cell: the
//  cell, inmate number and name, day count and hours locked in, hours
//  since the last meal, a filth bar and the tally.
//  CELL LIFE. An inmate touching his cell (walls, floor, straw, props)
//  gets his own menu from the CHORE lines of the notecard: scratch a
//  tally mark, wash in the bucket, knock on the wall (the inmates next
//  door hear it), hide something in the straw; plus Examine and Carve.
//  Anyone else touching an occupied cell gets the GUARD menu from the
//  GUARD lines: feed, douse, search the straw (d20 to find what is
//  hidden), read the record. What a button does comes from its name:
//    tally / scratch / mark ......... one more tally mark (prisoner)
//    wash / scrub / bucket / douse .. filth back to nothing
//    knock .......................... heard in the cells next door
//    hide / stash ................... hide a short text in the straw
//    feed / ration / slop / bread ... a meal for the inmates (guard)
//    search ......................... d20 against 10 finds the stash
//    record ......................... the jailer's record
//  Any other button just says its line.
//  ROUTINES. Once a day by SL time (Pacific), while anyone is about:
//  DAWN 06:00 (back to the WATCH mood), RATIONS 08:00 and 19:00 (everyone
//  locked in gets fed), ROLL CALL 12:00 (every inmate named), LIGHTS OUT
//  23:00 (the GLOOM mood) and HIGH TIDE every 6 hours (03, 09, 15, 21).
//  The lines are the BELL records of the notecard, heard on the parcel.
//  Without the notecard "pit_lore", short built-in lines are used.
//
//  Switches (/7 settings > Prison life): inmates (master for the rest),
//  cell_signs, cell_life, routines; plus hovertext, narration, moods,
//  sounds, locks, and examine and carvings for the two buttons.
//  Owner chat: /7 inmates (every record), /7 inmate release <number>
//  (struck from the register; if he is alone in his cell, the lock
//  opens), /7 lore (read the notecard again).
//  Link messages: 9510 "fed|<cell or avatar key>" and
//  "washed|<cell or avatar key>" from other scripts (the kennel slop,
//  the ducking chair); 9500 to pit_examine for Examine and Carve.
// =====================================================================

string  CARD = "pit_lore";
integer SCAN = 60;              // seconds between two head counts
float   HEADROOM = 2.8;         // height of a cell above its floor (m)
integer FILTH_HOURS = 8;        // hours locked in for each notch of the filth bar (5 notches)
integer KEEP_DAYS = 60;         // records unseen this long are pruned
integer MAX_RECORDS = 80;
integer STASH_DC = 10;          // d20 >= this finds what is hidden in the straw
integer WINDOW = 1200;          // a routine still rings this many seconds after its hour

list CELLS = ["C01", "C02", "C03", "C04", "C05", "C07", "C08"];
list ROOMS = ["THE PRESS-GANG", "THE RACK", "THE STOCKS", "THE CISTERN", "THE KENNEL", "THE CAGES", "THE MAST"];
list NEIGH = ["C02", "C01,C03", "C02,C04", "C03", "C07", "C05,C08", "C07"];      // cells sharing a wall
list EVENTS = ["DAWN", "RATIONS", "ROLLCALL", "LIGHTSOUT", "HIGHTIDE"];
list SLOTS = [21600, 0, 28800, 1, 43200, 2, 68400, 1, 82800, 3, 10800, 4, 32400, 4, 54000, 4, 75600, 4];  // [second of the day, event]

// used while the notecard has no lines of that kind
list BELL_DEF = [
    "Grey light leaks through the grates: dawn. The watch changes and the torches are trimmed.",
    "The ration cart rattles down the yard: slop, stale bread and brackish water for the cells.",
    "ROLL CALL! The jailer drags his club along the bars of every cell.",
    "LIGHTS OUT. The torches are snuffed one by one; only the braziers by the throne still glow.",
    "High tide: the sea pushes up the channel and the whole Pit smells of salt and rot."];
list CHORE_DEF = [
    "Scratch tally", "{who} scratches one more mark into the wall of {cell} with a splinter of bone.",
    "Wash", "{who} splashes the grime off with the water in the bucket. It stinks of salt.",
    "Knock on wall", "{who} knocks three times on the wall of {cell} and listens.",
    "Hide something", "{who} pushes something deep into the straw and smooths it over."];
list GUARD_DEF = [
    "Feed", "{who} shoves a bowl of cold slop through the bars. {target} will eat today.",
    "Douse", "{who} empties a bucket of sea water over {target}. The filth runs into the gutter.",
    "Search straw", "{who} kicks through the straw of {cell}, looking for anything hidden.",
    "Read record", "{who} takes down the jailer's slate of {cell} and reads it."];

list F_LINK; list D_LINK; integer BELL_LINK;   // cell floors and doors (C05_Door for the kennel), the winch
integer PRIMS;
// notecard index: (code << 20) | (first line << 8) | count; code: BELL event, 16 + chore button, 32 + guard button
list IDX; list CHORE_B; list GUARD_B; integer BELLS;
integer LINE; key Q; key CARD_KEY;
integer CH;
list SESS;      // open menus, one per avatar: [avatar, link, mode, expires, data]
list REQ;       // notecard lines on their way: [query, data]
list PARDON;    // released by the owner while still locked in: not booked again until he is out
integer LAST; integer JAILED; integer PRUNE_AT;
string OPTS;

integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

// The root prim carries the object's name, not its piece name: pit_core stores which piece it is.
string piece(integer l)
{
    if (l == 1)
    {
        string r = llLinksetDataRead("root_piece");
        if (r != "") return r;
    }
    return llGetLinkName(l);
}

string who(key k)
{
    string n = llGetDisplayName(k);
    if (n == "") n = llKey2Name(k);
    return n;
}
string clean(string s) { return llGetSubString(llDumpList2String(llParseString2List(s, ["|", ",", "\n"], []), " "), 0, 23); }
integer utf8(string s) { return (llStringLength(llStringToBase64(s)) * 3) >> 2; }   // byte length
string rest(list p, integer from)
{
    if (llGetListLength(p) <= from) return "";
    return llDumpList2String(llList2List(p, from, -1), "|");
}
string room(string t)
{
    integer i = llListFindList(CELLS, [t]);
    if (i == -1) return "THE PIT";
    return llList2String(ROOMS, i);
}
integer has(string s, list words)
{
    integer i;
    for (i = 0; i < llGetListLength(words); ++i) if (llSubStringIndex(s, llList2String(words, i)) != -1) return TRUE;
    return FALSE;
}

// pieces another script answers when touched (keep in step with pit_examine)
integer owned(string nm)
{
    if (llSubStringIndex(nm, "_Door") != -1 || llSubStringIndex(nm, "G_Leaf") == 0 || llSubStringIndex(nm, "C07_Cage") == 0
        || llSubStringIndex(nm, "C05_Kennel") == 0) return TRUE;
    if (llListFindList(["G_Portcullis", "G_Winch", "N_Throne", "C02_Rack", "C03_Pillory", "C03_Stocks", "C04_Chair",
                        "C08_Mast", "C05_Bowls", "V_Table", "V_Basket", "N_Kneeling_Stone"], [nm]) != -1) return TRUE;
    if (nm == "C01_Desk") return opt("muster_book");
    if (nm == "C01_Branding_Brazier") return opt("branding");
    return FALSE;
}

string cell_of(string nm)
{
    string t = llGetSubString(nm, 0, 2);
    if (t == "C06") t = "C05";
    if (llGetSubString(nm, 3, 3) != "_" || llListFindList(CELLS, [t]) == -1) return "";
    return t;
}

list inmates_of(string t) { return llParseString2List(llLinksetDataRead("jail:" + t), [","], []); }

string where(key k)
{
    integer i;
    for (i = 0; i < 7; ++i)
        if (llSubStringIndex(llLinksetDataRead("jail:" + llList2String(CELLS, i)), (string)k) != -1) return llList2String(CELLS, i);
    return "";
}

// the lock as pit_doors keeps it: "1|holder|name|until|keys"
integer locked(string t) { return opt("locks") && llGetSubString(llLinksetDataRead("lock:" + t), 0, 0) == "1"; }

// ------------------------------------------------------------- records
// inmate:<key> = number|name|cell|first day (unix)|seconds locked in|locked-in clock at the last meal|
//                ... at the last wash|tally|last seen (unix)
list rec(key k) { return llParseStringKeepNulls(llLinksetDataRead("inmate:" + (string)k), ["|"], []); }
integer hours(list r, integer f) { return ((integer)llList2String(r, 4) - (integer)llList2String(r, f)) / 3600; }
integer day(list r) { return (llGetUnixTime() - (integer)llList2String(r, 3)) / 86400 + 1; }
string filth(list r)
{
    integer n = hours(r, 6) / FILTH_HOURS;
    string bar = ""; integer i;
    for (i = 0; i < 5; ++i) { if (i < n) bar += "#"; else bar += "-"; }
    return "[" + bar + "]";
}

// 5: fed now, 6: washed now, 7: one more tally mark
mark(key k, integer f)
{
    list r = rec(k);
    if (llGetListLength(r) < 9) return;
    integer v = (integer)llList2String(r, 4);
    if (f == 7) v = (integer)llList2String(r, 7) + 1;
    llLinksetDataWrite("inmate:" + (string)k, llDumpList2String(llListReplaceList(r, [v], f, f), "|"));
}

string names(list ks)
{
    integer n = llGetListLength(ks);
    if (!n) return "the rats";
    string s = ""; integer i;
    for (i = 0; i < n; ++i)
    {
        if (i > 0 && i == n - 1) s += " and ";
        else if (i > 0) s += ", ";
        s += llList2String(rec((key)llList2String(ks, i)), 1);
    }
    return s;
}

// drops records unseen for KEEP_DAYS and, over MAX_RECORDS, the one unseen longest
prune()
{
    integer now = llGetUnixTime();
    integer i = 0; integer kept = 0; string oldest = ""; integer oldest_t = now;
    list ks;
    while ((ks = llLinksetDataFindKeys("^inmate:", i, 10)) != [])
    {
        integer j;
        for (j = 0; j < llGetListLength(ks); ++j)
        {
            string id = llList2String(ks, j);
            integer seen = (integer)llList2String(llParseStringKeepNulls(llLinksetDataRead(id), ["|"], []), 8);
            if (now - seen > KEEP_DAYS * 86400) llLinksetDataDelete(id);
            else
            {
                ++kept; ++i;
                if (seen < oldest_t) { oldest_t = seen; oldest = id; }
            }
        }
    }
    if (kept >= MAX_RECORDS && oldest != "") llLinksetDataDelete(oldest);
}

// RP line for everyone within 20 m of the piece (or only k with narration off)
narrate(integer l, key k, string s)
{
    if (!opt("chat")) return;      // chat switched off: no RP text at all
    if (!opt("narration")) { if (k) llRegionSayTo(k, 0, s); return; }
    vector c = llList2Vector(llGetLinkPrimitiveParams(l, [PRIM_POSITION]), 0);
    list ag = llGetAgentList(AGENT_LIST_REGION, []);
    integer i;
    for (i = 0; i < llGetListLength(ag); ++i)
    {
        key a = llList2Key(ag, i);
        if (llVecDist(llList2Vector(llGetObjectDetails(a, [OBJECT_POS]), 0), c) <= 20.0) llRegionSayTo(a, 0, s);
    }
}

// heard by everyone on the parcel, from "The Pit"
parcel(string s)
{
    if (!opt("chat")) return;      // chat switched off: no RP text at all
    string before = llGetObjectName();
    if (before != "The Pit") llSetObjectName("The Pit");
    list ag = llGetAgentList(AGENT_LIST_PARCEL, []);
    integer i;
    for (i = 0; i < llGetListLength(ag); ++i) llRegionSayTo(llList2Key(ag, i), 0, s);
    if (before != "The Pit") llSetObjectName(before);
}

book(key k, string t, integer dt, integer now, integer dl)
{
    string id = "inmate:" + (string)k;
    list r = llParseStringKeepNulls(llLinksetDataRead(id), ["|"], []);
    if (llGetListLength(r) < 9)
    {
        prune();
        integer num = (integer)llLinksetDataRead("inmates") + 1;
        llLinksetDataWrite("inmates", (string)num);
        r = [num, "", t, now, 0, 0, 0, 0, now];
        dt = 0;
        narrate(dl, k, "The jailer chalks a number on the door of " + room(t) + ": " + who(k) + " is inmate No."
            + (string)num + " now.");
    }
    else if (llSubStringIndex(llLinksetDataRead("jail:" + t), (string)k) == -1)
        narrate(dl, k, "The jailer knows that face: inmate No." + llList2String(r, 0) + ", " + who(k) + ", back in "
            + room(t) + ". Day " + (string)day(r) + ".");
    r = llListReplaceList(r, [clean(who(k)), t], 1, 2);
    r = llListReplaceList(r, [(integer)llList2String(r, 4) + dt], 4, 4);
    r = llListReplaceList(r, [now], 8, 8);
    llLinksetDataWrite(id, llDumpList2String(r, "|"));
}

// position, rotation and size of a piece in the root's frame
list frame(integer l)
{
    list p = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL, PRIM_SIZE]);
    if (l == 1) p = [ZERO_VECTOR, ZERO_ROTATION] + llList2List(p, 2, 2);
    return p;
}

// who stands in each locked cell now
census()
{
    integer now = llGetUnixTime();
    integer dt = now - LAST;
    if (dt < 0 || dt > 2 * SCAN) dt = SCAN;
    LAST = now;
    list ag = llGetAgentList(AGENT_LIST_PARCEL, []);
    vector rp = llGetRootPosition(); rotation rr = llGetRootRotation();
    list at = [];
    integer i;
    for (i = 0; i < llGetListLength(ag); ++i)
        at += (llList2Vector(llGetObjectDetails(llList2Key(ag, i), [OBJECT_POS]), 0) - rp) / rr;
    list still = [];
    JAILED = 0;
    integer c;
    for (c = 0; c < 7; ++c)
    {
        string t = llList2String(CELLS, c);
        integer fl = llList2Integer(F_LINK, c);
        integer dl = llList2Integer(D_LINK, c);
        list inside = [];
        if (opt("inmates") && fl > 0 && dl > 0 && at != [] && locked(t))
        {
            list f = frame(fl); list d = frame(dl);
            vector fp = llList2Vector(f, 0); rotation fr = llList2Rot(f, 1); vector fs = llList2Vector(f, 2);
            vector dp = llList2Vector(d, 0); vector ds = llList2Vector(d, 2);
            // the floor reaches a little past the door: count only the room's side of the door
            vector nrm = <1.0, 0.0, 0.0>;
            if (ds.y < ds.x) nrm = <0.0, 1.0, 0.0>;
            nrm = nrm * llList2Rot(d, 1);
            if ((fp - dp) * nrm < 0.0) nrm = -nrm;
            for (i = 0; i < llGetListLength(at); ++i)
            {
                vector a = llList2Vector(at, i);
                vector r = (a - fp) / fr;
                if (llFabs(r.x) <= fs.x * 0.5 && llFabs(r.y) <= fs.y * 0.5 && r.z >= -fs.z * 0.5
                    && r.z <= fs.z * 0.5 + HEADROOM && (a - dp) * nrm > 0.15)
                {
                    key k = llList2Key(ag, i);
                    if (llListFindList(PARDON, [k]) != -1) still += k;
                    else
                    {
                        book(k, t, dt, now, dl);
                        inside += (string)k;
                    }
                }
            }
        }
        string list_now = llDumpList2String(inside, ",");
        if (list_now != llLinksetDataRead("jail:" + t))
        {
            if (list_now == "") llLinksetDataDelete("jail:" + t);
            else llLinksetDataWrite("jail:" + t, list_now);
        }
        JAILED += llGetListLength(inside);
    }
    PARDON = still;
    signs();
}

// floating text over the door of every occupied cell (254 bytes at most)
signs()
{
    integer c;
    for (c = 0; c < 7; ++c)
    {
        integer dl = llList2Integer(D_LINK, c);
        if (dl > 0)
        {
            string t = llList2String(CELLS, c);
            list ks = inmates_of(t);
            integer n = llGetListLength(ks);
            string txt = "";
            if (n && opt("inmates") && opt("cell_signs") && opt("hovertext"))
            {
                txt = room(t);
                if (n > 1) txt += " - " + (string)n + " inmates";
                integer i;
                for (i = 0; i < n; ++i)
                {
                    list r = rec((key)llList2String(ks, i));
                    string line = "\nNo." + llList2String(r, 0) + " " + llGetSubString(llList2String(r, 1), 0, 15) + ", day "
                        + (string)day(r) + " (" + (string)((integer)llList2String(r, 4) / 3600) + " h in)\nfed "
                        + (string)hours(r, 5) + "h ago  filth " + filth(r) + "  tally " + llList2String(r, 7);
                    if (utf8(txt + line) > 238)
                    {
                        txt += "\n(+" + (string)(n - i) + " more)";
                        i = n;
                    }
                    else txt += line;
                }
            }
            if (llList2String(llGetLinkPrimitiveParams(dl, [PRIM_TEXT]), 0) != txt)
                llSetLinkPrimitiveParamsFast(dl, [PRIM_TEXT, txt, <0.85, 0.6, 0.4>, 0.85]);
        }
    }
}

links()
{
    F_LINK = [-1, -1, -1, -1, -1, -1, -1]; D_LINK = F_LINK; BELL_LINK = -1;
    integer n = llGetObjectPrimCount(llGetKey());
    PRIMS = n;
    integer i;
    for (i = 1; i <= n; ++i)
    {
        string nm = piece(i);
        integer c = llListFindList(CELLS, [llGetSubString(nm, 0, 2)]);
        string part = llGetSubString(nm, 3, -1);
        if (c != -1 && part == "_Floor") F_LINK = llListReplaceList(F_LINK, [i], c, c);
        else if (c != -1 && part == "_Door") D_LINK = llListReplaceList(D_LINK, [i], c, c);
        else if (nm == "G_Winch") BELL_LINK = i;
    }
}

// ------------------------------------------------------------- notecard lines
index(integer code, integer line)
{
    integer n = llGetListLength(IDX);
    if (n)
    {
        integer e = llList2Integer(IDX, -1);
        if ((e >> 20) == code && ((e >> 8) & 4095) + (e & 255) == line && (e & 255) < 255)
        {
            IDX = llListReplaceList(IDX, [e + 1], -1, -1);
            return;
        }
    }
    if (n < 300) IDX += (code << 20) | (line << 8) | 1;
}

integer pick(integer code)
{
    integer n = llGetListLength(IDX);
    integer total = 0; integer i;
    for (i = 0; i < n; ++i)
    {
        integer e = llList2Integer(IDX, i);
        if ((e >> 20) == code) total += e & 255;
    }
    if (!total) return -1;
    integer r = (integer)llFrand((float)total);
    for (i = 0; i < n; ++i)
    {
        integer e = llList2Integer(IDX, i);
        if ((e >> 20) == code)
        {
            if (r < (e & 255)) return ((e >> 8) & 4095) + r;
            r -= e & 255;
        }
    }
    return -1;
}

parse(string d, integer line)
{
    d = llStringTrim(d, STRING_TRIM);
    if (llGetSubString(d, 0, 0) == "#" || line > 4095) return;
    list p = llParseStringKeepNulls(d, ["|"], []);
    if (llGetListLength(p) < 3) return;
    string t = llToUpper(llStringTrim(llList2String(p, 0), STRING_TRIM));
    string f = llGetSubString(llStringTrim(llList2String(p, 1), STRING_TRIM), 0, 19);
    integer code = -1;
    if (t == "BELL")
    {
        code = llListFindList(EVENTS, [llToUpper(f)]);
        if (code != -1) ++BELLS;
    }
    else if (t == "CHORE" && f != "" && llListFindList(["Examine", "Carve", "Close"], [f]) == -1)
    {
        code = llListFindList(CHORE_B, [f]);
        if (code == -1 && llGetListLength(CHORE_B) < 9) { code = llGetListLength(CHORE_B); CHORE_B += f; }
        if (code != -1) code += 16;
    }
    else if (t == "GUARD" && f != "" && llListFindList(["Examine", "Close"], [f]) == -1)
    {
        code = llListFindList(GUARD_B, [f]);
        if (code == -1 && llGetListLength(GUARD_B) < 9) { code = llGetListLength(GUARD_B); GUARD_B += f; }
        if (code != -1) code += 32;
    }
    if (code != -1) index(code, line);
}

read_card()
{
    IDX = []; CHORE_B = []; GUARD_B = []; BELLS = 0; LINE = 0; Q = NULL_KEY;
    CARD_KEY = llGetInventoryKey(CARD);
    if (llGetInventoryType(CARD) == INVENTORY_NOTECARD) Q = llGetNotecardLine(CARD, 0);
    else report();      // pit_examine tells the owner how to add it
}

// says a line of the notecard (BELL: event; CHORE: 16 + button; GUARD: 32 + button) or the built-in one;
// l = 0: to the whole parcel. "after" follows the line (a result, the roll call...)
say(integer code, string def, integer l, key k, string target, string t, string after)
{
    string data = (string)l + "|" + (string)k + "|" + target + "|" + t + "|" + after;
    integer line = pick(code);
    if (line == -1 || llGetInventoryType(CARD) != INVENTORY_NOTECARD) { told(data, def); return; }
    string d = llGetNotecardLineSync(CARD, line);
    if (d == NAK)
    {
        REQ += [llGetNotecardLine(CARD, line), data];
        if (llGetListLength(REQ) > 20) REQ = llList2List(REQ, -20, -1);    // 10 lines
    }
    else told(data, rest(llParseStringKeepNulls(d, ["|"], []), 2));
}

told(string data, string txt)
{
    list x = llParseStringKeepNulls(data, ["|"], []);
    integer l = (integer)llList2String(x, 0);
    key k = (key)llList2String(x, 1);
    string w = "the jailer";
    if (k) w = who(k);
    txt = llReplaceSubString(txt, "{who}", w, 0);
    txt = llReplaceSubString(txt, "{target}", llList2String(x, 2), 0);
    txt = llReplaceSubString(txt, "{cell}", room(llList2String(x, 3)), 0);
    string after = rest(x, 4);
    if (l == 0)
    {
        if (txt != "") parcel(txt);
        if (after != "") parcel(after);
    }
    else
    {
        if (txt != "") narrate(l, k, txt);
        if (after != "") narrate(l, k, after);
    }
}

// ------------------------------------------------------------- cell life and guards
dialog(key k, integer l, string mode, string data, string txt, list b)
{
    integer i = llListFindList(SESS, [k]);
    if (i != -1) SESS = llDeleteSubList(SESS, i, i + 4);
    SESS += [k, l, mode, llGetUnixTime() + 120, data];
    if (mode == "stash") llTextBox(k, txt, CH);
    else llDialog(k, txt, b, CH);
}

list buttons(integer g)
{
    list b = CHORE_B; list d = CHORE_DEF;
    if (g) { b = GUARD_B; d = GUARD_DEF; }
    if (b == []) b = llList2ListStrided(d, 0, -1, 2);
    return llList2List(b, 0, 8);
}

string def_text(integer g, integer bi)
{
    if (g) return llList2String(GUARD_DEF, bi * 2 + 1);
    return llList2String(CHORE_DEF, bi * 2 + 1);
}

// the other inmates of the cell, by name
string others(key k, string t)
{
    list ks = inmates_of(t);
    integer i = llListFindList(ks, [(string)k]);
    if (i != -1) ks = llDeleteSubList(ks, i, i);
    return names(ks);
}

life_menu(key k, integer l, string t, string sp)
{
    list r = rec(k);
    string s = "CELL LIFE - " + room(t) + "\nInmate No." + llList2String(r, 0) + ", day " + (string)day(r) + " ("
        + (string)((integer)llList2String(r, 4) / 3600) + " h locked in)\nLast meal " + (string)hours(r, 5)
        + " h ago - filth " + filth(r) + " - tally " + llList2String(r, 7);
    if (llLinksetDataRead("stash:" + t) != "") s += "\nSomething is hidden in the straw.";
    list b = buttons(FALSE);
    if (opt("examine")) b += "Examine";
    if (opt("carvings")) b += "Carve";
    dialog(k, l, "life", t + "|" + sp, s, b + ["Close"]);
}

guard_menu(key k, integer l, string t, string sp)
{
    string s = "THE GUARD - " + room(t);
    list ks = inmates_of(t);
    integer i;
    for (i = 0; i < llGetListLength(ks); ++i)
    {
        list r = rec((key)llList2String(ks, i));
        string line = "\nNo." + llList2String(r, 0) + " " + llList2String(r, 1) + ": day " + (string)day(r) + ", fed "
            + (string)hours(r, 5) + " h ago, filth " + filth(r);
        if (utf8(s + line) < 480) s += line;
    }
    list b = buttons(TRUE);
    if (opt("examine")) b += "Examine";
    dialog(k, l, "guard", t + "|" + sp, s, b + ["Close"]);
}

knock(key k, string t)
{
    list nb = llParseString2List(llList2String(NEIGH, llListFindList(CELLS, [t])), [","], []);
    string s = "Three knocks come through the wall from " + room(t) + ": inmate No." + llList2String(rec(k), 0)
        + " is still alive.";
    integer i;
    for (i = 0; i < llGetListLength(nb); ++i)
    {
        list ks = inmates_of(llList2String(nb, i));
        integer j;
        for (j = 0; j < llGetListLength(ks); ++j) llRegionSayTo((key)llList2String(ks, j), 0, s);
    }
}

string search(key k, string t)
{
    integer d = 1 + (integer)llFrand(20.0);
    list s = llParseStringKeepNulls(llLinksetDataRead("stash:" + t), ["|"], []);
    if (llGetListLength(s) >= 3 && d >= STASH_DC)
    {
        llLinksetDataDelete("stash:" + t);
        llRegionSayTo(k, 0, "Hidden in the straw, left by " + llList2String(s, 0) + ": \"" + rest(s, 2) + "\"");
        return who(k) + " pulls something out of the straw! (d20 = " + (string)d + ")";
    }
    return who(k) + " finds nothing but lice and old bones. (d20 = " + (string)d + ")";
}

record(key k, string t, list ks)
{
    string s = "THE JAILER'S RECORD - " + room(t);
    integer i;
    for (i = 0; i < llGetListLength(ks); ++i)
    {
        list r = rec((key)llList2String(ks, i));
        string line = "\n\nNo." + llList2String(r, 0) + " " + llList2String(r, 1) + "\nDay " + (string)day(r) + ", "
            + (string)((integer)llList2String(r, 4) / 3600) + " h locked in. Last meal " + (string)hours(r, 5)
            + " h ago, last wash " + (string)hours(r, 6) + " h ago. Tally: " + llList2String(r, 7) + ".";
        if (utf8(s + line) < 500) s += line;
    }
    llDialog(k, s, ["Close"], CH);
}

act(key k, integer l, string t, integer g, integer bi, string b)
{
    string lb = llToLower(b);
    list ks = inmates_of(t);
    string target = others(k, t);
    string after = "";
    integer i;
    if (!g)
    {
        if (has(lb, ["tally", "scratch", "mark"])) mark(k, 7);
        else if (has(lb, ["wash", "scrub", "bucket", "douse"])) mark(k, 6);
        else if (has(lb, ["knock"])) knock(k, t);
        else if (has(lb, ["hide", "stash"]))
        {
            dialog(k, l, "stash", t + "|" + (string)bi, "What do you hide in the straw of " + room(t)
                   + "? A few words (60 characters): a note, a name, where the key is...", []);
            return;
        }
    }
    else
    {
        target = names(ks);
        if (has(lb, ["feed", "ration", "slop", "bread"])) for (i = 0; i < llGetListLength(ks); ++i) mark((key)llList2String(ks, i), 5);
        else if (has(lb, ["douse", "wash", "scrub", "bucket"])) for (i = 0; i < llGetListLength(ks); ++i) mark((key)llList2String(ks, i), 6);
        else if (has(lb, ["search"])) after = search(k, t);
        else if (has(lb, ["record"])) record(k, t, ks);
    }
    say(16 + 16 * g + bi, def_text(g, bi), l, k, target, t, after);
    signs();
}

stash(key k, integer l, string t, integer bi, string m)
{
    m = llStringTrim(llGetSubString(llDumpList2String(llParseString2List(m, ["\n", "|"], []), " "), 0, 59), STRING_TRIM);
    if (m == "" || where(k) != t) return;
    list old = llParseStringKeepNulls(llLinksetDataRead("stash:" + t), ["|"], []);
    if (llGetListLength(old) >= 3 && llList2String(old, 0) != clean(who(k)))
        llRegionSayTo(k, 0, "Deep in the straw your fingers find what someone hid before you, " + llList2String(old, 0)
            + ": \"" + rest(old, 2) + "\". You take it.");
    llLinksetDataWrite("stash:" + t, clean(who(k)) + "|" + (string)llGetUnixTime() + "|" + m);
    say(16 + bi, def_text(FALSE, bi), l, k, others(k, t), t, "");
}

// ------------------------------------------------------------- routines
string rollcall()
{
    string s = ""; integer n = 0; integer c;
    for (c = 0; c < 7; ++c)
    {
        string t = llList2String(CELLS, c);
        list ks = inmates_of(t);
        integer i;
        for (i = 0; i < llGetListLength(ks); ++i)
        {
            list r = rec((key)llList2String(ks, i));
            string one = "No." + llList2String(r, 0) + " " + llList2String(r, 1) + " (" + room(t) + ", day " + (string)day(r) + ")";
            if (utf8(s + one) < 900)
            {
                if (n) s += ", ";
                s += one;
            }
            ++n;
        }
    }
    if (!n) return "Roll call: every cell is empty. The jailer spits and walks on.";
    return "Roll call - " + (string)n + " in the cells: " + s + ".";
}

ring(integer ev)
{
    string after = "";
    if (ev == 0 && opt("moods")) llMessageLinked(LINK_SET, 9200, "WATCH", NULL_KEY);
    else if (ev == 3 && opt("moods")) llMessageLinked(LINK_SET, 9200, "GLOOM", NULL_KEY);
    else if (ev == 1)
    {
        integer c;
        for (c = 0; c < 7; ++c)
        {
            list ks = inmates_of(llList2String(CELLS, c));
            integer i;
            for (i = 0; i < llGetListLength(ks); ++i) mark((key)llList2String(ks, i), 5);
        }
    }
    else if (ev == 2) after = rollcall();
    if (ev != 4 && opt("sounds") && BELL_LINK > 0)
    {
        string s = "pit_press_gang_bell";
        if (llGetInventoryType(s) != INVENTORY_SOUND) s = "press_gang_bell";
        if (llGetInventoryType(s) == INVENTORY_SOUND) llLinkPlaySound(BELL_LINK, s, 0.8, SOUND_PLAY);
    }
    say(ev, llList2String(BELL_DEF, ev), 0, NULL_KEY, "", "", after);
    signs();
}

routines()
{
    if (!opt("routines") || llGetAgentList(AGENT_LIST_PARCEL, []) == []) return;
    integer wc = (integer)llGetWallclock();
    integer today = (llGetUnixTime() - wc + 43200) / 86400;      // one number per Pacific day
    list done = llParseStringKeepNulls(llLinksetDataRead("bell_days"), [","], []);
    while (llGetListLength(done) < 9) done += "0";
    integer s;
    for (s = 0; s < 9; ++s)
    {
        integer t = llList2Integer(SLOTS, s * 2);
        if (wc >= t && wc < t + WINDOW && (integer)llList2String(done, s) != today)
        {
            done = llListReplaceList(done, [(string)today], s, s);
            llLinksetDataWrite("bell_days", llDumpList2String(done, ","));
            ring(llList2Integer(SLOTS, s * 2 + 1));
        }
    }
}

// ------------------------------------------------------------- owner
roster()
{
    integer i = 0; integer n = 0; string out = ""; list ks;
    while ((ks = llLinksetDataFindKeys("^inmate:", i, 8)) != [])
    {
        integer j;
        for (j = 0; j < llGetListLength(ks); ++j)
        {
            list r = llParseStringKeepNulls(llLinksetDataRead(llList2String(ks, j)), ["|"], []);
            string line = "\nNo." + llList2String(r, 0) + " " + llList2String(r, 1) + " - " + room(llList2String(r, 2))
                + ", day " + (string)day(r) + ", " + (string)((integer)llList2String(r, 4) / 3600) + " h locked in, fed "
                + (string)hours(r, 5) + " h ago, filth " + filth(r) + ", tally " + llList2String(r, 7) + ", last seen "
                + (string)((llGetUnixTime() - (integer)llList2String(r, 8)) / 3600) + " h ago";
            if (utf8(out + line) > 1000) { llOwnerSay(out); out = ""; }
            out += line;
            ++n;
        }
        i += llGetListLength(ks);
    }
    llOwnerSay("pit_life: " + (string)n + " inmates on record, " + (string)JAILED + " locked in now." + out);
}

release(integer num)
{
    integer i = 0; list ks;
    while ((ks = llLinksetDataFindKeys("^inmate:", i, 10)) != [])
    {
        integer j;
        for (j = 0; j < llGetListLength(ks); ++j)
        {
            string id = llList2String(ks, j);
            list r = llParseStringKeepNulls(llLinksetDataRead(id), ["|"], []);
            if ((integer)llList2String(r, 0) == num)
            {
                key k = (key)llGetSubString(id, 7, -1);
                llLinksetDataDelete(id);
                string msg = "inmate No." + (string)num + " " + llList2String(r, 1) + " is struck from the register";
                string t = where(k);
                if (t != "")
                {
                    PARDON += k;
                    if (llGetListLength(inmates_of(t)) == 1)
                    {
                        llLinksetDataDelete("lock:" + t);     // pit_doors reads the lock from here
                        msg += " and the lock of " + room(t) + " clicks open";
                    }
                    narrate(llList2Integer(D_LINK, llListFindList(CELLS, [t])), k, "By order of the Lord of the Pit, " + msg + ".");
                }
                llOwnerSay("pit_life: " + msg + ".");
                census();
                return;
            }
        }
        i += llGetListLength(ks);
    }
    llOwnerSay("pit_life: there is no inmate No." + (string)num + ". /7 inmates lists them.");
}

report()
{
    integer cells = 0; integer i;
    for (i = 0; i < 7; ++i) if (llList2Integer(F_LINK, i) > 0 && llList2Integer(D_LINK, i) > 0) ++cells;
    string s = "pit_life: " + (string)cells + " of 7 cells found, " + (string)JAILED + " inmates locked in now, "
        + (string)llLinksetDataCountFound("^inmate:") + " records (" + (string)MAX_RECORDS + " at most); ";
    if (llGetInventoryType(CARD) != INVENTORY_NOTECARD) s += "no notecard pit_lore: built-in lines";
    else s += "notecard: " + (string)llGetListLength(CHORE_B) + " chores, " + (string)llGetListLength(GUARD_B)
        + " guard actions, " + (string)BELLS + " bell lines";
    if (cells < 7) s += ". MISSING CELLS: the pieces still have their old names - is pit_core in the root?";
    llOwnerSay(s + " - memory " + (string)(llGetUsedMemory() / 1024) + " of 64 KB.");
}

default
{
    state_entry()
    {
        CH = -1 - (integer)llFrand(1000000.0);
        llListen(CH, "", NULL_KEY, "");
        llListen(7, "", llGetOwner(), "");
        OPTS = llLinksetDataRead("opts");
        LAST = llGetUnixTime();
        links();
        census();
        llSetTimerEvent((float)SCAN);
        read_card();
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c)
    {
        if (c & CHANGED_OWNER) llResetScript();
        // sitting down or standing up also raises CHANGED_LINK: look again only if the prims changed
        if ((c & CHANGED_LINK) && llGetObjectPrimCount(llGetKey()) != PRIMS) links();
        // a new or edited notecard has a new key (no key at all if it is not full permission)
        if ((c & CHANGED_INVENTORY) && (llGetInventoryKey(CARD) != CARD_KEY
            || (CARD_KEY == NULL_KEY && llGetInventoryType(CARD) == INVENTORY_NOTECARD))) read_card();
    }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET)
        {
            OPTS = llLinksetDataRead("opts");
            census();
        }
        else if (llSubStringIndex(name, "lock:") == 0) census();      // a cell locked or unlocked: count at once
    }

    link_message(integer s, integer n, string str, key id)
    {
        if (n == 9001) { links(); census(); }
        else if (n == 9800) report();
        else if (n == 9510)
        {
            // "fed|C05", "washed|<avatar key>": a meal or a wash given by another script
            list p = llParseString2List(str, ["|"], []);
            integer f = llListFindList(["fed", "washed"], [llList2String(p, 0)]);
            string t = llList2String(p, 1);
            if (f == -1) return;
            list ks = [t];
            if (llStringLength(t) == 3)
            {
                if (t == "C06") t = "C05";
                ks = inmates_of(t);
            }
            integer i;
            for (i = 0; i < llGetListLength(ks); ++i) mark((key)llList2String(ks, i), 5 + f);
            signs();
        }
    }

    touch_start(integer total)
    {
        key k = llDetectedKey(0);
        integer l = llDetectedLinkNumber(0);
        if (l == 1 && k == llGetOwner()) return;        // pit_core: the owner's doorway test
        string nm = piece(l);
        string t = cell_of(nm);
        if (owned(nm) || t == "" || !opt("inmates") || !opt("cell_life")) return;
        // the touched spot, for Examine and Carve: face|x,y,z in cm in the root's frame
        vector p = llDetectedTouchPos(0);
        if (p == TOUCH_INVALID_VECTOR || p == ZERO_VECTOR) p = llList2Vector(llGetLinkPrimitiveParams(l, [PRIM_POSITION]), 0);
        p = (p - llGetRootPosition()) / llGetRootRotation();
        string sp = (string)llDetectedTouchFace(0) + "|" + (string)llRound(p.x * 100.0) + "," + (string)llRound(p.y * 100.0)
            + "," + (string)llRound(p.z * 100.0);
        string mine = where(k);
        if (mine != "") life_menu(k, l, mine, sp);
        else if (llLinksetDataRead("jail:" + t) != "") guard_menu(k, l, t, sp);
    }

    listen(integer c, string n, key id, string m)
    {
        if (c == 7)
        {
            m = llToLower(llStringTrim(m, STRING_TRIM));
            if (m == "inmates") roster();
            else if (llSubStringIndex(m, "inmate release ") == 0) release((integer)llGetSubString(m, 15, -1));
            else if (m == "lore") read_card();
            return;
        }
        integer si = llListFindList(SESS, [id]);
        if (si == -1 || llList2Integer(SESS, si + 3) < llGetUnixTime()) return;
        integer l = llList2Integer(SESS, si + 1);
        string mode = llList2String(SESS, si + 2);
        list x = llParseStringKeepNulls(llList2String(SESS, si + 4), ["|"], []);
        SESS = llDeleteSubList(SESS, si, si + 4);
        string t = llList2String(x, 0);
        if (mode == "stash") { stash(id, l, t, (integer)llList2String(x, 1), m); return; }
        string sp = (string)l + "|" + llList2String(x, 1) + "|" + llList2String(x, 2);
        if (m == "Examine" && opt("examine")) { llMessageLinked(LINK_SET, 9500, "examine|" + sp, id); return; }
        if (m == "Carve" && opt("carvings")) { llMessageLinked(LINK_SET, 9500, "carve|" + sp, id); return; }
        integer g = (mode == "guard");
        integer bi = llListFindList(buttons(g), [m]);
        if (bi == -1 || !opt("inmates") || !opt("cell_life")) return;
        // things may have changed while the menu was open
        if (g && llLinksetDataRead("jail:" + t) == "") return;
        if (!g && where(id) != t) return;
        act(id, l, t, g, bi, m);
    }

    dataserver(key id, string d)
    {
        if (id == Q)
        {
            while (d != EOF && d != NAK)
            {
                parse(d, LINE);
                d = llGetNotecardLineSync(CARD, ++LINE);
            }
            if (d == NAK) Q = llGetNotecardLine(CARD, LINE);
            else
            {
                Q = NULL_KEY;
                report();
            }
            return;
        }
        integer i = llListFindList(REQ, [id]);
        if (i == -1) return;
        string data = llList2String(REQ, i + 1);
        REQ = llDeleteSubList(REQ, i, i + 1);
        told(data, rest(llParseStringKeepNulls(d, ["|"], []), 2));
    }

    timer()
    {
        integer now = llGetUnixTime();
        integer i;
        for (i = llGetListLength(SESS) - 5; i >= 0; i -= 5)
            if (llList2Integer(SESS, i + 3) < now) SESS = llDeleteSubList(SESS, i, i + 4);
        // nobody about and nobody locked in: rest
        if (llGetAgentList(AGENT_LIST_PARCEL, []) == [] && !JAILED) return;
        census();
        routines();
        if (now > PRUNE_AT)
        {
            PRUNE_AT = now + 3600;
            prune();
        }
    }
}

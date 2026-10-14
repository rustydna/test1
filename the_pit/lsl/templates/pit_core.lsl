// =====================================================================
//  THE PIT - CORE (root prim; put it in first)
//
//  1. Recognises all 143 pieces even if Second Life lost their names on
//     upload: it compares each prim's size and position (measured from
//     the throne) with the model table and gives it its proper name.
//     Pieces from the first release are renamed the same way, so an
//     already uploaded build does NOT need to be uploaded again.
//  2. Physics: structure -> Prim; doors and furniture -> Convex Hull;
//     decoration, lights and water -> None.
//     (Even if this script never ran, every room can be entered: no
//     piece's convex hull blocks a passage.)
//  3. Self-test: casts rays through every doorway and reports anything
//     solid in the way.
//  4. Tells the other scripts (link_message 9001) to get ready.
//
//  Switches (/7 settings > System): rename, physics, diagnose.
//  Owner: touch the root prim or type /7 diagnose to repeat the test.
// =====================================================================

//@@TABLE@@

string OPTS;
integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

string name_from_table(integer link, vector rel)
{
    vector size = llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_SIZE]), 0);
    integer n = llGetListLength(TABLE);
    integer i;
    float best = 999.0; string found = "";
    for (i = 0; i < n; i += 4)
    {
        vector ts = llList2Vector(TABLE, i + 2);
        if (llFabs(ts.x - size.x) < 0.04 && llFabs(ts.y - size.y) < 0.04 && llFabs(ts.z - size.z) < 0.04)
        {
            float d = llVecDist(llList2Vector(TABLE, i + 3), rel);
            if (d < best) { best = d; found = llList2String(TABLE, i); }
        }
    }
    if (best < 0.3) return found;
    return "";
}

integer kind_of(string name)
{
    integer i = llListFindList(TABLE, [name]);
    if (i == -1) return -1;
    return llList2Integer(TABLE, i + 1);
}

recognise()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i; integer named = 0;
    for (i = 1; i <= n; ++i) if (kind_of(llGetLinkName(i)) != -1) ++named;
    integer renamed = 0;
    if (named < n * 9 / 10)
    {
        // find the throne by its unique size and measure everything from it
        integer throne = -1;
        vector ts = llList2Vector(TABLE, llListFindList(TABLE, ["N_Throne"]) + 2);
        for (i = 1; i <= n && throne == -1; ++i)
        {
            vector s = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_SIZE]), 0);
            if (llVecDist(s, ts) < 0.03) throne = i;
        }
        if (throne == -1)
        {
            llOwnerSay("Can't find the throne by its size: was the build rescaled? Upload it at scale 1.0.");
            return;
        }
        vector base = ZERO_VECTOR; rotation trot = ZERO_ROTATION;
        if (throne > 1)
        {
            list t = llGetLinkPrimitiveParams(throne, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
            base = llList2Vector(t, 0); trot = llList2Rot(t, 1);
        }
        for (i = 1; i <= n; ++i)
        {
            vector p = ZERO_VECTOR;
            if (i > 1) p = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0);
            string nm = name_from_table(i, (p - base) / trot);
            if (nm != "" && nm != llGetLinkName(i))
            {
                llSetLinkPrimitiveParamsFast(i, [PRIM_NAME, nm]);
                ++renamed;
            }
        }
    }
    llOwnerSay("pit_core: " + (string)n + " pieces, " + (string)renamed + " renamed to their English names.");
}

physics()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i; integer c0 = 0; integer c1 = 0; integer c2 = 0;
    for (i = 1; i <= n; ++i)
    {
        integer t = kind_of(llGetLinkName(i));
        integer shape = PRIM_PHYSICS_SHAPE_PRIM;
        if (t == 1 || t == 4) shape = PRIM_PHYSICS_SHAPE_CONVEX;
        else if (t == 2 || t == 3 || t == 5) shape = PRIM_PHYSICS_SHAPE_NONE;
        if (i == 1 && shape == PRIM_PHYSICS_SHAPE_NONE) shape = PRIM_PHYSICS_SHAPE_CONVEX;
        llSetLinkPrimitiveParamsFast(i, [PRIM_PHYSICS_SHAPE_TYPE, shape]);
        if (shape == PRIM_PHYSICS_SHAPE_PRIM) ++c0;
        else if (shape == PRIM_PHYSICS_SHAPE_CONVEX) ++c1;
        else ++c2;
    }
    llOwnerSay("Physics: Prim " + (string)c0 + ", Convex " + (string)c1 + ", None " + (string)c2 + ".");
}

diagnose()
{
    // horizontal rays at 0.5 / 1.1 / 1.7 m through every cell door, from the yard to the back of the room
    integer n = llGetObjectPrimCount(llGetKey());
    list doors = [];
    float sum = 0.0;
    integer i;
    for (i = 2; i <= n; ++i)
        if (llSubStringIndex(llGetLinkName(i), "_Door") != -1)
        {
            vector dp = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0);
            doors += i;
            sum += dp.x;
        }
    if (doors == []) { llOwnerSay("Diagnose: no cell doors found (type /7 doors)."); return; }
    float centre = sum / llGetListLength(doors);
    vector rp = llGetRootPosition(); rotation rr = llGetRootRotation();
    integer bad = 0;
    for (i = 0; i < llGetListLength(doors); ++i)
    {
        integer l = llList2Integer(doors, i);
        list d = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_SIZE]);
        vector p = llList2Vector(d, 0);
        float dir = 1.0; if (p.x > centre) dir = -1.0;   // towards the inside of the room
        float z;
        for (z = -0.8; z < 0.6; z += 0.6)
        {
            vector a = rp + (p + <-dir * 2.0, 0.3, z>) * rr;
            vector b = rp + (p + < dir * 2.0, 0.3, z>) * rr;
            list hits = llCastRay(a, b, [RC_REJECT_TYPES, RC_REJECT_AGENTS | RC_REJECT_LAND,
                                         RC_DATA_FLAGS, RC_GET_LINK_NUM, RC_MAX_HITS, 4]);
            integer h = llList2Integer(hits, -1);
            integer j;
            for (j = 0; j < h; ++j)
            {
                integer hl = llList2Integer(hits, j * 3 + 2);
                if (llList2Key(hits, j * 3) == llGetKey() && hl != l)
                {
                    llOwnerSay("WARNING: the doorway of " + llGetLinkName(l) + " hits " + llGetLinkName(hl)
                        + " at " + (string)((integer)((z + 1.33) * 100)) + " cm above the floor.");
                    ++bad;
                }
            }
        }
    }
    if (bad == 0) llOwnerSay("Diagnose: all " + (string)llGetListLength(doors)
        + " doorways are clear (with the door open).");
}

// One-time upgrade of the data stored by the first release (same values, English key names).
upgrade()
{
    if (llLinksetDataRead("pit_version") == "4") return;
    list ren = ["^p:", "lock:", "^leva:", "muster:", "^num:", "recruit:", "^marcas:", "brands:"];
    integer r;
    for (r = 0; r < llGetListLength(ren); r += 2)
    {
        list ks = llLinksetDataFindKeys(llList2String(ren, r), 0, 0);
        integer i;
        for (i = 0; i < llGetListLength(ks); ++i)
        {
            string k = llList2String(ks, i);
            llLinksetDataWrite(llList2String(ren, r + 1) + llGetSubString(k, llSubStringIndex(k, ":") + 1, -1),
                               llLinksetDataRead(k));
            llLinksetDataDelete(k);
        }
    }
    string count = llLinksetDataRead("reclutas");
    if (count != "") llLinksetDataWrite("recruits", count);
    list junk = llLinksetDataFindKeys("^(cerr:|sit:|senor$|potro$|azotes$|silla|reclutas$|C0[57]_)", 0, 0);
    integer j;
    for (j = 0; j < llGetListLength(junk); ++j) llLinksetDataDelete(llList2String(junk, j));
    llLinksetDataWrite("pit_version", "4");
}

default
{
    state_entry()
    {
        OPTS = llLinksetDataRead("opts");
        llOwnerSay("The Pit: getting ready...");
        upgrade();
        if (opt("rename")) recognise();
        if (opt("physics")) physics();
        llSleep(1.5);
        if (opt("diagnose")) diagnose();
        llMessageLinked(LINK_SET, 9001, "ready", NULL_KEY);
        llListen(7, "", llGetOwner(), "diagnose");
        llOwnerSay("pit_core ready" + " - memory " + (string)(llGetUsedMemory() / 1024) + " of 64 KB." + " Type /7 report for every script's status, /7 help for all commands.");
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if (c & CHANGED_OWNER) llResetScript(); }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) OPTS = llLinksetDataRead("opts");
    }
    listen(integer c, string n, key id, string m) { diagnose(); }
    touch_start(integer t)
    {
        if (llDetectedKey(0) == llGetOwner() && llDetectedLinkNumber(0) == 1) diagnose();
    }
}

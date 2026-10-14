// =====================================================================
//  THE PIT - PBR MATERIALS BY BLOCK (root prim)
//
//  Every piece has the same faces in the same order:
//    0 Stone · 1 Floor · 2 Wood · 3 Iron · 4 Cloth (and leather)
//    5 Bone  · 6 Straw · 7 Flame
//  and the water has pieces of its own (P_Water, C04_Water).
//
//  HOW TO USE: drop the PBR materials into the build's Contents tab (the
//  same tab that holds the scripts). They are applied AT ONCE, to every
//  piece, without touching anything:
//    * If there is a notecard called "materials", the notecard rules:
//          Stone = material name in the Contents (or its UUID)
//      (a ready-made one is in lsl/materials_notecard.txt)
//    * With no notecard, each material is matched by its name: the one
//      whose name contains "stone" goes on the stone, "iron" on the iron,
//      and so on (upper/lower case doesn't matter). With The Pit's .glb
//      files (Stone, Floor, Wood, Iron, Cloth, Bone, Straw, Water) no
//      notecard is needed.
//  To apply again: type /7 materials in chat.
//  Face 7 (flame) belongs to the fire script: don't put PBR on it.
//  Switch (/7 settings > System): auto_materials. Off = only /7 materials
//  applies them.
// =====================================================================

list BLOCKS = ["Stone", "Floor", "Wood", "Iron", "Cloth", "Bone", "Straw", "Water"];
list ASSIGN;   // [block, material]
key Q; integer LINE;
string OPTS;
integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

// inventory types that are NOT materials (anything else is taken as a material)
integer not_material(integer t)
{
    return t == INVENTORY_SCRIPT || t == INVENTORY_NOTECARD || t == INVENTORY_TEXTURE
        || t == INVENTORY_ANIMATION || t == INVENTORY_SOUND || t == INVENTORY_OBJECT
        || t == INVENTORY_LANDMARK || t == INVENTORY_CLOTHING || t == INVENTORY_BODYPART
        || t == INVENTORY_GESTURE || t == INVENTORY_SETTING || t == INVENTORY_NONE;
}

by_name()
{
    // each block gets the first material whose name contains the block's name
    ASSIGN = [];
    integer n = llGetInventoryNumber(INVENTORY_ALL);
    integer b;
    for (b = 0; b < llGetListLength(BLOCKS); ++b)
    {
        string block = llList2String(BLOCKS, b);
        integer i;
        for (i = 0; i < n; ++i)
        {
            string it = llGetInventoryName(INVENTORY_ALL, i);
            if (!not_material(llGetInventoryType(it))
                && llSubStringIndex(llToLower(it), llToLower(block)) != -1
                && llListFindList(ASSIGN, [block]) == -1)
                ASSIGN += [block, it];
        }
    }
    apply();
}

start()
{
    if (llGetInventoryType("materials") == INVENTORY_NOTECARD)
    {
        ASSIGN = []; LINE = 0;
        Q = llGetNotecardLine("materials", LINE);
    }
    else by_name();
}

apply()
{
    if (ASSIGN == [])
    {
        llOwnerSay("Materials: none found. Drop the PBR materials (Stone, Floor, Wood, Iron, Cloth, Bone, "
            + "Straw, Water) into the build's Contents tab.");
        return;
    }
    integer n = llGetObjectPrimCount(llGetKey());
    integer link; integer done = 0;
    for (link = 1; link <= n; ++link)
    {
        string nm = llGetLinkName(link);
        list rules = [];
        if (llSubStringIndex(nm, "_Water") != -1)
        {
            integer j = llListFindList(ASSIGN, ["Water"]);
            if (j != -1) rules = [PRIM_RENDER_MATERIAL, ALL_SIDES, llList2String(ASSIGN, j + 1)];
        }
        else
        {
            integer c;
            for (c = 0; c < 7; ++c)
            {
                integer j = llListFindList(ASSIGN, [llList2String(BLOCKS, c)]);
                if (j != -1) rules += [PRIM_RENDER_MATERIAL, c, llList2String(ASSIGN, j + 1)];
            }
        }
        if (rules != []) { llSetLinkPrimitiveParamsFast(link, rules); ++done; }
    }
    string summary = "";
    integer b;
    for (b = 0; b < llGetListLength(BLOCKS); ++b)
    {
        string block = llList2String(BLOCKS, b);
        integer j = llListFindList(ASSIGN, [block]);
        if (j == -1) summary += block + ": MISSING  ";
        else summary += block + " = " + llList2String(ASSIGN, j + 1) + "  ";
    }
    llOwnerSay("Materials applied to " + (string)done + " pieces. " + summary);
}

default
{
    state_entry()
    {
        OPTS = llLinksetDataRead("opts");
        llListen(7, "", llGetOwner(), "materials");
        if (opt("auto_materials")) start();
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if ((c & CHANGED_INVENTORY) && opt("auto_materials")) start(); }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) OPTS = llLinksetDataRead("opts");
    }
    listen(integer c, string n, key id, string m) { start(); }
    dataserver(key id, string d)
    {
        if (id != Q) return;
        if (d == EOF)
        {
            if (ASSIGN == []) by_name(); else apply();
            return;
        }
        list p = llParseString2List(d, ["="], []);
        if (llGetListLength(p) == 2)
            ASSIGN += [llStringTrim(llList2String(p, 0), STRING_TRIM), llStringTrim(llList2String(p, 1), STRING_TRIM)];
        Q = llGetNotecardLine("materials", ++LINE);
    }
}

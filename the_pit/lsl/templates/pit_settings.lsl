// =====================================================================
//  THE PIT - SETTINGS (root prim)
//
//  Every feature of The Pit can be switched on or off by the owner.
//  The switches live in the object's linkset data (key "opts"), so they
//  take effect at once in every script, survive resets and travel with
//  copies of the build.
//
//  Owner chat commands (channel 7):
//    /7 settings            menu with every switch, by category
//    /7 off fog             switch one feature off  (/7 on fog = back on)
//    /7 status              list what is switched off
//    /7 all on | /7 all off presets: everything on / everything off
//    /7 lowlag              switch off the heavy eye-candy, keep the RP
//    /7 help                every chat command of The Pit
//  The owner also gets a "Settings" button in the throne menu.
// =====================================================================

// name, category, short description (keep descriptions under ~34 characters)
list FEATURES = [
    "fire",        0, "everything fire (master switch)",
    "flames",      0, "particle flames",
    "lights",      0, "light from torches and braziers",
    "flicker",     0, "breathing, flickering light",
    "glow",        0, "glow on the mesh flames",
    "flipbook",    0, "animated mesh flames",
    "smoke",       0, "smoke from the braziers",
    "sparks",      0, "crackles and sparks",
    "projectors",  0, "bar shadows (projector lights)",
    "gusts",       0, "draughts when doors move",
    "fog",         1, "sea fog, kennel mist, steam",
    "drips",       1, "drips falling from the vaults",
    "bursts",      1, "splash, brand sparks, clothes",
    "moods",       1, "the Lord can change the mood",
    "tide",        1, "the channel rises and falls",
    "voices",      1, "whispers in the dark (chat)",
    "sounds",      1, "ambient sounds (if you add any)",
    "doors",       2, "door, gate and portcullis menus",
    "locks",       2, "locking with a personal key",
    "sentences",   2, "timed sentences",
    "escape",      2, "pick the lock (d20)",
    "pleas",       2, "beg for mercy, rattle the bars",
    "door_sounds", 2, "door sounds (if you add any)",
    "bell",        2, "the press-gang bell",
    "board",       2, "sentence board text",
    "furniture",   3, "every furniture menu (master)",
    "rack",        3, "the rack",
    "stocks",      3, "pillory and stocks",
    "cistern",     3, "the ducking chair",
    "cages",       3, "the hanging cages",
    "mast",        3, "the whipping mast",
    "kennel",      3, "kennels and bowls",
    "guardroom",   3, "dice table, laundry basket",
    "kneeling",    3, "the kneeling stone",
    "seats",       3, "sit positions and animations",
    "throne",      4, "throne menu and Lord title",
    "lord_keys",   4, "the Lord holds every key",
    "judgement",   4, "sentencing from the throne",
    "muster_book", 4, "the press-gang muster book",
    "branding",    4, "the branding brazier",
    "narration",   5, "RP lines in local chat",
    "hovertext",   5, "floating text",
    "rename",      5, "auto-name pieces after upload",
    "physics",     5, "auto physics shapes",
    "diagnose",    5, "doorway test at start",
    "auto_materials", 5, "auto-apply PBR materials"];

list CATEGORIES = ["Fire & light", "Atmosphere", "Doors", "Rooms", "Throne", "System"];
list LOWLAG = ["flicker", "smoke", "sparks", "projectors", "gusts", "fog", "drips", "tide", "voices"];

string OPTS;        // ",fog,drips," = what is switched off; "" = everything on
integer CH; integer LH; integer PAGE = -1;

integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

save()
{
    if (OPTS == ",") OPTS = "";
    llLinksetDataWrite("opts", OPTS);   // an empty value deletes the key: everything on
}

integer known(string f)
{
    integer i = llListFindList(FEATURES, [f]);
    return i != -1 && i % 3 == 0;
}

set(string f, integer value)
{
    if (value == opt(f)) return;
    if (!value)
    {
        if (OPTS == "") OPTS = ",";
        OPTS += f + ",";
    }
    else
    {
        integer i = llSubStringIndex(OPTS, "," + f + ",");
        OPTS = llDeleteSubString(OPTS, i, i + llStringLength(f));
    }
}

string status()
{
    if (OPTS == "") return "The Pit: every feature is ON.";
    list off = llParseString2List(OPTS, [","], []);
    return "The Pit - switched OFF: " + llDumpList2String(off, ", ") + ".";
}

help()
{
    llOwnerSay("THE PIT - owner commands (channel 7):\n"
        + "/7 settings - switch any feature on or off\n"
        + "/7 off <name> | /7 on <name> - e.g. /7 off fog\n"
        + "/7 status - what is switched off\n"
        + "/7 all on | /7 all off | /7 lowlag - presets\n"
        + "/7 doors - find the doors again | /7 doors reset - forget stored door poses\n"
        + "/7 materials - apply the PBR materials now\n"
        + "/7 diagnose - check that every doorway is clear\n"
        + "Feature names: " + llDumpList2String(llList2ListStrided(FEATURES, 0, -1, 3), ", "));
}

menu(integer page)
{
    PAGE = page;
    key k = llGetOwner();
    llListenRemove(LH);
    LH = llListen(CH, "", k, "");
    llSetTimerEvent(120.0);
    if (page < 0)
    {
        llDialog(k, "THE PIT - SETTINGS\nChoose a category. Every switch is saved in the build.\n\n" + status(),
                 CATEGORIES + ["All ON", "All OFF", "Low lag", "Status", "Close"], CH);
        return;
    }
    string txt = "THE PIT - " + llList2String(CATEGORIES, page) + "\n[+] on   [-] off   (tap to switch)\n";
    list b = [];
    integer i;
    for (i = 0; i < llGetListLength(FEATURES); i += 3)
        if (llList2Integer(FEATURES, i + 1) == page)
        {
            string f = llList2String(FEATURES, i);
            string mark = "[+] ";
            if (!opt(f)) mark = "[-] ";
            b += mark + f;
            txt += "\n" + mark + f + ": " + llList2String(FEATURES, i + 2);
        }
    llDialog(k, llGetSubString(txt, 0, 500), b + ["<< Back"], CH);
}

command(string m)
{
    m = llToLower(llStringTrim(m, STRING_TRIM));
    list w = llParseString2List(m, [" "], []);
    string a = llList2String(w, 0);
    string f = llList2String(w, 1);
    if (m == "settings" || m == "menu") { menu(-1); return; }
    if (m == "help") { help(); return; }
    if (m == "status") { llOwnerSay(status()); return; }
    if (m == "all on") { OPTS = ""; save(); llOwnerSay("The Pit: every feature ON."); return; }
    if (m == "all off")
    {
        integer i; OPTS = "";
        for (i = 0; i < llGetListLength(FEATURES); i += 3) set(llList2String(FEATURES, i), FALSE);
        save(); llOwnerSay("The Pit: every feature OFF (a still build). /7 all on to bring it back.");
        return;
    }
    if (m == "lowlag")
    {
        integer i;
        for (i = 0; i < llGetListLength(LOWLAG); ++i) set(llList2String(LOWLAG, i), FALSE);
        save(); llOwnerSay(status());
        return;
    }
    if ((a == "on" || a == "off") && f != "")
    {
        if (!known(f)) { llOwnerSay("Unknown feature \"" + f + "\". Type /7 help for the list."); return; }
        set(f, a == "on");
        save();
        llOwnerSay("The Pit: " + f + " " + llToUpper(a) + ".");
    }
}

default
{
    state_entry()
    {
        CH = -1 - (integer)llFrand(1000000.0);
        OPTS = llLinksetDataRead("opts");
        llListen(7, "", llGetOwner(), "");
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if (c & CHANGED_OWNER) llResetScript(); }

    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) OPTS = llLinksetDataRead("opts");
    }

    link_message(integer s, integer n, string str, key id)
    {
        if (n == 9700 && id == llGetOwner()) menu(-1);
    }

    listen(integer c, string n, key id, string m)
    {
        if (c == 7) { command(m); return; }
        if (m == "Close") { llListenRemove(LH); return; }
        if (m == "<< Back") { menu(-1); return; }
        if (m == "Status") { llOwnerSay(status()); menu(-1); return; }
        if (m == "All ON") { command("all on"); menu(-1); return; }
        if (m == "All OFF") { command("all off"); menu(-1); return; }
        if (m == "Low lag") { command("lowlag"); menu(-1); return; }
        integer cat = llListFindList(CATEGORIES, [m]);
        if (cat != -1) { menu(cat); return; }
        string f = llGetSubString(m, 4, -1);
        if (known(f))
        {
            set(f, !opt(f));
            save();
            menu(PAGE);
        }
    }

    timer() { llListenRemove(LH); llSetTimerEvent(0.0); }
}

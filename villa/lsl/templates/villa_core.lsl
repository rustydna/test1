// villa_core - the Villa Core menu: switch houses, materials, colours, lights, pool, ambience,
// doors, access and settings. Goes in the root of the Villa Core (the totem) next to
// villa_house. The houses (uploaded models with villa_house inside) go in the Core's contents.
// Touch the totem (or any part of the villa) for the menu. Chat: /88 menu, /88 help.

//@@TABLES@@

integer CH;                       // owner's private channel to the houses (same as villa_house)
integer DCH; integer DL;          // dialog channel and listener
integer CMD_L;
key HOUSE = NULL_KEY;
key USER;
string MENU = "main";
integer SLOT;                     // slot being edited in the Style menu
integer PAGE;
integer STARTED;

string get(string k, string d) { string v = llLinksetDataRead(k); if (v == "") return d; return v; }
put(string k, string v) { llLinksetDataWrite(k, v); }
integer opt(string f) { return llSubStringIndex("," + get("opts", OPTS_DEFAULT) + ",", "," + f + ",") >= 0; }
say(string t) { if (opt("chat")) llOwnerSay(t); }

send(string cmd)
{
    llMessageLinked(LINK_THIS, 7100, cmd, "");
    if (HOUSE != NULL_KEY) llRegionSayTo(HOUSE, CH, "V|" + cmd);
}

key mat_key(integer s, string id)
{
    string nm = "villa_" + llList2String(SLOTS, s) + "_" + id;
    if (s == 8) nm = "villa_water_" + id;
    if (llGetInventoryType(nm) != INVENTORY_MATERIAL) return NULL_KEY;
    return llGetInventoryKey(nm);
}

send_mat(integer s)
{
    key k = mat_key(s, get("mat" + (string)s, llList2String(DEFAULT_MATS, s)));
    if (k != NULL_KEY) send("MAT|" + (string)s + "|" + (string)k);
}

send_state()
{
    integer s;
    for (s = 0; s <= 8; ++s) send_mat(s);
    send("OPTS|" + get("opts", OPTS_DEFAULT));
    send("ACCESS|" + get("access", "owner"));
    send("TINT|" + get("tint", "<1,1,1>"));
    scene(get("scene", "Evening"));
    send("POOL|" + get("pool", "<0.3,0.75,1>"));
    send("SPA|" + get("spa", "1"));
    send("FIRE|" + get("fire", "1"));
    send("SOUND|" + get("sound", "") + "|" + get("vol", "0.5"));
}

scene(string s)
{
    put("scene", s);
    integer i = llListFindList(SCENES, [s]);
    if (i < 0) i = 0;
    vector c = (vector)get("led", (string)llList2Vector(SCENES, i + 1));
    float lv = llList2Float(SCENES, i + 2) * (float)get("bright", "1.0");
    send("GLOW|" + (string)c + "|" + (string)lv);
}

house_style(string name)
{
    // the defaults of each house (materials) when it is rezzed
    integer i;
    for (i = 0; i < llGetListLength(HOUSE_STYLES); i += 2)
        if (llSubStringIndex(llToLower(name), llToLower(llList2String(HOUSE_STYLES, i))) >= 0)
        {
            list ids = llCSV2List(llList2String(HOUSE_STYLES, i + 1));
            integer s;
            for (s = 0; s < llGetListLength(ids); ++s) put("mat" + (string)s, llList2String(ids, s));
        }
}

list houses()
{
    list out = [];
    integer i;
    for (i = 0; i < llGetInventoryNumber(INVENTORY_OBJECT); ++i) out += llGetInventoryName(INVENTORY_OBJECT, i);
    return out;
}

rez_house(string name)
{
    if (HOUSE != NULL_KEY) llRegionSayTo(HOUSE, CH, "V|DIE");
    HOUSE = NULL_KEY;
    if (name == "") { put("house", ""); return; }
    house_style(name);
    put("house", name);
    vector off = (vector)get("offset", (string)HOUSE_OFFSET);
    llRezObjectWithParams(name, [REZ_POS, llGetPos() + off * llGetRot(), FALSE, TRUE, REZ_ROT, llGetRot(), FALSE,
                                 REZ_PARAM, 1]);
    say("Rezzing " + name + "...");
}

dialog(key av, string text, list buttons)
{
    USER = av;
    llListenRemove(DL);
    DCH = -1000000 - (integer)llFrand(1000000.0);
    DL = llListen(DCH, "", av, "");
    // put Back/Close at the end, rows of 3 from the bottom up as SL draws them
    list b = [];
    integer i;
    for (i = 0; i < llGetListLength(buttons); i += 3)
        b = llList2List(buttons, i, i + 2) + b;
    llDialog(av, text, b, DCH);
    llSetTimerEvent(90.0);
}

list page(list items, string extra)
{
    integer n = llGetListLength(items);
    if (n <= 10) return items + [extra, "Back"];
    list out = llList2List(items, PAGE * 9, PAGE * 9 + 8);
    if (PAGE * 9 + 9 < n) out += ">>"; else out += "<<";
    return out + [extra, "Back"];
}

menu(key av, string m)
{
    MENU = m;
    if (m == "main")
        dialog(av, "THE VILLA\nHouse: " + get("house", "none") + "\nScene: " + get("scene", "Evening"),
               ["Houses", "Style", "Fabric", "Lights", "Pool", "Ambience", "Doors", "Settings", "Close"]);
    else if (m == "houses")
        dialog(av, "Choose the house (it replaces the current one):", page(houses(), "Remove"));
    else if (m == "style")
        dialog(av, "Which material?", ["Walls", "Floors", "Wood", "Stone", "Fabric", "Metal", "Glass", "Glow", "Water",
                                       "Back"]);
    else if (m == "variant")
    {
        list labels = [];
        integer i;
        for (i = 0; i < llGetListLength(MATS); i += 3)
            if (llList2Integer(MATS, i) == SLOT) labels += llList2String(MATS, i + 2);
        dialog(av, "Material for " + llList2String(SLOT_LABELS, SLOT) + ":", labels + ["Back"]);
    }
    else if (m == "fabric")
        dialog(av, "Upholstery colour (all sofas, chairs, beds, cushions):", llList2ListStrided(TINTS, 0, -1, 2) + ["Back"]);
    else if (m == "lights")
        dialog(av, "Light scene, LED colour and brightness:", llList2ListStrided(SCENES, 0, -1, 3)
               + ["LED colour", "Brighter", "Dimmer", "Back"]);
    else if (m == "led")
        dialog(av, "LED and lamp colour:", llList2ListStrided(LEDS, 0, -1, 2) + ["Back"]);
    else if (m == "pool")
        dialog(av, "Pool:", ["Turquoise", "Lagoon", "Black mirror", "Pool lights", "Spa on", "Spa off", "Back"]);
    else if (m == "poollight")
        dialog(av, "Pool light colour:", llList2ListStrided(POOL_LIGHTS, 0, -1, 2) + ["Back"]);
    else if (m == "ambience")
        dialog(av, "Ambient sound (Core) and fire:", llList2ListStrided(SOUNDS, 0, -1, 2)
               + ["Silence", "Louder", "Softer", "Fire on", "Fire off", "Back"]);
    else if (m == "doors")
        dialog(av, "Doors:", ["Open", "Close", "Back"]);
    else if (m == "settings")
        dialog(av, "Settings. Access: " + get("access", "owner") + "\nOn: " + get("opts", OPTS_DEFAULT),
               ["Chat", "Sounds", "Particles", "Lights on/off", "Owner only", "Group", "Everyone", "Adjust house",
                "Reset", "Back"]);
    else if (m == "adjust")
        dialog(av, "Move the house (saved for next time):",
               ["West", "East", "North", "South", "Up", "Down", "Fine/Coarse", "Back"]);
}

toggle(string f)
{
    list o = llCSV2List(get("opts", OPTS_DEFAULT));
    integer i = llListFindList(o, [f]);
    if (i >= 0) o = llDeleteSubList(o, i, i); else o += f;
    put("opts", llDumpList2String(o, ","));
    send("OPTS|" + get("opts", OPTS_DEFAULT));
}

nudge(vector d)
{
    float step = (float)get("step", "0.1");
    d *= step;
    put("offset", (string)((vector)get("offset", (string)HOUSE_OFFSET) + d));
    if (HOUSE != NULL_KEY) llRegionSayTo(HOUSE, CH, "V|NUDGE|" + (string)(d * llGetRot()));
}

choose(key av, string b)
{
    if (b == "Close") { llListenRemove(DL); return; }
    if (b == "Back") { PAGE = 0; menu(av, "main"); return; }
    if (MENU == "main")
    {
        PAGE = 0;
        menu(av, llList2String(["houses", "style", "fabric", "lights", "pool", "ambience", "doors", "settings"],
             llListFindList(["Houses", "Style", "Fabric", "Lights", "Pool", "Ambience", "Doors", "Settings"], [b])));
        return;
    }
    if (MENU == "houses")
    {
        if (b == ">>") { ++PAGE; menu(av, "houses"); return; }
        if (b == "<<") { PAGE = 0; menu(av, "houses"); return; }
        if (b == "Remove") rez_house("");
        else if (llGetInventoryType(b) == INVENTORY_OBJECT) rez_house(b);
        else
        {
            // dialog buttons are cut at 24 characters: find the object that starts with it
            list hs = houses();
            integer i;
            for (i = 0; i < llGetListLength(hs); ++i)
                if (llSubStringIndex(llList2String(hs, i), b) == 0) rez_house(llList2String(hs, i));
        }
        return;
    }
    if (MENU == "style")
    {
        SLOT = llListFindList(["Walls", "Floors", "Wood", "Stone", "Fabric", "Metal", "Glass", "Glow", "Water"], [b]);
        if (SLOT >= 0) menu(av, "variant");
        return;
    }
    if (MENU == "variant")
    {
        integer i;
        for (i = 0; i < llGetListLength(MATS); i += 3)
            if (llList2Integer(MATS, i) == SLOT && llList2String(MATS, i + 2) == b)
            {
                string id = llList2String(MATS, i + 1);
                if (mat_key(SLOT, id) == NULL_KEY) say("Material missing from the Core's contents: villa_..." + id);
                put("mat" + (string)SLOT, id);
                send_mat(SLOT);
                if (SLOT == 4) send("TINT|" + get("tint", "<1,1,1>"));
            }
        menu(av, "variant");
        return;
    }
    if (MENU == "fabric")
    {
        integer i = llListFindList(TINTS, [b]);
        if (i >= 0) { put("tint", llList2String(TINTS, i + 1)); send("TINT|" + llList2String(TINTS, i + 1)); }
        menu(av, "fabric");
        return;
    }
    if (MENU == "lights")
    {
        if (b == "LED colour") { menu(av, "led"); return; }
        if (b == "Brighter" || b == "Dimmer")
        {
            float k = (float)get("bright", "1.0");
            if (b == "Brighter") k += 0.2; else k -= 0.2;
            if (k < 0.2) k = 0.2;
            if (k > 1.6) k = 1.6;
            put("bright", (string)k);
            scene(get("scene", "Evening"));
        }
        else if (llListFindList(SCENES, [b]) >= 0) { llLinksetDataDelete("led"); scene(b); }
        menu(av, "lights");
        return;
    }
    if (MENU == "led")
    {
        integer i = llListFindList(LEDS, [b]);
        if (i >= 0) { put("led", llList2String(LEDS, i + 1)); scene(get("scene", "Evening")); }
        menu(av, "led");
        return;
    }
    if (MENU == "pool")
    {
        if (b == "Pool lights") { menu(av, "poollight"); return; }
        integer w = llListFindList(["Turquoise", "Lagoon", "Black mirror"], [b]);
        if (w >= 0) { put("mat8", llList2String(["turquoise", "lagoon", "infinity"], w)); send_mat(8); }
        if (b == "Spa on" || b == "Spa off") { put("spa", (string)(b == "Spa on")); send("SPA|" + get("spa", "1")); }
        menu(av, "pool");
        return;
    }
    if (MENU == "poollight")
    {
        integer i = llListFindList(POOL_LIGHTS, [b]);
        if (i >= 0) { put("pool", llList2String(POOL_LIGHTS, i + 1)); send("POOL|" + llList2String(POOL_LIGHTS, i + 1)); }
        menu(av, "poollight");
        return;
    }
    if (MENU == "ambience")
    {
        integer i = llListFindList(SOUNDS, [b]);
        if (i >= 0) put("sound", llList2String(SOUNDS, i + 1));
        if (b == "Silence") put("sound", "");
        if (b == "Louder" || b == "Softer")
        {
            float v = (float)get("vol", "0.5");
            if (b == "Louder") v += 0.15; else v -= 0.15;
            if (v < 0.05) v = 0.05;
            if (v > 1.0) v = 1.0;
            put("vol", (string)v);
        }
        if (b == "Fire on" || b == "Fire off") { put("fire", (string)(b == "Fire on")); send("FIRE|" + get("fire", "1")); }
        else send("SOUND|" + get("sound", "") + "|" + get("vol", "0.5"));
        menu(av, "ambience");
        return;
    }
    if (MENU == "doors") { send("DOOR|" + (string)(b == "Open")); menu(av, "doors"); return; }
    if (MENU == "settings")
    {
        if (b == "Chat") toggle("chat");
        else if (b == "Sounds") { toggle("sounds"); send("SOUND|" + get("sound", "") + "|" + get("vol", "0.5")); }
        else if (b == "Particles") { toggle("particles"); send("FIRE|" + get("fire", "1")); send("SPA|" + get("spa", "1")); }
        else if (b == "Lights on/off") toggle("lights");
        else if (b == "Owner only") put("access", "owner");
        else if (b == "Group") put("access", "group");
        else if (b == "Everyone") put("access", "all");
        else if (b == "Adjust house") { menu(av, "adjust"); return; }
        else if (b == "Reset") { llLinksetDataReset(); send_state(); }
        send("ACCESS|" + get("access", "owner"));
        menu(av, "settings");
        return;
    }
    if (MENU == "adjust")
    {
        if (b == "Fine/Coarse") { if (get("step", "0.1") == "0.1") put("step", "0.01"); else put("step", "0.1"); }
        else nudge(llList2Vector([<-1, 0, 0>, <1, 0, 0>, <0, 1, 0>, <0, -1, 0>, <0, 0, 1>, <0, 0, -1>],
                                 llListFindList(["West", "East", "North", "South", "Up", "Down"], [b])));
        menu(av, "adjust");
    }
}

integer allowed(key av)
{
    string a = get("access", "owner");
    if (av == llGetOwner()) return TRUE;
    if (a == "all") return TRUE;
    if (a == "group") return llSameGroup(av);
    return FALSE;
}

default
{
    state_entry()
    {
        integer l;
        for (l = 2; l <= llGetObjectPrimCount(llGetKey()); ++l)
        {
            string nm = llGetLinkName(l);
            if (llSubStringIndex(nm, "Nautilus_") == 0 || llSubStringIndex(nm, "Dune_") == 0
                || llSubStringIndex(nm, "Nocturne_") == 0)
            { llRemoveInventory(llGetScriptName()); return; }      // dropped into a house: not needed there
        }
        CH = -1 - (integer)("0x" + llGetSubString((string)llGetOwner(), 0, 6)) % 1000000 - 4100000;
        llListen(CH, "", NULL_KEY, "");
        CMD_L = llListen(88, "", llGetOwner(), "");
        llSetTimerEvent(2.0);       // first state push once villa_house has scanned the links
    }

    on_rez(integer p) { HOUSE = NULL_KEY; llResetScript(); }

    changed(integer c)
    {
        if (c & CHANGED_OWNER) { llLinksetDataReset(); llResetScript(); }
        if (c & CHANGED_INVENTORY) say("Villa Core: contents changed. Touch the Core > Houses to rez a house.");
    }

    timer()
    {
        llSetTimerEvent(0.0);
        llListenRemove(DL);
        if (!STARTED)
        {
            STARTED = TRUE;
            send_state();
            say("Villa Core ready. Touch it for the menu (/88 help).");
        }
    }

    object_rez(key id) { HOUSE = id; }

    link_message(integer s, integer n, string m, key id)
    {
        if (n == 7101 && allowed(id)) menu(id, "main");
    }

    listen(integer ch, string nm, key id, string m)
    {
        if (ch == DCH) { choose(id, m); return; }
        if (ch == 88)
        {
            m = llToLower(llStringTrim(m, STRING_TRIM));
            if (m == "menu") menu(id, "main");
            else if (m == "help")
                llOwnerSay("/88 menu - the Villa menu (or touch the Core or any part of the villa)\n"
                           + "/88 resend - send all settings again\n/88 house <name> - rez a house");
            else if (m == "resend") send_state();
            else if (llGetSubString(m, 0, 5) == "house ")
            {
                list hs = houses();
                integer i;
                for (i = 0; i < llGetListLength(hs); ++i)
                    if (llSubStringIndex(llToLower(llList2String(hs, i)), llGetSubString(m, 6, -1)) >= 0)
                    { rez_house(llList2String(hs, i)); return; }
            }
            return;
        }
        if (llGetOwnerKey(id) != llGetOwner() || llGetSubString(m, 0, 1) != "V|") return;
        list a = llParseString2List(m, ["|"], []);
        string c = llList2String(a, 1);
        if (c == "HELLO")
        {
            HOUSE = id;
            send_state();
            say(llList2String(a, 2) + " is ready.");
        }
        else if (c == "MENU" && id == HOUSE)
        {
            key av = (key)llList2String(a, 2);
            if (allowed(av)) menu(av, "main");
        }
    }
}

// cave_main - everything The Cave does: light moods, materials, fire, water, steam, ambient
// sounds, the hide curtain, seats with poses and the lore of each place.
// Goes in the root of the Cave (the hearth) together with the cave_ materials, sounds and poses.
// Touch the cave for the menu. Chat: /89 menu, /89 help.

//@@TABLES@@

integer DCH; integer DL;
key USER;
string MENU = "main";
integer SLOT;
list ROCKS; list FIRES; list CRYSTALS; list WATERS;
list DOORS;                  // [link, closed local position, slide vector]
integer DOOR_OPEN;
list SITTERS;                // [avatar, link, pose index]
integer STARTED;

string get(string k, string d) { string v = llLinksetDataRead(k); if (v == "") return d; return v; }
put(string k, string v) { llLinksetDataWrite(k, v); }
integer opt(string f) { return llSubStringIndex("," + get("opts", OPTS_DEFAULT) + ",", "," + f + ",") >= 0; }
say(key av, string t) { if (opt("chat")) llRegionSayTo(av, 0, t); }

integer allowed(key av)
{
    string a = get("access", "owner");
    if (av == llGetOwner()) return TRUE;
    if (a == "all") return TRUE;
    if (a == "group") return llSameGroup(av);
    return FALSE;
}

integer link_of(string name)
{
    integer l;
    for (l = 1; l <= llGetObjectPrimCount(llGetKey()); ++l) if (llGetLinkName(l) == name) return l;
    return 0;
}

scan()
{
    ROCKS = []; FIRES = []; CRYSTALS = []; WATERS = []; DOORS = [];
    list phys = [];
    integer n = llGetObjectPrimCount(llGetKey());
    integer l;
    for (l = 1; l <= n; ++l)
    {
        string nm = llGetLinkName(l);
        if (l == 1) nm = "Cave_Hearth";            // the root takes the object's name in SL
        if (llSubStringIndex(nm, "Cave_Rock_") == 0)
        {
            ROCKS += l;
            phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_PRIM];
        }
        else if (nm == "Cave_Hearth" || llSubStringIndex(nm, "Cave_Torch_") == 0 || nm == "Cave_Altar"
                 || nm == "Cave_Den_Fire") FIRES += l;
        else if (llSubStringIndex(nm, "Cave_Crystals_") == 0) CRYSTALS += l;
        else if (nm == "Cave_Lake" || nm == "Cave_Waterfall" || nm == "Cave_Spring_Water") WATERS += l;
        if (llListFindList(NO_PHYS, [nm]) >= 0 || llListFindList(WATERS, [l]) >= 0)
            phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_NONE];
        if (nm == "Cave_Curtain")
        {
            list p = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_SIZE]);
            vector sz = llList2Vector(p, 1);
            DOORS += [l, llList2Vector(p, 0), <0.0, -0.95 * sz.y, 0.0>];
        }
        integer s = llListFindList(SEATS, [nm]);
        if (s >= 0)
        {
            rotation r = llEuler2Rot(<0.0, 0.0, llList2Float(SEATS, s + 2) * DEG_TO_RAD>);
            string pose = llList2String(llCSV2List(llList2String(SEATS, s + 3)), 0);
            integer f = llListFindList(POSE_FIT, [pose]);
            vector fit = <0.1, 0.0, -0.23>;
            if (f >= 0) fit = <llList2Float(POSE_FIT, f + 1), 0.0, llList2Float(POSE_FIT, f + 2)>;
            llLinkSitTarget(l, llList2Vector(SEATS, s + 1) + <fit.x, 0.0, 0.0> * r + <0.0, 0.0, fit.z>, r);
        }
    }
    llSetLinkPrimitiveParamsFast(LINK_THIS, phys);
}

apply_list(list links, list params)
{
    integer i;
    list out = [];
    for (i = 0; i < llGetListLength(links); ++i)
    {
        out += [PRIM_LINK_TARGET, llList2Integer(links, i)] + params;
        if (llGetListLength(out) > 600) { llSetLinkPrimitiveParamsFast(LINK_THIS, out); out = []; }
    }
    if (llGetListLength(out)) llSetLinkPrimitiveParamsFast(LINK_THIS, out);
}

list everything_but_water()
{
    list out = [];
    integer l;
    for (l = 1; l <= llGetObjectPrimCount(llGetKey()); ++l) if (llListFindList(WATERS, [l]) < 0) out += l;
    return out;
}

key mat_key(integer s, string id)
{
    string nm = "cave_" + llList2String(SLOTS, s) + "_" + id;
    if (s == 8) nm = "cave_water_" + id;
    if (llGetInventoryType(nm) != INVENTORY_MATERIAL) return NULL_KEY;
    return llGetInventoryKey(nm);
}

material(integer s)
{
    key k = mat_key(s, get("mat" + (string)s, llList2String(DEFAULT_MATS, s)));
    if (k == NULL_KEY) return;
    if (s == 8) apply_list(WATERS, [PRIM_RENDER_MATERIAL, 0, k]);
    else apply_list(everything_but_water(), [PRIM_RENDER_MATERIAL, s, k]);
    if (s == 4) apply_list(everything_but_water(), [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", (vector)get("tint", "<1,1,1>"),
                                                    "", "", "", ""]);
    if (s == 7) mood(get("mood", "Torchlight"));
}

mood(string m)
{
    put("mood", m);
    integer i = llListFindList(MOODS, [m]);
    if (i < 0) i = 0;
    vector fire_c = (vector)get("firecol", (string)llList2Vector(MOODS, i + 1));
    float fire_lv = llList2Float(MOODS, i + 2);
    vector cry_c = llList2Vector(MOODS, i + 3);
    float cry_lv = llList2Float(MOODS, i + 4);
    vector worm_c = llList2Vector(MOODS, i + 5);
    float worm_lv = llList2Float(MOODS, i + 6);
    if (!opt("lights")) { fire_lv = 0.0; cry_lv = 0.0; worm_lv = 0.0; }
    if (get("fire", "1") == "0") fire_lv = 0.0;
    apply_list(FIRES, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", fire_c * fire_lv, PRIM_GLOW, 7, 0.2 * fire_lv,
                       PRIM_FULLBRIGHT, 7, fire_lv > 0.05, PRIM_POINT_LIGHT, fire_lv > 0.05, fire_c, fire_lv, 8.0, 1.0]);
    apply_list(CRYSTALS, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", cry_c * cry_lv, PRIM_GLOW, 7, 0.15 * cry_lv,
                          PRIM_FULLBRIGHT, 7, cry_lv > 0.05, PRIM_POINT_LIGHT, cry_lv > 0.05, cry_c, cry_lv * 0.8, 6.0, 1.0]);
    apply_list(ROCKS, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", worm_c * worm_lv, PRIM_GLOW, 7, 0.3 * worm_lv,
                       PRIM_FULLBRIGHT, 7, worm_lv > 0.05]);
    integer lake = link_of("Cave_Lake");
    if (lake) llSetLinkPrimitiveParamsFast(lake, [PRIM_POINT_LIGHT, worm_lv > 0.05, worm_c, worm_lv * 0.6, 12.0, 0.8]);
    flames();
}

flames()
{
    integer i;
    integer on = get("fire", "1") == "1" && opt("particles") && llList2Float(MOODS, llListFindList(MOODS,
                 [get("mood", "Torchlight")]) + 2) > 0.05;
    vector c = (vector)get("firecol", "<1.0,0.55,0.22>");
    for (i = 0; i < llGetListLength(FIRES); ++i)
    {
        integer l = llList2Integer(FIRES, i);
        float big = 1.0;
        if (l == 1) big = 2.6;
        if (on)
            llLinkParticleSystem(l, [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK
                | PSYS_PART_INTERP_SCALE_MASK, PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE,
                PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.3, PSYS_SRC_BURST_RADIUS, 0.05 * big,
                PSYS_PART_START_COLOR, c, PSYS_PART_END_COLOR, c * 0.5,
                PSYS_PART_START_ALPHA, 0.8, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.12, 0.2, 0.0> * big, PSYS_PART_END_SCALE, <0.03, 0.08, 0.0> * big,
                PSYS_PART_MAX_AGE, 0.6 + 0.2 * big, PSYS_SRC_BURST_RATE, 0.07, PSYS_SRC_BURST_PART_COUNT, 1 + (integer)big,
                PSYS_SRC_BURST_SPEED_MIN, 0.15, PSYS_SRC_BURST_SPEED_MAX, 0.3, PSYS_SRC_ACCEL, <0.0, 0.0, 0.4>]);
        else llLinkParticleSystem(l, []);
    }
}

effects()
{
    integer on = opt("particles");
    integer fall = link_of("Cave_Waterfall");
    integer spring = link_of("Cave_Spring_Water");
    if (fall)
    {
        float a = 1.0;
        if (get("waterfall", "1") == "0") a = 0.0;
        llSetLinkPrimitiveParamsFast(fall, [PRIM_GLTF_BASE_COLOR, ALL_SIDES, "", "", "", "", "", a, "", "", ""]);
        if (on && a > 0)
            llLinkParticleSystem(fall, [PSYS_PART_FLAGS, PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_INTERP_COLOR_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE, PSYS_SRC_BURST_RADIUS, 1.2,
                PSYS_PART_START_COLOR, <0.9, 0.95, 1.0>, PSYS_PART_START_ALPHA, 0.25, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.4, 0.4, 0.0>, PSYS_PART_END_SCALE, <1.2, 1.2, 0.0>, PSYS_PART_MAX_AGE, 2.5,
                PSYS_SRC_BURST_RATE, 0.1, PSYS_SRC_BURST_PART_COUNT, 2, PSYS_SRC_BURST_SPEED_MIN, 0.1,
                PSYS_SRC_BURST_SPEED_MAX, 0.3, PSYS_SRC_ACCEL, <0.0, 0.0, -0.05>]);
        else llLinkParticleSystem(fall, []);
    }
    if (spring)
    {
        if (on && get("steam", "1") == "1")
            llLinkParticleSystem(spring, [PSYS_PART_FLAGS, PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_INTERP_COLOR_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE, PSYS_SRC_BURST_RADIUS, 1.3,
                PSYS_PART_START_COLOR, <1.0, 1.0, 1.0>, PSYS_PART_START_ALPHA, 0.18, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.5, 0.5, 0.0>, PSYS_PART_END_SCALE, <1.6, 1.6, 0.0>, PSYS_PART_MAX_AGE, 4.0,
                PSYS_SRC_BURST_RATE, 0.25, PSYS_SRC_BURST_PART_COUNT, 2, PSYS_SRC_BURST_SPEED_MIN, 0.05,
                PSYS_SRC_BURST_SPEED_MAX, 0.12, PSYS_SRC_ACCEL, <0.0, 0.0, 0.12>]);
        else llLinkParticleSystem(spring, []);
    }
    sounds();
}

sounds()
{
    integer i;
    float v = (float)get("vol", "0.6");
    for (i = 0; i < llGetListLength(SOUND_SPOTS); i += 2)
    {
        integer l = link_of(llList2String(SOUND_SPOTS, i));
        string snd = llList2String(SOUND_SPOTS, i + 1);
        if (l == 0) l = 1;
        integer on = opt("sounds") && llGetInventoryType(snd) == INVENTORY_SOUND;
        if (snd == "cave_fire" && get("fire", "1") == "0") on = FALSE;
        if (snd == "cave_waterfall" && get("waterfall", "1") == "0") on = FALSE;
        if (on) llLinkPlaySound(l, snd, v, SOUND_LOOP);
        else llLinkStopSound(l);
    }
}

doors(integer open)
{
    DOOR_OPEN = open;
    integer step;
    integer i;
    if (opt("sounds") && llGetInventoryType("cave_curtain") == INVENTORY_SOUND) llPlaySound("cave_curtain", 0.6);
    for (step = 1; step <= 10; ++step)
    {
        float t = (float)step / 10.0;
        if (!open) t = 1.0 - t;
        t = t * t * (3.0 - 2.0 * t);
        list out = [];
        for (i = 0; i < llGetListLength(DOORS); i += 3)
            out += [PRIM_LINK_TARGET, llList2Integer(DOORS, i), PRIM_POS_LOCAL,
                    llList2Vector(DOORS, i + 1) + llList2Vector(DOORS, i + 2) * t];
        if (llGetListLength(out)) llSetLinkPrimitiveParamsFast(LINK_THIS, out);
        llSleep(0.05);
    }
}

all_state()
{
    integer s;
    for (s = 0; s <= 8; ++s) material(s);
    mood(get("mood", "Torchlight"));
    effects();
}

// ---------------------------------------------------------------- seats
seat_check()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer l;
    list now = [];
    for (l = 1; l <= n; ++l)
    {
        key av = llAvatarOnLinkSitTarget(l);
        if (av != NULL_KEY)
        {
            now += av;
            if (llListFindList(SITTERS, [av]) < 0)
            {
                SITTERS += [av, l, 0];
                llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION);
            }
        }
    }
    integer i;
    for (i = llGetListLength(SITTERS) - 3; i >= 0; i -= 3)
        if (llListFindList(now, [llList2Key(SITTERS, i)]) < 0) SITTERS = llDeleteSubList(SITTERS, i, i + 2);
}

play(key av, integer step)
{
    integer i = llListFindList(SITTERS, [av]);
    if (i < 0) return;
    integer l = llList2Integer(SITTERS, i + 1);
    string nm = llGetLinkName(l);
    if (l == 1) nm = "Cave_Hearth";
    integer s = llListFindList(SEATS, [nm]);
    if (s < 0) return;
    list ps = llCSV2List(llList2String(SEATS, s + 3));
    integer k = (llList2Integer(SITTERS, i + 2) + step) % llGetListLength(ps);
    SITTERS = llListReplaceList(SITTERS, [k], i + 2, i + 2);
    if (llGetPermissionsKey() != av || !(llGetPermissions() & PERMISSION_TRIGGER_ANIMATION)) return;
    llStopAnimation("sit");
    integer j;
    for (j = 0; j < llGetListLength(ps); ++j)
        if (j != k && llGetInventoryType(llList2String(ps, j)) == INVENTORY_ANIMATION) llStopAnimation(llList2String(ps, j));
    if (llGetInventoryType(llList2String(ps, k)) == INVENTORY_ANIMATION) llStartAnimation(llList2String(ps, k));
    else llStartAnimation("sit");
}

// ---------------------------------------------------------------- menus
dialog(key av, string text, list buttons)
{
    USER = av;
    llListenRemove(DL);
    DCH = -1000000 - (integer)llFrand(1000000.0);
    DL = llListen(DCH, "", av, "");
    list b = [];
    integer i;
    for (i = 0; i < llGetListLength(buttons); i += 3) b = llList2List(buttons, i, i + 2) + b;
    llDialog(av, text, b, DCH);
    llSetTimerEvent(90.0);
}

menu(key av, string m)
{
    MENU = m;
    if (m == "main")
        dialog(av, "THE CAVE\nMood: " + get("mood", "Torchlight"),
               ["Mood", "Materials", "Fire", "Water", "Sounds", "Curtain", "Settings", "Help", "Close"]);
    else if (m == "mood") dialog(av, "Light mood:", llList2ListStrided(MOODS, 0, -1, 7) + ["Back"]);
    else if (m == "materials")
        dialog(av, "Which material?", ["Rock", "Ground", "Wood", "Moss", "Fur", "Metal", "Crystal", "Glow", "Water", "Fur colour",
                                       "Back"]);
    else if (m == "variant")
    {
        list labels = [];
        integer i;
        for (i = 0; i < llGetListLength(MATS); i += 3)
            if (llList2Integer(MATS, i) == SLOT) labels += llList2String(MATS, i + 2);
        dialog(av, "Material for " + llList2String(SLOT_LABELS, SLOT) + ":", labels + ["Back"]);
    }
    else if (m == "tint") dialog(av, "Fur, leather and wool colour:", llList2ListStrided(TINTS, 0, -1, 2) + ["Back"]);
    else if (m == "fire")
        dialog(av, "Hearth, torches and altar:", ["Fire on", "Fire off"] + llList2ListStrided(FIRE_COLOURS, 0, -1, 2) + ["Back"]);
    else if (m == "water")
        dialog(av, "Lake, waterfall and spring:", ["Waterfall on", "Waterfall off", "Steam on", "Steam off", "Back"]);
    else if (m == "sounds") dialog(av, "Ambience (fire, water, drips, wind, crystals):", ["Sounds on", "Sounds off", "Louder",
                                                                                         "Softer", "Back"]);
    else if (m == "curtain") dialog(av, "Hide curtain at the entrance:", ["Open", "Close", "Back"]);
    else if (m == "settings")
        dialog(av, "Settings. Access: " + get("access", "owner") + "\nOn: " + get("opts", OPTS_DEFAULT),
               ["Chat text", "Lore", "Particles", "Lights", "Owner only", "Group", "Everyone", "Reset", "Back"]);
}

toggle(string f)
{
    list o = llCSV2List(get("opts", OPTS_DEFAULT));
    integer i = llListFindList(o, [f]);
    if (i >= 0) o = llDeleteSubList(o, i, i); else o += f;
    put("opts", llDumpList2String(o, ","));
}

choose(key av, string b)
{
    if (b == "Close") { llListenRemove(DL); return; }
    if (b == "Back") { menu(av, "main"); return; }
    if (MENU == "main")
    {
        if (b == "Help")
        {
            llRegionSayTo(av, 0, "Sit on logs, furs, beds, the raft, the spring stones or kneel at the altar; touch your "
                + "seat to change pose. Touch the altar, crystals, waterfall, chest or curtain to read them. Owner: /89 menu.");
            menu(av, "main");
            return;
        }
        menu(av, llToLower(b));
        return;
    }
    if (MENU == "mood") { if (llListFindList(MOODS, [b]) >= 0) { llLinksetDataDelete("firecol"); mood(b); flames(); }
                          menu(av, "mood"); return; }
    if (MENU == "materials")
    {
        if (b == "Fur colour") { menu(av, "tint"); return; }
        SLOT = llListFindList(SLOT_LABELS, [b]);
        if (SLOT >= 0) menu(av, "variant");
        return;
    }
    if (MENU == "variant")
    {
        integer i;
        for (i = 0; i < llGetListLength(MATS); i += 3)
            if (llList2Integer(MATS, i) == SLOT && llList2String(MATS, i + 2) == b)
            {
                put("mat" + (string)SLOT, llList2String(MATS, i + 1));
                material(SLOT);
            }
        menu(av, "variant");
        return;
    }
    if (MENU == "tint")
    {
        integer i = llListFindList(TINTS, [b]);
        if (i >= 0) { put("tint", llList2String(TINTS, i + 1)); material(4); }
        menu(av, "tint");
        return;
    }
    if (MENU == "fire")
    {
        if (b == "Fire on" || b == "Fire off") put("fire", (string)(b == "Fire on"));
        integer i = llListFindList(FIRE_COLOURS, [b]);
        if (i >= 0) put("firecol", llList2String(FIRE_COLOURS, i + 1));
        mood(get("mood", "Torchlight"));
        sounds();
        menu(av, "fire");
        return;
    }
    if (MENU == "water")
    {
        if (b == "Waterfall on" || b == "Waterfall off") put("waterfall", (string)(b == "Waterfall on"));
        if (b == "Steam on" || b == "Steam off") put("steam", (string)(b == "Steam on"));
        effects();
        menu(av, "water");
        return;
    }
    if (MENU == "sounds")
    {
        if (b == "Sounds on" && !opt("sounds")) toggle("sounds");
        if (b == "Sounds off" && opt("sounds")) toggle("sounds");
        float v = (float)get("vol", "0.6");
        if (b == "Louder") v += 0.15;
        if (b == "Softer") v -= 0.15;
        if (v < 0.05) v = 0.05;
        if (v > 1.0) v = 1.0;
        put("vol", (string)v);
        sounds();
        menu(av, "sounds");
        return;
    }
    if (MENU == "curtain") { doors(b == "Open"); menu(av, "curtain"); return; }
    if (MENU == "settings")
    {
        if (b == "Chat text") toggle("chat");
        else if (b == "Lore") toggle("lore");
        else if (b == "Particles") { toggle("particles"); flames(); effects(); }
        else if (b == "Lights") { toggle("lights"); mood(get("mood", "Torchlight")); }
        else if (b == "Owner only") put("access", "owner");
        else if (b == "Group") put("access", "group");
        else if (b == "Everyone") put("access", "all");
        else if (b == "Reset") { llLinksetDataReset(); all_state(); }
        menu(av, "settings");
    }
}

default
{
    state_entry()
    {
        scan();
        llListen(89, "", llGetOwner(), "");
        llSetTimerEvent(1.0);
    }

    on_rez(integer p) { llResetScript(); }

    changed(integer c)
    {
        if (c & CHANGED_OWNER) { llLinksetDataReset(); llResetScript(); }
        if (c & CHANGED_LINK) seat_check();
        if (c & CHANGED_INVENTORY) { STARTED = FALSE; llSetTimerEvent(2.0); }
    }

    timer()
    {
        llSetTimerEvent(0.0);
        llListenRemove(DL);
        if (!STARTED) { STARTED = TRUE; all_state(); }
    }

    run_time_permissions(integer p) { if (p & PERMISSION_TRIGGER_ANIMATION) play(llGetPermissionsKey(), 0); }

    touch_start(integer t)
    {
        key av = llDetectedKey(0);
        integer l = llDetectedLinkNumber(0);
        string nm = llGetLinkName(l);
        if (l == 1) nm = "Cave_Hearth";
        integer i = llListFindList(SITTERS, [av]);
        if (i >= 0 && llList2Integer(SITTERS, i + 1) == l)
        {
            if (llGetPermissionsKey() != av) llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION);
            else play(av, 1);
            return;
        }
        if (nm == "Cave_Curtain")
        {
            if (allowed(av) || get("access", "owner") != "owner") doors(!DOOR_OPEN);
            return;
        }
        integer lore = llListFindList(LORE, [nm]);
        if (lore < 0 && llSubStringIndex(nm, "Cave_Crystals_") == 0) lore = llListFindList(LORE, ["Cave_Crystals"]);
        if (lore >= 0 && opt("lore")) { say(av, llList2String(LORE, lore + 1)); return; }
        if (allowed(av)) menu(av, "main");
    }

    listen(integer ch, string nm, key id, string m)
    {
        if (ch == DCH) { choose(id, m); return; }
        m = llToLower(llStringTrim(m, STRING_TRIM));
        if (m == "menu") menu(id, "main");
        else if (m == "help") llOwnerSay("/89 menu - the Cave menu (or touch the cave)\n/89 reset - reapply everything");
        else if (m == "reset") all_state();
    }
}

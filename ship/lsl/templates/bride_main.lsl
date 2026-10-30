// bride_main - everything the Second Bride does: set or furl the sails, fire a broadside, strike
// the bell, light the lanterns, fly the Lord's flag, sea sounds and motion, doors, materials,
// seats with poses and the lore of the ship.
// Goes in the root of the ship with the bride_ materials, sounds and poses.
// Touch the ship for the menu. Owner chat: /90 menu, /90 float, /90 help.

//@@TABLES@@

integer DCH; integer DL;
string MENU = "main";
integer SLOT;
list SAILS; list FURLED; list GUNS; list LIGHTS; list FLAGS; list DOORS; list SITTERS;
integer BELL; integer STARTED; integer ROCKING;
list GUN_HOME;               // [link, local position]

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

string name_of(integer l) { if (l == 1) return ROOT_NAME; return llGetLinkName(l); }

scan()
{
    SAILS = []; FURLED = []; GUNS = []; LIGHTS = []; FLAGS = []; DOORS = []; GUN_HOME = []; BELL = 0;
    list phys = [];
    integer n = llGetObjectPrimCount(llGetKey());
    integer l;
    for (l = 1; l <= n; ++l)
    {
        string nm = name_of(l);
        if (llSubStringIndex(nm, "Bride_Sails_") == 0) SAILS += l;
        else if (llSubStringIndex(nm, "Bride_Furled_") == 0) FURLED += l;
        else if (llSubStringIndex(nm, "Bride_Gun_") == 0)
        {
            GUNS += l;
            GUN_HOME += [l, llList2Vector(llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL]), 0)];
        }
        else if (nm == "Bride_Flag_Lord" || nm == "Bride_Ensign") FLAGS += l;
        else if (nm == "Bride_Bell") BELL = l;
        if (llListFindList(LIGHT_PIECES, [nm]) >= 0) LIGHTS += l;
        if (nm == "Bride_Door_Cabin" || llSubStringIndex(nm, "Bride_Brig_Door_") == 0)
        {
            list p = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_SIZE]);
            vector sz = llList2Vector(p, 1);
            vector slide = <-0.95 * sz.x, 0.0, 0.0>;
            if (sz.y > sz.x) slide = <0.0, -0.95 * sz.y, 0.0>;
            DOORS += [l, llList2Vector(p, 0), slide, 0];
        }
        if (llListFindList(NO_PHYS, [nm]) >= 0)
            phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_NONE];
        else if (llListFindList(PRIM_PHYS, [nm]) >= 0)
            phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_PRIM];
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
        if (llGetListLength(phys) > 400) { llSetLinkPrimitiveParamsFast(LINK_THIS, phys); phys = []; }
    }
    if (llGetListLength(phys)) llSetLinkPrimitiveParamsFast(LINK_THIS, phys);
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

show(list links, integer visible)
{
    float a = 0.0;
    if (visible) a = 1.0;
    apply_list(links, [PRIM_GLTF_BASE_COLOR, ALL_SIDES, "", "", "", "", "", a, PRIM_GLTF_ALPHA_MODE_MASK, 0.5, "",
                       PRIM_COLOR, ALL_SIDES, <1.0, 1.0, 1.0>, a]);
}

sails()
{
    integer set = get("sails", "1") == "1";
    show(SAILS, set);
    show(FURLED, !set);
    canvas();
}

key mat_key(integer s, string id)
{
    string nm = "bride_" + llList2String(SLOTS, s) + "_" + id;
    if (s == 8) nm = "bride_water_" + id;
    if (llGetInventoryType(nm) != INVENTORY_MATERIAL) return NULL_KEY;
    return llGetInventoryKey(nm);
}

material(integer s)
{
    if (s == 8) return;
    key k = mat_key(s, get("mat" + (string)s, llList2String(DEFAULT_MATS, s)));
    if (k == NULL_KEY) return;
    integer l;
    list links = [];
    for (l = 1; l <= llGetObjectPrimCount(llGetKey()); ++l) links += l;
    apply_list(links, [PRIM_RENDER_MATERIAL, s, k]);
    if (s == 4) { canvas(); sails(); }
    if (s == 7) lights();
}

canvas()
{
    // sails and flags share the canvas face: the flags are dyed by the flag setting
    integer set = get("sails", "1") == "1";
    float a = 0.0;
    if (set) a = 1.0;
    apply_list(SAILS, [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", (vector)get("sailcol", "<1,1,1>"), a,
                       PRIM_GLTF_ALPHA_MODE_MASK, 0.5, ""]);
    string f = get("flag", "Lord");
    vector c = <0.06, 0.06, 0.06>;
    if (f == "Crown") c = <0.12, 0.2, 0.55>;
    if (f == "Blood") c = <0.55, 0.05, 0.05>;
    float fa = 1.0;
    if (f == "None") fa = 0.0;
    apply_list(FLAGS, [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", c, fa, PRIM_GLTF_ALPHA_MODE_MASK, 0.5, "",
                       PRIM_GLTF_BASE_COLOR, 3, "", "", "", "", "", fa, PRIM_GLTF_ALPHA_MODE_MASK, 0.5, ""]);
}

lights()
{
    string sc = get("scene", "Dusk");
    integer i = llListFindList(SCENES, [sc]);
    if (i < 0) i = 0;
    float lv = llList2Float(SCENES, i + 1);
    vector c = (vector)get("lampcol", "<1.0,0.62,0.3>");
    if (!opt("lights")) lv = 0.0;
    integer l;
    list links = [];
    for (l = 1; l <= llGetObjectPrimCount(llGetKey()); ++l) links += l;
    apply_list(links, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", c * lv, PRIM_GLOW, 7, 0.1 * lv, PRIM_FULLBRIGHT, 7, lv > 0.05]);
    apply_list(LIGHTS, [PRIM_POINT_LIGHT, lv > 0.05, c, lv, 6.0, 1.2]);
}

sounds()
{
    integer i;
    float v = (float)get("vol", "0.5");
    for (i = 0; i < llGetListLength(SOUND_SPOTS); i += 2)
    {
        integer l = 0;
        integer k;
        for (k = 1; k <= llGetObjectPrimCount(llGetKey()); ++k) if (name_of(k) == llList2String(SOUND_SPOTS, i)) l = k;
        if (l == 0) l = 1;
        string snd = llList2String(SOUND_SPOTS, i + 1);
        if (opt("sounds") && llGetInventoryType(snd) == INVENTORY_SOUND) llLinkPlaySound(l, snd, v, SOUND_LOOP);
        else llLinkStopSound(l);
    }
}

broadside(string side)
{
    if (!opt("guns")) return;
    integer i;
    integer fired = 0;
    for (i = 0; i < llGetListLength(GUNS); ++i)
    {
        integer l = llList2Integer(GUNS, i);
        string nm = name_of(l);
        if (llGetSubString(nm, 10, 10) == side || side == "B")
        {
            vector out = <0.0, 1.0, 0.0>;
            if (llGetSubString(nm, 10, 10) == "S") out = <0.0, -1.0, 0.0>;
            if (opt("particles"))
                llLinkParticleSystem(l, [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK
                    | PSYS_PART_EMISSIVE_MASK, PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE,
                    PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.25, PSYS_SRC_BURST_RADIUS, 0.4,
                    PSYS_PART_START_COLOR, <1.0, 0.75, 0.45>, PSYS_PART_END_COLOR, <0.55, 0.55, 0.55>,
                    PSYS_PART_START_ALPHA, 0.9, PSYS_PART_END_ALPHA, 0.0,
                    PSYS_PART_START_SCALE, <0.6, 0.6, 0.0>, PSYS_PART_END_SCALE, <3.5, 3.5, 0.0>,
                    PSYS_PART_MAX_AGE, 3.5, PSYS_SRC_MAX_AGE, 0.6, PSYS_SRC_BURST_RATE, 0.05,
                    PSYS_SRC_BURST_PART_COUNT, 6, PSYS_SRC_BURST_SPEED_MIN, 2.0, PSYS_SRC_BURST_SPEED_MAX, 5.0,
                    PSYS_SRC_ACCEL, <0.0, 0.0, 0.3>, PSYS_SRC_OMEGA, ZERO_VECTOR,
                    PSYS_SRC_TARGET_KEY, NULL_KEY]);
            integer h = llListFindList(GUN_HOME, [l]);
            vector home = llList2Vector(GUN_HOME, h + 1);
            llSetLinkPrimitiveParamsFast(l, [PRIM_POS_LOCAL, home - out * 0.55, PRIM_POINT_LIGHT, TRUE,
                                             <1.0, 0.7, 0.4>, 1.0, 14.0, 0.6]);
            if (opt("sounds") && llGetInventoryType("bride_cannon") == INVENTORY_SOUND)
                llLinkPlaySound(l, "bride_cannon", 1.0, SOUND_PLAY);
            llSleep(0.12);
            llSetLinkPrimitiveParamsFast(l, [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0.0, 0.0, 0.0]);
            llSleep(0.18);
            ++fired;
        }
    }
    llSleep(0.8);
    // run the guns out again
    integer step;
    for (step = 1; step <= 6; ++step)
    {
        list out = [];
        for (i = 0; i < llGetListLength(GUN_HOME); i += 2)
        {
            vector home = llList2Vector(GUN_HOME, i + 1);
            vector now = llList2Vector(llGetLinkPrimitiveParams(llList2Integer(GUN_HOME, i), [PRIM_POS_LOCAL]), 0);
            out += [PRIM_LINK_TARGET, llList2Integer(GUN_HOME, i), PRIM_POS_LOCAL, now + (home - now) * ((float)step / 6.0)];
        }
        llSetLinkPrimitiveParamsFast(LINK_THIS, out);
        llSleep(0.15);
    }
}

bell(integer strikes)
{
    if (!BELL || !opt("sounds") || llGetInventoryType("bride_bell") != INVENTORY_SOUND) return;
    integer i;
    for (i = 0; i < strikes; ++i)
    {
        llLinkPlaySound(BELL, "bride_bell", 1.0, SOUND_PLAY);
        if (i % 2) llSleep(1.4); else llSleep(0.7);
    }
}

door(integer i, integer open)
{
    integer l = llList2Integer(DOORS, i);
    vector home = llList2Vector(DOORS, i + 1);
    vector slide = llList2Vector(DOORS, i + 2);
    DOORS = llListReplaceList(DOORS, [open], i + 3, i + 3);
    if (opt("sounds") && llGetInventoryType("bride_door") == INVENTORY_SOUND) llLinkPlaySound(l, "bride_door", 0.7, SOUND_PLAY);
    integer step;
    for (step = 1; step <= 8; ++step)
    {
        float t = (float)step / 8.0;
        if (!open) t = 1.0 - t;
        llSetLinkPrimitiveParamsFast(l, [PRIM_POS_LOCAL, home + slide * (t * t * (3.0 - 2.0 * t))]);
        llSleep(0.05);
    }
}

rock(integer on)
{
    ROCKING = on;
    if (!on) { llSetKeyframedMotion([], [KFM_COMMAND, KFM_CMD_STOP]); return; }
    rotation a = llEuler2Rot(<2.2, 0.6, 0.0> * DEG_TO_RAD);
    rotation b = llEuler2Rot(<-2.2, -0.6, 0.0> * DEG_TO_RAD);
    llSetKeyframedMotion([<0.0, 0.0, 0.12>, a, 3.5, <0.0, 0.0, -0.24>, b / a, 7.0, <0.0, 0.0, 0.12>, ZERO_ROTATION / b, 3.5],
                         [KFM_MODE, KFM_LOOP]);
}

all_state()
{
    integer s;
    for (s = 0; s <= 7; ++s) material(s);
    sails();
    lights();
    sounds();
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
            if (llListFindList(SITTERS, [av]) < 0) { SITTERS += [av, l, 0]; llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION); }
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
    integer s = llListFindList(SEATS, [name_of(llList2Integer(SITTERS, i + 1))]);
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
        dialog(av, "THE SECOND BRIDE\nSails: " + llList2String(["furled", "set"], get("sails", "1") == "1")
               + "   Lights: " + get("scene", "Dusk"),
               ["Sails", "Broadside", "Bell", "Lights", "Flags", "Doors", "Materials", "Sea", "Settings", "Close"]);
    else if (m == "sails") dialog(av, "Sails:", ["Set sail", "Furl", "White canvas", "Weathered", "Black", "Blood red", "Back"]);
    else if (m == "broadside") dialog(av, "Run out the guns and fire:", ["Port", "Starboard", "Both", "Back"]);
    else if (m == "lights") dialog(av, "Lanterns and stern lights:", llList2ListStrided(SCENES, 0, -1, 2)
                                   + ["Warm", "Pale", "Blood", "Ghost green", "Back"]);
    else if (m == "flags") dialog(av, "Colours:", ["Lord", "Crown", "Blood", "None", "Back"]);
    else if (m == "doors") dialog(av, "Doors (or touch them):", ["Open all", "Close all", "Back"]);
    else if (m == "materials")
        dialog(av, "Which material?", ["Hull", "Deck", "Wood", "Trim", "Canvas", "Metal", "Glass", "Glow", "Back"]);
    else if (m == "variant")
    {
        list labels = [];
        integer i;
        for (i = 0; i < llGetListLength(MATS); i += 3)
            if (llList2Integer(MATS, i) == SLOT) labels += llList2String(MATS, i + 2);
        dialog(av, "Material for " + llList2String(SLOT_LABELS, SLOT) + ":", labels + ["Back"]);
    }
    else if (m == "sea") dialog(av, "The sea:", ["Rock on", "Rock off", "Float", "Sounds on", "Sounds off", "Louder", "Softer", "Back"]);
    else if (m == "settings")
        dialog(av, "Settings. Access: " + get("access", "owner") + "\nOn: " + get("opts", OPTS_DEFAULT),
               ["Chat text", "Lore", "Particles", "Lights", "Guns", "Owner only", "Group", "Everyone", "Reset", "Back"]);
}

toggle(string f)
{
    list o = llCSV2List(get("opts", OPTS_DEFAULT));
    integer i = llListFindList(o, [f]);
    if (i >= 0) o = llDeleteSubList(o, i, i); else o += f;
    put("opts", llDumpList2String(o, ","));
}

float_ship()
{
    vector p = llGetPos();
    llSetRegionPos(<p.x, p.y, llWater(ZERO_VECTOR) + ROOT_Z>);
}

choose(key av, string b)
{
    if (b == "Close") { llListenRemove(DL); return; }
    if (b == "Back") { menu(av, "main"); return; }
    if (MENU == "main")
    {
        if (b == "Bell") { bell(8); menu(av, "main"); return; }
        menu(av, llToLower(b));
        return;
    }
    if (MENU == "sails")
    {
        if (b == "Set sail") put("sails", "1");
        if (b == "Furl") put("sails", "0");
        integer c = llListFindList(["White canvas", "Weathered", "Black", "Blood red"], [b]);
        if (c >= 0) put("sailcol", llList2String(["<1,1,1>", "<0.85,0.76,0.6>", "<0.12,0.12,0.12>", "<0.5,0.07,0.06>"], c));
        sails();
        menu(av, "sails");
        return;
    }
    if (MENU == "broadside") { menu(av, "broadside"); broadside(llGetSubString(b, 0, 0)); return; }
    if (MENU == "lights")
    {
        if (llListFindList(SCENES, [b]) >= 0) put("scene", b);
        integer c = llListFindList(["Warm", "Pale", "Blood", "Ghost green"], [b]);
        if (c >= 0) put("lampcol", llList2String(["<1.0,0.62,0.3>", "<1.0,0.9,0.75>", "<1.0,0.2,0.1>", "<0.4,1.0,0.6>"], c));
        lights();
        menu(av, "lights");
        return;
    }
    if (MENU == "flags") { put("flag", b); canvas(); menu(av, "flags"); return; }
    if (MENU == "doors")
    {
        integer i;
        for (i = 0; i < llGetListLength(DOORS); i += 4)
            if (llList2Integer(DOORS, i + 3) != (b == "Open all")) door(i, b == "Open all");
        menu(av, "doors");
        return;
    }
    if (MENU == "materials")
    {
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
    if (MENU == "sea")
    {
        if (b == "Rock on") rock(TRUE);
        if (b == "Rock off") rock(FALSE);
        if (b == "Float") float_ship();
        if (b == "Sounds on" && !opt("sounds")) toggle("sounds");
        if (b == "Sounds off" && opt("sounds")) toggle("sounds");
        float v = (float)get("vol", "0.5");
        if (b == "Louder") v += 0.15;
        if (b == "Softer") v -= 0.15;
        if (v < 0.05) v = 0.05;
        if (v > 1.0) v = 1.0;
        put("vol", (string)v);
        sounds();
        menu(av, "sea");
        return;
    }
    if (MENU == "settings")
    {
        if (b == "Chat text") toggle("chat");
        else if (b == "Lore") toggle("lore");
        else if (b == "Particles") toggle("particles");
        else if (b == "Lights") { toggle("lights"); lights(); }
        else if (b == "Guns") toggle("guns");
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
        llListen(90, "", llGetOwner(), "");
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
        string nm = name_of(l);
        integer i = llListFindList(SITTERS, [av]);
        if (i >= 0 && llList2Integer(SITTERS, i + 1) == l)
        {
            if (llGetPermissionsKey() != av) llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION);
            else play(av, 1);
            return;
        }
        for (i = 0; i < llGetListLength(DOORS); i += 4)
            if (llList2Integer(DOORS, i) == l)
            {
                if (allowed(av) || llSubStringIndex(nm, "Bride_Brig_Door_") != 0) door(i, !llList2Integer(DOORS, i + 3));
                return;
            }
        if (l == BELL) { bell(2); return; }
        integer lore = llListFindList(LORE, [nm]);
        if (lore >= 0 && opt("lore") && !allowed(av)) { say(av, llList2String(LORE, lore + 1)); return; }
        if (lore >= 0 && opt("lore")) say(av, llList2String(LORE, lore + 1));
        if (allowed(av)) menu(av, "main");
    }

    listen(integer ch, string nm, key id, string m)
    {
        if (ch == DCH) { choose(id, m); return; }
        m = llToLower(llStringTrim(m, STRING_TRIM));
        if (m == "menu") menu(id, "main");
        else if (m == "float") float_ship();
        else if (m == "broadside") broadside("B");
        else if (m == "help") llOwnerSay("/90 menu - the ship's menu (or touch the ship)\n/90 float - set her on the water\n"
                                         + "/90 broadside - fire every gun\n/90 reset - reapply everything");
        else if (m == "reset") all_state();
    }
}

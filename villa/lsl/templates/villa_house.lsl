// villa_house - materials, colours, lights, doors, seats and effects of one Villa linkset.
// Goes in the root of the Villa Core AND of every house (the same script for all of them).
// Commands come from villa_core: by link message 7100 inside the Core, or on the owner's
// private channel for a house the Core has rezzed.

//@@TABLES@@

integer CH;                 // owner's private channel (same formula in villa_core)
key CORE = NULL_KEY;        // the Core that rezzed this house
integer IS_CORE;
list NORMAL;                // links that take the slot materials
list WATERS; list LIGHTS; list PLANTS; list FIRES; list POOLS; list SPAS;
list DOORS;                 // [link, closed local position, slide vector] ...
integer DOOR_OPEN;
vector LED = <1.0, 0.8, 0.58>;
float LEVEL = 0.7;
vector TINT = <1.0, 1.0, 1.0>;
vector POOL = <0.3, 0.75, 1.0>;
key WATER_MAT = NULL_KEY;
string OPTS = "chat,sounds,particles,lights";
string ACCESS = "owner";
list SITTERS;               // [avatar, link, pose index] ...
key ASKED = NULL_KEY;

integer opt(string f) { return llSubStringIndex("," + OPTS + ",", "," + f + ",") >= 0; }

integer allowed(key av)
{
    if (av == llGetOwner()) return TRUE;
    if (ACCESS == "all") return TRUE;
    if (ACCESS == "group") return llSameGroup(av);
    return FALSE;
}

integer kind(string name)
{
    integer k = llListFindList(KINDS, [name]);
    if (k < 0) return 0;
    return llList2Integer(KINDS, k + 1);
}

scan()
{
    NORMAL = []; WATERS = []; LIGHTS = []; PLANTS = []; FIRES = []; POOLS = []; SPAS = []; DOORS = [];
    list phys = [];
    integer n = llGetObjectPrimCount(llGetKey());
    integer l;
    for (l = 1; l <= n; ++l)
    {
        string nm = llGetLinkName(l);
        integer c = kind(nm);
        if (c & 4) WATERS += l; else NORMAL += l;
        if (c & 2) LIGHTS += l;
        if (c & 8) PLANTS += l;
        if (c & 16) FIRES += l;
        if (c & 32) POOLS += l;
        if (c & 64) SPAS += l;
        if (c & 1)
        {
            list p = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_SIZE]);
            vector sz = llList2Vector(p, 1);
            vector slide = <-0.95 * sz.x, 0.0, 0.0>;
            if (sz.y > sz.x) slide = <0.0, -0.95 * sz.y, 0.0>;
            DOORS += [l, llList2Vector(p, 0), slide];
        }
        if (c & 128) phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_NONE];
        if (c & 256) phys += [PRIM_LINK_TARGET, l, PRIM_PHYSICS_SHAPE_TYPE, PRIM_PHYSICS_SHAPE_PRIM];
        integer s = llListFindList(SEATS, [nm]);
        if (s >= 0)
        {
            vector off = llList2Vector(SEATS, s + 1);
            rotation r = llEuler2Rot(<0.0, 0.0, llList2Float(SEATS, s + 2) * DEG_TO_RAD>);
            string pose = llList2String(llCSV2List(llList2String(SEATS, s + 3)), 0);
            integer f = llListFindList(POSE_FIT, [pose]);
            vector fit = <0.1, 0.0, -0.23>;
            if (f >= 0) fit = <llList2Float(POSE_FIT, f + 1), 0.0, llList2Float(POSE_FIT, f + 2)>;
            llLinkSitTarget(l, off + <fit.x, 0.0, 0.0> * r + <0.0, 0.0, fit.z>, r);
        }
    }
    if (llGetListLength(phys)) llSetLinkPrimitiveParamsFast(LINK_THIS, phys);
    // plants are green whatever the fabric does
    apply_list(PLANTS, [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", <0.42, 0.55, 0.3>, "", "", "", ""]);
}

apply_list(list links, list params)
{
    integer i;
    integer n = llGetListLength(links);
    list out = [];
    for (i = 0; i < n; ++i)
    {
        out += [PRIM_LINK_TARGET, llList2Integer(links, i)] + params;
        if (llGetListLength(out) > 600) { llSetLinkPrimitiveParamsFast(LINK_THIS, out); out = []; }
    }
    if (llGetListLength(out)) llSetLinkPrimitiveParamsFast(LINK_THIS, out);
}

list minus(list a, list b)
{
    integer i;
    list out = [];
    for (i = 0; i < llGetListLength(a); ++i)
        if (llListFindList(b, [llList2Integer(a, i)]) < 0) out += llList2Integer(a, i);
    return out;
}

glow()
{
    float lv = LEVEL;
    if (!opt("lights")) lv = 0.0;
    apply_list(NORMAL, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", LED * lv, PRIM_GLOW, 7, 0.04 * lv,
                        PRIM_FULLBRIGHT, 7, lv > 0.05]);
    apply_list(LIGHTS, [PRIM_POINT_LIGHT, lv > 0.05, LED, lv, 7.0, 0.9]);
    pool();
}

pool()
{
    vector c = POOL;
    if (!opt("lights")) c = ZERO_VECTOR;
    apply_list(POOLS, [PRIM_GLTF_EMISSIVE, 7, "", "", "", "", c]);
    apply_list(WATERS, [PRIM_POINT_LIGHT, c != ZERO_VECTOR, c, 0.8, 9.0, 0.6]);
}

doors(integer open)
{
    DOOR_OPEN = open;
    integer i;
    integer step;
    if (opt("sounds") && llGetInventoryType("villa_door_slide") == INVENTORY_SOUND)
        llPlaySound("villa_door_slide", 0.6);
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

fire(integer on)
{
    integer i;
    for (i = 0; i < llGetListLength(FIRES); ++i)
    {
        integer l = llList2Integer(FIRES, i);
        if (on && opt("particles"))
            llLinkParticleSystem(l, [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK
                | PSYS_PART_INTERP_SCALE_MASK, PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE,
                PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.35, PSYS_SRC_BURST_RADIUS, 0.12,
                PSYS_PART_START_COLOR, <1.0, 0.62, 0.25>, PSYS_PART_END_COLOR, <1.0, 0.25, 0.05>,
                PSYS_PART_START_ALPHA, 0.75, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.18, 0.28, 0.0>, PSYS_PART_END_SCALE, <0.04, 0.1, 0.0>,
                PSYS_PART_MAX_AGE, 0.9, PSYS_SRC_BURST_RATE, 0.06, PSYS_SRC_BURST_PART_COUNT, 2,
                PSYS_SRC_BURST_SPEED_MIN, 0.25, PSYS_SRC_BURST_SPEED_MAX, 0.45,
                PSYS_SRC_ACCEL, <0.0, 0.0, 0.35>]);
        else llLinkParticleSystem(l, []);
    }
    apply_list(FIRES, [PRIM_POINT_LIGHT, on, <1.0, 0.55, 0.25>, 0.9, 6.0, 0.8]);
}

spa(integer on)
{
    integer i;
    for (i = 0; i < llGetListLength(SPAS); ++i)
    {
        if (on && opt("particles"))
            llLinkParticleSystem(llList2Integer(SPAS, i), [PSYS_PART_FLAGS, PSYS_PART_INTERP_SCALE_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE, PSYS_SRC_BURST_RADIUS, 1.2,
                PSYS_PART_START_COLOR, <0.95, 1.0, 1.0>, PSYS_PART_START_ALPHA, 0.55, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.05, 0.05, 0.0>, PSYS_PART_END_SCALE, <0.12, 0.12, 0.0>,
                PSYS_PART_MAX_AGE, 1.1, PSYS_SRC_BURST_RATE, 0.05, PSYS_SRC_BURST_PART_COUNT, 6,
                PSYS_SRC_BURST_SPEED_MIN, 0.05, PSYS_SRC_BURST_SPEED_MAX, 0.12, PSYS_SRC_ACCEL, <0.0, 0.0, 0.5>]);
        else llLinkParticleSystem(llList2Integer(SPAS, i), []);
    }
}

command(string msg)
{
    list a = llParseStringKeepNulls(msg, ["|"], []);
    string c = llList2String(a, 0);
    if (c == "MAT")
    {
        integer s = (integer)llList2String(a, 1);
        key m = (key)llList2String(a, 2);
        if (s == 8)
        {
            WATER_MAT = m;
            apply_list(WATERS, [PRIM_RENDER_MATERIAL, 0, m]);
            return;
        }
        apply_list(NORMAL, [PRIM_RENDER_MATERIAL, s, m]);
        if (s == 4)
        {
            apply_list(minus(NORMAL, PLANTS), [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", TINT, "", "", "", ""]);
            apply_list(PLANTS, [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", <0.42, 0.55, 0.3>, "", "", "", ""]);
        }
        if (s == 7) glow();
    }
    else if (c == "TINT")
    {
        TINT = (vector)llList2String(a, 1);
        apply_list(minus(NORMAL, PLANTS), [PRIM_GLTF_BASE_COLOR, 4, "", "", "", "", TINT, "", "", "", ""]);
    }
    else if (c == "GLOW") { LED = (vector)llList2String(a, 1); LEVEL = (float)llList2String(a, 2); glow(); }
    else if (c == "POOL") { POOL = (vector)llList2String(a, 1); pool(); }
    else if (c == "DOOR") { if ((integer)llList2String(a, 1) != DOOR_OPEN) doors((integer)llList2String(a, 1)); }
    else if (c == "FIRE") fire((integer)llList2String(a, 1));
    else if (c == "SPA") spa((integer)llList2String(a, 1));
    else if (c == "SOUND")
    {
        string snd = llList2String(a, 1);
        if (IS_CORE && snd != "" && opt("sounds") && llGetInventoryType(snd) == INVENTORY_SOUND)
            llLoopSound(snd, (float)llList2String(a, 2));
        else if (IS_CORE) llStopSound();
    }
    else if (c == "OPTS") { OPTS = llList2String(a, 1); glow(); }
    else if (c == "ACCESS") ACCESS = llList2String(a, 1);
    else if (c == "NUDGE" && !IS_CORE) llSetRegionPos(llGetPos() + (vector)llList2String(a, 1));
    else if (c == "DIE" && !IS_CORE) llDie();
}

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
                ASKED = av;
                llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION);
            }
        }
    }
    integer i;
    for (i = llGetListLength(SITTERS) - 3; i >= 0; i -= 3)
        if (llListFindList(now, [llList2Key(SITTERS, i)]) < 0) SITTERS = llDeleteSubList(SITTERS, i, i + 2);
}

list poses_of(integer link)
{
    integer s = llListFindList(SEATS, [llGetLinkName(link)]);
    if (s < 0) return [];
    return llCSV2List(llList2String(SEATS, s + 3));
}

play(key av, integer step)
{
    integer i = llListFindList(SITTERS, [av]);
    if (i < 0) return;
    list ps = poses_of(llList2Integer(SITTERS, i + 1));
    if (!llGetListLength(ps)) return;
    integer k = (llList2Integer(SITTERS, i + 2) + step) % llGetListLength(ps);
    SITTERS = llListReplaceList(SITTERS, [k], i + 2, i + 2);
    if (llGetAgentSize(av) == ZERO_VECTOR || llGetPermissionsKey() != av) return;
    if (!(llGetPermissions() & PERMISSION_TRIGGER_ANIMATION)) return;
    llStopAnimation("sit");
    integer j;
    for (j = 0; j < llGetListLength(ps); ++j)
        if (j != k && llGetInventoryType(llList2String(ps, j)) == INVENTORY_ANIMATION) llStopAnimation(llList2String(ps, j));
    if (llGetInventoryType(llList2String(ps, k)) == INVENTORY_ANIMATION) llStartAnimation(llList2String(ps, k));
    else llStartAnimation("sit");
}

init()
{
    // the Villa Core is the linkset with the deck; in a house a stray villa_core removes itself
    IS_CORE = FALSE;
    integer house = FALSE;
    integer l;
    for (l = 2; l <= llGetObjectPrimCount(llGetKey()); ++l)
    {
        string nm = llGetLinkName(l);
        if (llSubStringIndex(nm, "Site_") == 0) IS_CORE = TRUE;
        if (llSubStringIndex(nm, "Nautilus_") == 0 || llSubStringIndex(nm, "Dune_") == 0
            || llSubStringIndex(nm, "Nocturne_") == 0) house = TRUE;
    }
    if (!house && llGetInventoryType("villa_core") == INVENTORY_SCRIPT) IS_CORE = TRUE;
    CH = -1 - (integer)("0x" + llGetSubString((string)llGetOwner(), 0, 6)) % 1000000 - 4100000;
    scan();
    if (!IS_CORE)
    {
        llListen(CH, "", NULL_KEY, "");
        CORE = llList2Key(llGetObjectDetails(llGetKey(), [OBJECT_REZZER_KEY]), 0);
        if (CORE != NULL_KEY && CORE != llGetKey()) llRegionSayTo(CORE, CH, "V|HELLO|" + llGetObjectName());
    }
}

default
{
    state_entry() { init(); }
    on_rez(integer p) { llResetScript(); }

    changed(integer c)
    {
        if (c & CHANGED_OWNER) llResetScript();
        if (c & CHANGED_LINK) seat_check();
    }

    link_message(integer s, integer n, string m, key id) { if (n == 7100) command(m); }

    listen(integer ch, string nm, key id, string m)
    {
        if (llGetOwnerKey(id) != llGetOwner() || llGetSubString(m, 0, 1) != "V|") return;
        CORE = id;
        command(llDeleteSubString(m, 0, 1));
    }

    run_time_permissions(integer p)
    {
        if (p & PERMISSION_TRIGGER_ANIMATION) play(llGetPermissionsKey(), 0);
    }

    touch_start(integer t)
    {
        key av = llDetectedKey(0);
        integer l = llDetectedLinkNumber(0);
        integer i = llListFindList(SITTERS, [av]);
        if (i >= 0 && llList2Integer(SITTERS, i + 1) == l)
        {
            if (llGetPermissionsKey() != av) llRequestPermissions(av, PERMISSION_TRIGGER_ANIMATION);
            else play(av, 1);          // touch your own seat: next pose
            return;
        }
        if (kind(llGetLinkName(l)) & 1)
        {
            if (allowed(av)) doors(!DOOR_OPEN);
            return;
        }
        if (IS_CORE) llMessageLinked(LINK_THIS, 7101, "", av);
        else if (CORE != NULL_KEY) llRegionSayTo(CORE, CH, "V|MENU|" + (string)av);
    }
}

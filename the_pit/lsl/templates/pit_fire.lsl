// =====================================================================
//  THE PIT - LIVING FIRE, FOG AND ATMOSPHERE (root prim)
//
//  * Animated flames: every torch, lantern and brazier emits a particle
//    flame (a white-yellow core that rises, widens and dies in dark red)
//    over the mesh flame, which is its heart. Fire pieces have their
//    centre exactly at the base of the flame.
//  * Breathing light: intensity, radius and colour follow a smooth noise
//    of their own for every fire, with crackles (a short flare and a
//    shower of sparks) and gasps (the flame nearly chokes, then recovers).
//  * Draughts: when a door moves or someone rattles the bars, the fires
//    within 8 m lean over and gutter as if air rushed in.
//  * Sea fog over the channel, low mist in the kennel, steam over the
//    cistern, drips falling from the vaults.
//  * Moods (chosen by the Lord from the throne): WATCH, GLOOM,
//    JUDGEMENT (everything red, braziers roaring) and DARKNESS (only the
//    braziers burn).
//  * With the effect textures: animated mesh flame (4x4 flipbook), smoke
//    alternating with the flame on the braziers, and projector lights
//    that cast the bars and chains across floors and walls.
//
//  * Moonlight through the grates of the light wells in the vaults, sea
//    light (caustics) under the yard beams, dust drifting in the light.
//  * Sounds (if their files are in the Contents): fire_loop on the braziers,
//    torch_loop in the cells, sea_loop on the channel, ambient_wind at the
//    gate, drips from the vaults, whip_crack and splash with the bursts.
//
//  Switches (/7 settings): fire (master), flames, lights, flicker, glow,
//  flipbook, smoke, sparks, projectors, gusts, fog, drips, bursts, moods,
//  light_wells, caustics, dust, sounds.
// =====================================================================

// ---------------------------------------------------------------------
//  EFFECT TEXTURES (made by scripts/effect_sprites.py in output/effects/)
//  Easiest way: upload the PNGs (Build > Upload > Image) and drop them in
//  the root prim's Contents tab with these names (an upload keeps the
//  file name): fire_flipbook, flame_particle, smoke, fog, spark, drip,
//  fire_projector. The script finds them by name: nothing to paste.
//  Or paste a texture UUID between the quotes below (a UUID wins over the
//  Contents). Missing texture = default particle / no flipbook / no
//  alternating smoke / no projector.
//  Projector lights and their shadows only show with shadows enabled in
//  the viewer (Preferences > Graphics > Shadows: "Sun/Moon + Projectors").
//  They project along the piece's local -Z (downwards).
// ---------------------------------------------------------------------
string  UUID_FLIPBOOK = "";      // fire_flipbook.png   mesh flame (face 2), 4x4 frames
string  UUID_FLAME = "";         // flame_particle.png  flame particle
string  UUID_SMOKE = "";         // smoke.png           smoke rising from the braziers
string  UUID_FOG = "";           // fog.png             channel fog, mist and steam
string  UUID_SPARK = "";         // spark.png           crackles and branding sparks
string  UUID_DRIP = "";          // drip.png            drips from the vaults
string  UUID_PROJECTOR = "";     // fire_projector.png  projector light (throne braziers, kennel
                                 //                     lantern, yard lanterns)
float   FLIPBOOK_FPS = 12.0;
// SL sorts mesh faces by material name: the flame is face 2 in both the English and the
// Spanish upload (Bone Cloth FLAME Floor... / Hierro Hueso LLAMA Madera...)
integer FLAME = 2;     // flipbook frames per second (each fire varies a little)
//@@CONSTANTS@@

float   TICK = 0.2;
integer PER_TICK = 4;

string T_FLIPBOOK; string T_FLAME; string T_SMOKE; string T_FOG; string T_SPARK; string T_DRIP; string T_PROJECTOR;
string T_WELL; string T_CAUSTIC; string T_DUST;

list F_LINK; list F_TYPE; list F_POS; list F_LEVEL; list F_VEL; list F_GUST;  // type: 0 torch, 1 lantern, 2 brazier
list F_SMOKE; list F_PROJ;   // smoke: next switch time (>0 flame, <0 smoke); proj: carries a projector light
integer CURSOR; integer PRIMS; integer IDLE_CHECK; integer IDLE;
string MOOD = "WATCH";
float  K_LIGHT = 1.0; float K_RADIUS = 1.0; vector TINT = <1.0, 0.55, 0.22>; float FOG_DENSITY = 1.0;

string OPTS;
integer FIRE; integer FLAMES; integer LIGHTS; integer FLICKER; integer GLOW; integer FLIP; integer SMOKE;
integer SPARKS; integer PROJ; integer GUSTS; integer FOG; integer DRIPS; integer BURSTS; integer MOODS;
integer WELLS; integer CAUSTIC; integer DUST; integer SOUNDS;

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

load_options()
{
    OPTS = llLinksetDataRead("opts");
    FIRE = opt("fire");
    FLAMES = FIRE && opt("flames");
    LIGHTS = FIRE && opt("lights");
    FLICKER = FIRE && opt("flicker");
    GLOW = FIRE && opt("glow");
    FLIP = FIRE && opt("flipbook");
    SMOKE = FIRE && opt("smoke");
    SPARKS = FIRE && opt("sparks");
    PROJ = LIGHTS && opt("projectors");
    GUSTS = FLAMES && opt("gusts");
    FOG = opt("fog");
    DRIPS = opt("drips");
    BURSTS = opt("bursts");
    MOODS = opt("moods");
    WELLS = opt("light_wells");
    CAUSTIC = opt("caustics");
    DUST = opt("dust");
    SOUNDS = opt("sounds");
    if (!MOODS) MOOD = "WATCH";
}

// an item of the Contents by name, with or without the "pit_" prefix of the delivered files
string asset(string name, integer type)
{
    if (llGetInventoryType("pit_" + name) == type) return "pit_" + name;
    if (llGetInventoryType(name) == type) return name;
    return "";
}

string tex(string uuid, string name)
{
    if (uuid != "") return uuid;
    return asset(name, INVENTORY_TEXTURE);
}

load_textures()
{
    T_FLIPBOOK = tex(UUID_FLIPBOOK, "fire_flipbook");
    T_FLAME = tex(UUID_FLAME, "flame_particle");
    T_SMOKE = tex(UUID_SMOKE, "smoke");
    T_FOG = tex(UUID_FOG, "fog");
    T_SPARK = tex(UUID_SPARK, "spark");
    T_DRIP = tex(UUID_DRIP, "drip");
    T_PROJECTOR = tex(UUID_PROJECTOR, "fire_projector");
    T_WELL = tex("", "light_well");
    T_CAUSTIC = tex("", "caustics");
    T_DUST = tex("", "dust_mote");
}

integer has_sound(string s) { return asset(s, INVENTORY_SOUND) != ""; }

// specks of dust and ash drifting in the light of the cells and the yard
list dust()
{
    if (!DUST) return [];
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
            PSYS_SRC_TEXTURE, T_DUST,
            PSYS_PART_START_COLOR, <1.0, 0.86, 0.66>, PSYS_PART_END_COLOR, <0.8, 0.7, 0.6>,
            PSYS_PART_START_ALPHA, 0.0, PSYS_PART_END_ALPHA, 0.35,
            PSYS_PART_START_SCALE, <0.02, 0.02, 0.0>, PSYS_PART_END_SCALE, <0.03, 0.03, 0.0>,
            PSYS_PART_MAX_AGE, 14.0, PSYS_SRC_BURST_RATE, 0.9, PSYS_SRC_BURST_PART_COUNT, 1,
            PSYS_SRC_BURST_RADIUS, 1.6, PSYS_SRC_BURST_SPEED_MIN, 0.0, PSYS_SRC_BURST_SPEED_MAX, 0.03,
            PSYS_SRC_ACCEL, <0.0, 0.0, 0.012>, PSYS_SRC_MAX_AGE, 0.0];
}

list flame(integer type, float wind_x, float wind_y)
{
    if (!FLAMES || (MOOD == "DARKNESS" && type != 2)) return [];
    // few, larger particles: 24 fires stay well under the viewer's particle budget
    float sc = 0.11; float life = 0.7; integer count = 1; float rise = 0.55;
    if (type == 1) { sc = 0.055; life = 0.5; count = 1; rise = 0.3; }
    if (type == 2) { sc = 0.26; life = 1.0; count = 3; rise = 0.9; }
    if (MOOD == "JUDGEMENT") { sc = sc * 1.3; rise = rise * 1.4; }
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.25,
            PSYS_SRC_TEXTURE, T_FLAME,
            PSYS_PART_START_COLOR, <1.0, 0.92, 0.6>, PSYS_PART_END_COLOR, <0.75, 0.12, 0.02>,
            PSYS_PART_START_ALPHA, 0.85, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <sc, sc * 1.6, 0.0>, PSYS_PART_END_SCALE, <sc * 0.3, sc * 0.6, 0.0>,
            PSYS_PART_MAX_AGE, life, PSYS_SRC_BURST_RATE, 0.08, PSYS_SRC_BURST_PART_COUNT, count,
            PSYS_SRC_BURST_RADIUS, sc * 0.2, PSYS_SRC_BURST_SPEED_MIN, 0.03, PSYS_SRC_BURST_SPEED_MAX, 0.12,
            PSYS_SRC_ACCEL, <wind_x, wind_y, rise>, PSYS_SRC_MAX_AGE, 0.0];
}

list sparks()
{
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.6,
            PSYS_SRC_TEXTURE, T_SPARK,
            PSYS_PART_START_COLOR, <1.0, 0.85, 0.4>, PSYS_PART_END_COLOR, <0.9, 0.2, 0.0>,
            PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <0.03, 0.03, 0.0>, PSYS_PART_END_SCALE, <0.01, 0.01, 0.0>,
            PSYS_PART_MAX_AGE, 1.8, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 6,
            PSYS_SRC_BURST_SPEED_MIN, 0.6, PSYS_SRC_BURST_SPEED_MAX, 1.6,
            PSYS_SRC_ACCEL, <0.0, 0.0, 0.4>, PSYS_SRC_MAX_AGE, 0.0];
}

// brazier smoke: alternates with the particle flame (a prim has only one
// particle system); while it smokes, the animated mesh flame keeps burning
list smoke()
{
    return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.2,
            PSYS_SRC_TEXTURE, T_SMOKE,
            PSYS_PART_START_COLOR, <0.30, 0.27, 0.24>, PSYS_PART_END_COLOR, <0.16, 0.15, 0.14>,
            PSYS_PART_START_ALPHA, 0.32, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <0.3, 0.3, 0.0>, PSYS_PART_END_SCALE, <1.5, 1.5, 0.0>,
            PSYS_PART_MAX_AGE, 4.5, PSYS_SRC_BURST_RATE, 0.12, PSYS_SRC_BURST_PART_COUNT, 1,
            PSYS_SRC_BURST_RADIUS, 0.05, PSYS_SRC_BURST_SPEED_MIN, 0.35, PSYS_SRC_BURST_SPEED_MAX, 0.6,
            PSYS_SRC_ACCEL, <0.0, 0.0, 0.15>, PSYS_SRC_MAX_AGE, 0.0];
}

list fog(float density, vector colour, float radius)
{
    if (!FOG || density <= 0.0) return [];
    return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 1.2, PSYS_SRC_ANGLE_END, 1.57,
            PSYS_SRC_TEXTURE, T_FOG,
            PSYS_PART_START_COLOR, colour, PSYS_PART_END_COLOR, colour,
            PSYS_PART_START_ALPHA, 0.0, PSYS_PART_END_ALPHA, 0.09 * density,
            PSYS_PART_START_SCALE, <1.5, 1.5, 0.0>, PSYS_PART_END_SCALE, <4.0, 4.0, 0.0>,
            PSYS_PART_MAX_AGE, 14.0, PSYS_SRC_BURST_RATE, 0.35, PSYS_SRC_BURST_PART_COUNT, 2,
            PSYS_SRC_BURST_RADIUS, radius, PSYS_SRC_BURST_SPEED_MIN, 0.05, PSYS_SRC_BURST_SPEED_MAX, 0.25,
            PSYS_SRC_ACCEL, <0.0, 0.0, -0.01>, PSYS_SRC_MAX_AGE, 0.0];
}

list drips()
{
    if (!DRIPS) return [];
    return [PSYS_PART_FLAGS, PSYS_PART_FOLLOW_VELOCITY_MASK | PSYS_PART_INTERP_COLOR_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
            PSYS_SRC_TEXTURE, T_DRIP,
            PSYS_PART_START_COLOR, <0.7, 0.8, 0.85>, PSYS_PART_END_COLOR, <0.7, 0.8, 0.85>,
            PSYS_PART_START_ALPHA, 0.55, PSYS_PART_END_ALPHA, 0.35,
            PSYS_PART_START_SCALE, <0.012, 0.07, 0.0>, PSYS_PART_END_SCALE, <0.012, 0.09, 0.0>,
            PSYS_PART_MAX_AGE, 1.15, PSYS_SRC_BURST_RATE, 1.7, PSYS_SRC_BURST_PART_COUNT, 1,
            PSYS_SRC_BURST_RADIUS, 2.2, PSYS_SRC_BURST_SPEED_MIN, 0.0, PSYS_SRC_BURST_SPEED_MAX, 0.0,
            PSYS_SRC_ACCEL, <0.0, 0.0, -9.8>, PSYS_SRC_MAX_AGE, 0.0];
}

list burst(string what)
{
    if (what == "clothes")     // rags falling through the hatch in the kennel roof
        return [PSYS_PART_FLAGS, PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
                PSYS_PART_START_COLOR, <0.75, 0.7, 0.6>, PSYS_PART_END_COLOR, <0.6, 0.55, 0.45>,
                PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.9,
                PSYS_PART_START_SCALE, <0.3, 0.22, 0.0>, PSYS_PART_END_SCALE, <0.35, 0.25, 0.0>,
                PSYS_PART_MAX_AGE, 2.4, PSYS_SRC_BURST_RATE, 0.05, PSYS_SRC_BURST_PART_COUNT, 3,
                PSYS_SRC_BURST_RADIUS, 0.4, PSYS_SRC_BURST_SPEED_MIN, 0.2, PSYS_SRC_BURST_SPEED_MAX, 0.8,
                PSYS_SRC_ACCEL, <0.0, 0.0, -2.2>, PSYS_SRC_MAX_AGE, 1.5];
    if (what == "splash")
        return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.9,
                PSYS_PART_START_COLOR, <0.85, 0.9, 0.95>, PSYS_PART_END_COLOR, <0.6, 0.7, 0.75>,
                PSYS_PART_START_ALPHA, 0.9, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.08, 0.08, 0.0>, PSYS_PART_END_SCALE, <0.03, 0.03, 0.0>,
                PSYS_PART_MAX_AGE, 1.0, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 12,
                PSYS_SRC_BURST_SPEED_MIN, 1.5, PSYS_SRC_BURST_SPEED_MAX, 3.0,
                PSYS_SRC_ACCEL, <0.0, 0.0, -6.0>, PSYS_SRC_MAX_AGE, 0.6];
    // branding iron / lash: dust and sparks
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
            PSYS_SRC_TEXTURE, T_SPARK,
            PSYS_PART_START_COLOR, <1.0, 0.7, 0.3>, PSYS_PART_END_COLOR, <0.5, 0.1, 0.0>,
            PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <0.04, 0.04, 0.0>, PSYS_PART_END_SCALE, <0.01, 0.01, 0.0>,
            PSYS_PART_MAX_AGE, 1.2, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 15,
            PSYS_SRC_BURST_SPEED_MIN, 1.0, PSYS_SRC_BURST_SPEED_MAX, 2.5,
            PSYS_SRC_ACCEL, <0.0, 0.0, -2.0>, PSYS_SRC_MAX_AGE, 0.5];
}

integer link_of(string name)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (piece(i) == name) return i;
    return -1;
}

// throne braziers, kennel lantern and yard lanterns
integer is_projector(string nm)
{
    if (llSubStringIndex(nm, "N_Brazier") == 0) return TRUE;
    if (nm == "C05_Lantern") return TRUE;
    if (llGetSubString(nm, 0, 0) == "T" && llSubStringIndex(nm, "_Lantern") != -1) return TRUE;
    return FALSE;
}

// light and glow of fire i at level lv (1 = at rest)
light(integer i, float lv)
{
    integer type = llList2Integer(F_TYPE, i);
    list p = [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0.0, 0.0, 0.0];
    if (LIGHTS)
    {
        // intensity is capped at 1.0 by SL: the peak (lv 1.5) stays just under it so the flicker shows
        float base = 0.6; float radius = 6.0; float falloff = 1.4;
        if (type == 1) { base = 0.4; radius = 4.5; }
        if (type == 2) { base = 0.62; radius = 10.0; }
        if (MOOD == "JUDGEMENT") { radius = radius * 1.4; falloff = 0.8; }
        float k = K_LIGHT; if (type == 2 && MOOD == "DARKNESS") k = 0.7;
        vector col = TINT + <0.0, (lv - 1.0) * 0.12, (lv - 1.0) * 0.05>;
        p = [PRIM_POINT_LIGHT, TRUE, llsRGB2Linear(col), base * k * lv, radius * K_RADIUS * (0.9 + 0.1 * lv), falloff];
    }
    if (GLOW) p += [PRIM_GLOW, FLAME, 0.12 + 0.2 * lv];
    else p += [PRIM_GLOW, FLAME, 0.0];
    llSetLinkPrimitiveParamsFast(llList2Integer(F_LINK, i), p);
}

atmosphere()
{
    integer a = link_of("P_Water");
    if (a > 0) llLinkParticleSystem(a, fog(FOG_DENSITY, <0.55, 0.62, 0.68>, 1.2));
    a = link_of("C05_Floor");
    if (a > 0) llLinkParticleSystem(a, fog(FOG_DENSITY * 0.8, <0.45, 0.42, 0.38>, 0.7));
    a = link_of("C04_Water");
    if (a > 0) llLinkParticleSystem(a, fog(FOG_DENSITY * 1.2, <0.8, 0.85, 0.9>, 0.6));
    list vaults = ["C01_Vault", "C02_Vault", "C03_Vault", "C04_Vault", "C07_Vault", "C08_Vault"];
    integer i;
    for (i = 0; i < llGetListLength(vaults); ++i)
    {
        a = link_of(llList2String(vaults, i));
        if (a > 0)
        {
            llLinkParticleSystem(a, drips());
            // cold moonlight falling through the grate of the light well in the crown of the vault
            if (WELLS && T_WELL != "")
                llSetLinkPrimitiveParamsFast(a, [PRIM_POINT_LIGHT, TRUE, llsRGB2Linear(<0.55, 0.66, 0.9>), 0.45, 5.0, 1.2,
                                                 PRIM_PROJECTOR, T_WELL, 0.9, 3.0, 0.02]);
            else llSetLinkPrimitiveParamsFast(a, [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0.0, 0.0, 0.0,
                                                  PRIM_PROJECTOR, NULL_KEY, 0.9, 3.0, 0.0]);
        }
    }
    // sea light thrown about by the channel
    list beams = ["T1_Beam", "T3_Beam"];
    for (i = 0; i < 2; ++i)
    {
        a = link_of(llList2String(beams, i));
        if (a > 0)
        {
            if (CAUSTIC && T_CAUSTIC != "")
                llSetLinkPrimitiveParamsFast(a, [PRIM_POINT_LIGHT, TRUE, llsRGB2Linear(<0.45, 0.8, 0.8>), 0.3, 7.0, 1.0,
                                                 PRIM_PROJECTOR, T_CAUSTIC, 1.4, 4.0, 0.0]);
            else llSetLinkPrimitiveParamsFast(a, [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0.0, 0.0, 0.0,
                                                  PRIM_PROJECTOR, NULL_KEY, 1.4, 4.0, 0.0]);
        }
    }
    list floors = ["P1_Floor", "P2_Floor", "P3_Floor", "P4_Floor", "C01_Floor", "C02_Floor", "C03_Floor",
                   "C07_Floor", "C08_Floor"];
    for (i = 0; i < llGetListLength(floors); ++i)
    {
        a = link_of(llList2String(floors, i));
        if (a > 0) llLinkParticleSystem(a, dust());
    }
    // the sea against the rock, and the wind through the arrow slits
    loop_sound(link_of("P_Water"), "sea_loop", 0.7);
    loop_sound(link_of("G_Tower_W"), "ambient_wind", 0.5);
}

loop_sound(integer l, string s, float vol)
{
    if (l < 1) return;
    if (SOUNDS && has_sound(s) && vol > 0.0) llLinkPlaySound(l, asset(s, INVENTORY_SOUND), vol, SOUND_LOOP);
    else llLinkStopSound(l);
}

apply()
{
    if (MOOD == "WATCH") { K_LIGHT = 1.0; K_RADIUS = 1.0; TINT = <1.0, 0.55, 0.22>; FOG_DENSITY = 1.0; }
    else if (MOOD == "GLOOM") { K_LIGHT = 0.5; K_RADIUS = 0.7; TINT = <1.0, 0.45, 0.18>; FOG_DENSITY = 1.6; }
    else if (MOOD == "JUDGEMENT") { K_LIGHT = 1.0; K_RADIUS = 1.0; TINT = <1.0, 0.25, 0.08>; FOG_DENSITY = 0.8; }
    else if (MOOD == "DARKNESS") { K_LIGHT = 0.0; K_RADIUS = 0.6; TINT = <0.9, 0.3, 0.1>; FOG_DENSITY = 2.2; }
    // the flipbook texture already carries the colour: the tint only warms it a little
    vector flame_tint = <1.0, 0.7, 0.35>;
    integer use_flip = FLIP && T_FLIPBOOK != "";
    if (use_flip) flame_tint = <1.0, 0.92, 0.82>;
    integer i;
    for (i = 0; i < llGetListLength(F_LINK); ++i)
    {
        integer l = llList2Integer(F_LINK, i);
        integer type = llList2Integer(F_TYPE, i);
        integer dead = !FIRE || (MOOD == "DARKNESS" && type != 2);
        llLinkParticleSystem(l, flame(type, 0.0, 0.0));
        if (use_flip && !dead)
        {
            llSetLinkPrimitiveParamsFast(l, [PRIM_TEXTURE, FLAME, T_FLIPBOOK, <1.0, 1.0, 0.0>, ZERO_VECTOR, 0.0,
                                            PRIM_ALPHA_MODE, FLAME, PRIM_ALPHA_MODE_BLEND, 0]);
            // a slightly different speed for every fire: they never pulse together
            llSetLinkTextureAnim(l, ANIM_ON | LOOP, FLAME, 4, 4, 0.0, 16.0, FLIPBOOK_FPS * (0.82 + 0.045 * (i % 9)));
        }
        else
        {
            llSetLinkTextureAnim(l, FALSE, FLAME, 4, 4, 0.0, 16.0, 1.0);
            // flipbook switched off: a plain solid flame instead of the whole 4x4 sheet
            if (T_FLIPBOOK != "")
                llSetLinkPrimitiveParamsFast(l, [PRIM_TEXTURE, FLAME, TEXTURE_BLANK, <1.0, 1.0, 0.0>, ZERO_VECTOR, 0.0,
                                                PRIM_ALPHA_MODE, FLAME, PRIM_ALPHA_MODE_NONE, 0]);
        }
        if (llList2Integer(F_PROJ, i))
        {
            // wide FOV, short focus and low ambience: bars and chains in shadow
            float fov = 2.2;
            if (type == 2) fov = 2.8;
            if (PROJ && T_PROJECTOR != "" && !dead)
                llSetLinkPrimitiveParamsFast(l, [PRIM_PROJECTOR, T_PROJECTOR, fov, 1.5, 0.08]);
            else llSetLinkPrimitiveParamsFast(l, [PRIM_PROJECTOR, NULL_KEY, fov, 1.5, 0.0]);
        }
        // crackle: braziers roar, cell torches hiss (only some torches, to spare the viewer's sound slots)
        if (type == 2) loop_sound(l, "fire_loop", 0.8 * (!dead));
        else if (type == 0 && llGetSubString(piece(l), 0, 0) == "C") loop_sound(l, "torch_loop", 0.45 * (!dead));
        if (dead)
            llSetLinkPrimitiveParamsFast(l, [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0.0, 0.0, 0.0, PRIM_GLOW, FLAME, 0.0,
                                            PRIM_COLOR, FLAME, <0.1, 0.05, 0.03>, 1.0, PRIM_FULLBRIGHT, FLAME, FALSE]);
        else
        {
            llSetLinkPrimitiveParamsFast(l, [PRIM_COLOR, FLAME, flame_tint, 1.0, PRIM_FULLBRIGHT, FLAME, TRUE]);
            light(i, 1.0);
        }
    }
    // candles and lamps modelled into props, desks and tables: their flame face glows
    for (i = 0; i < llGetListLength(CANDLES); ++i)
    {
        integer c = link_of(llList2String(CANDLES, i));
        if (c > 0)
        {
            if (FIRE && MOOD != "DARKNESS")
                llSetLinkPrimitiveParamsFast(c, [PRIM_COLOR, FLAME, <1.0, 0.78, 0.45>, 1.0, PRIM_FULLBRIGHT, FLAME, TRUE,
                                                 PRIM_GLOW, FLAME, 0.18 * GLOW, PRIM_RENDER_MATERIAL, FLAME, NULL_KEY]);
            else
                llSetLinkPrimitiveParamsFast(c, [PRIM_COLOR, FLAME, <0.12, 0.08, 0.05>, 1.0, PRIM_FULLBRIGHT, FLAME, FALSE,
                                                 PRIM_GLOW, FLAME, 0.0]);
        }
    }
    atmosphere();
    // the timer only runs while something needs animating
    if (llGetListLength(F_LINK) && FIRE && ((FLICKER && (LIGHTS || GLOW)) || SPARKS || GUSTS || (SMOKE && T_SMOKE != "")))
        llSetTimerEvent(TICK);
    else llSetTimerEvent(0.0);
}

scan()
{
    F_LINK = []; F_TYPE = []; F_POS = []; F_LEVEL = []; F_VEL = []; F_GUST = []; F_SMOKE = []; F_PROJ = [];
    integer n = llGetObjectPrimCount(llGetKey());
    PRIMS = n;
    integer i;
    for (i = 1; i <= n; ++i)
    {
        string nm = piece(i);
        integer t = -1;
        if (llSubStringIndex(nm, "Torch") != -1) t = 0;
        else if (llSubStringIndex(nm, "Lantern") != -1) t = 1;
        else if (llSubStringIndex(nm, "Brazier") != -1) t = 2;
        if (t >= 0)
        {
            vector p = ZERO_VECTOR;
            if (i > 1) p = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0);
            // older scripts animated face 7 (wood or cloth): give it back its plain look once
            vector c7 = <0.36, 0.24, 0.14>;                                   // wood (English upload)
            if (llLinksetDataRead("faces") == "es") c7 = <0.38, 0.34, 0.28>;  // cloth (Spanish upload)
            llSetLinkPrimitiveParamsFast(i, [PRIM_GLOW, 7, 0.0, PRIM_FULLBRIGHT, 7, FALSE, PRIM_COLOR, 7, c7, 1.0,
                PRIM_TEXTURE, 7, TEXTURE_BLANK, <1.0, 1.0, 0.0>, ZERO_VECTOR, 0.0, PRIM_ALPHA_MODE, 7, PRIM_ALPHA_MODE_NONE, 0,
                PRIM_RENDER_MATERIAL, FLAME, NULL_KEY]);
            F_LINK += i; F_TYPE += t; F_POS += p; F_LEVEL += 1.0; F_VEL += 0.0; F_GUST += 0;
            F_SMOKE += llGetTime() + 2.0 + llFrand(5.0); F_PROJ += is_projector(nm);
        }
    }
    apply();
}

report()
{
    integer n = llGetListLength(F_LINK);
    integer t = 0; integer l = 0; integer b = 0; integer i;
    for (i = 0; i < n; ++i)
    {
        integer k = llList2Integer(F_TYPE, i);
        if (k == 0) ++t; else if (k == 1) ++l; else ++b;
    }
    list tex = [];
    if (T_FLIPBOOK != "") tex += "fire_flipbook";
    if (T_FLAME != "") tex += "flame_particle";
    if (T_SMOKE != "") tex += "smoke";
    if (T_FOG != "") tex += "fog";
    if (T_SPARK != "") tex += "spark";
    if (T_DRIP != "") tex += "drip";
    if (T_PROJECTOR != "") tex += "fire_projector";
    string s = "pit_fire: " + (string)n + " fires (" + (string)t + " torches, " + (string)l + " lanterns, "
        + (string)b + " braziers; 24 expected). Effect textures: ";
    if (tex == []) s += "none (optional)"; else s += llDumpList2String(tex, ", ");
    if (n == 0) s += ". NO FIRES: the pieces still have their old names - is pit_core in the root?";
    llOwnerSay(s + " - memory " + (string)(llGetUsedMemory() / 1024) + " of 64 KB.");
}

default
{
    state_entry() { load_options(); load_textures(); scan(); report(); }
    on_rez(integer p) { llResetScript(); }
    changed(integer c)
    {
        // sitting down or standing up also raises CHANGED_LINK: rescan only if the prims changed
        if ((c & CHANGED_LINK) && llGetObjectPrimCount(llGetKey()) != PRIMS) scan();
        else if (c & CHANGED_INVENTORY) { load_textures(); apply(); }
    }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) { load_options(); apply(); }
    }

    link_message(integer s, integer num, string str, key id)
    {
        if (num == 9001) { scan(); report(); }
        else if (num == 9800) report();
        else if (num == 9200) { if (MOODS) { MOOD = str; apply(); } }
        else if (num == 9100)
        {
            if (!GUSTS) return;
            // a draught from a door: the fires nearby lean over
            list p = llParseString2List(str, ["|"], []);
            string tag = llList2String(p, 1);
            integer l = link_of(tag + "_Door");
            if (tag == "G") l = link_of("G_Leaf_W");
            if (tag == "R") l = link_of("G_Portcullis");
            if (l < 0) return;
            vector o = llList2Vector(llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL]), 0);
            integer i;
            for (i = 0; i < llGetListLength(F_LINK); ++i)
            {
                vector fp = llList2Vector(F_POS, i);
                if (llVecDist(fp, o) < 8.0)
                {
                    vector v = llVecNorm(fp - o) * 1.2;
                    F_GUST = llListReplaceList(F_GUST, [18 + (integer)llFrand(10)], i, i);
                    llLinkParticleSystem(llList2Integer(F_LINK, i), flame(llList2Integer(F_TYPE, i), v.x, v.y));
                }
            }
        }
        else if (num == 9300)
        {
            if (!BURSTS) return;
            string where = "";
            if (str == "clothes") where = "C05_Roof";
            else if (str == "splash") where = "C04_Water";
            else if (str == "brand") where = "C01_Branding_Brazier";
            else if (str == "lash") where = "C08_Mast";
            integer l = link_of(where);
            if (l > 0)
            {
                llLinkParticleSystem(l, burst(str));
                if (SOUNDS || opt("door_sounds"))
                {
                    if (str == "lash" && has_sound("whip_crack")) llLinkPlaySound(l, asset("whip_crack", INVENTORY_SOUND), 1.0, SOUND_PLAY);
                    if (str == "splash" && has_sound("splash")) llLinkPlaySound(l, asset("splash", INVENTORY_SOUND), 1.0, SOUND_PLAY);
                }
                llSleep(2.0);
                if (str == "brand") llLinkParticleSystem(l, flame(2, 0.0, 0.0));
                else if (str == "splash") atmosphere();
                else llLinkParticleSystem(l, []);
            }
        }
    }

    timer()
    {
        integer n = llGetListLength(F_LINK);
        if (n == 0) return;
        // nobody on the parcel: let the fire rest (checked every ~10 s)
        if (++IDLE_CHECK >= 50) { IDLE_CHECK = 0; IDLE = (llGetAgentList(AGENT_LIST_PARCEL, []) == []); }
        if (IDLE) return;
        if (SOUNDS && llFrand(1.0) < 0.012)
        {
            integer v = link_of(llList2String(["C01_Vault", "C02_Vault", "C03_Vault", "C04_Vault", "C07_Vault", "C08_Vault", "N_Back_C"],
                                              (integer)llFrand(7)));
            string d = "drip_" + (string)(1 + (integer)llFrand(3));
            if (v > 0 && has_sound(d)) llLinkPlaySound(v, asset(d, INVENTORY_SOUND), 0.25 + llFrand(0.3), SOUND_TRIGGER);
        }
        integer j;
        for (j = 0; j < PER_TICK; ++j)
        {
            CURSOR = (CURSOR + 1) % n;
            integer i = CURSOR;
            integer type = llList2Integer(F_TYPE, i);
            integer l = llList2Integer(F_LINK, i);
            if (MOOD == "DARKNESS" && type != 2) jump skip;
            // smooth noise: a damped random walk around 1
            float lv = 1.0; float vel = 0.0;
            if (FLICKER)
            {
                lv = llList2Float(F_LEVEL, i);
                vel = llList2Float(F_VEL, i) * 0.6 + (llFrand(0.3) - 0.15) + (1.0 - lv) * 0.25;
                lv += vel * 0.5;
            }
            integer gust = llList2Integer(F_GUST, i);
            if (gust > 0)
            {
                if (FLICKER) lv = 0.35 + llFrand(0.5);
                --gust;
                if (gust == 0) llLinkParticleSystem(l, flame(type, 0.0, 0.0));
            }
            float dice = llFrand(1.0);
            if (dice < 0.012)          // crackle: a flare and sparks
            {
                if (FLICKER) lv = 1.45;
                if (SPARKS) { llLinkParticleSystem(l, sparks()); gust = 2; }
            }
            else if (dice < 0.02 && FLICKER) lv = 0.4;   // gasp
            // braziers: every few seconds the system turns from flame to smoke and back
            if (type == 2 && gust == 0 && SMOKE && T_SMOKE != "")
            {
                float ts = llList2Float(F_SMOKE, i);
                float now = llGetTime();
                if (ts > 0.0 && now > ts)
                {
                    llLinkParticleSystem(l, smoke());
                    ts = -(now + 2.5 + llFrand(2.5));
                }
                else if (ts < 0.0 && now > -ts)
                {
                    llLinkParticleSystem(l, flame(type, 0.0, 0.0));
                    ts = now + 3.0 + llFrand(5.0);
                }
                F_SMOKE = llListReplaceList(F_SMOKE, [ts], i, i);
            }
            if (lv < 0.3) lv = 0.3;
            if (lv > 1.5) lv = 1.5;
            F_LEVEL = llListReplaceList(F_LEVEL, [lv], i, i);
            F_VEL = llListReplaceList(F_VEL, [vel], i, i);
            F_GUST = llListReplaceList(F_GUST, [gust], i, i);
            if (FLICKER) light(i, lv);
            @skip;
        }
    }
}

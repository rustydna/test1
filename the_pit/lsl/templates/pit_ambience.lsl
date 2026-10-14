// =====================================================================
//  THE PIT - VOICES AND TIDE (root prim, optional)
//  * Tide: the water of the channel rises and falls a few centimetres
//    over PERIOD seconds, as if the sea breathed under the fortress.
//  * Voices of the Pit: while people are around, now and then something
//    is heard in the dark (whispers, chains, a distant scream...). Text
//    only; add sound UUIDs to SOUNDS, or drop sounds whose names start
//    with "ambient" into the root's Contents, to play one with each voice.
//  Switches (/7 settings > Atmosphere): tide, voices, sounds.
// =====================================================================

float PERIOD = 600.0;        // seconds for one full tide
float AMPLITUDE = 0.035;     // metres
float VOICE_MIN = 150.0;     // seconds between voices (minimum and maximum)
float VOICE_MAX = 420.0;
list  SOUNDS = [];           // optional ambient sound UUIDs

list VOICES = [
    "Something drags a chain through the dark at the far end. Then silence.",
    "From the Cistern comes the gurgle of water... and something like a cough.",
    "An icy drop falls from the vault, right on the back of your neck.",
    "In the Cages, the skeleton's cage turns by itself, squealing, though there is no wind.",
    "Someone whispers a recruit number. Nobody said it.",
    "The torches all lean at once, as if something had crossed the yard.",
    "Far away, beyond the walls, a wave breaks on the rock. The whole Pit trembles for a moment.",
    "The rats fall silent all at once.",
    "A smell of salt, rot and iron rises from the channel.",
    "A dull thud in the Kennel, then a stifled laugh.",
    "A skull rolls on its own in the Cages and stops, staring at you.",
    "The portcullis creaks in its groove, as if someone outside were testing it.",
    "For a moment the fog over the channel draws the shape of a man on his knees.",
    "The chains of the hanged man on the first beam jingle. There is no wind.",
    "A dog barks in the Kennel. No real dog lives here.",
    "Someone has carved into the stone beside a grille: DO NOT LOOK AT THE THRONE."];

integer WATER;
float T0;
vector BASE;
float NEXT;
string OPTS;
integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

integer link_of(string name)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == name) return i;
    return -1;
}

list sounds()
{
    list s = SOUNDS;
    integer n = llGetInventoryNumber(INVENTORY_SOUND);
    integer i;
    for (i = 0; i < n; ++i)
    {
        string nm = llGetInventoryName(INVENTORY_SOUND, i);
        if (llSubStringIndex(nm, "ambient") == 0) s += nm;
    }
    return s;
}

setup()
{
    OPTS = llLinksetDataRead("opts");
    if (WATER > 1 && !opt("tide")) llSetLinkPrimitiveParamsFast(WATER, [PRIM_POS_LOCAL, BASE]);
    if (opt("tide") || opt("voices")) llSetTimerEvent(8.0); else llSetTimerEvent(0.0);
}

default
{
    state_entry()
    {
        WATER = link_of("P_Water");
        if (WATER > 1) BASE = llList2Vector(llGetLinkPrimitiveParams(WATER, [PRIM_POS_LOCAL]), 0);
        T0 = llGetTime();
        NEXT = VOICE_MIN + llFrand(VOICE_MAX - VOICE_MIN);
        setup();
    }
    on_rez(integer p) { llResetScript(); }
    link_message(integer s, integer n, string str, key id) { if (n == 9001) llResetScript(); }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) setup();
    }
    timer()
    {
        float t = llGetTime() - T0;
        if (WATER > 1 && opt("tide"))
            llSetLinkPrimitiveParamsFast(WATER, [PRIM_POS_LOCAL,
                BASE + <0.0, 0.0, AMPLITUDE * llSin(TWO_PI * t / PERIOD)>]);
        if (t > NEXT)
        {
            NEXT = t + VOICE_MIN + llFrand(VOICE_MAX - VOICE_MIN);
            if (opt("voices") && llGetListLength(llGetAgentList(AGENT_LIST_PARCEL, [])) > 0)
            {
                string before = llGetObjectName();
                llSetObjectName("In the dark");
                llSay(0, llList2String(VOICES, (integer)llFrand(llGetListLength(VOICES))));
                llSetObjectName(before);
                list s = sounds();
                if (opt("sounds") && s != []) llTriggerSound(llList2String(s, (integer)llFrand(llGetListLength(s))), 0.6);
            }
        }
    }
}

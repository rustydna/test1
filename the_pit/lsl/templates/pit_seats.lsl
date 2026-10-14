// =====================================================================
//  THE PIT - SEATS (root prim)
//  Places the sit point of every piece of furniture (throne, rack,
//  pillory, stocks, ducking chair, kennels, cages, mast, table, winch,
//  kneeling stone) and hands each sitter to one of the "pit_pose"
//  scripts (one avatar per copy at a time).
//  Animations: if the root holds an animation with the listed name
//  (pit_rack, pit_dog...) it is used; otherwise a built-in SL one.
//  Put several copies of pit_pose in the root (SL numbers them itself:
//  "pit_pose 1"...).
//  Switch (/7 settings > Rooms): seats. Off = plain SL sitting, no
//  custom animations (and the throne no longer names a Lord).
// =====================================================================

//@@CONSTANTS@@

list SITTERS;   // [link, avatar, script]
string OPTS;
integer opt(string f) { return llSubStringIndex(OPTS, "," + f + ",") == -1; }

integer link_of(string name)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == name) return i;
    return -1;
}

place()
{
    integer on = opt("seats");
    integer i;
    for (i = 0; i < llGetListLength(SEATS); i += 5)
    {
        integer l = link_of(llList2String(SEATS, i));
        if (l > 0)
        {
            if (on)
                llLinkSitTarget(l, llList2Vector(SEATS, i + 1),
                                llEuler2Rot(<0.0, 0.0, llList2Float(SEATS, i + 2) * DEG_TO_RAD>));
            else llLinkSitTarget(l, ZERO_VECTOR, ZERO_ROTATION);
        }
    }
}

string free_script()
{
    integer n = llGetInventoryNumber(INVENTORY_SCRIPT);
    integer i;
    for (i = 0; i < n; ++i)
    {
        string s = llGetInventoryName(INVENTORY_SCRIPT, i);
        if (llSubStringIndex(s, "pit_pose") == 0 && llListFindList(SITTERS, [s]) == -1) return s;
    }
    return "";
}

check()
{
    // who stood up
    integer i;
    for (i = llGetListLength(SITTERS) - 3; i >= 0; i -= 3)
    {
        integer l = llList2Integer(SITTERS, i);
        key av = llList2Key(SITTERS, i + 1);
        if (llAvatarOnLinkSitTarget(l) != av)
        {
            llMessageLinked(LINK_THIS, 9501, llList2String(SITTERS, i + 2), av);
            llLinksetDataDelete("sit:" + llGetLinkName(l));
            llMessageLinked(LINK_SET, 9600, "out|" + llGetLinkName(l), av);
            SITTERS = llDeleteSubList(SITTERS, i, i + 2);
        }
    }
    // who sat down
    for (i = 0; i < llGetListLength(SEATS); i += 5)
    {
        string nm = llList2String(SEATS, i);
        integer l = link_of(nm);
        if (l > 0)
        {
            key av = llAvatarOnLinkSitTarget(l);
            if (av != NULL_KEY && llListFindList(SITTERS, [l]) == -1)
            {
                string anim = llList2String(SEATS, i + 3);
                if (llGetInventoryType(anim) != INVENTORY_ANIMATION) anim = llList2String(SEATS, i + 4);
                string sc = free_script();
                if (sc == "") llRegionSayTo(av, 0, "(Not enough copies of the pit_pose script to animate you.)");
                else llMessageLinked(LINK_THIS, 9500, sc + "|" + anim, av);
                SITTERS += [l, av, sc];
                llLinksetDataWrite("sit:" + nm, (string)av);
                llMessageLinked(LINK_SET, 9600, "in|" + nm, av);
            }
        }
    }
}

default
{
    state_entry() { OPTS = llLinksetDataRead("opts"); place(); check(); }
    on_rez(integer p) { llResetScript(); }
    link_message(integer s, integer n, string str, key id) { if (n == 9001) place(); }
    changed(integer c) { if (c & CHANGED_LINK) check(); }
    linkset_data(integer action, string name, string value)
    {
        if (name == "opts" || action == LINKSETDATA_RESET) { OPTS = llLinksetDataRead("opts"); place(); }
    }
}

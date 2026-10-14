// =====================================================================
//  EL FOSO V3 - ASIENTOS (en la raíz)
//  Coloca el punto de asiento de cada mueble (trono, potro, picota, cepos,
//  silla de inmersión, casetas, jaulas, mástil, mesa, torno, piedra) y reparte
//  a quien se sienta entre los scripts "foso_pose" (uno por avatar a la vez).
//  Animaciones: si en la raíz hay una animación con el nombre indicado
//  (foso_potro, foso_perro...) se usa esa; si no, una de serie de SL.
//  Mete varias copias de foso_pose (SL las numera solas: "foso_pose 1"...).
// =====================================================================

//@@CONSTANTES@@

list SENTADOS;   // [link, avatar, script]

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}

colocar()
{
    integer i;
    for (i = 0; i < llGetListLength(ASIENTOS); i += 5)
    {
        integer l = link_de(llList2String(ASIENTOS, i));
        if (l > 0)
        {
            llLinkSitTarget(l, llList2Vector(ASIENTOS, i + 1),
                            llEuler2Rot(<0.0, 0.0, llList2Float(ASIENTOS, i + 2) * DEG_TO_RAD>));
            llSetLinkPrimitiveParamsFast(l, [PRIM_SIT_TEXT, "Ocupar"]);
        }
    }
}

string script_libre()
{
    integer n = llGetInventoryNumber(INVENTORY_SCRIPT);
    integer i;
    for (i = 0; i < n; ++i)
    {
        string s = llGetInventoryName(INVENTORY_SCRIPT, i);
        if (llSubStringIndex(s, "foso_pose") == 0 && llListFindList(SENTADOS, [s]) == -1) return s;
    }
    return "";
}

revisar()
{
    // salidas
    integer i;
    for (i = llGetListLength(SENTADOS) - 3; i >= 0; i -= 3)
    {
        integer l = llList2Integer(SENTADOS, i);
        key av = llList2Key(SENTADOS, i + 1);
        if (llAvatarOnLinkSitTarget(l) != av)
        {
            llMessageLinked(LINK_THIS, 9501, llList2String(SENTADOS, i + 2), av);
            llLinksetDataDelete("sit:" + llGetLinkName(l));
            llMessageLinked(LINK_SET, 9600, "fuera|" + llGetLinkName(l), av);
            SENTADOS = llDeleteSubList(SENTADOS, i, i + 2);
        }
    }
    // entradas
    for (i = 0; i < llGetListLength(ASIENTOS); i += 5)
    {
        string nm = llList2String(ASIENTOS, i);
        integer l = link_de(nm);
        if (l > 0)
        {
            key av = llAvatarOnLinkSitTarget(l);
            if (av != NULL_KEY && llListFindList(SENTADOS, [l]) == -1)
            {
                string anim = llList2String(ASIENTOS, i + 3);
                if (llGetInventoryType(anim) != INVENTORY_ANIMATION) anim = llList2String(ASIENTOS, i + 4);
                string sc = script_libre();
                if (sc == "") llRegionSayTo(av, 0, "(Faltan copias del script foso_pose para animarte.)");
                else llMessageLinked(LINK_THIS, 9500, sc + "|" + anim, av);
                SENTADOS += [l, av, sc];
                llLinksetDataWrite("sit:" + nm, (string)av);
                llMessageLinked(LINK_SET, 9600, "dentro|" + nm, av);
            }
        }
    }
}

default
{
    state_entry() { colocar(); revisar(); }
    on_rez(integer p) { llResetScript(); }
    link_message(integer s, integer n, string str, key id) { if (n == 9001) colocar(); }
    changed(integer c) { if (c & CHANGED_LINK) revisar(); }
}

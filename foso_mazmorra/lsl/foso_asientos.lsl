// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_asientos.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - ASIENTOS (en la raíz)
//  Coloca el punto de asiento de cada mueble (trono, potro, picota, cepos,
//  silla de inmersión, casetas, jaulas, mástil, mesa, torno, piedra) y reparte
//  a quien se sienta entre los scripts "foso_pose" (uno por avatar a la vez).
//  Animaciones: si en la raíz hay una animación con el nombre indicado
//  (foso_potro, foso_perro...) se usa esa; si no, una de serie de SL.
//  Mete varias copias de foso_pose (SL las numera solas: "foso_pose 1"...).
// =====================================================================

vector PIVOTE_SILLA = <0.525,0.000,0.100>;
list ASIENTOS = [
    "C01_Escritorio", <0.000,-0.477,0.253>, 90, "foso_escriba", "sit",
    "C02_Potro", <-0.285,-0.080,0.368>, 0, "foso_potro", "dead",
    "C03_Picota", <0.000,0.150,0.183>, 90, "foso_picota", "stand",
    "C03_Cepos", <0.000,0.335,0.670>, -90, "foso_cepos", "sit",
    "C04_Silla", <-2.075,0.000,0.000>, 0, "foso_silla", "sit",
    "C05_Caseta_1", <0.005,0.085,-0.150>, 180, "foso_perro", "sleep",
    "C05_Caseta_2", <0.005,0.085,-0.150>, 180, "foso_perro", "sleep",
    "C05_Caseta_3", <0.005,0.085,-0.150>, 180, "foso_perro", "sleep",
    "C07_Jaula_1", <0.000,0.000,-1.863>, 0, "foso_jaula", "stand",
    "C07_Jaula_2", <0.000,0.000,-1.863>, 0, "foso_jaula", "stand",
    "C08_Mastil", <0.150,-0.538,-0.723>, 90, "foso_mastil", "stand",
    "G_Torno", <-0.775,-0.491,-0.915>, 90, "foso_torno", "stand",
    "V_Mesa", <0.000,-0.800,0.330>, 90, "foso_guardia", "sit",
    "N_Trono", <0.000,0.094,-0.643>, -90, "foso_senor", "sit",
    "N_Piedra", <-0.063,-0.200,0.313>, 90, "foso_rodillas", "sit_ground_constrained"];
vector TRONO_TAM = <1.950,1.387,3.413>;
list MOVILES = [
    "C01_Puerta", <0.218,1.415,2.550>, <-3.450,-23.054,-1.288>,
    "C02_Puerta", <0.218,1.415,2.550>, <-3.450,-17.304,-1.288>,
    "C03_Puerta", <0.218,1.415,2.550>, <-3.450,-11.554,-1.288>,
    "C04_Puerta", <0.218,1.415,2.550>, <-3.450,-5.804,-1.288>,
    "C05_Puerta", <0.218,1.415,2.550>, <3.450,-23.054,-1.288>,
    "C06_Puerta", <0.218,1.415,2.550>, <3.450,-17.304,-1.288>,
    "C07_Puerta", <0.218,1.415,2.550>, <3.450,-11.554,-1.288>,
    "C08_Puerta", <0.218,1.415,2.550>, <3.450,-5.804,-1.288>,
    "G_Rastrillo", <3.540,0.160,5.600>, <0.000,-32.026,0.207>,
    "G_Hoja_O", <1.826,0.258,3.050>, <-0.922,-28.735,-1.038>,
    "G_Hoja_E", <1.826,0.258,3.050>, <0.922,-28.735,-1.038>];

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

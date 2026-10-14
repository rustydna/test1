// =====================================================================
//  EL FOSO V3 - NÚCLEO (va el primero en la raíz)
//
//  1. Reconoce las 132 piezas aunque SL no haya conservado sus nombres:
//     compara el tamaño y la posición de cada primitiva con la tabla del
//     modelo (medida respecto al trono) y les pone el nombre correcto.
//  2. Asigna la física: estructura -> Prim; puertas y muebles -> Convex;
//     decoración, luces y agua -> None.
//     (Aunque este script no llegara a ejecutarse se puede entrar en todas
//     las salas: ninguna pieza tapa un paso con su casco convexo.)
//  3. Se autodiagnostica: lanza rayos a través de cada puerta abierta y
//     avisa si algo físico bloquea el paso.
//  4. Avisa al resto de scripts (link_message 9001) para que se preparen.
//
//  Toca la raíz siendo el dueño para repetir el diagnóstico.
// =====================================================================

//@@TABLA@@

integer TOL_CM = 4;

string nombre_por_tabla(integer link, vector rel)
{
    vector size = llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_SIZE]), 0);
    integer n = llGetListLength(TABLA);
    integer i;
    float mejor = 999.0; string elegido = "";
    for (i = 0; i < n; i += 4)
    {
        vector ts = llList2Vector(TABLA, i + 2);
        if (llFabs(ts.x - size.x) < 0.04 && llFabs(ts.y - size.y) < 0.04 && llFabs(ts.z - size.z) < 0.04)
        {
            float d = llVecDist(llList2Vector(TABLA, i + 3), rel);
            if (d < mejor) { mejor = d; elegido = llList2String(TABLA, i); }
        }
    }
    if (mejor < 0.3) return elegido;
    return "";
}

integer tipo_de(string nombre)
{
    integer i = llListFindList(TABLA, [nombre]);
    if (i == -1) return -1;
    return llList2Integer(TABLA, i + 1);
}

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}

reconocer()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i; integer con_nombre = 0;
    for (i = 1; i <= n; ++i) if (tipo_de(llGetLinkName(i)) != -1) ++con_nombre;
    integer renombradas = 0;
    if (con_nombre < n * 9 / 10)
    {
        // buscar el trono por su tamaño único y medir todo desde él
        integer trono = -1;
        vector ts = llList2Vector(TABLA, llListFindList(TABLA, ["N_Trono"]) + 2);
        for (i = 1; i <= n && trono == -1; ++i)
        {
            vector s = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_SIZE]), 0);
            if (llVecDist(s, ts) < 0.03) trono = i;
        }
        if (trono == -1)
        {
            llOwnerSay("No encuentro el trono por su tamaño: ¿se ha reescalado el edificio? Escala 1,0 al subir.");
            return;
        }
        vector base = llList2Vector(llGetLinkPrimitiveParams(trono, [PRIM_POS_LOCAL]), 0);
        if (trono == 1) base = ZERO_VECTOR;
        for (i = 1; i <= n; ++i)
        {
            vector p = ZERO_VECTOR;
            if (i > 1) p = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0);
            string nom = nombre_por_tabla(i, p - base);
            if (nom != "" && nom != llGetLinkName(i))
            {
                llSetLinkPrimitiveParamsFast(i, [PRIM_NAME, nom]);
                ++renombradas;
            }
        }
    }
    llOwnerSay("Piezas reconocidas: " + (string)n + " (" + (string)renombradas + " renombradas).");
}

fisica()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i; integer c0 = 0; integer c1 = 0; integer c2 = 0;
    for (i = 1; i <= n; ++i)
    {
        integer t = tipo_de(llGetLinkName(i));
        integer forma = PRIM_PHYSICS_SHAPE_PRIM;
        if (t == 1 || t == 4) forma = PRIM_PHYSICS_SHAPE_CONVEX;
        else if (t == 2 || t == 3 || t == 5) forma = PRIM_PHYSICS_SHAPE_NONE;
        if (i == 1 && forma == PRIM_PHYSICS_SHAPE_NONE) forma = PRIM_PHYSICS_SHAPE_CONVEX;
        llSetLinkPrimitiveParamsFast(i, [PRIM_PHYSICS_SHAPE_TYPE, forma]);
        if (forma == PRIM_PHYSICS_SHAPE_PRIM) ++c0;
        else if (forma == PRIM_PHYSICS_SHAPE_CONVEX) ++c1;
        else ++c2;
    }
    llOwnerSay("Física: Prim " + (string)c0 + ", Convex " + (string)c1 + ", None " + (string)c2 + ".");
}

diagnostico()
{
    // rayos horizontales a 0,5 / 1,1 / 1,7 m por cada puerta, desde el patio hasta el fondo de la sala
    integer n = llGetObjectPrimCount(llGetKey());
    list puertas = [];
    float suma = 0.0;
    integer i;
    for (i = 2; i <= n; ++i)
        if (llSubStringIndex(llGetLinkName(i), "_Puerta") != -1)
        {
            puertas += i;
            suma += llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0).x;
        }
    if (puertas == []) return;
    float centro = suma / llGetListLength(puertas);
    vector rp = llGetRootPosition(); rotation rr = llGetRootRotation();
    integer malos = 0;
    for (i = 0; i < llGetListLength(puertas); ++i)
    {
        integer l = llList2Integer(puertas, i);
        list d = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_SIZE]);
        vector p = llList2Vector(d, 0); vector s = llList2Vector(d, 1);
        float dir = 1.0; if (p.x > centro) dir = -1.0;   // hacia el interior de la sala
        float z;
        for (z = -0.8; z < 0.6; z += 0.6)
        {
            vector a = rp + (p + <-dir * 2.0, 0.3, z>) * rr;
            vector b = rp + (p + < dir * 2.0, 0.3, z>) * rr;
            list hits = llCastRay(a, b, [RC_REJECT_TYPES, RC_REJECT_AGENTS | RC_REJECT_LAND,
                                         RC_DATA_FLAGS, RC_GET_LINK_NUM, RC_MAX_HITS, 4]);
            integer h = llList2Integer(hits, -1);
            integer j;
            for (j = 0; j < h; ++j)
            {
                integer hl = llList2Integer(hits, j * 3 + 2);
                if (llList2Key(hits, j * 3) == llGetKey() && hl != l)
                {
                    llOwnerSay("AVISO: el paso de " + llGetLinkName(l) + " choca con " + llGetLinkName(hl)
                        + " a " + (string)((integer)((z + 1.33) * 100)) + " cm del suelo.");
                    ++malos;
                }
            }
        }
    }
    if (malos == 0) llOwnerSay("Diagnóstico: las " + (string)llGetListLength(puertas)
        + " puertas dejan paso libre (con la hoja abierta).");
}

default
{
    state_entry()
    {
        llOwnerSay("El Foso: preparando...");
        reconocer();
        fisica();
        llSleep(1.5);
        diagnostico();
        llMessageLinked(LINK_SET, 9001, "listo", NULL_KEY);
        llOwnerSay("Listo. Toca la raíz (dueño) para repetir el diagnóstico.");
    }
    on_rez(integer p) { llResetScript(); }
    touch_start(integer t)
    {
        if (llDetectedKey(0) == llGetOwner() && llDetectedLinkNumber(0) == 1) diagnostico();
    }
}

// =====================================================================
//  EL FOSO V2 - puertas de celda, portón de entrada y rastrillo
//  Un solo script en el objeto raíz. Tocar una pieza la abre o la cierra.
//
//  SL recentra cada pieza en su caja, así que el giro NO usa el origen de
//  la malla: el script calcula la bisagra a partir del tamaño de la pieza.
//    * Puertas de celda (Cxx_Puerta): bisagra en el canto -Y; abren hacia el patio.
//    * Portón (G_Hoja_O / G_Hoja_E): bisagras en los cantos exteriores; abren hacia dentro.
//    * Rastrillo (G_Rastrillo): sube 3,2 m dentro del muro.
//  Las posiciones cerradas se guardan al reiniciar el script: reinícialo
//  (Reset Scripts) con todo cerrado si mueves o giras el edificio.
// =====================================================================

string  ACCESO       = "TODOS";   // "TODOS", "GRUPO" o "DUENO"
float   ANGULO       = 100.0;     // grados de apertura de las puertas de celda
float   ANGULO_PORTON = 95.0;
float   SUBIDA_RASTRILLO = 3.2;
integer PASOS        = 10;
float   PAUSA        = 0.035;
string  SONIDO_PUERTA = "";       // UUID opcional
string  SONIDO_RASTRILLO = "";    // UUID opcional

// listas paralelas
list L_LINK;     // número de enlace
list L_TIPO;     // 0 celda, 1 portón, 2 rastrillo
list L_POS;      // posición local cerrada
list L_ROT;      // rotación local cerrada
list L_EJE;      // punto de la bisagra (local a la raíz)
list L_ANG;      // ángulo con signo (grados)
list L_ABIERTA;

float INSET = 0.03;   // distancia del eje de la bisagra al canto de la pieza

integer permitido(key k)
{
    if (ACCESO == "TODOS") return TRUE;
    if (ACCESO == "DUENO") return k == llGetOwner();
    return llSameGroup(k) || k == llGetOwner();
}

escanear()
{
    L_LINK = []; L_TIPO = []; L_POS = []; L_ROT = []; L_EJE = []; L_ANG = []; L_ABIERTA = [];
    integer n = llGetNumberOfPrims();
    integer i;
    // eje del patio: media de las X locales de las puertas de celda
    float suma = 0.0; integer cuenta = 0;
    for (i = 1; i <= n; ++i)
        if (llSubStringIndex(llGetLinkName(i), "_Puerta") != -1)
        {
            suma += llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0).x;
            ++cuenta;
        }
    float centro = 0.0;
    if (cuenta) centro = suma / cuenta;

    for (i = 1; i <= n; ++i)
    {
        string nombre = llGetLinkName(i);
        integer tipo = -1;
        if (llSubStringIndex(nombre, "_Puerta") != -1) tipo = 0;
        else if (llSubStringIndex(nombre, "G_Hoja") == 0) tipo = 1;
        else if (nombre == "G_Rastrillo") tipo = 2;
        if (tipo >= 0 && i > 1)
        {
            list p = llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL, PRIM_SIZE]);
            vector pos = llList2Vector(p, 0);
            rotation rot = llList2Rot(p, 1);
            vector size = llList2Vector(p, 2);
            vector off = ZERO_VECTOR;
            float ang = 0.0;
            if (tipo == 0)
            {
                off = <0.0, -(size.y * 0.5 - INSET), 0.0>;
                if (pos.x < centro) ang = -ANGULO; else ang = ANGULO;
            }
            else if (tipo == 1)
            {
                if (nombre == "G_Hoja_O") { off = <-(size.x * 0.5 - INSET), 0.0, 0.0>; ang = ANGULO_PORTON; }
                else { off = <size.x * 0.5 - INSET, 0.0, 0.0>; ang = -ANGULO_PORTON; }
            }
            L_LINK += i; L_TIPO += tipo; L_POS += pos; L_ROT += rot;
            L_EJE += pos + off * rot; L_ANG += ang; L_ABIERTA += FALSE;
        }
    }
    llOwnerSay("Puertas listas: " + (string)llGetListLength(L_LINK) + " piezas móviles.");
}

mover(integer idx)
{
    integer link = llList2Integer(L_LINK, idx);
    integer tipo = llList2Integer(L_TIPO, idx);
    vector pos = llList2Vector(L_POS, idx);
    rotation rot = llList2Rot(L_ROT, idx);
    integer abierta = llList2Integer(L_ABIERTA, idx);
    integer k;
    if (tipo == 2)
    {
        if (SONIDO_RASTRILLO != "") llTriggerSound(SONIDO_RASTRILLO, 1.0);
        for (k = 1; k <= PASOS * 2; ++k)
        {
            float t = (float)k / (PASOS * 2);
            if (abierta) t = 1.0 - t;
            llSetLinkPrimitiveParamsFast(link, [PRIM_POS_LOCAL, pos + <0.0, 0.0, SUBIDA_RASTRILLO * t>]);
            llSleep(PAUSA * 2);
        }
    }
    else
    {
        if (SONIDO_PUERTA != "") llTriggerSound(SONIDO_PUERTA, 1.0);
        vector eje = llList2Vector(L_EJE, idx);
        float ang = llList2Float(L_ANG, idx);
        for (k = 1; k <= PASOS; ++k)
        {
            float t = (float)k / PASOS;
            t = t * t * (3.0 - 2.0 * t);   // suavizado
            if (abierta) t = 1.0 - t;
            rotation z = llEuler2Rot(<0.0, 0.0, ang * t * DEG_TO_RAD>);
            llSetLinkPrimitiveParamsFast(link, [PRIM_POS_LOCAL, eje + (pos - eje) * z, PRIM_ROT_LOCAL, rot * z]);
            llSleep(PAUSA);
        }
    }
    L_ABIERTA = llListReplaceList(L_ABIERTA, [!abierta], idx, idx);
}

default
{
    state_entry() { escanear(); }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if (c & CHANGED_LINK) llResetScript(); }

    touch_start(integer total)
    {
        integer i;
        for (i = 0; i < total; ++i)
        {
            if (permitido(llDetectedKey(i)))
            {
                integer idx = llListFindList(L_LINK, [llDetectedLinkNumber(i)]);
                if (idx != -1) mover(idx);
            }
        }
    }
}

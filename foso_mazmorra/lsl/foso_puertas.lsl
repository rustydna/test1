// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_puertas.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - PUERTAS Y CERRADURAS DE ROL (en la raíz)
//
//  Toca una reja de celda, una hoja del portón o el torno/rastrillo:
//    Abrir / Cerrar            si no tiene la llave echada
//    Echar llave               la cierra y SOLO quien la cerró puede abrirla
//                              (y quien reciba copia, el dueño o el Señor en su trono)
//    Quitar llave · Dar llave · Condena (5-120 min, se abre sola al cumplirse)
//    Forzar (d20 contra la dificultad) · Clemencia (avisa al carcelero) · Golpear
//  Todo se anuncia en el chat local y queda en el "Tablón de condenas"
//  (texto flotante sobre el tablero de llaves del cuerpo de guardia).
//  El estado se guarda en los datos del objeto: sobrevive a reinicios.
// =====================================================================

float   ANGULO = 100.0;
float   ANGULO_PORTON = 95.0;
float   SUBIDA_RASTRILLO = 3.2;
integer PASOS = 14;
float   PAUSA = 0.035;
integer DIFICULTAD = 17;         // forzar: d20 >= DIFICULTAD
integer ENFRIAMIENTO = 120;      // segundos entre intentos de forzar por avatar
string  SONIDO_REJA = "";        // UUID opcional
string  SONIDO_CERROJO = "";
string  SONIDO_RASTRILLO = "";
string  SONIDO_CAMPANA = "";

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

float INSET = 0.03;
integer PRIMS;                // nº de primitivas en el último escaneo (las sentadas de avatares no cuentan)
list E_LINK; list E_TAG; list E_TIPO; list E_POS; list E_ROT; list E_EJE; list E_ANG;
list ABIERTA;                 // por etiqueta: [tag, 0/1, ...]
list INTENTOS;                // [key, unix]
integer CANAL; integer ESCUCHA;
key USUARIO; string TAG_MENU; string MODO;
list SENSOR_KEYS;

string sala(string t)
{
    if (t == "C01") return "LA LEVA";
    if (t == "C02") return "EL POTRO";
    if (t == "C03") return "EL CEPO";
    if (t == "C04") return "LA CISTERNA";
    if (t == "C05" || t == "C06") return "LA PERRERA";
    if (t == "C07") return "LAS JAULAS";
    if (t == "C08") return "EL MÁSTIL";
    if (t == "G") return "EL PORTÓN";
    if (t == "R") return "EL RASTRILLO";
    return t;
}

string nombre(key k) { return llGetDisplayName(k); }

list estado(string t)
{
    string s = llLinksetDataRead("p:" + t);
    if (s == "") return [0, NULL_KEY, "", 0, ""];
    list l = llParseStringKeepNulls(s, ["|"], []);
    return [(integer)llList2String(l, 0), (key)llList2String(l, 1), llList2String(l, 2),
            (integer)llList2String(l, 3), llList2String(l, 4)];
}

guardar(string t, integer cerrojo, key quien, string nom, integer hasta, string portadores)
{
    llLinksetDataWrite("p:" + t, llDumpList2String([cerrojo, quien, nom, hasta, portadores], "|"));
    tablon();
}

integer abierta(string t)
{
    integer i = llListFindList(ABIERTA, [t]);
    if (i == -1) return FALSE;
    return llList2Integer(ABIERTA, i + 1);
}

integer tiene_llave(string t, key k)
{
    if (k == llGetOwner()) return TRUE;
    if (k == (key)llLinksetDataRead("senor")) return TRUE;
    list e = estado(t);
    if (llList2Key(e, 1) == k) return TRUE;
    if (llSubStringIndex(llList2String(e, 4), (string)k) != -1) return TRUE;
    return FALSE;
}

// Devuelve el nombre de pieza móvil de un enlace: por su nombre o, si SL no lo
// conservó, por su tamaño y su posición respecto al trono (y la renombra).
string identificar(integer link, integer trono, vector base)
{
    string nm = llGetLinkName(link);
    if (llListFindList(MOVILES, [nm]) != -1) return nm;
    vector sz = llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_SIZE]), 0);
    vector p = llList2Vector(llGetLinkPrimitiveParams(link, [PRIM_POS_LOCAL]), 0);
    integer i; float mejor = 999.0; string elegido = "";
    for (i = 0; i < llGetListLength(MOVILES); i += 3)
    {
        vector ts = llList2Vector(MOVILES, i + 1);
        if (llVecDist(ts, sz) < 0.05)
        {
            float d = 0.0;
            if (trono > 0) d = llVecDist(llList2Vector(MOVILES, i + 2), p - base);
            if (d < mejor) { mejor = d; elegido = llList2String(MOVILES, i); }
        }
    }
    if (elegido != "" && mejor < 0.5)
    {
        llSetLinkPrimitiveParamsFast(link, [PRIM_NAME, elegido]);
        return elegido;
    }
    return "";
}

escanear()
{
    E_LINK = []; E_TAG = []; E_TIPO = []; E_POS = []; E_ROT = []; E_EJE = []; E_ANG = []; ABIERTA = [];
    integer n = llGetObjectPrimCount(llGetKey());
    PRIMS = n;
    integer i;
    // el trono sirve de referencia para reconocer piezas sin nombre
    integer trono = -1; vector base = ZERO_VECTOR;
    for (i = 1; i <= n && trono == -1; ++i)
        if (llGetLinkName(i) == "N_Trono" ||
            llVecDist(llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_SIZE]), 0), TRONO_TAM) < 0.03)
            trono = i;
    if (trono > 1) base = llList2Vector(llGetLinkPrimitiveParams(trono, [PRIM_POS_LOCAL]), 0);
    list nombres = [];
    float suma = 0.0; integer cuenta = 0;
    for (i = 2; i <= n; ++i)
    {
        string nm = identificar(i, trono, base);
        nombres += nm;
        if (llSubStringIndex(nm, "_Puerta") != -1)
        {
            suma += llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0).x; ++cuenta;
        }
    }
    float centro = 0.0; if (cuenta) centro = suma / cuenta;
    integer celdas = 0; integer hojas = 0; integer rastrillo = 0;
    for (i = 2; i <= n; ++i)
    {
        string nm = llList2String(nombres, i - 2);
        integer tipo = -1; string tag = "";
        if (llSubStringIndex(nm, "_Puerta") != -1) { tipo = 0; tag = llGetSubString(nm, 0, 2); ++celdas; }
        else if (llSubStringIndex(nm, "G_Hoja") == 0) { tipo = 1; tag = "G"; ++hojas; }
        else if (nm == "G_Rastrillo") { tipo = 2; tag = "R"; ++rastrillo; }
        if (tipo >= 0)
        {
            list p = llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL, PRIM_SIZE]);
            vector pos = llList2Vector(p, 0); rotation rot = llList2Rot(p, 1); vector sz = llList2Vector(p, 2);
            // posición CERRADA guardada la primera vez: si ahora está movida, es que estaba abierta
            integer abierta_ahora = FALSE;
            string guardada = llLinksetDataRead("cerr:" + nm);
            if (guardada == "") llLinksetDataWrite("cerr:" + nm, (string)pos + "|" + (string)rot);
            else
            {
                list g = llParseString2List(guardada, ["|"], []);
                vector gp = (vector)llList2String(g, 0);
                if (llVecDist(gp, pos) > 0.05) abierta_ahora = TRUE;
                pos = gp; rot = (rotation)llList2String(g, 1);
            }
            vector off = ZERO_VECTOR; float ang = 0.0;
            if (tipo == 0)
            {
                off = <0.0, -(sz.y * 0.5 - INSET), 0.0>;
                if (pos.x < centro) ang = -ANGULO; else ang = ANGULO;
            }
            else if (tipo == 1)
            {
                if (nm == "G_Hoja_O") { off = <-(sz.x * 0.5 - INSET), 0.0, 0.0>; ang = ANGULO_PORTON; }
                else { off = <sz.x * 0.5 - INSET, 0.0, 0.0>; ang = -ANGULO_PORTON; }
            }
            E_LINK += i; E_TAG += tag; E_TIPO += tipo; E_POS += pos; E_ROT += rot;
            E_EJE += pos + off * rot; E_ANG += ang;
            integer ia = llListFindList(ABIERTA, [tag]);
            if (ia == -1) ABIERTA += [tag, abierta_ahora];
            else if (abierta_ahora) ABIERTA = llListReplaceList(ABIERTA, [TRUE], ia + 1, ia + 1);
        }
    }
    string aviso = "Puertas listas: " + (string)celdas + " de celda (esperadas 8), " + (string)hojas
        + " hojas del portón (2), rastrillo: " + (string)rastrillo + " (1).";
    if (celdas < 8 || hojas < 2 || rastrillo < 1)
        aviso += " FALTAN PIEZAS: comprueba que subiste el modelo a escala 1,0 y escribe /7 puertas para reintentar.";
    llOwnerSay(aviso);
    tablon();
}

mover(string tag, integer abrir)
{
    if (abierta(tag) == abrir) return;
    integer k;
    integer n = llGetListLength(E_LINK);
    list mios = [];
    integer i;
    for (i = 0; i < n; ++i) if (llList2String(E_TAG, i) == tag) mios += i;
    integer primero = llList2Integer(mios, 0);
    if (llList2Integer(E_TIPO, primero) == 2)
    {
        if (SONIDO_RASTRILLO != "") llLinkPlaySound(llList2Integer(E_LINK, primero), SONIDO_RASTRILLO, 1.0, SOUND_PLAY);
    }
    else if (SONIDO_REJA != "") llLinkPlaySound(llList2Integer(E_LINK, primero), SONIDO_REJA, 1.0, SOUND_PLAY);
    integer pasos = PASOS;
    if (llList2Integer(E_TIPO, primero) == 2) pasos = PASOS * 3;
    for (k = 1; k <= pasos; ++k)
    {
        float t = (float)k / pasos;
        t = t * t * (3.0 - 2.0 * t);
        if (!abrir) t = 1.0 - t;
        integer m;
        for (m = 0; m < llGetListLength(mios); ++m)
        {
            integer j = llList2Integer(mios, m);
            integer link = llList2Integer(E_LINK, j);
            vector pos = llList2Vector(E_POS, j);
            if (llList2Integer(E_TIPO, j) == 2)
                llSetLinkPrimitiveParamsFast(link, [PRIM_POS_LOCAL, pos + <0.0, 0.0, SUBIDA_RASTRILLO * t>]);
            else
            {
                vector eje = llList2Vector(E_EJE, j);
                rotation z = llEuler2Rot(<0.0, 0.0, llList2Float(E_ANG, j) * t * DEG_TO_RAD>);
                llSetLinkPrimitiveParamsFast(link, [PRIM_POS_LOCAL, eje + (pos - eje) * z,
                                                    PRIM_ROT_LOCAL, llList2Rot(E_ROT, j) * z]);
            }
        }
        llSleep(PAUSA);
    }
    integer ia = llListFindList(ABIERTA, [tag]);
    ABIERTA = llListReplaceList(ABIERTA, [abrir], ia + 1, ia + 1);
    llMessageLinked(LINK_SET, 9100, "puerta|" + tag + "|" + (string)abrir, NULL_KEY);   // corriente: las antorchas cercanas tiemblan
}

tablon()
{
    string txt = "TABLÓN DE CONDENAS\n";
    list tags = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "G"];
    integer i; integer hay = 0;
    for (i = 0; i < llGetListLength(tags); ++i)
    {
        string t = llList2String(tags, i);
        list e = estado(t);
        if (llList2Integer(e, 0))
        {
            string linea = sala(t) + " - llave de " + llList2String(e, 2);
            integer hasta = llList2Integer(e, 3);
            if (hasta > 0) linea += " (" + (string)((hasta - llGetUnixTime()) / 60 + 1) + " min)";
            txt += linea + "\n"; hay = TRUE;
        }
    }
    if (!hay) txt += "(todas las rejas sin llave)";
    integer n = llGetObjectPrimCount(llGetKey());
    for (i = 1; i <= n; ++i)
        if (llGetLinkName(i) == "V_Atrezzo_O")
            llSetLinkPrimitiveParamsFast(i, [PRIM_TEXT, txt, <0.85, 0.65, 0.4>, 0.85]);
}

anunciar(string s) { llSay(0, s); }

menu(key k, string tag)
{
    USUARIO = k; TAG_MENU = tag; MODO = "principal";
    list e = estado(tag);
    integer cerrojo = llList2Integer(e, 0);
    string txt = sala(tag) + "\n";
    if (cerrojo) txt += "Con llave de " + llList2String(e, 2) + ".";
    else if (abierta(tag)) txt += "Abierta.";
    else txt += "Cerrada, sin llave.";
    if (llList2Integer(e, 3) > 0) txt += "\nCondena: " + (string)((llList2Integer(e, 3) - llGetUnixTime()) / 60 + 1) + " min.";
    list b = [];
    if (tag == "R") b = ["Subir", "Bajar", "Campana"];
    else if (!cerrojo)
    {
        if (abierta(tag)) b = ["Cerrar"]; else b = ["Abrir"];
        b += ["Echar llave"];
    }
    else if (tiene_llave(tag, k)) b = ["Quitar llave", "Dar llave", "Condena"];
    else b = ["Forzar", "Clemencia", "Golpear"];
    llListenRemove(ESCUCHA);
    ESCUCHA = llListen(CANAL, "", k, "");
    llSetTimerEvent(20.0);
    llDialog(k, txt, b, CANAL);
}

accion(key k, string b)
{
    string t = TAG_MENU; string q = nombre(k);
    list e = estado(t);
    if (b == "Abrir") { mover(t, TRUE); anunciar(q + " abre " + sala(t) + "."); }
    else if (b == "Cerrar") { mover(t, FALSE); anunciar(q + " cierra " + sala(t) + "."); }
    else if (b == "Subir") { mover("R", TRUE); anunciar(q + " hace girar el torno: el rastrillo sube entre crujidos."); }
    else if (b == "Bajar") { mover("R", FALSE); anunciar("El rastrillo cae con estruendo. " + q + " suelta el torno."); }
    else if (b == "Campana")
    {
        if (SONIDO_CAMPANA != "") llPlaySound(SONIDO_CAMPANA, 1.0);
        llMessageLinked(LINK_SET, 9300, "campana", k);
        anunciar("DONG... DONG... DONG... " + q + " toca la campana de la Leva: carne nueva para el Foso.");
    }
    else if (b == "Echar llave")
    {
        mover(t, FALSE);
        if (SONIDO_CERROJO != "") llPlaySound(SONIDO_CERROJO, 1.0);
        guardar(t, 1, k, q, 0, "");
        anunciar(q + " echa la llave a " + sala(t) + ". Solo " + q + " podrá abrirla.");
    }
    else if (b == "Quitar llave")
    {
        guardar(t, 0, NULL_KEY, "", 0, "");
        anunciar(q + " quita la llave de " + sala(t) + ".");
    }
    else if (b == "Dar llave") { MODO = "dar"; llSensor("", NULL_KEY, AGENT, 12.0, PI); }
    else if (b == "Condena")
    {
        MODO = "condena";
        llDialog(k, "¿Cuánto tiempo encerrado en " + sala(t) + "?", ["5 min", "15 min", "30 min", "60 min", "120 min"], CANAL);
        return;
    }
    else if (llSubStringIndex(b, " min") != -1 && MODO == "condena")
    {
        integer m = (integer)b;
        guardar(t, 1, llList2Key(e, 1), llList2String(e, 2), llGetUnixTime() + m * 60, llList2String(e, 4));
        anunciar(q + " impone " + (string)m + " minutos de condena en " + sala(t) + ".");
    }
    else if (b == "Forzar")
    {
        integer i = llListFindList(INTENTOS, [k]);
        if (i != -1 && llGetUnixTime() - llList2Integer(INTENTOS, i + 1) < ENFRIAMIENTO)
        {
            llRegionSayTo(k, 0, "Aún te tiemblan las manos. Espera antes de volver a intentarlo.");
            return;
        }
        if (i != -1) INTENTOS = llDeleteSubList(INTENTOS, i, i + 1);
        INTENTOS += [k, llGetUnixTime()];
        integer d = 1 + (integer)llFrand(20.0);
        if (d >= DIFICULTAD)
        {
            guardar(t, 0, NULL_KEY, "", 0, "");
            mover(t, TRUE);
            anunciar("¡" + q + " revienta la cerradura de " + sala(t) + "! (d20 = " + (string)d + ")");
            llInstantMessage(llList2Key(e, 1), q + " ha forzado " + sala(t) + " y está suelto.");
        }
        else
        {
            anunciar(q + " forcejea con la cerradura de " + sala(t) + "... y no cede. (d20 = " + (string)d + ")");
            llInstantMessage(llList2Key(e, 1), q + " ha intentado forzar " + sala(t) + ".");
        }
    }
    else if (b == "Clemencia")
    {
        anunciar(q + " se aferra a los barrotes de " + sala(t) + " y suplica clemencia.");
        llInstantMessage(llList2Key(e, 1), q + " suplica clemencia desde " + sala(t) + ".");
    }
    else if (b == "Golpear")
    {
        anunciar(q + " sacude los barrotes de " + sala(t) + ". El hierro retumba por todo el Foso.");
        llMessageLinked(LINK_SET, 9100, "golpe|" + t + "|0", NULL_KEY);
    }
}

default
{
    state_entry()
    {
        CANAL = -1 - (integer)llFrand(1000000.0);
        llListen(7, "", llGetOwner(), "");
        escanear();
        llSetTimerEvent(30.0);
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c)
    {
        // sentarse/levantarse también lanza CHANGED_LINK: solo se reescanea si cambian las primitivas
        if ((c & CHANGED_LINK) && llGetObjectPrimCount(llGetKey()) != PRIMS) escanear();
    }

    link_message(integer s, integer n, string str, key id)
    {
        if (n == 9001) escanear();
        else if (n == 9400)
        {
            // órdenes del trono: "todas|abrir", "todas|cerrar", "juicio|C04|<clave>|<nombre>|<preso>"
            list p = llParseString2List(str, ["|"], []);
            string o = llList2String(p, 0);
            if (o == "todas")
            {
                integer abrir = llList2String(p, 1) == "abrir";
                list tags = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08"];
                integer i;
                for (i = 0; i < 8; ++i)
                {
                    string t = llList2String(tags, i);
                    if (abrir) guardar(t, 0, NULL_KEY, "", 0, "");
                    mover(t, abrir);
                }
            }
            else if (o == "juicio")
            {
                string t = llList2String(p, 1);
                mover(t, FALSE);
                guardar(t, 1, (key)llList2String(p, 2), llList2String(p, 3), llGetUnixTime() + 30 * 60, "");
            }
        }
    }

    touch_start(integer total)
    {
        integer l = llDetectedLinkNumber(0);
        string nm = llGetLinkName(l);
        string tag = "";
        if (llSubStringIndex(nm, "_Puerta") != -1) tag = llGetSubString(nm, 0, 2);
        else if (llSubStringIndex(nm, "G_Hoja") == 0) tag = "G";
        else if (nm == "G_Rastrillo" || nm == "G_Torno") tag = "R";
        if (tag != "") menu(llDetectedKey(0), tag);
    }

    listen(integer c, string n, key id, string m)
    {
        if (c == 7)
        {
            // /7 puertas            -> vuelve a buscar las puertas
            // /7 puertas cerradas   -> con TODO cerrado, guarda de nuevo la posición cerrada de cada hoja
            if (m == "puertas") escanear();
            else if (m == "puertas cerradas")
            {
                list ks = llLinksetDataFindKeys("^cerr:", 0, 100);
                integer i;
                for (i = 0; i < llGetListLength(ks); ++i) llLinksetDataDelete(llList2String(ks, i));
                escanear();
            }
            return;
        }
        if (id != USUARIO) return;
        if (MODO == "dar")
        {
            integer i = llListFindList(SENSOR_KEYS, [m]);
            if (i == -1) return;
            key k2 = llList2Key(SENSOR_KEYS, i + 1);
            list e = estado(TAG_MENU);
            guardar(TAG_MENU, 1, llList2Key(e, 1), llList2String(e, 2), llList2Integer(e, 3),
                    llList2String(e, 4) + "," + (string)k2);
            anunciar(nombre(id) + " entrega una copia de la llave de " + sala(TAG_MENU) + " a " + nombre(k2) + ".");
            MODO = "";
            return;
        }
        accion(id, m);
    }

    sensor(integer num)
    {
        SENSOR_KEYS = [];
        list b = [];
        integer i;
        for (i = 0; i < num && i < 12; ++i)
        {
            string nm = llGetSubString(llDetectedName(i), 0, 23);
            SENSOR_KEYS += [nm, llDetectedKey(i)];
            b += nm;
        }
        llDialog(USUARIO, "¿A quién das la llave de " + sala(TAG_MENU) + "?", b, CANAL);
    }
    no_sensor() { llRegionSayTo(USUARIO, 0, "No hay nadie cerca."); }

    timer()
    {
        llListenRemove(ESCUCHA);
        llSetTimerEvent(30.0);
        list tags = ["C01", "C02", "C03", "C04", "C05", "C06", "C07", "C08", "G"];
        integer i;
        for (i = 0; i < 9; ++i)
        {
            string t = llList2String(tags, i);
            list e = estado(t);
            integer hasta = llList2Integer(e, 3);
            if (llList2Integer(e, 0) && hasta > 0 && llGetUnixTime() >= hasta)
            {
                guardar(t, 0, NULL_KEY, "", 0, "");
                anunciar("Se cumple la condena en " + sala(t) + ": la cerradura queda libre.");
            }
        }
        tablon();
    }
}

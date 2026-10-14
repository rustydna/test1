// =====================================================================
//  EL FOSO V3 - TRONO DEL SEÑOR Y LIBRO DE LA LEVA (en la raíz)
//
//  Quien se sienta en el trono es el SEÑOR DEL FOSO (texto sobre el trono).
//  Tocando el trono (el Señor o el dueño):
//    Abrir todas · Cerrar todas · Ambiente (VIGILIA / PENUMBRA / JUICIO /
//    TINIEBLAS) · Juicio (eliges a alguien cercano y una sala: queda
//    encerrado 30 min con la llave del Señor) · Campana · Libro
//  Escritorio del escriba (La Leva): Alistar (inscribe a quien elijas con
//  número de recluta y fecha), Ver libro, Juramento.
//  Brasero de marcar: Marcar (cuenta las marcas de cada recluta).
//  El Señor tiene llave de todas las rejas mientras ocupa el trono.
// =====================================================================

integer CANAL; integer ESCUCHA; key USUARIO; string MODO; key ELEGIDO;
list SENSADOS;

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}
string nom(key k) { return llGetDisplayName(k); }
dialogo(key k, string t, list b) { llListenRemove(ESCUCHA); ESCUCHA = llListen(CANAL, "", k, ""); llSetTimerEvent(60.0); llDialog(k, t, b, CANAL); }

rotulos()
{
    key senor = (key)llLinksetDataRead("senor");
    integer l = link_de("N_Trono");
    if (l > 0)
    {
        if (senor == NULL_KEY) llSetLinkPrimitiveParamsFast(l, [PRIM_TEXT, "EL TRONO VACÍO", <0.6, 0.35, 0.2>, 0.6]);
        else llSetLinkPrimitiveParamsFast(l, [PRIM_TEXT, "SEÑOR DEL FOSO\n" + nom(senor), <0.95, 0.6, 0.25>, 0.9]);
    }
    l = link_de("C01_Escritorio");
    if (l > 0) llSetLinkPrimitiveParamsFast(l, [PRIM_TEXT, "LIBRO DE LA LEVA\n" + (string)((integer)llLinksetDataRead("reclutas"))
                                                + " almas alistadas", <0.8, 0.6, 0.35>, 0.7]);
}

string libro()
{
    integer n = (integer)llLinksetDataRead("reclutas");
    string t = "LIBRO DE LA LEVA (" + (string)n + ")\n";
    integer i;
    for (i = n; i > 0 && i > n - 9; --i)
    {
        list e = llParseString2List(llLinksetDataRead("leva:" + (string)i), ["|"], []);
        key k = (key)llList2String(e, 0);
        t += "Nº " + (string)i + " " + llList2String(e, 1) + " - " + llList2String(e, 2)
             + " - marcas: " + (string)((integer)llLinksetDataRead("marcas:" + (string)k)) + "\n";
    }
    return t;
}

alistar(key k)
{
    if (llLinksetDataRead("num:" + (string)k) != "")
    {
        llSay(0, nom(k) + " ya figura en el Libro de la Leva con el número " + llLinksetDataRead("num:" + (string)k) + ".");
        return;
    }
    integer n = (integer)llLinksetDataRead("reclutas") + 1;
    string fecha = llGetSubString(llGetTimestamp(), 0, 9);
    llLinksetDataWrite("reclutas", (string)n);
    llLinksetDataWrite("leva:" + (string)n, (string)k + "|" + llGetSubString(nom(k), 0, 20) + "|" + fecha);
    llLinksetDataWrite("num:" + (string)k, (string)n);
    llSay(0, "El escriba moja la pluma: \"" + nom(k) + ", recluta número " + (string)n
          + ". Desde hoy tu vida pertenece al Señor del Foso.\"");
    rotulos();
}

marcar(key k)
{
    integer m = (integer)llLinksetDataRead("marcas:" + (string)k) + 1;
    llLinksetDataWrite("marcas:" + (string)k, (string)m);
    llMessageLinked(LINK_SET, 9300, "marca", USUARIO);
    llSay(0, "Huele a carne quemada: " + nom(USUARIO) + " aplica el hierro candente a " + nom(k)
          + ". Marca número " + (string)m + ".");
    rotulos();
}

default
{
    state_entry() { CANAL = -1 - (integer)llFrand(1000000.0); rotulos(); }
    on_rez(integer p) { llResetScript(); }

    link_message(integer s, integer n, string str, key id)
    {
        if (n == 9600 && str == "dentro|N_Trono")
        {
            llLinksetDataWrite("senor", (string)id);
            llSay(0, nom(id) + " ocupa el trono. Todas las rejas del Foso le obedecen.");
            rotulos();
        }
        else if (n == 9600 && str == "fuera|N_Trono")
        {
            llLinksetDataDelete("senor");
            rotulos();
        }
        else if (n == 9001) rotulos();
    }

    touch_start(integer t)
    {
        USUARIO = llDetectedKey(0);
        string p = llGetLinkName(llDetectedLinkNumber(0));
        if (p == "N_Trono")
        {
            if (USUARIO != (key)llLinksetDataRead("senor") && USUARIO != llGetOwner())
            {
                llRegionSayTo(USUARIO, 0, "Solo quien ocupa el trono puede dar órdenes.");
                return;
            }
            MODO = "trono";
            dialogo(USUARIO, "SEÑOR DEL FOSO", ["Abrir todas", "Cerrar todas", "Ambiente", "Juicio", "Campana", "Libro"]);
        }
        else if (p == "C01_Escritorio")
        {
            MODO = "libro";
            dialogo(USUARIO, "LIBRO DE LA LEVA", ["Alistar", "Ver libro", "Juramento"]);
        }
        else if (p == "C01_Brasero_Marcar") { MODO = "marcar"; llSensor("", NULL_KEY, AGENT, 8.0, PI); }
    }

    listen(integer c, string n, key id, string m)
    {
        if (id != USUARIO) return;
        if (MODO == "elegir" || MODO == "alistar" || MODO == "marcar_elegir")
        {
            integer i = llListFindList(SENSADOS, [m]);
            if (i == -1) return;
            ELEGIDO = llList2Key(SENSADOS, i + 1);
            if (MODO == "alistar") alistar(ELEGIDO);
            else if (MODO == "marcar_elegir") marcar(ELEGIDO);
            else
            {
                MODO = "sala";
                dialogo(id, "¿A qué sala condenas a " + nom(ELEGIDO) + "?",
                        ["La Leva", "El Potro", "El Cepo", "La Cisterna", "La Perrera", "Las Jaulas", "El Mástil"]);
            }
            return;
        }
        if (MODO == "sala")
        {
            list salas = ["La Leva", "El Potro", "El Cepo", "La Cisterna", "La Perrera", "Las Jaulas", "El Mástil"];
            list tags = ["C01", "C02", "C03", "C04", "C05", "C07", "C08"];
            integer i = llListFindList(salas, [m]);
            if (i == -1) return;
            llMessageLinked(LINK_SET, 9400, "juicio|" + llList2String(tags, i) + "|" + (string)id + "|" + nom(id), id);
            llMessageLinked(LINK_SET, 9200, "JUICIO", id);
            llSay(0, "Por orden del Señor del Foso, " + nom(ELEGIDO) + " es condenado a " + llToUpper(m)
                  + ". La guardia lo arrastra y echa la llave.");
            return;
        }
        if (m == "Abrir todas") { llMessageLinked(LINK_SET, 9400, "todas|abrir", id); llSay(0, nom(id) + " ordena abrir todas las rejas del Foso."); }
        else if (m == "Cerrar todas") { llMessageLinked(LINK_SET, 9400, "todas|cerrar", id); llSay(0, nom(id) + " ordena cerrar todas las rejas."); }
        else if (m == "Ambiente") { MODO = "ambiente"; dialogo(id, "Ambiente del Foso", ["VIGILIA", "PENUMBRA", "JUICIO", "TINIEBLAS"]); }
        else if (llListFindList(["VIGILIA", "PENUMBRA", "JUICIO", "TINIEBLAS"], [m]) != -1)
        {
            llMessageLinked(LINK_SET, 9200, m, id);
            if (m == "TINIEBLAS") llSay(0, "Las antorchas se apagan una a una. Solo arden los braseros del trono.");
            else if (m == "JUICIO") llSay(0, "Los braseros rugen y todo el Foso se tiñe de rojo.");
        }
        else if (m == "Juicio") { MODO = "elegir"; llSensor("", NULL_KEY, AGENT, 30.0, PI); }
        else if (m == "Campana") { llMessageLinked(LINK_SET, 9300, "campana", id); llSay(0, "DONG... El Señor manda tocar la campana de la Leva."); }
        else if (m == "Libro" || m == "Ver libro") llDialog(id, libro(), ["Cerrar"], CANAL);
        else if (m == "Alistar") { MODO = "alistar"; llSensor("", NULL_KEY, AGENT, 8.0, PI); }
        else if (m == "Juramento")
            llSay(0, nom(id) + " pone la mano sobre el libro y jura: \"Mi espalda al látigo, mi sangre a la mar, mi vida al Señor del Foso.\"");
    }

    sensor(integer num)
    {
        SENSADOS = []; list b = [];
        integer i;
        for (i = 0; i < num && i < 12; ++i)
        {
            string nm = llGetSubString(llDetectedName(i), 0, 23);
            SENSADOS += [nm, llDetectedKey(i)]; b += nm;
        }
        if (MODO == "marcar") MODO = "marcar_elegir";
        dialogo(USUARIO, "Elige a quién:", b);
    }
    no_sensor() { llRegionSayTo(USUARIO, 0, "No hay nadie cerca."); }
    timer() { llListenRemove(ESCUCHA); llSetTimerEvent(0.0); }
}

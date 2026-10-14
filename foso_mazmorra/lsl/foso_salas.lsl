// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_salas.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - SALAS DE CASTIGO Y PERRERA (en la raíz)
//  Toca cada mueble para su menú. Todo se narra en el chat local.
//    El Potro ........ Tensar / Aflojar (5 niveles, texto flotante)
//    La Picota/Cepos . Escarnio / Liberar
//    La Cisterna ..... Sumergir / Sacar (la silla bascula y hunde al avatar;
//                      cuenta los segundos bajo el agua) / Liberar
//    Las Jaulas ...... Izar / Bajar (sube al preso con la jaula) / Liberar
//    El Mástil ....... Azotar (cuenta) / Sal en las heridas / Desatar
//    La Perrera ...... Casetas: Nombrar perro / Ladrar / Quitar nombre
//                      Comederos: Rancho / Agua
//    Cuerpo de guardia: Mesa (Dados, Brindis) · Cesto (Arrojar ropa a la perrera)
//    Piedra del trono: Presentar
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

float ANG_SILLA = -28.0;
float SUBIDA_JAULA = 1.4;
integer CANAL; integer ESCUCHA; key USUARIO; string PIEZA; integer LINK;

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}

integer link_avatar(key av)
{
    integer i;
    for (i = llGetObjectPrimCount(llGetKey()) + 1; i <= llGetNumberOfPrims(); ++i)
        if (llGetLinkKey(i) == av) return i;
    return -1;
}

key ocupante(string nm) { return (key)llLinksetDataRead("sit:" + nm); }
string nom(key k) { if (k == NULL_KEY) return "nadie"; return llGetDisplayName(k); }
say(string s) { llSay(0, s); }
texto(integer l, string t) { llSetLinkPrimitiveParamsFast(l, [PRIM_TEXT, t, <0.8, 0.55, 0.35>, 0.8]); }
string azar(list l) { return llList2String(l, (integer)llFrand(llGetListLength(l))); }

// gira (o traslada) una pieza y a quien esté sentado en ella, en varios pasos
mover_con_avatar(integer l, vector pivote, rotation giro, vector desplaza, integer pasos)
{
    list d = llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
    vector p0 = llList2Vector(d, 0); rotation r0 = llList2Rot(d, 1);
    key av = ocupante(llGetLinkName(l));
    integer al = -1; vector ap0; rotation ar0;
    if (av != NULL_KEY) al = link_avatar(av);
    if (al > 0) { list a = llGetLinkPrimitiveParams(al, [PRIM_POS_LOCAL, PRIM_ROT_LOCAL]);
                  ap0 = llList2Vector(a, 0); ar0 = llList2Rot(a, 1); }
    integer k;
    for (k = 1; k <= pasos; ++k)
    {
        float t = (float)k / pasos; t = t * t * (3.0 - 2.0 * t);
        rotation g = llAxisAngle2Rot(llRot2Axis(giro), llRot2Angle(giro) * t);
        vector dz = desplaza * t;
        llSetLinkPrimitiveParamsFast(l, [PRIM_POS_LOCAL, pivote + (p0 - pivote) * g + dz, PRIM_ROT_LOCAL, r0 * g]);
        if (al > 0) llSetLinkPrimitiveParamsFast(al, [PRIM_POS_LOCAL, pivote + (ap0 - pivote) * g + dz,
                                                      PRIM_ROT_LOCAL, ar0 * g]);
        llSleep(0.06);
    }
}

menu(key k, integer l)
{
    USUARIO = k; LINK = l; PIEZA = llGetLinkName(l);
    string t = ""; list b = [];
    key oc = ocupante(PIEZA);
    if (PIEZA == "C02_Potro") { t = "EL POTRO\nAtado: " + nom(oc); b = ["Tensar", "Aflojar", "Liberar"]; }
    else if (PIEZA == "C03_Picota" || PIEZA == "C03_Cepos") { t = "EL CEPO\nPreso: " + nom(oc); b = ["Escarnio", "Liberar"]; }
    else if (PIEZA == "C04_Silla")
    {
        t = "LA CISTERNA\nEn la silla: " + nom(oc);
        if (llLinksetDataRead("silla") == "abajo") b = ["Sacar"]; else b = ["Sumergir"];
        b += ["Liberar"];
    }
    else if (llSubStringIndex(PIEZA, "C07_Jaula") == 0)
    {
        t = "LAS JAULAS\nDentro: " + nom(oc);
        if (llLinksetDataRead(PIEZA) == "arriba") b = ["Bajar"]; else b = ["Izar"];
        b += ["Liberar"];
    }
    else if (PIEZA == "C08_Mastil") { t = "EL MÁSTIL\nAtado: " + nom(oc); b = ["Azotar", "Sal", "Desatar"]; }
    else if (llSubStringIndex(PIEZA, "C05_Caseta") == 0)
    {
        t = "LA PERRERA\n" + llLinksetDataRead(PIEZA);
        b = ["Nombrar", "Ladrar", "Quitar nombre"];
    }
    else if (PIEZA == "C05_Comederos") { t = "COMEDEROS DE LA PERRERA"; b = ["Rancho", "Agua"]; }
    else if (PIEZA == "V_Mesa") { t = "MESA DE LA GUARDIA"; b = ["Dados", "Brindis"]; }
    else if (PIEZA == "V_Cesta") { t = "CESTO DE LA COLADA\nRopa interior sucia de la guardia y de los esclavos."; b = ["Arrojar ropa"]; }
    else if (PIEZA == "N_Piedra") { t = "PIEDRA DE RODILLAS\nAnte el trono: " + nom(oc); b = ["Presentar"]; }
    else return;
    llListenRemove(ESCUCHA);
    ESCUCHA = llListen(CANAL, "", k, "");
    llSetTimerEvent(60.0);
    llDialog(k, t, b, CANAL);
}

accion(string b)
{
    string q = nom(USUARIO);
    key oc = ocupante(PIEZA);
    string v = nom(oc);
    if (b == "Liberar" || b == "Desatar")
    {
        if (oc != NULL_KEY) llUnSit(oc);
        if (PIEZA == "C08_Mastil") { llLinksetDataWrite("azotes", "0"); texto(LINK, ""); }
        if (PIEZA == "C02_Potro") { llLinksetDataWrite("potro", "0"); texto(LINK, ""); }
        say(q + " libera a " + v + ".");
    }
    else if (b == "Tensar" || b == "Aflojar")
    {
        integer n = (integer)llLinksetDataRead("potro");
        if (b == "Tensar" && n < 5) ++n;
        if (b == "Aflojar" && n > 0) --n;
        llLinksetDataWrite("potro", (string)n);
        list frases = ["las cuerdas quedan flojas.", "las cuerdas se tensan y crujen.",
                       "las articulaciones de " + v + " empiezan a protestar.", "el rodillo gime; " + v + " se arquea.",
                       "la madera chasquea y " + v + " ya no puede moverse.", "el potro está al límite. Un giro más sería cruel."];
        say(q + " hace girar la rueda: " + llList2String(frases, n));
        string barra = ""; integer i; for (i = 0; i < 5; ++i) { if (i < n) barra += "■"; else barra += "□"; }
        texto(LINK, "TENSIÓN " + barra);
    }
    else if (b == "Escarnio")
        say(azar([q + " escupe a los pies de " + v + ".", q + " le lanza mendrugos podridos a " + v + ".",
                  q + " se ríe de " + v + " delante de la guardia.", q + " le cuelga al cuello a " + v + " un cartel: COBARDE."]));
    else if (b == "Sumergir")
    {
        mover_con_avatar(LINK, llList2Vector(llGetLinkPrimitiveParams(LINK, [PRIM_POS_LOCAL]), 0)
                         + PIVOTE_SILLA * llList2Rot(llGetLinkPrimitiveParams(LINK, [PRIM_ROT_LOCAL]), 0),
                         llEuler2Rot(<0.0, ANG_SILLA * DEG_TO_RAD, 0.0>), ZERO_VECTOR, 18);
        llLinksetDataWrite("silla", "abajo");
        llLinksetDataWrite("silla_t", (string)llGetUnixTime());
        llMessageLinked(LINK_SET, 9300, "chapuzon", USUARIO);
        say(q + " suelta el contrapeso. La silla se hunde y " + v + " desaparece bajo el agua salada.");
    }
    else if (b == "Sacar")
    {
        mover_con_avatar(LINK, llList2Vector(llGetLinkPrimitiveParams(LINK, [PRIM_POS_LOCAL]), 0)
                         + PIVOTE_SILLA * llList2Rot(llGetLinkPrimitiveParams(LINK, [PRIM_ROT_LOCAL]), 0),
                         llEuler2Rot(<0.0, -ANG_SILLA * DEG_TO_RAD, 0.0>), ZERO_VECTOR, 18);
        integer seg = llGetUnixTime() - (integer)llLinksetDataRead("silla_t");
        llLinksetDataWrite("silla", "arriba");
        llMessageLinked(LINK_SET, 9300, "chapuzon", USUARIO);
        say(v + " sale del agua tosiendo tras " + (string)seg + " segundos sumergido.");
    }
    else if (b == "Izar" || b == "Bajar")
    {
        float dz = SUBIDA_JAULA; if (b == "Bajar") dz = -dz;
        vector p = llList2Vector(llGetLinkPrimitiveParams(LINK, [PRIM_POS_LOCAL]), 0);
        mover_con_avatar(LINK, p, llEuler2Rot(<0.0, 0.0, 0.12>), <0.0, 0.0, dz>, 24);
        mover_con_avatar(LINK, llList2Vector(llGetLinkPrimitiveParams(LINK, [PRIM_POS_LOCAL]), 0),
                         llEuler2Rot(<0.0, 0.0, -0.12>), ZERO_VECTOR, 10);
        if (b == "Izar") { llLinksetDataWrite(PIEZA, "arriba"); say(q + " gira el torno: la jaula de " + v + " sube balanceándose entre chirridos."); }
        else { llLinksetDataWrite(PIEZA, "abajo"); say("La jaula baja de golpe. Las cadenas de " + v + " tintinean."); }
    }
    else if (b == "Azotar")
    {
        integer n = (integer)llLinksetDataRead("azotes") + 1;
        llLinksetDataWrite("azotes", (string)n);
        texto(LINK, "AZOTES: " + (string)n);
        llMessageLinked(LINK_SET, 9300, "azote", USUARIO);
        say(azar(["¡Zas! ", "¡Chas! ", "El gato de nueve colas silba. "]) + q + " azota a " + v + ". (" + (string)n + ")");
    }
    else if (b == "Sal") say(q + " frota sal del barril en la espalda de " + v + ". Costumbre de a bordo.");
    else if (b == "Nombrar")
    {
        llTextBox(USUARIO, "Nombre de perro para el ocupante de esta caseta:", CANAL);
        return;
    }
    else if (b == "Ladrar") say(q + " ladra desde la perrera. Los demás perros contestan.");
    else if (b == "Quitar nombre") { llLinksetDataDelete(PIEZA); texto(LINK, ""); say(q + " arranca la placa de la caseta."); }
    else if (b == "Rancho") say(q + " vuelca un cubo de rancho frío en los comederos. Que coman de rodillas.");
    else if (b == "Agua") say(q + " llena las escudillas de agua turbia.");
    else if (b == "Dados")
    {
        integer a = 1 + (integer)llFrand(6.0); integer c = 1 + (integer)llFrand(6.0);
        say(q + " tira los dados sobre la mesa: " + (string)a + " y " + (string)c + " (" + (string)(a + c) + ").");
    }
    else if (b == "Brindis") say(q + " alza la jarra: ¡Por el Señor del Foso y por la carne nueva!");
    else if (b == "Arrojar ropa")
    {
        llMessageLinked(LINK_SET, 9300, "ropa", USUARIO);
        say(q + " abre la trampilla y vacía el cesto: calzones y taparrabos sucios de la guardia llueven sobre la perrera.");
    }
    else if (b == "Presentar")
        say(q + " arroja a " + v + " de rodillas sobre la piedra. Que el Señor del Foso decida su destino.");
}

default
{
    state_entry() { CANAL = -1 - (integer)llFrand(1000000.0); }
    on_rez(integer p) { llResetScript(); }
    touch_start(integer n) { menu(llDetectedKey(0), llDetectedLinkNumber(0)); }
    listen(integer c, string n, key id, string m)
    {
        if (id != USUARIO) return;
        if (llSubStringIndex(PIEZA, "C05_Caseta") == 0 && llListFindList(["Nombrar", "Ladrar", "Quitar nombre"], [m]) == -1)
        {
            string txt = "PERRO: " + m + "\nAmo: " + nom(id);
            llLinksetDataWrite(PIEZA, txt);
            texto(LINK, txt);
            say(nom(id) + " cuelga una placa en la caseta: \"" + m + "\". Desde hoy responde a ese nombre.");
            return;
        }
        accion(m);
    }
    timer() { llListenRemove(ESCUCHA); llSetTimerEvent(0.0); }
}

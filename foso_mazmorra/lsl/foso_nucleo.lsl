// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_nucleo.lsl (no editar a mano)
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

list TABLA = [
    "M0O_Machon", 0, <0.980,2.486,8.200>, <-3.380,-24.963,0.707>,
    "M1O_Machon", 0, <0.980,4.361,8.200>, <-3.380,-20.151,0.707>,
    "M2O_Machon", 0, <0.980,4.361,8.200>, <-3.380,-14.401,0.707>,
    "M3O_Machon", 0, <0.980,4.361,8.200>, <-3.380,-8.651,0.707>,
    "M4O_Machon", 0, <0.980,2.475,8.200>, <-3.380,-3.844,0.707>,
    "C01_Arco", 0, <0.980,5.720,4.780>, <-3.380,-23.031,2.417>,
    "C01_Puerta", 1, <0.218,1.415,2.550>, <-3.450,-23.054,-1.288>,
    "C02_Arco", 0, <0.980,5.720,4.780>, <-3.380,-17.281,2.417>,
    "C02_Puerta", 1, <0.218,1.415,2.550>, <-3.450,-17.304,-1.288>,
    "C03_Arco", 0, <0.980,5.720,4.780>, <-3.380,-11.531,2.417>,
    "C03_Puerta", 1, <0.218,1.415,2.550>, <-3.450,-11.554,-1.288>,
    "C04_Arco", 0, <0.980,5.720,4.780>, <-3.380,-5.781,2.417>,
    "C04_Puerta", 1, <0.218,1.415,2.550>, <-3.450,-5.804,-1.288>,
    "M0E_Machon", 0, <0.980,2.486,8.200>, <3.380,-24.963,0.707>,
    "M1E_Machon", 0, <0.980,4.361,8.200>, <3.380,-20.151,0.707>,
    "M2E_Machon", 0, <0.980,4.361,8.200>, <3.380,-14.401,0.707>,
    "M3E_Machon", 0, <0.980,4.361,8.200>, <3.380,-8.651,0.707>,
    "M4E_Machon", 0, <0.980,2.475,8.200>, <3.380,-3.844,0.707>,
    "C05_Arco", 0, <0.980,5.720,4.780>, <3.380,-23.031,2.417>,
    "C05_Puerta", 1, <0.218,1.415,2.550>, <3.450,-23.054,-1.288>,
    "C06_Arco", 0, <0.980,5.720,4.780>, <3.380,-17.281,2.417>,
    "C06_Puerta", 1, <0.218,1.415,2.550>, <3.450,-17.304,-1.288>,
    "C07_Arco", 0, <0.980,5.720,4.780>, <3.380,-11.531,2.417>,
    "C07_Puerta", 1, <0.218,1.415,2.550>, <3.450,-11.554,-1.288>,
    "C08_Arco", 0, <0.980,5.720,4.780>, <3.380,-5.781,2.417>,
    "C08_Puerta", 1, <0.218,1.415,2.550>, <3.450,-5.804,-1.288>,
    "C01_Suelo", 0, <8.600,5.150,0.855>, <-7.300,-23.031,-2.965>,
    "C01_Particion", 0, <7.800,0.600,5.000>, <-7.700,-20.156,-0.893>,
    "C01_Muro", 0, <1.450,6.200,8.180>, <-12.275,-22.806,0.697>,
    "C01_Boveda", 0, <7.800,5.750,3.255>, <-7.700,-23.031,2.854>,
    "C02_Suelo", 0, <8.600,5.150,0.853>, <-7.300,-17.281,-2.966>,
    "C02_Particion", 0, <7.800,0.600,5.000>, <-7.700,-14.406,-0.893>,
    "C02_Muro", 0, <1.450,6.200,8.180>, <-12.275,-17.056,0.697>,
    "C02_Boveda", 0, <7.800,5.750,3.255>, <-7.700,-17.281,2.854>,
    "C03_Suelo", 0, <8.600,5.150,0.858>, <-7.300,-11.531,-2.964>,
    "C03_Particion", 0, <7.800,0.600,5.000>, <-7.700,-8.656,-0.893>,
    "C03_Muro", 0, <1.450,6.200,8.180>, <-12.275,-11.306,0.697>,
    "C03_Boveda", 0, <7.800,5.750,3.255>, <-7.700,-11.531,2.854>,
    "C04_Suelo", 0, <8.600,5.150,0.857>, <-7.300,-5.781,-2.964>,
    "C04_Particion", 0, <7.900,0.720,8.180>, <-7.700,-2.906,0.697>,
    "C04_Muro", 0, <1.450,6.200,8.180>, <-12.275,-5.556,0.697>,
    "C04_Boveda", 0, <7.800,5.750,3.255>, <-7.700,-5.781,2.854>,
    "C05_Suelo", 0, <8.600,10.900,0.860>, <7.300,-20.156,-2.963>,
    "C05_Particion", 0, <7.800,0.600,5.000>, <7.700,-14.406,-0.893>,
    "C05_Muro", 0, <1.450,11.950,8.180>, <12.275,-19.931,0.697>,
    "C05_Techo", 0, <7.800,10.940,0.663>, <7.700,-20.156,2.757>,
    "C07_Suelo", 0, <8.600,5.150,0.859>, <7.300,-11.531,-2.963>,
    "C07_Particion", 0, <7.800,0.600,5.000>, <7.700,-8.656,-0.893>,
    "C07_Muro", 0, <1.450,6.200,8.180>, <12.275,-11.306,0.697>,
    "C07_Boveda", 0, <7.800,5.750,3.255>, <7.700,-11.531,2.854>,
    "C08_Suelo", 0, <8.600,5.150,0.860>, <7.300,-5.781,-2.963>,
    "C08_Particion", 0, <7.900,0.720,8.180>, <7.700,-2.906,0.697>,
    "C08_Muro", 0, <1.450,6.200,8.180>, <12.275,-5.556,0.697>,
    "C08_Boveda", 0, <7.800,5.750,3.255>, <7.700,-5.781,2.854>,
    "C01_Escritorio", 4, <1.500,1.379,1.510>, <-7.600,-22.704,-1.846>,
    "C01_Brasero_Marcar", 3, <1.771,1.173,1.169>, <-9.618,-24.742,-2.008>,
    "C01_Atrezzo", 2, <0.845,4.410,2.500>, <-11.200,-23.126,-1.343>,
    "C02_Potro", 4, <3.075,1.200,1.564>, <-7.315,-17.201,-1.811>,
    "C02_Atrezzo", 2, <6.093,1.176,2.337>, <-8.047,-15.294,-1.462>,
    "C02_Antorcha", 3, <0.763,0.182,1.737>, <-11.218,-15.465,0.406>,
    "C03_Picota", 4, <2.220,2.800,2.335>, <-7.400,-11.831,-1.426>,
    "C03_Cepos", 4, <1.800,0.970,0.460>, <-9.900,-10.366,-2.363>,
    "C03_Atrezzo", 2, <1.285,2.461,3.174>, <-10.958,-13.047,-0.986>,
    "C03_Antorcha", 3, <0.765,0.188,1.737>, <-11.217,-10.916,0.406>,
    "C04_Cisterna", 0, <4.857,3.000,2.213>, <-9.072,-5.781,-1.887>,
    "C04_Agua", 5, <2.740,2.440,1.060>, <-9.850,-5.781,-2.353>,
    "C04_Silla", 4, <4.750,0.664,0.900>, <-7.825,-5.781,-0.943>,
    "C04_Antorcha", 3, <0.181,0.763,1.737>, <-4.984,-3.588,0.406>,
    "C04_Atrezzo", 2, <2.080,1.116,1.040>, <-5.370,-7.828,-2.053>,
    "C05_Caseta_1", 4, <1.110,1.771,1.100>, <10.595,-24.291,-2.043>,
    "C05_Caseta_2", 4, <1.110,1.771,1.100>, <10.595,-20.241,-2.043>,
    "C05_Caseta_3", 4, <1.110,1.771,1.100>, <10.595,-16.191,-2.043>,
    "C05_Comederos", 2, <5.540,1.216,1.082>, <6.970,-15.314,-2.072>,
    "C05_Ropa", 2, <5.683,1.685,0.313>, <7.119,-24.984,-2.474>,
    "C05_Farol", 3, <0.440,0.441,2.503>, <7.600,-20.156,1.541>,
    "C07_Jaula_1", 4, <0.867,0.880,5.861>, <7.000,-12.631,1.220>,
    "C07_Jaula_2", 4, <0.867,0.880,5.861>, <9.000,-10.531,1.220>,
    "C07_Torno", 2, <3.173,0.813,1.562>, <6.267,-13.756,-1.812>,
    "C07_Antorcha", 3, <0.761,0.192,1.737>, <11.220,-11.747,0.406>,
    "C08_Mastil", 4, <1.500,0.924,4.247>, <7.250,-5.793,-0.870>,
    "C08_Atrezzo", 2, <5.930,1.150,2.200>, <7.965,-3.781,-1.493>,
    "C08_Antorcha", 3, <0.762,0.182,1.737>, <11.219,-7.397,0.406>,
    "P1_Suelo", 0, <6.000,5.750,0.841>, <0.000,-23.031,-2.973>,
    "P2_Suelo", 0, <6.000,5.750,0.842>, <0.000,-17.281,-2.972>,
    "P3_Suelo", 0, <6.000,5.750,0.837>, <0.000,-11.531,-2.975>,
    "P4_Suelo", 0, <6.000,5.750,0.840>, <0.000,-5.781,-2.973>,
    "P_Agua", 5, <0.420,23.000,0.000>, <0.000,-14.406,-2.663>,
    "T0_Viga", 2, <6.500,0.460,1.050>, <0.000,-25.906,3.232>,
    "T1_Viga", 2, <6.500,0.460,1.050>, <0.000,-20.156,3.232>,
    "T2_Viga", 2, <6.500,0.460,1.050>, <0.000,-14.406,3.232>,
    "T3_Viga", 2, <6.500,0.460,1.050>, <0.000,-8.656,3.232>,
    "T4_Viga", 2, <6.500,0.460,1.050>, <0.000,-2.906,3.232>,
    "P_Ajusticiado", 2, <2.546,0.331,2.903>, <0.836,-20.080,1.910>,
    "T1_Farol", 3, <0.441,0.441,2.503>, <-1.301,-20.156,2.080>,
    "T2_Farol", 3, <0.440,0.440,2.503>, <-0.200,-14.406,2.080>,
    "T3_Farol", 3, <0.441,0.440,2.503>, <-0.200,-8.656,2.080>,
    "A0O_Antorcha", 3, <0.761,0.183,1.737>, <-2.620,-25.890,0.356>,
    "A0E_Antorcha", 3, <0.764,0.182,1.737>, <2.618,-25.922,0.356>,
    "A1O_Antorcha", 3, <0.763,0.181,1.737>, <-2.618,-20.140,0.356>,
    "A1E_Antorcha", 3, <0.762,0.195,1.737>, <2.619,-20.171,0.356>,
    "A2O_Antorcha", 3, <0.763,0.198,1.737>, <-2.619,-14.391,0.356>,
    "A2E_Antorcha", 3, <0.764,0.192,1.737>, <2.618,-14.421,0.356>,
    "A3O_Antorcha", 3, <0.761,0.183,1.737>, <-2.619,-8.640,0.356>,
    "A3E_Antorcha", 3, <0.763,0.181,1.737>, <2.618,-8.671,0.356>,
    "A4O_Antorcha", 3, <0.762,0.182,1.737>, <-2.619,-2.890,0.356>,
    "A4E_Antorcha", 3, <0.762,0.182,1.737>, <2.619,-2.922,0.356>,
    "G_Muro_O", 0, <7.000,1.500,8.180>, <-9.500,-30.256,0.697>,
    "V_Muro_O", 0, <1.400,4.150,8.180>, <-12.300,-27.531,0.697>,
    "V_Particion_O", 0, <7.850,0.720,8.180>, <-7.675,-25.906,0.697>,
    "G_Torre_O", 0, <4.650,4.070,11.000>, <-4.025,-30.721,2.107>,
    "G_Muro_E", 0, <7.000,1.500,8.180>, <9.500,-30.256,0.697>,
    "V_Muro_E", 0, <1.400,4.150,8.180>, <12.300,-27.531,0.697>,
    "V_Particion_E", 0, <7.850,0.720,8.180>, <7.675,-25.906,0.697>,
    "G_Torre_E", 0, <4.650,4.070,11.000>, <4.025,-30.721,2.107>,
    "A0O_Antorcha_Vestibulo", 3, <0.181,0.762,1.737>, <-7.684,-26.587,0.406>,
    "A0E_Antorcha_Vestibulo", 3, <0.198,0.764,1.737>, <7.716,-26.588,0.406>,
    "V_Suelo_1", 0, <7.600,3.700,0.800>, <-7.800,-27.756,-2.993>,
    "V_Suelo_2", 0, <8.000,3.700,0.800>, <0.000,-27.756,-2.993>,
    "V_Suelo_3", 0, <7.600,3.700,0.800>, <7.800,-27.756,-2.993>,
    "G_Escalinata", 0, <6.000,4.000,0.800>, <0.000,-31.606,-2.993>,
    "G_Arco", 0, <5.460,4.000,7.410>, <0.000,-30.706,3.852>,
    "G_Rastrillo", 1, <3.540,0.160,5.600>, <0.000,-32.026,0.207>,
    "G_Hoja_O", 1, <1.826,0.258,3.050>, <-0.922,-28.735,-1.038>,
    "G_Hoja_E", 1, <1.826,0.258,3.050>, <0.922,-28.735,-1.038>,
    "G_Torno", 4, <4.509,1.001,3.830>, <-3.425,-28.315,-0.678>,
    "V_Mesa", 4, <2.000,1.900,1.140>, <6.600,-27.806,-2.023>,
    "V_Atrezzo_O", 2, <4.926,0.634,2.800>, <-8.537,-29.573,-1.193>,
    "V_Cesta", 2, <1.374,1.762,0.700>, <9.699,-27.584,-2.243>,
    "N_Muro_O", 0, <1.400,4.500,8.180>, <-12.300,-0.656,0.697>,
    "N_Fondo_O", 0, <7.100,1.060,8.180>, <-8.050,1.134,0.697>,
    "N_Muro_E", 0, <1.400,4.500,8.180>, <12.300,-0.656,0.697>,
    "N_Fondo_E", 0, <7.100,1.060,8.180>, <8.050,1.134,0.697>,
    "N_Fondo_C", 0, <9.000,0.990,8.180>, <0.000,1.169,0.697>,
    "N_Suelo_1", 0, <7.600,3.700,0.800>, <-7.800,-1.056,-2.993>,
    "N_Suelo_2", 0, <8.000,3.700,0.800>, <0.000,-1.056,-2.993>,
    "N_Suelo_3", 0, <7.600,3.700,0.800>, <7.800,-1.056,-2.993>,
    "N_Estrado", 0, <8.580,3.890,1.000>, <0.000,-1.151,-2.193>,
    "N_Trono", 4, <1.950,1.387,3.413>, <0.000,0.000,0.000>,
    "N_Piedra", 4, <1.026,1.300,0.312>, <0.063,-1.606,-1.556>,
    "N_Brasero_O", 3, <1.579,1.506,2.060>, <-2.332,-0.425,-0.663>,
    "N_Brasero_E", 3, <1.579,1.506,2.060>, <2.268,-0.425,-0.663>,
    "N_Atrezzo_O", 2, <4.217,2.333,2.400>, <-8.971,-0.592,-1.393>,
    "N_Atrezzo_E", 2, <3.594,1.617,2.400>, <9.283,-0.069,-1.393>];

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

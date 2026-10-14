// =====================================================================
//  EL FOSO V3 - FUEGO VIVO, NIEBLA Y AMBIENTE (en la raíz)
//
//  * Llamas animadas: cada antorcha, farol y brasero emite una llama de
//    partículas (núcleo blanco-amarillo que asciende, se ensancha y se apaga
//    en rojo oscuro) sobre la llama de malla, que hace de corazón.
//    Las piezas de fuego tienen su centro justo en la base de la llama.
//  * La luz respira: intensidad, radio y color siguen un ruido suave
//    independiente para cada fuego, con "chasquidos" (destello breve y una
//    lluvia de chispas) y "boqueadas" (la llama casi se ahoga y se recupera).
//  * Corrientes: al abrir o golpear una reja, los fuegos a menos de 8 m se
//    tumban y parpadean como si entrara aire.
//  * Niebla de mar sobre el canal, bruma baja en la perrera, gotas que caen
//    de las bóvedas, vapor sobre la cisterna.
//  * Ambientes (los elige el Señor desde el trono): VIGILIA, PENUMBRA,
//    JUICIO (todo rojo, braseros rugiendo) y TINIEBLAS (solo los braseros).
//
//  * Con texturas propias (ver abajo): llama de malla animada (flipbook
//    4x4), humo que alterna con la llama en los braseros y luces
//    proyectoras que dibujan barrotes y cadenas en suelos y paredes.
// =====================================================================

// ---------------------------------------------------------------------
//  TEXTURAS DE EFECTOS: las genera scripts/sprites_efectos.py en
//  salida/efectos/. Sube cada PNG (Construir > Subir > Imagen), en el
//  inventario clic derecho > "Copiar UUID" y pégalo entre las comillas.
//  Vacío ("") = comportamiento anterior (partícula por defecto, sin
//  flipbook, sin humo alterno, sin proyector).
//    TEXTURA_FLIPBOOK   fuego_flipbook.png   llama de malla (cara 7), 4x4 fotogramas
//    TEXTURA_LLAMA      llama_particula.png  partícula de llama
//    TEXTURA_HUMO       humo.png             humo que sube de los braseros
//    TEXTURA_NIEBLA     niebla.png           niebla del canal, bruma y vapor
//    TEXTURA_CHISPA     chispa.png           chispas de los chasquidos y la marca
//    TEXTURA_GOTA       gota.png             gotas que caen de las bóvedas
//    TEXTURA_PROYECTOR  proyector_fuego.png  luz proyectora en los braseros del
//                       trono, el farol de la perrera y los faroles del patio.
//  Las luces proyectoras y sus sombras solo se ven con las sombras activadas
//  en el visor (Preferencias > Gráficos > Sombras: "Sol/Luna + proyectores").
//  Proyectan hacia el -Z local de la pieza (hacia abajo).
// ---------------------------------------------------------------------
string  TEXTURA_FLIPBOOK = "";
string  TEXTURA_LLAMA = "";
string  TEXTURA_HUMO = "";
string  TEXTURA_NIEBLA = "";
string  TEXTURA_CHISPA = "";
string  TEXTURA_GOTA = "";
string  TEXTURA_PROYECTOR = "";
float   FPS_FUEGO = 12.0;        // fotogramas por segundo del flipbook (cada fuego varía un poco)
float   TICK = 0.12;
integer POR_TICK = 5;

list F_LINK; list F_TIPO; list F_POS; list F_NIVEL; list F_VEL; list F_RACHA;  // tipo: 0 antorcha, 1 farol, 2 brasero
list F_HUMO; list F_PROY;   // humo: próximo cambio (>0 llama, <0 humo); proy: lleva luz proyectora
integer cursor;
string AMBIENTE = "VIGILIA";
float  K_LUZ = 1.0; float K_RADIO = 1.0; vector TINTE = <1.0, 0.55, 0.22>;

list llama(integer tipo, float viento_x, float viento_y, integer chispas)
{
    float esc = 0.09; float vida = 0.7; integer cant = 3; float sube = 0.55;
    if (tipo == 1) { esc = 0.045; vida = 0.5; cant = 2; sube = 0.3; }
    if (tipo == 2) { esc = 0.22; vida = 1.0; cant = 6; sube = 0.9; }
    if (AMBIENTE == "JUICIO") { cant = cant * 2; sube = sube * 1.4; }
    if (AMBIENTE == "TINIEBLAS" && tipo != 2) return [];
    if (chispas)
        return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_WIND_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.6,
                PSYS_SRC_TEXTURE, TEXTURA_CHISPA,
                PSYS_PART_START_COLOR, <1.0, 0.85, 0.4>, PSYS_PART_END_COLOR, <0.9, 0.2, 0.0>,
                PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.03, 0.03, 0.0>, PSYS_PART_END_SCALE, <0.01, 0.01, 0.0>,
                PSYS_PART_MAX_AGE, 1.8, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 6,
                PSYS_SRC_BURST_SPEED_MIN, 0.6, PSYS_SRC_BURST_SPEED_MAX, 1.6,
                PSYS_SRC_ACCEL, <viento_x, viento_y, 0.4>, PSYS_SRC_MAX_AGE, 0.0];
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.25,
            PSYS_SRC_TEXTURE, TEXTURA_LLAMA,
            PSYS_PART_START_COLOR, <1.0, 0.92, 0.6>, PSYS_PART_END_COLOR, <0.75, 0.12, 0.02>,
            PSYS_PART_START_ALPHA, 0.85, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <esc, esc * 1.6, 0.0>, PSYS_PART_END_SCALE, <esc * 0.3, esc * 0.6, 0.0>,
            PSYS_PART_MAX_AGE, vida, PSYS_SRC_BURST_RATE, 0.03, PSYS_SRC_BURST_PART_COUNT, cant,
            PSYS_SRC_BURST_RADIUS, esc * 0.2, PSYS_SRC_BURST_SPEED_MIN, 0.03, PSYS_SRC_BURST_SPEED_MAX, 0.12,
            PSYS_SRC_ACCEL, <viento_x, viento_y, sube>, PSYS_SRC_MAX_AGE, 0.0];
}

// humo de brasero: alterna con la llama de partículas (una prim solo tiene
// un sistema); mientras humea, la llama de malla animada sigue ardiendo
list humo()
{
    return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.2,
            PSYS_SRC_TEXTURE, TEXTURA_HUMO,
            PSYS_PART_START_COLOR, <0.30, 0.27, 0.24>, PSYS_PART_END_COLOR, <0.16, 0.15, 0.14>,
            PSYS_PART_START_ALPHA, 0.32, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <0.3, 0.3, 0.0>, PSYS_PART_END_SCALE, <1.5, 1.5, 0.0>,
            PSYS_PART_MAX_AGE, 4.5, PSYS_SRC_BURST_RATE, 0.12, PSYS_SRC_BURST_PART_COUNT, 1,
            PSYS_SRC_BURST_RADIUS, 0.05, PSYS_SRC_BURST_SPEED_MIN, 0.35, PSYS_SRC_BURST_SPEED_MAX, 0.6,
            PSYS_SRC_ACCEL, <0.0, 0.0, 0.15>, PSYS_SRC_MAX_AGE, 0.0];
}

list niebla(float densidad, vector color, float radio)
{
    if (densidad <= 0.0) return [];
    return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK | PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 1.2, PSYS_SRC_ANGLE_END, 1.57,
            PSYS_SRC_TEXTURE, TEXTURA_NIEBLA,
            PSYS_PART_START_COLOR, color, PSYS_PART_END_COLOR, color,
            PSYS_PART_START_ALPHA, 0.0, PSYS_PART_END_ALPHA, 0.09 * densidad,
            PSYS_PART_START_SCALE, <1.5, 1.5, 0.0>, PSYS_PART_END_SCALE, <4.0, 4.0, 0.0>,
            PSYS_PART_MAX_AGE, 14.0, PSYS_SRC_BURST_RATE, 0.35, PSYS_SRC_BURST_PART_COUNT, 2,
            PSYS_SRC_BURST_RADIUS, radio, PSYS_SRC_BURST_SPEED_MIN, 0.05, PSYS_SRC_BURST_SPEED_MAX, 0.25,
            PSYS_SRC_ACCEL, <0.0, 0.0, -0.01>, PSYS_SRC_MAX_AGE, 0.0];
}

list goteo()
{
    return [PSYS_PART_FLAGS, PSYS_PART_FOLLOW_VELOCITY_MASK | PSYS_PART_INTERP_COLOR_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
            PSYS_SRC_TEXTURE, TEXTURA_GOTA,
            PSYS_PART_START_COLOR, <0.7, 0.8, 0.85>, PSYS_PART_END_COLOR, <0.7, 0.8, 0.85>,
            PSYS_PART_START_ALPHA, 0.55, PSYS_PART_END_ALPHA, 0.35,
            PSYS_PART_START_SCALE, <0.012, 0.07, 0.0>, PSYS_PART_END_SCALE, <0.012, 0.09, 0.0>,
            PSYS_PART_MAX_AGE, 1.15, PSYS_SRC_BURST_RATE, 1.7, PSYS_SRC_BURST_PART_COUNT, 1,
            PSYS_SRC_BURST_RADIUS, 2.2, PSYS_SRC_BURST_SPEED_MIN, 0.0, PSYS_SRC_BURST_SPEED_MAX, 0.0,
            PSYS_SRC_ACCEL, <0.0, 0.0, -9.8>, PSYS_SRC_MAX_AGE, 0.0];
}

list rafaga(string que)
{
    if (que == "ropa")     // trapos que caen por la trampilla del techo de la perrera
        return [PSYS_PART_FLAGS, PSYS_PART_INTERP_SCALE_MASK | PSYS_PART_WIND_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
                PSYS_PART_START_COLOR, <0.75, 0.7, 0.6>, PSYS_PART_END_COLOR, <0.6, 0.55, 0.45>,
                PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.9,
                PSYS_PART_START_SCALE, <0.3, 0.22, 0.0>, PSYS_PART_END_SCALE, <0.35, 0.25, 0.0>,
                PSYS_PART_MAX_AGE, 2.4, PSYS_SRC_BURST_RATE, 0.05, PSYS_SRC_BURST_PART_COUNT, 3,
                PSYS_SRC_BURST_RADIUS, 0.4, PSYS_SRC_BURST_SPEED_MIN, 0.2, PSYS_SRC_BURST_SPEED_MAX, 0.8,
                PSYS_SRC_ACCEL, <0.0, 0.0, -2.2>, PSYS_SRC_MAX_AGE, 1.5];
    if (que == "chapuzon")
        return [PSYS_PART_FLAGS, PSYS_PART_INTERP_COLOR_MASK,
                PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_ANGLE_CONE, PSYS_SRC_ANGLE_BEGIN, 0.0, PSYS_SRC_ANGLE_END, 0.9,
                PSYS_PART_START_COLOR, <0.85, 0.9, 0.95>, PSYS_PART_END_COLOR, <0.6, 0.7, 0.75>,
                PSYS_PART_START_ALPHA, 0.9, PSYS_PART_END_ALPHA, 0.0,
                PSYS_PART_START_SCALE, <0.08, 0.08, 0.0>, PSYS_PART_END_SCALE, <0.03, 0.03, 0.0>,
                PSYS_PART_MAX_AGE, 1.0, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 12,
                PSYS_SRC_BURST_SPEED_MIN, 1.5, PSYS_SRC_BURST_SPEED_MAX, 3.0,
                PSYS_SRC_ACCEL, <0.0, 0.0, -6.0>, PSYS_SRC_MAX_AGE, 0.6];
    // marca / azote: polvo y chispas
    return [PSYS_PART_FLAGS, PSYS_PART_EMISSIVE_MASK | PSYS_PART_INTERP_COLOR_MASK,
            PSYS_SRC_PATTERN, PSYS_SRC_PATTERN_EXPLODE,
            PSYS_SRC_TEXTURE, TEXTURA_CHISPA,
            PSYS_PART_START_COLOR, <1.0, 0.7, 0.3>, PSYS_PART_END_COLOR, <0.5, 0.1, 0.0>,
            PSYS_PART_START_ALPHA, 1.0, PSYS_PART_END_ALPHA, 0.0,
            PSYS_PART_START_SCALE, <0.04, 0.04, 0.0>, PSYS_PART_END_SCALE, <0.01, 0.01, 0.0>,
            PSYS_PART_MAX_AGE, 1.2, PSYS_SRC_BURST_RATE, 0.02, PSYS_SRC_BURST_PART_COUNT, 15,
            PSYS_SRC_BURST_SPEED_MIN, 1.0, PSYS_SRC_BURST_SPEED_MAX, 2.5,
            PSYS_SRC_ACCEL, <0.0, 0.0, -2.0>, PSYS_SRC_MAX_AGE, 0.5];
}

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}

// braseros del trono, farol de la perrera y faroles del patio
integer es_proyector(string nm)
{
    if (llSubStringIndex(nm, "N_Brasero") == 0) return TRUE;
    if (nm == "C05_Farol") return TRUE;
    if (llGetSubString(nm, 0, 0) == "T" && llSubStringIndex(nm, "_Farol") != -1) return TRUE;
    return FALSE;
}

ambientar()
{
    float d = 1.0;
    if (AMBIENTE == "VIGILIA") { K_LUZ = 1.0; K_RADIO = 1.0; TINTE = <1.0, 0.55, 0.22>; d = 1.0; }
    else if (AMBIENTE == "PENUMBRA") { K_LUZ = 0.5; K_RADIO = 0.7; TINTE = <1.0, 0.45, 0.18>; d = 1.6; }
    else if (AMBIENTE == "JUICIO") { K_LUZ = 1.3; K_RADIO = 1.2; TINTE = <1.0, 0.25, 0.08>; d = 0.8; }
    else if (AMBIENTE == "TINIEBLAS") { K_LUZ = 0.0; K_RADIO = 0.6; TINTE = <0.9, 0.3, 0.1>; d = 2.2; }
    // con flipbook la textura ya trae el color: el tinte apenas la calienta
    vector tinte_llama = <1.0, 0.7, 0.35>;
    if (TEXTURA_FLIPBOOK != "") tinte_llama = <1.0, 0.92, 0.82>;
    integer i;
    for (i = 0; i < llGetListLength(F_LINK); ++i)
    {
        integer l = llList2Integer(F_LINK, i);
        integer tipo = llList2Integer(F_TIPO, i);
        integer apagado = (AMBIENTE == "TINIEBLAS" && tipo != 2);
        llLinkParticleSystem(l, llama(tipo, 0.0, 0.0, FALSE));
        if (TEXTURA_FLIPBOOK != "")
        {
            llSetLinkPrimitiveParamsFast(l, [PRIM_TEXTURE, 7, TEXTURA_FLIPBOOK, <1.0, 1.0, 0.0>, ZERO_VECTOR, 0.0,
                                            PRIM_ALPHA_MODE, 7, PRIM_ALPHA_MODE_BLEND, 0]);
            // velocidad algo distinta en cada fuego: no laten a la vez
            if (apagado) llSetLinkTextureAnim(l, FALSE, 7, 4, 4, 0.0, 16.0, 1.0);
            else llSetLinkTextureAnim(l, ANIM_ON | LOOP, 7, 4, 4, 0.0, 16.0, FPS_FUEGO * (0.82 + 0.045 * (i % 9)));
        }
        if (TEXTURA_PROYECTOR != "" && llList2Integer(F_PROY, i))
        {
            // FOV amplio, foco corto y ambiente bajo: barrotes y cadenas en sombra
            float fov = 2.2;
            if (tipo == 2) fov = 2.8;
            if (apagado) llSetLinkPrimitiveParamsFast(l, [PRIM_PROJECTOR, NULL_KEY, fov, 1.5, 0.0]);
            else llSetLinkPrimitiveParamsFast(l, [PRIM_PROJECTOR, TEXTURA_PROYECTOR, fov, 1.5, 0.08]);
        }
        if (apagado)
            llSetLinkPrimitiveParamsFast(l, [PRIM_POINT_LIGHT, FALSE, ZERO_VECTOR, 0, 0, 0, PRIM_GLOW, 7, 0.0,
                                            PRIM_COLOR, 7, <0.1, 0.05, 0.03>, 1.0, PRIM_FULLBRIGHT, 7, FALSE]);
        else
            llSetLinkPrimitiveParamsFast(l, [PRIM_COLOR, 7, tinte_llama, 1.0, PRIM_FULLBRIGHT, 7, TRUE]);
    }
    integer a = link_de("P_Agua");
    if (a > 0) llLinkParticleSystem(a, niebla(d, <0.55, 0.62, 0.68>, 1.2));
    a = link_de("C05_Suelo");
    if (a > 0) llLinkParticleSystem(a, niebla(d * 0.8, <0.45, 0.42, 0.38>, 0.7));
    a = link_de("C04_Agua");
    if (a > 0) llLinkParticleSystem(a, niebla(d * 1.2, <0.8, 0.85, 0.9>, 0.6));
    list bov = ["C01_Boveda", "C02_Boveda", "C03_Boveda", "C04_Boveda", "C07_Boveda", "C08_Boveda"];
    for (i = 0; i < llGetListLength(bov); ++i)
    {
        a = link_de(llList2String(bov, i));
        if (a > 0) llLinkParticleSystem(a, goteo());
    }
}

escanear()
{
    F_LINK = []; F_TIPO = []; F_POS = []; F_NIVEL = []; F_VEL = []; F_RACHA = []; F_HUMO = []; F_PROY = [];
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i)
    {
        string nm = llGetLinkName(i);
        integer t = -1;
        if (llSubStringIndex(nm, "Antorcha") != -1) t = 0;
        else if (llSubStringIndex(nm, "Farol") != -1) t = 1;
        else if (llSubStringIndex(nm, "Brasero") != -1) t = 2;
        if (t >= 0)
        {
            vector p = ZERO_VECTOR;
            if (i > 1) p = llList2Vector(llGetLinkPrimitiveParams(i, [PRIM_POS_LOCAL]), 0);
            F_LINK += i; F_TIPO += t; F_POS += p; F_NIVEL += 1.0; F_VEL += 0.0; F_RACHA += 0;
            F_HUMO += llGetTime() + 2.0 + llFrand(5.0); F_PROY += es_proyector(nm);
        }
    }
    ambientar();
}

default
{
    state_entry() { escanear(); llSetTimerEvent(TICK); }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if (c & CHANGED_LINK) escanear(); }

    link_message(integer s, integer num, string str, key id)
    {
        if (num == 9001) escanear();
        else if (num == 9200) { AMBIENTE = str; ambientar(); }
        else if (num == 9100)
        {
            // corriente de aire desde una reja: los fuegos cercanos se tumban
            list p = llParseString2List(str, ["|"], []);
            string tag = llList2String(p, 1);
            integer l = link_de(tag + "_Puerta");
            if (tag == "G") l = link_de("G_Hoja_O");
            if (tag == "R") l = link_de("G_Rastrillo");
            if (l < 0) return;
            vector o = llList2Vector(llGetLinkPrimitiveParams(l, [PRIM_POS_LOCAL]), 0);
            integer i;
            for (i = 0; i < llGetListLength(F_LINK); ++i)
            {
                vector fp = llList2Vector(F_POS, i);
                if (llVecDist(fp, o) < 8.0)
                {
                    vector v = llVecNorm(fp - o) * 1.2;
                    F_RACHA = llListReplaceList(F_RACHA, [18 + (integer)llFrand(10)], i, i);
                    llLinkParticleSystem(llList2Integer(F_LINK, i), llama(llList2Integer(F_TIPO, i), v.x, v.y, FALSE));
                }
            }
        }
        else if (num == 9300)
        {
            string donde = "";
            if (str == "ropa") donde = "C05_Techo";
            else if (str == "chapuzon") donde = "C04_Agua";
            else if (str == "marca") donde = "C01_Brasero_Marcar";
            else if (str == "azote") donde = "C08_Mastil";
            integer l = link_de(donde);
            if (l > 0)
            {
                llLinkParticleSystem(l, rafaga(str));
                llSleep(2.0);
                if (donde == "C01_Brasero_Marcar") llLinkParticleSystem(l, llama(2, 0, 0, FALSE));
                else if (donde == "C04_Agua") ambientar();
                else llLinkParticleSystem(l, []);
            }
        }
    }

    timer()
    {
        integer n = llGetListLength(F_LINK);
        if (n == 0) return;
        integer j;
        for (j = 0; j < POR_TICK; ++j)
        {
            cursor = (cursor + 1) % n;
            integer i = cursor;
            integer tipo = llList2Integer(F_TIPO, i);
            if (AMBIENTE == "TINIEBLAS" && tipo != 2) jump siguiente;
            // ruido suave: paseo aleatorio amortiguado hacia 1
            float nivel = llList2Float(F_NIVEL, i);
            float vel = llList2Float(F_VEL, i) * 0.6 + (llFrand(0.3) - 0.15) + (1.0 - nivel) * 0.25;
            nivel += vel * 0.5;
            integer racha = llList2Integer(F_RACHA, i);
            if (racha > 0)
            {
                nivel = 0.35 + llFrand(0.5);
                --racha;
                if (racha == 0) llLinkParticleSystem(llList2Integer(F_LINK, i), llama(tipo, 0, 0, FALSE));
            }
            float azar = llFrand(1.0);
            if (azar < 0.012)          // chasquido: destello y chispas
            {
                nivel = 1.45;
                llLinkParticleSystem(llList2Integer(F_LINK, i), llama(tipo, 0, 0, TRUE));
                racha = 2;
            }
            else if (azar < 0.02) nivel = 0.4;   // boqueada
            // braseros: cada pocos segundos el sistema pasa de llama a humo y vuelve
            if (tipo == 2 && racha == 0 && TEXTURA_HUMO != "")
            {
                float th = llList2Float(F_HUMO, i);
                float ahora = llGetTime();
                if (th > 0.0 && ahora > th)
                {
                    llLinkParticleSystem(llList2Integer(F_LINK, i), humo());
                    th = -(ahora + 2.5 + llFrand(2.5));
                }
                else if (th < 0.0 && ahora > -th)
                {
                    llLinkParticleSystem(llList2Integer(F_LINK, i), llama(tipo, 0, 0, FALSE));
                    th = ahora + 3.0 + llFrand(5.0);
                }
                F_HUMO = llListReplaceList(F_HUMO, [th], i, i);
            }
            if (nivel < 0.3) nivel = 0.3;
            if (nivel > 1.5) nivel = 1.5;
            F_NIVEL = llListReplaceList(F_NIVEL, [nivel], i, i);
            F_VEL = llListReplaceList(F_VEL, [vel], i, i);
            F_RACHA = llListReplaceList(F_RACHA, [racha], i, i);
            float base = 0.75; float radio = 6.0;
            if (tipo == 1) { base = 0.5; radio = 4.5; }
            if (tipo == 2) { base = 1.0; radio = 10.0; if (AMBIENTE == "JUICIO") base = 1.6; }
            float k = K_LUZ; if (tipo == 2 && AMBIENTE == "TINIEBLAS") k = 0.7;
            vector col = TINTE + <0.0, (nivel - 1.0) * 0.12, (nivel - 1.0) * 0.05>;
            llSetLinkPrimitiveParamsFast(llList2Integer(F_LINK, i), [
                PRIM_POINT_LIGHT, TRUE, col, base * k * nivel, radio * K_RADIO * (0.9 + 0.1 * nivel), 1.4,
                PRIM_GLOW, 7, 0.12 + 0.2 * nivel]);
            @siguiente;
        }
    }
}

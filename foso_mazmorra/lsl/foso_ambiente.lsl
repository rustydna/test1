// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_ambiente.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - VOCES Y MAREA (en la raíz, opcional)
//  * Marea: el agua del canal sube y baja unos centímetros a lo largo de
//    PERIODO segundos, como si el mar respirara bajo la fortaleza.
//  * Voces del Foso: cuando hay gente cerca, de vez en cuando se oye algo
//    en la oscuridad (susurros, cadenas, un grito lejano...). Solo texto;
//    puedes añadir sonidos en SONIDOS (UUID) para que suenen a la vez.
// =====================================================================

float PERIODO = 600.0;       // segundos de una marea completa
float AMPLITUD = 0.035;      // metros
float VOZ_MIN = 150.0;       // segundos entre voces (mínimo y máximo)
float VOZ_MAX = 420.0;
list SONIDOS = [];           // UUID de sonidos ambientales opcionales

list VOCES = [
    "Algo arrastra una cadena en la oscuridad del fondo. Luego, silencio.",
    "Desde La Cisterna llega el gorgoteo del agua... y algo que parece una tos.",
    "Una gota helada cae de la bóveda justo en la nuca.",
    "En Las Jaulas, la jaula del esqueleto gira sola, chirriando, aunque no corre el aire.",
    "Alguien susurra un número de recluta. Nadie lo ha dicho.",
    "Las antorchas se inclinan a la vez, como si algo hubiera pasado por el patio.",
    "Lejos, tras los muros, rompe una ola contra la roca. Todo el Foso tiembla un instante.",
    "Las ratas se callan de golpe.",
    "Del canal sube un olor a sal, a podredumbre y a hierro.",
    "Se oye un golpe seco en La Perrera, y después una risa ahogada.",
    "Una calavera rueda sola en Las Jaulas y se detiene mirándote.",
    "El rastrillo cruje en su ranura, como si alguien probara a levantarlo desde fuera.",
    "Por un instante, la niebla del canal dibuja la silueta de un hombre de rodillas.",
    "Las cadenas del ajusticiado de la primera viga tintinean. No hay viento.",
    "Un perro ladra en La Perrera. Ningún perro de verdad vive aquí.",
    "Alguien ha grabado en la piedra, junto a una reja: NO MIRES AL TRONO."];

integer link_agua;
float t0;
vector base;
float proxima;

integer link_de(string nombre)
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer i;
    for (i = 1; i <= n; ++i) if (llGetLinkName(i) == nombre) return i;
    return -1;
}

default
{
    state_entry()
    {
        link_agua = link_de("P_Agua");
        if (link_agua > 1) base = llList2Vector(llGetLinkPrimitiveParams(link_agua, [PRIM_POS_LOCAL]), 0);
        t0 = llGetTime();
        proxima = VOZ_MIN + llFrand(VOZ_MAX - VOZ_MIN);
        llSetTimerEvent(8.0);
    }
    on_rez(integer p) { llResetScript(); }
    link_message(integer s, integer n, string str, key id) { if (n == 9001) llResetScript(); }
    timer()
    {
        float t = llGetTime() - t0;
        if (link_agua > 1)
            llSetLinkPrimitiveParamsFast(link_agua, [PRIM_POS_LOCAL,
                base + <0.0, 0.0, AMPLITUD * llSin(TWO_PI * t / PERIODO)>]);
        if (t > proxima)
        {
            proxima = t + VOZ_MIN + llFrand(VOZ_MAX - VOZ_MIN);
            if (llGetListLength(llGetAgentList(AGENT_LIST_PARCEL, [])) > 0)
            {
                string antes = llGetObjectName();
                llSetObjectName("En la oscuridad");
                llSay(0, llList2String(VOCES, (integer)llFrand(llGetListLength(VOCES))));
                llSetObjectName(antes);
                if (SONIDOS != []) llTriggerSound(llList2String(SONIDOS, (integer)llFrand(llGetListLength(SONIDOS))), 0.6);
            }
        }
    }
}

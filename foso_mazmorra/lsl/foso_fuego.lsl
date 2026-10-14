// =====================================================================
//  EL FOSO V2 - parpadeo del fuego (opcional)
//  Un solo script en la raíz. Cada pocos instantes cambia la intensidad de
//  algunas luces al azar, sin saturar el simulador.
//  Requiere haber pasado antes foso_configurar.lsl (que enciende las luces).
// =====================================================================

float INTERVALO = 0.25;
integer POR_TICK = 4;
list FUEGOS;   // enlace, radio base, intensidad base

default
{
    state_entry()
    {
        FUEGOS = [];
        integer n = llGetNumberOfPrims();
        integer i;
        for (i = 1; i <= n; ++i)
        {
            string nombre = llGetLinkName(i);
            if (llSubStringIndex(nombre, "Antorcha") != -1 || llSubStringIndex(nombre, "_Farol") != -1
                || nombre == "N_Brasero")
            {
                float r = 6.0; float k = 0.8;
                if (nombre == "N_Brasero") { r = 12.0; k = 1.0; }
                else if (llSubStringIndex(nombre, "_Farol") != -1) { r = 5.0; k = 0.6; }
                FUEGOS += [i, r, k];
            }
        }
        if (FUEGOS != []) llSetTimerEvent(INTERVALO);
    }

    changed(integer c) { if (c & CHANGED_LINK) llResetScript(); }

    timer()
    {
        integer total = llGetListLength(FUEGOS) / 3;
        integer j;
        for (j = 0; j < POR_TICK; ++j)
        {
            integer b = (integer)llFrand(total) * 3;
            integer link = llList2Integer(FUEGOS, b);
            float r = llList2Float(FUEGOS, b + 1);
            float k = llList2Float(FUEGOS, b + 2);
            float f = 0.75 + llFrand(0.3);
            llSetLinkPrimitiveParamsFast(link, [
                PRIM_POINT_LIGHT, TRUE, <1.0, 0.5 + llFrand(0.1), 0.22>, k * f, r * (0.92 + llFrand(0.1)), 1.2,
                PRIM_GLOW, 0, 0.25 + llFrand(0.15)]);
        }
    }
}

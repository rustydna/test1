// =====================================================================
//  EL FOSO V2 - configuración en un solo paso
//  Ponlo en el contenido del objeto raíz (el edificio entero enlazado).
//  Se ejecuta una vez y se borra solo.
//
//  1. Tipo de física de cada pieza (es lo que arregla entrar en las celdas):
//       estructura (muros, frentes, suelos, bóvedas, torres)  -> Prim
//       puertas, hojas del portón, rastrillo                  -> Convex Hull
//       decoración (rejas, cadenas, paja, antorchas, faroles) -> None
//     Las rejas van a None porque su física está en la pieza _Frente
//     (una losa fina justo en el plano de los barrotes).
//  2. Fuego: la cara 0 de antorchas, faroles y brasero es la llama:
//     brillo propio, glow y luz puntual.
// =====================================================================

integer is_deco(string n)
{
    list tails = ["_Reja", "_Cadena", "_Paja", "_Comedero", "_Viga", "_Farol"];
    integer i;
    for (i = 0; i < llGetListLength(tails); ++i)
    {
        string t = llList2String(tails, i);
        integer p = llSubStringIndex(n, t);
        if (p != -1 && p == llStringLength(n) - llStringLength(t)) return TRUE;
    }
    if (llSubStringIndex(n, "Antorcha") != -1) return TRUE;
    if (n == "N_Brasero" || n == "N_Argollas" || n == "N_Pacas" || n == "N_Barriles") return TRUE;
    return FALSE;
}

integer is_mobile(string n)
{
    return llSubStringIndex(n, "_Puerta") != -1 || llSubStringIndex(n, "G_Hoja") == 0
        || n == "G_Rastrillo";
}

integer has_fire(string n)
{
    return llSubStringIndex(n, "Antorcha") != -1 || llSubStringIndex(n, "_Farol") != -1
        || n == "N_Brasero";
}

default
{
    state_entry()
    {
        integer n = llGetNumberOfPrims();
        integer prim = 0; integer hull = 0; integer none = 0; integer fire = 0; integer unknown = 0;
        integer link;
        for (link = 1; link <= n; ++link)
        {
            string name = llGetLinkName(link);
            integer shape = PRIM_PHYSICS_SHAPE_PRIM;
            if (is_deco(name)) shape = PRIM_PHYSICS_SHAPE_NONE;
            else if (is_mobile(name)) shape = PRIM_PHYSICS_SHAPE_CONVEX;
            else if (llSubStringIndex(name, "_") == -1) ++unknown;

            // la raíz no admite None: se queda en Convex Hull
            if (link == 1 && shape == PRIM_PHYSICS_SHAPE_NONE) shape = PRIM_PHYSICS_SHAPE_CONVEX;
            llSetLinkPrimitiveParamsFast(link, [PRIM_PHYSICS_SHAPE_TYPE, shape]);
            if (shape == PRIM_PHYSICS_SHAPE_PRIM) ++prim;
            else if (shape == PRIM_PHYSICS_SHAPE_CONVEX) ++hull;
            else ++none;

            if (has_fire(name))
            {
                float radius = 6.0;
                float intensity = 0.8;
                if (name == "N_Brasero") { radius = 12.0; intensity = 1.0; }
                else if (llSubStringIndex(name, "_Farol") != -1) { radius = 5.0; intensity = 0.6; }
                llSetLinkPrimitiveParamsFast(link, [
                    PRIM_COLOR, 0, <1.0, 0.62, 0.28>, 1.0,
                    PRIM_FULLBRIGHT, 0, TRUE,
                    PRIM_GLOW, 0, 0.35,
                    PRIM_POINT_LIGHT, TRUE, <1.0, 0.55, 0.25>, intensity, radius, 1.2]);
                ++fire;
            }
        }
        llOwnerSay("Foso V2 configurado: " + (string)n + " piezas. Física Prim " + (string)prim
            + ", Convex " + (string)hull + ", None " + (string)none + ". Fuegos: " + (string)fire + ".");
        if (unknown > n / 2)
            llOwnerSay("AVISO: muchas piezas no tienen el nombre del modelo (C01_Frente, G_Arco...). "
                + "Revisa que la subida haya conservado los nombres; si no, asigna la física a mano.");
        llOwnerSay("Comprueba la física con Develop > Render Metadata > Physics Shapes.");
        llRemoveInventory(llGetScriptName());
    }
}

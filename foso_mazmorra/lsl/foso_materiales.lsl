// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_materiales.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - MATERIALES PBR POR BLOQUES (en la raíz)
//
//  Todas las piezas tienen las mismas caras en el mismo orden:
//    0 Piedra · 1 Suelo · 2 Madera · 3 Hierro · 4 Tela (y cuero)
//    5 Hueso  · 6 Paja  · 7 Llama
//  y el agua va en sus propias piezas (P_Agua, C04_Agua).
//
//  1. Mete en el contenido de la raíz tus materiales PBR (los que creas en
//     Build > Upload > Material, o los que compres) y una nota llamada
//     "materiales" con líneas así (nombre del material o su UUID):
//         Piedra = Mi piedra húmeda
//         Suelo = Losas viejas
//         Madera = Roble podrido
//         Hierro = Hierro forjado oxidado
//         Tela = Lino sucio
//         Hueso = Hueso viejo
//         Paja = Paja seca
//         Agua = Agua de mar
//  2. Toca la raíz (dueño): se aplica cada material a TODAS sus caras del
//     edificio de una vez. Vuelve a tocar tras cambiar la nota.
//  (La cara 7, la llama, la gestiona el script del fuego: no le pongas PBR.)
// =====================================================================

list CARAS = ["Piedra", "Suelo", "Madera", "Hierro", "Tela", "Hueso", "Paja", "Llama"];
list ASIGNA;   // [bloque, material]
key Q; integer LINEA;

aplicar()
{
    integer n = llGetObjectPrimCount(llGetKey());
    integer link; integer hechos = 0;
    for (link = 1; link <= n; ++link)
    {
        string nm = llGetLinkName(link);
        list reglas = [];
        if (llSubStringIndex(nm, "_Agua") != -1)
        {
            integer j = llListFindList(ASIGNA, ["Agua"]);
            if (j != -1) reglas = [PRIM_RENDER_MATERIAL, ALL_SIDES, llList2String(ASIGNA, j + 1)];
        }
        else
        {
            integer c;
            for (c = 0; c < 7; ++c)
            {
                integer j = llListFindList(ASIGNA, [llList2String(CARAS, c)]);
                if (j != -1) reglas += [PRIM_RENDER_MATERIAL, c, llList2String(ASIGNA, j + 1)];
            }
        }
        if (reglas != []) { llSetLinkPrimitiveParamsFast(link, reglas); ++hechos; }
    }
    llOwnerSay("Materiales aplicados en " + (string)hechos + " piezas.");
}

default
{
    touch_start(integer t)
    {
        if (llDetectedKey(0) != llGetOwner() || llDetectedLinkNumber(0) != 1) return;
        if (llGetInventoryType("materiales") != INVENTORY_NOTECARD) { llOwnerSay("Falta la nota \"materiales\"."); return; }
        ASIGNA = []; LINEA = 0;
        Q = llGetNotecardLine("materiales", LINEA);
    }
    dataserver(key id, string d)
    {
        if (id != Q) return;
        if (d == EOF) { aplicar(); return; }
        list p = llParseString2List(d, ["="], []);
        if (llGetListLength(p) == 2)
            ASIGNA += [llStringTrim(llList2String(p, 0), STRING_TRIM), llStringTrim(llList2String(p, 1), STRING_TRIM)];
        Q = llGetNotecardLine("materiales", ++LINEA);
    }
}

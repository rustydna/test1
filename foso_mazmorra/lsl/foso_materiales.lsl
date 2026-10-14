// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_materiales.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - MATERIALES PBR POR BLOQUES (en la raíz)
//
//  Todas las piezas tienen las mismas caras en el mismo orden:
//    0 Piedra · 1 Suelo · 2 Madera · 3 Hierro · 4 Tela (y cuero)
//    5 Hueso  · 6 Paja  · 7 Llama
//  y el agua va en sus propias piezas (P_Agua, C04_Agua).
//
//  USO: mete los materiales PBR en el contenido del edificio (pestaña
//  Contenido, la misma donde están los scripts). Se aplican SOLOS al
//  instante, sin tocar nada:
//    * Si hay una nota llamada "materiales", manda la nota:
//          Piedra = nombre del material en el inventario (o su UUID)
//    * Si no hay nota, cada material se asigna por su nombre: el que
//      contenga "piedra" va a la piedra, el que contenga "hierro" al
//      hierro, etc. (da igual mayúsculas o minúsculas). Con los .glb del
//      Foso (Piedra, Suelo, Madera, Hierro, Tela, Hueso, Paja, Agua) no
//      hace falta nota.
//  Para repetirlo: escribe en el chat  /7 materiales
//  La cara 7 (llama) la gestiona el script del fuego: no le pongas PBR.
// =====================================================================

list BLOQUES = ["Piedra", "Suelo", "Madera", "Hierro", "Tela", "Hueso", "Paja", "Agua"];
list ASIGNA;   // [bloque, material]
key Q; integer LINEA;

// tipos de inventario que NO son materiales (el resto se considera material)
integer no_es_material(integer t)
{
    return t == INVENTORY_SCRIPT || t == INVENTORY_NOTECARD || t == INVENTORY_TEXTURE
        || t == INVENTORY_ANIMATION || t == INVENTORY_SOUND || t == INVENTORY_OBJECT
        || t == INVENTORY_LANDMARK || t == INVENTORY_CLOTHING || t == INVENTORY_BODYPART
        || t == INVENTORY_GESTURE || t == INVENTORY_SETTING || t == INVENTORY_NONE;
}

por_nombre()
{
    // asigna cada bloque al primer material cuyo nombre contenga el nombre del bloque
    ASIGNA = [];
    integer n = llGetInventoryNumber(INVENTORY_ALL);
    integer b;
    for (b = 0; b < llGetListLength(BLOQUES); ++b)
    {
        string bloque = llList2String(BLOQUES, b);
        integer i;
        for (i = 0; i < n; ++i)
        {
            string it = llGetInventoryName(INVENTORY_ALL, i);
            if (!no_es_material(llGetInventoryType(it))
                && llSubStringIndex(llToLower(it), llToLower(bloque)) != -1
                && llListFindList(ASIGNA, [bloque]) == -1)
                ASIGNA += [bloque, it];
        }
    }
    aplicar();
}

empezar()
{
    if (llGetInventoryType("materiales") == INVENTORY_NOTECARD)
    {
        ASIGNA = []; LINEA = 0;
        Q = llGetNotecardLine("materiales", LINEA);
    }
    else por_nombre();
}

aplicar()
{
    if (ASIGNA == [])
    {
        llOwnerSay("Materiales: no encuentro ninguno. Mete los materiales PBR (Piedra, Suelo, Madera, Hierro, "
            + "Tela, Hueso, Paja, Agua) en la pestaña Contenido del edificio.");
        return;
    }
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
                integer j = llListFindList(ASIGNA, [llList2String(BLOQUES, c)]);
                if (j != -1) reglas += [PRIM_RENDER_MATERIAL, c, llList2String(ASIGNA, j + 1)];
            }
        }
        if (reglas != []) { llSetLinkPrimitiveParamsFast(link, reglas); ++hechos; }
    }
    string resumen = "";
    integer b;
    for (b = 0; b < llGetListLength(BLOQUES); ++b)
    {
        string bloque = llList2String(BLOQUES, b);
        integer j = llListFindList(ASIGNA, [bloque]);
        if (j == -1) resumen += bloque + ": FALTA  ";
        else resumen += bloque + " = " + llList2String(ASIGNA, j + 1) + "  ";
    }
    llOwnerSay("Materiales aplicados en " + (string)hechos + " piezas. " + resumen);
}

default
{
    state_entry()
    {
        llListen(7, "", llGetOwner(), "materiales");
        empezar();
    }
    on_rez(integer p) { llResetScript(); }
    changed(integer c) { if (c & CHANGED_INVENTORY) empezar(); }
    listen(integer c, string n, key id, string m) { empezar(); }
    dataserver(key id, string d)
    {
        if (id != Q) return;
        if (d == EOF)
        {
            if (ASIGNA == []) por_nombre(); else aplicar();
            return;
        }
        list p = llParseString2List(d, ["="], []);
        if (llGetListLength(p) == 2)
            ASIGNA += [llStringTrim(llList2String(p, 0), STRING_TRIM), llStringTrim(llList2String(p, 1), STRING_TRIM)];
        Q = llGetNotecardLine("materiales", ++LINEA);
    }
}

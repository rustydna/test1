// GENERADO por scripts/build_foso.py a partir de lsl/plantillas/foso_pose.lsl (no editar a mano)
// =====================================================================
//  EL FOSO V3 - POSE (pon 6 u 8 copias en la raíz; SL las numera solas)
//  Anima a un avatar sentado. Lo gestiona foso_asientos.
// =====================================================================
key AV; string ANIM;

default
{
    link_message(integer s, integer n, string str, key id)
    {
        if (n == 9500)
        {
            list p = llParseString2List(str, ["|"], []);
            if (llList2String(p, 0) != llGetScriptName()) return;
            AV = id; ANIM = llList2String(p, 1);
            llRequestPermissions(AV, PERMISSION_TRIGGER_ANIMATION);
        }
        else if (n == 9501 && str == llGetScriptName())
        {
            if (llGetPermissions() & PERMISSION_TRIGGER_ANIMATION && llGetPermissionsKey() == AV)
                llStopAnimation(ANIM);
            AV = NULL_KEY;
        }
    }
    run_time_permissions(integer p)
    {
        if (p & PERMISSION_TRIGGER_ANIMATION)
        {
            llStopAnimation("sit");
            llStartAnimation(ANIM);
        }
    }
}

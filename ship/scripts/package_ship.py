"""Packs the Second Bride for Second Life: ship/Bride_SL_A_model_and_script.zip, ship/Bride_SL_B_bulk_upload.zip."""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")


def main():
    a = os.path.join(ROOT, "Bride_SL_A_model_and_script.zip")
    with zipfile.ZipFile(a, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, "INSTALL.txt"), "INSTALL.txt")
        for fn in sorted(os.listdir(os.path.join(OUT, "models"))):
            if fn.endswith(".dae"):
                z.write(os.path.join(OUT, "models", fn), "1_model/" + fn)
        z.write(os.path.join(ROOT, "lsl", "bride_main.lsl"), "3_script/bride_main.lsl")
    b = os.path.join(ROOT, "Bride_SL_B_bulk_upload.zip")
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for sub, ext in (("pbr_materials", ".glb"), ("sounds", ".wav"), ("animations", ".anim")):
            folder = os.path.join(OUT, sub)
            for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                if fn.endswith(ext) and fn.startswith("bride_"):
                    z.write(os.path.join(folder, fn), "2_bulk_upload/" + fn)
    for p in (a, b):
        print(p, round(os.path.getsize(p) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()

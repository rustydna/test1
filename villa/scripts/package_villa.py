"""Packs the Villa for Second Life:  villa/Villa_SL_A_models_and_scripts.zip and
villa/Villa_SL_B_bulk_upload.zip (unzip both into the same folder; see INSTALL.txt)."""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")


def main():
    a = os.path.join(ROOT, "Villa_SL_A_models_and_scripts.zip")
    with zipfile.ZipFile(a, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, "INSTALL.txt"), "INSTALL.txt")
        for fn in sorted(os.listdir(os.path.join(OUT, "models"))):
            if fn.endswith(".dae"):
                z.write(os.path.join(OUT, "models", fn), "1_models/" + fn)
        for fn in ("villa_core.lsl", "villa_house.lsl"):
            z.write(os.path.join(ROOT, "lsl", fn), "3_scripts/" + fn)
    b = os.path.join(ROOT, "Villa_SL_B_bulk_upload.zip")
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for sub, ext in (("pbr_materials", ".glb"), ("sounds", ".wav"), ("animations", ".anim")):
            for fn in sorted(os.listdir(os.path.join(OUT, sub))):
                if fn.endswith(ext) and fn.startswith("villa_"):
                    z.write(os.path.join(OUT, sub, fn), "2_bulk_upload/" + fn)
    for p in (a, b):
        print(p, round(os.path.getsize(p) / 1e6, 1), "MB")


if __name__ == "__main__":
    main()

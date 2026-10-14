"""Packs everything Second Life needs, laid out in upload order, in two zips (each under the
30 MB limit of most file transfers):

    python the_pit/scripts/package_sl.py
      ->  the_pit/ThePit_SL_A_model_and_scripts.zip   (INSTALL.txt, 1_model/, 3_scripts/)
      ->  the_pit/ThePit_SL_B_bulk_upload.zip         (2_bulk_upload/)
      ->  the_pit/ThePit_SL_C_poses_only.zip          (just the 12 pose animations)
Unzip both into the same folder.
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
LSL = os.path.join(ROOT, "lsl")


def main():
    a = os.path.join(ROOT, "ThePit_SL_A_model_and_scripts.zip")
    with zipfile.ZipFile(a, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, "INSTALL.txt"), "INSTALL.txt")
        for fn in ["ThePit.dae", "ThePit_LOD2.dae", "ThePit_LOD1.dae", "ThePit_LOD0.dae", "ThePit_PHYS.dae"]:
            z.write(os.path.join(OUT, fn), "1_model/" + fn)
        for fn in sorted(os.listdir(LSL)):
            if fn.endswith(".lsl") or fn.endswith(".txt"):
                z.write(os.path.join(LSL, fn), "3_scripts/" + fn)
    b = os.path.join(ROOT, "ThePit_SL_B_bulk_upload.zip")
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for sub, ext in (("pbr_materials", ".glb"), ("effects", ".png"), ("animations", ".anim")):
            for fn in sorted(os.listdir(os.path.join(OUT, sub))):
                if fn.endswith(ext):
                    z.write(os.path.join(OUT, sub, fn), "2_bulk_upload/" + fn)
    c = os.path.join(ROOT, "ThePit_SL_C_poses_only.zip")
    with zipfile.ZipFile(c, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(os.path.join(OUT, "animations"))):
            if fn.endswith(".anim"):
                z.write(os.path.join(OUT, "animations", fn), "poses/" + fn)
    print(a)
    print(b)
    print(c)


if __name__ == "__main__":
    main()

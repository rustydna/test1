"""Packs everything Second Life needs into one zip, laid out in upload order.

    python the_pit/scripts/package_sl.py   ->  the_pit/ThePit_SecondLife.zip
"""

import os
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
LSL = os.path.join(ROOT, "lsl")


def main():
    target = os.path.join(ROOT, "ThePit_SecondLife.zip")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, "INSTALL.txt"), "INSTALL.txt")
        for fn in ["ThePit.dae", "ThePit_LOD2.dae", "ThePit_LOD1.dae", "ThePit_LOD0.dae", "ThePit_PHYS.dae"]:
            z.write(os.path.join(OUT, fn), "1_model/" + fn)
        for sub, ext in (("pbr_materials", ".glb"), ("effects", ".png")):
            for fn in sorted(os.listdir(os.path.join(OUT, sub))):
                if fn.endswith(ext):
                    z.write(os.path.join(OUT, sub, fn), "2_bulk_upload/" + fn)
        for fn in sorted(os.listdir(LSL)):
            if fn.endswith(".lsl") or fn.endswith(".txt"):
                z.write(os.path.join(LSL, fn), "3_scripts/" + fn)
    print(target)


if __name__ == "__main__":
    main()

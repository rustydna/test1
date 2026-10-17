"""Packs everything Second Life needs, laid out in upload order, in two zips (each under the
30 MB limit of most file transfers):

    python the_pit/scripts/package_sl.py
      ->  the_pit/ThePit_SL_A_model_and_scripts.zip   (INSTALL.txt, 1_model/, 3_scripts/)
      ->  the_pit/ThePit_SL_B_bulk_upload.zip         (2_bulk_upload/)
      ->  the_pit/ThePit_SL_C_poses_only.zip          (just the 12 pose animations)
Unzip both into the same folder.
"""

import json
import os
import struct
import zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "output")
LSL = os.path.join(ROOT, "lsl")


def renamed_glb(path, name):
    """The .glb with its material renamed (Second Life names the uploaded material after it)."""
    data = open(path, "rb").read()
    magic, version, _ = struct.unpack_from("<III", data, 0)
    jlen, jtype = struct.unpack_from("<II", data, 12)
    doc = json.loads(data[20:20 + jlen])
    for m in doc.get("materials", []):
        m["name"] = name
    j = json.dumps(doc, separators=(",", ":")).encode()
    j += b" " * (-len(j) % 4)
    rest = data[20 + jlen:]
    body = struct.pack("<II", len(j), jtype) + j + rest
    return struct.pack("<III", magic, version, 12 + len(body)) + body


def main():
    a = os.path.join(ROOT, "ThePit_SL_A_model_and_scripts.zip")
    with zipfile.ZipFile(a, "w", zipfile.ZIP_DEFLATED) as z:
        z.write(os.path.join(ROOT, "INSTALL.txt"), "INSTALL.txt")
        for fn in ["ThePit.dae", "ThePit_LOD2.dae", "ThePit_LOD1.dae", "ThePit_LOD0.dae", "ThePit_PHYS.dae"]:
            z.write(os.path.join(OUT, fn), "1_model/" + fn)
        for fn in sorted(os.listdir(LSL)):
            if fn.endswith(".lsl") or fn.endswith(".txt"):
                z.write(os.path.join(LSL, fn), "3_scripts/" + fn)
    # every uploaded item is called pit_...: in SL, search "pit_" in the inventory, select all, drag once
    b = os.path.join(ROOT, "ThePit_SL_B_bulk_upload.zip")
    with zipfile.ZipFile(b, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in sorted(os.listdir(os.path.join(OUT, "pbr_materials"))):
            if fn.endswith(".glb"):
                name = "pit_" + fn[:-4].lower()
                z.writestr("2_bulk_upload/" + name + ".glb", renamed_glb(os.path.join(OUT, "pbr_materials", fn), name))
        for sub, ext in (("effects", ".png"), ("animations", ".anim"), ("sounds", ".wav")):
            folder = os.path.join(OUT, sub)
            for fn in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
                if fn.endswith(ext):
                    z.write(os.path.join(folder, fn), "2_bulk_upload/" + (fn if fn.startswith("pit_") else "pit_" + fn))
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

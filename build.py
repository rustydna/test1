"""Genera los dos paquetes de venta en dist/.

  python build.py

* Founder Edition  — Blender 3.5 o superior (complemento clásico, sin manifest).
* Standard Edition — Blender 4.2 o superior (extensión con blender_manifest.toml).
"""

import pathlib
import re
import zipfile

ROOT = pathlib.Path(__file__).parent
SRC = ROOT / "sl_rigger"
DIST = ROOT / "dist"

EDITIONS = {
    "FOUNDER": {"blender": "(3, 5, 0)", "manifest": False},
    "STANDARD": {"blender": "(4, 2, 0)", "manifest": True},
}


def version():
    m = re.search(r'"version": \((\d+), (\d+), (\d+)\)', (SRC / "__init__.py").read_text(encoding="utf-8"))
    return ".".join(m.groups())


def build(edition):
    cfg = EDITIONS[edition]
    ver = version()
    DIST.mkdir(exist_ok=True)
    out = DIST / f"sl_rigger_{edition.lower()}_{ver}.zip"
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(SRC.rglob("*")):
            if path.is_dir() or "__pycache__" in path.parts or path.suffix == ".pyc":
                continue
            rel = path.relative_to(ROOT).as_posix()
            if path.name == "blender_manifest.toml" and not cfg["manifest"]:
                continue
            text = None
            if path.name == "edition.py":
                text = path.read_text(encoding="utf-8").replace('EDITION = "STANDARD"', f'EDITION = "{edition}"')
            elif path.name == "__init__.py" and path.parent == SRC:
                text = re.sub(r'"blender": \(\d+, \d+, \d+\)', f'"blender": {cfg["blender"]}',
                              path.read_text(encoding="utf-8"))
            elif path.name == "blender_manifest.toml":
                text = re.sub(r'version = ".*?"', f'version = "{ver}"', path.read_text(encoding="utf-8"))
            if text is None:
                zf.write(path, rel)
            else:
                zf.writestr(rel, text)
    return out


if __name__ == "__main__":
    for ed in EDITIONS:
        print(build(ed))

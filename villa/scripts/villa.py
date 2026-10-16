"""Registers every piece of the Villa (site, houses, furniture) with vbuild.

Each house / site module calls vbuild.linkset() and decorates its piece builders with
vbuild.piece(); importing this module imports them all in a fixed order.
"""

import importlib
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

# module names under villa/scripts/ (packages or files); missing ones are skipped while the
# villa is under construction, and listed in MISSING
MODULES = ["site", "houses", "furniture.catalogue"]
MISSING = []

for _m in MODULES:
    try:
        importlib.import_module(_m)
    except ModuleNotFoundError as e:   # only skip the module itself, not errors inside it
        if e.name and (e.name == _m or _m.startswith(e.name + ".") or e.name.startswith(_m)):
            MISSING.append(_m)
        else:
            raise

"""Builds the whole Villa: every linkset -> villa/output/models/<Linkset>*.dae + Report.json.

    python3 villa/scripts/build_villa.py [LINKSET ...] [--save]
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import vbuild as B  # noqa: E402
import villa  # noqa: E402,F401  (registers every piece)


def main():
    only = [a for a in sys.argv[1:] if not a.startswith("--")] or None
    rep = B.build(only=only, export=True, save="--save" in sys.argv)
    path = B.write_report(rep) if not only else B.write_report(rep, os.path.join(B.OUT, "Report_partial.json"))
    print(json.dumps({k: {kk: v[kk] for kk in ("pieces", "li_estimate", "size_m", "triangles_high")}
                      for k, v in rep["linksets"].items()}, indent=1))
    for w in rep["warnings"]:
        print("WARNING:", w)
    if villa.MISSING:
        print("not built yet:", ", ".join(villa.MISSING))
    print(path, f"{rep['seconds']} s")


if __name__ == "__main__":
    main()

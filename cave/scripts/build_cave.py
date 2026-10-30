"""Builds The Cave: cave/output/models/Cave*.dae + Report.json.   python3 cave/scripts/build_cave.py"""

import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import cave  # noqa: E402,F401  (registers every piece)
import vbuild as B  # noqa: E402


def main():
    rep = B.build(export=True)
    path = B.write_report(rep)
    for k, v in rep["linksets"].items():
        print(k, {kk: v[kk] for kk in ("pieces", "li_estimate", "size_m", "triangles_high")})
    for w in rep["warnings"]:
        print("WARNING:", w)
    print(path, rep["seconds"], "s")


if __name__ == "__main__":
    main()

"""Story details of The Pit: small props, carvings, stains and relics added INSIDE existing pieces.

Every module registers decorators with @decorates("PieceName", ...). build_pit.built() calls
decorate(name, lod, g) after each piece is built, so a decorator adds geometry to the piece's
Geo for that LOD (0 HIGH, 1 MEDIUM, 2 LOW, 3 LOWEST; most details only exist in HIGH).

Rules (checked by tests/test_pit.py):
* stay inside the piece's bounding box: the piece size and centre must not change, so the LSL
  piece table (and builds already uploaded) keep working;
* use only the 8 block materials (Stone, Floor, Wood, Iron, Cloth, Bone, Straw, Flame);
* never put anything in a doorway or walkway.
"""

DECOR = {}


def decorates(*names):
    def wrap(fn):
        for n in names:
            DECOR.setdefault(n, []).append(fn)
        return fn
    return wrap


def decorate(name, lod, g):
    for fn in DECOR.get(name, []):
        fn(g, lod)


from . import cells_west, cells_east, yard_gate, throne_hall  # noqa: E402,F401

"""Presets de proporciones para avatares no estándar (gigantes, tinies, furros…).

Cada preset modifica los desplazamientos del esqueleto SL antes de crearlo:
  * scale: escala global.
  * mul:   multiplica por componentes (X delante, Y izquierda, Z arriba) el
           desplazamiento de un hueso respecto a su padre.
  * add:   suma un desplazamiento (en ejes SL; para huesos "Right" se refleja Y).
  * extras: grupos de huesos Bento opcionales ("tail", "ears").

Los avatares con proporciones distintas a las de SL necesitan subirse con
"Include joint positions" marcado.
"""

# Huesos Bento extra. Posiciones aproximadas, con la jerarquía de avatar_skeleton.xml.
BENTO_TAIL = [
    ("mTail1", "mPelvis", (-0.116, 0.0, 0.047)),
    ("mTail2", "mTail1", (-0.197, 0.0, 0.0)),
    ("mTail3", "mTail2", (-0.168, 0.0, 0.0)),
    ("mTail4", "mTail3", (-0.142, 0.0, 0.0)),
    ("mTail5", "mTail4", (-0.112, 0.0, 0.0)),
    ("mTail6", "mTail5", (-0.094, 0.0, 0.0)),
]

BENTO_EARS = [
    ("mFaceRoot", "mHead", (0.025, 0.0, 0.045)),
    ("mFaceEar1Left", "mFaceRoot", (-0.019, 0.060, 0.008)),
    ("mFaceEar2Left", "mFaceEar1Left", (-0.013, 0.0, 0.033)),
    ("mFaceEar1Right", "mFaceRoot", (-0.019, -0.060, 0.008)),
    ("mFaceEar2Right", "mFaceEar1Right", (-0.013, 0.0, 0.033)),
]

EXTRAS = {"tail": BENTO_TAIL, "ears": BENTO_EARS}

_LEGS = ("mKneeLeft", "mKneeRight", "mAnkleLeft", "mAnkleRight")
_ARMS = ("mElbowLeft", "mElbowRight", "mWristLeft", "mWristRight")
_HEAD = ("mHead", "mSkull", "mEyeLeft", "mEyeRight")


def _all(names, value):
    return {n: value for n in names}


PRESETS = {
    "HUMAN": {
        "label": "Humano estándar",
        "description": "Proporciones por defecto de Second Life (~1,9 m)",
    },
    "PETITE": {
        "label": "Petite",
        "description": "Adulto pequeño (~1,5 m), proporciones humanas",
        "scale": 0.8,
    },
    "GIANT": {
        "label": "Gigante",
        "description": "~3 m de alto, hombros algo más anchos",
        "scale": 1.6,
        "mul": {"mCollarLeft": (1, 1.1, 1), "mCollarRight": (1, 1.1, 1)},
    },
    "TITAN": {
        "label": "Titán / kaiju",
        "description": "~5 m de alto, torso y hombros masivos",
        "scale": 2.6,
        "mul": {
            "mCollarLeft": (1, 1.25, 1), "mCollarRight": (1, 1.25, 1),
            "mChest": (1, 1, 1.1), "mNeck": (1, 1, 0.7),
        },
    },
    "MUSCLE": {
        "label": "Musculoso",
        "description": "Culturista / héroe: espalda ancha, cuello corto",
        "scale": 1.15,
        "mul": {
            "mCollarLeft": (1, 1.35, 1), "mCollarRight": (1, 1.35, 1),
            "mShoulderLeft": (1, 1.2, 1), "mShoulderRight": (1, 1.2, 1),
            "mHipLeft": (1, 1.15, 1), "mHipRight": (1, 1.15, 1),
            "mNeck": (1, 1, 0.7),
        },
    },
    "TINY": {
        "label": "Tiny",
        "description": "Avatar diminuto (~0,8 m): cabeza grande, piernas y brazos cortos",
        "scale": 0.45,
        "mul": {
            **_all(_LEGS, (1, 1, 0.7)), **_all(_ARMS, (1, 0.8, 1)),
            "mNeck": (1, 1, 0.6),
            "mEyeLeft": (1.2, 1.5, 1.6), "mEyeRight": (1.2, 1.5, 1.6),
            "mSkull": (1, 1, 1.8), "mHead": (1, 1, 1.4),
        },
        "extras": ["tail", "ears"],
    },
    "FURRY": {
        "label": "Furro antropomorfo",
        "description": "Anthro plantígrado: hocico, cuello algo más largo, cola y orejas",
        "mul": {
            "mNeck": (1, 1, 1.15),
            "mEyeLeft": (1.3, 1.1, 1), "mEyeRight": (1.3, 1.1, 1),
        },
        "extras": ["tail", "ears"],
    },
    "FURRY_DIGI": {
        "label": "Furro digitígrado",
        "description": "Patas de animal: tobillo elevado hacia atrás y pie largo, con cola y orejas",
        "mul": {
            "mNeck": (1, 1, 1.15),
            "mEyeLeft": (1.3, 1.1, 1), "mEyeRight": (1.3, 1.1, 1),
            "mKneeLeft": (1, 1, 0.85), "mKneeRight": (1, 1, 0.85),
            "mAnkleLeft": (4.0, 1, 0.75), "mAnkleRight": (4.0, 1, 0.75),
            "mFootLeft": (0.45, 1, 2.8), "mFootRight": (0.45, 1, 2.8),
            "mToeLeft": (0.6, 1, 1), "mToeRight": (0.6, 1, 1),
        },
        "add": {"mKneeLeft": (0.06, 0, 0), "mKneeRight": (0.06, 0, 0)},
        "extras": ["tail", "ears"],
    },
    "KEMONO": {
        "label": "Kemono / chibi furro",
        "description": "Estilo anime: cabeza grande, torso corto, cola y orejas",
        "scale": 0.85,
        "mul": {
            "mChest": (1, 1, 0.85), "mNeck": (1, 1, 0.6),
            **_all(_LEGS, (1, 1, 0.85)),
            "mEyeLeft": (1.2, 1.4, 1.4), "mEyeRight": (1.2, 1.4, 1.4),
            "mSkull": (1, 1, 1.5),
        },
        "extras": ["tail", "ears"],
    },
}


def enum_items():
    return [(k, v["label"], v["description"]) for k, v in PRESETS.items()]


def apply(bones, preset_key):
    """Devuelve la tabla de huesos con el preset aplicado (y sus huesos extra)."""
    preset = PRESETS.get(preset_key or "HUMAN", PRESETS["HUMAN"])
    present = {b[0] for b in bones}
    out = list(bones)
    for extra in preset.get("extras", []):
        out += [b for b in EXTRAS[extra] if b[0] not in present]
    scale = preset.get("scale", 1.0)
    mul = preset.get("mul", {})
    add = preset.get("add", {})
    result = []
    for name, parent, (x, y, z) in out:
        mx, my, mz = mul.get(name, (1.0, 1.0, 1.0))
        ax, ay, az = add.get(name, (0.0, 0.0, 0.0))
        if "Right" in name:
            ay = -ay
        result.append((name, parent, ((x * mx + ax) * scale, (y * my + ay) * scale, (z * mz + az) * scale)))
    base_foot = _lowest_foot(out)
    return _ground(result, target=None if base_foot is None else base_foot * scale)


def _lowest_foot(bones):
    world = {}
    for name, parent, (x, y, z) in bones:
        world[name] = (world[parent] if parent else 0.0) + z
    feet = [world[n] for n in ("mToeLeft", "mToeRight", "mFootLeft", "mFootRight") if n in world]
    return min(feet) if feet else None


def _ground(bones, target):
    """Mueve mPelvis para que el pie más bajo quede donde lo tendría el esqueleto SL escalado."""
    lowest = _lowest_foot(bones)
    if lowest is None or target is None:
        return bones
    shift = lowest - target
    return [(n, p, (o[0], o[1], o[2] - shift)) if p is None else (n, p, o) for n, p, o in bones]

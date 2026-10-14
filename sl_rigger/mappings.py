"""Tablas para convertir rigs de otros programas a nombres de huesos de Second Life.

Varios huesos de origen pueden apuntar al mismo hueso SL: sus pesos se suman.
"""

import re

_FINGERS = ("Thumb", "Index", "Middle", "Ring", "Pinky")


def _mixamo():
    m = {
        "Hips": "mPelvis",
        "Spine": "mTorso",
        "Spine1": "mChest",
        "Spine2": "mChest",
        "Neck": "mNeck",
        "Head": "mHead",
        "HeadTop_End": "mSkull",
    }
    for side in ("Left", "Right"):
        m.update({
            f"{side}Eye": f"mEye{side}",
            f"{side}Shoulder": f"mCollar{side}",
            f"{side}Arm": f"mShoulder{side}",
            f"{side}ForeArm": f"mElbow{side}",
            f"{side}Hand": f"mWrist{side}",
            f"{side}UpLeg": f"mHip{side}",
            f"{side}Leg": f"mKnee{side}",
            f"{side}Foot": f"mAnkle{side}",
            f"{side}ToeBase": f"mFoot{side}",
            f"{side}Toe_End": f"mToe{side}",
        })
        for f in _FINGERS:
            for i in (1, 2, 3):
                m[f"{side}Hand{f}{i}"] = f"mHand{f}{i}{side}"
    return m


def _unreal():
    m = {
        "pelvis": "mPelvis",
        "spine_01": "mTorso",
        "spine_02": "mChest",
        "spine_03": "mChest",
        "spine_04": "mChest",
        "spine_05": "mChest",
        "neck_01": "mNeck",
        "neck_02": "mNeck",
        "head": "mHead",
    }
    names = {"thumb": "Thumb", "index": "Index", "middle": "Middle", "ring": "Ring", "pinky": "Pinky"}
    for s, side in (("l", "Left"), ("r", "Right")):
        m.update({
            f"clavicle_{s}": f"mCollar{side}",
            f"upperarm_{s}": f"mShoulder{side}",
            f"upperarm_twist_01_{s}": f"mShoulder{side}",
            f"lowerarm_{s}": f"mElbow{side}",
            f"lowerarm_twist_01_{s}": f"mElbow{side}",
            f"hand_{s}": f"mWrist{side}",
            f"thigh_{s}": f"mHip{side}",
            f"thigh_twist_01_{s}": f"mHip{side}",
            f"calf_{s}": f"mKnee{side}",
            f"calf_twist_01_{s}": f"mKnee{side}",
            f"foot_{s}": f"mAnkle{side}",
            f"ball_{s}": f"mFoot{side}",
        })
        for src, dst in names.items():
            for i in (1, 2, 3):
                m[f"{src}_0{i}_{s}"] = f"mHand{dst}{i}{side}"
    return m


def _rigify():
    m = {
        "spine": "mPelvis",
        "spine.001": "mTorso",
        "spine.002": "mChest",
        "spine.003": "mChest",
        "spine.004": "mNeck",
        "spine.005": "mNeck",
        "spine.006": "mHead",
    }
    fingers = {"thumb": "Thumb", "f_index": "Index", "f_middle": "Middle", "f_ring": "Ring", "f_pinky": "Pinky"}
    for s, side in (("L", "Left"), ("R", "Right")):
        m.update({
            f"shoulder.{s}": f"mCollar{side}",
            f"upper_arm.{s}": f"mShoulder{side}",
            f"upper_arm.{s}.001": f"mShoulder{side}",
            f"forearm.{s}": f"mElbow{side}",
            f"forearm.{s}.001": f"mElbow{side}",
            f"hand.{s}": f"mWrist{side}",
            f"thigh.{s}": f"mHip{side}",
            f"thigh.{s}.001": f"mHip{side}",
            f"shin.{s}": f"mKnee{side}",
            f"shin.{s}.001": f"mKnee{side}",
            f"foot.{s}": f"mAnkle{side}",
            f"toe.{s}": f"mFoot{side}",
            f"eye.{s}": f"mEye{side}",
        })
        for src, dst in fingers.items():
            for i in (1, 2, 3):
                m[f"{src}.0{i}.{s}"] = f"mHand{dst}{i}{side}"
    # Rigify añade el prefijo DEF- a los huesos que deforman.
    return {**m, **{f"DEF-{k}": v for k, v in m.items()}}


PRESETS = {
    "MIXAMO": ("Mixamo", _mixamo()),
    "UNREAL": ("Unreal / UE Mannequin", _unreal()),
    "RIGIFY": ("Rigify (DEF-)", _rigify()),
}

_PREFIX = re.compile(r"^.*?:")  # "mixamorig:Hips" -> "Hips"


def normalize_name(name):
    return _PREFIX.sub("", name)


def detect_preset(names):
    """Elige el preset que reconoce más nombres."""
    best, best_hits = None, 0
    for key, (_, table) in PRESETS.items():
        hits = sum(1 for n in names if normalize_name(n) in table)
        if hits > best_hits:
            best, best_hits = key, hits
    return best

#!/usr/bin/env python3
"""
THE PIT - the twelve seat poses (static, looping) for Second Life.

    python the_pit/scripts/poses.py                 # build, verify and render all twelve
    python the_pit/scripts/poses.py --no-render     # files and checks only (bpy not needed)
    python the_pit/scripts/poses.py --only pit_dog,pit_cage

Writes, for every pose named in lsl/pit_throne.lsl (the LSL loads them by inventory name):

    output/animations/<name>.anim           internal SL format: Build > Upload > Bulk takes it as is
    output/animations/<name>.bvh            fallback for Build > Upload > Animation (one by one)
    output/animations/previews/<name>.png   front / left side / 3-4 view of a capsule figure posed
                                            with the rotations READ BACK from the .anim file
    output/animations/poses.json            per pose: pelvis offset, contacts, checks

Facts taken from the viewer source (github.com/secondlife/viewer, branch main):

* .anim = LLKeyframeMotion::serialize() through LLDataPackerBinaryBuffer: little endian,
  strings NUL-terminated.  U16 version=1, U16 sub_version=0, S32 base_priority, F32 duration,
  string emote_name, F32 loop_in_point, F32 loop_out_point, S32 loop, F32 ease_in_duration,
  F32 ease_out_duration, U32 hand_pose, U32 num_joints, then per joint: string joint_name,
  S32 joint_priority, S32 num_rot_keys, keys of {U16 time, U16 x, U16 y, U16 z}, S32 num_pos_keys,
  keys of {U16 time, U16 x, U16 y, U16 z}; finally S32 num_constraints.
  time is quantised over [0, duration]; a rotation is the x,y,z of the unit quaternion with w >= 0
  (LLQuaternion::packToVector3) quantised over [-1, 1]; a position over
  [-LL_MAX_PELVIS_OFFSET, +LL_MAX_PELVIS_OFFSET] = [-5, 5] m.  F32_to_U16 / U16_to_F32 from
  llquantize.h (65535 steps; decoded values closer to 0 than one step read as 0).
* Rotations are joint-local, in the avatar frame X forward, Y left, Z up.  Every joint of
  avatar_skeleton.xml has rot="0 0 0", so the rest pose (arms straight out, palms down, legs
  straight down) is the identity and a key is the joint's rotation relative to its parent.
  Child position = parent position + parent world rotation * pos (pos from avatar_skeleton.xml).
* The pelvis position key is an offset from the avatar root: LLPelvisFixMotion holds mPelvis at
  (0,0,0) at LOW priority, so (0,0,0) = default height and (0,0,-0.5) = half a metre lower.
* Joint priority 4 = HIGHEST_PRIORITY; >= 7 (ADDITIVE) is clamped by deserialize().
* hand_pose: 1 = HAND_POSE_RELAXED, 3 = HAND_POSE_FIST, 9 = HAND_POSE_FIST_R (llhandmotion.h).
* BVH (llbvhloader.cpp): frame 0 is only a reference and is not played; the last frame only
  sets what the one before blends to (duration = (frames - 2) * frame time).  Joint names are the
  skeleton aliases (hip, abdomen, chest, neck, head, lCollar, lShldr, lForeArm, lHand, rCollar...,
  lThigh, lShin, lFoot, rThigh, rShin, rFoot).  BVH axes map to SL as X->Y(left), Y->Z(up),
  Z->X(forward); each joint's key is used as is (frame 0 is subtracted only for the hip), so with
  a zero T-pose frame 0 the BVH rotations equal the .anim ones.  Hip translation is in inches,
  relative to frame 0.  A joint whose keys never differ from frame 0 is dropped by the loader:
  every pose therefore moves every joint by at least a small angle.
* Build > Upload > Bulk (llviewermenufile.cpp do_bulk_upload, file picker FFLOAD_ALL) takes .anim:
  LLNewFileResourceUploadInfo::prepareUpload() deserializes it (unknown joints rejected) and
  re-serializes the same motion, so priority, loop, loop points, ease and hand pose are kept and
  the inventory name is the file name without extension.  .bvh is refused in bulk
  ("DoNotSupportBulkAnimationUpload"); it goes through Build > Upload > Animation one file at a
  time, where priority 4, Loop on, In 0 %, Out 100 %, ease 0.3 s have to be set by hand.

Vertical placement (the convention of SL's built-in animations: "sit" keeps the pelvis, floor poses
such as "sit_ground", "sleep" and "dead" lower it; pit_stocks is lowered although its fallback in
pit_throne.lsl is "sit", so its sit target must sit like a floor pose):
* chair poses pit_lord, pit_chair, pit_scribe, pit_guard and the standing pit_mast keep the pelvis
  at its default height (seat 0.115 m under the avatar root);
* poses on the floor are lowered towards the soles of a standing avatar (1.067 m under the root):
  pit_kneel, pit_dog, pit_rack, pit_stocks (bench 0.46 m high, as in the model), and slightly
  pit_cage (crouched), pit_winch and pit_pillory (knees bent).  See poses.json for the numbers.
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
OUT = os.path.join(ROOT, "output", "animations")
PREV = os.path.join(OUT, "previews")

PRIORITY = 4            # HIGHEST_PRIORITY (lljoint.h)
DURATION = 1.0          # seconds; two identical keys at 0 and DURATION
EASE_IN = 0.3
EASE_OUT = 0.3
MAX_PELVIS_OFFSET = 5.0  # LL_MAX_PELVIS_OFFSET (lljoint.h)
INCHES = 0.02540005      # INCHES_TO_METERS (llbvhloader.cpp)
HAND_RELAXED, HAND_FIST, HAND_FIST_R = 1, 3, 9

ROOT_Z = 1.067           # mPelvis pos in avatar_skeleton.xml: the default pelvis is this high over
                         # the soles of a standing avatar.  Previews and targets use "ground"
                         # coordinates: z = 0 at the standing soles, the avatar root at ROOT_Z.

# ---------------------------------------------------------------------------------------------
# The 19 animated joints: SL name, BVH alias, parent, position relative to the parent (metres,
# SL frame) from avatar_skeleton.xml.  mTorso and mChest sum the in-between extended spine bones
# (mSpine1..4), whose positions cancel out and whose rotation is identity.
# ---------------------------------------------------------------------------------------------
JOINTS = [
    ("mPelvis", "hip", None, (0.0, 0.0, 0.0)),
    ("mTorso", "abdomen", "mPelvis", (0.0, 0.0, 0.084)),
    ("mChest", "chest", "mTorso", (-0.015, 0.0, 0.205)),
    ("mNeck", "neck", "mChest", (-0.010, 0.0, 0.251)),
    ("mHead", "head", "mNeck", (0.0, 0.0, 0.076)),
    ("mCollarLeft", "lCollar", "mChest", (-0.021, 0.085, 0.165)),
    ("mShoulderLeft", "lShldr", "mCollarLeft", (0.0, 0.079, 0.0)),
    ("mElbowLeft", "lForeArm", "mShoulderLeft", (0.0, 0.248, 0.0)),
    ("mWristLeft", "lHand", "mElbowLeft", (0.0, 0.205, 0.0)),
    ("mCollarRight", "rCollar", "mChest", (-0.021, -0.085, 0.165)),
    ("mShoulderRight", "rShldr", "mCollarRight", (0.0, -0.079, 0.0)),
    ("mElbowRight", "rForeArm", "mShoulderRight", (0.0, -0.248, 0.0)),
    ("mWristRight", "rHand", "mElbowRight", (0.0, -0.205, 0.0)),
    ("mHipLeft", "lThigh", "mPelvis", (0.034, 0.127, -0.041)),
    ("mKneeLeft", "lShin", "mHipLeft", (-0.001, -0.046, -0.491)),
    ("mAnkleLeft", "lFoot", "mKneeLeft", (-0.029, 0.001, -0.468)),
    ("mHipRight", "rThigh", "mPelvis", (0.034, -0.129, -0.041)),
    ("mKneeRight", "rShin", "mHipRight", (-0.001, 0.049, -0.491)),
    ("mAnkleRight", "rFoot", "mKneeRight", (-0.029, 0.0, -0.468)),
]
NAMES = [j[0] for j in JOINTS]
BVH_NAME = {j[0]: j[1] for j in JOINTS}
PARENT = {j[0]: j[2] for j in JOINTS}
OFF = {j[0]: j[3] for j in JOINTS}
CHILDREN = {n: [j[0] for j in JOINTS if j[2] == n] for n in NAMES}
# end sites (avatar_skeleton.xml): top of the head (mSkull), end of the hand, mFoot then mToe
END = {"mHead": (0.0, 0.0, 0.079), "mWristLeft": (0.0, 0.060, 0.0), "mWristRight": (0.0, -0.060, 0.0),
       "mAnkleLeft": (0.112, 0.0, -0.061), "mAnkleRight": (0.112, 0.0, -0.061)}
TOE = (0.109, 0.0, 0.0)
SIDE = {"L": 1.0, "R": -1.0}
ARM = {s: (f"mCollar{n}", f"mShoulder{n}", f"mElbow{n}", f"mWrist{n}") for s, n in (("L", "Left"), ("R", "Right"))}
LEG = {s: (f"mHip{n}", f"mKnee{n}", f"mAnkle{n}") for s, n in (("L", "Left"), ("R", "Right"))}

# ---------------------------------------------------------------------------------------------
# vectors and quaternions: Hamilton product, (w, x, y, z), q * v * q^-1 rotates column vectors.
# (LLQuaternion stores the same x,y,z,w; only its operator* is written the other way round:
#  SL a*b == Hamilton b*a.)
# ---------------------------------------------------------------------------------------------
QI = (1.0, 0.0, 0.0, 0.0)


def add(a, b):
    return (a[0] + b[0], a[1] + b[1], a[2] + b[2])


def sub(a, b):
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def mul(a, s):
    return (a[0] * s, a[1] * s, a[2] * s)


def dot(a, b):
    return a[0] * b[0] + a[1] * b[1] + a[2] * b[2]


def cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def length(a):
    return math.sqrt(dot(a, a))


def norm(a):
    n = length(a)
    return (a[0] / n, a[1] / n, a[2] / n)


def perp(v, axis):
    """Unit component of v perpendicular to the unit vector axis."""
    return norm(sub(v, mul(axis, dot(v, axis))))


def angle(a, b):
    return math.degrees(math.acos(max(-1.0, min(1.0, dot(norm(a), norm(b))))))


def qmul(a, b):
    aw, ax, ay, az = a
    bw, bx, by, bz = b
    return (aw * bw - ax * bx - ay * by - az * bz,
            aw * bx + ax * bw + ay * bz - az * by,
            aw * by - ax * bz + ay * bw + az * bx,
            aw * bz + ax * by - ay * bx + az * bw)


def qconj(q):
    return (q[0], -q[1], -q[2], -q[3])


def qnorm(q):
    n = math.sqrt(sum(c * c for c in q))
    return tuple(c / n for c in q)


def qrot(q, v):
    w, x, y, z = q
    r = qmul(qmul(q, (0.0, v[0], v[1], v[2])), (w, -x, -y, -z))
    return (r[1], r[2], r[3])


def qaxis(axis, deg):
    a = norm(axis)
    h = math.radians(deg) / 2
    s = math.sin(h)
    return (math.cos(h), a[0] * s, a[1] * s, a[2] * s)


def qx(d):
    return qaxis((1, 0, 0), d)


def qy(d):
    return qaxis((0, 1, 0), d)


def qz(d):
    return qaxis((0, 0, 1), d)


def qangle(q):
    return math.degrees(2 * math.acos(min(1.0, abs(q[0]))))


def qdiff(a, b):
    """Angle in degrees between two rotations."""
    return qangle(qmul(qconj(a), b))


def qmat(q):
    w, x, y, z = q
    return ((1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)),
            (2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)),
            (2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)))


def mat_q(m):
    tr = m[0][0] + m[1][1] + m[2][2]
    if tr > 0:
        s = math.sqrt(tr + 1.0) * 2
        q = (0.25 * s, (m[2][1] - m[1][2]) / s, (m[0][2] - m[2][0]) / s, (m[1][0] - m[0][1]) / s)
    elif m[0][0] > m[1][1] and m[0][0] > m[2][2]:
        s = math.sqrt(1.0 + m[0][0] - m[1][1] - m[2][2]) * 2
        q = ((m[2][1] - m[1][2]) / s, 0.25 * s, (m[0][1] + m[1][0]) / s, (m[0][2] + m[2][0]) / s)
    elif m[1][1] > m[2][2]:
        s = math.sqrt(1.0 + m[1][1] - m[0][0] - m[2][2]) * 2
        q = ((m[0][2] - m[2][0]) / s, (m[0][1] + m[1][0]) / s, 0.25 * s, (m[1][2] + m[2][1]) / s)
    else:
        s = math.sqrt(1.0 + m[2][2] - m[0][0] - m[1][1]) * 2
        q = ((m[1][0] - m[0][1]) / s, (m[0][2] + m[2][0]) / s, (m[1][2] + m[2][1]) / s, 0.25 * s)
    return qnorm(q)


def qframes(b0, c0, b1, c1):
    """Rotation that takes the rest bone axis b0 to b1 and the rest side axis c0 to c1."""
    def frame(b, c):
        b = norm(b)
        c = perp(c, b)
        return (b, c, cross(b, c))
    f0, f1 = frame(b0, c0), frame(b1, c1)
    m = tuple(tuple(sum(f1[k][i] * f0[k][j] for k in range(3)) for j in range(3)) for i in range(3))
    return mat_q(m)


def qarc(a, b):
    """Shortest rotation taking direction a to direction b."""
    a, b = norm(a), norm(b)
    c = cross(a, b)
    d = dot(a, b)
    if d < -0.999999:
        return qaxis(perp((1, 0, 0) if abs(a[0]) < 0.9 else (0, 1, 0), a), 180)
    return qnorm((1 + d, c[0], c[1], c[2]))


def swing_twist(q, axis):
    """q = swing * twist, twist about the unit axis (in q's own frame)."""
    p = dot((q[1], q[2], q[3]), axis)
    t = (q[0], axis[0] * p, axis[1] * p, axis[2] * p)
    n = math.sqrt(sum(c * c for c in t))
    t = QI if n < 1e-9 else tuple(c / n for c in t)
    return qmul(q, qconj(t)), t


def signed_twist(q, axis):
    _, t = swing_twist(q, axis)
    a = qangle(t)
    return a if dot((t[1], t[2], t[3]), axis) * t[0] >= 0 else -a


# ---------------------------------------------------------------------------------------------
# forward kinematics (the same function feeds the previews and the checks)
# ---------------------------------------------------------------------------------------------
def fk(local, pelvis_pos):
    """World (avatar-root) rotations and positions; pelvis at ground (0, 0, ROOT_Z) + pelvis_pos."""
    W, P = {}, {}
    for n in NAMES:
        q = local.get(n, QI)
        par = PARENT[n]
        if par is None:
            W[n] = q
            P[n] = (pelvis_pos[0], pelvis_pos[1], ROOT_Z + pelvis_pos[2])
        else:
            W[n] = qmul(W[par], q)
            P[n] = add(P[par], qrot(W[par], OFF[n]))
    return W, P


def end_point(W, P, n, off=None):
    return add(P[n], qrot(W[n], off or END[n]))


# ---------------------------------------------------------------------------------------------
# pose builder: spine by angles, limbs by world directions or by a target (two-bone IK with a
# pole = the way the elbow / knee cap points).  The elbow and the knee are pure hinges on the
# crease side, so they cannot bend backwards; forearm roll (pronation) is moved from the wrist
# into the forearm so the wrist only bends.
# ---------------------------------------------------------------------------------------------
class Builder:
    def __init__(self, name):
        self.name = name
        self.loc = {n: QI for n in NAMES}
        self.pelvis_pos = (0.0, 0.0, 0.0)
        self.hand_pose = HAND_RELAXED
        self.props = []
        self.targets = []       # (joint or ("end", joint), target, label) checked after the round trip
        self.notes = []

    def fk(self):
        return fk(self.loc, self.pelvis_pos)

    def pos(self, n):
        return self.fk()[1][n]

    # --- trunk -------------------------------------------------------------------------------
    @staticmethod
    def euler(pitch=0.0, lean=0.0, yaw=0.0):
        """pitch + bends forward, lean + tilts the top to the avatar's left, yaw + turns left."""
        return qmul(qz(yaw), qmul(qy(pitch), qx(-lean)))

    def pelvis(self, pitch=0.0, lean=0.0, yaw=0.0, offset=(0.0, 0.0, 0.0), q=None):
        self.loc["mPelvis"] = q if q is not None else self.euler(pitch, lean, yaw)
        self.pelvis_pos = tuple(offset)

    def spine(self, joint, pitch=0.0, lean=0.0, yaw=0.0):
        self.loc[joint] = self.euler(pitch, lean, yaw)

    def collar(self, side, elev=0.0, fwd=0.0):
        s = SIDE[side]
        e, f = math.radians(elev), math.radians(fwd)
        d = (math.sin(f) * math.cos(e), s * math.cos(f) * math.cos(e), math.sin(e))
        self.loc[ARM[side][0]] = qarc((0, s, 0), d)

    # --- limbs -------------------------------------------------------------------------------
    @staticmethod
    def ik(S, T, L1, L2, pole):
        d = sub(T, S)
        dist = length(d)
        t = norm(d)
        dist = max(abs(L1 - L2) * 1.05, min(dist, (L1 + L2) * 0.9995))
        ca = (L1 * L1 + dist * dist - L2 * L2) / (2 * L1 * dist)
        a = math.acos(max(-1.0, min(1.0, ca)))
        p = perp(pole, t)
        E = add(S, mul(add(mul(t, math.cos(a)), mul(p, math.sin(a))), L1))
        Tc = add(S, mul(t, dist))
        return norm(sub(E, S)), norm(sub(Tc, E))

    def _limb(self, upper, lower, end, rest_crease, u, f, pole):
        W, P = self.fk()
        b0u, b0l = norm(OFF[lower]), norm(OFF[end])
        c0u, c0l = perp(rest_crease, b0u), perp(rest_crease, b0l)
        u, f = norm(u), norm(f)
        bend = angle(u, f)
        if bend > 10.0:
            cu = perp(f, u)
        else:
            # nearly straight: the pole decides the plane, and the small bend goes to the crease side
            cu = mul(perp(pole, u), -1.0)
            f = norm(add(mul(u, math.cos(math.radians(bend))), mul(cu, math.sin(math.radians(bend)))))
        hinge = qaxis(cross(u, cu), bend)
        Wu = qframes(b0u, c0u, u, cu)
        Wl = qframes(b0l, c0l, f, qrot(hinge, cu))
        self.loc[upper] = qmul(qconj(W[PARENT[upper]]), Wu)
        self.loc[lower] = qmul(qconj(Wu), Wl)
        return bend

    def arm(self, side, wrist=None, pole=None, upper=None, fore=None, elbow=None, hand=None, palm=None,
            flex=0.0, spread=0.0):
        """wrist: target of the wrist joint (ground coords), pole: where the elbow points.
        upper / fore: world directions instead; elbow: target of the elbow instead of upper.
        hand: world direction of the hand (wrist->knuckles), palm: world direction the palm faces.
        spread: also try poles turned up to this many degrees about the shoulder->wrist line and keep
        the one with the least roll in the shoulder and the forearm (less skin twist in SL)."""
        if not spread:
            self._arm(side, wrist, pole, upper, fore, elbow, hand, palm, flex)
            return
        _, sh, el, wr = ARM[side]
        keep = dict(self.loc)
        ntargets = len(self.targets)
        S = self.pos(sh)
        if wrist is not None:
            axis = norm(sub(wrist, S))
        else:
            axis = norm(add(norm(upper), norm(fore)))
        best = None
        for a in range(-int(spread), int(spread) + 1, 5):
            pl = qrot(qaxis(axis, a), pole)
            self.loc = dict(keep)
            del self.targets[ntargets:]
            self._arm(side, wrist, pl, upper, fore, elbow, hand, palm, flex)
            b0 = norm(OFF[wr])
            ut = signed_twist(self.loc[sh], norm(OFF[el]))
            fr = signed_twist(self.loc[el], b0)
            cost = ut * ut + fr * fr + 0.02 * a * a
            if best is None or cost < best[0]:
                best = (cost, a, pl, round(ut), round(fr))
        self.loc = dict(keep)
        del self.targets[ntargets:]
        self._arm(side, wrist, best[2], upper, fore, elbow, hand, palm, flex)
        self.notes.append(f"{side} arm pole turned {best[1]:+d} deg (shoulder roll {best[3]}, forearm roll {best[4]})")

    def _arm(self, side, wrist, pole, upper, fore, elbow, hand, palm, flex):
        s = SIDE[side]
        _, sh, el, wr = ARM[side]
        S = self.pos(sh)
        L1, L2 = length(OFF[el]), length(OFF[wr])
        if wrist is not None:
            upper, fore = self.ik(S, wrist, L1, L2, pole)
            self.targets.append((wr, wrist, f"{side} wrist"))
        elif elbow is not None:
            upper = sub(elbow, S)
            self.targets.append((el, elbow, f"{side} elbow"))
        self._limb(sh, el, wr, (1, 0, 0), upper, fore, pole or (-1, 0, 0))
        if hand is not None or palm is not None:
            W, _ = self.fk()
            Wl = W[el]
            b0 = (0.0, s, 0.0)
            h = norm(hand) if hand is not None else qrot(Wl, b0)
            p = palm if palm is not None else qrot(Wl, (0, 0, -1))
            Wh = qframes(b0, (0, 0, -1), h, p)
            L = qmul(qconj(Wl), Wh)
            _, tw = swing_twist(L, b0)
            self.loc[el] = qmul(self.loc[el], tw)
            self.loc[wr] = qmul(qconj(tw), L)
        if flex:
            self.loc[wr] = qmul(self.loc[wr], qx(-flex * s))

    def leg(self, side, ankle=None, pole=(1, 0, 0), thigh=None, shin=None, foot="flat"):
        """ankle: target of the ankle joint (ground coords), pole: where the knee cap points.
        thigh / shin: world directions instead.  foot: 'flat', a plantar-flexion angle in degrees,
        or the world direction the sole points to (heel -> toes)."""
        hp, kn, an = LEG[side]
        S = self.pos(hp)
        L1, L2 = length(OFF[kn]), length(OFF[an])
        if ankle is not None:
            thigh, shin = self.ik(S, ankle, L1, L2, pole)
            self.targets.append((an, ankle, f"{side} ankle"))
        self._limb(hp, kn, an, (-1, 0, 0), thigh, shin, pole)
        W, _ = self.fk()
        Wk = W[kn]
        if isinstance(foot, (int, float)):
            self.loc[an] = qy(foot)
            return
        if foot == "flat":
            fwd = qrot(Wk, (1, 0, 0))
            target = norm((fwd[0], fwd[1], 0.0))
        else:
            target = norm(foot)
        best = min((angle(qrot(qmul(Wk, qy(a / 4.0)), (1, 0, 0)), target), a / 4.0) for a in range(-200, 361))
        if best[0] > 12:
            self.notes.append(f"{side} foot misses its direction by {best[0]:.0f} deg")
        self.loc[an] = qy(best[1])

    def ground(self, joints, z, radius=0.0):
        """Shift the pelvis vertically so the lowest of `joints` sits at height z (+ radius)."""
        _, P = self.fk()
        low = min(P[j][2] for j in joints) - radius
        x, y, oz = self.pelvis_pos
        self.pelvis_pos = (x, y, oz + z - low)

    # --- props drawn in the previews (ground coordinates) ------------------------------------
    def box(self, lo, hi, color="prop"):
        self.props.append(("box", tuple(lo), tuple(hi), color))

    def cyl(self, a, b, r, color="prop"):
        self.props.append(("cyl", tuple(a), tuple(b), r, color))


# ---------------------------------------------------------------------------------------------
# the twelve poses (the avatar faces +X, its left is +Y; ground coordinates: the soles of a
# standing avatar at z = 0, its root / default pelvis at z = ROOT_Z)
# ---------------------------------------------------------------------------------------------
def seat_props(b, seat_depth=0.5, seat_w=0.56, back=True, arm_z=None, arm_y=0.3, arm_len=0.5, floor=True):
    W, P = b.fk()
    pz = P["mPelvis"][2]
    top = pz - 0.115
    px = P["mPelvis"][0]
    b.box((px - 0.22, -seat_w / 2, top - 0.08), (px - 0.22 + seat_depth, seat_w / 2, top))
    if back:
        b.box((px - 0.30, -seat_w / 2, top), (px - 0.22, seat_w / 2, top + 0.75))
    if arm_z is not None:
        for s in (1, -1):
            b.box((px - 0.22, s * arm_y - 0.04, arm_z - 0.06), (px - 0.22 + arm_len, s * arm_y + 0.04, arm_z))
    if floor:
        sole = min(P["mAnkleLeft"][2], P["mAnkleRight"][2]) - 0.075
        b.box((px - 0.3, -0.45, sole - 0.03), (px + 0.75, 0.45, sole), "floor")


def pit_lord(b):
    """Pirate lord on his throne: back straight, knees apart, forearms on the armrests."""
    b.pelvis(pitch=-6)
    b.spine("mTorso", pitch=3, yaw=1)
    b.spine("mChest", pitch=2, yaw=1)
    b.spine("mNeck", pitch=-2, yaw=4)
    b.spine("mHead", pitch=-6, yaw=8)
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=-3, fwd=-5)
        b.arm(s, upper=(-0.10, 0.48 * k, -0.87), fore=(1.0, 0.10 * k, -0.02), palm=(0.0, 0.15 * k, -1.0),
              flex=12)
        b.leg(s, thigh=(0.92, 0.38 * k, -0.08), shin=(0.18, 0.12 * k, -1.0), foot="flat")
    W, P = b.fk()
    arm_z = min(P["mElbowLeft"][2], P["mWristLeft"][2]) - 0.045
    seat_props(b, seat_depth=0.62, seat_w=1.0, arm_z=arm_z, arm_y=abs(P["mElbowLeft"][1]) + 0.02, arm_len=0.62)


def pit_kneel(b):
    """Kneeling upright on the stone, hands behind the back, head bowed."""
    b.pelvis(pitch=3)
    b.spine("mTorso", pitch=-1)
    b.spine("mChest", pitch=-3)
    b.spine("mNeck", pitch=18)
    b.spine("mHead", pitch=24)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, thigh=(0.06, 0.05 * k, -1.0), shin=(-1.0, 0.03 * k, 0.03), foot=(-1.0, 0.0, -0.3))
    b.ground(["mKneeLeft", "mKneeRight"], 0.055)
    W, P = b.fk()
    pz = P["mPelvis"][2]
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=-4, fwd=-10)
        b.arm(s, wrist=(-0.19, 0.055 * k, pz + 0.10), pole=(-0.5, k, 0.0),
              hand=(-0.1, -0.5 * k, -1.0), palm=(-1.0, 0.0, 0.0), spread=45)
    b.box((-0.75, -0.45, -0.28), (0.25, 0.45, 0.0))


def pit_rack(b):
    """Lying on the back, arms stretched above the head, legs straight and slightly apart."""
    b.pelvis(pitch=-90)
    b.spine("mTorso", pitch=1)
    b.spine("mChest", pitch=1)
    b.spine("mNeck", pitch=-2)
    b.spine("mHead", pitch=-6)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, thigh=(1.0, 0.10 * k, -0.06), shin=(1.0, 0.10 * k, -0.04), pole=(0, 0, 1), foot=(0.6, 0.0, 1.0))
    b.ground(["mPelvis", "mChest"], 0.11)
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=28, fwd=0)
        b.arm(s, upper=(-1.0, 0.20 * k, 0.0), fore=(-1.0, 0.20 * k, 0.0), pole=(0.0, 0.3 * k, 1.0),
              palm=(0.0, 0.0, 1.0), spread=180)
    b.box((-1.25, -0.4, -0.15), (1.25, 0.4, 0.0))
    for x in (-1.15, 1.15):
        b.cyl((x, -0.5, 0.12), (x, 0.5, 0.12), 0.08)


def pit_pillory(b):
    """Standing, bent ~80 deg at the hips, neck and wrists in a yoke at ~1.15 m."""
    b.pelvis(pitch=62, offset=(0.0, 0.0, -0.03))
    b.spine("mTorso", pitch=13)
    b.spine("mChest", pitch=13)
    b.spine("mNeck", pitch=-22)
    b.spine("mHead", pitch=-26)
    W, P = b.fk()
    px = P["mPelvis"][0]
    for s in "LR":
        k = SIDE[s]
        b.leg(s, ankle=(px + 0.0, 0.13 * k, 0.067), pole=(1, 0.1 * k, 0))
    W, P = b.fk()
    neck = P["mNeck"]
    yoke_x = P["mHead"][0] + 0.03
    yoke_z = (neck[2] + P["mHead"][2]) / 2
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=4, fwd=18)
        b.arm(s, wrist=(yoke_x, 0.30 * k, yoke_z), pole=(-0.5, 1.0 * k, -0.6),
              hand=(1.0, -0.05 * k, -0.45), palm=(-0.3, -0.2 * k, -1.0), spread=120)
    b.notes.append(f"yoke (neck/wrists) at {yoke_z:.2f} m over the feet")
    b.box((yoke_x - 0.06, -0.65, yoke_z - 0.17), (yoke_x + 0.06, 0.65, yoke_z + 0.17))
    b.box((yoke_x + 0.06, -0.08, 0.0), (yoke_x + 0.18, 0.08, yoke_z + 0.4))
    b.box((-0.6, -0.6, -0.04), (yoke_x + 0.3, 0.6, 0.0), "floor")


def pit_stocks(b):
    """Sitting on the low bench, legs straight forward in the foot stocks, hands on the bench."""
    bench = 0.46
    b.pelvis(pitch=-12, offset=(0.0, 0.0, bench + 0.11 - ROOT_Z))
    b.spine("mTorso", pitch=6)
    b.spine("mChest", pitch=8)
    b.spine("mNeck", pitch=4)
    b.spine("mHead", pitch=12)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, thigh=(1.0, 0.07 * k, -0.17), shin=(1.0, 0.07 * k, -0.17), pole=(0, 0, 1), foot=12)
    W, P = b.fk()
    px, pz = P["mPelvis"][0], P["mPelvis"][2]
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=-8, fwd=4)
        b.arm(s, wrist=(px + 0.10, 0.25 * k, bench + 0.12), pole=(-1.0, 0.3 * k, 0.0),
              hand=(0.55, 0.05 * k, -0.85), palm=(-0.85, 0.0, -0.55), spread=60)
    W, P = b.fk()
    ax = P["mAnkleLeft"][0]
    az = (P["mAnkleLeft"][2] + P["mAnkleRight"][2]) / 2
    b.box((px - 0.15, -0.9, bench - 0.08), (px + 0.15, 0.9, bench))
    b.box((ax - 0.06, -0.7, 0.0), (ax + 0.06, 0.7, az + 0.07))
    b.box((px - 0.4, -0.9, -0.04), (ax + 0.4, 0.9, 0.0), "floor")
    b.notes.append(f"ankles at {az:.2f} m in the stocks, bench top at {bench:.2f} m")


def pit_chair(b):
    """Sitting upright in the ducking chair, forearms on the armrests, as if tied."""
    b.hand_pose = HAND_FIST
    b.pelvis(pitch=-3)
    b.spine("mTorso", pitch=2)
    b.spine("mChest", pitch=1)
    b.spine("mNeck", pitch=6)
    b.spine("mHead", pitch=10, yaw=-6)
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=1, fwd=-2)
        b.arm(s, upper=(-0.22, 0.30 * k, -0.93), fore=(1.0, 0.02 * k, 0.0), palm=(0.0, 0.0, -1.0))
        b.leg(s, thigh=(1.0, 0.03 * k, -0.04), shin=(0.04, 0.0, -1.0), foot="flat")
    W, P = b.fk()
    arm_z = min(P["mElbowLeft"][2], P["mWristLeft"][2]) - 0.045
    seat_props(b, seat_depth=0.56, seat_w=0.56, arm_z=arm_z, arm_y=0.28, arm_len=0.56)


def pit_dog(b):
    """On all fours on hands and knees, head up."""
    b.pelvis(pitch=82)
    b.spine("mTorso", pitch=14)
    b.spine("mChest", pitch=18)
    b.spine("mNeck", pitch=-62)
    b.spine("mHead", pitch=-50)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, thigh=(0.42, 0.07 * k, -1.0), shin=(-1.0, 0.02 * k, 0.02), foot=(-1.0, 0.0, -0.35))
    b.ground(["mKneeLeft", "mKneeRight"], 0.055)
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=-6, fwd=6)
        W, P = b.fk()
        sh = P[ARM[s][1]]
        b.arm(s, wrist=(sh[0] + 0.05, sh[1] + 0.03 * k, 0.05), pole=(-1.0, 0.25 * k, 0.0),
              hand=(1.0, 0.12 * k, 0.0), palm=(0.0, 0.0, -1.0), spread=90)
    b.box((-0.7, -0.5, -0.04), (0.9, 0.5, 0.0), "floor")


def pit_cage(b):
    """Crouched and hunched in the hanging cage, hands gripping the bars at shoulder height."""
    b.hand_pose = HAND_FIST
    b.pelvis(pitch=14, offset=(-0.12, 0.0, -0.27))
    b.spine("mTorso", pitch=10)
    b.spine("mChest", pitch=16)
    b.spine("mNeck", pitch=-4)
    b.spine("mHead", pitch=-6, yaw=6)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, ankle=(-0.02, 0.15 * k, 0.067), pole=(1.0, 0.35 * k, 0.0), foot="flat")
    R = 0.42
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=6, fwd=10)
        W, P = b.fk()
        sz = P[ARM[s][1]][2]
        a = math.radians(32)
        bar = (R * math.cos(a), k * R * math.sin(a))
        hd = norm((bar[0] - 0.0, bar[1] - 0.06 * k, 0.0))
        wrist = (bar[0] - 0.085 * hd[0], bar[1] - 0.085 * hd[1], sz)
        b.arm(s, wrist=wrist, pole=(-0.3, 0.6 * k, -1.0), hand=hd, palm=(0.0, -k, 0.0), spread=30)
    for i in range(12):
        a = 2 * math.pi * i / 12
        p = (R * math.cos(a), R * math.sin(a))
        b.cyl((p[0], p[1], 0.0), (p[0], p[1], 1.64), 0.012, "iron")
    b.cyl((0, 0, -0.03), (0, 0, 0.0), R, "floor")


def pit_mast(b):
    """Standing against the mast, arms raised above the head, wrists tied together."""
    b.hand_pose = HAND_FIST
    b.pelvis(pitch=3)
    b.spine("mTorso", pitch=-2)
    b.spine("mChest", pitch=-3)
    b.spine("mNeck", pitch=4, yaw=-12)
    b.spine("mHead", pitch=6, yaw=-26, lean=-4)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, ankle=(0.03, 0.12 * k, 0.067), pole=(1.0, 0.12 * k, 0.0), foot="flat")
    for s in "LR":
        b.collar(s, elev=26, fwd=8)
    W, P = b.fk()
    top = max(P["mShoulderLeft"][2], P["mShoulderRight"][2]) + 0.41
    for s in "LR":
        k = SIDE[s]
        b.arm(s, wrist=(0.13, 0.035 * k, top), pole=(1.0, 0.6 * k, 0.0), hand=(0.1, -0.15 * k, 1.0),
              palm=(1.0, 0.0, 0.0), spread=180)
    b.cyl((0.36, 0, 0.0), (0.36, 0, 2.45), 0.15)
    b.box((-0.5, -0.5, -0.04), (0.6, 0.5, 0.0), "floor")
    b.notes.append(f"tied wrists at {top:.2f} m over the feet")


def pit_scribe(b):
    """Sitting at the desk writing: right hand on the page, left hand holding it."""
    b.hand_pose = HAND_FIST_R
    b.pelvis(pitch=4)
    b.spine("mTorso", pitch=7)
    b.spine("mChest", pitch=9, yaw=4)
    b.spine("mNeck", pitch=14)
    b.spine("mHead", pitch=20, yaw=-4)
    for s in "LR":
        k = SIDE[s]
        b.leg(s, thigh=(1.0, 0.14 * k, -0.06), shin=(0.10, 0.05 * k, -1.0), foot="flat")
    W, P = b.fk()
    seat = P["mPelvis"][2] - 0.115
    desk = seat + 0.40
    b.collar("R", elev=2, fwd=6)
    b.collar("L", elev=0, fwd=8)
    b.arm("R", wrist=(0.40, -0.10, desk + 0.035), pole=(-0.3, -1.0, -0.6),
          hand=(0.80, 0.45, -0.25), palm=(-0.1, 0.45, -1.0), spread=60)
    b.arm("L", wrist=(0.40, 0.21, desk + 0.03), pole=(-0.3, 1.0, -0.7),
          hand=(0.75, -0.55, -0.05), palm=(0.0, -0.05, -1.0), spread=60)
    px = P["mPelvis"][0]
    b.cyl((px, 0, seat - 0.05), (px, 0, seat), 0.22)
    b.box((0.33, -0.75, desk - 0.06), (1.17, 0.75, desk))
    sole = min(P["mAnkleLeft"][2], P["mAnkleRight"][2]) - 0.075
    b.box((-0.4, -0.6, sole - 0.03), (1.2, 0.6, sole), "floor")


def pit_guard(b):
    """Sitting relaxed at the table, leaning on the right elbow, legs apart."""
    b.hand_pose = HAND_FIST_R
    b.pelvis(pitch=0, lean=-3)
    b.spine("mTorso", pitch=12, lean=-3)
    b.spine("mChest", pitch=16, lean=-2, yaw=-6)
    b.spine("mNeck", pitch=-10, yaw=10)
    b.spine("mHead", pitch=-8, yaw=16)
    b.leg("L", thigh=(0.88, 0.45, -0.12), shin=(0.30, 0.12, -1.0), foot="flat")
    b.leg("R", thigh=(0.92, -0.40, -0.05), shin=(0.02, -0.10, -1.0), foot="flat")
    W, P = b.fk()
    seat = P["mPelvis"][2] - 0.115
    b.collar("R", elev=4, fwd=10)
    b.collar("L", elev=-2, fwd=4)
    b.arm("R", upper=(0.82, -0.12, -0.55), fore=(0.32, 0.30, 0.90), hand=(0.32, 0.30, 0.90),
          palm=(-0.15, 1.0, -0.1))
    W, P = b.fk()
    table = P["mElbowRight"][2] - 0.045
    hp, kn = P["mHipLeft"], P["mKneeLeft"]
    mid = add(hp, mul(sub(kn, hp), 0.62))
    b.arm("L", wrist=(mid[0], mid[1] - 0.01, mid[2] + 0.10), pole=(-0.4, 1.0, -0.3),
          hand=(1.0, 0.05, -0.35), palm=(-0.3, 0.0, -1.0), spread=30)
    b.box((0.33, -0.9, table - 0.06), (1.2, 0.9, table))
    b.box((-0.15, -0.9, seat - 0.06), (0.15, 0.9, seat))
    sole = min(P["mAnkleLeft"][2], P["mAnkleRight"][2]) - 0.075
    b.box((-0.4, -0.8, sole - 0.03), (1.2, 0.8, sole), "floor")
    b.notes.append(f"table top {table - seat:.2f} m over the seat (model: 0.34)")


def pit_winch(b):
    """Standing, slightly crouched, both hands forward at waist height on the winch handle."""
    b.hand_pose = HAND_FIST
    b.pelvis(pitch=10, offset=(0.0, 0.0, -0.07))
    b.spine("mTorso", pitch=6)
    b.spine("mChest", pitch=5)
    b.spine("mNeck", pitch=-8)
    b.spine("mHead", pitch=-6)
    b.leg("L", ankle=(0.20, 0.14, 0.067), pole=(1.0, 0.15, 0.0), foot="flat")
    b.leg("R", ankle=(-0.22, -0.14, 0.067), pole=(1.0, -0.15, 0.0), foot="flat")
    hz = 1.05
    for s in "LR":
        k = SIDE[s]
        b.collar(s, elev=0, fwd=12)
        b.arm(s, wrist=(0.34, 0.11 * k, hz), pole=(-0.3, 0.6 * k, -1.0), hand=(1.0, -0.05 * k, -0.9),
              palm=(-0.6, 0.0, -1.0), spread=60)
    W, P = b.fk()
    grip = end_point(W, P, "mWristLeft", (0.0, 0.07, 0.0))
    b.cyl((grip[0], -0.35, grip[2]), (grip[0], 0.35, grip[2]), 0.022, "iron")
    b.box((-0.6, -0.5, -0.04), (0.8, 0.5, 0.0), "floor")


POSES = [pit_lord, pit_kneel, pit_rack, pit_pillory, pit_stocks, pit_chair, pit_dog, pit_cage, pit_mast,
         pit_scribe, pit_guard, pit_winch]


def build(fn):
    b = Builder(fn.__name__)
    fn(b)
    # every joint must differ from the rest pose, or the BVH importer drops it (rot_changed)
    for n in NAMES:
        if qangle(b.loc[n]) < 0.3:
            b.loc[n] = qmul(b.loc[n], qx(0.4))
        b.loc[n] = qnorm(b.loc[n])
    return b


# ---------------------------------------------------------------------------------------------
# .anim writer / reader (mirrors LLKeyframeMotion::serialize / deserialize)
# ---------------------------------------------------------------------------------------------
def f2u(v, lo, hi):
    v = min(max(v, lo), hi)
    return int(round((v - lo) / (hi - lo) * 65535.0))


def u2f(u, lo, hi):
    v = u / 65535.0 * (hi - lo) + lo
    return 0.0 if abs(v) < (hi - lo) / 65535.0 else v


def anim_bytes(local, pelvis_pos, hand_pose):
    out = bytearray()

    def pk(fmt, *v):
        out.extend(struct.pack("<" + fmt, *v))

    pk("HH", 1, 0)
    pk("i", PRIORITY)
    pk("f", DURATION)
    out.extend(b"\0")                       # emote_name
    pk("ff", 0.0, DURATION)                 # loop_in_point, loop_out_point
    pk("i", 1)                              # loop
    pk("ff", EASE_IN, EASE_OUT)
    pk("I", hand_pose)
    pk("I", len(NAMES))
    for n in NAMES:
        out.extend(n.encode("ascii") + b"\0")
        pk("i", PRIORITY)
        q = qnorm(local[n])
        if q[0] < 0:
            q = tuple(-c for c in q)
        pk("i", 2)
        for t in (0.0, DURATION):
            pk("HHHH", f2u(t, 0.0, DURATION), *(f2u(c, -1.0, 1.0) for c in q[1:]))
        if n == "mPelvis":
            pk("i", 2)
            for t in (0.0, DURATION):
                pk("HHHH", f2u(t, 0.0, DURATION),
                   *(f2u(c, -MAX_PELVIS_OFFSET, MAX_PELVIS_OFFSET) for c in pelvis_pos))
        else:
            pk("i", 0)
    pk("i", 0)                              # num_constraints
    return bytes(out)


def read_anim(data):
    """Parse a .anim the way LLKeyframeMotion::deserialize does; raises on anything it rejects."""
    o = [0]

    def up(fmt):
        r = struct.unpack_from("<" + fmt, data, o[0])
        o[0] += struct.calcsize("<" + fmt)
        return r

    def ustr():
        e = data.index(b"\0", o[0])
        s = data[o[0]:e].decode("ascii")
        o[0] = e + 1
        return s

    a = {}
    a["version"], a["sub_version"] = up("HH")
    assert (a["version"], a["sub_version"]) == (1, 0), "bad version"
    a["priority"], = up("i")
    assert 0 <= a["priority"] < 7, "base priority out of range"
    a["duration"], = up("f")
    assert 0 < a["duration"] <= 60.0, "duration"
    a["emote"] = ustr()
    a["loop_in"], a["loop_out"] = up("ff")
    a["loop"], = up("i")
    a["ease_in"], a["ease_out"] = up("ff")
    a["hand_pose"], = up("I")
    assert a["hand_pose"] <= 14, "hand pose"
    nj, = up("I")
    assert 0 < nj <= 216, "joint count"
    joints = {}
    D = a["duration"]
    for _ in range(nj):
        name = ustr()
        assert name in NAMES, f"unknown joint {name}"
        prio, = up("i")
        assert prio >= -1
        nr, = up("i")
        rots = []
        for _k in range(nr):
            t, x, y, z = up("HHHH")
            v = (u2f(x, -1, 1), u2f(y, -1, 1), u2f(z, -1, 1))
            w = math.sqrt(max(0.0, 1.0 - dot(v, v)))
            rots.append((u2f(t, 0, D), (w,) + v))
        npos, = up("i")
        poss = []
        for _k in range(npos):
            t, x, y, z = up("HHHH")
            poss.append((u2f(t, 0, D), tuple(u2f(c, -MAX_PELVIS_OFFSET, MAX_PELVIS_OFFSET) for c in (x, y, z))))
        joints[name] = {"priority": prio, "rot": rots, "pos": poss}
    nc, = up("i")
    assert nc == 0
    assert o[0] == len(data), "trailing bytes"
    a["joints"] = joints
    return a


# ---------------------------------------------------------------------------------------------
# .bvh writer / reader (SL / QAvimator skeleton, inches, Y up, avatar facing +Z)
# ---------------------------------------------------------------------------------------------
# BVH vector = P * SL vector: (x, y, z)_bvh = (y_sl, z_sl, x_sl)
def sl_to_bvh(v):
    return (v[1], v[2], v[0])


def bvh_to_sl(v):
    return (v[2], v[0], v[1])


def q_sl_to_bvh(q):
    w, x, y, z = q
    return (w, y, z, x)


def q_bvh_to_sl(q):
    w, x, y, z = q
    return (w, z, x, y)


def euler_xzy(q):
    """Angles (X, Z, Y) in degrees with R = Rx(X) * Rz(Z) * Ry(Y): channels Xrotation Zrotation Yrotation."""
    m = qmat(q)
    c = math.asin(max(-1.0, min(1.0, -m[0][1])))
    if abs(math.cos(c)) > 1e-6:
        a = math.atan2(m[2][1], m[1][1])
        b = math.atan2(m[0][2], m[0][0])
    else:
        a = math.atan2(-m[1][2], m[2][2])
        b = 0.0
    return math.degrees(a), math.degrees(c), math.degrees(b)


def bvh_text(local, pelvis_pos):
    lines = ["HIERARCHY"]
    order = []

    def joint(n, depth):
        ind = "\t" * depth
        lines.append(f"{ind}{'ROOT' if depth == 0 else 'JOINT'} {BVH_NAME[n]}")
        lines.append(ind + "{")
        off = mul(sl_to_bvh(OFF[n]), 1 / INCHES) if depth else (0.0, 0.0, 0.0)
        lines.append(f"{ind}\tOFFSET {off[0]:.6f} {off[1]:.6f} {off[2]:.6f}")
        if depth == 0:
            lines.append(f"{ind}\tCHANNELS 6 Xposition Yposition Zposition Xrotation Zrotation Yrotation")
        else:
            lines.append(f"{ind}\tCHANNELS 3 Xrotation Zrotation Yrotation")
        order.append(n)
        for c in CHILDREN[n]:
            joint(c, depth + 1)
        if n in END:
            e = mul(sl_to_bvh(add(END[n], TOE) if n.startswith("mAnkle") else END[n]), 1 / INCHES)
            lines.append(f"{ind}\tEnd Site")
            lines.append(ind + "\t{")
            lines.append(f"{ind}\t\tOFFSET {e[0]:.6f} {e[1]:.6f} {e[2]:.6f}")
            lines.append(ind + "\t}")
        lines.append(ind + "}")

    joint("mPelvis", 0)
    hip_y = ROOT_Z / INCHES
    t_pose = []
    pose = []
    for n in order:
        if n == "mPelvis":
            t_pose += [0.0, hip_y, 0.0]
            d = mul(sl_to_bvh(pelvis_pos), 1 / INCHES)
            pose += [d[0], hip_y + d[1], d[2]]
        t_pose += [0.0, 0.0, 0.0]
        pose += list(euler_xzy(q_sl_to_bvh(local[n])))
    lines += ["MOTION", "Frames: 3", f"Frame Time: {DURATION:.6f}"]
    for fr in (t_pose, pose, pose):
        lines.append(" ".join(f"{v:.6f}" for v in fr))
    return "\n".join(lines) + "\n"


def read_bvh(text):
    """Joint rotations of frame 1 as llbvhloader.cpp turns them into keys (SL frame), hip offset."""
    toks = text.split()
    names, chans = [], []
    i = 0
    while toks[i] != "MOTION":
        if toks[i] in ("ROOT", "JOINT"):
            names.append(toks[i + 1])
        if toks[i] == "CHANNELS":
            n = int(toks[i + 1])
            chans.append(toks[i + 2:i + 2 + n])
        i += 1
    nframes = int(toks[i + 2])
    ftime = float(toks[i + 5])
    vals = [float(v) for v in toks[i + 6:]]
    width = sum(len(c) for c in chans)
    assert len(vals) == width * nframes
    frames = [vals[k * width:(k + 1) * width] for k in range(nframes)]
    alias = {v: k for k, v in BVH_NAME.items()}

    def decode(fr):
        rots, pos = {}, None
        k = 0
        for nm, ch in zip(names, chans):
            v = dict(zip(ch, fr[k:k + len(ch)]))
            k += len(ch)
            order = [c[0] for c in ch if c.endswith("rotation")]
            q = QI
            for ax in order:       # BVH: R = R(first channel) * R(second) * R(third)
                q = qmul(q, qaxis({"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}[ax], v[ax + "rotation"]))
            rots[alias[nm]] = q_bvh_to_sl(q)
            if "Xposition" in v:
                pos = (v["Xposition"], v["Yposition"], v["Zposition"])
        return rots, pos

    r0, p0 = decode(frames[0])
    r1, p1 = decode(frames[1])
    # the hip key is relative to frame 0 (mRelativeRotationKey / mRelativePositionKey)
    r1["mPelvis"] = qmul(qconj(r0["mPelvis"]), r1["mPelvis"]) if r0["mPelvis"] != QI else r1["mPelvis"]
    off = mul(bvh_to_sl(sub(p1, p0)), INCHES)
    return {"rot": r1, "pelvis": off, "duration": (nframes - 2) * ftime, "frame0": r0}


# ---------------------------------------------------------------------------------------------
# checks
# ---------------------------------------------------------------------------------------------
def limb_report(local, W, P):
    rep = {}
    for s in "LR":
        _, sh, el, wr = ARM[s]
        b0 = norm(OFF[wr])
        rep[f"{s} upper arm roll"] = round(signed_twist(local[sh], norm(OFF[el])), 1)
        rep[f"{s} elbow bend"] = round(angle(qrot(W[sh], norm(OFF[el])), qrot(W[el], b0)), 1)
        rep[f"{s} forearm roll"] = round(signed_twist(local[el], b0), 1)
        rep[f"{s} wrist bend"] = round(qangle(local[wr]), 1)
        rep[f"{s} wrist roll"] = round(signed_twist(local[wr], b0), 1)
        hp, kn, an = LEG[s]
        rep[f"{s} knee bend"] = round(angle(qrot(W[hp], norm(OFF[kn])), qrot(W[kn], norm(OFF[an]))), 1)
        rep[f"{s} thigh roll"] = round(signed_twist(local[hp], norm(OFF[kn])), 1)
        rep[f"{s} shin roll"] = round(signed_twist(local[kn], norm(OFF[an])), 1)
        rep[f"{s} ankle"] = round(math.degrees(2 * math.atan2(local[an][2], local[an][0])), 1)
    return rep


def contacts(W, P):
    def lowz(n):
        return round(P[n][2], 3)
    soles = [end_point(W, P, a, add(END[a], TOE)) for a in ("mAnkleLeft", "mAnkleRight")]
    return {
        "pelvis": [round(c, 3) for c in P["mPelvis"]],
        "knees_z": [lowz("mKneeLeft"), lowz("mKneeRight")],
        "ankles_z": [lowz("mAnkleLeft"), lowz("mAnkleRight")],
        "toes_z": [round(s[2], 3) for s in soles],
        "wrists": [[round(c, 3) for c in P["mWristLeft"]], [round(c, 3) for c in P["mWristRight"]]],
        "neck_z": lowz("mNeck"),
        "head_top_z": round(end_point(W, P, "mHead")[2] + 0.06, 3),
    }


def verify(b, data, bvh):
    a = read_anim(data)
    errs = {}
    assert a["loop"] == 1 and a["priority"] == PRIORITY and abs(a["loop_out"] - DURATION) < 1e-6
    assert set(a["joints"]) == set(NAMES)
    dec = {}
    for n, j in a["joints"].items():
        assert j["priority"] == PRIORITY and len(j["rot"]) == 2
        assert j["rot"][0][1] == j["rot"][1][1] and j["rot"][0][0] == 0.0 and j["rot"][1][0] == DURATION
        dec[n] = j["rot"][0][1]
        errs[n] = qdiff(dec[n], b.loc[n])
    pel = a["joints"]["mPelvis"]["pos"]
    assert len(pel) == 2
    dpos = pel[0][1]
    max_anim = max(errs.values())
    assert max_anim < 0.02, f"anim rotation round trip {max_anim} deg"
    assert length(sub(dpos, b.pelvis_pos)) < 2e-4
    bv = read_bvh(bvh)
    max_bvh = max(qdiff(bv["rot"][n], dec[n]) for n in NAMES)
    assert max_bvh < 0.02, f"bvh vs anim {max_bvh} deg"
    assert length(sub(bv["pelvis"], b.pelvis_pos)) < 1e-4
    assert all(qangle(bv["frame0"][n]) < 1e-9 for n in NAMES)
    assert abs(bv["duration"] - DURATION) < 1e-6
    return dec, dpos, {"anim_max_err_deg": round(max_anim, 4), "bvh_vs_anim_max_err_deg": round(max_bvh, 4)}


# ---------------------------------------------------------------------------------------------
# previews (Blender, Cycles): the figure is built with fk() from the rotations read back from
# the .anim, so what is rendered is what SL will play
# ---------------------------------------------------------------------------------------------
COLORS = {"L": (0.15, 0.35, 0.85, 1), "R": (0.85, 0.2, 0.12, 1), "C": (0.82, 0.74, 0.62, 1),
          "palm": (1.0, 0.85, 0.05, 1), "cap": (0.98, 0.98, 0.98, 1), "nose": (0.25, 0.15, 0.1, 1),
          "prop": (0.55, 0.42, 0.28, 0.3), "iron": (0.2, 0.2, 0.22, 0.6), "floor": (0.32, 0.32, 0.34, 1),
          "text": (0.02, 0.02, 0.02, 1)}


class Mesh:
    def __init__(self):
        self.v, self.f, self.m = [], [], []

    def _rf(self, d):
        d = norm(d)
        a = perp((0, 0, 1) if abs(d[2]) < 0.9 else (1, 0, 0), d)
        return a, cross(d, a)

    def cyl(self, p0, p1, r, mat, n=14, caps=True):
        d = sub(p1, p0)
        if length(d) < 1e-6:
            return
        a, c = self._rf(d)
        base = len(self.v)
        for p in (p0, p1):
            for i in range(n):
                t = 2 * math.pi * i / n
                self.v.append(add(p, add(mul(a, r * math.cos(t)), mul(c, r * math.sin(t)))))
        for i in range(n):
            j = (i + 1) % n
            self.f.append((base + i, base + j, base + n + j, base + n + i))
            self.m.append(mat)
        if caps:
            self.f.append(tuple(base + i for i in reversed(range(n))))
            self.m.append(mat)
            self.f.append(tuple(base + n + i for i in range(n)))
            self.m.append(mat)

    def ell(self, c, q, radii, mat, nu=16, nv=10):
        base = len(self.v)
        for j in range(1, nv):
            ph = math.pi * j / nv
            for i in range(nu):
                th = 2 * math.pi * i / nu
                p = (radii[0] * math.sin(ph) * math.cos(th), radii[1] * math.sin(ph) * math.sin(th),
                     radii[2] * math.cos(ph))
                self.v.append(add(c, qrot(q, p)))
        top = len(self.v)
        self.v.append(add(c, qrot(q, (0, 0, radii[2]))))
        bot = len(self.v)
        self.v.append(add(c, qrot(q, (0, 0, -radii[2]))))
        for j in range(nv - 2):
            for i in range(nu):
                k = (i + 1) % nu
                self.f.append((base + j * nu + i, base + j * nu + k, base + (j + 1) * nu + k, base + (j + 1) * nu + i))
                self.m.append(mat)
        for i in range(nu):
            k = (i + 1) % nu
            self.f.append((top, base + k, base + i))
            self.m.append(mat)
            last = base + (nv - 2) * nu
            self.f.append((bot, last + i, last + k))
            self.m.append(mat)

    def sph(self, c, r, mat):
        self.ell(c, QI, (r, r, r), mat, 12, 8)

    def capsule(self, p0, p1, r, mat):
        self.cyl(p0, p1, r, mat, caps=False)
        self.sph(p0, r, mat)
        self.sph(p1, r, mat)

    def box(self, lo, hi, mat):
        base = len(self.v)
        for z in (lo[2], hi[2]):
            for (x, y) in ((lo[0], lo[1]), (hi[0], lo[1]), (hi[0], hi[1]), (lo[0], hi[1])):
                self.v.append((x, y, z))
        for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
            self.f.append(tuple(base + i for i in f))
            self.m.append(mat)


def figure(mesh, W, P):
    C = "C"
    pel = P["mPelvis"]
    mesh.ell(add(pel, qrot(W["mPelvis"], (-0.01, 0, -0.03))), W["mPelvis"], (0.11, 0.16, 0.10), C)
    mesh.capsule(pel, P["mTorso"], 0.085, C)
    mesh.capsule(P["mTorso"], P["mChest"], 0.095, C)
    mesh.ell(add(P["mChest"], qrot(W["mChest"], (0.01, 0, 0.12))), W["mChest"], (0.11, 0.17, 0.15), C)
    mesh.capsule(P["mNeck"], P["mHead"], 0.045, C)
    hc = add(P["mHead"], qrot(W["mHead"], (0.015, 0, 0.075)))
    mesh.ell(hc, W["mHead"], (0.10, 0.08, 0.115), C)
    mesh.sph(add(P["mHead"], qrot(W["mHead"], (0.11, 0, 0.055))), 0.025, "nose")
    for s in "LR":
        k = SIDE[s]
        co, sh, el, wr = ARM[s]
        mesh.capsule(P[co], P[sh], 0.035, s)
        mesh.capsule(P[sh], P[el], 0.048, s)
        mesh.capsule(P[el], P[wr], 0.04, s)
        mesh.sph(add(P[el], qrot(W[sh], (-0.045, 0, 0))), 0.02, "cap")              # elbow point
        hw = W[wr]
        mesh.ell(add(P[wr], qrot(hw, (0.0, 0.085 * k, 0.0))), hw, (0.045, 0.085, 0.018), s)
        mesh.capsule(add(P[wr], qrot(hw, (0.03, 0.03 * k, -0.01))), add(P[wr], qrot(hw, (0.065, 0.085 * k, -0.02))),
                     0.013, s)                                                     # thumb
        mesh.sph(add(P[wr], qrot(hw, (0.0, 0.085 * k, -0.02))), 0.024, "palm")      # palm side
        hp, kn, an = LEG[s]
        mesh.capsule(P[hp], P[kn], 0.07, s)
        mesh.capsule(P[kn], P[an], 0.052, s)
        mesh.sph(add(P[kn], qrot(W[hp], (0.06, 0, 0))), 0.028, "cap")               # knee cap
        ball = end_point(W, P, an)
        toe = end_point(W, P, an, add(END[an], TOE))
        heel = add(P[an], qrot(W[an], (-0.04, 0, -0.06)))
        mesh.capsule(heel, ball, 0.04, s)
        mesh.capsule(P[an], ball, 0.04, s)
        mesh.capsule(ball, toe, 0.03, s)
    mesh.capsule(P["mHipLeft"], P["mHipRight"], 0.06, C)


def props_mesh(mesh, props):
    for p in props:
        if p[0] == "box":
            mesh.box(p[1], p[2], p[3])
        else:
            mesh.cyl(p[1], p[2], p[3], p[4], n=24)


def blender_bvh_check(names):
    """Independent check of the .bvh: import it with Blender's own BVH importer and compare the
    joint positions of the posed frame with fk() of the rotations read back from the .anim."""
    import bpy
    import addon_utils
    import numpy as np

    addon_utils.enable("io_anim_bvh", default_set=True)
    out = {}
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_anim.bvh(filepath=os.path.join(OUT, f"{name}.bvh"), global_scale=1.0,
                                rotate_mode="NATIVE", update_scene_fps=False, update_scene_duration=True)
        ob = bpy.context.selected_objects[0]
        sc = bpy.context.scene

        def heads(frame):
            sc.frame_set(frame)
            return {pb.name: np.array(ob.matrix_world @ pb.head) * INCHES for pb in ob.pose.bones}

        with open(os.path.join(OUT, f"{name}.anim"), "rb") as fh:
            a = read_anim(fh.read())
        dec = {n: j["rot"][0][1] for n, j in a["joints"].items()}
        dpos = a["joints"]["mPelvis"]["pos"][0][1]
        _, P0 = fk({}, (0, 0, 0))
        _, P1 = fk(dec, dpos)
        h0, h1 = heads(1), heads(2)
        A = np.array([h0[BVH_NAME[n]] for n in NAMES])
        B = np.array([P0[n] for n in NAMES])
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
        R = Vt.T @ D @ U.T
        rest = np.abs((A - ca) @ R.T + cb - B).max()
        A1 = np.array([h1[BVH_NAME[n]] for n in NAMES])
        B1 = np.array([P1[n] for n in NAMES])
        err = np.abs((A1 - ca) @ R.T + cb - B1).max()
        out[name] = (round(float(rest), 5), round(float(err), 5), round(float(np.linalg.det(R)), 3))
        assert err < 0.002, f"{name}: Blender's BVH import differs from the .anim pose by {err} m"
    return out


def render_previews(items):
    import bpy
    from mathutils import Matrix, Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = 24
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    PW = 2.6
    sc.render.resolution_x = 1350
    sc.render.resolution_y = 480
    sc.render.film_transparent = False
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.78, 0.8, 0.84, 1)
    bg.inputs[1].default_value = 0.9
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam_d.ortho_scale = PW * 3
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
    cam.location = (0, -12, 1.15)
    cam.rotation_euler = (math.pi / 2, 0, 0)
    sc.camera = cam
    for rot, energy in (((0.9, 0.2, -0.6), 3.0), ((1.2, -0.3, 2.4), 1.2)):
        ld = bpy.data.lights.new("sun", "SUN")
        ld.energy = energy
        lo = bpy.data.objects.new("sun", ld)
        lo.rotation_euler = rot
        sc.collection.objects.link(lo)

    mats = {}
    for k, c in COLORS.items():
        m = bpy.data.materials.new(k)
        m.use_nodes = True
        bsdf = m.node_tree.nodes["Principled BSDF"]
        bsdf.inputs["Base Color"].default_value = c
        bsdf.inputs["Roughness"].default_value = 0.65
        if c[3] < 1:
            bsdf.inputs["Alpha"].default_value = c[3]
        if k == "text":
            bsdf.inputs["Emission Color"].default_value = c
        mats[k] = m

    panels = [("front", -90.0, 0.0), ("left side", 180.0, 0.0), ("3/4 from above", -135.0, 22.0)]
    for name, W, P, props, info in items:
        for o in list(sc.collection.objects):
            if o.type in ("MESH", "FONT"):
                bpy.data.objects.remove(o, do_unlink=True)
        for i, (label, yaw, tilt) in enumerate(panels):
            mesh = Mesh()
            figure(mesh, W, P)
            props_mesh(mesh, props)
            rz = Matrix.Rotation(math.radians(yaw), 4, "Z")
            pts = [rz @ Vector(v) for v in mesh.v]
            figpts = pts[:]
            xs = [p.x for p in figpts]
            cx = (min(xs) + max(xs)) / 2
            px = (i - 1) * PW
            if tilt:
                zs = [p.z for p in figpts]
                cz = (min(zs) + max(zs)) / 2
                rx = Matrix.Rotation(math.radians(tilt), 4, "X")
                pts = [rx @ (p - Vector((cx, 0, cz))) + Vector((px, 0, 1.15)) for p in pts]
            else:
                pts = [p - Vector((cx - px, 0, 0)) for p in pts]
            me = bpy.data.meshes.new(f"{name}_{i}")
            me.from_pydata([tuple(p) for p in pts], [], mesh.f)
            keys = list(COLORS)
            for k in keys:
                me.materials.append(mats[k])
            idx = [keys.index(m) for m in mesh.m]
            me.polygons.foreach_set("material_index", idx)
            me.update()
            ob = bpy.data.objects.new(f"{name}_{i}", me)
            sc.collection.objects.link(ob)
            cu = bpy.data.curves.new(f"t{i}", "FONT")
            cu.body = f"{name}  {label}" if i == 0 else label
            cu.size = 0.11
            to = bpy.data.objects.new(f"t{i}", cu)
            to.data.materials.append(mats["text"])
            to.location = (px - PW / 2 + 0.06, -3, 2.42)
            to.rotation_euler = (math.pi / 2, 0, 0)
            sc.collection.objects.link(to)
        cu = bpy.data.curves.new("info", "FONT")
        cu.body = info
        cu.size = 0.075
        to = bpy.data.objects.new("info", cu)
        to.data.materials.append(mats["text"])
        to.location = (-1.5 * PW + 0.06, -3, -0.2)
        to.rotation_euler = (math.pi / 2, 0, 0)
        sc.collection.objects.link(to)
        sc.render.filepath = os.path.join(PREV, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("  rendered", sc.render.filepath, flush=True)


# ---------------------------------------------------------------------------------------------
def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    os.makedirs(PREV, exist_ok=True)
    report_path = os.path.join(OUT, "poses.json")
    report = {}
    if os.path.exists(report_path):
        try:
            with open(report_path) as fh:
                report = json.load(fh)
        except ValueError:
            report = {}
    items = []
    for fn in POSES:
        name = fn.__name__
        if only and name not in only:
            continue
        b = build(fn)
        data = anim_bytes(b.loc, b.pelvis_pos, b.hand_pose)
        bvh = bvh_text(b.loc, b.pelvis_pos)
        with open(os.path.join(OUT, f"{name}.anim"), "wb") as fh:
            fh.write(data)
        with open(os.path.join(OUT, f"{name}.bvh"), "w") as fh:
            fh.write(bvh)
        dec, dpos, rt = verify(b, data, bvh)
        W, P = fk(dec, dpos)
        miss = {}
        for j, tgt, label in b.targets:
            miss[label] = round(length(sub(P[j], tgt)), 3)
        limbs = limb_report(dec, W, P)
        ct = contacts(W, P)
        report[name] = {"doc": fn.__doc__, "pelvis_offset_m": [round(c, 3) for c in dpos],
                        "hand_pose": b.hand_pose, "anim_bytes": len(data), "roundtrip": rt,
                        "target_miss_m": miss, "limbs_deg": limbs, "contacts_ground_m": ct, "notes": b.notes}
        print(f"{name}: pelvis {tuple(round(c, 3) for c in dpos)}  {rt}  miss {miss}")
        print("    limbs", limbs)
        print("    contacts", ct, b.notes)
        info = (f"pelvis offset z {dpos[2]:+.2f} m   hand pose {b.hand_pose}   "
                f"blue = left, red = right, yellow = palm, white = knee cap / elbow point, "
                f"brown dot = nose   (ground = soles of a standing avatar)")
        items.append((name, W, P, b.props, info))
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=1)
    if "--no-render" not in sys.argv:
        chk = blender_bvh_check([it[0] for it in items])
        for n, v in chk.items():
            print(f"  blender bvh import {n}: rest fit {v[0]} m, pose max error {v[1]} m, det {v[2]}")
            report[n]["blender_bvh_import_max_err_m"] = v[1]
        with open(report_path, "w") as fh:
            json.dump(report, fh, indent=1)
        render_previews(items)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
THE VILLA - pose animations for the furniture and the pool (Second Life).

    python villa/scripts/vposes.py                     # build, verify and render everything
    python villa/scripts/vposes.py --no-render         # files and checks only (bpy not needed)
    python villa/scripts/vposes.py --only villa_lounge,villa_cuddle
    python villa/scripts/vposes.py --samples 12        # quicker previews

Writes, for every animation:

    output/animations/<name>.anim           SL internal format: Build > Upload > Bulk takes it as is
    output/animations/<name>.bvh            fallback for Build > Upload > Animation (one by one:
                                            set priority 4, Loop on, In 0 %, Out 100 %, ease 0.3 s)
    output/animations/previews/<name>.png   three views of a capsule body posed with the rotations
                                            READ BACK from the .anim, with the furniture it is for
    output/animations/poses.json            per animation: furniture, pelvis offset, contacts,
                                            suggested sit target, pair offset (couples), checks

The format, skeleton, forward kinematics and pose builder come from the_pit/scripts/poses.py
(imported, not modified): the facts about LLKeyframeMotion, the 19 joints of
avatar_skeleton.xml, quantisation and the BVH loader are documented there.  This file adds:

* a writer for any number of keys (poses.py writes two identical keys); the static poses are
  checked to be byte-identical to poses.py's writer, and villa_swim is a real 2 s cycle;
* a collision body (capsules sized like an average SL mesh body) used for three checks:
  limbs against the own body, against the partner (couples) and against the furniture
  (soft cushions may sink a few cm, hard stone / wood may not);
* weight: the centre of mass (segment masses of Dempster / de Leva) against the support polygon
  of the contacts with the furniture (and the partner), and joint range-of-motion limits;
* a suggested sit target per animation for a seat whose top surface is at the stated height.

Frames: avatar X forward, Y left, Z up.  "Ground" coordinates put the soles of a standing avatar
at z = 0 and its root (the default pelvis) at z = ROOT_Z = 1.067.  Vertical convention (as in
SL's built-in "sit" / "sit_ground" / "sleep"): seated poses keep the pelvis at its default height,
floor and bed poses are lowered so the surface they lie on is near z = 0, standing poses in the
pool stand on z = 0, and floating poses keep the body around the root (like "fly").

Sit target: SL puts the avatar root about LIFT = 0.35 m above the llSitTarget point
(0.4 m minus the agent-size correction ~0.05 m of an average 1.9 m agent).  For each animation the
anchor is a named point of the furniture (e.g. the seat top under the sit bones); with the prim
origin on the floor directly below the anchor and the prim's +X the way the avatar faces,

    llSitTarget(<-ax, -ay, h + ROOT_Z - az - LIFT>, llEuler2Rot(<0, 0, yaw> * DEG_TO_RAD))

where (ax, ay, az) is the anchor in ground coordinates and h its height in the furniture.
Couples: both animations share one frame (A's); the pair offset is B's root relative to A's
root (in A's frame) plus B's yaw, so B's sit target = A's sit target + offset, rot = A's * yaw.
"""
import json
import math
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
VILLA = os.path.dirname(HERE)
REPO = os.path.dirname(VILLA)
sys.path.insert(0, os.path.join(REPO, "the_pit", "scripts"))

import poses as PZ  # noqa: E402  (the_pit/scripts/poses.py: skeleton, FK, builder, .anim / .bvh)
from poses import (  # noqa: E402
    ARM, BVH_NAME, CHILDREN, END, HAND_RELAXED, INCHES, LEG, MAX_PELVIS_OFFSET, NAMES, OFF, PARENT,
    QI, ROOT_Z, SIDE, TOE, Builder, Mesh, add, angle, cross, dot, euler_xzy, f2u, fk, length, mul, norm,
    perp, q_bvh_to_sl, q_sl_to_bvh, qangle, qaxis, qconj, qdiff, qmul, qnorm, qrot, qx, qy, qz,
    qarc, read_anim, signed_twist, sl_to_bvh, sub, swing_twist, u2f)

OUT = os.path.join(VILLA, "output", "animations")
PREV = os.path.join(OUT, "previews")

PRIORITY = 4
DURATION = 1.0           # static poses: two identical keys at 0 and DURATION (as poses.py)
EASE = (0.3, 0.3)
LIFT = 0.35              # avatar root over the sit target point (see the docstring)
SINK_SOFT = 0.025        # how far a seated body presses into an upholstered seat
SEAT = {"sofa": 0.43, "chair": 0.46, "stool": 0.75, "stool_footrest": 0.25, "bed": 0.55,
        "lounger": 0.38, "cushion": 0.12, "pool_edge": 0.0, "pool_floor": -1.3, "spa_seat": -0.5}
SOLE = 0.067             # ankle joint over the sole of a flat foot (standing: ROOT_Z - 1.0)


# ---------------------------------------------------------------------------------------------
# small helpers
# ---------------------------------------------------------------------------------------------
def lerp(a, b, t):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def r3(v, n=3):
    return [round(c, n) for c in v]


def rotz_v(v, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return (c * v[0] - s * v[1], s * v[0] + c * v[1], v[2])


def seg_dist(p0, p1, q0, q1):
    """Closest distance between segments p0p1 and q0q1, and the parameters (s, t)."""
    d1, d2, r = sub(p1, p0), sub(q1, q0), sub(p0, q0)
    a, e, f = dot(d1, d1), dot(d2, d2), dot(d2, r)
    if a < 1e-12 and e < 1e-12:
        return length(r), 0.0, 0.0
    if a < 1e-12:
        s, t = 0.0, min(1.0, max(0.0, f / e))
    else:
        c = dot(d1, r)
        if e < 1e-12:
            t, s = 0.0, min(1.0, max(0.0, -c / a))
        else:
            b = dot(d1, d2)
            den = a * e - b * b
            s = min(1.0, max(0.0, (b * f - c * e) / den)) if den > 1e-12 else 0.0
            t = (b * s + f) / e
            if t < 0:
                t, s = 0.0, min(1.0, max(0.0, -c / a))
            elif t > 1:
                t, s = 1.0, min(1.0, max(0.0, (b - c) / a))
    cp = add(p0, mul(d1, s))
    cq = add(q0, mul(d2, t))
    return length(sub(cp, cq)), s, t


# ---------------------------------------------------------------------------------------------
# collision body: capsules in the proportions of an average SL mesh body on the SL skeleton
# (name, joint frame, start, end (joint-local offsets or another joint), radius, colour)
# ---------------------------------------------------------------------------------------------
def body_caps(W, P):
    def at(j, o):
        return add(P[j], qrot(W[j], o))

    caps = [("pelvis", at("mPelvis", (-0.03, 0.07, -0.04)), at("mPelvis", (-0.03, -0.07, -0.04)), 0.10, "C")]
    for k, tag in ((1, "l"), (-1, "r")):
        caps.append((f"belly_{tag}", at("mTorso", (0.0, 0.055 * k, -0.04)), at("mTorso", (0.0, 0.055 * k, 0.15)), 0.095, "C"))
        caps.append((f"chest_{tag}", at("mChest", (0.005, 0.045 * k, -0.01)), at("mChest", (0.005, 0.04 * k, 0.13)), 0.10, "C"))
    caps.append(("neck", P["mNeck"], at("mHead", (0.0, 0.0, 0.0)), 0.05, "C"))
    caps.append(("head", at("mHead", (0.015, 0.0, 0.035)), at("mHead", (0.015, 0.0, 0.115)), 0.088, "C"))
    for s in "LR":
        k = SIDE[s]
        co, sh, el, wr = ARM[s]
        caps.append((f"uarm_{s}", P[sh], P[el], 0.045, s))
        caps.append((f"farm_{s}", P[el], P[wr], 0.037, s))
        caps.append((f"hand_{s}", at(wr, (0.0, 0.02 * k, -0.003)), at(wr, (0.0, 0.10 * k, -0.008)), 0.025, s))
        hp, kn, an = LEG[s]
        caps.append((f"thigh_{s}", P[hp], P[kn], 0.07, s))
        caps.append((f"shin_{s}", P[kn], P[an], 0.05, s))
        caps.append((f"foot_{s}", at(an, (-0.05, 0.0, -0.035)), at(an, (0.112, 0.0, -0.035)), 0.032, s))
        caps.append((f"toes_{s}", at(an, (0.112, 0.0, -0.035)), at(an, (0.20, 0.0, -0.045)), 0.022, s))
    return caps


TRUNK = {"pelvis", "belly_l", "belly_r", "chest_l", "chest_r", "neck", "head"}


def part(name):
    """('arm'|'leg'|'trunk', side or '')"""
    if name in TRUNK:
        return "trunk", ""
    kind, s = name.split("_")
    return ("arm" if kind in ("uarm", "farm", "hand") else "leg"), s


def self_pair_rule(a, b):
    """None = skip, else (trim of a from its start, trim of b, tolerance in m)."""
    pa, sa = part(a)
    pb, sb = part(b)
    ka, kb = a.split("_")[0], b.split("_")[0]
    if pa == "trunk" and pb == "trunk":
        return None
    if pa == pb and sa == sb:                                  # same limb: only non-neighbours
        chain = ["uarm", "farm", "hand"] if pa == "arm" else ["thigh", "shin", "foot", "toes"]
        if abs(chain.index(ka) - chain.index(kb)) <= 1 or {ka, kb} == {"shin", "toes"}:
            return None
        return (0.0, 0.0, 0.02)
    if pa == "trunk" or pb == "trunk":
        limb_first = pb == "trunk"
        kl, kt = (ka, b) if limb_first else (kb, a)
        if kl == "uarm":
            if kt == "neck":
                return None
            trim, tol = (0.45 if kt.startswith("chest") else 0.0), 0.035
        elif kl == "thigh":
            if kt == "pelvis":
                return None
            trim, tol = (0.3 if kt.startswith("belly") else 0.0), 0.035
        else:
            trim, tol = 0.0, (0.02 if kl in ("hand", "foot", "toes") else 0.03)
        return (trim, 0.0, tol) if limb_first else (0.0, trim, tol)
    return (0.0, 0.0, 0.03 if {ka, kb} <= {"thigh", "shin", "uarm", "farm"} else 0.02)


def trim_seg(p0, p1, f):
    return (lerp(p0, p1, f), p1) if f else (p0, p1)


# ---------------------------------------------------------------------------------------------
# props: oriented boxes and capped cylinders with a signed distance (for the contact checks)
# ---------------------------------------------------------------------------------------------
TOL = {"soft": 0.05, "hard": 0.012}


class Prop:
    def __init__(self, shape, kind, color, label, **kw):
        self.shape, self.kind, self.color, self.label = shape, kind, color, label
        self.__dict__.update(kw)

    def sdf(self, p):
        if self.shape == "box":
            d = qrot(qconj(self.q), sub(p, self.c))
            e = [abs(d[i]) - self.h[i] for i in range(3)]
            out = length([max(x, 0.0) for x in e])
            return out + min(max(e), 0.0)
        a, b, r = self.a, self.b, self.r
        ax = sub(b, a)
        L = length(ax)
        u = mul(ax, 1 / L)
        t = dot(sub(p, a), u)
        radial = length(sub(sub(p, a), mul(u, t)))
        dr = radial - r
        dz = abs(t - L / 2) - L / 2
        return length((max(dr, 0.0), max(dz, 0.0), 0.0)) + min(max(dr, dz), 0.0)

    def mesh(self, m):
        if self.shape == "box":
            base = len(m.v)
            for z in (-1, 1):
                for (x, y) in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
                    m.v.append(add(self.c, qrot(self.q, (x * self.h[0], y * self.h[1], z * self.h[2]))))
            for f in ((0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                m.f.append(tuple(base + i for i in f))
                m.m.append(self.color)
        else:
            m.cyl(self.a, self.b, self.r, self.color, n=28)


# ---------------------------------------------------------------------------------------------
# actors and scenes
# ---------------------------------------------------------------------------------------------
class VBuilder(Builder):
    """poses.py's Builder plus a placement in the scene (couples: B's frame in A's frame)."""

    def __init__(self, name, place=(0.0, 0.0, 0.0, 0.0)):
        super().__init__(name)
        self.place = place      # dx, dy, dz, yaw (deg) of this avatar's ground frame in the scene

    def W(self, p):
        """local ground point -> scene point"""
        return add(rotz_v(p, self.place[3]), self.place[:3])

    def Wd(self, v):
        return rotz_v(v, self.place[3])

    def L(self, p):
        """scene point -> local ground point"""
        return rotz_v(sub(p, self.place[:3]), -self.place[3])

    def Ld(self, v):
        return rotz_v(v, -self.place[3])

    def scene_fk(self, local=None, pelvis_pos=None):
        Wl, Pl = fk(local or self.loc, self.pelvis_pos if pelvis_pos is None else pelvis_pos)
        qz_ = qz(self.place[3])
        return {n: qmul(qz_, q) for n, q in Wl.items()}, {n: self.W(p) for n, p in Pl.items()}

    def caps(self):
        return body_caps(*self.scene_fk())

    def cap(self, name):
        return next(c for c in self.caps() if c[0] == name)

    def lowest(self, names):
        """Lowest surface point (scene z) of the named capsules."""
        return min(min(c[1][2], c[2][2]) - c[3] for c in self.caps() if c[0] in names)

    def surface_x(self, names, back=True):
        caps = [c for c in self.caps() if c[0] in names]
        if back:
            return min(min(c[1][0], c[2][0]) - c[3] for c in caps)
        return max(max(c[1][0], c[2][0]) + c[3] for c in caps)

    def spos(self, n):
        return self.scene_fk()[1][n]

    def back_plane_x(self, seat_top, recline, names=("pelvis", "belly_l", "belly_r", "chest_l", "chest_r"),
                     sink=0.02):
        """x where a back cushion reclined by `recline` deg, rising from (x, seat_top), touches the
        back of the named capsules (pressed in by `sink`)."""
        th = math.radians(recline)
        best = 1e9
        for c in self.caps():
            if c[0] not in names:
                continue
            pts, r = samples(c, 0.01)
            for p in pts:
                best = min(best, (p[0] * math.cos(th) + (p[2] - seat_top) * math.sin(th) - r + sink) / math.cos(th))
        return best

    def reach(self, arm_side, target_fn, fmax, slack=0.92):
        """target_fn(frac) -> point; the largest frac <= fmax the arm reaches with its elbow bent
        (shoulder-wrist distance <= slack * arm length)."""
        sh = self.fk()[1][ARM[arm_side][1]]
        lim = slack * (length(OFF[ARM[arm_side][2]]) + length(OFF[ARM[arm_side][3]]))
        lo, hi = 0.0, fmax
        if length(sub(target_fn(hi), sh)) <= lim:
            return target_fn(hi)
        for _ in range(30):
            mid = (lo + hi) / 2
            if length(sub(target_fn(mid), sh)) <= lim:
                lo = mid
            else:
                hi = mid
        return target_fn(lo)

    # --- placement helpers (LOCAL ground coordinates unless the name says scene) ----------------
    def drop(self, names, z):
        """Shift the pelvis vertically so the lowest surface of the named capsules is at local z."""
        low = min(min(c[1][2], c[2][2]) - c[3] for c in body_caps(*self.fk()) if c[0] in names)
        x, y, oz = self.pelvis_pos
        self.pelvis_pos = (x, y, oz + z - low)

    def lowest_local(self, names):
        return min(min(c[1][2], c[2][2]) - c[3] for c in body_caps(*self.fk()) if c[0] in names)

    def limb_surface(self, kind, side, frac, around=0.0, ref=(0.0, 0.0, 1.0)):
        """Point on the skin of a limb capsule (thigh, shin, uarm, farm), `frac` from its upper joint,
        and the outward normal there.  The normal is `ref` made perpendicular to the limb, turned
        `around` degrees about the limb toward the avatar's left (+) / right (-).  Returns
        (point, normal, limb direction)."""
        j0, j1, r = {"thigh": (LEG[side][0], LEG[side][1], 0.07), "shin": (LEG[side][1], LEG[side][2], 0.05),
                     "uarm": (ARM[side][1], ARM[side][2], 0.045), "farm": (ARM[side][2], ARM[side][3], 0.037)}[kind]
        _, P = self.fk()
        d = norm(sub(P[j1], P[j0]))
        up = perp(ref, d)
        left = norm(cross(up, d))
        if dot(left, (0, 1, 0)) < 0 and abs(d[2]) < 0.9:
            left = mul(left, -1)
        a = math.radians(around)
        n = norm(add(mul(up, math.cos(a)), mul(left, math.sin(a))))
        return add(lerp(P[j0], P[j1], frac), mul(n, r)), n, d

    def body_point(self, joint, off, normal):
        """Local point and normal from a joint-frame offset and normal."""
        W, P = self.fk()
        return add(P[joint], qrot(W[joint], off)), qrot(W[joint], normal)

    def hand_back(self, side):
        """(point on the back of the hand, its normal, finger direction) in local coordinates."""
        W, P = self.fk()
        wr = ARM[side][3]
        k = SIDE[side]
        n = qrot(W[wr], (0, 0, 1))
        c = add(P[wr], qrot(W[wr], (0.0, 0.065 * k, -0.005)))
        return add(c, mul(n, 0.025)), n, qrot(W[wr], (0, k, 0))

    def arm_pen(self, side, others=(), props=()):
        """Excess penetration (m, summed) of this arm into the own body, `others` (scene capsules of
        a partner) and solid `props` (scene), beyond the check tolerances minus a small margin."""
        names = {f"uarm_{side}", f"farm_{side}", f"hand_{side}"}
        caps = self.caps()
        pen = 0.0
        for a in caps:
            if a[0] not in names:
                continue
            for c in caps:
                if c[0] in names:
                    continue
                rule = self_pair_rule(a[0], c[0])
                if rule is None:
                    continue
                ta, tb, tol = rule
                pa, pb = trim_seg(a[1], a[2], ta), trim_seg(c[1], c[2], tb)
                pen += max(0.0, a[3] + c[3] - seg_dist(pa[0], pa[1], pb[0], pb[1])[0] - tol + 0.008)
            for c in others:
                pen += max(0.0, a[3] + c[3] - seg_dist(a[1], a[2], c[1], c[2])[0] - 0.022)
            if props:
                pts, r = samples(a, 0.03)
                for pr in props:
                    if pr.kind != "water":
                        pen += max(0.0, max(r - pr.sdf(p) for p in pts) - TOL[pr.kind] + 0.008)
        return pen

    def place_arm(self, side, wrist, pole, hand=None, palm=None, spread=90, others=(), props=(), flex=0.0,
                  dev=0.02):
        """Two-bone IK to `wrist` (local) choosing, among poles turned up to `spread` deg about the
        shoulder-wrist line, the one with the least skin twist (shoulder and forearm roll), wrist
        bend and penetration of the arm into the body, the partner and the furniture."""
        _, sh, el, wr = ARM[side]
        keep, nt = dict(self.loc), len(self.targets)
        axis = norm(sub(wrist, self.pos(sh)))
        best = None
        for a in range(-int(spread), int(spread) + 1, 5):
            pl = qrot(qaxis(axis, a), pole)
            self.loc = dict(keep)
            del self.targets[nt:]
            self._arm(side, wrist, pl, None, None, None, hand, palm, flex)
            ut = signed_twist(self.loc[sh], norm(OFF[el]))
            fr = signed_twist(self.loc[el], norm(OFF[wr]))
            wb = qangle(self.loc[wr])
            pen = self.arm_pen(side, others, props)
            cost = (ut * ut + fr * fr + dev * a * a + 4e6 * pen * pen + 8 * max(0.0, wb - 50) ** 2
                    + 30 * max(0.0, abs(ut) - 80) ** 2 + 30 * max(0.0, abs(fr) - 80) ** 2)
            if best is None or cost < best[0]:
                best = (cost, a, pl, ut, fr, pen)
        self.loc = dict(keep)
        del self.targets[nt:]
        self._arm(side, wrist, best[2], None, None, None, hand, palm, flex)
        self.notes.append(f"{side} arm pole turned {best[1]:+d} deg (shoulder roll {best[3]:.0f}, forearm roll "
                          f"{best[4]:.0f}, residual penetration {best[5] * 100:.1f} cm)")

    def palm_on(self, side, pt, normal, fingers, back=False, pole=None, spread=90, others=(), props=(),
                lift=0.0, dev=0.02):
        """Rest the palm (or with back=True the back of the hand) on a surface: pt = the skin / surface
        point under the middle of the hand, normal = out of that surface, fingers = where they point."""
        n = norm(normal)
        h = perp(fingers, n)
        wrist = add(add(pt, mul(h, -0.065)), mul(n, 0.031 + lift))
        k = SIDE[side]
        self.place_arm(side, wrist, pole or (-0.4, 0.9 * k, -0.5), hand=h, palm=n if back else mul(n, -1),
                       spread=spread, others=others, props=props, dev=dev)
        return wrist

    def palm_reach(self, side, fn, fmax=1.0, fmin=0.0, slack=0.95, **kw):
        """palm_on at the largest f in [fmin, fmax] whose wrist the arm reaches with the elbow still
        bent (shoulder-wrist <= slack * arm length); fn(f) -> (point, normal, fingers)."""
        sh = self.pos(ARM[side][1])
        lim = slack * (length(OFF[ARM[side][2]]) + length(OFF[ARM[side][3]]))

        def wrist(f):
            pt, n, h = fn(f)
            n = norm(n)
            h = perp(h, n)
            return add(add(pt, mul(h, -0.065)), mul(n, 0.031 + kw.get("lift", 0.0)))

        lo, hi = fmin, fmax
        if length(sub(wrist(hi), sh)) > lim:
            for _ in range(30):
                mid = (lo + hi) / 2
                if length(sub(wrist(mid), sh)) <= lim:
                    lo = mid
                else:
                    hi = mid
            hi = lo
        pt, n, h = fn(hi)
        self.palm_on(side, pt, n, h, **kw)
        return hi

    def foot_on(self, side, ball, plantar, pole, iters=6):
        """Ankle IK so that the sole under the ball of the foot (mFoot) rests on `ball` (local) with
        the foot plantar-flexed `plantar` deg from the shin's normal."""
        an = LEG[side][2]
        target = add(ball, (-0.112, 0.0, 0.067))
        for _ in range(iters):
            self.leg(side, ankle=target, pole=pole, foot=plantar)
            W, P = self.fk()
            got = add(P[an], qrot(W[an], (0.112, 0.0, -0.067)))
            target = add(target, sub(ball, got))
        self.leg(side, ankle=target, pole=pole, foot=plantar)

    def leg_knee(self, side, knee, shin, foot="flat", pole=(1, 0, 0)):
        """Leg by the direction to a knee point (local) and a world shin direction."""
        hp = LEG[side][0]
        self.leg(side, thigh=sub(knee, self.pos(hp)), shin=shin, pole=pole, foot=foot)


class Anchor:
    def __init__(self, point, height, what):
        self.point, self.height, self.what = tuple(point), height, what


class Scene:
    def __init__(self, name, doc):
        self.name, self.doc = name, doc
        self.actors = []
        self.props = []
        self.anchor = None
        self.furniture = ""
        self.views = "seated"
        self.buoyant = False
        self.notes = []
        self.keys = None          # animated: function(scene) filling actor.anim_keys
        self.duration = DURATION
        self.nkeys = 2
        self.water_z = None       # scene z of the water surface (pool poses)
        self.pair_note = ""

    def actor(self, name, place=(0.0, 0.0, 0.0, 0.0)):
        a = VBuilder(name, place)
        self.actors.append(a)
        return a

    def box(self, lo, hi, kind="soft", color="fabric", label=""):
        c = mul(add(lo, hi), 0.5)
        h = mul(sub(hi, lo), 0.5)
        self.props.append(Prop("box", kind, color, label, c=c, h=h, q=QI))

    def obox(self, c, size, q=QI, kind="soft", color="fabric", label=""):
        self.props.append(Prop("box", kind, color, label, c=tuple(c), h=mul(size, 0.5), q=q))

    def cyl(self, a, b, r, kind="hard", color="metal", label=""):
        self.props.append(Prop("cyl", kind, color, label, a=tuple(a), b=tuple(b), r=r))

    def water(self, z, lo, hi):
        self.water_z = z
        self.props.append(Prop("box", "water", "water", "water", c=((lo[0] + hi[0]) / 2, (lo[1] + hi[1]) / 2, z - 0.005),
                               h=((hi[0] - lo[0]) / 2, (hi[1] - lo[1]) / 2, 0.005), q=QI))

    def floor(self, z, lo=(-0.8, -0.8), hi=(0.9, 0.8), color="floor", label="floor"):
        self.box((lo[0], lo[1], z - 0.03), (hi[0], hi[1], z), "hard", color, label)


POSES = []


def pose(fn):
    POSES.append(fn)
    return fn


# ---------------------------------------------------------------------------------------------
# shared furniture (scene coordinates; x = the way the avatar faces).  Sizes follow the villa's
# furniture: the Orbit sofa of furniture/reference.py (seat 0.43 m, back leaning 12 deg, 0.50 m over
# the seat, 0.26 m thick, seat ~0.6 m deep) and the heights given for the other pieces.
# ---------------------------------------------------------------------------------------------
SOFA_RECLINE, SOFA_DEPTH, SOFA_BACK_H, SOFA_BACK_T = 12.0, 0.60, 0.50, 0.26
SOFA_DOC = ("sofa (Orbit): seat top 0.43 m, 0.60 m deep, back cushion leaning 12 deg, its top 0.50 m over "
            "the seat")


def sofa(s, seat_top, back_x, y0, y1, floor_z, recline=SOFA_RECLINE, depth=SOFA_DEPTH, back_h=SOFA_BACK_H,
         t=SOFA_BACK_T):
    """Upholstered seat (top seat_top) whose back cushion's front face meets the seat at back_x."""
    s.box((back_x - 0.03, y0, seat_top - 0.19), (back_x + depth, y1, seat_top), "soft", "fabric", "seat cushion")
    s.box((back_x - 0.25, y0 - 0.02, floor_z + 0.07), (back_x + depth - 0.03, y1 + 0.02, seat_top - 0.19), "hard",
          "wood", "plinth")
    q = qy(-recline)
    c = sub((back_x, (y0 + y1) / 2, seat_top), qrot(q, (t / 2, 0.0, -back_h / 2)))
    s.obox(c, (t, y1 - y0, back_h), q, "soft", "fabric", "back cushion")
    s.floor(floor_z, (back_x - 0.35, y0 - 0.1), (back_x + 1.4, y1 + 0.1))


def back_top(back_x, seat_top, recline, back_h, t):
    """Middle of the top face of a reclined back cushion (its front face meets the seat at back_x)
    and the normal of that face."""
    q = qy(-recline)
    up, out = qrot(q, (0, 0, 1)), qrot(q, (1, 0, 0))
    front_top = add((back_x, 0.0, seat_top), mul(up, back_h))
    return sub(front_top, mul(out, t / 2)), up


def thigh_palm(b, sd, frac=0.55, inward=16, turn=14, leg=None, **kw):
    """Rest the hand of side sd on the top of a thigh (its own unless `leg`), fingers along it and
    turned inward, as far toward `frac` as the arm reaches."""
    k = SIDE[sd]
    lg = leg or sd

    def fn(f):
        pt, n, d = b.limb_surface("thigh", lg, f, around=-k * inward)
        return pt, n, rotz_v(d, -k * turn)
    return b.palm_reach(sd, fn, frac, 0.1, **kw)


# ---------------------------------------------------------------------------------------------
# the single poses
# ---------------------------------------------------------------------------------------------
@pose
def villa_sit_relaxed(s):
    """Sofa (seat 0.43 m): leaning back into the cushions, the left arm resting along the top of the
    back, the right hand on the thigh, knees relaxed apart, head turned a little to the left."""
    s.furniture = SOFA_DOC
    b = s.actor("villa_sit_relaxed")
    b.pelvis(pitch=-16, lean=1)
    b.spine("mTorso", pitch=-2)
    b.spine("mChest", pitch=3, lean=2, yaw=4)
    b.spine("mNeck", pitch=8, yaw=6)
    b.spine("mHead", pitch=5, yaw=10, lean=-3)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - SEAT["sofa"]
    back_x = b.back_plane_x(seat, SOFA_RECLINE)
    hx = b.pos("mHipLeft")[0]
    b.leg("L", ankle=(hx + 0.60, 0.25, fl + SOLE), pole=(1, 0.35, 0.1), foot="flat")
    b.leg("R", ankle=(hx + 0.54, -0.17, fl + SOLE), pole=(1, -0.3, 0.1), foot="flat")
    b.collar("L", elev=10, fwd=-6)
    b.collar("R", elev=-4, fwd=4)
    sofa(s, seat, back_x, -0.75, 0.95, fl)
    top, n = back_top(back_x, seat, SOFA_RECLINE, SOFA_BACK_H, SOFA_BACK_T)
    sh = b.pos("mShoulderLeft")
    b.palm_on("L", (top[0], sh[1] + 0.40, top[2]), n, (0.1, 1.0, 0.0), props=s.props, spread=120)
    thigh_palm(b, "R", 0.55, props=s.props)
    s.anchor = Anchor((back_x, 0.0, seat), SEAT["sofa"], "seat top at the foot of the back cushion")
    s.notes.append(f"pelvis joint {b.pos('mPelvis')[0] - back_x:.2f} m in front of the back cushion's foot")


@pose
def villa_sit_crossed(s):
    """Sofa (seat 0.43 m): sitting back, the right leg crossed over the left at the knee, the left hand on
    the crossed knee and the right hand resting on it."""
    s.furniture = SOFA_DOC
    b = s.actor("villa_sit_crossed")
    b.pelvis(pitch=-6, lean=6, yaw=18)
    b.spine("mTorso", pitch=1, lean=-3, yaw=-7)
    b.spine("mChest", pitch=3, yaw=-7, lean=-3)
    b.spine("mNeck", pitch=6, yaw=-3)
    b.spine("mHead", pitch=3, yaw=4, lean=3)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - SEAT["sofa"]
    back_x = b.back_plane_x(seat, SOFA_RECLINE)
    hl, hr = b.pos("mHipLeft"), b.pos("mHipRight")
    over = (0.0, 0.05, 0.125)            # right knee joint over the left one
    best = None
    for i in range(21):                  # place the left foot so the right thigh just reaches over the left knee
        ax = hl[0] + 0.42 + 0.01 * i
        b.leg("L", ankle=(ax, 0.08, fl + SOLE), pole=(1, -0.05, 0.3), foot="flat")
        err = abs(length(sub(add(b.pos("mKneeLeft"), over), hr)) - length(OFF["mKneeRight"]))
        if best is None or err < best[0]:
            best = (err, ax)
    b.leg("L", ankle=(best[1], 0.08, fl + SOLE), pole=(1, -0.05, 0.3), foot="flat")
    kl = b.pos("mKneeLeft")
    b.leg_knee("R", add(kl, over), shin=(0.30, 0.40, -0.86), foot=30)
    b.collar("L", elev=-3, fwd=10)
    b.collar("R", elev=-3, fwd=8)
    sofa(s, seat, back_x, -0.75, 0.95, fl)
    b.palm_reach("L", lambda f: b.limb_surface("thigh", "R", f)[:2] + ((0.25, -1.0, 0.0),), 0.9, 0.4,
                 props=s.props)
    pt, n, f = b.hand_back("L")
    b.palm_on("R", pt, n, (0.4, 1.0, 0.0), props=s.props)
    s.anchor = Anchor((back_x, 0.0, seat), SEAT["sofa"], "seat top at the foot of the back cushion")


@pose
def villa_sit_curl(s):
    """Sofa (seat 0.43 m): curled up cosily, both feet tucked up on the seat beside the right hip
    (side sit), leaning back and to the left, the left arm along the top of the back, the head tilted
    toward it, the right hand on the right thigh."""
    s.furniture = SOFA_DOC
    b = s.actor("villa_sit_curl")
    yaw = 22.0
    b.pelvis(pitch=-12, lean=17, yaw=yaw)
    b.spine("mTorso", pitch=-2, lean=-8, yaw=-4)
    b.spine("mChest", pitch=3, lean=-7, yaw=-8)
    b.spine("mNeck", pitch=6, yaw=-6, lean=-2)
    b.spine("mHead", pitch=4, yaw=-8, lean=9)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - SEAT["sofa"]
    back_x = b.back_plane_x(seat, SOFA_RECLINE)
    pel = b.pos("mPelvis")

    def H(x, y, z):
        """pelvis-heading offset from the pelvis joint -> local point"""
        v = rotz_v((x, y, 0.0), yaw)
        return (pel[0] + v[0], pel[1] + v[1], z)

    lie = seat + 0.05
    b.leg("L", ankle=H(0.44, -0.12, lie), pole=sub(H(0.47, 0.27, lie + 0.07), b.pos("mHipLeft")), foot=35)
    b.leg("R", ankle=H(0.0, -0.43, lie), pole=sub(H(0.40, -0.40, lie + 0.02), b.pos("mHipRight")), foot=50)
    b.collar("L", elev=10, fwd=-6)
    b.collar("R", elev=-4, fwd=6)
    sofa(s, seat, back_x, -0.95, 0.95, fl)
    top, n = back_top(back_x, seat, SOFA_RECLINE, SOFA_BACK_H, SOFA_BACK_T)
    sh = b.pos("mShoulderLeft")
    b.palm_on("L", (top[0], sh[1] + 0.40, top[2]), n, (0.1, 1.0, 0.0), props=s.props, spread=120)
    thigh_palm(b, "R", 0.4, inward=0, turn=0, props=s.props)
    s.anchor = Anchor((back_x, 0.0, seat), SEAT["sofa"], "seat top at the foot of the back cushion")


@pose
def villa_sit_upright(s):
    """Dining chair (seat 0.46 m): upright and elegant, knees together, the right foot a little behind
    the left, hands resting on the thighs."""
    s.furniture = "dining chair: upholstered seat top 0.46 m, 0.46 m deep, back 0.45 m over the seat leaning 6 deg"
    b = s.actor("villa_sit_upright")
    b.pelvis(pitch=3)
    b.spine("mTorso", pitch=-2)
    b.spine("mChest", pitch=-2)
    b.spine("mNeck", pitch=5)
    b.spine("mHead", pitch=2, yaw=5, lean=-1)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - SEAT["chair"]
    back_x = b.back_plane_x(seat, 6.0, sink=0.0)
    hx = b.pos("mHipLeft")[0]
    b.leg("L", ankle=(hx + 0.50, 0.06, fl + SOLE), pole=(1, -0.1, 0.25), foot="flat")
    b.leg("R", ankle=(hx + 0.42, -0.065, fl + SOLE), pole=(1, 0.1, 0.25), foot="flat")
    s.box((back_x - 0.01, -0.24, seat - 0.06), (back_x + 0.46, 0.24, seat), "soft", "fabric", "seat pad")
    s.box((back_x - 0.03, -0.25, seat - 0.10), (back_x + 0.47, 0.25, seat - 0.06), "hard", "wood", "seat shell")
    q = qy(-6.0)
    s.obox(sub((back_x, 0.0, seat), qrot(q, (0.025, 0.0, -0.225))), (0.05, 0.46, 0.45), q, "hard", "wood", "back")
    for x in (back_x + 0.02, back_x + 0.43):
        for y in (-0.21, 0.21):
            s.cyl((x, y, fl), (x, y, seat - 0.10), 0.018, "hard", "wood", "leg")
    s.floor(fl, (back_x - 0.4, -0.5), (back_x + 1.0, 0.5))
    for sd in "LR":
        b.collar(sd, elev=-4, fwd=6)
        thigh_palm(b, sd, 0.58, props=s.props)
    s.anchor = Anchor((back_x, 0.0, seat), SEAT["chair"], "seat top at the foot of the back")


@pose
def villa_sit_stool(s):
    """Bar stool (seat 0.75 m, footrest ring 0.25 m): upright and easy, both feet on the footrest ring,
    the left one a little further round, hands resting on the thighs."""
    s.furniture = "bar stool: round seat top 0.75 m (r 0.19 m), footrest ring at 0.25 m (r 0.26 m)"
    b = s.actor("villa_sit_stool")
    b.pelvis(pitch=5)
    b.spine("mTorso", pitch=2)
    b.spine("mChest", pitch=-1)
    b.spine("mNeck", pitch=3)
    b.spine("mHead", pitch=0, yaw=-6)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - SEAT["stool"]
    cx = b.pos("mPelvis")[0] - 0.01
    ring_z, R = fl + SEAT["stool_footrest"], 0.26
    s.cyl((cx, 0, seat - 0.07), (cx, 0, seat), 0.19, "soft", "fabric", "seat")
    s.cyl((cx, 0, fl + 0.02), (cx, 0, seat - 0.07), 0.035, "hard", "metal", "column")
    s.cyl((cx, 0, fl), (cx, 0, fl + 0.02), 0.24, "hard", "metal", "base")
    n = 16
    for i in range(n):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        s.cyl((cx + R * math.cos(a0), R * math.sin(a0), ring_z), (cx + R * math.cos(a1), R * math.sin(a1), ring_z),
              0.012, "hard", "metal", "footrest ring")
    s.floor(fl, (cx - 0.5, -0.5), (cx + 0.7, 0.5))
    for sd, a, pf in (("L", 28.0, 22.0), ("R", -18.0, 14.0)):
        k = SIDE[sd]
        ball = (cx + R * math.cos(math.radians(a)), R * math.sin(math.radians(a)), ring_z + 0.012)
        b.foot_on(sd, ball, pf, pole=(1, 0.3 * k, 0.3))
    for sd in "LR":
        b.collar(sd, elev=-4, fwd=6)
        thigh_palm(b, sd, 0.6, props=s.props)
    s.anchor = Anchor((cx, 0.0, seat), SEAT["stool"], "centre of the seat top")


@pose
def villa_lounge(s):
    """Chaise longue (seat 0.46 m, back reclined 40 deg): reclining, legs stretched out along the seat,
    the right knee slightly bent, the right hand on the belly, the left hand resting on the cushion."""
    s.furniture = ("chaise longue: seat top 0.46 m, 1.30 m long, 0.76 m wide, back reclined 40 deg from vertical, "
                   "left arm bolster 0.13 m over the seat")
    b = s.actor("villa_lounge")
    rec = 40.0
    b.pelvis(pitch=-36)
    b.spine("mTorso", pitch=-3)
    b.spine("mChest", pitch=1)
    b.spine("mNeck", pitch=16)
    b.spine("mHead", pitch=10, yaw=8, lean=-3)
    seat = b.lowest(["pelvis"]) + SINK_SOFT
    fl = seat - 0.46
    back_x = b.back_plane_x(seat, rec)
    hl, hr = b.pos("mHipLeft"), b.pos("mHipRight")
    b.leg("L", ankle=(hl[0] + 0.95, 0.17, seat + 0.06), pole=(0.1, 0.3, 1.0), foot=(0.45, 0.25, 0.86))
    b.leg("R", ankle=(hr[0] + 0.88, -0.13, seat + 0.07), pole=(0.25, -0.25, 1.0), foot="flat")
    s.box((back_x - 0.03, -0.38, seat - 0.14), (back_x + 1.30, 0.38, seat), "soft", "fabric", "seat cushion")
    s.box((back_x - 0.45, -0.38, fl + 0.06), (back_x + 1.27, 0.38, seat - 0.14), "hard", "wood", "frame")
    q = qy(-rec)
    s.obox(sub((back_x, 0.0, seat), qrot(q, (0.07, 0.0, -0.40))), (0.14, 0.76, 0.80), q, "soft", "fabric",
           "back cushion")
    arm_y, arm_z = 0.45, seat + 0.13
    s.cyl((back_x - 0.15, arm_y, arm_z), (back_x + 0.55, arm_y, arm_z), 0.09, "soft", "fabric", "arm bolster")
    s.floor(fl, (back_x - 0.6, -0.6), (back_x + 1.5, 0.6))
    b.collar("L", elev=-2, fwd=4)
    b.collar("R", elev=-2, fwd=8)
    pt, n = b.body_point("mTorso", (0.095, -0.01, 0.07), (1, 0, 0))
    b.palm_on("R", pt, n, qrot(b.fk()[0]["mTorso"], (0.0, 1.0, 0.25)), props=s.props)
    b.palm_reach("L", lambda f: ((back_x + f, arm_y - 0.02, arm_z + 0.09), (0, 0, 1), (1.0, -0.15, -0.2)), 0.5,
                 0.0, props=s.props)
    s.anchor = Anchor((back_x, 0.0, seat), 0.46, "seat top at the foot of the back cushion")


#@@POSES2@@
# ---------------------------------------------------------------------------------------------
# build, write, read back, check
# ---------------------------------------------------------------------------------------------
def finalize(b):
    for n in NAMES:
        if qangle(b.loc[n]) < 0.3:
            b.loc[n] = qmul(b.loc[n], qx(0.4))
        b.loc[n] = qnorm(b.loc[n])


def anim_bytes_keys(keys, duration, hand_pose, priority=PRIORITY, ease=EASE):
    """LLKeyframeMotion::serialize for any number of keys: keys = [(t, {joint: q}, pelvis_pos)]."""
    out = bytearray()

    def pk(fmt, *v):
        out.extend(struct.pack("<" + fmt, *v))

    pk("HH", 1, 0)
    pk("i", priority)
    pk("f", duration)
    out.extend(b"\0")
    pk("ff", 0.0, duration)
    pk("i", 1)
    pk("ff", *ease)
    pk("I", hand_pose)
    pk("I", len(NAMES))
    for n in NAMES:
        out.extend(n.encode("ascii") + b"\0")
        pk("i", priority)
        pk("i", len(keys))
        for t, loc, _ in keys:
            q = qnorm(loc[n])
            if q[0] < 0:
                q = tuple(-c for c in q)
            pk("HHHH", f2u(t, 0.0, duration), *(f2u(c, -1.0, 1.0) for c in q[1:]))
        if n == "mPelvis":
            pk("i", len(keys))
            for t, _, pp in keys:
                pk("HHHH", f2u(t, 0.0, duration), *(f2u(c, -MAX_PELVIS_OFFSET, MAX_PELVIS_OFFSET) for c in pp))
        else:
            pk("i", 0)
    pk("i", 0)
    return bytes(out)


def bvh_text_frames(frames, frame_time):
    """poses.py's BVH writer for any number of frames: frames = [(local, pelvis_pos)], after the
    zero T-pose reference frame 0."""
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
    rows = []
    t_pose = []
    for n in order:
        if n == "mPelvis":
            t_pose += [0.0, hip_y, 0.0]
        t_pose += [0.0, 0.0, 0.0]
    rows.append(t_pose)
    for local, pelvis_pos in frames:
        row = []
        for n in order:
            if n == "mPelvis":
                d = mul(sl_to_bvh(pelvis_pos), 1 / INCHES)
                row += [d[0], hip_y + d[1], d[2]]
            row += list(euler_xzy(q_sl_to_bvh(local[n])))
        rows.append(row)
    lines += ["MOTION", f"Frames: {len(rows)}", f"Frame Time: {frame_time:.6f}"]
    for fr in rows:
        lines.append(" ".join(f"{v:.6f}" for v in fr))
    return "\n".join(lines) + "\n"


def read_bvh_frames(text):
    """Every played frame of a BVH as llbvhloader.cpp turns it into keys (SL frame)."""
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
    alias = {v: k for k, v in BVH_NAME.items()}
    axes = {"X": (1, 0, 0), "Y": (0, 1, 0), "Z": (0, 0, 1)}

    def decode(fr):
        rots, pos = {}, None
        k = 0
        for nm, ch in zip(names, chans):
            v = dict(zip(ch, fr[k:k + len(ch)]))
            k += len(ch)
            q = QI
            for ax in [c[0] for c in ch if c.endswith("rotation")]:
                q = qmul(q, qaxis(axes[ax], v[ax + "rotation"]))
            rots[alias[nm]] = q_bvh_to_sl(q)
            if "Xposition" in v:
                pos = (v["Xposition"], v["Yposition"], v["Zposition"])
        return rots, pos

    frames = [decode(vals[k * width:(k + 1) * width]) for k in range(nframes)]
    r0, p0 = frames[0]
    out = []
    for r, p in frames[1:]:
        out.append((r, mul(PZ.bvh_to_sl(sub(p, p0)), INCHES)))
    return {"frames": out, "frame0": r0, "duration": (nframes - 2) * ftime}


def keys_of(scene, b):
    if scene.keys is None:
        return [(0.0, dict(b.loc), b.pelvis_pos), (scene.duration, dict(b.loc), b.pelvis_pos)]
    return b.anim_keys


def verify(scene, b, data, bvh):
    keys = keys_of(scene, b)
    a = read_anim(data)
    D = scene.duration
    assert a["loop"] == 1 and a["priority"] == PRIORITY and abs(a["loop_out"] - D) < 1e-6
    assert abs(a["duration"] - D) < 1e-6 and a["hand_pose"] == b.hand_pose
    assert set(a["joints"]) == set(NAMES)
    dec_keys = [({}, None) for _ in keys]
    max_anim = 0.0
    for n, j in a["joints"].items():
        assert j["priority"] == PRIORITY and len(j["rot"]) == len(keys)
        for i, (t, q) in enumerate(j["rot"]):
            assert abs(t - keys[i][0]) < D / 65535 * 1.01, (n, t, keys[i][0])
            dec_keys[i][0][n] = q
            max_anim = max(max_anim, qdiff(q, keys[i][1][n]))
    pel = a["joints"]["mPelvis"]["pos"]
    assert len(pel) == len(keys)
    max_pos = 0.0
    for i, (t, p) in enumerate(pel):
        dec_keys[i] = (dec_keys[i][0], p)
        max_pos = max(max_pos, length(sub(p, keys[i][2])))
    assert max_anim < 0.02, f"anim rotation round trip {max_anim} deg"
    assert max_pos < 2e-4, f"pelvis round trip {max_pos} m"
    if scene.keys is None:
        assert data == PZ.anim_bytes(b.loc, b.pelvis_pos, b.hand_pose), "differs from poses.py's writer"
        assert bvh == PZ.bvh_text(b.loc, b.pelvis_pos), "differs from poses.py's BVH writer"
    bv = read_bvh_frames(bvh)
    assert len(bv["frames"]) == len(keys)
    max_bvh = 0.0
    for (r, p), (dr, dp) in zip(bv["frames"], dec_keys):
        max_bvh = max(max_bvh, max(qdiff(r[n], dr[n]) for n in NAMES))
        assert length(sub(p, dp)) < 2e-4
    assert max_bvh < 0.02, f"bvh vs anim {max_bvh} deg"
    assert all(qangle(bv["frame0"][n]) < 1e-9 for n in NAMES)
    assert abs(bv["duration"] - D) < 1e-6
    return dec_keys, {"anim_max_err_deg": round(max_anim, 4), "bvh_vs_anim_max_err_deg": round(max_bvh, 4),
                      "pelvis_max_err_m": round(max_pos, 5), "keys": len(keys), "duration_s": D}


# --- checks on the decoded pose ---------------------------------------------------------------
SEG_MASS = {"head": 0.081, "chest": 0.216, "belly": 0.139, "pelvis": 0.142, "uarm": 0.028, "farm": 0.016,
            "hand": 0.006, "thigh": 0.100, "shin": 0.0465, "foot": 0.0145}


def com(W, P):
    def at(j, o):
        return add(P[j], qrot(W[j], o))
    pts = [(SEG_MASS["head"], at("mHead", (0.015, 0, 0.06))), (SEG_MASS["chest"], at("mChest", (0.0, 0, 0.10))),
           (SEG_MASS["belly"], at("mTorso", (0.0, 0, 0.08))), (SEG_MASS["pelvis"], at("mPelvis", (-0.01, 0, -0.03)))]
    for s in "LR":
        k = SIDE[s]
        _, sh, el, wr = ARM[s]
        hp, kn, an = LEG[s]
        pts += [(SEG_MASS["uarm"], lerp(P[sh], P[el], 0.436)), (SEG_MASS["farm"], lerp(P[el], P[wr], 0.43)),
                (SEG_MASS["hand"], at(wr, (0, 0.05 * k, 0))), (SEG_MASS["thigh"], lerp(P[hp], P[kn], 0.433)),
                (SEG_MASS["shin"], lerp(P[kn], P[an], 0.433)), (SEG_MASS["foot"], at(an, (0.06, 0, -0.03)))]
    m = sum(w for w, _ in pts)
    return tuple(sum(w * p[i] for w, p in pts) / m for i in range(3))


def hull(points):
    pts = sorted(set((round(p[0], 4), round(p[1], 4)) for p in points))
    if len(pts) < 3:
        return pts

    def cr(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])
    lo, hi = [], []
    for p in pts:
        while len(lo) >= 2 and cr(lo[-2], lo[-1], p) <= 0:
            lo.pop()
        lo.append(p)
    for p in reversed(pts):
        while len(hi) >= 2 and cr(hi[-2], hi[-1], p) <= 0:
            hi.pop()
        hi.append(p)
    return lo[:-1] + hi[:-1]


def hull_margin(h, p):
    """Signed distance of p inside the convex polygon h (positive inside)."""
    if len(h) < 3:
        return -1.0
    best = 1e9
    for i in range(len(h)):
        a, b = h[i], h[(i + 1) % len(h)]
        e = (b[0] - a[0], b[1] - a[1])
        L = math.hypot(*e)
        if L < 1e-9:
            continue
        d = ((p[0] - a[0]) * e[1] - (p[1] - a[1]) * e[0]) / L
        best = min(best, -d)
    return best


def samples(c, step=0.02):
    _, p0, p1, r = c[:4]
    n = max(1, int(length(sub(p1, p0)) / step))
    return [lerp(p0, p1, i / n) for i in range(n + 1)], r


def prop_contacts(caps, props):
    """Per capsule and solid prop: deepest penetration and the contact points."""
    clips, touch = [], []
    for c in caps:
        pts, r = samples(c)
        for pr in props:
            if pr.kind == "water":
                continue
            worst = None
            for p in pts:
                d = pr.sdf(p) - r
                if d < 0.012:
                    touch.append((c[0], pr.label, p, d))
                if worst is None or d < worst:
                    worst = d
            if worst is not None and -worst > TOL[pr.kind]:
                clips.append(f"{c[0]} into {pr.label} ({pr.kind}) {-worst * 100:.1f} cm")
    return clips, touch


def body_pairs(caps_a, caps_b, same):
    clips, touches = [], []
    for i, a in enumerate(caps_a):
        for j, b in enumerate(caps_b):
            if same and j <= i:
                continue
            if same:
                rule = self_pair_rule(a[0], b[0])
                if rule is None:
                    continue
                ta, tb, tol = rule
            else:
                ta, tb, tol = 0.0, 0.0, 0.03
            pa = trim_seg(a[1], a[2], ta)
            pb = trim_seg(b[1], b[2], tb)
            d, _, _ = seg_dist(pa[0], pa[1], pb[0], pb[1])
            pen = a[3] + b[3] - d
            if pen > tol:
                clips.append(f"{a[0]} / {b[0]} {pen * 100:.1f} cm")
            elif pen > -0.01:
                touches.append(f"{a[0]}/{b[0]}")
    return clips, touches


def limits(local, W, P):
    rep = PZ.limb_report(local, W, P)
    warn = []
    for s in "LR":
        if rep[f"{s} knee bend"] > 152:
            warn.append(f"{s} knee bend {rep[f'{s} knee bend']}")
        if rep[f"{s} elbow bend"] > 148:
            warn.append(f"{s} elbow bend {rep[f'{s} elbow bend']}")
        if rep[f"{s} wrist bend"] > 75:
            warn.append(f"{s} wrist bend {rep[f'{s} wrist bend']}")
        if abs(rep[f"{s} upper arm roll"]) > 100:
            warn.append(f"{s} upper arm roll {rep[f'{s} upper arm roll']}")
        if abs(rep[f"{s} forearm roll"]) > 95:
            warn.append(f"{s} forearm roll {rep[f'{s} forearm roll']}")
        if abs(rep[f"{s} thigh roll"]) > 60:
            warn.append(f"{s} thigh roll {rep[f'{s} thigh roll']}")
        if abs(rep[f"{s} shin roll"]) > 35:
            warn.append(f"{s} shin roll {rep[f'{s} shin roll']}")
        if not -35 <= rep[f"{s} ankle"] <= 60:
            warn.append(f"{s} ankle {rep[f'{s} ankle']}")
        hp, kn, _ = LEG[s]
        d = qrot(qconj(W["mPelvis"]), norm(sub(P[kn], P[hp])))
        flex = math.degrees(math.atan2(d[0], -d[2]))
        abd = math.degrees(math.asin(max(-1, min(1, d[1] * SIDE[s]))))
        rep[f"{s} hip flexion"] = round(flex, 1)
        rep[f"{s} hip abduction"] = round(abd, 1)
        if not -25 <= flex <= 135:
            warn.append(f"{s} hip flexion {flex:.0f}")
        if not -30 <= abd <= 65:
            warn.append(f"{s} hip abduction {abd:.0f}")
    for j, lim in (("mTorso", 40), ("mChest", 40), ("mNeck", 45), ("mHead", 50)):
        a = qangle(local[j])
        rep[f"{j} bend"] = round(a, 1)
        if a > lim:
            warn.append(f"{j} {a:.0f} deg")
    return rep, warn


def check_scene(scene, decoded):
    """decoded: {actor name: (W, P) in scene coordinates}.  Returns per actor checks + contacts."""
    out = {}
    caps = {n: body_caps(*wp) for n, wp in decoded.items()}
    for b in scene.actors:
        W, P = decoded[b.name]
        local = None
        res = {}
        c = caps[b.name]
        self_clip, self_touch = body_pairs(c, c, True)
        prop_clip, ptouch = prop_contacts(c, scene.props)
        partner_clip, partner_touch, support_pts = [], [], [p for _, _, p, _ in ptouch]
        for o in scene.actors:
            if o is b:
                continue
            pc, pt = body_pairs(c, caps[o.name], False)
            if o.name > b.name:
                partner_clip += pc
            partner_touch += pt
            for a_ in c:
                pts, r = samples(a_)
                for o_ in caps[o.name]:
                    for p in pts:
                        d, _, _ = seg_dist(p, p, o_[1], o_[2])
                        if d - r - o_[3] < 0.012:
                            support_pts.append(p)
        res["self_clip"] = self_clip
        res["furniture_clip"] = prop_clip
        res["partner_clip"] = partner_clip
        res["touching"] = sorted(set(f"{a} on {p}" for a, p, _, _ in ptouch)) + sorted(set(partner_touch))
        res["self_touch"] = sorted(set(self_touch))
        cm = com(W, P)
        h = hull(support_pts)
        if scene.buoyant:
            res["weight"] = {"com": r3(cm), "support": "water carries the body (buoyant pose)"}
        else:
            m = hull_margin(h, cm)
            res["weight"] = {"com": r3(cm), "support_points": len(support_pts),
                             "com_inside_support_margin_m": round(m, 3), "ok": m > 0.0}
        out[b.name] = (res, local)
    return out


# ---------------------------------------------------------------------------------------------
# previews (Blender, Cycles): the collision body of the decoded pose + the furniture
# ---------------------------------------------------------------------------------------------
COLORS = dict(PZ.COLORS)
COLORS.update({"L2": (0.1, 0.62, 0.52, 1), "R2": (0.95, 0.55, 0.08, 1), "C2": (0.66, 0.56, 0.72, 1),
               "fabric": (0.80, 0.70, 0.55, 0.35), "wood": (0.45, 0.30, 0.18, 0.45), "stone": (0.78, 0.76, 0.70, 0.45),
               "metal": (0.75, 0.6, 0.3, 0.7), "water": (0.15, 0.55, 0.85, 0.22), "pillow": (0.95, 0.95, 0.92, 0.45),
               "floor": (0.32, 0.32, 0.34, 1)})

VIEWS = {
    "seated": [("front", -90.0, 0.0), ("left side", 180.0, 0.0), ("3/4 from above", -135.0, 22.0)],
    "lying": [("left side", 180.0, 0.0), ("from above", 0.0, 90.0), ("3/4 from above", -135.0, 35.0)],
    "couple": [("front", -90.0, 0.0), ("left side", 180.0, 0.0), ("3/4 from above", -135.0, 30.0)],
}


def figure_mesh(m, W, P, second=False):
    ren = {"C": "C2", "L": "L2", "R": "R2"} if second else {}
    for c in body_caps(W, P):
        m.capsule(c[1], c[2], c[3], ren.get(c[4], c[4]))
    m.sph(add(P["mHead"], qrot(W["mHead"], (0.10, 0.0, 0.065))), 0.022, "nose")
    for s in "LR":
        k = SIDE[s]
        _, sh, el, wr = ARM[s]
        m.sph(add(P[wr], qrot(W[wr], (0.0, 0.07 * k, -0.02))), 0.016, "palm")
        m.sph(add(P[el], qrot(W[sh], (-0.035, 0, 0))), 0.016, "cap")
        hp, kn, _ = LEG[s]
        m.sph(add(P[kn], qrot(W[hp], (0.055, 0, 0))), 0.022, "cap")


def render(jobs, samples=24):
    """jobs: [(png name, [panel rows], info)]; a panel = (label, yaw, tilt, figures, props)."""
    import bpy
    from mathutils import Matrix, Vector

    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.cycles.use_denoising = True
    sc.cycles.max_bounces = 4
    sc.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("w")
    sc.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.80, 0.80, 0.82, 1)
    bg.inputs[1].default_value = 0.9
    cam_d = bpy.data.cameras.new("cam")
    cam_d.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_d)
    sc.collection.objects.link(cam)
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
        bsdf.inputs["Roughness"].default_value = 0.6
        if c[3] < 1:
            bsdf.inputs["Alpha"].default_value = c[3]
        if k == "text":
            bsdf.inputs["Emission Color"].default_value = c
        mats[k] = m
    keys = list(COLORS)
    PW, PH = 2.6, 2.6 * 480 / 450
    for name, rows, info in jobs:
        for o in list(sc.collection.objects):
            if o.type in ("MESH", "FONT"):
                bpy.data.objects.remove(o, do_unlink=True)
        ncol = max(len(r) for r in rows)
        nrow = len(rows)
        sc.render.resolution_x = 450 * ncol
        sc.render.resolution_y = 480 * nrow
        cam_d.ortho_scale = PW * ncol if ncol * 450 >= nrow * 480 else PH * nrow
        cam.location = (0, -12, 1.15)
        for j, row in enumerate(rows):
            for i, (label, yaw, tilt, figs, props) in enumerate(row):
                fm = Mesh()
                for k_, (W, P) in enumerate(figs):
                    figure_mesh(fm, W, P, second=k_ == 1)
                pm = Mesh()
                for p in props:
                    p.mesh(pm)
                rz = Matrix.Rotation(math.radians(yaw), 4, "Z")
                rx = Matrix.Rotation(math.radians(tilt), 4, "X")
                fpts = [rx @ (rz @ Vector(v)) for v in fm.v]
                xs, zs = [p.x for p in fpts], [p.z for p in fpts]
                cx, cz = (min(xs) + max(xs)) / 2, (min(zs) + max(zs)) / 2
                px = (i - (ncol - 1) / 2) * PW
                pz = 1.15 + ((nrow - 1) / 2 - j) * PH - 0.08
                shift = Vector((px - cx, 0, pz - cz))
                for tag, mesh in (("f", fm), ("p", pm)):
                    if not mesh.v:
                        continue
                    pts = [tuple(rx @ (rz @ Vector(v)) + shift) for v in mesh.v]
                    me = bpy.data.meshes.new(f"{name}_{j}_{i}_{tag}")
                    me.from_pydata(pts, [], mesh.f)
                    for k in keys:
                        me.materials.append(mats[k])
                    me.polygons.foreach_set("material_index", [keys.index(m) for m in mesh.m])
                    me.update()
                    for poly in me.polygons:
                        poly.use_smooth = tag == "f"
                    ob = bpy.data.objects.new(me.name, me)
                    sc.collection.objects.link(ob)
                cu = bpy.data.curves.new(f"t{j}{i}", "FONT")
                cu.body = f"{name}  {label}" if (i == 0 and j == 0) else label
                cu.size = 0.11
                to = bpy.data.objects.new(f"t{j}{i}", cu)
                to.data.materials.append(mats["text"])
                to.location = (px - PW / 2 + 0.06, -3, 1.15 + ((nrow - 1) / 2 - j) * PH + PH / 2 - 0.2)
                to.rotation_euler = (math.pi / 2, 0, 0)
                sc.collection.objects.link(to)
        cu = bpy.data.curves.new("info", "FONT")
        cu.body = info
        cu.size = 0.07
        to = bpy.data.objects.new("info", cu)
        to.data.materials.append(mats["text"])
        to.location = (-ncol * PW / 2 + 0.06, -3, 1.15 - nrow * PH / 2 + 0.06)
        to.rotation_euler = (math.pi / 2, 0, 0)
        sc.collection.objects.link(to)
        sc.render.filepath = os.path.join(PREV, f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("  rendered", sc.render.filepath, flush=True)


def blender_bvh_check(names):
    """Import every .bvh with Blender's own importer and compare its joint positions, frame by
    frame, with fk() of the rotations read back from the .anim (as poses.py does)."""
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
        nk = len(a["joints"]["mPelvis"]["rot"])
        _, P0 = fk({}, (0, 0, 0))
        h0 = heads(1)
        A = np.array([h0[BVH_NAME[n]] for n in NAMES])
        B = np.array([P0[n] for n in NAMES])
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((A - ca).T @ (B - cb))
        D = np.diag([1, 1, np.sign(np.linalg.det(Vt.T @ U.T))])
        R = Vt.T @ D @ U.T
        err = 0.0
        for k in range(nk):
            dec = {n: j["rot"][k][1] for n, j in a["joints"].items()}
            dpos = a["joints"]["mPelvis"]["pos"][k][1]
            _, P1 = fk(dec, dpos)
            h1 = heads(2 + k)
            A1 = np.array([h1[BVH_NAME[n]] for n in NAMES])
            B1 = np.array([P1[n] for n in NAMES])
            err = max(err, float(np.abs((A1 - ca) @ R.T + cb - B1).max()))
        out[name] = round(err, 5)
        assert err < 0.002, f"{name}: Blender's BVH import differs from the .anim pose by {err} m"
    return out


# ---------------------------------------------------------------------------------------------
def sit_target(scene, b):
    ax = scene.anchor
    root = b.W((0.0, 0.0, ROOT_Z))
    rel = sub(root, ax.point)
    off = (rel[0], rel[1], ax.height + rel[2] - LIFT)
    yaw = b.place[3]
    return {"anchor": ax.what, "anchor_height_m": ax.height, "root_over_anchor_m": r3(rel),
            "offset_m": r3(off), "rot_z_deg": round(yaw, 1),
            "lsl": (f"llSitTarget(<{off[0]:.3f}, {off[1]:.3f}, {off[2]:.3f}>, "
                    f"llEuler2Rot(<0.0, 0.0, {yaw:.1f}> * DEG_TO_RAD));")}


def contacts_of(W, P):
    def at(j, o):
        return add(P[j], qrot(W[j], o))
    return {"pelvis": r3(P["mPelvis"]), "head": r3(at("mHead", (0.015, 0, 0.075))),
            "wrists": [r3(P["mWristLeft"]), r3(P["mWristRight"])],
            "elbows": [r3(P["mElbowLeft"]), r3(P["mElbowRight"])],
            "knees": [r3(P["mKneeLeft"]), r3(P["mKneeRight"])],
            "ankles": [r3(P["mAnkleLeft"]), r3(P["mAnkleRight"])],
            "soles": [r3(at(a, (0.03, 0, -SOLE))) for a in ("mAnkleLeft", "mAnkleRight")]}


def main():
    only = None
    if "--only" in sys.argv:
        only = set(sys.argv[sys.argv.index("--only") + 1].split(","))
    nsamp = int(sys.argv[sys.argv.index("--samples") + 1]) if "--samples" in sys.argv else 24
    os.makedirs(PREV, exist_ok=True)
    report_path = os.path.join(OUT, "poses.json")
    report = {}
    if os.path.exists(report_path):
        try:
            with open(report_path) as fh:
                report = json.load(fh)
        except ValueError:
            report = {}
    jobs, written = [], []
    for fn in POSES:
        name = fn.__name__
        sc = Scene(name, " ".join((fn.__doc__ or "").split()))
        fn(sc)
        if only and name not in only and not any(a.name in only for a in sc.actors):
            continue
        decoded, frames = {}, {}
        for b in sc.actors:
            if sc.keys is None:
                finalize(b)
            data = anim_bytes_keys(keys_of(sc, b), sc.duration, b.hand_pose)
            ft = sc.duration / (len(keys_of(sc, b)) - 1)
            bvh = bvh_text_frames([(loc, pp) for _, loc, pp in keys_of(sc, b)], ft)
            with open(os.path.join(OUT, f"{b.name}.anim"), "wb") as fh:
                fh.write(data)
            with open(os.path.join(OUT, f"{b.name}.bvh"), "w") as fh:
                fh.write(bvh)
            dec_keys, rt = verify(sc, b, data, bvh)
            frames[b.name] = [b.scene_fk(loc, pp) for loc, pp in dec_keys]
            decoded[b.name] = frames[b.name][0]
            b._rt, b._dec = rt, dec_keys
            b._bytes = len(data)
            written.append(b.name)
        checks = check_scene(sc, decoded)
        for b in sc.actors:
            res, _ = checks[b.name]
            dloc, dpos = b._dec[0]
            Wl, Pl = fk(dloc, dpos)
            limbs, warn = limits(dloc, Wl, Pl)
            res["joint_limits"] = warn
            miss = {}
            for j, tgt, label in b.targets:
                miss[label] = round(length(sub(Pl[j], tgt)), 3)
            res["target_miss_m"] = miss
            res["roundtrip"] = b._rt
            res["ok"] = (not res["self_clip"] and not res["furniture_clip"] and not res["partner_clip"]
                         and not warn and all(v < 0.02 for v in miss.values())
                         and res["weight"].get("ok", True))
            entry = {"doc": sc.doc, "furniture": sc.furniture, "hand_pose": b.hand_pose,
                     "priority": PRIORITY, "loop": True, "duration_s": sc.duration,
                     "pelvis_offset_m": r3(dpos), "anim_bytes": b._bytes,
                     "sit_target": sit_target(sc, b) if sc.anchor else None,
                     "contacts_scene_m": contacts_of(*decoded[b.name]),
                     "checks": res, "limbs_deg": limbs, "notes": sc.notes + b.notes}
            if len(sc.actors) == 2:
                other = [o for o in sc.actors if o is not b][0]
                a0 = sc.actors[0]
                rootB = sc.actors[1].W((0, 0, ROOT_Z))
                entry["pair"] = {"partner": other.name, "role": "A" if b is a0 else "B",
                                 "B_root_rel_A_root_m": r3(sub(rootB, (0, 0, ROOT_Z))),
                                 "B_yaw_rel_A_deg": round(sc.actors[1].place[3], 1)}
            report[b.name] = entry
            print(f"{b.name}: ok={res['ok']}  pelvis {r3(dpos)}  {b._rt}")
            for k in ("self_clip", "furniture_clip", "partner_clip", "joint_limits"):
                if res[k]:
                    print(f"    {k}: {res[k]}")
            print(f"    weight {res['weight']}  miss {miss}")
            print(f"    touching {res['touching']}")
            if sc.anchor:
                print(f"    sit target {entry['sit_target']['lsl']}")
        views = VIEWS[sc.views]
        if sc.keys is None:
            figs = [decoded[b.name] for b in sc.actors]
            rows = [[(lab, yaw, tilt, figs, sc.props) for lab, yaw, tilt in views]]
            info = (f"{sc.furniture}   |   blue/red = left/right" + ("  (B: green/orange)" if len(sc.actors) > 1 else "")
                    + ", yellow = palm, white = knee cap / elbow, brown = nose")
            jobs.append((name if len(sc.actors) == 1 else name, rows, info))
        else:
            jobs.append(sc.preview(frames, sc))
    with open(report_path, "w") as fh:
        json.dump(report, fh, indent=1)
    if "--no-render" not in sys.argv:
        chk = blender_bvh_check(written)
        for n, v in chk.items():
            print(f"  blender bvh import {n}: max error {v} m")
            report[n]["checks"]["blender_bvh_import_max_err_m"] = v
        with open(report_path, "w") as fh:
            json.dump(report, fh, indent=1)
        render(jobs, nsamp)


if __name__ == "__main__":
    main()

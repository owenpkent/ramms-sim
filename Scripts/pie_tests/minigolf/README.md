# Mini-golf PIE test

A Kinova Gen3 putting a free ball on a three-hole mini-golf course, entirely under
MuJoCo (URLab) inside Unreal. The arm is driven through its position servos with a
planned joint stroke, a rigid putter head rides on its bracelet, and the ball is a
free sphere struck by contact. Everything the ball does after impact (launch,
skid, roll, line, drop into the cup) is MuJoCo's.

`make_minigolf_map.py` authors `/Game/Maps/URL/Map_MiniGolf_URL` from scratch, the
newton test's way (scratch world, then `save_map`; read the comments in
`../newton/make_newton_map.py` for why). No imported assets and nothing from
`/RammsPrivateAssets/`; the map builder checks the saved package's dependencies to
make sure of it.

```
data/putter_head.json     the putter head's pose on the bracelet (cm, Unreal; measured)
data/stroke_hole1.json    the planned stroke: 241 frames x 7 joints, degrees, 24 fps
make_minigolf_map.py      the level builder (runs inside the editor)
minigolf_op.py            the in-editor op, one op per call (runs inside the editor)
run_minigolf.py           the host: map / probe / kick / record / stop (uses ../common.py)
recordings/               per-tick recordings, numbered, gitignored
```

## Run

The ramms-sim editor must be open with Python Remote Execution enabled. From the repo
root, with PIE stopped:

```
python Scripts/pie_tests/minigolf/run_minigolf.py map --hole 1     # author the level
python Scripts/pie_tests/minigolf/run_minigolf.py probe            # drive the arm to the address pose, report the bracelet
python Scripts/pie_tests/minigolf/run_minigolf.py kick             # launch the ball by velocity: the rolling-friction calibration
python Scripts/pie_tests/minigolf/run_minigolf.py record           # the putt -> recordings/hole1 vN.json, with a summary of what the ball did
python Scripts/pie_tests/minigolf/run_minigolf.py stop
```

`map` takes `--hole 1|2|3`, `--friction slide,torsion,roll`, `--base-yaw`, `--map` and
`--no-putter`. The map builder itself is parameterised through `unreal._ramms_minigolf_*`
attributes, consumed on read (listed in its docstring), so another level can reuse it.
The stroke in `data/` was planned for hole 1's ball position; holes 2 and 3 build and
simulate, but nothing aims the stroke at them.

A recording row is `[sim_s, wall_s, frame, j1..j7 (rad), bracelet xf, putter_head xf, ball xf]`
with `xf = [x y z qx qy qz qw]` in Unreal world cm.

## What is simulated, and what is not

- **The arm.** The Gen3 from the project's own MJCF (`gen3_2f85_fixed`), driven through
  its `<general>` position servos (kp 2000 / 500) with the stroke as the target. Gravity,
  inertia, servo lag and droop are the sim's. With the stroke below the recorded joints
  stay within about 6 degrees of the plan.
- **The putter.** A rigid child body of the bracelet (a 10 x 2.5 x 2 cm box, 350 g), not a
  grasped club. The simulated 2F-85 lets go of a club above about 0.5 m/s hand speed.
- **The ball.** A free 42.7 mm, 45.9 g sphere with sliding, torsional and rolling friction
  (`condim` 6) on a static green.
- **The course.** The hole's walls as thin static boxes along the measured wall lines of each
  tile kind (tables inlined in the builder, measured from the Kenney Minigolf Kit, CC0), the
  green as slabs with a 10.8 cm gap at the cup, and a liner 10.5 cm deep.
- **Not simulated.** A chair under the arm (the base is fixed at its mount), the arm's carry
  phase before frame 72 (a run starts at the address pose), and any assist for the long
  holes (see below).

## Numbers (hole 1)

The stroke is a 20 cm back-swing and 28 cm through-swing pendulum over 1.2 s, impact around
frame 112, raise at frames 180 to 204.

| What | MuJoCo |
|---|---|
| Head speed at impact | 1.45 m/s |
| Launch | 1.36 x head speed, 2.26 m/s off the box face |
| Skid | the struck ball skids to 5/7 of its launch speed before it rolls (a free sphere given a pure linear velocity does exactly that: 1.41 to 1.02 m/s) |
| Carpet | rolling friction 0.00135, about 0.5 m/s^2 on a kicked ball |
| Roll | 153 cm, sunk about 36 frames after impact, resting in the liner at z -8.4 cm (that take); a second run on a fresh editor rolled 145 cm and stopped 5 cm short, 3.5 cm left |
| Line | 1.9 cm of pull over 97 cm with the face yawed -3.9 degrees (the first run, unyawed, pulled 3.9 degrees) |

The finding that matters: a 1.5 m putt on mini-golf carpet takes the Gen3 to 1.45 m/s at the
head, close to its 1.63 m/s ceiling (joint 7 at 54 of 69.9 deg/s). The 3.5 m hole is beyond the
arm alone.

Run to run the roll varies by a few percent. The sim is real time and the stroke's targets are interpolated once per
editor tick (48 to 55 Hz here), so the exact moment the face meets the ball shifts by a fraction of a tick between runs,
and the launch speed with it (2.26 m/s in the take above, 2.02 m/s in the second run). A fixed-rate step would remove that.

## Conventions

Unreal is left-handed and uses centimetres; MuJoCo is right-handed and uses metres. URLab
maps between them by mirroring Y (`URLabAxisConv.h`), so every number crossing into a MuJoCo
element is converted:

- positions: `(x, -y, z) / 100`
- quaternions: Unreal `(x, y, z, w)` to MuJoCo `(w, -x, y, -z)`

`make_minigolf_map.py` does this for the putter head's pose (`mj_pos`, `mj_quat`); the pose
calls used by the op (`get_world_position` and friends) already return the Unreal side. The
Gen3 Blueprint's frame is the MJCF's: the stroke's joint angles drive the MJCF joints with no
sign changes, and the level mounts the Blueprint at yaw -90.

## Traps, each one cost a run

- **Disable the Blueprint's controllers before PIE.** The Gen3 Blueprint (and any pawn that
  carries it) has an end-effector controller. A bound, enabled controller rewrites every
  actuator target each step whether or not the component is active, so no Python joint
  command takes. Its `enabled` flag can only be switched safely before PIE (issue #76), so
  the map builder saves the level with the controllers disabled, and the level has no default
  pawn.
- **`set_control` does nothing by default.** The articulation applies the network control slot
  (`ControlSource` 0); `MjActuatorRuntime.set_control` stages the internal one.
  `set_network_control` moves the joints, and the op stages both.
- **Release the keyframe hold.** The Blueprint starts holding a keyframe (`ApplyControls` pins
  the joints to it every step); `take_over` calls `stop_hold_keyframe`.
- **Stage after the slots exist.** Targets staged the moment the sim reports ready were
  dropped; the host waits 2 s.
- **The map starts paused.** No pawn starts the sim, so the host calls `set_paused(False)`
  when it sees initialized but not running.
- **Quick-convert is for walls.** A putter head quick-converted as a mocap box became a body
  with no geoms (the ball sailed through it). A ball quick-converted as a sphere is a faceted
  hull that drifted 20 cm sideways over 2 m and slowed at half the carpet rate. Both are now
  MuJoCo elements built from components (`MjBody`, `MjGeom`, `MjFreeJoint` on an
  `MjArticulation`, the newton test's pattern).
- **Add the head under the bracelet by name.** A Blueprint instance's components do not match
  by object, so `add_component` accepts a name for the parent.
- **An actor attached to a Blueprint's component loses its offset** when the Blueprint
  constructs at PIE start.
- **`friction` is a `Vector3d` struct** that takes no init args: build it and set x, y, z.
- **Paths with spaces break a whitespace-split op line.** `play` takes `|`-separated fields.

## Open

- Holes 2 and 3 need a longer stroke than the arm delivers alone: drive the arm base along the
  lane during the swing, or shorten the holes.
- The box face has a degree or two of loft at impact, so the ball hops about 2 mm and skids
  with backspin. A face with a measured loft is a one-line change.
- The editor ticks at 50 to 60 Hz on this level, so a recording is variable-rate. Resample it
  to a fixed rate for downstream use.

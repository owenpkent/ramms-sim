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
data/putter_head.json     the putter head's pose on the bracelet (cm, Unreal; measured, face square to the lane)
data/putter_head_hole3.json  the same with the face yawed +2.6 degrees, a per-hole aim for hole 3
data/stroke_hole1.json    the planned stroke: 241 frames x 7 joints, degrees, 24 fps, plus the planned
                          putter transform at the address frame ("address_putter") that fitputter reads
make_minigolf_map.py      the level builder (runs inside the editor)
minigolf_op.py            the in-editor op, one op per call (runs inside the editor)
run_minigolf.py           the host: map / probe / fitputter / kick / record / stop (uses ../common.py)
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
python Scripts/pie_tests/minigolf/run_minigolf.py fitputter       # re-measure the putter head on the bracelet -> data/putter_head.json
python Scripts/pie_tests/minigolf/run_minigolf.py stop

# hole 3, chair-assisted (the Gen3 slides along +x at 56 cm/s between frames 104 and 130):
python Scripts/pie_tests/minigolf/run_minigolf.py map --hole 3 --gen3-bp /Game/Robots/URL/gen3_2f85 \
    --putter Scripts/pie_tests/minigolf/data/putter_head_hole3.json
python Scripts/pie_tests/minigolf/run_minigolf.py record --hole 3 --chair 56,104,130 --sim-speed 50
```

`map` takes `--hole 1|2|3`, `--friction slide,torsion,roll`, `--base-yaw`, `--map`, `--putter FILE`
and `--no-putter`, plus `--gen3-bp` (the Gen3 Blueprint; the default is the fixed base,
`/Game/Robots/URL/gen3_2f85` has the free base welded to a mocap body that `--chair` moves),
`--solref T,D` (contact softness of the ball and the putter head), `--wall-solref T,D`,
`--wall-friction slide,torsion,roll` and `--timestep S` (the model timestep). `record` takes
`--chair v_cm_s,fa,fb` and `--sim-speed PERCENT` (the approach wait scales with it).
`fitputter` takes `--aim-yaw DEGREES` and `--out FILE`. The map builder itself is parameterised through
`unreal._ramms_minigolf_*` attributes, consumed on read (listed in its docstring), so another level can reuse it.
The stroke in `data/` was planned for hole 1's ball position and addresses the ball directly (the face 0.5 cm
behind it). Holes 2 and 3 build and simulate with it; hole 3 needs the chair assist and its own aim (below).

A recording row is `[sim_s, wall_s, frame, j1..j7 (rad), bracelet xf, putter_head xf, ball xf, chair_x_cm, base_link xf]`
with `xf = [x y z qx qy qz qw]` in Unreal world cm. The recording format is `ramms-minigolf/2`: the last two columns
(the chair's slide since the start of play, in cm, and the base_link pose) are new in 2, and are 0 and the fixed base
when no chair is used. Format 1 rows end at the ball.

## What is simulated, and what is not

- **The arm.** The Gen3 from the project's own MJCF (`gen3_2f85_fixed`), driven through
  its `<general>` position servos (kp 2000 / 500) with the stroke as the target. Gravity,
  inertia, servo lag and droop are the sim's. With the stroke below the recorded joints
  stay within about 6 degrees of the plan.
- **The putter.** A rigid child body of the bracelet (a 10 x 2.5 x 2 cm box, 350 g), not a
  grasped club. The simulated 2F-85 lets go of a club above about 0.5 m/s hand speed.
- **The ball.** A free 42.7 mm, 45.9 g sphere with sliding, torsional and rolling friction
  (`condim` 6) on a static green.
- **The course.** The hole's walls as 6 cm thick static boxes whose inner faces lie on the measured wall
  lines of each tile kind (tables inlined in the builder, measured from the Kenney Minigolf Kit, CC0),
  the green as slabs with a 10.8 cm gap at the cup, and a liner 10.5 cm deep. Walls and liner have
  solref (0.004, 0.3) and friction (0.3, 0.001, 0.0001); see "Holes 2 and 3" below for why.
- **The chair, only as a slide.** With the free-base Blueprint, `--chair` slides the Gen3 along +x
  at a set speed between two frames; there is no wheelchair body, drive model or steering.
- **Not simulated.** A chair under the arm beyond that slide, the arm's carry phase before frame 72
  (a run starts at the address pose).

## Numbers

The stroke is a 20 cm back-swing and 28 cm through-swing pendulum over 1.2 s, impact around
frame 112, raise at frames 180 to 204. Hole 1, arm alone (the launch and line rows are from
before the address moved to the ball; see the next section for what that changed):

| What | MuJoCo |
|---|---|
| Head speed at impact | 1.45 m/s |
| Launch | 1.36 x head speed, 2.26 m/s off the box face (about 2.6 m/s once the stroke addresses the ball) |
| Skid | the struck ball skids to 5/7 of its launch speed before it rolls (a free sphere given a pure linear velocity does exactly that: 1.41 to 1.02 m/s) |
| Carpet | rolling friction 0.00135, about 0.5 m/s^2 on a kicked ball |
| Roll | 153 cm, sunk about 36 frames after impact, resting in the liner at z -8.4 cm (that take); a second run on a fresh editor rolled 145 cm and stopped 5 cm short, 3.5 cm left |
| Line | 1.9 cm of pull over 97 cm with the face yawed -3.9 degrees (the first run, unyawed, pulled 3.9 degrees); with the stroke addressing the ball, 0 cm over 150 and the face square |
| Hole 3, chair-assisted | 352 cm, sunk, at a 56 cm/s slide (full stick is 60), through the windmill tunnel |
| Hole 2, the bank | returns the ball down the dogleg at about 58 percent of its speed (34 percent of its energy) |

The finding that matters: a 1.5 m putt on mini-golf carpet takes the Gen3 to 1.45 m/s at the
head, close to its 1.63 m/s ceiling (joint 7 at 54 of 69.9 deg/s). The 3.5 m hole is beyond the
arm alone.

Run to run the roll varies by a few percent. The sim is real time and the stroke's targets are interpolated once per
editor tick (48 to 55 Hz here), so the exact moment the face meets the ball shifts by a fraction of a tick between runs,
and the launch speed with it (2.26 m/s in the take above, 2.02 m/s in the second run). A fixed-rate step would remove that.

## Holes 2 and 3: the chair-assist stroke

The long holes are beyond the arm alone (its 20/28 stroke at the joint-7 cap carries the ball about 170 cm on this
carpet), so the chair-assist stroke is built in the sim and works.

- **Mechanism.** The non-fixed Gen3 Blueprint (`/Game/Robots/URL/gen3_2f85`) has a free base welded to a mocap
  body, `base_target`, whose component follows the actor. `play` slides the Gen3 actor along +x at the given speed
  between two frames (`record --chair v,fa,fb`, 6-frame smoothstep ramps, on the sim clock). The base follows, the arm
  rides it, and the head meets the ball with the arm's speed plus the slide's. It is timed to the downswing (frames 104
  to 130; the stroke is 96 to 125) so the backswing is not cancelled. At 56 cm/s the ball rolled 352 cm and dropped into
  hole 3's cup, through the windmill tunnel. The slide is recorded per tick in the extra columns.
- **Address at the ball.** The stroke used to address 6 cm behind the ball, so the face met it 6 cm up the arc: 3.4 degrees
  of loft, a hop and backspin, and half the roll. The stroke now addresses 0.5 cm behind the ball, so impact is at the bottom
  of the arc. The pull went away with it (0 cm over 150 on hole 1) and the launch rose from 2.26 to about 2.6 m/s.
- **Walls are thick, bouncy and slippery.** A 1 cm wall let a 2.5 m/s ball drive past its mid-plane (MuJoCo's soft contact
  penetrates several cm at the default 20 ms time constant) and held it dead at hole 2's bank. Walls are now 6 cm thick,
  offset outward from the ball's centre line so the inner face stays on the measured line, with solref (0.004, 0.3) and
  friction (0.3, 0.001, 0.0001). The friction mattered most: unset, a quick-convert's default is (1, 1, 1), and torsional
  and rolling friction of 1.0 at the wall swallowed the ball's spin. With that fixed the bank returns the ball down the
  dogleg at about 58 percent of its speed: a real bank, not a perfect bounce. "Outward" comes from a per-hole centre-line
  polyline inlined in the builder (`CENTRE_LINES`).
- **Hole 2 as laid out does not work.** 343 cm of path with a bank in it needs roughly three times the energy one assisted
  stroke has after the bank (the ball got 46 cm down the dogleg). Either shorten it (the corner one tile from the ball and
  the hole tile straight below the corner, about 145 cm of path, still marginal after the bank) or make it a two-putt:
  the first putt banks and dies in the dogleg, the base is driven round the corner, and a second putt drops it. The
  two-putt needs a second stroke with the base re-parked beside the ball; nothing here does that yet.
- **Takes vary.** The sim is real time: control targets and the base slide update once per editor tick (48 to 55 Hz, or twice
  that in sim time at `--sim-speed 50`), so the strike lands at a slightly different phase each run. Hole 3 at the same
  settings: 352 (sunk), 387, 338, 327, 356 cm, and 5 to 15 cm of lateral wander. A finer model timestep (`--timestep 0.0005`)
  did not narrow it (338 / 327 / 356), so it is the real-time tick, not the contact resolution; the fix would be
  fixed-step Direct mode through the bridge, which nothing here connects to. Treat a recording as one take of several and
  keep the one you want.
- **Per-hole aim.** `fitputter --aim-yaw D --out FILE` writes a per-hole putter pose; hole 3 uses +2.6 degrees
  (`data/putter_head_hole3.json`), probably a degree too much now that the thick tunnel walls stopped the grazes.

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
- **`friction` is a `Vector3d` struct** that takes no init args: build it and set x, y, z (the builder's `vec3d`).
  Left unset on a quick-convert it is (1, 1, 1), which is far too grippy for a wall: always set it.
- **Setting a property during PIE can unbind the articulation** (#76). The `speed` op sets
  `physics_engine.sim_speed_percent` and reports whether the arm is still bound afterwards.
- **Paths with spaces break a whitespace-split op line.** `play` takes `|`-separated fields.

## Open

- Hole 2: shorten it, or make it a two-putt (above).
- Repeatable takes need fixed-step stepping (the bridge's Direct mode) or a per-substep mocap driver in C++.
- The box face has a degree or two of loft at impact, so the ball hops about 2 mm and skids
  with backspin. A face with a measured loft is a one-line change.
- The editor ticks at 50 to 60 Hz on this level, so a recording is variable-rate. Resample it
  to a fixed rate for downstream use.

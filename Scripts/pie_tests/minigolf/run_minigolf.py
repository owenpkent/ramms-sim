"""Host side of the mini-golf scenario: drives the running ramms-sim editor through
minigolf_op.py, one op per call, using Scripts/editor_remote_exec.py. Plain Python 3,
stdlib only. The editor must be open with Python Remote Execution enabled.

    python Scripts/pie_tests/minigolf/run_minigolf.py map [--hole 1] [--no-putter] [--friction 0.6,0.005,0.00135]
        author the level (PIE stopped) -> /Game/Maps/URL/Map_MiniGolf_URL
    python Scripts/pie_tests/minigolf/run_minigolf.py probe [--frame 72]
        start PIE, drive the arm to a stroke pose, print where the bracelet settles relative to the base
    python Scripts/pie_tests/minigolf/run_minigolf.py kick [--kick 1.41]
        launch the ball by its free joint's velocity and report the roll (the rolling-friction calibration)
    python Scripts/pie_tests/minigolf/run_minigolf.py record
        the putt: start PIE, approach, play the stroke from frame 72, record -> recordings/hole1 vN.json
    python Scripts/pie_tests/minigolf/run_minigolf.py stop
        end PIE

Recordings go to recordings/ next to this file (gitignored), numbered and never overwritten.
"""
import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))                        # Scripts/pie_tests
import common  # noqa: E402

OP = HERE / "minigolf_op.py"
BUILD = HERE / "make_minigolf_map.py"
DATA = HERE / "data"
REC = HERE / "recordings"
MAP = "/Game/Maps/URL/Map_MiniGolf_URL"
OP_VAR, OP_TAG = "_minigolf_op", "MINIGOLF"
BUILD_TAG = "MINIGOLFMAP"


def op(cmd):
    """One op call: `op("status")`, `op("goto 3 0 0 0 0 0 0 0")`."""
    return common.remote(OP, OP_VAR, cmd, OP_TAG)


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def stroke_degrees(frame):
    return load_json("stroke_hole1.json")["frames"][frame]


def start_pie(map_path=MAP):
    """Start PIE on `map_path` (default the minigolf level). The op stops a running PIE instead of starting, so call again after it did."""
    r = op("start " + map_path)
    if r.get("stopped"):
        time.sleep(2.0)
        r = op("start " + map_path)
    return r


def wait_ready(seconds=90):
    t0 = time.time()
    last = None
    while time.time() - t0 < seconds:
        try:
            st = op("status")
            last = st
            if st.get("ready") and st.get("bound") and st.get("sim", 0) > 1.0:
                return st
            if st.get("initialized") and not st.get("running"):
                op("run")                     # the map comes up paused: no pawn to start the sim
        except RuntimeError as e:
            last = str(e)[-600:]
        time.sleep(1.0)
    raise SystemExit("the sim did not come up in %d s; last: %s" % (seconds, last))


def build_map(a):
    setup = ["unreal._ramms_minigolf_map = %r" % a.map, "unreal._ramms_minigolf_hole = %d" % a.hole,
             "unreal._ramms_minigolf_base_yaw = %r" % a.base_yaw,
             "unreal._ramms_minigolf_friction = %r" % [float(v) for v in a.friction.split(",")]]
    if not a.no_putter:
        setup.append("unreal._ramms_minigolf_putter = %r" % load_json("putter_head.json"))
    # The builder takes its parameters from attributes on `unreal`, so this is remote_code (arbitrary editor code) rather
    # than a one-string op.
    code = "import unreal; %s; exec(open(r'%s', encoding='utf-8').read())" % ("; ".join(setup), BUILD)
    line = common.remote_code(code, BUILD_TAG + " ")
    print("[map]", json.loads(line.split(BUILD_TAG + " ", 1)[1]))


def probe(a):
    """Drive the arm to the stroke's pose at --frame and report where the bracelet settles relative to the base."""
    deg = stroke_degrees(a.frame)
    q = [math.radians(d) for d in deg]
    q = [((v + math.pi) % (2 * math.pi)) - math.pi for v in q]      # wrap into the actuators' ctrlrange
    print("[probe] starting PIE", start_pie(a.map))
    st = wait_ready()
    print("[probe] ready: sim %.2f, base %s" % (st["sim"], st["base"]["pos"]))
    info = op("arm")
    print("[probe] actuators", info["actuators"][:8], "joints at rest", info["joints"])
    r = op("probe " + " ".join("%.5f" % v for v in q) + " %g" % a.settle)
    print("[probe] take over", r["take_over"], "applied", r["ctrl_applied"])
    print("[probe] ctrl", [round(v, 3) for v in q], "-> joints", r["joints"], "settled", r["settled_sim_s"])
    print("[probe] bracelet in base (Unreal cm)", r["bracelet_in_base"], "base quat", r["base"]["quat"])
    REC.mkdir(exist_ok=True)
    (REC / ("probe-f%d.json" % a.frame)).write_text(json.dumps({"frame": a.frame, "ctrl": q, "reply": r}, indent=1), encoding="utf-8")


def record(a):
    """Start PIE, bring the arm to the stroke's frame f0 pose, play frames f0..f1 on the sim clock, and keep the per-tick
    recording as recordings/hole<N> vK.json. Prints what the ball did."""
    out = common.next_path(REC, "hole%d" % a.hole)
    start_pie(a.map)
    st = wait_ready()
    time.sleep(2.0)                                       # the control slots exist a moment after the sim reports ready
    q0 = [math.radians(d) for d in stroke_degrees(a.f0)]
    print("[record] ready at sim %.2f; moving to the frame %d pose over %g s" % (st["sim"], a.f0, a.approach))
    print("[record]", op("goto %g " % a.approach + " ".join("%.5f" % v for v in q0))["take_over"])
    time.sleep(a.approach + 1.5)
    pose = op("pose")
    print("[record] at address: joints", pose["joints"], "bracelet", pose["bracelet"]["pos"])
    print("[record] bodies", op("headbody"))
    print("[record]", op("play %s|%d|%d|%s" % (DATA / "stroke_hole1.json", a.f0, a.f1, out)))
    while True:
        time.sleep(1.0)
        pr = op("progress")
        if pr["done"]:
            break
        print("[record] frame %.0f, %d samples" % (pr["frame"] or 0, pr["samples"]))
    if pr["error"]:
        raise SystemExit("play failed: %s" % pr["error"])
    rows = json.loads(out.read_text(encoding="utf-8"))["samples"]
    print("[record] %d samples over %.2f s of sim (wall %.2f), written %s" % (len(rows), rows[-1][0] - rows[0][0], rows[-1][1] - rows[0][1], out))
    summarize(rows)
    if not a.keep_pie:
        op("stop")


def kick(a):
    """Launch the ball at --kick m/s down the lane (the free joint's velocity) on a fresh PIE and report the roll: the
    rolling-friction calibration. A free sphere given a pure linear velocity skids to 5/7 of it before it rolls."""
    start_pie(a.map)
    wait_ready()
    time.sleep(1.0)
    print("[kick]", op("kick %g 5" % a.kick))
    time.sleep(7.0)
    r = op("kickresult")
    path = r["path"]
    x0, xe = path[0][1], r["last"][1]
    # the launch speed from the first 0.35 s, the deceleration from the stop distance
    early = [p for p in path if p[0] < 0.35]
    v0 = (early[-1][1] - early[0][1]) / (early[-1][0] - early[0][0]) / 100.0 if len(early) > 1 else float("nan")
    d = (xe - x0) / 100.0
    print("[kick] v0 %.2f m/s (asked %.2f), stopped after %.0f cm: decel %.2f m/s^2; y drift %.1f cm" % (
        v0, a.kick, d * 100, v0 * v0 / (2 * d) if d > 0 else float("nan"), r["last"][2] - path[0][2]))
    if not a.keep_pie:
        op("stop")


def summarize(rows):
    """What the ball did: where it started, when it first moved, its peak speed, where it ended; and the head's path.
    Rows are [sim_s, wall_s, frame, joints, bracelet xf, head xf, ball xf], xf = [x y z qx qy qz qw] in Unreal cm."""
    balls = [(r[0], r[2], r[6]) for r in rows if r[6]]
    if not balls:
        print("[record] no ball in the recording")
        return
    x0 = balls[0][2][:3]
    moved = [(t, f, b) for t, f, b in balls if math.dist(b[:3], x0) > 0.3]
    vmax, tmax = 0.0, None
    for (t1, f1, b1), (t2, f2, b2) in zip(balls, balls[1:]):
        if t2 > t1:
            v = math.dist(b1[:3], b2[:3]) / (t2 - t1)
            if v > vmax:
                vmax, tmax = v, (t2, f2)
    end = balls[-1][2][:3]
    print("[ball] start %s, first moved at frame %s, peak %.0f cm/s at frame %s, end %s (%.0f cm from start, z %.1f)" % (
        [round(v, 1) for v in x0], round(moved[0][1], 1) if moved else None, vmax, round(tmax[1], 1) if tmax else None,
        [round(v, 1) for v in end], math.dist(end[:2], x0[:2]), end[2]))
    heads = [(r[2], r[5]) for r in rows if r[5]]
    if heads:
        lo = min(heads, key=lambda h: h[1][2])
        print("[head] lowest z %.1f at frame %.1f; x range %.1f..%.1f" % (lo[1][2], lo[0], min(h[1][0] for h in heads), max(h[1][0] for h in heads)))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["map", "probe", "record", "kick", "stop"])
    ap.add_argument("--hole", type=int, default=1, help="map: which hole to build (1-3); record names its file after it")
    ap.add_argument("--map", default=MAP, help="the level: map writes it, probe/record/kick start PIE on it")
    ap.add_argument("--base-yaw", type=float, default=-90.0, help="map: yaw of the Gen3 Blueprint at its mount, degrees")
    ap.add_argument("--no-putter", action="store_true", help="map: leave the putter head out")
    ap.add_argument("--friction", default="0.6,0.005,0.00135", help="map: green and ball friction slide,torsion,roll (MuJoCo units)")
    ap.add_argument("--f0", type=int, default=72, help="record: first stroke frame (the arm at address)")
    ap.add_argument("--f1", type=int, default=240, help="record: last stroke frame")
    ap.add_argument("--approach", type=float, default=3.0, help="record: seconds to ramp from the start pose to the frame f0 pose")
    ap.add_argument("--keep-pie", action="store_true", help="leave PIE running afterwards")
    ap.add_argument("--kick", type=float, default=1.41, help="kick: the ball's launch speed, m/s")
    ap.add_argument("--frame", type=int, default=72, help="probe: the stroke frame to drive the arm to")
    ap.add_argument("--settle", type=float, default=3.0, help="probe: seconds of sim time to settle")
    a = ap.parse_args()
    if a.cmd == "stop":
        print(op("stop"))
    elif a.cmd == "map":
        build_map(a)
    elif a.cmd == "record":
        record(a)
    elif a.cmd == "kick":
        kick(a)
    else:
        probe(a)


if __name__ == "__main__":
    main()

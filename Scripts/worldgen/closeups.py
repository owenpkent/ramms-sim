"""Street-level close-ups of one example level, for judging facades and props.

    exec(open(r"C:/Users/waemf/data/ramms/Scripts/worldgen/closeups.py").read())
Set CLOSEUP_MAP / CLOSEUP_VIEWS before exec to change the level or the camera list.
Screenshots: Saved/Screenshots/WindowsEditor/Close_<Map>_<n>.png
"""
import time
import unreal

MAP = globals().get("CLOSEUP_MAP", "/Game/Maps/Gen/Map_Gen_Downtown")
# (offset from site centre as fraction of site size: x, y, z) and a look-at offset (fractions)
VIEWS = globals().get("CLOSEUP_VIEWS", [
    ((-0.02, -0.52, 0.012), (-0.02, 0.0, 0.03)),   # standing on a street, looking along it
    ((-0.26, -0.30, 0.015), (0.0, -0.10, 0.05)),   # a facade from the sidewalk
    ((0.20, 0.05, 0.10), (0.0, 0.30, 0.0)),        # low oblique over a block
    ((0.0, -0.40, 0.25), (0.0, 0.0, 0.0)),         # elevated
])
st = {"phase": "load", "until": 0.0, "i": 0, "handle": None, "busy": False}


def cam(i):
    import ramms_worldgen._helpers as H
    gen = H.find_generator()
    p = gen.get_editor_property("params")
    d = max(p.get_editor_property("site_size_x"), p.get_editor_property("site_size_y"))
    loc = gen.get_actor_location()
    (ox, oy, oz), (tx, ty, tz) = VIEWS[i]
    c = unreal.Vector(loc.x + d * ox, loc.y + d * oy, loc.z + d * oz)
    t = unreal.Vector(loc.x + d * tx, loc.y + d * ty, loc.z + d * tz)
    rot = unreal.MathLibrary.find_look_at_rotation(c, t)
    unreal.get_editor_subsystem(unreal.UnrealEditorSubsystem).set_level_viewport_camera_info(c, rot)


def tick(dt):
    if st["busy"] or time.time() < st["until"]:
        return
    st["busy"] = True
    try:
        if st["phase"] == "load":
            unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).load_level(MAP)
            st["phase"] = "cam"; st["until"] = time.time() + 3.0
        elif st["phase"] == "cam":
            if st["i"] >= len(VIEWS):
                unreal.unregister_slate_post_tick_callback(st["handle"]); unreal.log("[closeups] done"); return
            cam(st["i"]); st["phase"] = "shoot"; st["until"] = time.time() + 4.0
        elif st["phase"] == "shoot":
            unreal.AutomationLibrary.take_high_res_screenshot(1600, 900, "Close_%s_%d" % (MAP.rsplit("/", 1)[-1], st["i"]))
            st["i"] += 1; st["phase"] = "cam"; st["until"] = time.time() + 2.0
    except Exception as exc:
        unreal.log_warning("[closeups] %s" % exc); st["phase"] = "cam"; st["i"] += 1; st["until"] = time.time() + 1.0
    finally:
        st["busy"] = False


st["handle"] = unreal.register_slate_post_tick_callback(tick)
unreal.log("[closeups] started")

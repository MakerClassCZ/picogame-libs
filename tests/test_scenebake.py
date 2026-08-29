"""picogame_scenebake must bake a level EXACTLY like tools/scene_build.py does.

The device baker and the desktop CLI are two implementations of one format. If they drift, a level
runs differently depending on which one baked it - the worst kind of bug, because both look right in
isolation. So every fixture here is compared against a golden produced by the CLI itself
(`fixtures/*_golden.py`, regenerate with `python3 tools/scene_build.py <fixture>.json`).

The browser copy (picogame-web/web/play/scene_bake.py) gets the same guarantee from web/tbake.mjs.
"""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import json
import os

import picogame_scenebake

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
FIXTURES = ["demo_platformer_scene", "demo_openworld_scene", "ext_orient_scene"]


def _golden(name):
    """The CLI's baked module, executed for its SCENE dict (it is plain data, no imports)."""
    ns = {}
    with open(os.path.join(FIX, name + "_golden.py")) as f:
        exec(f.read(), ns)
    return ns["SCENE"]


def _norm(o):
    """Tuples and lists mean the same thing here (JSON gives lists, the CLI writes tuples);
    everything else must match exactly, bytes included."""
    if isinstance(o, (tuple, list)):
        return [_norm(x) for x in o]
    if isinstance(o, dict):
        return {k: _norm(v) for k, v in sorted(o.items())}
    return o


def test_bake_matches_the_cli_on_every_fixture():
    for name in FIXTURES:
        with open(os.path.join(FIX, name + ".json")) as f:
            scene = json.load(f)
        got = _norm(picogame_scenebake.bake(scene))
        want = _norm(_golden(name))
        assert set(got) == set(want), "%s: keys %s != %s" % (name, sorted(got), sorted(want))
        for k in want:
            assert got[k] == want[k], "%s: '%s' differs from the CLI" % (name, k)


def test_colours_are_wire_order():
    # A byte-swapped palette is the failure this catches: the loader writes the baked palette
    # straight into the native framebuffer, so authored brown would come out light blue.
    assert picogame_scenebake._w565((255, 0, 0)) == 0x00F8
    assert picogame_scenebake._w565((0, 0, 0)) == 0
    assert picogame_scenebake._w565((255, 255, 255)) == 0xFFFF


def test_png_backed_assets_are_declined_not_mangled():
    for kind in ("sprite", "bitmap", "tileset"):
        scene = {"size": [320, 240], "assets": {"a": {"type": kind, "src": "x.png", "fw": 8, "fh": 8}},
                 "layers": []}
        try:
            picogame_scenebake.bake(scene)
        except NotImplementedError:
            continue
        raise AssertionError("%s asset should raise NotImplementedError (needs the desktop CLI)" % kind)


def test_unknown_asset_type_is_an_error():
    scene = {"size": [320, 240], "assets": {"a": {"type": "wat"}}, "layers": []}
    try:
        picogame_scenebake.bake(scene)
    except ValueError:
        return
    raise AssertionError("an unknown asset type must raise, not bake silently")


def test_sparse_colour_map_fills_gaps_with_magenta():
    # A tileset_color whose keys skip a value must still produce a dense palette - a missing entry
    # bakes as magenta so the gap is VISIBLE on screen rather than silently black.
    scene = {"size": [320, 240], "layers": [],
             "assets": {"t": {"type": "tileset_color", "tile": [8, 8],
                              "colors": {"1": [10, 20, 30], "3": [40, 50, 60]}}}}
    fmt, hexdata, tw, th, frames, transp, pal = picogame_scenebake.bake(scene)["assets"]["t"]
    assert frames == 4, "tiles 0..3 -> 4 frames, got %d" % frames
    assert pal[2] == picogame_scenebake._w565((255, 0, 255)), "the skipped index must be magenta"


def test_load_json_builds_a_view_and_releases_the_baker():
    # The whole point of load_json is that the JSON text and the parse tree are LOCALS: they are
    # unreachable the moment it returns. What we can assert here is the observable contract -
    # a working View, and (release=True) the baker module gone from sys.modules.
    import sys
    import picogame as pg
    import picogame_scene

    path = os.path.join(FIX, "demo_platformer_scene.json")
    sys.modules.pop("picogame_scenebake", None)
    view = picogame_scene.load_json(pg, path)
    assert view.scene is not None
    assert view.point("spawn") == (40, 208), "named points must survive the on-device bake"
    assert view.is_solid(0, 14), "tile props must survive it too"
    assert "picogame_scenebake" not in sys.modules, "release=True must drop the baker (~3.6 kB)"

    view2 = picogame_scene.load_json(pg, path, release=False)
    assert view2.scene is not None
    assert "picogame_scenebake" in sys.modules, "release=False must keep it for the next level"


def test_load_json_and_the_prebaked_module_agree():
    # Same level, both routes -> the game must not be able to tell which one built it.
    import picogame as pg
    import picogame_scene
    a = picogame_scene.load_json(pg, os.path.join(FIX, "demo_platformer_scene.json"))
    b = picogame_scene.load(pg, _golden("demo_platformer_scene"))
    assert a.point("spawn") == b.point("spawn")
    assert a.camera == b.camera
    assert [a.is_solid(x, 14) for x in range(20)] == [b.is_solid(x, 14) for x in range(20)]

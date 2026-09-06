"""picogame_scene.Game: one game.json in, levels out - streamed on the device, whole-file here.

The walker (picogame_scenebake.walk) runs the SAME code on CPython through _load_first's
raw_decode shim, so these tests exercise the streaming path, not just json.load."""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import io
import json
import os
import sys
import tempfile

import picogame as pg
import picogame_scene
import picogame_scenebake as sb

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
GAME = os.path.join(FIX, "quest_game.json")


def _tmp_copy(text=None):
    d = tempfile.mkdtemp()
    p = os.path.join(d, "game.json")
    with open(p, "w") as f:
        f.write(text if text is not None else open(GAME).read())
    return p


def test_walker_reads_every_top_level_value_and_streams_levels():
    seen = []
    with open(GAME, "rb") as f:
        top = sb.walk(f, lambda lv, i, pos: seen.append((i, lv["name"], pos)))
    assert top["name"] == "Quest" and top["start"] == "village"
    assert sorted(top["assets"]) == ["goomba", "hero", "tiles"]
    assert [n for _, n, _ in seen] == ["village", "cave"]
    assert top["_levels"] == 2
    # the reported offsets point at each level's opening brace
    raw = open(GAME, "rb").read()
    for _, _, pos in seen:
        assert raw[pos:pos + 1] == b"{"


def test_walker_stops_early_for_the_launcher():
    with open(GAME, "rb") as f:
        top = sb.walk(f, None, {"name", "icon"} & {"name"})
    assert top["name"] == "Quest"
    assert "assets" not in top, "stop_after must return before the big keys"
    assert sb.head(GAME, ("name", "launcher"))["launcher"]["category"] == "demo"


def test_walker_takes_any_key_order():
    d = json.load(open(GAME))
    shuffled = {"levels": d["levels"], "assets": d["assets"], "name": d["name"],
                "size": d["size"], "start": d["start"]}
    p = _tmp_copy(json.dumps(shuffled))
    g = picogame_scene.Game(pg, p)
    assert g.levels == ["village", "cave"] and g.start == "village"
    assert g.load("cave").named["player"] is not None


def test_game_bakes_all_levels_at_boot_and_releases_the_baker():
    sys.modules.pop("picogame_scenebake", None)
    g = picogame_scene.Game(pg, GAME)
    assert g.levels == ["village", "cave"]
    assert g.start == "village" and g.size == (320, 240) and g.name == "Quest"
    assert "picogame_scenebake" not in sys.modules, "the baker must be released after boot"
    v = g.load()
    assert v.name == "village"
    assert v.named["player"] is not None
    assert len(v.group("foes")) == 3, "a tagged single sprite joins its group next to the group layer"
    assert v.effects and v.effects[0]["swap"] == [7, 0]
    assert v.world == (640, 240)
    assert v.is_solid(0, 0) and not v.is_solid(1, 1)
    assert v.tilemap.get_tile(6, 2) == 7, "legend from the ASSET must map G -> 7"
    assert len(v.zones) == 4 and v.zones[0][5]["say"]


def test_goto_reuses_the_strip_buffers_and_places_the_player():
    g = picogame_scene.Game(pg, GAME)
    v1 = g.load("village")
    bufs = (v1.bufA, v1.bufB)
    v2 = g.load("cave", "entry")
    assert (v2.bufA, v2.bufB) == bufs or bufs == (None, None)
    assert (v2.named["player"].x, v2.named["player"].y) == (24, 32)


def test_lazy_mode_keeps_offsets_and_bakes_on_demand():
    g = picogame_scene.Game(pg, GAME, lazy=True)
    assert g.levels == ["village", "cave"]
    assert set(g._offsets) == {"village", "cave"}
    assert not g._baked
    v = g.load("cave")
    assert v.tilemap.get_tile(1, 1) == 0 and v.is_solid(0, 0)
    try:
        g.load("nowhere")
    except KeyError as e:
        assert "nowhere" in str(e)
    else:
        raise AssertionError("an unknown level must raise KeyError")


def test_module_mode_imports_bank_and_levels_on_demand():
    # what scene_build.py build writes: game_bank.py (BANK + levels/start/size) and level_<name>.py
    d = json.load(open(GAME))
    bank = sb.bake_bank(d["assets"], d.get("sounds"))
    bank.update({"levels": [lv["name"] for lv in d["levels"]], "start": d["start"], "size": d["size"]})
    tmp = tempfile.mkdtemp()
    with open(os.path.join(tmp, "quest_bank.py"), "w") as f:
        f.write("BANK = " + repr(bank) + "\n")
    for lv in d["levels"]:
        with open(os.path.join(tmp, "level_%s.py" % lv["name"]), "w") as f:
            f.write("LEVEL = " + repr(sb.bake_level(lv, d["size"], d["assets"])) + "\n")
    sys.path.insert(0, tmp)
    try:
        g = picogame_scene.Game(pg, "quest_bank")
        assert g.levels == ["village", "cave"] and g.start == "village"
        assert "quest_bank" not in sys.modules
        v = g.load("village")
        assert "level_village" not in sys.modules, "a level module must not stay resident"
        assert v.tilemap.get_tile(6, 2) == 7
    finally:
        sys.path.remove(tmp)


def test_json_errors_name_the_level_and_the_byte():
    text = open(GAME).read().replace('"name": "cave"', '"name": "cave",,')
    p = _tmp_copy(text)
    try:
        picogame_scene.Game(pg, p)
    except ValueError as e:
        assert "level 1" in str(e) and "byte" in str(e), str(e)
    else:
        raise AssertionError("broken JSON must raise a ValueError naming the level")


def test_pal8_sidecar_round_trip_and_mismatch_message():
    data = bytes([0, 1, 2, 3] * 4 * 2)          # 4x4, 2 frames -> stride 8, 4 rows = 32 bytes
    blob = sb.encode_pal8(data, 4, 4, 2, [0, 0xF800, 0x07E0, 0x001F], 0)
    tmp = tempfile.mkdtemp()
    path = os.path.join(tmp, "hero.pal8")
    with open(path, "wb") as f:
        f.write(blob)
    pal, got, fw, fh, frames, transp = picogame_scene.read_pal8(path)
    assert (fw, fh, frames, transp) == (4, 4, 2, 0) and bytes(got) == data and list(pal)[1] == 0xF800
    bank = sb.bake_bank({"hero": {"type": "sprite", "src": "hero.png", "frame": [4, 4], "frames": 2}},
                        None, tmp)
    assert bank["assets"]["hero"][0] == "pal8f" and bank["assets"]["hero"][1].endswith("hero.pal8")
    bm = picogame_scene.load_bank(pg, bank)["bitmaps"]["hero"]
    assert bm.width == 4 and bm.frames == 2
    bad = sb.bake_bank({"hero": {"type": "sprite", "src": "hero.png", "frame": [4, 8], "frames": 2}},
                       None, tmp)
    try:
        picogame_scene.load_bank(pg, bad)
    except ValueError as e:
        assert "4x4x2" in str(e) and "4x8x2" in str(e) and "scene_build.py art" in str(e)
    else:
        raise AssertionError("a geometry mismatch must raise with the fix in the message")


def test_load_json_opens_a_project_too():
    v = picogame_scene.load_json(pg, GAME)
    assert v.name == "village"


def test_launcher_reads_game_json_as_the_fourth_source():
    import picogame_launcher
    tmp = tempfile.mkdtemp()
    folder = os.path.join(tmp, "quest")
    os.mkdir(folder)
    with open(os.path.join(folder, "game.json"), "w") as f:
        f.write(open(GAME).read())
    apps = picogame_launcher._apps_in(folder, "games")
    assert len(apps) == 1
    a = apps[0]
    assert a.title == "Quest" and a.category == "demo" and a.author == "picogame"

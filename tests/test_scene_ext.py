"""picogame_scene format extensions — tile orientations, sprite angle, zone/point data —
plus the scene_build baker side and the tiled2scene orientation map (Tiled H/V/D bits ->
native flipX/flipY/transpose; the axes SWAP when the diagonal bit is set, so the lookup
table is regression-tested against a from-scratch derivation of both transform stacks)."""
import _bootstrap  # noqa: F401

import os
import sys

import picogame as pg
import picogame_scene

# tools/ (scene_build.py, tiled2scene.py) live in the sibling dev or public checkout.
_REPOS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _cand in ("picogame-final", "picogame-dev", "picogame"):
    _tools = os.path.join(_REPOS, _cand, "tools")
    if os.path.exists(os.path.join(_tools, "scene_build.py")):
        sys.path.insert(0, _tools)
        break
import scene_build
import tiled2scene


def _mini_scene():
    """A baked-shape scene dict (what scene_build emits) with every new field."""
    pal = (0, 0xFFFF)
    tile = bytes([0] * 32 + [1] * 32)                     # 8x8 frame0 empty-ish, frame1 solid
    return {
        "bg": 0,
        "assets": {"t": ("pal8", tile.hex(), 8, 8, 2, 0, pal)},
        "tileprops": {}, "anims": {},
        "layers": [
            ("tilemap", "t", 2, 2, 0, 0, bytes([1, 1, 0, 1]), bytes([0, 5, 0, 0])),
            ("sprite", "t", "hero", 10, 20, 0, 1, 1, {"hp": 3}, None, 90),
        ],
        "camera": None,
        "zones": [("goal", 24, 0, 8, 16, {"next": "level2"})],
        "points": {"spawn": (4, 20)},
        "pdata": {"spawn": {"wave": 1}},
    }


def test_loader_applies_orient_angle_and_data():
    v = picogame_scene.load(pg, _mini_scene())
    tm = v.tilemap
    assert tm._orient is not None
    assert tm._orient[1] == 5                              # flipX + transpose survived
    assert tm._orient[0] == 0 and tm._orient[3] == 0
    assert v.named["hero"].angle == 90
    assert v.named["hero"].data == {"hp": 3}
    assert v.pdata["spawn"] == {"wave": 1}
    assert v.point("spawn") == (4, 20)                    # (x, y) shape unchanged
    z = v.in_zone(25, 5, "goal")
    assert z[5] == {"next": "level2"}


def test_loader_backcompat_old_tuples():
    s = _mini_scene()
    s["layers"] = [
        ("tilemap", "t", 2, 2, 0, 0, bytes([1, 0, 0, 1])),          # no orient plane
        ("sprite", "t", "old", 0, 0, 0, 0, 0, None, None),          # no angle field
    ]
    s["zones"] = [("goal", 0, 0, 8, 8)]                             # 5-tuple zone
    del s["pdata"]
    v = picogame_scene.load(pg, s)
    assert v.tilemap._orient is None
    assert v.named["old"].angle == 0
    assert v.pdata == {}
    assert v.in_zone(1, 1, "goal") is not None


def test_baker_splits_orientation_plane():
    layer = {"kind": "tilemap", "asset": "t", "pos": [0, 0],
             "grid": [[1, 1 | (5 << 8)], [0, 2]]}
    out = scene_build.bake_tilemap(layer)
    assert len(out) == 8
    assert out[6] == bytes([1, 1, 0, 2])                  # tile bits masked
    assert out[7] == bytes([0, 5, 0, 0])                  # orient plane
    plain = scene_build.bake_tilemap({"kind": "tilemap", "asset": "t", "pos": [0, 0],
                                      "grid": [[1, 0], [0, 2]]})
    assert len(plain) == 7                                # no plane when unused


def test_baker_validates_orientation_bits():
    scene = {"assets": {"t": {"type": "tileset_color", "tile": [8, 8],
                              "colors": {"1": [255, 0, 0]}}},
             "layers": [{"kind": "tilemap", "asset": "t", "pos": [0, 0],
                         "grid": [[1 | (9 << 8)], [0 | (1 << 8)]]}]}
    errs = scene_build.validate(scene)
    assert any("bad orientation bits" in e for e in errs)
    assert any("orientation bits on an empty cell" in e for e in errs)


def test_orient_map_matches_derivation():
    """Re-derive Tiled(H,V,D) -> pg(fx,fy,tp) from both transform definitions and
    compare with the shipped table (guards both sides against 'simplification')."""
    def pg_t(S, fx, fy, tp):
        sh, sw = len(S), len(S[0])
        if tp:
            return [[S[sh - 1 - lx if fy else lx][sw - 1 - ly if fx else ly]
                     for lx in range(sh)] for ly in range(sw)]
        return [[S[sh - 1 - r if fy else r][sw - 1 - c if fx else c]
                 for c in range(sw)] for r in range(sh)]

    def tiled_t(S, H, V, D):
        if D:
            S = [list(col) for col in zip(*S)]
        if H:
            S = [row[::-1] for row in S]
        if V:
            S = S[::-1]
        return S

    S = [[1, 2, 3], [4, 5, 6]]
    for bits in range(8):
        want = tiled_t(S, bool(bits & 1), bool(bits & 2), bool(bits & 4))
        hits = [fx | fy << 1 | tp << 2 for fx in (0, 1) for fy in (0, 1) for tp in (0, 1)
                if pg_t(S, fx, fy, tp) == want]
        assert hits == [tiled2scene.ORIENT_MAP[bits]], bits


def test_set_tile_prop_flips_at_runtime():
    s = _mini_scene()
    s["tileprops"] = {"t": {"solid": bytes([0, 1])}}       # tile 1 baked solid
    v = picogame_scene.load(pg, s)
    assert v.is_solid(0, 0)                                # cell (0,0) holds tile 1
    v.set_tile_prop(1, "solid", False)                     # the lever opens the gate
    assert not v.is_solid(0, 0)
    v.set_tile_prop(1, "solid", True)
    assert v.is_solid(0, 0)


def test_set_tile_prop_creates_missing_table():
    v = picogame_scene.load(pg, _mini_scene())             # no tileprops baked at all
    assert not v.tile_has(0, 0, "hazard")
    v.set_tile_prop(1, "hazard")
    assert v.tile_has(0, 0, "hazard")                      # cell (0,0) holds tile 1
    assert not v.tile_has(0, 1, "hazard")                  # cell (0,1) holds tile 0


def test_set_tile_prop_does_not_leak_between_bank_loads():
    s = _mini_scene()
    s["tileprops"] = {"t": {"solid": bytes([0, 1])}}
    bank = picogame_scene.load_bank(pg, {"assets": s["assets"],
                                         "tileprops": s["tileprops"], "anims": {}})
    lvl = {k: s[k] for k in ("bg", "layers", "camera")}
    a = picogame_scene.load(pg, lvl, bank=bank)
    a.set_tile_prop(1, "solid", False)                     # mutate level A's meaning
    b = picogame_scene.load(pg, lvl, bank=bank)            # a fresh load of the same bank
    assert not a.is_solid(0, 0)
    assert b.is_solid(0, 0)                                # ...must come back solid
    assert bank["tileprops"]["t"]["solid"][1] == 1         # the bank itself untouched


def test_set_tile_prop_grows_short_baked_table():
    s = _mini_scene()
    s["tileprops"] = {"t": {"solid": bytes([0, 1])}}       # table of length 2
    v = picogame_scene.load(pg, s)
    v.set_tile_prop(7, "solid")                            # beyond the baked length
    assert len(v._props["t"]["solid"]) >= 8
    assert v.is_solid(0, 0)                                # existing flags survived the grow

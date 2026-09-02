"""picogame_fx.Shake — screen-shake (shake.add/tick, 14 calls). Driven with a fake scene that just
records set_view(), so we test the trauma model + the idle early-out + bounded offset without any
engine. (A1 change: idle must not call the RNG; offsets stay within max_offset; trauma decays.)"""
import _bootstrap  # noqa: F401

import picogame_fx as FX


class FakeScene:
    def __init__(self):
        self.view = None
        self.calls = 0

    def set_view(self, x, y):
        self.view = (x, y)
        self.calls += 1


def test_shake_idle_tracks_camera_no_shake():
    s = FakeScene()
    sh = FX.Shake(s)
    r = sh.tick(5, 7)                       # trauma 0 -> just apply the camera, no offset
    assert r is False
    assert s.view == (5, 7)


def test_shake_active_within_bounds():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6)
    sh.add(1.0)
    for _ in range(5):
        r = sh.tick(0, 0)
        ox, oy = s.view
        assert -6 <= ox <= 6 and -6 <= oy <= 6   # offset never exceeds max_offset
        assert r is True                          # still shaking


def test_shake_offset_rides_camera():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6)
    sh.add(1.0)
    sh.tick(100, 200)
    ox, oy = s.view
    assert 100 - 6 <= ox <= 100 + 6              # shake is added ON TOP of the camera
    assert 200 - 6 <= oy <= 200 + 6


def test_shake_decays_and_stops():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6, decay=0.1)
    sh.add(0.3)
    ticks = 0
    while sh.tick(0, 0):
        ticks += 1
        assert ticks < 100                       # must terminate
    assert sh.trauma == 0.0
    # once stopped, idle ticks keep working and stay centred
    assert sh.tick(0, 0) is False
    assert s.view == (0, 0)


def test_shake_add_clamps_to_one():
    sh = FX.Shake(FakeScene())
    sh.add(0.8)
    sh.add(0.8)
    assert sh.trauma <= 1.0


def test_shake_sceneless_exposes_offsets_only():
    """scene=None: no set_view target at all - tick() just publishes ox/oy for the game's
    own renderer params (road lateral, raycaster horizon). The StripDraw-genre mode."""
    sh = FX.Shake(None, max_offset=6)
    assert sh.tick(3, 4) is False and (sh.ox, sh.oy) == (0, 0)   # idle: zero offset, no crash
    sh.add(1.0)
    moved = False
    for _ in range(6):
        sh.tick()
        assert -6 <= sh.ox <= 6 and -6 <= sh.oy <= 6
        moved = moved or sh.ox or sh.oy
    assert moved                                    # the model actually produced offsets


def test_shake_scene_mode_offsets_match_the_applied_view():
    s = FakeScene()
    sh = FX.Shake(s, max_offset=6)
    sh.add(1.0)
    sh.tick(10, 20)
    assert s.view == (10 + sh.ox, 20 + sh.oy)       # ox/oy are exactly what set_view got


def _sprite():
    import picogame as pg
    bm = pg.Bitmap(bytearray(4), 2, 2)
    return pg.Sprite(bm, 0, 0)


def test_flash_lights_for_exactly_the_frames_asked():
    """The hand-rolled counter renders 2 frames as 1 (spent before the frame it covers);
    Flash counts DRAWN frames."""
    s = _sprite()
    fl = FX.Flash(s)
    fl.hit(0xF800, 2)
    lit = 0
    for _ in range(5):
        if s.flash:                 # what the compositor would draw this frame
            lit += 1
        fl.tick()
    assert lit == 2
    assert not s.flash


def test_flash_restores_the_effect_it_replaced():
    """flash shares ONE slot with tint/dither/shadow, so a flashed sprite must come back
    wearing what it had (a permanently dithered ghost stays a ghost after being hit)."""
    s = _sprite()
    s.dither = 6
    fl = FX.Flash(s)
    fl.hit(0xFFFF, 1)
    assert s.flash and not s.dither
    fl.tick()
    assert not s.flash and s.dither == 6


def test_flash_rearm_extends_but_never_shortens():
    s = _sprite()
    fl = FX.Flash(s)
    fl.hit(0xF800, 3)
    fl.hit(0xF800, 1)               # a second hit in the same frame must not cut it short
    assert fl.t == 3


# ---- Camera + a reserved HUD band (round-9 finding: BAND px lost at both world edges) ---------

def _band_scene(top=0, bottom=0):
    import board
    import picogame as pg
    d = board.DISPLAY
    return pg.Scene(d, bytearray(d.width * 24 * 2), bytearray(d.width * 24 * 2),
                    background=0, top=top, bottom=bottom), d


def _snap(cam, x, y):
    return cam.follow(x, y, snap=True).offset()


def test_camera_defaults_centre_and_clamp_to_the_screen():
    scene, d = _band_scene()
    W, H = d.width, d.height
    cam = FX.Camera(scene, W, H, world_w=2 * W, world_h=2 * H)
    assert _snap(cam, W, H) == (-W // 2, -H // 2)          # centred: world (W,H) at screen centre
    assert _snap(cam, -500, -500) == (0, 0)                # top-left edge
    assert _snap(cam, 5000, 5000) == (W - 2 * W, H - 2 * H)  # bottom-right edge


def test_camera_band_centres_and_clamps_inside_the_visible_rect():
    BAR = 20
    scene, d = _band_scene(top=BAR)
    W, H = d.width, d.height
    cam = FX.Camera(scene, W, H, world_w=2 * W, world_h=2 * H, top=BAR)
    vis_h = H - BAR
    # centre sits in the middle of the VISIBLE part, i.e. BAR px lower than a bandless camera
    assert _snap(cam, W, H)[1] == BAR + vis_h // 2 - H
    # top edge: world row 0 lands just under the HUD, not beneath it
    assert _snap(cam, -500, -500) == (0, BAR)
    # bottom edge: the last world row reaches the bottom of the screen (the old H+BAR trick
    # stopped BAR px short of it)
    assert _snap(cam, 5000, 5000)[1] == H - 2 * H


def test_camera_band_mismatch_is_flagged_by_the_sim():
    import _host
    scene, d = _band_scene(top=20)
    _host.take_notes()
    FX.Camera(scene, d.width, d.height, top=20)
    assert not [n for n in _host.take_notes() if "Camera(" in n], "matching band: no note"
    FX.Camera(scene, d.width, d.height)                     # forgot the band
    notes = [n for n in _host.take_notes() if "Camera(" in n]
    assert notes and "top=20" in notes[0], notes

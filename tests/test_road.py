"""picogame_road.Road - the wrapper around the native road pair. Pins the contract the
round-2 racing probe had to derive by hand: human-unit cfg, the int32-safe power-of-two
phase wrap, hill headroom sizing, and the gameplay queries staying consistent with the
tables the C actually reads."""
import _bootstrap  # noqa: F401

import picogame as pg
import picogame_road

W, H = 320, 240
COLORS = dict(sky=1, road_a=2, road_b=3, rumble_a=4, rumble_b=5, dash=6)


def make(**kw):
    return picogame_road.Road(pg, W, H, H // 3, COLORS, **kw)


def test_straight_road_is_symmetric():
    r = make(curves=((1024, 0.0),))
    r.tick(1234)
    mid = W // 2
    for i in range(r.rows):
        assert abs((r.rl[i] + r.rr[i]) / 2 - mid) < 1


def test_curve_wraps_continuously():
    r = make()
    r.tick(777)
    a = (list(r.rl), list(r.rr))
    r.tick(777 + r._wrap * 5)          # any multiple of the longest period
    assert (list(r.rl), list(r.rr)) == a       # the ROAD SHAPE is wrap-periodic


def test_stripe_phases_stay_small_and_continuous():
    r = make()
    # bounded (no big-int growth on device) ...
    for d in (0, 10 ** 9, 10 ** 12):
        r.tick(d)
        assert 0 <= r._d05 < 512 and 0 <= r._d07 < 512
    # ... and the parity a row actually reads never skips a step for monotone dist
    band = r._band
    flips = 0
    last = None
    for i in range(200):
        r.tick(i * band / 10)          # 10 samples per stripe
        par = (r._d05 >> 8) & 1
        if last is not None and par != last:
            flips += 1
        last = par
    assert 18 <= flips <= 22           # ~20 stripe boundaries crossed, each exactly once


def test_periods_are_rounded_to_pow2():
    r = make(curves=((1000, 50.0), (300, 10.0)))
    for p in r._periods:
        assert p & (p - 1) == 0        # power of two -> f exact -> no wrap jump


def test_curve_at_matches_the_bend_direction():
    r = make()
    d = r._wrap // 8                   # first sine positive
    r.tick(d)
    tip = (r.rl[0] + r.rr[0]) / 2 - W // 2
    c = r.curve_at(d)
    assert c != 0 and (c > 0) == (tip > 0)


def test_lateral_shifts_the_whole_road():
    r = make(curves=((1024, 0.0),))
    r.tick(0, 0)
    base = r.rr[r.rows - 1]            # right edge: stays positive, so trunc-toward-zero
    r.tick(0, 25)                      # cannot introduce an off-by-one across zero
    assert r.rr[r.rows - 1] == base - 25


def test_hill_headroom_sizes_the_tables():
    r = make(hill_amp=24)
    assert r.rows == (H - H // 3) + 24
    assert len(r.rl) == r.rows and len(r._hw) == r.rows
    assert r.horizon_now == r.horizon  # flat until a grade is set
    r.set_grade(1.0)
    assert r._pitch == -24             # downhill lifts the horizon
    assert r.horizon_now == r.horizon - 24
    r.set_grade(-0.5)
    assert r.horizon_now == r.horizon + 12
    # a plain attribute, not a property: Road.tick's stores must not pay the accessor lookup
    assert not any(isinstance(v, property) for v in vars(type(r)).values())


def test_row_queries_are_consistent():
    r = make()
    row = r.row_of(0)
    assert row == r.rows - 1           # z=0 -> at the car (no hills: nominal == full bottom)
    assert r.row_of(10 ** 9) is None   # beyond the horizon
    assert r.half_of(r.rows - 1) > r.half_of(0)          # near > far
    r.tick(0)
    l, rr_ = r.edges_of(r.rows - 1)
    assert rr_ - l == 2 * r.half_of(r.rows - 1) or abs((rr_ - l) - 2 * r.half_of(r.rows - 1)) <= 1


def test_draw_paints_sky_and_road():
    r = make(curves=((1024, 0.0),))
    r.tick(0)
    cv = pg.Canvas(W, H)
    r.draw(cv, 0)                      # full-frame view at vy=0
    assert cv._data[0] == COLORS["sky"]                       # above the horizon
    mid_bottom = (H - 1) * W + W // 2
    assert cv._data[mid_bottom] in (COLORS["road_a"], COLORS["road_b"], COLORS["dash"])


def test_row_of_anchors_at_the_nominal_bottom_with_hills():
    """The curve sampling anchors dist at the NOMINAL bottom row (cfg drow = nrow-1); row_of
    must anchor there too, or every sprite sits hill_amp rows too low the moment hills are on
    (the round-3 racing probe shipped its own mapping because of exactly this)."""
    r = make(hill_amp=18)
    nrow = (240 - 240 // 3)
    assert r.cfg[6] == nrow - 1
    assert r.row_of(0) == nrow - 1     # the car, NOT the headroom bottom
    assert r.row_of(0) == r.cfg[6]     # one anchor for sampling and placement

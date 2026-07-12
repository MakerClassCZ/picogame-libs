"""picogame_clock — the frame-rate cap + dt (clock.tick 68 calls) and fixed-step accumulator.
Drives the module through a CONTROLLED millisecond clock (monkeypatch _ms/_sleep) so we can assert
exact rates, wrap-safety across the 2**29 boundary, and the no-dt-inflation contract on overload."""
import _bootstrap  # noqa: F401

import picogame_clock as C

_MASK = (1 << 29) - 1
_clock = {"t": 0}

# Drive the module off our controlled clock instead of the wall clock.
C._ms = lambda: _clock["t"] & _MASK
C._sleep = lambda s: None                       # default: sleeping doesn't advance our clock


def _set(t):
    _clock["t"] = t & _MASK


def test_metronome_exact_average_rate():
    for rate in (24, 30, 40, 50, 60, 120):
        m = C._Metronome(rate)
        m._next = 0
        start = m._next
        for _ in range(rate):                   # exactly `rate` intervals == exactly 1000 ms
            m.advance()
        assert (m._next - start) & _MASK == 1000, "rate %d" % rate


def test_metronome_jitter_bounded():
    m = C._Metronome(60)
    m._next = 0
    prev, incs = 0, set()
    for _ in range(600):
        m.advance()
        incs.add((m._next - prev) & _MASK)
        prev = m._next
    assert incs == {16, 17}                      # 60 fps == 16.67 ms, spread as 16/17 only


def test_fixedstep_exact_steps_per_second():
    for sf in (30, 50, 60):
        _set(0)                                 # clock at 0 BEFORE construct so the metronome primes
        fs = C.FixedStep(sf, max_steps=10000)   # from 0 (don't poke _next: that desyncs the carry)
        total, t = 0, 0
        while t < 1000:
            t = min(t + 33, 1000)                # ~30 fps frames, land exactly on 1000 ms
            _set(t)
            total += fs.step_count()
        assert total == sf, "sf=%d got %d" % (sf, total)
        assert abs(fs.dt - 1.0 / sf) < 1e-12


def test_fixedstep_backlog_capped():
    _set(0)
    fs = C.FixedStep(60, max_steps=5)
    fs._metro._next = 0
    _set(10_000)                                 # 10 s stall
    assert fs.step_count() == 5                  # capped, no spiral
    _set(10_017)
    assert fs.step_count() <= 2                  # resynced, resumes normally


def test_clock_wrap_dt_sane():
    C._sleep = lambda s: None
    _set(_MASK - 40)
    clk = C.Clock(30)
    clk._metro._next = (_MASK - 40)
    clk._last = (_MASK - 40)
    t = _MASK - 40
    dts = []
    for _ in range(6):                           # step across the 2**29 wrap
        t += 33
        _set(t)
        dts.append(clk.tick())
    assert all(0.0 <= d <= 0.1 for d in dts)     # never negative/garbage across the wrap
    assert all(d >= 0.02 for d in dts[1:])       # ~frame time once running


def test_clock_uncapped_dt():
    _set(5000)
    clk = C.Clock(0)
    clk._last = 5000
    _set(5000)
    assert clk.tick() == 0.0                     # sub-ms frame -> 0 (documented)
    _set(5050)
    assert abs(clk.tick() - 0.05) < 1e-9


def test_overload_no_dt_inflation():
    # Sustained render slower than the cap must NOT run the game fast: sum(dt) == wall clock.
    C._sleep = lambda s: None
    _set(0)
    clk = C.Clock(30)
    clk._metro._next = 0
    clk._last = 0
    t, total = 0, 0.0
    for _ in range(50):
        t += 40                                  # 40 ms/frame render, > the 33 ms budget
        _set(t)
        total += clk.tick()
    assert abs(total - t / 1000.0) < 0.05, "sum_dt=%.3f wall=%.3f" % (total, t / 1000.0)


def test_hiccup_telescopes():
    C._sleep = lambda s: None
    _set(0)
    clk = C.Clock(30)
    clk._metro._next = 0
    clk._last = 0
    t, ds = 0, []
    for r in (33, 33, 50, 33, 33):
        t += r
        _set(t)
        ds.append(clk.tick())
    assert abs(sum(ds) - t / 1000.0) < 0.01      # one hiccup, no lasting speed-up


def test_float_rate_accepted():
    C.Clock(30.0).tick()                         # must not TypeError on the & mask
    C.FixedStep(60.0).step_count()


def test_first_capped_tick_primed():
    # A fresh capped Clock's first tick should sleep to a boundary and return ~1/fps, never 0
    # (so a game doing x/dt on frame 1 can't divide by zero).
    def adv_sleep(s):
        _clock["t"] = (_clock["t"] + int(round(s * 1000))) & _MASK
    C._sleep = adv_sleep
    _set(100_000)
    clk = C.Clock(30)
    d0 = clk.tick()
    C._sleep = lambda s: None                    # restore
    assert abs(d0 - 1.0 / 30) < 0.003, "d0=%r" % d0

"""picogame_rand — the seeded PRNG games rely on for reproducible spawns/shuffles.
Guards: determinism per seed, range bounds, and the Bag no-immediate-repeat contract.
(Usage survey: below/randint/choice/chance are the load-bearing calls.)"""
import _bootstrap  # noqa: F401

import picogame_rand as R


def test_determinism_same_seed():
    a = R.Rand(1234)
    b = R.Rand(1234)
    assert [a.below(1000) for _ in range(20)] == [b.below(1000) for _ in range(20)]
    a2 = R.Rand(1234)
    b2 = R.Rand(1234)
    assert [a2.randint(-5, 5) for _ in range(20)] == [b2.randint(-5, 5) for _ in range(20)]


def test_different_seed_differs():
    a = [R.Rand(1).below(1_000_000) for _ in range(5)]
    b = [R.Rand(2).below(1_000_000) for _ in range(5)]
    assert a != b  # astronomically unlikely to collide


def test_below_range():
    r = R.Rand(7)
    for _ in range(2000):
        v = r.below(10)
        assert 0 <= v < 10
    assert r.below(1) == 0          # degenerate n=1 always 0


def test_randint_inclusive():
    r = R.Rand(9)
    seen = set()
    for _ in range(4000):
        v = r.randint(3, 7)
        assert 3 <= v <= 7
        seen.add(v)
    assert seen == {3, 4, 5, 6, 7}  # both endpoints reachable


def test_random_unit_interval():
    r = R.Rand(3)
    for _ in range(2000):
        x = r.random()
        assert 0.0 <= x < 1.0


def test_chance_extremes():
    r = R.Rand(5)
    assert all(not r.chance(0.0) for _ in range(200))
    assert all(r.chance(1.0) for _ in range(200))


def test_choice_in_seq():
    r = R.Rand(11)
    seq = ["a", "b", "c", "d"]
    for _ in range(200):
        assert r.choice(seq) in seq


def test_shuffle_is_permutation():
    r = R.Rand(13)
    lst = list(range(20))
    r.shuffle(lst)
    assert sorted(lst) == list(range(20))    # same multiset, in place


def test_weighted_respects_zero():
    r = R.Rand(17)
    # weight 0 on indices 0 and 2 -> only index 1 ever chosen
    for _ in range(500):
        assert r.weighted([0, 1, 0]) == 1


def test_bag_no_immediate_exhaustion():
    # A Bag should deal every item once before repeating any (7-bag / shuffle-bag contract).
    bag = R.Bag(list(range(5)), R.Rand(42))
    first_cycle = [bag.next() for _ in range(5)]
    assert sorted(first_cycle) == list(range(5))   # all 5, no repeat within the cycle


def test_small_int_safe_core():
    # Every intermediate of _next() must stay below 2**30 so a MicroPython small int (31-bit
    # signed on 32-bit boards) never spills into a heap big int - the whole point of the
    # combined-Lehmer core. Guarded subclass re-derives the Schrage terms and asserts them.
    import picogame_rand as pr
    LIM = 1 << 30

    class Guard(pr.Rand):
        def _next(self):
            x, y = self._x, self._y
            assert 0 < x < LIM and 0 < y < LIM
            assert pr._A1 * (x % pr._Q1) < LIM and pr._R1 * (x // pr._Q1) < LIM
            assert pr._A2 * (y % pr._Q2) < LIM and pr._R2 * (y // pr._Q2) < LIM
            z = super()._next()
            assert 1 <= z < LIM
            return z

    for seed in (0, 1, 0x1234, 0x3FFFFFFF, 2**31 - 1):
        g = Guard(seed)
        for _ in range(5000):
            g.below(6)

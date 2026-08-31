"""picogame_pool.Pool - the fixed-size sprite pool. The point of these tests is the SEPARATION of
"this slot is in use" (the pool's own bit) from "draw this sprite" (`sprite.visible`): hiding a
pooled sprite - the house idiom for blinking, used on 12 non-pooled sprites across the games - must
not hand its slot to the next spawn(). The rest pins the contract every shipped game relies on:
`items` never reorders, `data` is never touched by the pool (games pre-allocate a dict per slot and
only mutate it), and a freed sprite is hidden so the classic `if not s.visible: continue` guard and
the inline `if b.visible and b.near(e, R)` collision reads keep giving the same answer."""
import _bootstrap  # noqa: F401

import picogame as pg
import picogame_pool


class FakeScene:
    """Records add() and nothing else - Pool only ever calls scene.add(sprite, fixed=...)."""

    def __init__(self):
        self.added = []

    def add(self, obj, fixed=False):
        self.added.append((obj, fixed))


def make(capacity=4, **kw):
    bm = pg.Bitmap(bytearray(2 * 2 * 2), 2, 2)
    return picogame_pool.Pool(FakeScene(), bm, capacity, **kw)


# --- the regression this design exists for ---------------------------------

def test_hiding_a_live_sprite_does_not_free_its_slot():
    p = make()
    e = p.spawn()
    e.visible = False                    # blink off - the house idiom
    other = p.spawn()
    assert other is not e                # slot must NOT have been handed out again
    assert p.count() == 2                # both are alive; one just isn't drawn


def test_a_blinked_sprite_survives_a_full_spawn_sweep():
    p = make(capacity=3)
    e = p.spawn()
    e.visible = False
    rest = [p.spawn(), p.spawn()]
    assert p.spawn() is None             # pool is full: the hidden one still holds its slot
    assert e not in rest


def test_blink_back_on_changes_nothing_about_aliveness():
    p = make()
    e = p.spawn()
    for _ in range(4):                   # two full blink cycles
        e.visible = False
        e.visible = True
    assert p.count() == 1
    assert p.spawn() is not e


# --- the contract the shipped games read -----------------------------------

def test_free_hides_so_the_visible_guard_still_works():
    p = make()
    s = p.spawn()
    assert s.visible is True             # spawn() shows it
    p.free(s)
    assert s.visible is False            # ... and free() hides it again


def test_spawn_shows_a_slot_its_previous_user_left_hidden():
    p = make()
    s = p.spawn()
    s.visible = False                    # game hid it, then dropped it
    p.free(s)
    again = p.spawn()
    assert again is s and again.visible is True


def test_items_never_reorders():
    p = make(capacity=4)
    before = list(p.items)
    a, b, c = p.spawn(), p.spawn(), p.spawn()
    p.free(b)                            # freeing the middle one must not swap anything
    p.spawn()
    assert p.items == before             # 159 loops in the games free while iterating items


def test_pool_never_touches_data():
    """asteroids/cavern/starfall pre-allocate one dict per slot and only mutate it - a pool that
    cleared or replaced `data` would turn a zero-alloc pool into one that allocates per spawn."""
    p = make()
    for s in p.items:
        s.data = {"vx": 0}
    d = p.items[0].data
    s = p.spawn()
    assert s.data is d                   # spawn() did not replace it
    s.data["vx"] = 7
    p.free(s)
    assert s.data is d and s.data["vx"] == 7   # free() did not clear it
    assert p.spawn().data is d


# --- capacity, counting, bulk reset ----------------------------------------

def test_spawn_returns_none_when_full():
    p = make(capacity=2)
    assert p.spawn() is not None and p.spawn() is not None
    assert p.spawn() is None


def test_free_returns_the_slot_to_the_pool():
    p = make(capacity=1)
    s = p.spawn()
    assert p.spawn() is None
    p.free(s)
    assert p.spawn() is s


def test_count_tracks_live_slots():
    p = make(capacity=3)
    assert p.count() == 0
    a, b = p.spawn(), p.spawn()
    assert p.count() == 2
    p.free(a)
    assert p.count() == 1


def test_free_all_clears_and_hides_everything():
    p = make(capacity=3)
    p.spawn(), p.spawn()
    p.free_all()
    assert p.count() == 0
    assert all(not s.visible for s in p.items)
    assert p.spawn() is p.items[0]


def test_freeing_twice_is_harmless():
    p = make()
    s = p.spawn()
    p.free(s)
    p.free(s)
    assert p.count() == 0


def test_free_of_a_foreign_sprite_raises():
    p = make()
    outsider = pg.Sprite(pg.Bitmap(bytearray(8), 2, 2), 0, 0)
    try:
        p.free(outsider)
    except ValueError:
        return
    raise AssertionError("free() of a sprite outside the pool must raise, not silently hide it")


# --- construction -----------------------------------------------------------

def test_every_slot_is_added_to_the_scene_hidden():
    scene = FakeScene()
    bm = pg.Bitmap(bytearray(2 * 2 * 2), 2, 2)
    p = picogame_pool.Pool(scene, bm, 3, anchor=(0.5, 0.5), fixed=True)
    assert len(scene.added) == 3
    assert all(fixed for _, fixed in scene.added)
    assert all(not s.visible for s in p.items)
    assert all(s.anchor == (0.5, 0.5) for s in p.items)

"""picogame_anim.AnimatedSprite - the fluent play() contract (audit B2): play() returns
self on BOTH paths (switch and already-playing no-op), so the documented chains
`AnimatedSprite(...).play("idle")` and `hero.play(state).tick(dt)` work."""
import _bootstrap  # noqa: F401

import picogame as pg
import picogame_anim


def _sprite():
    bm = pg.Bitmap(b"\x01" * 16 * 3, 4, 4, format=pg.PAL8, palette=(0, 0xFFFF), frames=3)
    return pg.Sprite(bm, 0, 0)


def _anims():
    return {"idle": ([0], 1, True), "walk": ([1, 2], 8, True)}


def test_play_returns_self_on_switch_and_noop():
    hero = picogame_anim.AnimatedSprite(_sprite(), _anims())
    assert hero.play("walk") is hero          # switch path
    assert hero.play("walk") is hero          # already-playing no-op path
    assert hero.current == "walk"


def test_documented_chains_work():
    hero = picogame_anim.AnimatedSprite(_sprite(), _anims()).play("idle")
    assert isinstance(hero, picogame_anim.AnimatedSprite) and hero.current == "idle"
    hero.play("walk").tick(0.5)               # play().tick() in one statement
    assert hero.sprite.frame in (1, 2)


def test_noop_play_does_not_restart():
    hero = picogame_anim.AnimatedSprite(_sprite(), _anims()).play("walk")
    hero.tick(0.2)                            # advance a bit
    pos = hero.anim.t
    hero.play("walk")                         # same name: must NOT reset the phase
    assert hero.anim.t == pos

"""picogame_game.setup(rgb444=...): the settings.toml default and what an explicit argument does
to it. The sim's Display records the flag it was built with."""
import _bootstrap  # noqa: F401

import os

import picogame as pg
import picogame_game as G


def _setup_with(env, **kw):
    """Run setup() with os.getenv answering from `env`; return the rgb444 the Display got."""
    real_getenv, real_supported = os.getenv, getattr(pg, "RGB444_SUPPORTED", None)
    os.getenv = lambda k, default=None: env.get(k, default)
    pg.RGB444_SUPPORTED = env.pop("_supported", True)
    G._RESOLVED.clear()
    G._TARGET.clear()
    try:
        scene, _, _ = G.setup(**kw)
        return scene.display.rgb444
    finally:
        os.getenv = real_getenv
        pg.RGB444_SUPPORTED = real_supported


def test_default_reads_settings_toml():
    assert _setup_with({}) is False                          # unset = RGB565
    assert _setup_with({"PICOGAME_RGB444": 0}) is False
    assert _setup_with({"PICOGAME_RGB444": 1}) is True
    assert _setup_with({"PICOGAME_RGB444": "1"}) is True
    assert _setup_with({"PICOGAME_RGB444": 1, "_supported": False}) is False   # = "auto": capability-gated


def test_explicit_argument_wins():
    assert _setup_with({"PICOGAME_RGB444": 1}, rgb444=False) is False
    assert _setup_with({}, rgb444=True) is True
    assert _setup_with({}, rgb444="auto") is True
    assert _setup_with({"_supported": False}, rgb444="auto") is False

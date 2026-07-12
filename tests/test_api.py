"""API-surface guard: the whole point is to fail loudly if a refactor removes/renames something
games depend on. Two layers:
  1. every picogame_*.py must still IMPORT (under the sim shims) — catches syntax / broken deps;
  2. the load-bearing public classes + methods (from the games/demos/examples usage survey) must
     still exist. Add to API_SPEC when a new public method becomes something games call."""
import _bootstrap  # noqa: F401

import glob
import importlib
import os

_LIBS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Class -> methods that games actually call (survey: btn.is_pressed/just_pressed 340+, clock.tick 68,
# rng.below/randint/choice/chance 36, shake.add/tick 14, pool.spawn/free 15, ...).
API_SPEC = {
    "picogame_input": {"Buttons": ["poll", "is_pressed", "just_pressed", "just_released",
                                    "has", "repeat", "clear"],
                       "Timer": ["feed", "consume", "charge"]},
    "picogame_clock": {"Clock": ["tick", "tick_async", "set_fps"],
                       "FixedStep": ["step_count", "steps"]},
    "picogame_rand": {"Rand": ["below", "randint", "random", "chance", "choice",
                               "shuffle", "weighted", "seed"],
                      "Bag": ["next"]},
    "picogame_pool": {"Pool": ["spawn", "free", "free_all", "count"]},
    "picogame_fx": {"Shake": ["add", "tick"]},
    "picogame_save": {"Save": ["load", "save", "defaults", "reset"]},
}

# Module-level functions games call as `mod.fn(...)`.
MODULE_FUNCS = {
    "picogame_game": ["setup"],
}

# Button name constants (btn.UP etc.) that games reference directly.
BUTTON_CONSTS = ["UP", "DOWN", "LEFT", "RIGHT", "A", "B", "X", "Y", "ALL"]


def test_all_libs_import():
    """Every shipped picogame_*.py imports cleanly under the sim shims."""
    failures = []
    for f in sorted(glob.glob(os.path.join(_LIBS, "picogame_*.py"))):
        name = os.path.basename(f)[:-3]
        try:
            importlib.import_module(name)
        except Exception as e:  # noqa: BLE001
            failures.append("%s: %r" % (name, e))
    assert not failures, "libs failed to import:\n  " + "\n  ".join(failures)


def test_class_methods_present():
    missing = []
    for mod_name, classes in API_SPEC.items():
        mod = importlib.import_module(mod_name)
        for cls_name, methods in classes.items():
            cls = getattr(mod, cls_name, None)
            if cls is None:
                missing.append("%s.%s (class)" % (mod_name, cls_name))
                continue
            for m in methods:
                if not hasattr(cls, m):
                    missing.append("%s.%s.%s" % (mod_name, cls_name, m))
    assert not missing, "removed/renamed API:\n  " + "\n  ".join(missing)


def test_module_funcs_present():
    missing = []
    for mod_name, funcs in MODULE_FUNCS.items():
        mod = importlib.import_module(mod_name)
        for fn in funcs:
            if not callable(getattr(mod, fn, None)):
                missing.append("%s.%s" % (mod_name, fn))
    assert not missing, "removed module funcs:\n  " + "\n  ".join(missing)


def test_button_constants_present():
    b = importlib.import_module("picogame_input").Buttons
    missing = [c for c in BUTTON_CONSTS if not hasattr(b, c)]
    assert not missing, "missing Buttons constants: %s" % missing
    # constants must be distinct single bits (except ALL) so masks don't collide
    bits = [getattr(b, c) for c in BUTTON_CONSTS if c != "ALL"]
    assert len(set(bits)) == len(bits), "Buttons bit constants collide"

# picogame_debug is a DIAGNOSTIC helper and must never be a hard dependency: a user who deploys
# picogame_audioout/picogame_synth without it must still get sound (2026-08 field report: audio
# silently failed because the debug module was missing - and without it nothing could say so).
import sys


def _without_debug():
    """Import picogame_audioout with picogame_debug made unimportable; return the module."""
    # Save AND restore the audio modules too: other tests hold references bound at their
    # import (picogame_music._ps), so leaving a fresh picogame_synth in sys.modules would
    # make identity checks against the "current" module fail later in the run.
    saved = {k: sys.modules.pop(k) for k in list(sys.modules)
             if k.startswith(("picogame_debug", "picogame_audioout", "picogame_synth"))}
    sys.modules["picogame_debug"] = None            # None entry -> ImportError on import
    try:
        import picogame_audioout
        return picogame_audioout
    finally:
        for k in ("picogame_debug", "picogame_audioout", "picogame_synth"):
            sys.modules.pop(k, None)
        sys.modules.update(saved)


def test_audioout_imports_without_debug():
    mod = _without_debug()
    assert hasattr(mod, "make_output")
    mod._debug("must be a silent no-op")            # fallback must exist and not raise


def test_debug_present_is_still_used():
    saved = sys.modules.pop("picogame_audioout", None)
    try:
        import picogame_debug
        import picogame_audioout
        assert picogame_audioout._debug is picogame_debug.note
    finally:
        if saved is not None:
            sys.modules["picogame_audioout"] = saved

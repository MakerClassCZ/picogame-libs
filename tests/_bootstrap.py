"""Test bootstrap: put the picogame-libs SOURCE and the simulator's CPython shims on sys.path,
so the libs import and run under plain CPython (against sim/picogame.py, board.py, digitalio.py,
micropython.py, ...). Import this first in every test module and in the runner.

The sim shims live in a sibling repo; we probe a few known layouts so the suite works whether the
checkout is the dev tree (repos/picogame-final/sim) or the public distro (repos/picogame/sim)."""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_LIBS = os.path.dirname(_HERE)                       # repos/picogame-libs
_REPOS = os.path.dirname(_LIBS)                      # repos/

_SIM_CANDIDATES = [
    os.path.join(_REPOS, "picogame-final", "sim"),
    os.path.join(_REPOS, "picogame", "sim"),
    os.path.join(_REPOS, "picogame-dev", "sim"),
]


def _find_sim():
    for c in _SIM_CANDIDATES:
        if os.path.exists(os.path.join(c, "picogame.py")):
            return c
    raise RuntimeError("sim shims not found; tried:\n  " + "\n  ".join(_SIM_CANDIDATES))


SIM = _find_sim()
# libs FIRST so the source under test wins over any copy inside sim/
for p in (_LIBS, SIM):
    if p not in sys.path:
        sys.path.insert(0, p)

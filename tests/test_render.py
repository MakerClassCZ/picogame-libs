"""Golden render tests: render a deterministic fixture scene headless through the simulator and
compare the frame pixel-for-pixel against a committed reference PNG. Catches RENDER regressions
(sprite blit / flips / transforms / blit-effects, Canvas + fill565, ...) that the logic tests miss.

Note: this validates the SIMULATOR engine (sim/picogame.py) - the Python reference implementation of
the C engine - so it guards the reference behaviour, not the on-device C directly (they could drift).

Regenerate goldens after an INTENTIONAL render change:  PICOGAME_REGEN_GOLDEN=1 python3 tests/run_tests.py render
"""
import _bootstrap

import os
import subprocess
import sys

try:
    from PIL import Image, ImageChops
    _HAVE_PIL = True
except ImportError:
    _HAVE_PIL = False

_HERE = os.path.dirname(os.path.abspath(__file__))
_SCENES = os.path.join(_HERE, "render", "scenes")
_GOLDEN = os.path.join(_HERE, "render", "golden")
_RUN_PY = os.path.join(_bootstrap.SIM, "run.py")
_TMP = os.environ.get("TMPDIR", "/tmp")
_FRAMES = 2                                  # static scenes -> any frame is identical; keep it small
_REGEN = os.environ.get("PICOGAME_REGEN_GOLDEN") == "1"

SCENES = ["sprites", "transforms", "canvas", "layers", "invert"]


def _render(scene, out_png):
    scene_path = os.path.join(_SCENES, scene + ".py")
    r = subprocess.run([sys.executable, _RUN_PY, scene_path, "--frames", str(_FRAMES),
                        "--shot", out_png],
                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    assert r.returncode == 0, "sim run failed for %s:\n%s" % (scene, r.stdout.decode("utf-8", "replace"))
    assert os.path.exists(out_png), "no screenshot produced for %s:\n%s" % (scene, r.stdout.decode())


def _one(scene):
    if not _HAVE_PIL:
        raise AssertionError("PIL/Pillow not installed - render tests need it")
    out = os.path.join(_TMP, "picogame_render_%s.png" % scene)
    if os.path.exists(out):
        os.remove(out)
    _render(scene, out)
    golden = os.path.join(_GOLDEN, scene + ".png")

    if _REGEN or not os.path.exists(golden):
        os.makedirs(_GOLDEN, exist_ok=True)
        Image.open(out).convert("RGB").save(golden)
        if not _REGEN:
            raise AssertionError("golden missing; generated %s - rerun to verify (or set "
                                 "PICOGAME_REGEN_GOLDEN=1 deliberately)" % golden)
        return  # regen mode: accept

    cur = Image.open(out).convert("RGB")
    ref = Image.open(golden).convert("RGB")
    assert cur.size == ref.size, "%s: size %s != golden %s" % (scene, cur.size, ref.size)
    diff = ImageChops.difference(cur, ref)
    box = diff.getbbox()
    if box is not None:
        n = sum(1 for p in diff.getdata() if p != (0, 0, 0))
        raise AssertionError("%s: %d pixels differ from golden (bbox %s). If intended, regen with "
                             "PICOGAME_REGEN_GOLDEN=1." % (scene, n, box))


def test_render_sprites():
    _one("sprites")


def test_render_transforms():
    _one("transforms")


def test_render_canvas():
    _one("canvas")


def test_render_layers():
    _one("layers")


def test_render_invert():
    _one("invert")

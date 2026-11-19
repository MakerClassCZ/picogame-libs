"""frozen/core is the set boards freeze into firmware; it must stay a working subset of the library.

It holds symlinks, not copies, so it cannot drift from the modules in the root. These tests catch
the ways it can still break: a symlink left behind when a module is renamed or removed, a copy
committed in place of a link, and a frozen module whose required import is not frozen with it
(an ImportError on a board where that module cannot be copied to /lib).
"""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import glob
import os
import re

LIBS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORE = os.path.join(LIBS, "frozen", "core")


def _frozen():
    return sorted(glob.glob(os.path.join(CORE, "*.py")))


def test_every_frozen_module_links_to_a_root_module():
    assert _frozen(), "frozen/core has no modules"
    for path in _frozen():
        name = os.path.basename(path)
        assert os.path.islink(path), "%s is a copy; make it a symlink to ../../%s" % (name, name)
        assert os.readlink(path) == "../../" + name, "%s links to %s" % (name, os.readlink(path))
        assert os.path.isfile(path), "%s links to a module that no longer exists" % name


def test_required_imports_are_frozen_too():
    # Only unindented imports are required: the optional ones sit in try: blocks or in functions.
    frozen = {os.path.basename(p)[:-3] for p in _frozen()}
    missing = []
    for path in _frozen():
        with open(path, encoding="utf-8") as f:
            for dep in re.findall(r"^(?:from|import) (picogame_\w+)", f.read(), re.M):
                if dep not in frozen:
                    missing.append("%s needs %s" % (os.path.basename(path), dep))
    assert not missing, "not in frozen/core: " + ", ".join(missing)

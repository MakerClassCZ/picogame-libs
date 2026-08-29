"""Every module must appear in the README's index.

A helper nobody can find does not exist. Seven modules had drifted out of that index by 0.2.0 -
including the whole pseudo-3D set (mode7 / ray / iso) and the PICO-8 music importer - so someone
looking for "3D" or "music" found nothing, in either repo. Nothing failed; the modules simply were
not listed, and adding a module is exactly the moment nobody thinks about the README.

So the index is a build artefact with a test, not a document kept up by good intentions.
"""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import glob
import os
import re

LIBS = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
README = os.path.join(LIBS, "README.md")


def _listed():
    with open(README, encoding="utf-8") as f:
        return set(re.findall(r"^\| `(picogame_\w+)`", f.read(), re.M))


def _shipped():
    return {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(LIBS, "picogame_*.py"))}


def test_every_module_is_in_the_readme_index():
    missing = sorted(_shipped() - _listed())
    assert not missing, (
        "not in the README index, so nobody browsing the repo will find them: %s\n"
        "Add a row under the group it belongs to (one sentence: what it gives you, not how)."
        % ", ".join(missing))


def test_the_index_lists_no_module_that_was_removed():
    stale = sorted(_listed() - _shipped())
    assert not stale, (
        "the README index still advertises modules that no longer ship: %s" % ", ".join(stale))

#!/usr/bin/env python3
"""Dependency-free test runner for picogame-libs (no pytest needed).

Discovers every `tests/test_*.py`, runs each top-level `test_*` function, and reports pass/fail.
A test fails by raising (assert or any exception). Exit code is nonzero if anything failed.

    python3 tests/run_tests.py            # run all
    python3 tests/run_tests.py rand fx    # run only test_rand.py and test_fx.py
"""
import _bootstrap  # noqa: F401  (must be first: sets sys.path)

import glob
import importlib
import os
import sys
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))


def main(argv):
    only = set(argv)
    files = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    passed = failed = 0
    failures = []
    for f in files:
        modname = os.path.basename(f)[:-3]
        short = modname[len("test_"):]
        if only and short not in only and modname not in only:
            continue
        mod = importlib.import_module(modname)
        tests = [n for n in dir(mod) if n.startswith("test_") and callable(getattr(mod, n))]
        for name in sorted(tests):
            try:
                getattr(mod, name)()
                passed += 1
                print("  PASS  %s::%s" % (short, name))
            except Exception as e:  # noqa: BLE001
                failed += 1
                failures.append((short, name, e, traceback.format_exc()))
                print("  FAIL  %s::%s  -- %r" % (short, name, e))
    print("\n%d passed, %d failed" % (passed, failed))
    for short, name, e, tb in failures:
        print("\n=== FAIL %s::%s ===\n%s" % (short, name, tb))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

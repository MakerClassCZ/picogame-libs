# picogame-stubs

Type stubs (`.pyi`) for the **native `picogame` module** - the C game engine that ships in
picogame CircuitPython firmware. They give VS Code (Pylance), Pyright and mypy autocomplete and
type checking for `import picogame as pg` while you edit a game on your PC.

    pip install "git+https://github.com/MakerClassCZ/picogame-libs#subdirectory=stubs"
    # (or the picogame_stubs-*.whl attached to each release)

The `picogame_*` helper libraries are plain Python: point Pylance at a checkout of this repo
(`python.analysis.extraPaths`), not at the board's `/lib` (`.mpy` bytecode can't be analysed).
For `board`, `displayio`, `synthio`... use `pip install circuitpython-stubs`.

The stub is generated from the engine's `//|` docstrings in
`shared-bindings/picogame` (`tools/extract_pyi.py` from CircuitPython) - the same source that
builds the docs at https://picogame.makerclass.cz/reference/.

Regenerate it from the INTEGRATION branch (never a feature branch - what has not shipped must not
appear here), because "generated" only stays true if someone regenerates:

    git -C <circuitpython-fork> archive picogame shared-bindings/picogame | tar -x -C /tmp/b
    python3 <circuitpython-fork>/tools/extract_pyi.py /tmp/b/shared-bindings/picogame /tmp/out
    cp /tmp/out/__init__.pyi stubs/picogame-stubs/__init__.pyi

The extractor needs `isort`, `black` and `circuitpython_typing` (only its `__all__` is read).
`sim/selftest_api.py` checks the same signatures from the other side, so the two agree by
construction - if they ever disagree, one of them was hand-edited.

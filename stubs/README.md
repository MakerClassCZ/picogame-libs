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
builds the docs at https://picogame.makerclass.cz/reference/, so it can't drift from the firmware.

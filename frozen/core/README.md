# frozen/core - the helpers to freeze into a firmware

A core set of picogame-libs modules for boards that freeze them into CircuitPython instead of
copying them to `CIRCUITPY/lib` (for example a board with a small CIRCUITPY drive). Frozen
modules take no space on the drive and run from flash.

The files here are symlinks to the modules in the repo root, so this folder always matches the
library at the same commit. In a CircuitPython board's `mpconfigboard.mk`:

```make
FROZEN_MPY_DIRS += $(TOP)/frozen/picogame-libs/frozen/core
```

| Group | Modules |
|---|---|
| Base | `picogame_game`, `picogame_input`, `picogame_clock`, `picogame_rand`, `picogame_math` |
| Text and UI | `picogame_font`, `picogame_ui`, `picogame_bitfont` |
| Sound | `picogame_audioout`, `picogame_synth`, `picogame_sfx` |
| Gameplay | `picogame_pool`, `picogame_anim`, `picogame_tiles`, `picogame_seq` |
| Art in code | `picogame_shapes`, `picogame_palette` |
| Accelerometer as a D-pad | `picogame_tiltpad` |

Every module a frozen one needs is frozen too; the modules they import only when present
(`picogame_debug`, the USB, I2C and shift-register pads) can be copied to `CIRCUITPY/lib` when a
board has that hardware. Any other module a game needs goes to `CIRCUITPY/lib` as usual.

**Frozen modules come before `/lib`** on `sys.path` (`['', '/', '.frozen', '/lib']`). To try a
newer version of a frozen module, put it in the CIRCUITPY root, not in `/lib`.

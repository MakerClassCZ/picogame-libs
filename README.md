# picogame helper library

Python helpers for [**picogame**](https://github.com/MakerClassCZ/circuitpython/tree/picogame) -
a 2D game engine built into CircuitPython for the PicoPad and similar MCU consoles. The C engine
provides the fast primitives (`Scene`, `Sprite`, `Tilemap`, `Canvas`, `Particles`, `Display`); these
modules are the everyday Python layer on top: input, a frame clock, text and HUD, collision, sprite
pools, animation, audio, save files, and the game-feel bits you'd otherwise rewrite for every game.

Pick what you need - every module stands alone, so a game copies only the ones it imports. They need a
CircuitPython firmware with the `picogame` C module built in.

## Deploy
Copy the modules a game needs into **`CIRCUITPY/lib/`**. The game's own
`code.py` and its assets go in the CIRCUITPY root.

> The `stage`/`ugame` compatibility shim (run unmodified python-ugame games on picogame) lives in its
> own repo, [**picogame-stage**](https://github.com/MakerClassCZ/picogame-stage).

---

## Scaffolding - stand a game up fast
| Module | Provides |
|---|---|
| `picogame_game` | `setup(...)` - one call: take over the display, build a retained `Scene` + its double strip buffers. `fast=` toggles the DMA vs portable renderer. Returns `(scene, bufA, bufB)`. |
| `picogame_input` | `Buttons` - masks UP/DOWN/LEFT/RIGHT/A/B/X/Y (+L1/L2/R1/R2/START/SELECT); `poll() / is_pressed / just_pressed / just_released / repeat`. Auto keypad-or-digitalio backend, per-board profiles + `settings.toml` override. `Timer` - small frame countdown (coyote-time / jump-buffer). |
| `picogame_clock` | `Clock(fps)` - frame-rate cap + `dt`. `FixedStep` - fixed-timestep accumulator for deterministic physics. |
| `picogame_scene` | Declarative scene loader: `load()` / `load_bank()` build a ready `Scene` from a baked SCENE dict. `View`. |

## Text & UI
| Module | Provides |
|---|---|
| `picogame_font` | `render_text()` / `render_text_pal()` - rasterise a string (any `fontio` font, e.g. bundled `terminalio.FONT`) into a `picogame.Bitmap`. `Label` - single-line text sprite. |
| `picogame_bitfont` | `render_text(pg, text, fg=...)` - a tiny 8x8, 4-shade **outlined** bitmap font baked to a PAL8 Bitmap; the dark outline keeps text readable over gameplay with no HUD box. |
| `picogame_ui` | Scene-layer widgets (`SceneLabel`, `SceneBox`, `SceneMenu`, `HudBar`, `GridCursor`) + immediate-mode (`Menu`, `TextBox`). Camera-independent HUD. |
| `picogame_options` | `OptionsMenu` - settings/value rows (choice / stepper / toggle / action) built on `ui.SceneBox`. (Provisional, outside the frozen `ui` core.) |

## Art in code
| Module | Provides |
|---|---|
| `picogame_shapes` | Generators that bake single-colour PAL8 Bitmaps: `rect / circle / ring / from_mask / atlas / color_frames / tileset_colors / poly_frames`. Placeholder sprite/tile art straight from code. |
| `picogame_palette` | Cheap colour effects by mutating the PALETTE, not the pixels (the Game Boy trick): `cycle` (animated water/lava), `swap` (recolour a shared bitmap), `fade`, `snapshot` / `restore`. |

## Juice & effects
| Module | Provides |
|---|---|
| `picogame_fx` | Built on the engine, compose with your camera: `Shake` (trauma-model screen shake), `Fade`, `Tween`, `Camera`, `Sky`, `Scanlines`, `InvertFlash`. |

## Gameplay helpers
| Module | Provides |
|---|---|
| `picogame_collide` | Zero-allocation collision read straight off sprites: `hit` (box/box), `hit_point`, `is_within`. |
| `picogame_pool` | `Pool` - reusable fixed-size sprite pool (`spawn / free / free_all`, `.items`, `count`) for bullets/enemies/pipes. |
| `picogame_anim` | `FrameAnim` / `AnimatedSprite` - drive a Sprite's frame from a time-based sequence (no more `(frame//4)%n`). |
| `picogame_tiles` | `TileFlags` - per-tile metadata bitfield keyed by tile index (solid / hazard / ladder ...); turns tilemap collision into a flag lookup. |
| `picogame_seq` | `Seq` - write timed/sequenced logic as generators (cutscenes, "do X over N frames", staged AI). `wait`, `over`, `move_over`. |

## Numbers
| Module | Provides |
|---|---|
| `picogame_math` | Scalars (`clamp / mid / lerp / inv_lerp / remap / sgn / approach / wrap`), turn-based trig (angles as 0..1 turns: `sin_t / cos_t / atan2_t`), 2D vectors (`length / distance / normalize / angle_rad`). |
| `picogame_rand` | `Rand` - tiny **seedable** deterministic RNG (reproducible replays). `Bag` - shuffle-bag (Tetris-style even draws). |

## Audio
| Module | Provides |
|---|---|
| `picogame_audio` | `Audio` - convenience layer over `audiopwmio` + `audiocore` + `audiomixer` (PWM audio): load/play WAVs, overlapping sfx + music. `tone()` test beep. |
| `picogame_synth` | `Synth` - on-device sound via `synthio`, no WAV files / sample RAM: `sine / saw / triangle / square / noise / note / pitch_bend`, `load_midi`. |

## Persistence & streaming
| Module | Provides |
|---|---|
| `picogame_save` | `Save(key, schema)` - structured store backed by `microcontroller.nvm` (reserved flash; highscores / settings). |
| `picogame_stream` | `StreamSheet` - play a big sprite sheet straight from a flash file, holding only ONE frame in RAM. |
| `picogame_cutscene` | `show()` / `play()` - display a fullscreen image strip-streamed from a flash file (~0 RAM). |

## Memory
| Module | Provides |
|---|---|
| `picogame_arena` | `Arena` - pre-allocated buffer arena to dodge heap fragmentation on long-running games. |

---

## License
MIT - see [`LICENSE`](LICENSE).

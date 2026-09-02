"""Rendering core for games

The `picogame` module composites sprites, tilemaps, drawing canvases,
particle layers, 3D triangle batches and immediate-mode callbacks into a
small reusable strip buffer and sends each strip to the display, so a full-screen game does not
need a full-screen buffer. A :py:class:`Scene` tracks what changed and
repaints only those regions when :py:meth:`Scene.refresh` is called.

A scene targets a :py:class:`~busdisplay.BusDisplay`, an accelerated
:py:class:`Display` or a RAM :py:class:`Framebuffer`. picogame drives the
display itself, so it requires ``display.auto_refresh = False`` and cannot
show displayio groups on the same display at the same time.

Most programs start with :py:class:`Scene`, :py:class:`Sprite` and
:py:class:`Bitmap`.

.. note::
   This module is the engine's rendering and compute core and is fully
   usable on its own. The pure-Python `picogame helper libraries
   <https://github.com/MakerClassCZ/picogame-libs>`_
   (``picogame_game``, ``picogame_ray`` and others) build a complete game
   framework on top of it: display, input and audio setup that adapts to
   the board, game-loop timing, sprite pools and collision helpers,
   animation, text, HUD and menus, sound effects and music, visual
   effects, saved games, scene loading and pseudo-3D cameras. A desktop
   simulator, asset-conversion tools, examples and tutorials live in the
   `picogame repository <https://github.com/MakerClassCZ/picogame>`_, with
   documentation at `picogame.makerclass.cz
   <https://picogame.makerclass.cz/>`_.

Example::

  import array
  import board
  import time

  import picogame

  display = board.DISPLAY
  display.auto_refresh = False

  size = display.width * picogame.STRIP_H * 2
  scene = picogame.Scene(display, bytearray(size), bytearray(size))

  # One solid white 8x8 frame.
  white = picogame.rgb565(255, 255, 255)
  bitmap = picogame.Bitmap(array.array("H", [white] * 64), 8, 8)
  player = scene.add(picogame.Sprite(bitmap, x=0, y=display.height // 2))

  while True:
      player.x = (player.x + 1) % display.width
      scene.refresh()
      time.sleep(0.02)

This moves a white square across the screen, repainting only the pixels
that changed each frame."""

from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import busdisplay
import fontio
import picodvi
from circuitpython_typing import ReadableBuffer, WriteableBuffer

RGB565: int
"""16-bit color bitmap format (transfer byte order)."""
PAL8: int
"""8-bit paletted bitmap format."""

STRIP_H: int
"""Recommended render-strip height in rows for this build. Sizing a `Scene`
strip buffer as ``display.width * STRIP_H * 2`` bytes yields strips this
tall."""

FPU: int
"""``1`` when `project` uses hardware floating point (its buffers are
``float32``), ``0`` when it uses signed 16.16 fixed-point ``int32``."""

API_LEVEL: int
"""Version of the picogame API. Helper libraries compare this value against
the API level they target."""

RGB444_SUPPORTED: bool
"""Whether `Display` supports ``rgb444=True`` on this board."""

FAST_DISPLAY_SUPPORTED: bool
"""Whether the accelerated `Display` backend is available on this board."""

FRAMEBUFFER_SUPPORTED: bool
"""Whether `Framebuffer` is available on this board."""

def rgb565(r: int, g: int, b: int) -> int:
    """Build an RGB565 color in the display's transfer byte order from 8-bit
    components. Every color integer in this module is such a value."""
    ...

def invert(
    display: Union[Display, busdisplay.BusDisplay, Framebuffer], on: bool
) -> None:
    """Enable or disable color inversion.

    Bus displays receive the controller's inversion command (INVON/INVOFF), which
    takes effect immediately and sends no pixel data; the controller must support
    it (ST7789 and ST7735 do). A `Framebuffer` target is instead inverted during
    composition, starting with the next refresh."""
    ...

def render(
    display: Union[Display, busdisplay.BusDisplay, Framebuffer],
    layers: List[Union[Sprite, Tilemap, Canvas, Particles, StripDraw, Triangles]],
    buffer: Optional[WriteableBuffer],
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    background: int = 0,
) -> None:
    """Render ``layers`` into the screen region from ``(x0, y0)`` up to, but not
    including, ``(x1, y1)``, and push it to ``display``, without a `Scene`.

    :param display: the render target
    :param layers: layers of any kind, drawn bottom to top
    :param ~circuitpython_typing.WriteableBuffer buffer: a reusable strip buffer of
        at least ``(x1 - x0) * 2`` bytes; ignored (may be `None`) on a
        `Framebuffer` target
    :param int x0: left edge of the region
    :param int y0: top edge of the region
    :param int x1: right edge of the region (exclusive)
    :param int y1: bottom edge of the region (exclusive)
    :param int background: color the region is cleared to first"""
    ...

def collide(
    x1: int,
    y1: int,
    x2: int,
    y2: int,
    ax1: int,
    ay1: int,
    ax2: int = ...,
    ay2: int = ...,
) -> bool:
    """Return whether an inclusive rectangle overlaps another rectangle or contains
    a point. Both corners are part of the rectangle, so touching edges count as an
    overlap.

    With six arguments, test rectangle ``(x1, y1, x2, y2)`` against the point
    ``(ax1, ay1)``; with eight, test it against the rectangle
    ``(ax1, ay1, ax2, ay2)``.

    Unlike the pixel regions used by `render`, whose upper bounds are excluded,
    collision bounds are inclusive."""
    ...

def value2d(x: float, y: float, *, seed: int = 0) -> float:
    """Smooth 2-D value noise in ``0..1``."""
    ...

def value1d(x: float, *, seed: int = 0) -> float:
    """Smooth 1-D value noise in ``0..1``."""
    ...

def fbm2d(
    x: float,
    y: float,
    *,
    octaves: int = 4,
    seed: int = 0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float:
    """Fractal (fBm) 2-D noise in ``0..1``: ``octaves`` layers of :py:func:`value2d`, each
    ``lacunarity`` times finer and ``gain`` times weaker than the last."""
    ...

def fbm1d(
    x: float,
    *,
    octaves: int = 4,
    seed: int = 0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float:
    """Fractal (fBm) 1-D noise in ``0..1``: ``octaves`` layers of
    :py:func:`value1d`, each ``lacunarity`` times finer and ``gain`` times
    weaker than the last."""
    ...

def project(
    cam: ReadableBuffer,
    pts: ReadableBuffer,
    n: int,
    out_sx: WriteableBuffer,
    out_sy: WriteableBuffer,
) -> None:
    """Batch-project ``n`` 3D world points to screen coordinates.

    When :py:data:`FPU` is ``1``, ``cam`` and ``pts`` hold ``float32`` elements;
    otherwise they hold signed 16.16 fixed-point ``int32`` elements.

    :param ~circuitpython_typing.ReadableBuffer cam: 15 camera parameters, in order:
        eye x/y/z, right x/z (the camera cannot roll, so right has no y
        component), up x/y/z, forward x/y/z, focal length, screen center x/y,
        near-plane distance
    :param ~circuitpython_typing.ReadableBuffer pts: ``3 * n`` world coordinates
        (x, y, z per point)
    :param int n: number of points
    :param ~circuitpython_typing.WriteableBuffer out_sx: at least ``n`` ``int16``
        values; receives screen x, or the sentinel ``-32768`` for a point behind
        the near plane
    :param ~circuitpython_typing.WriteableBuffer out_sy: at least ``n`` ``int16``
        values; receives screen y, or ``-32768`` for a point behind the near plane"""
    ...

def raycast(
    map: ReadableBuffer,
    mw: int,
    mh: int,
    posx: int,
    posy: int,
    lrx: int,
    lry: int,
    srx: int,
    sry: int,
    sh: int,
    stride: int,
    ncols: int,
    wcolors: ReadableBuffer,
    top: WriteableBuffer,
    bot: WriteableBuffer,
    col: WriteableBuffer,
    dist: WriteableBuffer,
    runs: Optional[WriteableBuffer] = None,
) -> Optional[int]:
    """Cast one frame of wall-finding rays across the screen columns of a
    grid-map view. A low-level interface used by the ``picogame_ray`` helper,
    which computes these inputs.

    All fixed-point arguments are signed 16.16 integers.

    :param ~circuitpython_typing.ReadableBuffer map: at least ``mw * mh`` wall-type
        bytes, row-major; 0 is empty
    :param int mw: map width in cells
    :param int mh: map height in cells
    :param int posx: camera x position (fixed-point)
    :param int posy: camera y position (fixed-point)
    :param int lrx: x of the column-0 ray direction (fixed-point)
    :param int lry: y of the column-0 ray direction (fixed-point)
    :param int srx: per-column ray step x (fixed-point)
    :param int sry: per-column ray step y (fixed-point)
    :param int sh: screen height in pixels
    :param int stride: pixel width of one column
    :param int ncols: number of columns to cast
    :param ~circuitpython_typing.ReadableBuffer wcolors: two ``uint16`` colors per
        wall type: near face at ``[type * 2]``, side face at ``[type * 2 + 1]``
    :param ~circuitpython_typing.WriteableBuffer top: at least ``ncols`` ``uint16``
        values; receives each column's wall top row
    :param ~circuitpython_typing.WriteableBuffer bot: at least ``ncols`` ``uint16``
        values; receives each column's wall bottom row
    :param ~circuitpython_typing.WriteableBuffer col: at least ``ncols`` ``uint16``
        values; receives each column's wall color
    :param ~circuitpython_typing.WriteableBuffer dist: at least ``ncols`` ``int32``
        values; receives each column's perpendicular distance (fixed-point)
    :param ~circuitpython_typing.WriteableBuffer runs: optional; at least
        ``5 * ncols`` ``uint16`` values, laid out as five ``ncols``-long planes
        (x0s, x1s, tops, bots, colors). When given, adjacent equal columns are
        merged into wall runs suitable for :py:meth:`Canvas.vspans` and the run
        count is returned; otherwise `None` is returned."""
    ...

def road_edges(
    rl: WriteableBuffer,
    rr: WriteableBuffer,
    hw: ReadableBuffer,
    n: int,
    cx0: int,
    dist: int,
    cfg: ReadableBuffer,
) -> None:
    """Compute one racing-road frame's left and right edge columns. A low-level
    interface used by the ``picogame_road`` helper, which packs these inputs.

    Walks ``n`` screen rows bottom-up, accumulating the road curve, and writes the
    edge x coordinates into ``rl`` and ``rr``.

    :param ~circuitpython_typing.WriteableBuffer rl: at least ``n`` ``int16`` values;
        receives the left edge per row
    :param ~circuitpython_typing.WriteableBuffer rr: at least ``n`` ``int16`` values;
        receives the right edge per row
    :param ~circuitpython_typing.ReadableBuffer hw: at least ``n`` ``int32`` per-row
        half-widths (signed 16.16 fixed-point)
    :param int n: number of rows to compute
    :param int cx0: screen center x including lateral offset (signed 16.16 fixed-point)
    :param int dist: integer world distance
    :param ~circuitpython_typing.ReadableBuffer cfg: seven ``int32`` curve parameters,
        in order: ``f1_q20``, ``f2_q20``, ``amp1k_q16``, ``amp2k_q16``, ``world_step``,
        ``curve_step``, ``d_row_off``"""
    ...

def xip_map(path: str) -> memoryview:
    """A read-only memoryview over the flash bytes of `path` - 0 RAM, 0 copy - for a file on
    the internal-flash CIRCUITPY drive that occupies one contiguous run of clusters. Give it
    to ``Bitmap`` (PAL8/RGB565, slicing stays 0-copy). Raises OSError(ENOENT) if missing,
    OSError(EOPNOTSUPP) if not on internal flash, OSError(EINVAL) if empty, and OSError(EIO)
    with "fragmented" if the file is not one run - then load it another way (a smaller file
    copied onto a drive with free space usually lands contiguous)."""
    ...

def fat_layout(path: str) -> Tuple[int, int, int, int, int]:
    """(fragments, size, first_cluster, cluster_bytes, data_base_sector) for a file on a
    FAT mount. fragments == 1 means the file is one contiguous cluster run."""
    ...

def fat_max_free_run(path: str = "/") -> int:
    """Largest run of contiguous FREE clusters on the FAT mount holding `path`, in bytes
    (binary search via f_expand(opt=0), which only probes - nothing is allocated). This is the
    biggest file repack() can produce right now."""
    ...

def repack(path: str) -> int:
    """Rewrite `path` as ONE contiguous cluster run (a copy into a fresh f_expand-allocated
    file, verified, then renamed over the original). Returns the fragment count BEFORE
    (1 = was already contiguous, nothing written). Needs the drive writable by Python
    (boot.py, or storage.remount('/', readonly=False) with the host drive read-only) and a free
    run >= the file size (OSError(ENOSPC) otherwise, nothing changed)."""
    ...

def vblank(framebuffer: picodvi.Framebuffer) -> None:
    """Block until the DVI scanout's next vertical blanking (up to ~16.7 ms). Starting a
    full-frame compose right after vblank keeps the publish front consistently behind the
    beam, so each sweep shows one WHOLE frame (old or new) - removes single-buffer tearing
    when the compose fits within two sweeps. Costs the wait: budget it against your cap.
    """
    ...

class Bitmap:
    """An image atlas of one or more frames that all share one size. RGB565
    pixel data and palette entries must be in the display's transfer byte
    order (use :py:func:`rgb565` to build colors); PAL8 pixel data are
    palette indices.

    The bitmap references the caller-provided data without copying or modifying
    it. The backing buffer may live in RAM or in read-only memory."""

    def __init__(
        self,
        data: ReadableBuffer,
        width: int,
        height: int,
        *,
        format: int = RGB565,
        palette: Optional[ReadableBuffer] = None,
        frames: int = 1,
        stride: int = 0,
        transparent: Optional[int] = None,
    ) -> None:
        """:param ~circuitpython_typing.ReadableBuffer data: RGB565 pixel data in
            the display's transfer byte order, or palette indices for ``PAL8``
        :param int width: width of one frame in pixels
        :param int height: height of one frame in pixels
        :param int format: :py:data:`RGB565` (2 bytes per pixel) or :py:data:`PAL8`
            (1 byte per pixel, indexing ``palette``)
        :param ~circuitpython_typing.ReadableBuffer palette: for ``PAL8``, a buffer
            of transfer-order RGB565 colors, two bytes per entry. Every byte in
            ``data`` must be a valid palette index, that is, less than
            ``len(palette) // 2``.
        :param int frames: number of equal-size frames, laid out left to right in
            one horizontal atlas
        :param int stride: distance between two rows in pixels. ``0``, the
            default, means ``width * frames``; set it explicitly to reference a
            sub-region of a wider image.
        :param int transparent: color (``RGB565``) or index (``PAL8``) that is
            skipped when drawing. Defaults to `None`, fully opaque."""
        ...
    width: int
    """Width of one frame in pixels. (read-only)"""
    height: int
    """Height of one frame in pixels. (read-only)"""
    frames: int
    """Number of frames in the atlas. (read-only)"""
    format: int
    """:py:data:`RGB565` or :py:data:`PAL8`. (read-only)"""
    stride: int
    """Row stride in pixels. (read-only)"""
    palette: Optional[ReadableBuffer]
    """The ``PAL8`` palette buffer this Bitmap was built with, or `None` for
    ``RGB565``. (read-only)"""
    transparent: Optional[int]
    """The transparent color or index, or `None` if the Bitmap is fully
    opaque. (read-only)"""

class Canvas:
    """A RAM drawing surface composited as a `Scene` layer. Draw primitives
    into it; only redrawn areas repaint. Colors come from
    :py:func:`rgb565`."""

    def __init__(
        self,
        width: int,
        height: int,
        *,
        transparent: Optional[int] = None,
        buffer: Optional[WriteableBuffer] = None,
    ) -> None:
        """:param int width: surface width in pixels
        :param int height: surface height in pixels
        :param int transparent: color that is skipped when the canvas is
            composited; `None` makes every pixel opaque
        :param ~circuitpython_typing.WriteableBuffer buffer: optional caller-owned
            pixel buffer of at least ``width * height * 2`` bytes (for example a
            ``bytearray`` or a writable ``memoryview``). The canvas draws into it
            instead of allocating its own."""
        ...

    def clear(self, color: int) -> None:
        """Fill the whole surface with ``color``."""
        ...

    def pixel(self, x: int, y: int, color: int) -> None:
        """Set a single pixel."""
        ...

    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        """Fill an axis-aligned rectangle."""
        ...

    def blit(
        self,
        bitmap: Bitmap,
        x: int,
        y: int,
        frame: int = 0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Copy one frame of ``bitmap``, selected by ``frame``, into the canvas
        at ``(x, y)``, honoring the bitmap's transparent color."""
        ...

    def mode7(
        self,
        texture: Bitmap,
        horizon: int,
        y_off: int,
        z: int,
        rx0: int,
        ry0: int,
        rsx: int,
        rsy: int,
        cam_x: int,
        cam_y: int,
    ) -> None:
        """Fill rows below ``horizon`` with a perspective projection of ``texture``.
        The ``picogame_mode7`` helper computes the camera terms from an angle,
        position and field of view.

        :param Bitmap texture: texture whose width and height are powers of two
        :param int horizon: first canvas row to fill
        :param int y_off: vertical offset of the projection, in rows
        :param int z: camera height (signed 16.16 fixed-point)
        :param int rx0: ray x at the left column (signed 16.16 fixed-point)
        :param int ry0: ray y at the left column (signed 16.16 fixed-point)
        :param int rsx: per-column ray step x (signed 16.16 fixed-point)
        :param int rsy: per-column ray step y (signed 16.16 fixed-point)
        :param int cam_x: camera x position (signed 16.16 fixed-point)
        :param int cam_y: camera y position (signed 16.16 fixed-point)"""
        ...

    def fill_triangles(
        self,
        verts: ReadableBuffer,
        colors: ReadableBuffer,
        n: int,
        x_off: int = 0,
        y_off: int = 0,
    ) -> None:
        """Fill a batch of triangles in one call, which is faster than repeated
        :py:meth:`fill_triangle` calls for many triangles.

        :param ~circuitpython_typing.ReadableBuffer verts: ``6 * n`` ``int16``
            values: x0, y0, x1, y1, x2, y2 per triangle
        :param ~circuitpython_typing.ReadableBuffer colors: ``n`` ``uint16`` colors,
            one per triangle
        :param int n: number of triangles
        :param int x_off: added to every x before clipping
        :param int y_off: added to every y before clipping

        The offsets translate the whole batch, so one screen-space batch can be
        replayed into each `StripDraw` view by passing the negated view origin
        (``x_off=-vx, y_off=-vy``); triangles outside the view are skipped."""
        ...

    def vspans(
        self,
        x0s: ReadableBuffer,
        x1s: ReadableBuffer,
        tops: ReadableBuffer,
        bots: ReadableBuffer,
        colors: ReadableBuffer,
        n: int,
        x_off: int = 0,
        y_off: int = 0,
    ) -> None:
        """Fill a batch of vertical color spans in one call. Span ``i`` covers
        columns ``x0s[i]`` through ``x1s[i]`` (exclusive) and rows ``tops[i]``
        through ``bots[i]`` (exclusive) in color ``colors[i]``.

        :param ~circuitpython_typing.ReadableBuffer x0s: ``n`` ``uint16`` left edges
        :param ~circuitpython_typing.ReadableBuffer x1s: ``n`` ``uint16`` exclusive
            right edges
        :param ~circuitpython_typing.ReadableBuffer tops: ``n`` ``uint16`` top rows
        :param ~circuitpython_typing.ReadableBuffer bots: ``n`` ``uint16`` exclusive
            bottom rows
        :param ~circuitpython_typing.ReadableBuffer colors: ``n`` ``uint16`` colors
        :param int n: number of spans
        :param int x_off: added to every x before clipping
        :param int y_off: added to every y before clipping

        The offsets translate the whole batch, so one screen-space batch (for
        example `raycast` wall runs) can be replayed into each `StripDraw` view by
        passing the negated view origin; spans outside the view are skipped."""
        ...

    def road(
        self,
        ri0: int,
        tab: ReadableBuffer,
        rl: ReadableBuffer,
        rr: ReadableBuffer,
        d05_q8: int,
        d07_q8: int,
        colors: ReadableBuffer,
    ) -> None:
        """Draw one racing-road strip from precomputed tables. A low-level
        interface used by the ``picogame_road`` helper, which builds the tables.

        :param int ri0: road-table row of this surface's row 0; negative values
            are sky rows
        :param ~circuitpython_typing.ReadableBuffer tab: ``int16`` rows of
            ``edge_w``, ``dash_hw``, ``wb05_q8``, ``wb07_q8``, ``flags``
        :param ~circuitpython_typing.ReadableBuffer rl: ``int16`` per-row left
            edges, as computed by :py:func:`road_edges`
        :param ~circuitpython_typing.ReadableBuffer rr: ``int16`` per-row right
            edges
        :param int d05_q8: scroll phase (Q8 fixed-point)
        :param int d07_q8: scroll phase (Q8 fixed-point)
        :param ~circuitpython_typing.ReadableBuffer colors: six ``uint16`` colors,
            in order: sky, road a, road b, rumble a, rumble b, dash"""
        ...

    def rect(self, x: int, y: int, w: int, h: int, color: int) -> None:
        """Draw a one-pixel rectangle outline."""
        ...

    def line(self, x0: int, y0: int, x1: int, y1: int, color: int) -> None:
        """Draw a one-pixel line between two points."""
        ...

    def fill_circle(self, cx: int, cy: int, r: int, color: int) -> None:
        """Fill a circle of radius ``r`` centered on ``(cx, cy)``."""
        ...

    def circle(self, cx: int, cy: int, r: int, color: int) -> None:
        """Draw a one-pixel circle outline."""
        ...

    def ring(self, cx: int, cy: int, r: int, thickness: int, color: int) -> None:
        """Draw a circle outline ``thickness`` pixels wide, grown inwards from radius ``r``."""
        ...

    def triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int
    ) -> None:
        """Draw a one-pixel triangle outline through the three points."""
        ...

    def fill_triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int
    ) -> None:
        """Fill a triangle. See :py:meth:`fill_triangles` to submit a whole batch
        in one call."""
        ...

    def ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int) -> None:
        """Draw a one-pixel ellipse outline with radii ``rx``/``ry``."""
        ...

    def fill_ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int) -> None:
        """Fill an ellipse with radii ``rx``/``ry``."""
        ...

    def fill_round_rect(
        self, x: int, y: int, w: int, h: int, r: int, color: int
    ) -> None:
        """Fill a rectangle with corners rounded to radius ``r``."""
        ...

    def frame3d(self, x: int, y: int, w: int, h: int, light: int, dark: int) -> None:
        """Draw a one-pixel bevelled frame: top and left edges in ``light``, bottom and
        right in ``dark``, giving a raised look (swap the two for a sunken one)."""
        ...

    def text(
        self,
        x: int,
        y: int,
        s: str,
        fg: int,
        font: fontio.BuiltinFont,
        bg: int | None = None,
    ) -> None:
        """Draw ``s`` into the surface, rasterizing each glyph from ``font`` as it
        is drawn; no memory is retained between calls. Only ASCII characters are
        supported. If ``bg`` is given the glyph background is filled with it,
        otherwise it is transparent. Inside a `StripDraw` callback the view is a
        Canvas, so ``view.text(...)`` draws text directly into the frame."""
        ...

    def move(self, x: int, y: int) -> None:
        """Move the surface's top-left corner to (x, y) and mark both the old and new area dirty."""
        ...
    x: int
    """Horizontal position of the canvas top-left corner. (read-only)

    Set with :py:meth:`move`."""
    y: int
    """Vertical position of the canvas top-left corner. (read-only)

    Set with :py:meth:`move`."""
    width: int
    """Surface width in pixels. (read-only)"""
    height: int
    """Surface height in pixels. (read-only)"""

class Display:
    """An accelerated display backend that wraps an existing
    :py:class:`~busdisplay.BusDisplay` and sends pixels with asynchronous,
    double-buffered DMA. It reuses the wrapped display's bus, window commands
    and dimensions.

    Constructing it raises :py:class:`NotImplementedError` when
    :py:data:`FAST_DISPLAY_SUPPORTED` is `False`."""

    def __init__(self, display: busdisplay.BusDisplay, *, rgb444: bool = False) -> None:
        """:param ~busdisplay.BusDisplay display: the display to wrap
        :param bool rgb444: drive the panel in 12-bit RGB444 instead of 16-bit
            RGB565, reducing bus traffic at the cost of color depth (4,096 colors
            instead of 65,536). The panel controller must support 12-bit color;
            ST7789 and ST7735 do, ILI9341 does not. See :py:data:`RGB444_SUPPORTED`."""
        ...

    def render(
        self,
        sprites: List[Sprite],
        buffer_a: WriteableBuffer,
        buffer_b: WriteableBuffer,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        *,
        background: int = 0,
    ) -> None:
        """Render ``sprites`` into the screen region from ``(x0, y0)`` up to, but
        not including, ``(x1, y1)``, and send it with asynchronous DMA. ``buffer_a`` and ``buffer_b`` are two
        equal strip buffers of at least ``(x1 - x0) * 2`` bytes each, used for
        double buffering.

        This method accepts sprites only. For mixed layer kinds use a `Scene` or
        the module-level :py:func:`render`."""
        ...

class Framebuffer:
    """A RAM framebuffer render target that a `Scene` or :py:func:`render` can
    draw into instead of a :py:class:`~busdisplay.BusDisplay`, for example the
    scanout buffer of a :py:class:`picodvi.Framebuffer`.

    Constructing it raises :py:class:`NotImplementedError` when
    :py:data:`FRAMEBUFFER_SUPPORTED` is `False`."""

    def __init__(
        self,
        buffer: WriteableBuffer,
        width: int,
        height: int,
        *,
        native_rgb565: bool = False,
        rgb332: bool = False,
    ) -> None:
        """:param ~circuitpython_typing.WriteableBuffer buffer: caller-owned target
            buffer of at least ``width * height * 2`` bytes, or ``width * height``
            bytes with ``rgb332=True``
        :param int width: target width in pixels
        :param int height: target height in pixels
        :param bool native_rgb565: fill the buffer with native-endian RGB565, the
            format 16-bit scanout targets expect. By default the buffer holds
            transfer-order RGB565.
        :param bool rgb332: fill the buffer with 8-bit RGB332, the format of 8-bit
            scanout targets

        ``native_rgb565`` and ``rgb332`` cannot both be true. Bitmaps, palettes and
        :py:func:`rgb565` values stay transfer-order RGB565 regardless of the
        output format."""
        ...
    width: int
    """Target width in pixels. (read-only)"""
    height: int
    """Target height in pixels. (read-only)"""

class Particles:
    """A pooled particle layer (small moving dots), drawn as one Scene layer.
    Add it to a Scene, ``emit()`` bursts, and call ``tick()`` each frame."""

    def __init__(
        self, capacity: int, *, size: int = 1, gravity: float = 0.0, fade: bool = False
    ) -> None:
        """``capacity`` is how many particles may be alive at once; the pool is
        allocated once here and never grows. If :py:meth:`emit` would exceed it,
        the excess particles are dropped.

        ``size`` is the square side of one particle in pixels. ``gravity`` is added to
        each particle's vertical speed every :py:meth:`tick`. ``fade=True`` dims
        particles towards the end of their life instead of letting them vanish at full
        brightness."""
        ...

    def emit(
        self,
        x: int,
        y: int,
        count: int,
        speed: int = 1,
        life: int = 30,
        color: int = 0xFFFF,
    ) -> None:
        """Spawn ``count`` particles at ``(x, y)``, living ``life`` ticks, in
        ``color`` (default white). Each particle's horizontal and vertical velocity is chosen
        independently from ``-speed`` through ``speed`` pixels per tick."""
        ...

    def tick(self) -> None:
        """Advance all particles one step (movement, gravity, aging)."""
        ...

    def clear(self) -> None:
        """Remove all particles."""
        ...

class Scene:
    """A retained-mode scene with dirty-rectangle rendering for a `Display`,
    :py:class:`~busdisplay.BusDisplay` or `Framebuffer` target. Add layers once
    (insertion order is bottom to top), mutate them each frame, then call
    :py:meth:`refresh`; only the regions reported changed are repainted."""

    def __init__(
        self,
        display: Union[Display, busdisplay.BusDisplay, Framebuffer],
        buffer_a: Optional[WriteableBuffer] = None,
        buffer_b: Optional[WriteableBuffer] = None,
        *,
        background: int = 0,
        top: int = 0,
        bottom: int = 0,
        left: int = 0,
        right: int = 0,
    ) -> None:
        """:param display: the render target
        :param ~circuitpython_typing.WriteableBuffer buffer_a: a strip buffer,
            typically ``display.width * STRIP_H * 2`` bytes. Its size sets the
            strip height: each strip is ``size // (display.width * 2)`` rows. Two
            buffers let the next strip be composited while the previous one is
            being sent. On a `Framebuffer` target there are no strips and the
            buffers are unused; both default to `None`.
        :param ~circuitpython_typing.WriteableBuffer buffer_b: the second strip
            buffer, sized like ``buffer_a``
        :param int background: color that exposed areas are cleared to
        :param int top: rows at the top edge the scene never renders into
        :param int bottom: rows at the bottom edge the scene never renders into
        :param int left: columns at the left edge the scene never renders into
        :param int right: columns at the right edge the scene never renders into

        The four border insets reserve screen edges for content the application
        draws itself, for example with :py:func:`render`; the scene renders only
        the inner rectangle and never repaints the border."""
        ...

    def add(
        self,
        item: Union[Sprite, Tilemap, Canvas, Particles, StripDraw, Triangles],
        *,
        fixed: bool = False,
    ) -> Union[Sprite, Tilemap, Canvas, Particles, StripDraw, Triangles]:
        """Add a layer of any kind, drawn starting with the next refresh; insertion
        order is bottom to top. Returns the added item.

        ``fixed=True`` pins the item to the screen so it ignores the view offset
        set by :py:meth:`set_view`, for example for a HUD over a scrolling world.
        `StripDraw` and `Triangles` layers always draw in screen coordinates and
        are unaffected by both ``fixed`` and the view offset."""
        ...

    def add_all(
        self,
        items: Iterable[
            Union[Sprite, Tilemap, Canvas, Particles, StripDraw, Triangles]
        ],
    ) -> None:
        """Add several layers at once, bottom to top in iteration order."""
        ...

    def remove(
        self, item: Union[Sprite, Tilemap, Canvas, Particles, StripDraw, Triangles]
    ) -> None:
        """Remove a previously added item; the draw order of the rest is unchanged.
        The next refresh repaints the scene, so the item leaves no ghost. The item
        itself is untouched and may be added again later. Raises
        :py:class:`ValueError` if the item is not in the scene."""
        ...

    def invalidate(self) -> None:
        """Force the scene's whole render area to repaint on the next refresh."""
        ...

    def set_view(self, ox: int, oy: int) -> None:
        """Set the screen position ``(ox, oy)`` of scene coordinate ``(0, 0)``:
        a scene point ``(x, y)`` is drawn at ``(x + ox, y + oy)``. Use a constant
        offset to center a small scene, or update it each frame to scroll, which
        repaints the whole render area."""
        ...
    view: Tuple[int, int]
    """The current view offset ``(ox, oy)`` as set by :py:meth:`set_view`. (read-only)"""
    display: Union[Display, busdisplay.BusDisplay, Framebuffer]
    """The render target this Scene was built with. (read-only)"""

    def refresh(self) -> Optional[list]:
        """Repaint the regions changed by the scene's layers since the previous
        refresh. Returns the bounding dirty rectangle as a list
        ``[x1, y1, x2, y2]`` with exclusive ``x2``/``y2``, or `None` if nothing
        changed. The returned list object is reused: read it before the next
        ``refresh()`` call."""
        ...

class Sprite:
    """A positioned, animatable instance of a :py:class:`Bitmap`."""

    def __init__(
        self,
        bitmap: Bitmap,
        x: int = 0,
        y: int = 0,
        *,
        frame: int = 0,
        visible: bool = True,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Place ``bitmap`` with its top-left corner at ``(x, y)`` in scene
        coordinates, showing the frame selected by ``frame``. Scene coordinates
        follow the view offset, so the sprite moves with a scrolling world.

        ``visible=False`` creates the sprite without drawing it, for example to
        pre-allocate a pool of sprites up front. ``flip_x`` and ``flip_y`` mirror
        the frame at draw time."""
        ...
    frame: int
    """Which frame of the bitmap's atlas to draw, starting at 0. Stepping this
    animates the sprite."""
    visible: bool
    """`False` hides the sprite. It stays in the scene and the area under it
    repaints."""
    flip_x: bool
    """Mirror the frame horizontally at draw time."""
    flip_y: bool
    """Mirror the frame vertically at draw time."""
    x: int
    """Horizontal pixel position in scene coordinates. Setting accepts a float
    for sub-pixel placement; reading returns the floored pixel."""
    y: int
    """Vertical pixel position in scene coordinates. Setting accepts a float
    for sub-pixel placement; reading returns the floored pixel."""
    fx: float
    """Horizontal sub-pixel position, for example ``sprite.fx += 2.4``."""
    fy: float
    """Vertical sub-pixel position, for example ``sprite.fy += 2.4``."""
    scale: float
    """Uniform draw scale using nearest-neighbor sampling. ``1.0`` is native size;
    fractional values are allowed. The anchor point stays put."""
    angle: float
    """Rotation in degrees about the anchor; ``0`` is unrotated. Values are stored
    as whole degrees. Rotation uses nearest-neighbor sampling."""
    shadow: bool
    """Draw opaque pixels by darkening the destination instead of writing color,
    producing a shadow silhouette or a dimming overlay. Mutually exclusive with
    `flash`, `dither` and `tint`."""
    flash: int
    """Draw opaque pixels as one solid color instead of their own, for example as
    a brief hit flash. Set to a color from :py:func:`rgb565` to enable, ``0`` to
    disable. Because ``0`` disables the effect, pure black cannot be the flash
    color; use a near-black color instead. Mutually exclusive with `shadow`,
    `dither` and `tint`."""
    dither: int
    """Approximate transparency with an ordered (Bayer) dither pattern; there is
    no alpha blending. ``0`` is opaque (off), ``8`` is about half transparent and
    ``16`` is invisible. Mutually exclusive with `shadow`, `flash` and `tint`."""
    tint: int
    """Multiply opaque pixels by a color from :py:func:`rgb565`, preserving the
    sprite's shading (unlike `flash`, which replaces it). ``0`` disables, so pure
    black cannot be the tint color. Mutually exclusive with `shadow`, `flash`
    and `dither`."""
    transpose: bool
    """Transpose the frame by swapping its x and y axes. Combined with `flip_x`
    and `flip_y` this yields all 8 orthogonal orientations. Applies only at
    ``scale == 1.0`` and ``angle == 0``; for rotation combined with scaling use
    `angle`. The drawn footprint swaps width and height."""
    data: Any
    """Arbitrary per-sprite user payload for game state (default None)."""
    bitmap: Bitmap
    """The sprite's source bitmap. Assigning a new one swaps the graphics and may
    change the sprite's size; the scene repaints both the old and new bounds on
    the next refresh."""
    anchor: Tuple[float, float]
    """Pivot as fractions of the bitmap size: ``(0, 0)`` = top-left (default),
    ``(0.5, 0.5)`` = center, ``(0.5, 1.0)`` = bottom-center. ``x``/``y`` then
    refer to this point, so rotating frames or swapping to a different size
    stays aligned. Stored in 1/256 steps."""

    def move(self, x: float, y: float) -> None:
        """Set the sprite position. Accepts floats for sub-pixel placement."""
        ...

    def touch(self) -> None:
        """Force this sprite to repaint on the next :py:meth:`Scene.refresh` even
        though none of its tracked properties (position, frame, scale, angle,
        bitmap) changed. Call it after mutating the bitmap's backing buffer in
        place, which the dirty-region tracking cannot otherwise detect."""
        ...

    def overlaps(
        self,
        other: Union[Sprite, Tuple[int, int], Tuple[int, int, int, int]],
        inset: int = 0,
    ) -> bool:
        """Return `True` if this sprite's drawn rectangle overlaps ``other``. Bounds
        are inclusive, so touching edges count as an overlap. ``other`` may be
        another `Sprite`, a point ``(x, y)`` or a rectangle ``(x1, y1, x2, y2)``.
        The rectangle accounts for anchor, scale and rotation. ``inset`` shrinks
        this sprite's rectangle by that many pixels on each side."""
        ...

    def near(self, other: Union[Sprite, Tuple[int, int]], r: int) -> bool:
        """Return `True` when the distance between centers is less than ``r``
        pixels. ``other`` may be a `Sprite` or a point ``(x, y)``. Centers come
        from the drawn rectangle, so the test accounts for the anchor."""
        ...

class StripDraw:
    """An immediate-mode draw layer that holds no pixel buffer. On each refresh,
    for every render strip overlapping its rectangle, ``callback(view, vx, vy,
    vw, vh)`` is called with a `Canvas` view of the live strip buffer, so the
    callback draws primitives directly into the frame. StripDraw layers always
    draw in screen coordinates and ignore the scene's view offset.

    ``(vx, vy)`` is the view origin in screen coordinates and ``(vw, vh)`` is
    its size: to draw a screen point ``(sx, sy)``, draw at ``(sx - vx, sy - vy)``
    in ``view``. The view may span the full render-region width even when the
    layer is narrower (the layer's rectangle only limits which rows are drawn),
    so fill your own rectangle with :py:meth:`Canvas.fill_rect` rather than
    ``view.clear()``, which fills the whole width.

    Moving or resizing the layer by assigning :py:attr:`x`, :py:attr:`y`,
    :py:attr:`width` or :py:attr:`height` can leave the old area stale; call
    :py:meth:`Scene.invalidate` afterwards for a clean repaint."""

    def __init__(
        self,
        callback: Callable[[Canvas, int, int, int, int], None],
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
        *,
        always_dirty: bool = True,
    ) -> None:
        """:param callback: called for each overlapping render strip as
            ``callback(view, vx, vy, vw, vh)``
        :param int x: left edge of the layer's screen rectangle
        :param int y: top edge of the layer's screen rectangle
        :param int width: rectangle width in pixels
        :param int height: rectangle height in pixels
        :param bool always_dirty: when `True` the layer redraws every refresh;
            when `False`, call :py:meth:`invalidate` after its content changes"""
        ...
    x: int
    """Left edge of the layer's screen rectangle."""
    y: int
    """Top edge of the layer's screen rectangle."""
    width: int
    """Width of the layer's screen rectangle in pixels."""
    height: int
    """Height of the layer's screen rectangle in pixels."""
    always_dirty: bool
    """When `True` (the default) the rectangle repaints every frame, for animated
    content. When `False` the layer renders once initially and then repaints only
    after an :py:meth:`invalidate` call or when overlapped by another dirty
    layer; call :py:meth:`invalidate` after each content change."""

    def invalidate(self, x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> None:
        """Mark the layer dirty so it repaints on the next refresh; only needed
        when ``always_dirty`` is `False`.

        With no arguments the whole layer repaints. To repaint one region, pass
        all four values as a rectangle in the view-local coordinates the draw
        callback uses; passing only some of them raises :py:class:`ValueError`.
        Repeated calls accumulate, and the rectangle is clamped to the layer."""
        ...

class Tilemap:
    """A grid of tile indices into a tileset `Bitmap`, where each bitmap frame
    is one tile. Add it to a `Scene` as a background layer; setting tiles or
    moving the map marks only the affected area dirty."""

    def __init__(self, tileset: Bitmap, cols: int, rows: int) -> None:
        """:param Bitmap tileset: the tile images, one frame per tile
        :param int cols: map width in tiles
        :param int rows: map height in tiles"""
        ...

    def get_tile(self, tx: int, ty: int) -> int:
        """Return the tile index at (tx, ty). Out-of-range reads as 0."""
        ...

    def set_tile(
        self,
        tx: int,
        ty: int,
        value: int,
        *,
        flip_x: bool = False,
        flip_y: bool = False,
        transpose: bool = False,
    ) -> None:
        """Set the tile at ``(tx, ty)`` and mark it dirty. The keyword flags orient
        the tile at draw time; together they yield all 8 orientations (4 rotations
        times mirror), so one stored tile can serve as several. The flags can
        represent the remap table emitted by the ``png2picogame.py --dedup``
        tool. Out-of-range writes are ignored."""
        ...

    def move(self, x: int, y: int) -> None:
        """Move the whole map to pixel (x, y)."""
        ...

    def fill(self, value: int) -> None:
        """Set every tile to ``value``."""
        ...
    x: int
    """Horizontal position of the map's top-left corner. (read-only)

    Set with :py:meth:`move`."""
    y: int
    """Vertical position of the map's top-left corner. (read-only)

    Set with :py:meth:`move`."""
    cols: int
    """Map width in tiles. (read-only)"""
    rows: int
    """Map height in tiles. (read-only)"""

class Triangles:
    """A retained triangle batch drawn as a `Scene` layer. The batch is
    rasterized directly into each render strip; no per-strip Python runs and no
    pixel buffer is held. Triangles layers always draw in screen coordinates and
    ignore the scene's view offset.

    For each frame: project points with :py:func:`project`, write triangles
    into the buffers in back-to-front order, set :py:attr:`count`, then call
    :py:meth:`Scene.refresh`."""

    def __init__(self, verts: ReadableBuffer, colors: ReadableBuffer) -> None:
        """:param ~circuitpython_typing.ReadableBuffer verts: caller-owned buffer of
            ``int16`` values, six per triangle: x0, y0, x1, y1, x2, y2. Refill it in
            place each frame.
        :param ~circuitpython_typing.ReadableBuffer colors: caller-owned buffer of
            ``uint16`` colors, one per triangle"""
        ...
    count: int
    """How many triangles of the batch draw on the next refresh, clamped to the
    buffer capacity. Assigning marks the layer dirty for a full repaint."""

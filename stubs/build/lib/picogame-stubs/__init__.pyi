from __future__ import annotations

from typing import Any, Callable, Iterable, List, Optional, Tuple, Union

import busdisplay
import fontio
from circuitpython_typing import ReadableBuffer, WriteableBuffer

class Bitmap:
    """An image atlas of one or more equal-size frames, of arbitrary size.

    Unlike ``_stage`` (fixed 16x16 tiles), frames may be any width/height.
    Pixel data and palette entries must be in the display's wire byte order
    (use :py:func:`picogame.rgb565` to build colors)."""

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
    ) -> None: ...

    width: int
    height: int
    frames: int
    """Frame dimensions and frame count (read-only)."""
    format: int
    """RGB565 or PAL8 (read-only)."""
    stride: int
    """Row stride in pixels (read-only)."""
    palette: Optional[ReadableBuffer]
    """The PAL8 palette buffer this Bitmap was built with, or None for RGB565
    (read-only). Lets palette helpers read it back instead of holding a sidecar ref."""
    transparent: Optional[int]
    """The transparent color/index, or None if the Bitmap is fully opaque (read-only)."""

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
    ) -> None: ...

    bitmap: Bitmap
    """The Bitmap drawn (swap it at runtime to change the art; the frame index is kept)."""
    frame: int
    """Which frame of the bitmap's atlas to draw (0-based) - animation = stepping this."""
    visible: bool
    """False hides the sprite (it stays in the scene; the area under it repaints)."""
    flip_x: bool
    flip_y: bool
    """Mirror the frame horizontally / vertically at draw time (free on the fast path)."""
    x: int
    y: int
    """Integer pixel position (scene coords). Setting accepts a float for
    sub-pixel placement; reading returns the floored pixel."""
    fx: float
    fy: float
    """Sub-pixel position (use for smooth physics: e.g. ``sprite.fx += 2.4``)."""
    scale: float
    """Uniform draw scale (nearest-neighbour). 1.0 = native (fast path); 2.0 = double
    size, fractional values are allowed (e.g. a powerup grow tween). Anchor stays put."""
    angle: float
    """Rotation in degrees about the anchor (0 = none, the fast path). Nearest-neighbour,
    so integer scales stay crisp; rotation shimmers slightly (pixel-art trade-off)."""
    shadow: bool
    """Draw opaque pixels as a darkened destination instead of colour - a drop-shadow
    silhouette (offset copy below the sprite) or a dim overlay (a solid sprite scaled
    over a dialog/pause area)."""
    flash: int
    """Draw opaque pixels as a solid colour (a wire-order RGB565 int from rgb565) instead
    of their own colour - a hit-flash or tint. Set to a colour to enable, 0/False to turn
    off. Pulse it for 1-3 frames on impact. Mutually exclusive with shadow/dither."""
    dither: int
    """Fake transparency via an ordered (Bayer) dither, no alpha blending: 0 = opaque
    (off), 8 = ~50% see-through, 16 = invisible. A classic 1-bit look - for ghosts,
    fading/spawning enemies, fog, force fields. Mutually exclusive with shadow/flash."""
    tint: int
    """Multiply opaque pixels by a colour (wire-order RGB565 from rgb565), keeping the
    sprite's shading - coloured lighting, a red damage flush, a blue freeze, a power-up
    glow. Unlike ``flash`` (flat replace) ``tint`` preserves detail. 0/False = off. Mutually
    exclusive with shadow/flash/dither."""
    transpose: bool
    """Swap the sprite's X/Y axes - a cheap 90deg turn (no shimmer, unlike ``angle``).
    Combined with ``flip_x``/``flip_y`` it gives all 8 orientations for free. Only on the fast
    path (scale 1.0, angle 0); for rotation WITH scaling use ``angle``. The drawn footprint
    swaps width/height."""
    data: Any
    """Arbitrary per-sprite user payload for game state (default None)."""
    bitmap: Bitmap
    """The sprite's source bitmap. Assigning a new one swaps graphics and may
    change size; the scene repaints both the old and new bounds next refresh
    (e.g. powerups, resizable HUD bars, text labels)."""
    anchor: Tuple[float, float]
    """Pivot as fractions of the bitmap size: ``(0, 0)`` = top-left (default),
    ``(0.5, 0.5)`` = center, ``(0.5, 1.0)`` = bottom-center. ``x``/``y`` then
    refer to this point, so rotating frames or swapping to a different size
    stays aligned. Stored in 1/256 steps."""

    def move(self, x: int, y: int) -> None:
        """Set the sprite position."""
        ...

    def touch(self) -> None:
        """Force this sprite to repaint on the next ``Scene.refresh()`` even though none
        of its tracked properties (position, frame, scale, angle, bitmap) changed. Call
        it after mutating the sprite's bitmap pixels IN PLACE (e.g. streaming a new frame
        into the same buffer), which the dirty-rect tracker can't otherwise detect."""
        ...

    def overlaps(self, other: "Sprite | tuple", inset: int = 0) -> bool:
        """True if this sprite's drawn box overlaps ``other`` - an inclusive AABB, so they
        collide the moment they touch. ``other`` may be another Sprite, a point ``(x, y)``,
        or a rect ``(x1, y1, x2, y2)`` (e.g. a trigger zone or the screen for culling).
        The box is anchor/scale/rotation aware. ``inset`` shrinks THIS sprite's box by N px
        on each side, for a fair hitbox smaller than the art."""
        ...

    def near(self, other: "Sprite | tuple", r: int) -> bool:
        """True if this sprite's centre is within ``r`` pixels of ``other``'s centre (squared
        distance, no sqrt) - the round/forgiving test for bullets, pickups, explosions.
        ``other`` may be a Sprite or a point ``(x, y)``. Centres come from the drawn box, so
        it is anchor aware."""
        ...

class StripDraw:
    """An immediate-mode draw layer that holds NO pixel buffer. Each refresh, for
    every render strip overlapping its rect, ``callback(view, vx, vy, vw, vh)`` is
    called with a :py:class:`Canvas` ``view`` pointing straight at the live strip
    buffer - so you draw primitives directly into the frame (zero RAM, vs a Canvas
    which costs width*height*2 bytes). The view's local (0, 0) is screen pixel
    (vx, vy); (vw, vh) is the strip size. Draw only the rows in [vy, vy+vh) for
    speed (anything outside the view is clipped anyway). The rect is repainted every
    frame, so use it for animated / scanline content (pseudo-3D, gradients,
    procedural backgrounds), not static art (use Canvas for that).

    COORDINATE CONTRACT: ``vx`` is the RENDER REGION's origin (NOT this layer's x), and the
    view spans the FULL region WIDTH (the layer's rect only gates which ROWS run). So draw at
    ABSOLUTE screen coords minus (vx, vy), and fill only your own rect with ``fill_rect`` -
    ``view.clear()`` fills the whole region width. (When you render a StripDraw via
    ``picogame.render([sd], buf, x,y,x+w,y+h)`` the region == the rect, so vx == x.)
    Text via ``Canvas.text`` is ASCII (the built-in font); non-ASCII has no glyph."""

    def __init__(
        self,
        callback: Callable[[Canvas, int, int, int, int], None],
        x: int = 0,
        y: int = 0,
        width: int = 0,
        height: int = 0,
    ) -> None: ...

    x: int
    y: int
    width: int
    height: int
    """The screen rect repainted each refresh (read/write). Move or resize the layer
    by assigning these. Shrinking the rect leaves stale pixels behind - follow a
    shrink with ``scene.invalidate()`` for a clean repaint (as the fx helpers do)."""
    always_dirty: bool
    """True (default): repaint every frame - for animated content (pseudo-3D, gradients). False:
    repaint only after an ``invalidate()`` call (or when overlapped by another dirty layer) - for on-change UI,
    so a static panel doesn't re-rasterize+re-push every frame. With False you MUST invalidate() on
    every content/visibility change (it's invisible until you do)."""

    def invalidate(self, x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> None:
        """Mark dirty so the layer repaints on the next refresh (only needed when
        ``always_dirty=False``). With no args, the whole layer repaints. Pass a rect in
        VIEW-LOCAL coordinates (the same (0,0)-at-``(vx, vy)`` space the draw callback uses) to
        repaint only that region - like Canvas/Tilemap, the Scene then recomposites and pushes just
        those rows. Repeated calls union; the rect is clamped to the layer."""

class Triangles:
    def __init__(self, verts: ReadableBuffer, colors: ReadableBuffer) -> None:
        """A retained SCREEN-SPACE triangle batch drawn entirely in C by the compositor:
        ``verts`` = int16 x0,y0,x1,y1,x2,y2 per triangle, ``colors`` = uint16 wire RGB565 per
        triangle - both CALLER-OWNED (fill them in place each frame). Set ``count`` to how
        many triangles should draw; the assignment marks the layer dirty (full screen).
        Unlike a StripDraw callback this runs no Python per strip, and unlike a Canvas it
        holds no pixel buffer - the batch rasterises straight into each render strip with
        a cheap band reject. The 3D-scene layer: pg.project into the arrays, painter's-order
        the faces, set count, scene.refresh()."""
        ...
    count: int
    """How many triangles of the batch draw next refresh (clamped to the buffer
    capacity). Assigning marks the layer dirty for a full repaint."""

"""2D game engine for the PicoPad and similar boards.

Draws arbitrary-size sprites (unlike ``_stage``'s fixed 16x16 tiles) to a
``busdisplay`` through a reusable strip buffer, with a dirty-rect scene,
tilemaps, particles, a drawing canvas and camera/effects."""

RGB565: int
"""16-bit color bitmap format (wire byte order)."""
PAL8: int
"""8-bit paletted bitmap format."""

def rgb565(r: int, g: int, b: int) -> int:
    """Build a display wire-order RGB565 color from 8-bit components."""
    ...

def invert(display: busdisplay.BusDisplay, on: bool) -> None:
    """Toggle the panel's hardware colour inversion (INVON/INVOFF). Instant and sends NO
    pixel data, so a brief invert is a FREE full-screen flash (a 1-bit negative 'hit' look)
    - cheaper than a Fade overlay. ST7789/ST7735 support it."""
    ...

def render(
    display: busdisplay.BusDisplay,
    sprites: List[Sprite],
    buffer: WriteableBuffer,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    *,
    background: int = 0,
) -> None:
    """Render ``sprites`` into the screen region [x0,x1) x [y0,y1) and push it
    to ``display``. ``buffer`` is a reusable strip buffer (>= region_width*2 bytes)."""
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
    """AABB overlap test with INCLUSIVE bounds - both corners are part of the box, so two
    boxes collide the moment they TOUCH (no visible overlap, no gap). Pass sprite hitboxes
    as (x, y, x+w, y+h): collision fires on contact, the usual game feel. With 8 args: box
    (x1,y1,x2,y2) vs box (ax1,ay1,ax2,ay2). With 6 args: box vs point (ax1, ay1).
    NOTE: this is intentionally inclusive, unlike render's half-open [x0,x1) pixel ranges -
    render is about pixels, collide is about game hitboxes (touch = hit)."""
    ...

def value2d(x: float, y: float, *, seed: int = 0) -> float:
    """Smooth 2-D value noise in 0..1 (fast C)."""
    ...

def value1d(x: float, *, seed: int = 0) -> float: ...
def fbm2d(
    x: float,
    y: float,
    *,
    octaves: int = 4,
    seed: int = 0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float: ...
def fbm1d(
    x: float,
    *,
    octaves: int = 4,
    seed: int = 0,
    lacunarity: float = 2.0,
    gain: float = 0.5,
) -> float: ...

class Framebuffer:
    """A RAM framebuffer render target that a Scene or :py:func:`render` can draw
    into instead of a BusDisplay. ``buffer`` must be a writable buffer of at least
    ``width*height*2`` bytes (``width*height`` for ``rgb332=True``); the caller owns it
    (a ``bytearray`` in the browser, the DVI scanout buffer on FruitJam). By default the
    pixels are wire-order RGB565 (the engine's internal format); ``native_rgb565=True``
    byte-swaps each finished region to NATIVE RGB565 - the format 16-bit picodvi /
    canvas scanout targets expect; ``rgb332=True`` quantizes each finished region to
    RGB332 bytes - the format of 8-bit picodvi scanout (FruitJam 640x480, which the
    hardware only offers at 8bpp). Assets, palettes and ``rgb565()`` stay wire-order
    RGB565 throughout regardless of the output format."""

    def __init__(
        self,
        buffer: WriteableBuffer,
        width: int,
        height: int,
        *,
        native_rgb565: bool = False,
        rgb332: bool = False,
    ) -> None: ...

    width: int
    height: int
    """Target size in pixels (read-only)."""

class Canvas:
    """A RAM drawing surface (any size) composited as a Scene layer. Draw
    primitives into it; only redrawn areas repaint. Colors are wire-order
    (use picogame.rgb565)."""

    def __init__(
        self,
        width: int,
        height: int,
        *,
        transparent: Optional[int] = None,
        buffer: Optional[WriteableBuffer] = None,
    ) -> None:
        """If ``buffer`` is given (>= width*height*2 bytes, e.g. a memoryview from
        picogame_arena), the Canvas draws into it instead of allocating its own -
        lets you pre-allocate big surfaces once and dodge heap fragmentation."""
        ...

    def clear(self, color: int) -> None: ...
    def pixel(self, x: int, y: int, color: int) -> None: ...
    def fill_rect(self, x: int, y: int, w: int, h: int, color: int) -> None: ...
    def blit(
        self,
        bitmap: Bitmap,
        x: int,
        y: int,
        frame: int = 0,
        flip_x: bool = False,
        flip_y: bool = False,
    ) -> None:
        """Stamp frame ``frame`` of ``bitmap`` into the canvas at (x, y), honouring its transparent
        key. The retained way to bake an image (icon, portrait, rendered text) into a panel.
        """
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
        """Fill rows below ``horizon`` with a perspective ground plane (Mode-7) of
        ``texture`` (power-of-2 dims). The int args are 16.16 fixed-point camera
        terms; use the picogame_mode7 helper to compute them from angle/pos/fov."""
        ...

    def fill_triangles(
        self,
        verts: ReadableBuffer,
        colors: ReadableBuffer,
        n: int,
        x_off: int = 0,
        y_off: int = 0,
    ) -> None:
        """Fill ``n`` triangles in ONE call: ``verts`` = int16 x0,y0,x1,y1,x2,y2 per triangle,
        ``colors`` = uint16 wire RGB565 per triangle. Same rasteriser as fill_triangle, but the
        whole batch crosses the Python/C boundary once - the win for many small triangles
        (blocky 3D, low-poly meshes) where the ~10 us per-call overhead otherwise dominates.
        ``x_off``/``y_off`` translate every vertex before clipping - pass the negated strip
        origin (``y_off=-vy``) to replay one screen-space batch into each StripDraw view;
        triangles fully outside the band are rejected with three compares, so the
        per-strip re-submission stays cheap."""
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
        """Fill ``n`` vertical colour spans in ONE call: span i covers x0s[i]..x1s[i] (exclusive)
        by tops[i]..bots[i] (exclusive) in colour colors[i] - all five are uint16 arrays.
        The batch primitive for column renderers (a raycaster's merged wall runs): the whole
        span list crosses the Python/C boundary once per strip instead of once per span.
        ``x_off``/``y_off`` translate every span before clipping - pass the negated strip origin
        (x_off=-vx, y_off=-vy) to replay one screen-space batch into each StripDraw view;
        spans outside the band are rejected with two compares."""
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
        """Draw one racing-road strip (OutRun-style) from precomputed tables - the whole
        per-scanline loop in one call. ri0 = road-table row of this surface's row 0 (may be
        negative = sky rows). tab = int16 rows of {edge_w, dash_hw, wb05_q8, wb07_q8, flags};
        rl/rr = int16 per-row edges (see picogame.road_edges); d05/d07 = Q8 scroll phases;
        colors = 6x uint16 {sky, road_a, road_b, rumble_a, rumble_b, dash}."""
        ...

    def rect(self, x: int, y: int, w: int, h: int, color: int) -> None: ...
    def line(self, x0: int, y0: int, x1: int, y1: int, color: int) -> None: ...
    def fill_circle(self, cx: int, cy: int, r: int, color: int) -> None: ...
    def circle(self, cx: int, cy: int, r: int, color: int) -> None: ...
    def ring(self, cx: int, cy: int, r: int, thickness: int, color: int) -> None: ...
    def triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int
    ) -> None: ...
    def fill_triangle(
        self, x0: int, y0: int, x1: int, y1: int, x2: int, y2: int, color: int
    ) -> None: ...
    def ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int) -> None: ...
    def fill_ellipse(self, cx: int, cy: int, rx: int, ry: int, color: int) -> None: ...
    def fill_round_rect(
        self, x: int, y: int, w: int, h: int, r: int, color: int
    ) -> None: ...
    def frame3d(
        self, x: int, y: int, w: int, h: int, light: int, dark: int
    ) -> None: ...
    def text(
        self,
        x: int,
        y: int,
        s: str,
        fg: int,
        font: fontio.BuiltinFont,
        bg: int | None = None,
    ) -> None:
        """Composite ``s`` into the surface in C, rasterizing each glyph from ``font`` on the fly -
        no Python glyph cache, no per-call Bitmap/Sprite (zero retained text RAM, no fragmentation).
        If ``bg`` is given the glyph background is filled too; otherwise it is transparent. Inside a
        StripDraw callback the ``view`` is a Canvas pointing at the live strip, so ``view.text(...)``
        draws immediate-mode HUD/screen text straight into the frame."""

    def move(self, x: int, y: int) -> None: ...

    x: int
    y: int
    """Current pixel position of the canvas top-left (read-only; set with move())."""
    width: int
    height: int
    """Surface size in pixels (read-only)."""

class Display:
    """Fast display backend: wraps an existing ``busdisplay.BusDisplay`` and
    pushes pixels with asynchronous double-buffered DMA, overlapping the CPU
    blit of the next strip with the SPI transfer of the current one.

    Controller- and resolution-agnostic: reuses the busdisplay's SPI bus,
    window commands and dimensions."""

    def __init__(self, display: busdisplay.BusDisplay, *, rgb444: bool = False) -> None:
        """rgb444=True drives the panel in 12-bit RGB444 instead of 16-bit RGB565: ~25% less
        SPI traffic (and thus more FPS on full-screen / scrolling, transfer-bound scenes), at
        4096 colours instead of 65536 - which PAL8 art doesn't notice. The panel controller
        must support COLMOD 12-bit (ST7789/ST7735 do; ILI9341 does NOT)."""
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
        """Render ``sprites`` into region [x0,x1) x [y0,y1) and push via async
        DMA. ``buffer_a``/``buffer_b`` are two equal strip buffers used for
        double buffering (each >= region_width*2 bytes).

        SPRITES ONLY (unlike module-level ``picogame.render()``, which also accepts
        StripDraw/Canvas/Tilemap/Particles): this is the low-level double-buffered
        sprite push. For mixed layer kinds use a ``Scene`` or ``picogame.render()``."""
        ...

class Particles:
    """A pooled particle layer (small moving dots), drawn as one Scene layer.
    Add it to a Scene, ``emit()`` bursts, and call ``tick()`` each frame."""

    def __init__(
        self, capacity: int, *, size: int = 1, gravity: float = 0.0, fade: bool = False
    ) -> None: ...
    def emit(
        self,
        x: int,
        y: int,
        count: int,
        speed: int = 1,
        life: int = 30,
        color: int = 0xFFFF,
    ) -> None:
        """Spawn ``count`` particles at (x, y) with random velocity up to ``speed``
        px/tick, living ``life`` ticks, in wire-order ``color``."""
        ...

    def tick(self) -> None:
        """Advance all particles one step (move, gravity, ageing)."""
        ...

    def clear(self) -> None:
        """Remove all particles."""
        ...

class Scene:
    """Retained-mode scene with dirty-rectangle rendering. Add sprites and
    tilemaps once (tilemaps first = bottom layer), mutate them each frame,
    then call :py:meth:`refresh` - only the changed region is repainted.
    Backed by a fast :py:class:`Display`."""

    def __init__(
        self,
        display: Display,
        buffer_a: WriteableBuffer,
        buffer_b: WriteableBuffer,
        *,
        background: int = 0,
    ) -> None: ...
    def add(
        self, item: Union[Sprite, Tilemap], *, fixed: bool = False
    ) -> Union[Sprite, Tilemap]:
        """Add a sprite/tilemap/particles/canvas (drawn next refresh; insertion
        order is bottom-to-top). fixed=True pins the item to the screen (it ignores
        the view offset) - use it for HUD / score / dialog over a scrolling world.
        Returns the added item, so you can write ``spr = scene.add(Sprite(...))``."""
        ...

    def add_all(self, items: Iterable[Union[Sprite, Tilemap]]) -> None:
        """Add several sprites/tilemaps at once (bottom-to-top in order)."""
        ...

    def remove(self, item: Union[Sprite, Tilemap]) -> None:
        """Remove a previously add()ed item (draw order of the rest is unchanged).
        The next refresh repaints over where it was (a full repaint, like
        :py:meth:`invalidate`), so it leaves no ghost. The item itself is untouched -
        keep a reference and add() it again later to bring it back. Raises
        ValueError if the item is not in the scene (e.g. already removed)."""
        ...

    def invalidate(self) -> None:
        """Force a full-screen repaint on the next refresh (e.g. on scene change)."""
        ...

    def set_view(self, ox: int, oy: int) -> None:
        """Set the view offset = screen position of the scene origin. Use a
        constant offset to centre a small game, or update it each frame to
        scroll (which repaints the whole screen)."""
        ...
    view: Tuple[int, int]
    """The current view offset (ox, oy) as set by set_view() (read-only)."""
    display: Union[Display, busdisplay.BusDisplay]
    """The backend this Scene was built with (a picogame.Display or a busdisplay),
    read-only - handy for one-off picogame.render() / Display.render() calls."""

    def refresh(self) -> Optional[list]:
        """Diff against the previous frame and repaint only the changed region(s).
        Returns the bounding dirty rect as a REUSED list [x1, y1, x2, y2] (read it
        immediately; it's overwritten next call), or None if nothing changed."""
        ...

class Tilemap:
    """A grid of tile indices into a tileset Bitmap (each frame = one tile).
    Add it to a Scene as a background layer; setting tiles or moving the map
    marks only the affected area dirty."""

    def __init__(self, tileset: Bitmap, cols: int, rows: int) -> None:
        """A map ``cols`` tiles wide by ``rows`` tiles tall (each cell indexes a
        frame of ``tileset``)."""
        ...

    def tile(
        self,
        tx: int,
        ty: int,
        value: Optional[int] = None,
        *,
        flip_x: bool = False,
        flip_y: bool = False,
        transpose: bool = False,
    ) -> Optional[int]:
        """Get the tile at (tx, ty) -> int; with ``value``, set it (and mark dirty) -> None.
        The optional keyword ``flip_x``/``flip_y``/``transpose`` flags orient the tile - together
        they give all 8 orientations (4 rotations x mirror) for free at draw time; use them
        with a deduplicated tileset (png2picogame --dedup REMAP). Out-of-range reads as 0,
        ignores writes."""
        ...

    def move(self, x: int, y: int) -> None:
        """Move the whole map to pixel (x, y)."""
        ...

    def fill(self, value: int) -> None:
        """Set every tile to ``value``."""
        ...
    x: int
    y: int
    """Current pixel position of the map's top-left (read-only; set with move())."""
    cols: int
    rows: int
    """Map size in tiles (read-only)."""

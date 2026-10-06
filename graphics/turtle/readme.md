# Turtle graphics

A turtle interpreter implemented in an OpenType font. GSUB substitutions
track position, heading, pen state, and color; the glyph outlines draw the path.
The browser only supplies text and measures the font's boundary signal.

## Editable document

Open [turtle.odt](turtle.odt) in LibreOffice Writer. It embeds the font and
shows the same editable commands in an ordinary font and as a colorful
drawing. Follow the document's "Try it" instructions to change the path,
pen state, and color directly in the text.

## Commands

Start a program with `b`. The turtle starts in the center of a 21×21 canvas,
facing east, with the pen down.

| Command | Meaning |
| --- | --- |
| `f` | Forward one cell; draw a segment when the pen is down |
| `l` | Turn left 90° |
| `r` | Turn right 90° |
| `u` | Pen up: move without drawing |
| `d` | Pen down: resume drawing |
| `0` | Ink (default) |
| `1` | Red |
| `2` | Blue |
| `3` | Green |
| `4` | Orange |
| `5` | Purple |

Uppercase aliases and spaces work in the font. For example:

```text
bffffl ffffl ffffl ffffl
bfff ufff dfff
b1ffffl 2ffffl 3ffffl 5ffffl
```

Color commands select the pen color for subsequent strokes and the turtle
marker. Previous strokes retain their colors; retracing a segment paints over
it with the new color. Colors persist through turns and pen-up moves. These
digits are commands, not distances: `f2f` draws one step in ink, selects blue,
and draws one blue step. The third example draws a square with four colors.

The filled triangle shows the turtle's heading with the pen down; the hollow
triangle means pen up. A move outside the canvas replaces the turtle with an X
at its last valid position and stops execution. Previous strokes remain.
Turning, raising/lowering the pen, and selecting a color also count toward the
128-command limit.
Commands beyond that limit are left unevaluated and invisible.

## Playground

From the repository root:

```bash
python3 -m http.server 8000
```

Open <http://localhost:8000/graphics/turtle/playground.html>.
Edit the command text, load an example, or append commands using the buttons
and F/L/R/U/D keys (↑ forward, ← left, → right also work outside the editor).
Use the color buttons or 0–5 keys to append a color selection.
Undo removes the last command; Clear / reset starts a blank drawing.
The editor accepts an optional leading `b`, strips whitespace, and rejects
unsupported characters and programs over 128 commands. Invalid text leaves
the last valid drawing visible. Multi-line editor input is flattened into
one shaping run before it reaches the font.

## Build

Requires Python 3.10+ and FontTools:

```bash
python3 -m pip install fonttools
python3 graphics/turtle/build.py
python3 graphics/turtle/build.py --size 15x9 --output /tmp/turtle-15x9.ttf
```

The default output is `turtle-font.ttf` beside the builder, regardless of the
working directory. Custom dimensions default to `turtle-WIDTHxHEIGHT-font.ttf`
beside the builder. Each dimension must be 3–25. Relative `--output` paths
are relative to the current directory. Imports do not build or write files.
The supplied playground expects the bundled 21×21 font; to use a custom
canvas, also update its SVG viewBox, text baseline, and measured board advance
in `turtle-controls.js`.

## How it works

The `b` glyph expands into a frame and the initial turtle state. For each
command, a ligature consumes the current state and command into a temporary
token. A second lookup expands it into a line (when drawing) and a new state.
Turns and pen changes expand to just a new state. Each glyph uses absolute
canvas coordinates; all overlays have zero advance after the frame's advance.
The X has one unit of advance, allowing the playground to detect the boundary
without computing the turtle's position in JavaScript.

There are 128 shaping passes with distinct lookup indices. Small contextual
wrappers reuse the shared rule tables to keep the font and validation work
manageable. The font uses `liga`, with default and Latin script support.
Spaces and strokes are marks ignored by movement rules; no GPOS attachment
is applied to these marks.

A color mark travels immediately after the turtle state. Each pass selects
a color if requested, consumes a command, expands the next state, and paints
any newly emitted stroke using that color. Finished strokes are never recolored.
A final lookup colors the turtle or boundary marker after the 128 passes.
The font embeds a six-color palette in CPAL and uses COLR v0 layers to render
each stroke and marker. TrueType outlines remain as a monochrome fallback in
renderers without color font support. The playground keeps the drawing in one
text run so styling cannot split the computation.

## Tests and limitations

```bash
python3 -m unittest discover -s graphics/turtle -p 'test_*.py' -v
node graphics/turtle/test_turtle_controls.cjs
```

FontTools is required; font-shaping tests additionally require HarfBuzz's
`hb-shape`. Tests check the bundled and newly generated fonts against an
independent interpreter, including custom canvases, random paths, all four
boundaries, pen changes, repeated turns, whitespace, colors, palette tables,
fallback outlines, and the command limit.

This is discrete turtle graphics: quarter turns and single-cell steps, with
no numeric arguments, arbitrary angles, custom RGB colors, loops, or Logo syntax. Repeat
commands to go farther. Shape valid input as one left-to-right text run with
standard ligatures enabled; line breaks or run splitting reset the computation.
Use one `b` at the start. An unknown character interrupts execution. Drawings
use original geometric outlines under Apache License 2.0.

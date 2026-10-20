# Achi: exact play, including draws, inside a font

[Play in your browser](playground.html). This is **Berkeley's three-counter
Achi variant**, with the standard two board diagonals. Each player places
three counters; if neither has won, players slide along a drawn line into an
adjacent empty point. No jumps or captures. Three counters in a straight
horizontal, vertical or diagonal row win during either phase. A player with
no legal move loses. See [Berkeley's rules](https://gamescrafters.berkeley.edu/games.php?game=achi).
Four-counter Achi is a different variant and is not implemented here.

## Playing and notation

Columns A–C run left to right; rows 1–3 run bottom to top. Start with `h` to
play first (solid teal), or `b` for the font to start (you have red rings).
Append only your moves: `A1;` places a counter; `A1A2;` slides from A1 to A2.
Every move ends with a semicolon. Spaces, tabs and line breaks are ignored.
Wrong phases, occupied points, wrong pieces and moves off the drawn lines
are invalid. Other syntax is malformed. Errors keep the valid prefix;
finished games freeze and ignore trailing input.

The font displays PLACE/SLIDE, its latest destination in gold, and the solved
outlook of the position. Drawing cycles have no move cutoff or automatic
repetition adjudication. Append `=` or use **Offer draw** to finish by agreement.
The font declines when it can force a win, and accepts otherwise, including
when accepting improves its forced loss to a draw. `hA1;=` reaches a drawing
position and agrees a draw; `b=` is declined. A declined offer is an invalid
input in editable source; button rejections do not append it to the history.

## Complete solution and implementation

Retrograde analysis finds 5,390 reachable board/turn states: 2,997 wins for
the player to move, 1,185 losses and 1,208 draws, matching
[Berkeley's analysis](https://gamescrafters.berkeley.edu/analysis/gameanalysis.php?game=achi&variant=2).
The opening is a first-player win in nine plies against optimal delaying
defense. The policy takes the fastest forced win, delays a forced loss, and
preserves a draw when it cannot win; equal choices break lexically.

All human continuations against that policy are compiled for both roles.
The shared forward-cursor pipeline has no repeated shaping clock or fixed
turn limit. Native tests repeat a reachable policy cycle 512 times, then
verify both continued play and error detection. Runtime rules, replies,
draw decisions and original geometric artwork all execute in GSUB. The
browser transports text, measures status and stores Undo; it has no board
or strategy model. Only the standard empty-board start is supported.

The bundled font contains 1,475 glyphs, 620 GSUB lookups and 435,264 bytes.
The [Chomp transport protocol](../chomp/readme.md) applies: U+E000/U+E001
framing, ASCII/private-use aliases, one LTR run with `liga`, no kerning or
letter/word spacing. Advance is 1,800 units plus status 1–6, or **7 for an
agreed draw**. Color uses COLRv0; solid counters and rings remain distinct
in monochrome. The browser caps source at 1,024 characters; actual shaping
limits depend on the host.

## Build and verification

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required:

```sh
python3 games/achi/build.py
python3 games/achi/test_font.py -v
node games/achi/test_controls.cjs
python3 -m http.server 8000
```

`--output` selects another destination; importing the builder creates nothing.
An independent bitboard implementation with a separately specified adjacency
table and synchronous fixed-point solver checks the full graph and every
move/outcome. Native HarfBuzz checks every compiled placement, slide, invalid
move, draw decision, malformed input and stopped state. Tests also cover
reachable policy histories, long cycles, terminal tails, Unicode transport,
metrics, disabled ligatures, both roles, Undo/reset, agreed draws, stale
clearing and font-loading failures using real font measurements.

Original implementation, generated policy and artwork; Apache 2.0.

Typography uses smooth, proportional Roboto Regular and Bold outlines from the
[pinned Apache-2.0 sources](../../decoders/shared/fonts/roboto-2/readme.md).
The generated font retains upstream attribution. Text is baked in at build
time; no installed typeface or runtime font download is required.

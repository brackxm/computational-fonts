# Domineering: perfect play in a 4×4 font

[Play in your browser](playground.html). The first player places vertical
dominoes and the second places horizontal dominoes on two neighboring empty
squares. No overlap is allowed. A player with no legal placement loses.
These are the standard [Domineering rules](https://arxiv.org/abs/math/0006066).

Start with `h` to play Vertical first or `b` to play Horizontal after the font's
opening. Append only your placements, such as `hA2V;`. Columns A–D run left to
right, rows 1–4 bottom to top. `V` extends up from its coordinate; `H` extends
right. Every placement ends with a semicolon. Spaces, tabs and line breaks
are insignificant. Wrong orientation, overlaps, and board-edge crossings are
invalid moves; other syntax is malformed. Errors show the valid prefix;
terminal results freeze and ignore trailing input.

Teal dominoes belong to Vertical, red to Horizontal. Their orientation remains
visible in monochrome. A gold outline marks the font's latest placement.
The complete rules, legality checks, automatic replies, status and geometric
artwork run in GSUB. The browser holds input/Undo and reads the font's status.

## Exact solution

The build enumerates 3,120 reachable board/turn states, retaining ownership
for drawing. These collapse to 2,443 strategic occupancy/turn states. Exact
minimax through the shared retrograde solver confirms a first-player win in
seven plies against optimal delaying defense. The policy takes the fastest
forced win, delays a forced loss, and breaks equal ties lexically. Every human
continuation against that policy is compiled for both sides. There is no
runtime search or external strategy database. Only the fixed 4×4 start is
supported; this is a complete solution of that bounded game.

The font uses the shared forward cursor pipeline, with no repeated shaping
clock, and reusable domino components. The [Chomp protocol](../chomp/readme.md)
applies: U+E000/U+E001 framing; ASCII or private-use input aliases; one LTR run
with `liga` enabled; zero letter/word spacing and no kerning. Advance is 1,800
units plus status 1–6. COLRv0 provides color with a monochrome fallback. The
playground caps source at 1,024 characters. Actual host shaping limits apply.

The bundled font contains 798 glyphs, 235 GSUB lookups and 200,916 bytes.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required:

```sh
python3 games/domineering/build.py
python3 games/domineering/test_font.py -v
node games/domineering/test_controls.cjs
python3 -m http.server 8000
```

`--output` chooses another file; importing the builder writes nothing.
An independent occupancy-only solver generates placements with coordinate
sets and checks every legal move, game outcome and terminal distance. Native
HarfBuzz tests cover all compiled legal and illegal placements, malformed input,
every reachable policy state, stopped states, terminal tails, transport, metrics
and disabled ligatures. Controller tests measure the actual font and exercise
both sides, wins/losses, Undo/reset, stale clearing and font-loading failures.

Original rules implementation, generated policy and geometric artwork;
Apache 2.0. No external strategy data is embedded.

Typography uses original, proportional [Game Sans](../shared/fonts/game-sans/readme.md)
Regular and Bold outlines, Copyright 2026 Michael Brackx, Apache 2.0.
Text is baked in at build time; no installed typeface or runtime font download
is required, and no third-party font outlines are used.

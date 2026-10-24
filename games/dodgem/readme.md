# Dodgem: a perfect opponent in a font

[Play in your browser](playground.html). Standard 3×3 Dodgem with a complete
exact opponent on either side. Blue has two horizontal cars and exits east;
Red has two vertical cars and exits north. Blue moves east/north/south, Red
north/east/west, one square into an empty neighbor. Cars cannot capture or
reverse their forward direction. First to get both cars off wins; a player
with no legal move loses. See [Berkeley's rules](https://gamescrafters.berkeley.edu/games.php?game=dodgem).

Columns A–C run left to right; rows 1–3 run bottom to top. Start with `h` to
play Blue first or `b` to let the font play Blue. Append only your moves as
semicolon-terminated coordinates: `hA3B3;`. `C2X;` exits a Blue car at C2;
`B3X;` exits a Red car at B3. All coordinate pairs and origin/exit forms are
syntactically recognized; illegal directions, jumps, occupied destinations,
wrong pieces and wrong-edge exits are invalid moves. Missing semicolons or
unsupported characters are malformed. Spaces, tabs and line breaks are ignored.
Errors keep the valid prefix; terminal games freeze and ignore trailing input.
Gold marks the latest font destination, or the origin of an exiting car.

## Exact solution

The original rules generate 1,963 reachable board/turn states, matching
[Berkeley's published analysis](https://gamescrafters.berkeley.edu/analysis.php).
Retrograde attractor analysis solves cycles without a depth cutoff. A priority
queue processes terminal distances in increasing order, selecting the fastest
forced win or longest forced loss, then breaking ties lexically. Unresolved
cycles would be draws; every reachable standard Dodgem state is decisive.
Blue wins with perfect play, in 19 plies against optimal delaying defense.

The shared `../shared/exactgame.py` compiler emits every human continuation
against that deterministic policy for both sides. It uses forward-reading
GSUB cursors, removes old cursors and last-move marks afterward, and has no
fixed shaping clock. The browser contains no board or strategy model. Artwork
uses original reusable car components, distinguishable in monochrome too.
Only the standard initial position is supported. The bundled font contains
1,247 glyphs, 357 GSUB lookups and 405,392 bytes.

## Protocol, build and verification

The font uses the same [transport and status protocol as Chomp](../chomp/readme.md):
U+E000/U+E001 framing, ASCII or private-use aliases, one LTR run with `liga`
enabled, and 1,800 units plus status 1–6. A reserved draw status is 7; it is
unreachable in standard Dodgem. Colors use COLRv0. The browser caps source at
1,024 characters; the font has no turn counter. Host shaping limits still apply.

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required:

```sh
python3 games/dodgem/build.py
python3 games/dodgem/test_font.py -v
node games/dodgem/test_controls.cjs
python3 -m http.server 8000
```

`--output` selects another destination; importing the builder writes nothing.
The tests independently enumerate bitboard rules and solve their graph with
synchronous fixed-point updates. They compare every reachable move/outcome,
check remoteness recurrences, exercise synthetic drawing/winning cycles,
and shape every compiled move, error state and terminal state through native
HarfBuzz using temporary test-only aliases. Reachable policy histories, long
cycles where present, malformed input, Unicode, metrics, disabled ligatures,
Undo/reset, terminal freezing and font/controller failures are covered.

Original implementation, strategy data and artwork; Apache 2.0. No external strategy table is embedded.

Typography uses original, proportional [Game Sans](../shared/fonts/game-sans/readme.md)
Regular and Bold outlines, Copyright 2026 Michael Brackx, Apache 2.0.
Text is baked in at build time; no installed typeface or runtime font download
is required, and no third-party font outlines are used.

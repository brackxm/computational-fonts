# Sim: a perfect opponent inside a font

[Play in your browser](playground.html). This is the complete six-dot game
[documented by Berkeley GamesCrafters](https://gamescrafters.berkeley.edu/games.php?game=sim).
Players alternate colouring one unused connection between two dots. The player
who completes a triangle in their own colour loses immediately. A triangle
must use three of the six original dots; crossings do not create new vertices.

## Playing and notation

Dots A–F run clockwise from the top. Start with `h` to play first (solid teal
edges), or `b` for the font to start (you have red double edges). Append only
your edges, in alphabetical order, ending in semicolons: `hAB;CD;`. The font
inserts its own replies. Spaces, tabs and line breaks are ignored. An occupied
edge is invalid; a reversed edge, unknown vertex, missing semicolon or other
syntax is malformed. Errors preserve the valid board prefix. Finished games
freeze and ignore all trailing input. Undo removes your previous submission.

The font plays perfectly on either side. Second can force a win from the
empty board; as First, the font exploits any mistake that changes the solved
outcome. Among moves with the same win/loss outcome it chooses the earliest
edge alphabetically. It does not optimize the number of moves until a loss.
Solid and double edges distinguish the sides in monochrome, too.

Examples against the bundled policy:

- `hEF;DF;DE;` — you complete a triangle and the font wins.
- `bEF;DF;CE;AF;` — you win as Second.
- `hAB;AB;` — occupied edge; retains the board after the first exchange.

## Independent exact solution

`solver.cpp` recursively solves the entire reachable game without symmetry
reduction or pruning. Each board is a fifteen-digit ternary integer: empty,
First, or Second for each of AB, AC, …, EF. Its temporary 3^15-byte signed
table records win/loss and minimax remoteness; zero marks unreachable boards.
The solver finds **2,230,702 reachable board/turn states**, including terminal
positions. The root is a Second win with a minimax remoteness of fifteen plies.

`verify.cpp` is an independent bottom-up oracle. It enumerates all 3^15 boards,
uses a vertex adjacency matrix to detect triangles, checks turn counts and
whether a terminal triangle could have been formed by the last move, and
recomputes every result and remoteness in reverse numeric order. It compares
every table byte, including unreachable slots. Neither program imports a
third-party strategy or database.

`policy.py` extracts both human-role closures: every possible human move and
one outcome-preserving font reply at each font turn. There are 15,054 playable
human-turn states (11,733 when you start; 3,321 when the font starts). Font-only
intermediate states remain build-time data. Runtime strategy and legality
are compiled into GSUB; no solver or policy file is loaded by the playground.

## Font execution and transport

The font tokenizes edges, detects invalid input, applies the selected reply,
ends games and draws the board. The browser transports text, measures the
font's status and stores Undo; it has no board or strategy model.

One setup pass and eight human-move passes suffice: a game has at most fifteen
plies, so First can submit at most eight edges and Second at most seven.
Each pass first marks errors, then ligates the board cursor and one legal
human token into the board after the font's reply. A final error/freeze pass
removes terminal tails. Error marks preserve the current board without
allocating a separate error-board glyph for every state.

`layout.py` groups identical error-rule memberships into bounded class-context
subtables and explicitly wraps GSUB lookups in extension tables. Binary
readback tests verify the resulting packed table. The font contains 44,521
glyphs and 120 lookups, and is approximately 8.2 MiB.

The [Chomp transport protocol](../chomp/readme.md) applies: U+E000/U+E001
framing, ASCII/private-use aliases, one LTR run with `liga`, and zero kerning
or letter/word spacing. Total advance is 1,800 units plus status 1–6. The
playground caps source at 1,024 characters; host shaping limits still apply.
Only the standard six-dot empty start is supported.

Colour uses **COLRv1**, because the complete board layers exceed COLRv0's
16-bit layer-index limit. Browsers/applications with COLRv1 support display
teal and red. Equivalent TrueType composite outlines provide a monochrome
fallback with solid/double edges. Original Game Sans Regular/Bold text is
baked into the font; no installed font or third-party font outlines are used.

## Build and verification

Python 3.11+, the pinned FontTools/uharfbuzz versions, a C++17 compiler named `c++`,
native HarfBuzz/`hb-shape`, and Node.js are required. Build from the repository:

```sh
python3 -m venv games/sim/.venv
. games/sim/.venv/bin/activate
python -m pip install -r games/sim/requirements.txt
python games/sim/build.py
python games/sim/test_font.py -v
node games/sim/test_controls.cjs
python -m http.server 8000
```

`--output` selects another destination. Importing the builder creates nothing.
Keep these dependencies in the isolated environment above: other projects may
need a newer FontTools version. Run `deactivate` when finished.
The FontTools pin avoids quadratic compilation of large ligature tables in
newer generic substitution builders. uharfbuzz repacks the large GSUB table
within OpenType's offset limits.
The solver executable and table are generated in a temporary directory and
removed after use; the bundled TTF is self-contained.

Tests independently verify the whole solved table, read back every compiled
legal edge and occupied-edge/syntax rejection from the binary font, and shape
complete games through native HarfBuzz on both sides. They also check all
openings, Unicode and malformed transport, stopped-game tails, maximum-length
games, metrics, disabled ligatures and original typography. Controller tests
measure the actual font for both roles, wins/losses, rejected moves, Undo,
reset, stale clearing and loading failures.

Original implementation, independently generated policy and geometric artwork.
Copyright 2026 Michael Brackx; Apache 2.0. Typography uses original
[Game Sans](../shared/fonts/game-sans/readme.md), also Apache 2.0.

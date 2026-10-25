# Dots and Boxes: perfect scoring inside a font

[Play in your browser](playground.html). This is the complete **2×2-box game**
on a 3×3 dot grid. Draw an undrawn edge between adjacent dots. Completing a
box claims it and earns another turn; completing two boxes claims both and
still earns another turn. Play continues until all twelve edges are drawn.
The player with more boxes wins; 2–2 is a draw.

## Playing and notation

Columns A–C run left to right, rows 1–3 bottom to top. Start with `h` to move
first or `b` for the font to start. Append only your edges: `A1H;` extends
right from A1; `B2V;` extends up from B2. Each edge ends with a semicolon.
Spaces, tabs and line breaks are ignored. Occupied edges and edges extending
beyond the dot grid are invalid; other syntax is malformed. Errors retain
the valid prefix; terminal results freeze and ignore trailing input.

After completing a box, submit your next edge yourself. When it is the font's
turn, it automatically plays all of its own bonus edges before returning
control. A solid teal disk marks a first-player box; a red ring marks a
second-player box. First and Second show the scores. Gold marks only the
font's latest edge, and stays on that edge while the human takes bonus turns.

## Exact solution and font execution

There are 5,559 reachable edge/ownership/turn states: 3,123 wins for the player
to move, 869 losses and 1,567 draws, matching
[Berkeley's analysis](https://gamescrafters.berkeley.edu/analysis.php).
The first player wins 3–1 with perfect play. An exact score minimax maximizes
the final first-player box margin on first-player turns and minimizes it on
second-player turns. This preserves bonus turns and scores, and optimizes
the number of boxes as well as the win/draw/loss result. Equal choices break
lexically. A separate retrograde solver verifies the win/draw/loss policy.

Both roles and every human continuation against the selected policy are
compiled into GSUB. The font handles legality, scoring, box ownership, bonus
turn chains, opponent replies, end detection and original geometric artwork.
The browser transports text, measures status and stores Undo; it has no
board, score or strategy model. Only the fixed 2×2-box game is supported.

The shared forward-cursor compiler has no repeated shaping clock or runtime
search. The bundled font contains 1,503 glyphs, 574 GSUB lookups and 399,576
bytes. The [Chomp transport protocol](../chomp/readme.md) applies: U+E000/U+E001
framing, ASCII/private-use aliases, one LTR run with `liga`, and zero kerning
or letter/word spacing. Advance is 1,800 units plus status 1–6, or **7 for a
terminal 2–2 draw**. Color uses COLRv0, with distinct monochrome box markers.
The browser caps source at 1,024 characters; actual host shaping limits apply.

## Build and verification

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required:

```sh
python3 games/dots-and-boxes/build.py
python3 games/dots-and-boxes/test_font.py -v
node games/dots-and-boxes/test_controls.cjs
python3 -m http.server 8000
```

`--output` selects another destination; importing the builder writes nothing.
Independent tests represent edges geometrically and compute future score
advantage without an ownership/turn table. They check every reachable move,
score-optimal choice, owner assignment, bonus turn, double-box capture and
game outcome. Native HarfBuzz tests check every compiled legal/illegal edge,
malformed input and stopped state, together with reachable policy histories,
human bonus turns, automatic font chains, terminal tails, Unicode, metrics
and disabled ligatures. Controller tests measure the real font for both roles,
wins/losses/draws, Undo/reset, stale clearing and font-loading failures.

Original implementation, generated policies and artwork; Apache 2.0.

Typography uses original, proportional [Game Sans](../shared/fonts/game-sans/readme.md)
Regular and Bold outlines, Copyright 2026 Michael Brackx, Apache 2.0.
Text is baked in at build time; no installed typeface or runtime font download
is required, and no third-party font outlines are used.

# Hexapawn: a perfect opponent inside a font

[Play in your browser](playground.html). Complete **3×3 Hexapawn**, with the font
playing perfectly as either color. White moves first. **Black has a forced win**
from the standard starting position, so the default puts the font second.
Choose “Font first” to play Black and try to win against its best defense.

White pawns are outlined, start on rank 1, and move up. Black pawns are solid
teal, start on rank 3, and move down. A pawn advances one square into an empty
square, or captures an enemy pawn one square diagonally forward. Captures are
optional. No double steps, en passant, or other chess moves are included.

Win by reaching the opposite back rank, capturing every enemy pawn, or leaving
the opponent with no legal moves. Reaching the far rank ends the game; the pawn
does not turn into a queen. Draws are impossible. These rules follow
[Gardner’s original description](https://www.cs.williams.edu/~freund/cs136-073/GardnerHexapawn.pdf)
and the [UW–Madison activity](https://education.mrsec.wisc.edu/hexapawn/).

## Notation

Start with `h` to play White, or `b` to let the font play White. Append **only
your own moves**, using uppercase source/destination coordinates:

```text
h
hB1B2
hB1B2C1B2A1A2
bA3B2C3C2C2C1
```

The third example is a font win against optimal White resistance. The fourth
is a human Black win against optimal White defense. The font inserts its own
replies. Columns are A–C from left to right, ranks 1–3 from bottom to top.
For example, `C1B2` is a diagonal capture, provided B2 contains an enemy pawn.

ASCII spaces, tabs, and line breaks are ignored, including inside coordinates.
Moves with canonical coordinates but illegal geometry, occupation, or ownership
are invalid. Lowercase coordinates, out-of-domain coordinates, incomplete moves,
and other characters are malformed. Errors leave the board at the valid prefix.
Terminal games freeze and ignore trailing input.

The gold box and label identify the font’s latest move. The board also states
which color you control and who can force a win. Undo restores the previous
text. The playground accepts at most **512 source characters** and submits
candidate moves to the font before appending them. Static form defaults are
examples; JavaScript does not generate legal moves or choose replies.

## Complete exact solution

The generator enumerates all **135 reachable states**, including **70
nonterminal states**, without symmetry reduction. Each state contains the
complete board and side to move. A memoized minimax solver computes the outcome
and distance to termination. The AI takes the fastest forced win, delays a
forced loss as long as possible, and breaks ties alphabetically by coordinates.
White’s initial value is a loss in **six individual moves** under optimal play.

The game graph is acyclic: the sum of every remaining pawn’s distance from its
promotion rank decreases on every move, and captures can only reduce it further.
No heuristic evaluation, learning, runtime search, external engine, or imported
strategy data is used. An independent bitboard solver verifies the complete
graph, every legal move, every value, and every remoteness.

The bundled TTF contains **968 glyphs, 95 GSUB lookups, and 147,856 bytes**.
Seven direct feature stages remove spaces, tokenize four-character moves,
initialize the cursor, run the exact transition policy, finalize the explicit
end sentinel, and delete old move/board cursors. The forward cursor architecture
needs no repeated shaping clock. Old boards never accumulate in the output.
Pawn shapes, colored layers, role labels, and highlights are inside the font.

## Font protocol

Frame source with U+E000 / U+E001. The browser maps printable ASCII to U+E100
plus its code so the program remains in one left-to-right run. Unsupported
Unicode and reserved transport characters become a DEL rejection token.
Direct ASCII is also mapped for command-line experiments:

```bash
hb-shape games/hexapawn/hexapawn-font.ttf --text=$'\ue000hB1B2\ue001'
```

Enable `liga`, with zero letter/word spacing and no kerning. The frame advances
1,800 units; exactly one final status adds the following extra advance:

| Extra advance | Meaning |
| --- | --- |
| 1 | Human’s turn |
| 2 | Font wins |
| 3 | Human wins |
| 4 | Illegal move |
| 5 | Malformed source |
| 6 | Reserved internal error |

The browser probes at 1,000 px, making one font unit one CSS pixel. It verifies
actual shaping support before enabling play and clears stale results as soon
as editing begins. Color uses COLRv0 with five palette entries; outlined White
and solid Black pawns also remain distinct in monochrome. Splitting the program
across runs or disabling standard ligatures prevents it from running.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz / `hb-shape`, and Node.js are used:

```bash
python3 -m pip install fonttools
python3 games/hexapawn/build.py
python3 games/hexapawn/test_font.py -v
node games/hexapawn/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/hexapawn/playground.html>. The builder defaults
to the font beside its source regardless of the current directory. `--output`
selects another file. Imports write no files.

Verification compares the graph against the independent solver, tests **every
one of the 81 coordinate-pair actions in each compiled active state**, and
checks every stopped cursor with trailing source. Temporary test-only cmap
aliases are absent from the shipped font. Tests also explore every human game
against the fixed AI from both sides, malformed/illegal inputs, capture and
promotion behavior, disabled ligatures, metrics, palette, and metadata.
Controller tests use the real font for both terminal outcomes, rejected moves,
side changes, Undo, editing, input limits, and failed font loading. Browser
checks cover pawn art, capture, side selection, and form defaults.

Shared drawing helpers replace duplicated geometry. Rebuilding both this font
and Mū tōrere after that refactor preserves every non-timestamp font table.
The shared forward pipeline also supports the move-token preprocessor used
here. See [`../shared/`](../shared/).

All code, generated policy, pawn silhouettes, and geometric
artwork are original and licensed under Apache 2.0. No external strategy table is embedded.

Titles, coordinates, and status labels use original, proportional
[Game Sans](../shared/fonts/game-sans/readme.md) Regular and Bold outlines, baked
into the font by [`game_text.py`](../shared/game_text.py). The lettering is
Copyright 2026 Michael Brackx, Apache 2.0; no third-party font outlines are used.

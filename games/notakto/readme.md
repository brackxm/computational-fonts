# Notakto: a perfect opponent inside a font

[Play in your browser](playground.html). The bundled font plays first on three
3×3 boards, checks your moves, chooses exact winning replies, and draws all
three boards through OpenType substitutions. JavaScript transports your input
and reads a small advance-width status signal; it contains no game model.

Both players place **X**. A row, column, or diagonal of three closes that board.
Closed boards cannot be played on. **Whoever closes the last board loses.**
The opening position is a first-player win, and the font preserves that win
against every legal human continuation. Undo lets you explore alternatives.

## Input

Start with `b`, then append **only your own moves**. Use a board letter A–C and
a square 1–9, numbered left to right, top to bottom:

```text
b          # The font opens at A1.
bA2        # You play A2; the font replies at A3 and closes board A.
bA2B9      # You then play B9; the font replies at B2.
```

The comments above explain the examples; comments themselves are not input.
ASCII spaces, tabs, and line breaks are ignored. Lowercase board names,
coordinates outside the board, incomplete moves, and other characters are
malformed. Occupied squares and closed boards are invalid. A terminal result
freezes the game and ignores any trailing input. Error displays show the valid
prefix of the history, with the error printed inside the font.

The latest font move has a gold outline. All Xs have the same meaning;
Notakto has no player-owned pieces.

## Exact strategy and size

`model.py` generates the strategy from the rules, without an imported book or
third-party strategy data. Each of the 512 board masks is reduced by the eight
square symmetries; all closed boards are equivalent. This leaves 47 single-board
states. Backward induction solves all **18,424 multisets of three states**.
The all-closed position is winning for the player about to move because their
opponent just lost by making the final move.

Comparing each board against every possible two-board context derives **eight
single-board classes for this fixed three-board game**. The generator checks
that replacing all three boards by their class representatives preserves every
outcome. This is a bounded compression, not the general misère quotient for an
arbitrary number of boards. Each AI choice depends on one exact board mask and
the other two boards' classes. It chooses the first legal move leaving a losing
position, in board/square order. From the standard opening it always has one.

The bundled TTF has **1,752 glyphs, 495 GSUB lookups, and 964,500 bytes**.
It stores three individual board registers rather than a glyph for each whole
game position. Fifteen shaping passes cover the conservative 27-ply bound,
including the opening move and explicit end-of-input validation. There is no
search, network access, randomness, or external engine during play.

## Font protocol

The browser wraps the source in U+E000 / U+E001 sentinels. Each printable ASCII
character is mapped to U+E100 plus its ASCII code, keeping the entire program
in one left-to-right shaping run. Unsupported Unicode and reserved transport
characters become the DEL rejection token. ASCII also has direct cmap entries
for command-line experiments:

```bash
hb-shape notakto-font.ttf --text=$'\ue000bA2B9\ue001'
```

Enable `liga`; use a single run with zero letter/word spacing and no kerning.
The frame advances 1,800 font units. The final status advances 1–6 units:

| Extra advance | Result |
| --- | --- |
| 1 | Your turn |
| 2 | Font wins |
| 3 | Human wins (unreachable with valid play against this strategy) |
| 4 | Invalid move |
| 5 | Malformed history |
| 6 | Strategy failure (unreachable with valid play) |

Only accept a result with exactly one final status. At the playground's probe
size of 1,000 px, one font unit is one CSS pixel. The playground caps editable
input at 256 characters, clears stale results immediately when you edit, and
checks actual shaping support before enabling play. Color uses COLRv0; engines
without color support can still draw the monochrome outlines. Applications
which split the program across runs or disable standard ligatures cannot play.

## Build and verify

Python 3.10+, FontTools, and a system HarfBuzz library / `hb-shape` are needed:

```bash
python3 -m pip install fonttools
python3 games/notakto/build.py
python3 games/notakto/test_font.py -v
node games/notakto/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/notakto/playground.html>. The builder defaults
to the font beside its source, independent of the current directory; use
`--output /path/to/font.ttf` to select another destination. Importing it does
not generate a font.

Tests compare all 18,424 reduced positions with an independent string-board
solver, prove every winning position has a legal reply to a losing position,
check all 400,061 reachable positions against every human continuation, and
exercise every compiled decision context through native HarfBuzz. They also
shape 300 complete seeded games, check input errors and terminal freezing, and
exercise the browser controller against the real font.
Manual browser verification covers the rendered boards, controls, and layout.

All generator code, strategy data, lettering, and board artwork are original
and licensed under Apache 2.0. No external artwork or published strategy table
is embedded.

# Tic-tac-toe: a perfect opponent inside a font

[Play in your browser](playground.html). Standard 3×3 tic-tac-toe with X moving
first. Make three marks in a row, column, or diagonal. Choose either side; the
font supplies every opponent move and never loses from the standard start.
A full board without a winning line is a draw.

The board, exact outcome hint, latest-move outline, move validation, and perfect
opponent all run through OpenType GSUB. JavaScript transports text, manages Undo,
and measures a status signal. It contains no board model or strategy.

## Input

Squares are numbered left to right, top to bottom:

```text
1 2 3
4 5 6
7 8 9
```

Start with `h` to play X first, or `b` to let the font play X while you play O.
Append **only your square numbers**. The font inserts its replies automatically.

| Source | Result |
| --- | --- |
| `h` | Empty board; you play X |
| `b` | Font plays X in the centre; you play O |
| `h124` | Font wins as O |
| `h12768` | Draw, with you as X |
| `b1762` | Draw, with you as O |
| `h11` | Occupied-square error; the first move and reply remain visible |

ASCII spaces, tabs, and line breaks are ignored. Other characters are malformed.
An invalid or malformed history displays its valid prefix. Finished games freeze
and ignore trailing input. The playground accepts 512 source characters and
clears stale output immediately when you edit. Buttons append a move only after
the font accepts it. Desktop buttons and the compact square selector send the
same text.

## Complete solution, small policy

The builder solves all **5,478 legal positions** by exact acyclic minimax. Of
these, 4,520 are nonterminal; 626 end in an X win, 316 in an O win, and 16 are
full-board draws. The empty board is a draw with perfect play.

The opponent chooses a forced win when one exists, otherwise preserves a draw.
It finishes wins quickly and delays forced losses; remaining ties use centre,
corners, then edges. From the standard start it never reaches a position where
a human can force a win. A hint on active boards distinguishes a draw from a
forced font win.

A fixed perfect opponent needs only the positions reachable against its own
policy. Starting from **both** first-player choices, the builder follows every
legal human move and the exact opponent reply. This leaves **121 human-turn
positions and 295 displayed boards**, including terminal results. No human
branch is omitted. This is a complete opponent for the standard game, rather
than an arbitrary-position analysis font.

## Font implementation

The bundled TTF contains **1,000 glyphs, 202 GSUB lookups, and 149,996 bytes**.
It uses a forward cursor: each input square produces the next board and a reply
marker. Later lookups preserve the latest cursor and marker. No runtime search,
external strategy file, fixed replay clock, or host-side opponent is required.

X and O artwork is reused across positions. Colored layers and the monochrome
fallback share the same positioned components. The simplify pass removed
redundant whole-board glyphs and shared repeated mark arrangements, reducing
the font from 179,576 to 149,996 bytes without changing the policy.

Frame input with U+E000 / U+E001. Browser transport maps printable ASCII to
U+E100 plus its ASCII value so that the whole program stays in one left-to-right
shaping run. Unsupported Unicode and reserved transport characters become a
DEL rejection token. Direct ASCII also works for command-line experiments:

```bash
hb-shape games/tic-tac-toe/tic-tac-toe-font.ttf --text=$'\ue000h12768\ue001'
```

Enable `liga`, use zero letter/word spacing, and disable kerning. The frame
advances 1,800 font units, plus exactly one status advance:

| Extra advance | Meaning |
| --- | --- |
| 1 | Human turn |
| 2 | Font wins |
| 3 | Human wins; reserved for completeness, unreachable against this policy |
| 4 | Occupied square |
| 5 | Malformed input |
| 6 | Internal error, reserved |
| 7 | Draw |

At the playground’s 1,000 px probe size, one unit is one CSS pixel. The controller
checks actual shaping before enabling play. COLRv0 supplies colors; ordinary
outlines provide a monochrome fallback. Hosts that split the source into runs
or disable standard ligatures cannot execute the game.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz / `hb-shape`, and Node.js are needed:

```bash
python3 -m pip install fonttools
python3 games/tic-tac-toe/build.py
python3 games/tic-tac-toe/test_font.py -v
node games/tic-tac-toe/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/tic-tac-toe/playground.html>. The builder defaults
to the font beside its source; `--output` selects another path. Imports write no
files.

An independent bitboard solver checks legal moves, terminals, minimax values,
and distances for all 5,478 positions. A separate closure check proves that
every legal human response is retained by the compiled policy. Native HarfBuzz
tests every ASCII input at every active cursor, every stopped cursor, latest
reply preservation, and all **969 history prefixes / 613 completed human games**
across both sides. Additional checks cover automatic draws, malformed and
occupied inputs, terminal freezing, disabled ligatures, font metadata, and
status advances. Controller tests use real HarfBuzz measurements for buttons,
the compact selector, side changes, Undo, input limits, stale output, and failed
font loading. Browser checks cover the board artwork, a perfect reply, a complete
draw, and disabled terminal controls.

All code, generated policy, pixel lettering, and mark artwork are original and
licensed under Apache 2.0. Shared helpers are in `../shared/`.

# Chomp: a perfect opponent in a font

[Play in your browser](playground.html). The complete 6-column, 5-row game
is solved at build time, with a perfect opponent on either side. All move
validation, automatic replies, end detection and artwork run in OpenType GSUB.
The browser transports text, measures the font's status, and maintains Undo.

Choose a remaining square and eat it along with all squares above and to its
right. A1, at the bottom left, is poisoned. It cannot be selected; being left
with only A1 loses. These are [Berkeley's Chomp rules](https://gamescrafters.berkeley.edu/games.php?game=chomp).

Start with `h` to move first or `b` for the font to move first. Append only
your bites, ending every coordinate with a semicolon: `hC3;`. Uppercase A–F
and rows 1–5 are required. Spaces, tabs and line breaks are ignored. A1 and
already eaten squares are invalid moves. Missing semicolons or other input
are malformed. An error retains the valid replay prefix; a finished game
freezes and ignores trailing input. The gold outline marks the font's latest
bite. The poisoned square has a cut-out X in monochrome too.

## Solution and implementation

Nonincreasing row lengths describe the remaining chocolate. There are
461 nonempty shapes and 920 reachable shape/turn states from the initial bar.
Exact minimax solves every state, selecting the fastest forced win or delaying
a forced loss, then breaking ties lexically. First player wins with perfect
play. The font compiles all human continuations against one fixed perfect
policy for each side, rather than storing every possible two-player history.

The shared `../shared/exactgame.py` compiler uses reusable geometric glyphs,
tokenizes semicolon-terminated coordinates, and executes one forward cursor
pass. Old cursors and last-move marks are deleted afterward. There is no runtime
search, JavaScript board model or repeated shaping clock. This release is a
fixed 6×5 game; other bar sizes and arbitrary setup positions are unsupported.

The bundled font has 405 glyphs, 100 GSUB lookups and 105,832 bytes.
Frame source with U+E000/U+E001. Printable ASCII also has U+E100+ASCII aliases
to keep browser input in one LTR run. Unsupported characters become DEL.
Enable `liga`, with zero letter/word spacing and no kerning. The board advances
1,800 font units, plus exactly one status: 1 your turn, 2 font wins, 3 you win,
4 invalid move, 5 malformed input, 6 reserved internal error. Colors use COLRv0,
with monochrome outlines. Hosts that split shaping runs or disable ligatures
cannot execute the game. The playground limits source to 1,024 characters.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz/`hb-shape`, and Node.js are required.

```sh
python3 -m pip install fonttools
python3 games/chomp/build.py
python3 games/chomp/test_font.py -v
node games/chomp/test_controls.cjs
python3 -m http.server 8000
```

The builder writes beside its source by default; `--output` chooses another
path. Importing it creates no artifacts. Tests independently represent chocolate
as a bitboard, compare every legal move and minimax result, and inject test-only
cursor aliases into a temporary font to check every compiled legal/illegal bite
through native HarfBuzz. Reachable policy histories, malformed input, Unicode
transport, frozen errors/results, metrics, disabled ligatures, font failures,
Undo/reset and the controller's actual font measurements are covered.

Original implementation and board artwork; Apache 2.0. Text uses smooth,
proportional Roboto Regular and Bold outlines from the repository’s
[pinned Apache-2.0 sources](../../decoders/shared/fonts/roboto-2/readme.md),
with upstream attribution retained in the generated font. The outlines are
baked in at build time; no installed font or runtime fetch is needed. No
external strategy table is embedded.

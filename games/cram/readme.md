# Cram: a perfect opponent in a 135 KB font

[Play in your browser](playground.html). This is complete normal-play **6×5
Cram** from the empty board, with the font as first player. Both players can
place a horizontal or vertical domino on two empty neighboring squares.
**The player with no legal placement loses.** The font has a forced win.

The rules, occupancy checks, automatic replies, endgame detection, and artwork
are implemented through OpenType GSUB. JavaScript passes source text, stores
edits for Undo, and reads the font’s status. It contains no board model.

## Play and notation

Start with `b`. The font opens at **C3H**, covering C3 and D3. Append only your
own placements, without separators:

```text
b
bA1H
bA1HB2V
bE5HC5HD4HB4VA3V
```

Columns are A–F. Rows are 1–5 from top to bottom. `A1H` covers A1 and B1;
`B2V` covers B2 and B3. A horizontal domino extends right from its start square;
a vertical domino extends down. The last example ends with a font win and
**eight isolated empty squares**, demonstrating that play need not fill the
board.

ASCII spaces, tabs, and line breaks are insignificant. Lowercase coordinates,
incomplete moves, punctuation, and other characters are malformed. A placement
overlapping any existing tile or crossing the board edge is invalid and
changes no cells. A terminal game freezes and ignores trailing input. Error
displays show a partial replay of the valid prefix.

Teal tiles belong to the font and red tiles to the human. These colors simply
show move history; both players have the same legal placements. The gold box
and label identify the last font reply. Undo restores the previous source.
The playground caps editable input at 256 characters and rejects button moves
without adding them to history if the font reports an error.

## Why the opponent is perfect

After taking the two central squares, the font responds to each human domino
with its **180° rotation**. After each reply the occupied set is rotationally
symmetric. If a human move is legal, the rotated cells are also free. The only
domino fixed by this rotation is the central opening, which is already
occupied. The human domino and its rotated partner are therefore disjoint.
Thus the font always has a legal reply, and necessarily makes the last move.

This standard even-by-odd strategy is described in
[Demaine and Hearn’s survey](https://erikdemaine.org/papers/AlgGameTheoryDraft/paper.pdf).
The implementation generates the mirror map directly from board coordinates;
it imports no strategy table. This release supports the fixed 6×5 starting
game, rather than arbitrary setups, other dimensions, or misère play.

Each cell is an independent glyph register, holding empty or one of eight
colored domino-half shapes. The font retains all 30 cell slots in a fixed
order. One validation lookup checks a placement before any cells change;
another phase writes both halves. The font then mirrors, validates, and draws
its own reply. An endgame lookup tests **all 49 adjacent pairs** for a remaining
legal placement, including boards with isolated holes.

The bundled font contains **528 glyphs, 166 GSUB lookups, and 135,496 bytes**.
There is no search or full-board state table. Nine shaping passes cover the
opening and at most seven human turns, including explicit end validation.

## Font protocol

The host frames source with U+E000 / U+E001. For a single left-to-right shaping
run, the browser maps printable ASCII to U+E100 plus the ASCII code. Unsupported
Unicode and reserved transport characters become a DEL rejection token.
Direct ASCII is also mapped for command-line experiments:

```bash
hb-shape games/cram/cram-font.ttf --text=$'\ue000bA1HB2V\ue001'
```

Enable `liga`, zero letter/word spacing, and no kerning. The frame advances
1,800 font units and exactly one final status adds the following advance:

| Extra advance | Meaning |
| --- | --- |
| 1 | Human’s turn |
| 2 | Font wins: no legal placement remains |
| 3 | Reserved human-win signal (unreachable in this game) |
| 4 | Overlap or placement crossing the board edge |
| 5 | Malformed input |
| 6 | Internal mirror failure (unreachable with valid play) |

The playground measures at 1,000 px, making a font unit one CSS pixel, and
checks shaping support before enabling play. It clears stale results as soon
as the source is edited. Colors use COLRv0; monochrome outlines also render.
Hosts that split the program across runs or disable standard ligatures cannot
run the game.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz / `hb-shape`, and Node.js are needed:

```bash
python3 -m pip install fonttools
python3 games/cram/build.py
python3 games/cram/test_font.py -v
node games/cram/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/cram/playground.html>. The builder defaults to
the font beside its source, independent of the current directory. Use
`--output` for another destination. Importing the builder writes no files.

The independent coordinate proof checks every legal reply on all **16,384
symmetric occupancy sets containing the central domino**. Native font tests
visit all **2,104 reachable occupancies and 20,392 legal human continuations**,
including all 89 terminal occupancies, all boundary placements, occupied-cell
errors, the maximum seven-turn human history, and terminal freezing. Tests also
check advances, metadata, and disabled ligatures. Controller integration uses
real font measurements for legal/illegal moves, terminal games, Undo, editing,
input limits, and failed font loading. Browser verification covers tile shapes,
placement controls, colors, and highlighting. Rebuilt tables match apart from
timestamp fields.

Shared construction, transport, and test helpers are in `../shared/`. All game
code, strategy data, pixel lettering, and artwork are original, Apache 2.0.

# Gardner minichess: a playable opponent inside a font

[Play in your browser](playground.html). Play Black on the standard **5×5
Gardner board**; the font plays White. The opponent uses an **8,192-position
opening book**, then generates legal replies with a capture-and-safety
heuristic. **It is not perfect and can be beaten.** Leaving the book does not
stop the game.

An optional [certified-corpus research variant](research/readme.md) can be built
locally from its separately preserved inputs. Its
[research playground](research/playground.html) requires that local build.
It remains incomplete and stops at
two unproved openings. This lightweight font remains the default.

All board updates, move legality, opponent choices, terminal detection, and
artwork run in OpenType GSUB. JavaScript edits the history, transports text,
and reads the font's status; it contains no chess rules or move selection.

## Play and rules

White starts `RNBQK` on A1–E1, with pawns on rank 2. Black starts `rnbqk` on
A5–E5, with pawns on rank 4. White moves toward rank 5; Black toward rank 1.
Kings, queens, rooks, bishops, and knights move as in chess. Pawns advance one
square into an empty square and capture diagonally. Promotion is mandatory on
the far rank. There is no castling, en passant, or initial double pawn step.
Moves that leave the moving side's king in check are rejected.

Checkmate wins; stalemate draws. Draw handling is simplified: the font detects
bare kings, king plus one bishop or knight, bishops confined to one square
color, and **150 consecutive individual moves** without a pawn move or capture.
Checkmate takes precedence over that automatic draw. Repetition draws,
fifty-move claims, and more complicated dead positions are not implemented.
Repetitions can continue until the quiet-move counter ends the game.

White pieces are outlined; Black pieces are solid teal. The gold frame marks
the destination of White's latest move. Undo restores the previous history.
The browser accepts **2,048 source characters**; this is a history limit,
not a fixed depth for the opponent's strategy.

## Notation

Start with `b`. Append **only Black's moves**, in uppercase coordinates followed
by a semicolon:

```text
b
bB4A3;
bB4A3;C4C3;
```

The font inserts White's replies. A promotion adds `Q`, `R`, `B`, or `N`, for
example `C2C1N;` when that move is legal. Omission or an inappropriate promotion
is illegal. Spaces, tabs, and line breaks are ignored, even inside a move.
Lowercase coordinates, incomplete moves, other coordinates, and unsupported
characters are malformed. An error preserves the valid board prefix and
removes its last-move marker. Finished games ignore trailing input.

## Opponent and limits

The opening book was generated breadth first: choose one White engine move,
then consider every legal Black response. Searches request **50,000 nodes per
position**, with **500,000 at the root**, one thread, and a 64 MiB hash table.
Every stored move is checked against the original Python rules before it is
compiled. The engine is used only when regenerating the book.

Outside the book, the font first tries moves whose destination is not attacked.
Within that pass it prefers captures of queens, rooks, bishops, knights, and
pawns, then quiet moves. Promotion, developing pawns/minor pieces, central
squares, and advancement break ties, followed by coordinates. If every move
lands on an attacked square, it repeats the ordering while allowing those
moves. Every candidate must still leave White's king safe. The fallback
promotes to a queen; Black may choose any of the four promotion pieces.

This fallback does no multi-move search. It can overlook tactics, mates, and
beneficial exchanges. The implementation does not claim a certified game
value or a complete perfect strategy.

See [PROVENANCE.md](PROVENANCE.md) for engine and book provenance.

## Font execution and transport

The font carries a 53-glyph record: a state, a last-move marker, 25 scratch
cells, 25 displayed cells, and a quiet-move counter. A forward transition
copies the previous board, validates Black's move, selects White's reply,
and tests whether Black has any legal response. Candidate king-safety tests
inspect the resulting board, including discovered attacks and pins. Opening
positions use a small decision tree rather than a linear book scan. One
cleanup pass hides complete older records and leaves only the final board.

The bundled TTF is 4,463,004 bytes, with 7,433 glyphs and 2,682 lookups.

Use the encoder in [`protocol.py`](protocol.py) or `gardnerText()` in
[`controls.js`](controls.js). It frames the source with U+E000/U+E001, maps
printable ASCII to U+E100 plus its character code, and substitutes a rejection
token for unsupported characters. It also inserts **64 inert space tokens per
source character, plus 64**, before the end sentinel. The font removes these
spaces first; they supply enough initial input length for HarfBuzz's shaping
operation budget on longer histories. They never appear in the visible record
and carry no moves or rules. Short raw ASCII examples may shape without this
padding; complete games must use the encoder.

Enable `liga`, with no kerning or letter/word spacing, and keep the complete
program in one left-to-right shaping run. The board advances 1,800 units. One
status glyph adds:

| Extra advance | Meaning |
| --- | --- |
| 1 | Black to move |
| 2 | Font checkmates |
| 3 | Black checkmates |
| 4 | Illegal move |
| 5 | Malformed source |
| 7 | Draw |

The browser measures at 1,000 px to read that status. It verifies shaping
support before enabling controls. No runtime engine, network request for a
move, strategy file, or installed font is required.

## Build and verify

Python 3.10+, FontTools with the HarfBuzz repacker, native HarfBuzz/`hb-shape`,
and Node.js are used:

```bash
python3 -m pip install -r games/gardner/requirements.txt
python3 games/gardner/build.py
python3 games/gardner/test_font.py -v
node games/gardner/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/gardner/playground.html>.
[Browser shaping checks](browser_check.html) test actual browser font metrics.
The builder accepts `--output PATH`, works from any directory, and replaces
the output only after the complete font has been serialized successfully.

The tests use real native HarfBuzz. They check every coordinate-pair input
after the opening, every stored book move, arbitrary positions outside the
book, all Black promotions, malformed/illegal input, quiet counters, complete
random games, and frozen terminal histories. Test-only cmap aliases expose
arbitrary positions without adding entry points to the shipped font. A separate
Python move generator supplies the legality reference. These are implementation
tests, not a formal proof of a perfect strategy.

To regenerate the book with an externally installed Gardner-capable
[Fairy-Stockfish](https://github.com/fairy-stockfish/Fairy-Stockfish) build:

```bash
python3 games/gardner/book.py --engine /absolute/path/to/stockfish
```

`--positions` and `--nodes` control the budgets. Normal font rebuilds use the
bundled book and do not run or download an engine.

Code, geometric piece artwork, and generated book are Apache 2.0. Text outlines
use the repository's pinned Apache-2.0 Roboto 2 fonts, with attribution retained
in the font metadata and root [third-party notices](../../THIRD_PARTY_NOTICES.md).

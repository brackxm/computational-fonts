# Wythoff’s Nim: a perfect opponent inside a font

[Play in your browser](playground.html). Two configurable heaps, one exact
opponent. On your turn take a positive number of tokens from one heap, or the
same positive number from both. **Whoever takes the last tokens wins.**

Every heap starts at **0–63**; at least one token must be present. All subsequent
positions are within that range, and the font implements the complete rules
and optimal outcome for every such starting position. Choose who moves first.
The default, 31 and 47 with the font first, is a forced win for the font.
Starting at 21 and 34 with the font first lets you beat it with correct play:
perfect play cannot rescue an initially losing position.

The font checks moves, updates heaps, chooses its own replies, and draws the
tokens and exact counts. Its latest reply is printed in gold: either the size
it left in a selected heap, both remaining sizes, or its one-token fallback
from a losing position. JavaScript only serializes input, keeps edit history,
and reads the font’s terminal advance signal.

## Input

Use two digits for all amounts and a semicolon after the header and each move:

```text
b31,47;            font first, initially 31 in A and 47 in B
h31,47;            human first, same starting heaps
b31,47;A01;        human takes 1 from A after the font’s opening
h01,01;D01;        human takes 1 from each and wins
```

The explanations after the spaces above are not part of the input. Append
**only human moves**: `A03;`, `B02;`, or `D04;`. `D` takes that amount from each
heap. Move amounts are 01–63. ASCII spaces, tabs, and line breaks are ignored,
including between digits. Invalid moves consume no tokens. Malformed input
shows the valid prefix, which may include a partially read starting position.
Terminal games freeze and ignore trailing input. No comments or other syntax
are supported.

Move buttons submit a candidate to the font and append it only if the font
accepts it. Manual edits show the font’s error status. An empty setup field is
rejected, rather than silently becoming a zero. Undo restores the previous
text. The playground accepts at most 1,024 source characters and clears stale
results as soon as editing starts.

## Exact strategy and compact representation

For sorted heap sizes `a ≤ b`, put `n = b − a`. The position is losing exactly
when `a = floor(n φ)`, where `φ = (1 + sqrt(5))/2`. The generator calculates this
without floating point as `(n + isqrt(5*n*n)) // 2`. See
[Nivasch’s exposition](https://www.gabrielnivasch.org/fun/combinatorial-games/wythoff)
and the standard-game definition in
[Hu, Sleator and Tsin](https://arxiv.org/abs/2408.02851).

The GSUB strategy first tries a losing position on the same row, then the same
column, then the same diagonal. A hidden register stores `63 + B − A`; two
small lookup stages rebuild it from the heap registers. This lets the font
recognize a diagonal using the difference and one heap, instead of storing a
decision for every pair of heap sizes. Each nonzero winning position has a
legal move to a losing one. At a losing position all moves have the same
losing outcome, so the deterministic fallback takes one token from A.

There is no runtime search or external engine. The strategy is generated from
the rules and the formula; no external table or artwork is embedded. The
bundled TTF contains **1,239 glyphs, 2,696 GSUB lookups, and 674,032 bytes**.
Heap art uses independent registers for 64 counts on each side, rather than a
whole-board glyph for every combination. Sixty-five shaping passes cover all
legal histories, since each move removes at least one of at most 126 tokens.

## Font protocol

The source is framed by U+E000 / U+E001. The browser maps each printable ASCII
character to U+E100 plus its code to keep a single left-to-right shaping run.
Unsupported Unicode, including reserved transport characters, maps to a DEL
rejection token. The font also maps direct ASCII for command-line use:

```bash
hb-shape games/wythoff/wythoff-font.ttf --text=$'\ue000b31,47;A01;\ue001'
```

Enable `liga`, with zero letter/word spacing and no kerning. The frame advances
1,800 font units; a final status contributes the following extra advance:

| Extra advance | Meaning |
| --- | --- |
| 1 | Human’s turn |
| 2 | Font wins |
| 3 | Human wins |
| 4 | Invalid move or empty starting position |
| 5 | Malformed input |
| 6 | Reserved internal error |

Require one final status. The playground probes at 1,000 px, making each font
unit one CSS pixel, and verifies actual shaping support before enabling play.
Colors use COLRv0; monochrome outlines also work. A host that splits the source
across shaping runs or disables standard ligatures cannot run the game.

## Build and verify

Python 3.10+, FontTools, native HarfBuzz, `hb-shape`, and Node.js are used:

```bash
python3 -m pip install fonttools
python3 games/wythoff/build.py
python3 games/wythoff/test_font.py -v
node games/wythoff/test_controls.cjs
python3 -m http.server 8000
```

Open <http://localhost:8000/games/wythoff/playground.html>. The default output is
beside the builder regardless of the current directory. `--output` selects a
different file. Importing the builder does not generate anything.

Tests compare the integer formula and policy with an independent complete
dynamic-programming solution, and check 10,000 cold pairs using a greedy mex
construction. Native HarfBuzz checks every starting position with each player
first, every move amount and its boundary errors, 200 complete seeded games,
the longest legal history against this policy, terminal freezing, and metadata.
Controller tests use real font measurements for legal/illegal moves, both
outcomes, Undo, edited histories, limits, and failed font loading. Browser
verification covers the artwork, controls, and counts. Rebuilt tables match
the bundled artifact apart from timestamp fields.

`../shared/fontgame.py`, `game-controls.js`, and the test drivers supply reusable
font construction, text transport, and native shaping. They contain no rules
or strategy for this game. All code, strategy data and artwork are
original, licensed under Apache 2.0.

Titles, coordinates, and status labels use original, proportional
[Game Sans](../shared/fonts/game-sans/readme.md) Regular and Bold outlines, baked
into the font by [`game_text.py`](../shared/game_text.py). The lettering is
Copyright 2026 Michael Brackx, Apache 2.0; no third-party font outlines are used.
